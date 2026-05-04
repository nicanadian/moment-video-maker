"""Lookup adapters by ``"<provider>:<model>"`` shorthand.

Adapters are constructed lazily so that an SDK missing for one provider
doesn't break another. ``resolve_text("gemini:gemini-2.5-flash")`` returns
a ready-to-call instance.
"""

from __future__ import annotations

from solypsizm_moment_studio.providers.protocols import (
    ImageProvider,
    TextProvider,
    VideoProvider,
)


def _split(spec: str) -> tuple[str, str]:
    if ":" not in spec:
        raise ValueError(
            f"Provider spec must be 'provider:model' (got {spec!r}). "
            "Examples: 'gemini:gemini-2.5-flash', 'openai:gpt-image-1', "
            "'openrouter:anthropic/claude-opus-4.7'."
        )
    provider, model = spec.split(":", 1)
    return provider.strip().lower(), model.strip()


def resolve_text(spec: str) -> TextProvider:
    provider, model = _split(spec)
    if provider == "openai":
        from solypsizm_moment_studio.providers.adapters.openai_adapter import OpenAITextAdapter
        return OpenAITextAdapter(model_id=model)
    if provider == "gemini":
        from solypsizm_moment_studio.providers.adapters.gemini_adapter import GeminiTextAdapter
        return GeminiTextAdapter(model_id=model)
    if provider == "openrouter":
        from solypsizm_moment_studio.providers.adapters.openrouter_adapter import (
            OpenRouterTextAdapter,
        )
        return OpenRouterTextAdapter(model_id=model)
    raise ValueError(f"Unknown text provider {provider!r}.")


def resolve_image(spec: str) -> ImageProvider:
    provider, model = _split(spec)
    if provider == "openai":
        from solypsizm_moment_studio.providers.adapters.openai_adapter import OpenAIImageAdapter
        return OpenAIImageAdapter(model_id=model)
    if provider == "gemini":
        from solypsizm_moment_studio.providers.adapters.gemini_adapter import GeminiImageAdapter
        return GeminiImageAdapter(model_id=model)
    raise ValueError(f"Unknown image provider {provider!r}.")


def resolve_video(spec: str) -> VideoProvider:
    provider, model = _split(spec)
    if provider == "gemini":
        from solypsizm_moment_studio.providers.adapters.gemini_adapter import GeminiVideoAdapter
        return GeminiVideoAdapter(model_id=model)
    if provider == "openai":
        from solypsizm_moment_studio.providers.adapters.openai_adapter import OpenAIVideoAdapter
        return OpenAIVideoAdapter(model_id=model)
    raise ValueError(f"Unknown video provider {provider!r}.")


# Sensible v1 defaults — overridable per project / per call once benchmarks land.
DEFAULT_TEXT = "gemini:gemini-2.5-flash"
DEFAULT_JUDGE = "gemini:gemini-2.5-flash"
DEFAULT_IMAGE = "openai:gpt-image-1"
DEFAULT_VIDEO = "gemini:veo-3"
