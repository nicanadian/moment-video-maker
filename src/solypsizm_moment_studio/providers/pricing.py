"""Pricing table loader + per-call cost computation.

The table at ``pricing.json`` is keyed by ``"<provider>/<model>"`` for text
and image, with one row per (model, quality-tier) combination. Override at
runtime by setting ``SOLYPSIZM_PRICING`` to an alternate JSON path.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def _load_table() -> dict[str, Any]:
    override = os.environ.get("SOLYPSIZM_PRICING")
    if override:
        return json.loads(Path(override).read_text(encoding="utf-8"))
    raw = (
        files("solypsizm_moment_studio.providers")
        .joinpath("pricing.json")
        .read_text(encoding="utf-8")
    )
    return json.loads(raw)


def text_cost(model_key: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for a text completion. ``model_key`` is
    ``"<provider>/<model>"`` (or ``"openrouter/<vendor>/<model>"``).
    Returns 0.0 with a warning if the model isn't in the table."""
    table = _load_table().get("text", {})
    row = table.get(model_key)
    if not row:
        return 0.0
    return input_tokens / 1_000_000 * row.get(
        "input_per_1m", 0.0
    ) + output_tokens / 1_000_000 * row.get("output_per_1m", 0.0)


def image_cost(model_key: str) -> float:
    table = _load_table().get("image", {})
    row = table.get(model_key)
    if not row:
        return 0.0
    return float(row.get("per_image", 0.0))


def video_cost(model_key: str, duration_seconds: float) -> float:
    table = _load_table().get("video", {})
    row = table.get(model_key)
    if not row:
        return 0.0
    duration = max(duration_seconds, float(row.get("min_duration", 0.0)))
    return duration * float(row.get("per_second", 0.0))


def known_models() -> dict[str, list[str]]:
    """For diagnostics: which models the table knows about, by modality."""
    table = _load_table()
    return {
        "text": sorted(table.get("text", {}).keys()),
        "image": sorted(table.get("image", {}).keys()),
        "video": sorted(table.get("video", {}).keys()),
    }
