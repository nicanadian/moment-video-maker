"""Tests for the benchmark prompt-set parser, JudgeScore math, and the
report builder. Doesn't call the SDK — those paths run live during a real
benchmark.
"""

from __future__ import annotations

from pathlib import Path

from solypsizm_moment_studio.benchmark import (
    BenchmarkRecord,
    PromptSet,
    _build_report,
    _parse_prompt_set,
    estimate_cost,
)
from solypsizm_moment_studio.judge import JudgeScore


# ---------------------------------------------------------------------------
# Prompt-set parser
# ---------------------------------------------------------------------------


def test_parse_image_prompt_set(tmp_path) -> None:
    p = tmp_path / "image.yaml"
    p.write_text(
        """name: keyframe
modality: image
reference: character-reference/front.png
size: "1024x1792"
prompt: |
  Generate a vertical illustration.

  Multiple paragraphs supported.
""",
        encoding="utf-8",
    )
    ps = _parse_prompt_set(p)
    assert ps.name == "keyframe"
    assert ps.modality == "image"
    assert ps.reference == "character-reference/front.png"
    assert ps.size == "1024x1792"
    assert "Multiple paragraphs supported" in ps.prompt


def test_parse_video_prompt_set_with_duration(tmp_path) -> None:
    p = tmp_path / "video.yaml"
    p.write_text(
        """name: motion
modality: video
reference: character-reference/front.png
duration_seconds: 6.0
prompt: |
  Subject: walks forward.
""",
        encoding="utf-8",
    )
    ps = _parse_prompt_set(p)
    assert ps.duration_seconds == 6.0
    assert ps.modality == "video"


def test_parse_handles_quoted_size(tmp_path) -> None:
    p = tmp_path / "image.yaml"
    p.write_text(
        'name: x\nmodality: image\nreference: r.png\nsize: "9:16"\nprompt: |\n  a\n',
        encoding="utf-8",
    )
    ps = _parse_prompt_set(p)
    assert ps.size == "9:16"


# ---------------------------------------------------------------------------
# JudgeScore weighting
# ---------------------------------------------------------------------------


def test_judge_score_total_is_weighted() -> None:
    perfect = JudgeScore(
        character_fidelity=10, prompt_fidelity=10,
        aesthetic_match=10, quality=10, justification="great",
    )
    assert perfect.total == 40.0

    only_quality = JudgeScore(
        character_fidelity=0, prompt_fidelity=0,
        aesthetic_match=0, quality=10, justification="off-brand",
    )
    # Quality weight is 10% × 4 = 0.4 per point; max 4.
    assert only_quality.total == 4.0

    only_character = JudgeScore(
        character_fidelity=10, prompt_fidelity=0,
        aesthetic_match=0, quality=0, justification="on brand but wrong scene",
    )
    # Character weight is 40% × 4 = 1.6 per point; max 16.
    assert only_character.total == 16.0


def test_judge_score_extracts_extras() -> None:
    """Extra fields from the judge's JSON shouldn't break parsing."""
    score = JudgeScore.model_validate(
        {
            "character_fidelity": 8,
            "prompt_fidelity": 7,
            "aesthetic_match": 9,
            "quality": 6,
            "justification": "...",
            "extra_dim_added_later": 99,
        }
    )
    assert score.character_fidelity == 8
    assert score.total == (0.4 * 8 + 0.25 * 7 + 0.25 * 9 + 0.10 * 6) * 4


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


def test_estimate_cost_uses_max_per_artifact() -> None:
    ps = PromptSet(
        name="x", modality="image", reference="r.png",
        prompt="prompt", size="1024x1792",
    )
    # Max image cost in pricing.json among these is gpt-image-1-high $0.20.
    # Plus $0.005/judge × 2 specs × 2 takes = small total.
    est = estimate_cost(["openai:gpt-image-1-high", "gemini:imagen-3"], takes=2, prompt_set=ps)
    assert 0.4 < est < 1.0  # 0.205 × 4 = 0.82


# ---------------------------------------------------------------------------
# Report building
# ---------------------------------------------------------------------------


def test_report_sorts_by_score_then_cost() -> None:
    ps = PromptSet(
        name="keyframe", modality="image", reference="r.png", prompt="x",
    )
    a = BenchmarkRecord(
        spec="gemini:imagen-4", take=1, artifact_path="x", cost_usd=0.06, latency_ms=2000,
        score=JudgeScore(character_fidelity=8, prompt_fidelity=8,
                         aesthetic_match=8, quality=8, justification="good"),
    )
    b = BenchmarkRecord(
        spec="openai:gpt-image-1", take=1, artifact_path="x", cost_usd=0.04, latency_ms=3000,
        score=JudgeScore(character_fidelity=9, prompt_fidelity=9,
                         aesthetic_match=9, quality=9, justification="better"),
    )
    report = _build_report([a, b], ps)
    assert report.find("openai:gpt-image-1") < report.find("gemini:imagen-4"), (
        "higher-scored model should appear first in the report"
    )
    assert "Recommended default for image: `openai:gpt-image-1`" in report


def test_report_handles_errors() -> None:
    ps = PromptSet(name="x", modality="image", reference="r.png", prompt="x")
    rec = BenchmarkRecord(
        spec="gemini:imagen-4", take=1, artifact_path="missing.png",
        cost_usd=0.0, latency_ms=0,
        error="ProviderRateLimited: 429",
    )
    report = _build_report([rec], ps)
    assert "errors" in report
    # Errored runs still appear with score 0.0.
    assert "0.0 / 40" in report
