"""Provider protocols (PEP 544 structural typing — no inheritance required).

Adapters in ``providers/adapters/`` implement these. Callers depend only on
the protocol, not the concrete adapter.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from solypsizm_moment_studio.providers.results import (
    CompletionResult,
    ImageResult,
    VideoResult,
)


@runtime_checkable
class TextProvider(Protocol):
    """Concept brainstorm + scene breakdown + judge scoring."""

    provider: str  # "openai" / "gemini" / "openrouter"
    model_id: str  # e.g. "gpt-5", "gemini-2.5-flash", "anthropic/claude-opus-4-7"

    def complete(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> CompletionResult: ...


@runtime_checkable
class ImageProvider(Protocol):
    """Start / end keyframe generation. ``reference`` is the brand-locked
    avatar PNG; adapters that don't accept references should still preserve
    the call but signal lower fidelity in the benchmark."""

    provider: str
    model_id: str

    def generate(
        self,
        prompt: str,
        out_path: Path,
        *,
        reference: Path | None = None,
        size: str = "1024x1792",  # vertical 9:16 aspect by default
        seed: int | None = None,
    ) -> ImageResult: ...


@runtime_checkable
class VideoProvider(Protocol):
    """Motion clip generation between two keyframes (Veo 3 native pattern).

    Some providers only accept a text prompt without start/end frames; they
    receive the same call signature and ignore the frames.
    """

    provider: str
    model_id: str

    def generate(
        self,
        prompt: str,
        out_path: Path,
        *,
        start_frame: Path | None = None,
        end_frame: Path | None = None,
        duration_seconds: float = 6.0,
        seed: int | None = None,
    ) -> VideoResult: ...
