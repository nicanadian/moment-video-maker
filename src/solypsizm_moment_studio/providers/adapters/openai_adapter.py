"""OpenAI adapter: text via Chat Completions, image via gpt-image-1.

Sora video is stubbed — full API access is uncertain as of v1; the adapter
raises ``ProviderUnavailable`` when called. Re-enable when access opens.

Auth:
- Prefer OAuth: the ``openai`` SDK reads ``~/.openai/auth.json``
  automatically when no API key is set. Run ``openai oauth login`` once.
- Fall back to ``OPENAI_API_KEY`` env var or our credentials file.
"""

from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any

from solypsizm_moment_studio.providers import pricing, secrets
from solypsizm_moment_studio.providers.exceptions import (
    ProviderError,
    ProviderRateLimited,
    ProviderRefused,
    ProviderUnavailable,
)
from solypsizm_moment_studio.providers.results import (
    CompletionResult,
    ImageResult,
    VideoResult,
)


def _client():
    """Lazy-import the OpenAI SDK and build a client. Falls back to OAuth
    if no API key is found (SDK reads ~/.openai/auth.json itself)."""
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ProviderUnavailable(
            "openai SDK not installed. Run `pip install -e '.[api]'`."
        ) from e
    api_key = secrets.openai_credential()
    # If api_key is None, the SDK will look for OAuth tokens / OPENAI_API_KEY
    # automatically. Don't pass api_key=None explicitly — the SDK rejects it.
    if api_key:
        return OpenAI(api_key=api_key)
    return OpenAI()


def _translate_sdk_error(exc: Exception) -> ProviderError:
    """Map openai SDK errors to our typed hierarchy."""
    name = type(exc).__name__
    msg = str(exc)
    if "RateLimit" in name:
        return ProviderRateLimited(msg)
    if "ContentPolicy" in name or "Moderation" in name or "BadRequest" in name and "policy" in msg.lower():
        return ProviderRefused(msg)
    if "APIConnection" in name or "ServiceUnavailable" in name or "InternalServer" in name:
        return ProviderUnavailable(msg)
    return ProviderError(f"{name}: {msg}")


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------


class OpenAITextAdapter:
    provider = "openai"

    def __init__(self, model_id: str) -> None:
        self.model_id = model_id

    def complete(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> CompletionResult:
        client = _client()
        start = time.monotonic()
        try:
            kwargs: dict[str, Any] = {
                "model": self.model_id,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": temperature,
            }
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens
            response = client.chat.completions.create(**kwargs)
        except Exception as e:
            raise _translate_sdk_error(e) from e
        latency_ms = int((time.monotonic() - start) * 1000)

        text = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        in_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        out_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
        cost = pricing.text_cost(f"openai/{self.model_id}", in_tokens, out_tokens)

        return CompletionResult(
            text=text,
            cost_usd=cost,
            latency_ms=latency_ms,
            provider=self.provider,
            model_id=self.model_id,
            raw_response={"id": response.id, "usage": {"in": in_tokens, "out": out_tokens}},
        )


# ---------------------------------------------------------------------------
# Image
# ---------------------------------------------------------------------------


class OpenAIImageAdapter:
    provider = "openai"

    def __init__(self, model_id: str = "gpt-image-1", quality: str = "med") -> None:
        self.model_id = model_id
        self.quality = quality  # low | med | high

    def generate(
        self,
        prompt: str,
        out_path: Path,
        *,
        reference: Path | None = None,
        size: str = "1024x1792",
        seed: int | None = None,
    ) -> ImageResult:
        client = _client()
        start = time.monotonic()
        try:
            if reference is not None and reference.is_file():
                # Use images.edit for reference-anchored generation.
                with reference.open("rb") as f:
                    response = client.images.edit(
                        model=self.model_id,
                        image=f,
                        prompt=prompt,
                        size=size,
                    )
            else:
                response = client.images.generate(
                    model=self.model_id,
                    prompt=prompt,
                    size=size,
                    quality={"low": "low", "med": "medium", "high": "high"}.get(
                        self.quality, "medium"
                    ),
                )
        except Exception as e:
            raise _translate_sdk_error(e) from e
        latency_ms = int((time.monotonic() - start) * 1000)

        # Extract bytes (base64-encoded by default for gpt-image-1).
        data = response.data[0]
        b64 = getattr(data, "b64_json", None)
        if b64:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(base64.b64decode(b64))
        else:
            # Fallback: download via URL.
            url = getattr(data, "url", None)
            if not url:
                raise ProviderError("OpenAI returned no image data.")
            import urllib.request
            with urllib.request.urlopen(url) as resp:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(resp.read())

        cost = pricing.image_cost(f"openai/{self.model_id}-{self.quality}")
        return ImageResult(
            image_path=str(out_path),
            cost_usd=cost,
            latency_ms=latency_ms,
            provider=self.provider,
            model_id=self.model_id,
            raw_response={"size": size, "quality": self.quality},
        )


# ---------------------------------------------------------------------------
# Video (Sora — stubbed until API access opens)
# ---------------------------------------------------------------------------


class OpenAIVideoAdapter:
    provider = "openai"

    def __init__(self, model_id: str = "sora") -> None:
        self.model_id = model_id

    def generate(
        self,
        prompt: str,
        out_path: Path,
        *,
        start_frame: Path | None = None,
        end_frame: Path | None = None,
        duration_seconds: float = 6.0,
        seed: int | None = None,
    ) -> VideoResult:
        raise ProviderUnavailable(
            "OpenAI Sora API is not wired in v1 — access is still limited. "
            "Use `gemini:veo-3` for video generation."
        )
