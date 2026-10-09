# Warehouse source plugins

This tree holds warehouse source plugins. Team warehouse-sources owns it.
New plugin vendors go here, not under `products/warehouse_sources/backend/temporal/data_imports/sources/`.
Vendors that other code imports (core-coupled vendors) stay in the product.

## One directory is one vendor

```text
sources/<vendor>/
  __init__.py      # required: tach, grimp and pytest only see regular packages
  source.py        # the source class, registered with SourceRegistry
  _config.py       # generated config (pnpm generate:source-configs); marks the directory as a plugin
  icon.png
  tests/
    __init__.py
    test_<vendor>.py
```

The loader finds `sources/<vendor>/source.py` on its own.
A vendor needs no line in `_load_all.py`, `generated_configs/` or the `ExternalDataSourceType` enum.
Write the first `_config.py` by hand (copy the shape of `demo_acme/_config.py`), then let the generator keep it current.

## A vendor imports only `sources.sdk`

A vendor directory imports shared code only from `sources.sdk`.
It does not import `posthog`, `products` or another vendor.
`hogli lint:tach` enforces this (`sources.*` in `tach.toml`).
Third-party libraries (for example `requests`) and the standard library are allowed.

`sources/sdk` re-exports the shared source code that still lives in `products/warehouse_sources`.
Add a name to the SDK only when it imports without Django, dlt or pyarrow.

## Tests run without services

Vendor tests do not use Django, a database, Redis or the network.

```sh
hogli test sources/                                            # uses sources/pytest.ini
pytest -c sources/pytest.ini --confcutdir=sources sources/     # same, without hogli
```

`--confcutdir=sources` keeps the root `conftest.py` (Django) out.
`sources/conftest.py` caps `time.sleep` so retry backoff does not run at real duration.
