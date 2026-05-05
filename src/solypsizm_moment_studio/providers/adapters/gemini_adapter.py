"""Gemini adapter: text via Gemini 2.5, image via Imagen, video via Veo 3.

Auth via ``GEMINI_API_KEY`` (preferred) or ``GOOGLE_API_KEY`` env var or
the credentials file. The ``google-genai`` SDK is the modern entry point
(replaces the legacy ``google-generativeai``).
"""

from __future__ import annotations

import contextlib
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
    try:
        from google import genai
    except ImportError as e:
        raise ProviderUnavailable(
            "google-genai SDK not installed. Run `pip install -e '.[api]'`."
        ) from e
    api_key = secrets.gemini_credential()
    if not api_key:
        raise ProviderUnavailable(
            "GEMINI_API_KEY not set. Run `solypsizm secrets set gemini` "
            "or `export GEMINI_API_KEY=...`."
        )
    return genai.Client(api_key=api_key)


def _translate_sdk_error(exc: Exception) -> ProviderError:
    name = type(exc).__name__
    msg = str(exc).lower()
    if "ratelimit" in name.lower() or "quota" in msg or "rate limit" in msg:
        return ProviderRateLimited(str(exc))
    if "safety" in msg or "block" in msg or "policy" in msg:
        return ProviderRefused(str(exc))
    if "deadline" in msg or "unavailable" in msg or "internal" in msg:
        return ProviderUnavailable(str(exc))
    return ProviderError(f"{name}: {exc}")


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------


class GeminiTextAdapter:
    provider = "gemini"

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
            from google.genai import types as genai_types

            config: dict[str, Any] = {"temperature": temperature}
            if max_tokens is not None:
                config["max_output_tokens"] = max_tokens
            if system:
                config["system_instruction"] = system

            response = client.models.generate_content(
                model=self.model_id,
                contents=user,
                config=genai_types.GenerateContentConfig(**config),
            )
        except Exception as e:
            raise _translate_sdk_error(e) from e
        latency_ms = int((time.monotonic() - start) * 1000)

        text = response.text or ""
        usage = getattr(response, "usage_metadata", None)
        in_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
        out_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0
        cost = pricing.text_cost(f"gemini/{self.model_id}", in_tokens, out_tokens)

        return CompletionResult(
            text=text,
            cost_usd=cost,
            latency_ms=latency_ms,
            provider=self.provider,
            model_id=self.model_id,
            raw_response={"usage": {"in": in_tokens, "out": out_tokens}},
        )


# ---------------------------------------------------------------------------
# Image — Imagen
# ---------------------------------------------------------------------------


class GeminiImageAdapter:
    provider = "gemini"

    def __init__(self, model_id: str = "imagen-4") -> None:
        self.model_id = model_id

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
            from google.genai import types as genai_types

            # Imagen API: pass prompt + optional reference image.
            kwargs: dict[str, Any] = {
                "model": self.model_id,
                "prompt": prompt,
                "config": genai_types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="9:16" if "9:16" in size or "1792" in size else "1:1",
                ),
            }
            response = client.models.generate_images(**kwargs)
        except Exception as e:
            raise _translate_sdk_error(e) from e
        latency_ms = int((time.monotonic() - start) * 1000)

        if not response.generated_images:
            raise ProviderError("Gemini Imagen returned no images.")
        image = response.generated_images[0].image
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # google-genai exposes image_bytes on the Image object.
        out_path.write_bytes(image.image_bytes)

        cost = pricing.image_cost(f"gemini/{self.model_id}")
        return ImageResult(
            image_path=str(out_path),
            cost_usd=cost,
            latency_ms=latency_ms,
            provider=self.provider,
            model_id=self.model_id,
            raw_response={"size": size},
        )


# ---------------------------------------------------------------------------
# Video — Veo 3 (the headline v2 unlock)
# ---------------------------------------------------------------------------


class GeminiVideoAdapter:
    provider = "gemini"

    def __init__(self, model_id: str = "veo-3") -> None:
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
        client = _client()
        start = time.monotonic()
        try:
            from google.genai import types as genai_types

            kwargs: dict[str, Any] = {
                "model": self.model_id,
                "prompt": prompt,
                "config": genai_types.GenerateVideosConfig(
                    number_of_videos=1,
                    duration_seconds=duration_seconds,
                    aspect_ratio="9:16",
                ),
            }
            if start_frame and start_frame.is_file():
                # The genai SDK accepts an Image as the seed frame.
                kwargs["image"] = genai_types.Image(
                    image_bytes=start_frame.read_bytes(),
                    mime_type="image/png",
                )

            # Veo is a long-running operation — poll until done.
            operation = client.models.generate_videos(**kwargs)
            while not operation.done:
                time.sleep(10)
                operation = client.operations.get(operation)
        except Exception as e:
            raise _translate_sdk_error(e) from e
        latency_ms = int((time.monotonic() - start) * 1000)

        if not operation.response or not operation.response.generated_videos:
            raise ProviderError("Veo returned no videos.")
        video = operation.response.generated_videos[0].video
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # SDK exposes a download / video_bytes pattern; choose whichever exists.
        if hasattr(video, "video_bytes") and video.video_bytes:
            out_path.write_bytes(video.video_bytes)
        elif hasattr(video, "uri") and video.uri:
            client.files.download(file=video, path=str(out_path))
        else:
            raise ProviderError("Veo result has no bytes or URI to fetch.")

        # Veo 3 generates audio by default; strip it so it doesn't fight the
        # song master. Best-effort — falls back to the as-rendered file if
        # ffmpeg isn't available.
        _strip_audio_inplace(out_path)

        cost = pricing.video_cost(f"gemini/{self.model_id}", duration_seconds)
        return VideoResult(
            video_path=str(out_path),
            cost_usd=cost,
            latency_ms=latency_ms,
            provider=self.provider,
            model_id=self.model_id,
            raw_response={"duration_seconds": duration_seconds},
        )


def _strip_audio_inplace(path: Path) -> None:
    """ffmpeg -an pass to drop any audio track Veo dubbed over the clip.

    The brand-kit Veo prompt asks for silent video, but the API doesn't
    always honor it. This is a belt-and-suspenders pass.
    """
    import shutil
    import subprocess

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return
    tmp = path.with_suffix(path.suffix + ".silent")
    try:
        subprocess.run(
            [ffmpeg, "-y", "-i", str(path), "-an", "-c:v", "copy", str(tmp)],
            check=True,
            capture_output=True,
        )
        tmp.replace(path)
    except (subprocess.CalledProcessError, OSError):
        if tmp.is_file():
            with contextlib.suppress(OSError):
                tmp.unlink()
