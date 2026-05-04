"""High-level entry points: ``call_text``, ``call_image``, ``call_video``.

Wraps adapter calls in three things every caller needs:
- **Cache lookup** (free hit on repeats; $0 cost recorded as cache_hit).
- **Budget reservation** (refuse with BudgetExceeded if daily cap is hit).
- **Budget recording** (post-call ledger entry).

Adapters themselves are dumb — they just call the SDK and report. Cost
guards and persistence live here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from solypsizm_moment_studio.providers import cache as _cache
from solypsizm_moment_studio.providers import cost, pricing, registry
from solypsizm_moment_studio.providers.results import (
    CompletionResult,
    ImageResult,
    VideoResult,
)


def call_text(
    project_root: Path,
    spec: str,
    *,
    system: str,
    user: str,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> CompletionResult:
    provider, model = spec.split(":", 1)
    params = {"temperature": temperature, "max_tokens": max_tokens}

    cached = _cache.lookup_text(
        project_root, provider=provider, model=model, prompt=f"{system}\n\n{user}", params=params
    )
    if cached is not None:
        cached["cache_hit"] = True
        cached["cost_usd"] = 0.0
        return CompletionResult.model_validate(cached)

    # Budget-reserve a conservative estimate. Text calls are cheap; we use
    # a static $0.10 reservation that's tight enough to flag big spend
    # spikes early but loose enough not to refuse 99% of calls.
    cost.reserve(0.10, model=spec, kind="text")

    adapter = registry.resolve_text(spec)
    result = adapter.complete(
        system=system, user=user, temperature=temperature, max_tokens=max_tokens
    )

    cost.record(result.cost_usd, model=spec, kind="text", latency_ms=result.latency_ms)
    _cache.store_text(
        project_root,
        provider=provider,
        model=model,
        prompt=f"{system}\n\n{user}",
        result=result.model_dump(),
        params=params,
    )
    return result


def call_image(
    project_root: Path,
    spec: str,
    *,
    prompt: str,
    out_path: Path,
    reference: Path | None = None,
    size: str = "1024x1792",
    seed: int | None = None,
) -> ImageResult:
    provider, model = spec.split(":", 1)
    params = {"size": size, "seed": seed}

    cached = _cache.lookup_artifact(
        project_root,
        provider=provider,
        model=model,
        kind="image",
        prompt=prompt,
        params=params,
        reference_path=reference,
    )
    if cached is not None:
        cached_path, meta = cached
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path != cached_path:
            import shutil
            shutil.copy2(cached_path, out_path)
        return ImageResult(
            image_path=str(out_path),
            cost_usd=0.0,
            latency_ms=meta.get("latency_ms", 0),
            provider=provider,
            model_id=model,
            cache_hit=True,
            raw_response=meta.get("raw_response", {}),
        )

    cost.reserve(pricing.image_cost(f"{provider}/{model}") or 0.20, model=spec, kind="image")

    adapter = registry.resolve_image(spec)
    result = adapter.generate(
        prompt=prompt, out_path=out_path, reference=reference, size=size, seed=seed
    )

    cost.record(result.cost_usd, model=spec, kind="image", latency_ms=result.latency_ms)
    _cache.store_artifact(
        project_root,
        provider=provider,
        model=model,
        kind="image",
        prompt=prompt,
        artifact_source=Path(result.image_path),
        metadata=result.model_dump(),
        params=params,
        reference_path=reference,
    )
    return result


def call_video(
    project_root: Path,
    spec: str,
    *,
    prompt: str,
    out_path: Path,
    start_frame: Path | None = None,
    end_frame: Path | None = None,
    duration_seconds: float = 6.0,
    seed: int | None = None,
) -> VideoResult:
    provider, model = spec.split(":", 1)
    params = {"duration": duration_seconds, "seed": seed}
    # Hash the start frame as the reference for cache keying.
    ref = start_frame

    cached = _cache.lookup_artifact(
        project_root,
        provider=provider,
        model=model,
        kind="video",
        prompt=prompt,
        params=params,
        reference_path=ref,
    )
    if cached is not None:
        cached_path, meta = cached
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path != cached_path:
            import shutil
            shutil.copy2(cached_path, out_path)
        return VideoResult(
            video_path=str(out_path),
            cost_usd=0.0,
            latency_ms=meta.get("latency_ms", 0),
            provider=provider,
            model_id=model,
            cache_hit=True,
            raw_response=meta.get("raw_response", {}),
        )

    cost.reserve(
        pricing.video_cost(f"{provider}/{model}", duration_seconds) or 3.00,
        model=spec,
        kind="video",
    )

    adapter = registry.resolve_video(spec)
    result = adapter.generate(
        prompt=prompt,
        out_path=out_path,
        start_frame=start_frame,
        end_frame=end_frame,
        duration_seconds=duration_seconds,
        seed=seed,
    )

    cost.record(result.cost_usd, model=spec, kind="video", latency_ms=result.latency_ms)
    _cache.store_artifact(
        project_root,
        provider=provider,
        model=model,
        kind="video",
        prompt=prompt,
        artifact_source=Path(result.video_path),
        metadata=result.model_dump(),
        params=params,
        reference_path=ref,
    )
    return result
