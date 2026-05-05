"""VLM-as-judge for benchmarks + auto-pipeline confidence gating.

Calls Gemini 2.5 Flash with the brand-locked reference image + the
generated artifact + a structured rubric prompt, returns a 0-10 score
per dimension. Total score is weighted (character fidelity 40%, prompt
25%, aesthetic 25%, quality 10%), scaled to 0-40 for easy threshold math.

Bypasses the dispatch layer because the judge needs multimodal input
(text + 2 images) which the TextProvider protocol doesn't model.
We can promote vision to a protocol method later if other providers join.
"""

from __future__ import annotations

import contextlib
import json
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from solypsizm_moment_studio.models import BrandKit
from solypsizm_moment_studio.providers import cost, secrets
from solypsizm_moment_studio.providers.exceptions import (
    ProviderError,
    ProviderUnavailable,
)

DEFAULT_JUDGE_MODEL = "gemini-2.5-flash"


class JudgeScore(BaseModel):
    model_config = ConfigDict(extra="allow")

    character_fidelity: float
    prompt_fidelity: float
    aesthetic_match: float
    quality: float
    justification: str = ""

    @property
    def total(self) -> float:
        """Weighted total scaled 0-40. Character fidelity dominates because
        brand consistency is the single biggest signal per the brand kit."""
        return (
            0.40 * self.character_fidelity
            + 0.25 * self.prompt_fidelity
            + 0.25 * self.aesthetic_match
            + 0.10 * self.quality
        ) * 4.0


def _build_image_judge_prompt(brand_kit: BrandKit, prompt_used: str) -> str:
    char = brand_kit.character
    return f"""You are scoring an AI-generated image for the Solypsizm music video brand.
The brand has a STRICT locked character (visor, jacket piping, etc.) and aesthetic.
Failures to preserve them are common and should score zero.

LOCKED CHARACTER (the avatar in image 1 is the canonical reference):
- Visor: {char.visor}
- Jacket: {char.jacket}
- Pants: {char.pants}
- Boots: {char.boots}
- Style: {char.style}

AESTHETIC:
- Palette: cyan #00D4FF (dominant), violet #8A2BE2, brand purple #5B2A86, crushed blacks
- Color grade: {" ".join(brand_kit.aesthetic.color_grade)}
- Lighting: {brand_kit.aesthetic.lighting_cues}

The model was asked to generate:
"{prompt_used}"

Two images are attached:
1. The LOCKED reference (canonical front view of the avatar — ground truth).
2. The GENERATED artifact to score.

Score the generated artifact (image 2) on these dimensions, 0-10 each:
- character_fidelity: does the character match the reference? Visor as a single horizontal
  cyan strip (NOT goggles, NOT sunglasses, NOT a helmet visor)? Jacket with hexagonal
  cyan+violet piping (NOT zigzag, NOT racing stripes)? Pants with side-seam piping?
  Combat boots? Score 0 if a different character, 10 if visually indistinguishable
  from reference.
- prompt_fidelity: does the scene match the prompt above? Score 0 if it generated
  something else entirely, 10 if every prompt element is present.
- aesthetic_match: cel-shaded anime (NOT photoreal)? Cyan+violet palette? Crushed
  blacks + neon rim lighting? Score 0 if photoreal or wrong palette, 10 if perfectly
  on-brand.
- quality: composition, sharp linework, no artifacts, no text/watermarks? Score 0 if
  visibly broken, 10 if professionally clean.

Reply with STRICT JSON only — no markdown fences, no prose:
{{
  "character_fidelity": <0-10>,
  "prompt_fidelity": <0-10>,
  "aesthetic_match": <0-10>,
  "quality": <0-10>,
  "justification": "<one sentence summary>"
}}
"""


def _build_video_judge_prompt(brand_kit: BrandKit, prompt_used: str) -> str:
    """Same structure but tweaked for motion clips. The judge sees the
    reference + a single thumbnail extracted from the video.
    """
    base = _build_image_judge_prompt(brand_kit, prompt_used)
    return base.replace(
        "Score the generated artifact (image 2)",
        "Score the generated motion clip (image 2 is a thumbnail from the clip)",
    ).replace(
        "no text/watermarks?",
        (
            "no text/watermarks? Veo clips frequently have a Veo watermark — "
            "penalize heavily if visible."
        ),
    )


def judge_image(
    brand_kit: BrandKit,
    reference_path: Path,
    artifact_path: Path,
    prompt_used: str,
    *,
    model: str = DEFAULT_JUDGE_MODEL,
) -> JudgeScore:
    """Score a generated image against the brand-locked reference."""
    return _judge_with_gemini(
        brand_kit,
        reference_path,
        artifact_path,
        _build_image_judge_prompt(brand_kit, prompt_used),
        kind="image",
        model=model,
    )


def judge_video(
    brand_kit: BrandKit,
    reference_path: Path,
    artifact_path: Path,
    prompt_used: str,
    *,
    model: str = DEFAULT_JUDGE_MODEL,
) -> JudgeScore:
    """Score a generated motion clip. Pulls a thumbnail at t=2s and
    judges that frame; not full motion analysis. Cheap proxy for v2."""
    thumb = _extract_thumbnail(artifact_path)
    if thumb is None:
        raise ProviderError(
            f"Could not extract a thumbnail from {artifact_path} (ffmpeg missing?)."
        )
    try:
        return _judge_with_gemini(
            brand_kit,
            reference_path,
            thumb,
            _build_video_judge_prompt(brand_kit, prompt_used),
            kind="video",
            model=model,
        )
    finally:
        with contextlib.suppress(OSError):
            thumb.unlink()


def _extract_thumbnail(video_path: Path) -> Path | None:
    """ffmpeg -ss 2 -frames:v 1 — pulls a single PNG at the 2s mark."""
    import shutil
    import subprocess
    import tempfile

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return None
    out = Path(tempfile.mkstemp(suffix=".png")[1])
    try:
        subprocess.run(
            [ffmpeg, "-y", "-ss", "2", "-i", str(video_path), "-frames:v", "1", str(out)],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError:
        out.unlink(missing_ok=True)
        return None
    return out


def _judge_with_gemini(
    brand_kit: BrandKit,
    reference_path: Path,
    artifact_path: Path,
    rubric_prompt: str,
    *,
    kind: str,
    model: str,
) -> JudgeScore:
    api_key = secrets.gemini_credential()
    if not api_key:
        raise ProviderUnavailable("GEMINI_API_KEY not set. Run `solypsizm secrets set gemini`.")
    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError as e:
        raise ProviderUnavailable(
            "google-genai SDK not installed. Run `pip install -e '.[api]'`."
        ) from e

    client = genai.Client(api_key=api_key)
    start = time.monotonic()

    contents = [
        genai_types.Part.from_bytes(
            reference_path.read_bytes(),
            mime_type=_mime_for(reference_path),
        ),
        genai_types.Part.from_bytes(
            artifact_path.read_bytes(),
            mime_type=_mime_for(artifact_path),
        ),
        rubric_prompt,
    ]
    try:
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=genai_types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            ),
        )
    except Exception as e:
        raise ProviderError(f"Judge call failed: {type(e).__name__}: {e}") from e
    latency_ms = int((time.monotonic() - start) * 1000)

    text = response.text or "{}"
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise ProviderError(f"Judge returned non-JSON: {text[:200]}") from e

    score = JudgeScore.model_validate(parsed)

    # Bookkeep cost. Judge cost is small but not zero; estimate from token
    # usage when SDK reports it, fall back to a flat estimate otherwise.
    usage = getattr(response, "usage_metadata", None)
    in_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
    out_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0
    from solypsizm_moment_studio.providers import pricing

    cost_usd = pricing.text_cost(f"gemini/{model}", in_tokens, out_tokens) or 0.001
    cost.record(cost_usd, model=f"gemini:{model}", kind=f"judge-{kind}", latency_ms=latency_ms)

    return score


def _mime_for(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(suffix, "image/png")
