"""Typed results from each provider call.

Every adapter returns one of these. ``cost_usd`` is computed from the pricing
table at call time, not extracted from the SDK response (most SDKs don't
report cost). ``raw_response`` is kept for debugging — adapters should never
strip it.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CompletionResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    text: str
    cost_usd: float
    latency_ms: int
    provider: str
    model_id: str
    cache_hit: bool = False
    raw_response: dict[str, Any] = Field(default_factory=dict)


class ImageResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    # Path to the saved PNG/JPEG on disk (adapter writes the bytes).
    image_path: str
    cost_usd: float
    latency_ms: int
    provider: str
    model_id: str
    cache_hit: bool = False
    raw_response: dict[str, Any] = Field(default_factory=dict)


class VideoResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    # Path to the saved MP4/WebM on disk.
    video_path: str
    cost_usd: float
    latency_ms: int
    provider: str
    model_id: str
    cache_hit: bool = False
    raw_response: dict[str, Any] = Field(default_factory=dict)
