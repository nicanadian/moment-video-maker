"""OpenRouter adapter — uses the OpenAI-compatible client with a custom base
URL. Single key gives access to GPT-5, Claude Opus 4.7, Gemini 2.5,
DeepSeek V3, Llama 4, and many others. Useful for benchmarking text models
without managing a separate cred per vendor.

Image and video coverage is thinner; not implemented for v2 launch.
"""

from __future__ import annotations

import time
from typing import Any

from solypsizm_moment_studio.providers import pricing, secrets
from solypsizm_moment_studio.providers.exceptions import (
    ProviderError,
    ProviderRateLimited,
    ProviderRefused,
    ProviderUnavailable,
)
from solypsizm_moment_studio.providers.results import CompletionResult


def _client():
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ProviderUnavailable(
            "openai SDK not installed (used by OpenRouter as the transport). "
            "Run `pip install -e '.[api]'`."
        ) from e
    api_key = secrets.openrouter_credential()
    if not api_key:
        raise ProviderUnavailable(
            "OPENROUTER_API_KEY not set. Run `solypsizm secrets set openrouter` "
            "or `export OPENROUTER_API_KEY=...`."
        )
    return OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "https://github.com/nicanadian/moment-video-maker",
            "X-Title": "Solypsizm Moment Studio",
        },
    )


def _translate_sdk_error(exc: Exception) -> ProviderError:
    name = type(exc).__name__
    msg = str(exc).lower()
    if "ratelimit" in name.lower() or "429" in msg:
        return ProviderRateLimited(str(exc))
    if "policy" in msg or "moderation" in msg:
        return ProviderRefused(str(exc))
    if "5" in name and "Server" in name:
        return ProviderUnavailable(str(exc))
    return ProviderError(f"{name}: {exc}")


class OpenRouterTextAdapter:
    provider = "openrouter"

    def __init__(self, model_id: str) -> None:
        # OpenRouter model IDs include the vendor: "anthropic/claude-opus-4.7",
        # "openai/gpt-5", "google/gemini-2.5-pro", etc.
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
        cost = pricing.text_cost(f"openrouter/{self.model_id}", in_tokens, out_tokens)

        return CompletionResult(
            text=text,
            cost_usd=cost,
            latency_ms=latency_ms,
            provider=self.provider,
            model_id=self.model_id,
            raw_response={"id": getattr(response, "id", None), "usage": {"in": in_tokens, "out": out_tokens}},
        )
