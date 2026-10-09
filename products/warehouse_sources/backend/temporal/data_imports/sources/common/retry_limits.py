def retry_budget_seconds() -> float:
    """The longest time one request may spend on retries, from its first failure."""
    from django.conf import settings  # noqa: PLC0415 — keeps Django off the import path of a source

    return settings.DATA_WAREHOUSE_SOURCE_RETRY_BUDGET_SECONDS


def max_retry_after_seconds() -> float:
    """The longest server-provided retry delay that shared code waits for."""
    from django.conf import settings  # noqa: PLC0415 — keeps Django off the import path of a source

    return settings.DATA_WAREHOUSE_SOURCE_MAX_RETRY_AFTER_SECONDS
