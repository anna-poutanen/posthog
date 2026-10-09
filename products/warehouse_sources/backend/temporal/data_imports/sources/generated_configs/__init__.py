# Hand-written resolver for the generated per-source config modules in this package.
# `pnpm generate:source-configs` (re)writes the per-source modules; it never touches this file.
import importlib
import importlib.util

from products.warehouse_sources.backend.temporal.data_imports.sources import PLUGIN_PACKAGE, source_module_path
from products.warehouse_sources.backend.temporal.data_imports.sources.common.config import Config
from products.warehouse_sources.backend.types import ExternalDataSourceType

_PRODUCT_SOURCES_PACKAGE = "products.warehouse_sources.backend.temporal.data_imports.sources"


def _module_exists(module_name: str) -> bool:
    # find_spec imports the parent package, and raises when that package does not exist.
    try:
        return importlib.util.find_spec(module_name) is not None
    except ModuleNotFoundError:
        return False


def _config_module_name(source: ExternalDataSourceType) -> str:
    source_module = source_module_path(source)
    if source_module is not None:
        vendor_dir = source_module.split(".")[-2]
        for plugin_config_module in (
            f"{PLUGIN_PACKAGE}.{vendor_dir}._config",
            f"{_PRODUCT_SOURCES_PACKAGE}.{vendor_dir}._config",
        ):
            if _module_exists(plugin_config_module):
                return plugin_config_module
    return f"{__package__}.{source.name.lower()}"


def get_config_for_source(source: ExternalDataSourceType) -> type[Config]:
    """Resolve a source's generated config class.

    Module and class names are derived from the enum member (`<name.lower()>.py`,
    `<value>SourceConfig`) — the same rule the generator uses to emit them — so adding a
    source needs no change here. Static importers should import the class from its
    per-source module directly (e.g. `from ...generated_configs.stripe import
    StripeSourceConfig`).

    DEMO (warehouse source plugins): a plugin directory keeps its config next to its code, in
    `<source dir>/_config.py`. Look in the top-level `sources/<vendor>/` first, then in the
    vendor directory of this product, then here.
    """
    module = importlib.import_module(_config_module_name(source))
    return getattr(module, f"{source}SourceConfig")
