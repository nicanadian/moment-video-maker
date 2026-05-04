"""Multi-provider API mode (PRD §12.2 + docs/projects/03-v2-api-and-automation.md).

Three protocols (text / image / video) with adapter implementations for
OpenAI (OAuth), Gemini (key), OpenRouter (key). All routed through:

- ``BudgetGuard`` — daily $40 cap with persisted spend tracking.
- ``Cache`` — per-project idempotent cache keyed by (provider, model,
  prompt, params, reference-hash).
- ``secrets`` — env vars first, then ``~/.solypsizm/credentials.json``.
"""

from solypsizm_moment_studio.providers.exceptions import (
    BudgetExceeded,
    ProviderError,
    ProviderRateLimited,
    ProviderRefused,
    ProviderUnavailable,
)
from solypsizm_moment_studio.providers.protocols import (
    ImageProvider,
    TextProvider,
    VideoProvider,
)
from solypsizm_moment_studio.providers.results import (
    CompletionResult,
    ImageResult,
    VideoResult,
)

__all__ = [
    "BudgetExceeded",
    "CompletionResult",
    "ImageProvider",
    "ImageResult",
    "ProviderError",
    "ProviderRateLimited",
    "ProviderRefused",
    "ProviderUnavailable",
    "TextProvider",
    "VideoProvider",
    "VideoResult",
]
