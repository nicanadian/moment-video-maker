"""Provider exception hierarchy. Adapters translate SDK-specific errors into these."""


class ProviderError(Exception):
    """Base class for any provider-call failure."""


class ProviderRateLimited(ProviderError):
    """The provider returned a rate-limit response. Retry with backoff."""


class ProviderRefused(ProviderError):
    """Content policy / safety / moderation blocked the request. Don't auto-retry."""


class ProviderUnavailable(ProviderError):
    """Provider returned 5xx, network failed, model not found. Backoff or fall back."""


class BudgetExceeded(ProviderError):
    """The pre-call budget check refused this call. Daily cap or per-run cap was hit."""
