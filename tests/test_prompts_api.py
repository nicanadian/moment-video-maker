"""Regression coverage for direct API prompt generation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import click
import pytest

from solypsizm_moment_studio.commands.scenes import _run_prompts_api
from solypsizm_moment_studio.models import Project, Scene
from solypsizm_moment_studio.state import load_brand_kit


def test_prompts_api_uses_prompt_templates_and_imports_generated_assets(
    tmp_path: Path, monkeypatch
) -> None:
    """`prompts --api` should build prompts from templates before provider calls.

    This catches the v2 regression where _run_prompts_api referenced
    start_frame_prompt/end_frame_prompt/veo_motion_prompt without importing
    them, crashing with NameError before any provider dispatch.
    """
    home = tmp_path / "home"
    home.mkdir()
    (home / "brand-kit.json").write_text(Path("brand-kit.json").read_text(), encoding="utf-8")
    reference_dir = home / "character-reference"
    reference_dir.mkdir()
    (reference_dir / "front.png").write_bytes(b"fake-png")
    monkeypatch.setenv("SOLYPSIZM_HOME", str(home))

    root = tmp_path / "project"
    root.mkdir()
    (root / "scenes" / "concept-01").mkdir(parents=True)
    bk = load_brand_kit(home / "brand-kit.json")
    project = Project(
        song_title="Haze over the Horizon",
        song_slug="haze",
        artist="Solypsizm",
        release_date="2026-01-09",
        created_at="2026-05-01T00:00:00+00:00",
        updated_at="2026-05-01T00:00:00+00:00",
    )
    scene = Scene(
        id="scene-01-tower",
        concept_id="concept-01",
        title="Tower",
        description="A tower scene",
        duration_target_seconds=6,
        shot_type="wide",
        camera_motion="push in",
        subject_motion="turns toward dawn",
        environment="neon tower",
        lighting="cyan rim light",
        mood_tags=["isolation"],
        song_section_fit=["intro"],
        energy_target="low-mid",
        created_at="2026-05-01T00:00:00+00:00",
        updated_at="2026-05-01T00:00:00+00:00",
    )

    calls: list[tuple[str, str, Path]] = []

    def fake_image(project_root, spec, *, prompt, out_path, reference):
        calls.append(("image", prompt, Path(out_path)))
        Path(out_path).write_bytes(b"image")
        return SimpleNamespace(cost_usd=0.01, latency_ms=10, cache_hit=False)

    def fake_video(
        project_root, spec, *, prompt, out_path, start_frame, end_frame, duration_seconds
    ):
        calls.append(("video", prompt, Path(out_path)))
        Path(out_path).write_bytes(b"video")
        return SimpleNamespace(cost_usd=0.02, latency_ms=20, cache_hit=False)

    imported: list[tuple[str, str]] = []
    monkeypatch.setattr("solypsizm_moment_studio.providers.dispatch.call_image", fake_image)
    monkeypatch.setattr("solypsizm_moment_studio.providers.dispatch.call_video", fake_video)
    monkeypatch.setattr(
        "solypsizm_moment_studio.commands.media.run_import_frame",
        lambda file, scene_id, frame_type, move=True: imported.append(("frame", frame_type)),
    )
    monkeypatch.setattr(
        "solypsizm_moment_studio.commands.media.run_import_clip",
        lambda file, scene_id, rating, notes, move=True: imported.append(("clip", notes)),
    )

    _run_prompts_api(root, bk, project, scene, "gemini:test-image", "gemini:test-video")

    assert [kind for kind, _prompt, _path in calls] == ["image", "image", "video"]
    assert "neon tower" in calls[0][1]
    assert "push in" in calls[1][1]
    assert "neon tower" in calls[2][1]
    assert imported == [("frame", "start"), ("frame", "end"), ("clip", "auto-generated")]


def test_prompts_api_wraps_provider_resolution_errors(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "brand-kit.json").write_text(Path("brand-kit.json").read_text(), encoding="utf-8")
    reference_dir = home / "character-reference"
    reference_dir.mkdir()
    (reference_dir / "front.png").write_bytes(b"fake-png")
    monkeypatch.setenv("SOLYPSIZM_HOME", str(home))

    root = tmp_path / "project"
    root.mkdir()
    (root / "scenes" / "concept-01").mkdir(parents=True)
    bk = load_brand_kit(home / "brand-kit.json")
    project = Project(
        song_title="Haze over the Horizon",
        song_slug="haze",
        artist="Solypsizm",
        release_date="2026-01-09",
        created_at="2026-05-01T00:00:00+00:00",
        updated_at="2026-05-01T00:00:00+00:00",
    )
    scene = Scene(
        id="scene-01-tower",
        concept_id="concept-01",
        title="Tower",
        description="A tower scene",
        duration_target_seconds=6,
        environment="neon tower",
        created_at="2026-05-01T00:00:00+00:00",
        updated_at="2026-05-01T00:00:00+00:00",
    )

    monkeypatch.setattr(
        "solypsizm_moment_studio.providers.dispatch.call_image",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ValueError("Unknown image provider 'fake'")
        ),
    )

    with pytest.raises(click.ClickException, match="Unknown image provider"):
        _run_prompts_api(root, bk, project, scene, "fake:no-call", "fake:no-call")


def test_prompts_api_dry_run_writes_planned_prompts_without_provider_calls(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "brand-kit.json").write_text(Path("brand-kit.json").read_text(), encoding="utf-8")
    reference_dir = home / "character-reference"
    reference_dir.mkdir()
    (reference_dir / "front.png").write_bytes(b"fake-png")
    monkeypatch.setenv("SOLYPSIZM_HOME", str(home))

    root = tmp_path / "project"
    root.mkdir()
    (root / "scenes" / "concept-01").mkdir(parents=True)
    bk = load_brand_kit(home / "brand-kit.json")
    project = Project(
        song_title="Haze over the Horizon",
        song_slug="haze",
        artist="Solypsizm",
        release_date="2026-01-09",
        created_at="2026-05-01T00:00:00+00:00",
        updated_at="2026-05-01T00:00:00+00:00",
    )
    scene = Scene(
        id="scene-01-tower",
        concept_id="concept-01",
        title="Tower",
        description="A tower scene",
        duration_target_seconds=6,
        environment="neon tower",
        created_at="2026-05-01T00:00:00+00:00",
        updated_at="2026-05-01T00:00:00+00:00",
    )

    monkeypatch.setattr(
        "solypsizm_moment_studio.providers.dispatch.call_image",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("provider called")),
    )

    _run_prompts_api(
        root,
        bk,
        project,
        scene,
        "fake:image",
        "fake:video",
        dry_run=True,
    )

    plan = root / "scenes" / "concept-01" / "scene-01-tower-api-dry-run.md"
    assert plan.is_file()
    text = plan.read_text(encoding="utf-8")
    assert "fake:image" in text
    assert "fake:video" in text
    assert "neon tower" in text
    assert not (root / "scenes" / "concept-01" / "scene-01-tower-staging").exists()
