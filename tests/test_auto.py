"""Tests for the auto-pipeline state machine.

Covers state persistence, resume semantics, gate behavior, and
idempotent stage transitions. Doesn't call providers — those are exercised
in test_providers.py and validated by the live `solypsizm auto` run.
"""

from __future__ import annotations

from solypsizm_moment_studio.auto import (
    AutoConfig,
    AutoState,
    _gate,
    clear_state,
    load_state,
    save_state,
    state_path,
)


def _state(slug: str = "haze", **config_kwargs) -> AutoState:
    cfg = AutoConfig(**config_kwargs)
    return AutoState(project_slug=slug, started_at="2026-05-04T00:00:00+00:00", config=cfg)


def test_default_review_gates() -> None:
    cfg = AutoConfig()
    assert "concept" in cfg.review_gates
    assert "final" in cfg.review_gates


def test_state_round_trip(tmp_path) -> None:
    state = _state()
    state.stage = "scenes_generated"
    state.completed_scene_ids = ["scene-01-walk", "scene-02-rise"]
    save_state(tmp_path, state)
    loaded = load_state(tmp_path)
    assert loaded is not None
    assert loaded.stage == "scenes_generated"
    assert loaded.completed_scene_ids == ["scene-01-walk", "scene-02-rise"]


def test_state_path_is_under_dot_state(tmp_path) -> None:
    assert state_path(tmp_path).parent.name == ".state"


def test_load_state_returns_none_when_absent(tmp_path) -> None:
    assert load_state(tmp_path) is None


def test_clear_state_removes_file(tmp_path) -> None:
    state = _state()
    save_state(tmp_path, state)
    assert state_path(tmp_path).is_file()
    clear_state(tmp_path)
    assert not state_path(tmp_path).is_file()


def test_clear_state_when_absent_is_safe(tmp_path) -> None:
    """Idempotent — clearing a non-existent state is a no-op."""
    clear_state(tmp_path)


def test_gate_check_with_default_gates() -> None:
    state = _state()
    assert _gate("concept", state) is True
    assert _gate("final", state) is True
    assert _gate("scenes", state) is False


def test_gate_check_with_none_gates() -> None:
    state = _state(review_gates=[])
    assert _gate("concept", state) is False
    assert _gate("final", state) is False


def test_config_threshold_default_is_eighty_percent() -> None:
    cfg = AutoConfig()
    assert cfg.auto_approve_threshold == 32.0  # 80% of 40


def test_config_extra_fields_allowed() -> None:
    """The config is permissive so future model overrides don't break old states."""
    cfg = AutoConfig.model_validate(
        {
            "target_moments": 9,
            "review_gates": ["concept"],
            "auto_approve_threshold": 30.0,
            "budget_usd": 20.0,
            "text_model": "openrouter:openai/gpt-5",
            "image_model": "openai:gpt-image-1",
            "video_model": "gemini:veo-3",
            "concept_count": 3,
            "future_field": "ignored",
        }
    )
    assert cfg.text_model == "openrouter:openai/gpt-5"


def test_auto_command_dry_run_prints_plan_without_saving_state(
    tmp_path, monkeypatch, capsys
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "project.json").write_text(
        '{"song_title":"Haze","song_slug":"haze","artist":"Solypsizm",'
        '"release_date":"2026-01-09","created_at":"x","updated_at":"x"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "solypsizm_moment_studio.commands.auto.require_project_root",
        lambda: root,
    )
    monkeypatch.setattr(
        "solypsizm_moment_studio.commands.auto.run_auto",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("runner called")),
    )

    from solypsizm_moment_studio.commands.auto import run_auto_cmd

    run_auto_cmd(
        moments=3,
        review_gates="none",
        threshold=30.0,
        budget=1.0,
        text_model="fake:text",
        image_model="fake:image",
        video_model="fake:video",
        reset=False,
        dry_run=True,
    )

    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "fake:text" in out
    assert not (root / ".state" / "auto-state.json").exists()
