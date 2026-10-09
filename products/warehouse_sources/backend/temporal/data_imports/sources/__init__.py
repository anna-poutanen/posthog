import functools
import importlib
import importlib.util
from pathlib import Path
from typing import Any

import structlog

from products.warehouse_sources.backend.types import ExternalDataSourceType

from .common.registry import SourceRegistry

__all__ = ["SourceRegistry", "load_all_sources", "load_source", "source_module_path"]

logger = structlog.get_logger(__name__)

# DEMO (warehouse source plugins): plugin vendors live in the top-level `sources` package, one
# directory per vendor, and register as `sources.<vendor>.source`.
PLUGIN_PACKAGE = "sources"


def load_all_sources() -> None:
    """Import every source module so each registers itself with ``SourceRegistry``.

    Deferred out of module scope so importing a leaf (e.g. ``sources.stripe.constants``)
    doesn't drag every vendor SDK at app startup. Importing ``_load_all`` runs each
    source module's ``@SourceRegistry.register`` decorator. Idempotent — re-imports are
    cheap dict lookups in ``sys.modules``.

    Best-effort: a source module that can't be imported is reported and skipped, leaving the
    rest of the catalog usable.
    """
    try:
        _bulk_load()
    except Exception:
        # `_load_all` is one flat import list, so a single unimportable source module aborts it
        # and leaves every later source unregistered — failing every sync and the whole sources
        # UI rather than just the offending source. Import the rest individually so one broken
        # vendor module costs only its own source.
        logger.exception("load_all_sources: bulk import failed, falling back to per-source import")
        for module_path in _source_module_paths():
            _load_source(module_path)


def _bulk_load() -> None:
    from . import _load_all  # noqa: F401, PLC0415

    for module_path in _plugin_module_paths():
        importlib.import_module(module_path)


def source_module_path(source_type: ExternalDataSourceType) -> str | None:
    """The source module that registers ``source_type``, or None when no directory matches.

    A source directory is the enum member's name in lowercase with underscores added
    (``BINGADS`` -> ``bing_ads``), so the lookup strips underscores from the directory names.
    A test asserts every registered source resolves this way.

    DEMO (warehouse source plugins): a plugin key with no enum member is its own name
    (``"DemoAcme"`` -> ``demo_acme``).
    """
    name = source_type.name if isinstance(source_type, ExternalDataSourceType) else source_type
    return _source_modules_by_squashed_name().get(name.lower())


def load_source(source_type: ExternalDataSourceType) -> None:
    """Import only the module that registers ``source_type``.

    Request paths ask the registry for a handful of source types, and importing every
    source module costs seconds per process, so they import just the modules they need.
    """
    module_path = source_module_path(source_type)
    if module_path is not None:
        _load_source(module_path)


@functools.cache
def _source_modules_by_squashed_name() -> dict[str, str]:
    return {path.rsplit(".", 2)[1].replace("_", ""): path for path in _source_module_paths()}


def _plugin_package_dir() -> Path | None:
    """The directory of the top-level `sources` package, or None when it is not importable."""
    spec = importlib.util.find_spec(PLUGIN_PACKAGE)
    if spec is None or not spec.submodule_search_locations:
        return None
    return Path(spec.submodule_search_locations[0])


def _top_level_plugin_module_paths() -> list[str]:
    plugin_dir = _plugin_package_dir()
    if plugin_dir is None:
        return []
    return sorted(f"{PLUGIN_PACKAGE}.{source.parent.name}.source" for source in plugin_dir.glob("*/source.py"))


def _source_module_paths() -> list[str]:
    """Every source module `_load_all` imports, derived from the directory layout.

    A test asserts this stays in step with `_load_all`'s import list.

    DEMO (warehouse source plugins): this also holds the vendors of the top-level `sources` package.
    """
    package_dir = Path(__path__[0])
    product_modules = [f"{__name__}.{source.parent.name}.source" for source in package_dir.glob("*/source.py")]
    return sorted(product_modules + _top_level_plugin_module_paths())


def _plugin_module_paths() -> list[str]:
    """Source modules of plugin directories, which keep their generated config in ``_config.py``.

    DEMO (warehouse source plugins): a plugin directory has no line in `_load_all`, so the bulk
    load imports these on their own. Every vendor of the top-level `sources` package is a plugin.
    A directory in this package with a ``_config.py`` is a plugin too.
    """
    package_dir = Path(__path__[0])
    product_plugins = [f"{__name__}.{config.parent.name}.source" for config in package_dir.glob("*/_config.py")]
    return sorted(product_plugins + _top_level_plugin_module_paths())


def _load_source(module_path: str) -> None:
    try:
        importlib.import_module(module_path)
    except Exception as e:
        logger.exception("load_all_sources: source module failed to import", module=module_path)
        if _should_capture_import_failure(e):
            from posthog.exceptions_capture import (
                capture_exception,  # noqa: PLC0415 — keeps Django off the import path of a source
            )

            capture_exception(e)


def _should_capture_import_failure(error: Exception) -> bool:
    """Whether an import failure is a broken source or an incomplete checkout.

    A missing module means the tree is incomplete: an interpreter without the source SDKs,
    or a source directory added before its generated config was written. A deploy has every
    SDK locked and every generated config committed, so only there does a missing module
    mean a source dropped out of the catalog. Any other error is module-level breakage,
    which counts wherever it happens.
    """
    if isinstance(error, ImportError):  # ModuleNotFoundError is a subclass
        from django.conf import settings  # noqa: PLC0415 — keeps Django off the import path of a source

        from posthog.run_mode import derive_run_mode  # noqa: PLC0415 — keeps Django off the import path of a source

        return derive_run_mode(settings.CLOUD_DEPLOYMENT, settings.DEBUG).is_deployed_cloud
    return True


def __getattr__(name: str) -> Any:
    # Back-compat: source classes used to be re-exported here. Resolve them lazily so
    # `from ...sources import StripeSource` keeps working without eager-loading every SDK.
    # Guard private/dunder names (including `_load_all` itself) to avoid recursing through
    # the very import we use to populate the namespace. Every re-exported class is a
    # `*Source`, so anything else is an attribute probe (pytest looking for `pytest_plugins`,
    # a `hasattr` check) that must not drag in 1200-odd vendor modules to answer.
    if name.startswith("_") or not name.endswith("Source"):
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from . import _load_all  # noqa: PLC0415

    try:
        return getattr(_load_all, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
