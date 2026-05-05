"""Auto-pipeline state machine: song + lyrics → 9 reviewable moments.

Synchronous execution for v2.0 — no asyncio. Each stage is idempotent
against the persisted state at ``.state/auto-state.json``, so Ctrl+C /
network drops / daily-budget pauses can resume cleanly.

Stages:
    init → concepts_generated → concept_picked
        → scenes_generated → media_in_progress → media_done
        → analyzed → moments_suggested → complete

Review gates (default: concept, final) write a 'paused' marker and
exit; the user runs `solypsizm auto resume <slug>` to continue.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import click
from pydantic import BaseModel, ConfigDict, Field

from solypsizm_moment_studio.state import (
    append_log,
    list_concepts,
    list_scenes,
    load_project,
    save_project,
)
from solypsizm_moment_studio.utils import now_iso

Stage = Literal[
    "init",
    "concepts_generated",
    "concept_picked",
    "scenes_generated",
    "media_in_progress",
    "media_done",
    "analyzed",
    "moments_suggested",
    "complete",
    "paused",
    "failed",
]


class AutoConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    target_moments: int = 9
    review_gates: list[str] = Field(default_factory=lambda: ["concept", "final"])
    auto_approve_threshold: float = 32.0  # 0-40 (80%)
    budget_usd: float = 30.0
    text_model: str = "gemini:gemini-2.5-flash"
    image_model: str = "openai:gpt-image-1"
    video_model: str = "gemini:veo-3"
    concept_count: int = 5


class AutoState(BaseModel):
    model_config = ConfigDict(extra="allow")

    project_slug: str
    started_at: str
    stage: Stage = "init"
    paused_reason: str | None = None
    current_scene_id: str | None = None
    completed_scene_ids: list[str] = Field(default_factory=list)
    config: AutoConfig
    error: str | None = None


def state_path(project_root: Path) -> Path:
    return project_root / ".state" / "auto-state.json"


def load_state(project_root: Path) -> AutoState | None:
    path = state_path(project_root)
    if not path.is_file():
        return None
    return AutoState.model_validate_json(path.read_text(encoding="utf-8"))


def save_state(project_root: Path, state: AutoState) -> None:
    from solypsizm_moment_studio.state import save_json_atomic

    save_json_atomic(state_path(project_root), state.model_dump())


def clear_state(project_root: Path) -> None:
    p = state_path(project_root)
    if p.is_file():
        p.unlink()


def _gate(name: str, state: AutoState) -> bool:
    """True if this stage should pause for human review."""
    return name in state.config.review_gates


def _pause(project_root: Path, state: AutoState, reason: str) -> None:
    """Persist a 'paused' marker and emit instructions to resume."""
    state.stage = "paused"
    state.paused_reason = reason
    save_state(project_root, state)
    click.echo("")
    click.echo(f"⏸  paused: {reason}")
    click.echo(f"   resume with `solypsizm --project {state.project_slug} auto-resume`")


def run_auto(project_root: Path, config: AutoConfig) -> None:
    """Top-level entry. Starts a fresh run, refusing if state exists."""
    if state_path(project_root).is_file():
        raise click.ClickException(
            f"Auto-pipeline state already exists at {state_path(project_root)}. "
            f"Use `solypsizm auto-resume` to continue, or `solypsizm auto --reset` to start over."
        )
    project = load_project(project_root)
    state = AutoState(
        project_slug=project.song_slug,
        started_at=now_iso(),
        stage="init",
        config=config,
    )
    save_state(project_root, state)
    append_log(project_root, "auto_started", config=config.model_dump())
    _run_loop(project_root, state)


def run_resume(project_root: Path) -> None:
    state = load_state(project_root)
    if state is None:
        raise click.ClickException(
            "No auto-pipeline state found. Run `solypsizm auto <slug>` to start."
        )
    if state.stage == "complete":
        click.echo("✓ Auto-pipeline already complete.")
        return
    if state.stage == "failed":
        raise click.ClickException(
            f"Auto-pipeline previously failed: {state.error}. "
            f"Inspect, then run `solypsizm auto --reset <slug>` to restart."
        )
    state.paused_reason = None
    if state.stage == "paused":
        # Move past the gate that paused us. Determine which by looking at
        # what's complete on disk.
        state.stage = _next_stage_after_pause(project_root, state)
    save_state(project_root, state)
    append_log(project_root, "auto_resumed", from_stage=state.stage)
    _run_loop(project_root, state)


def _next_stage_after_pause(project_root: Path, state: AutoState) -> Stage:
    """Decide what stage to enter when resuming from a pause. Reads the
    project state to figure out where the user picked up after the gate."""
    project = load_project(project_root)
    if state.paused_reason and "concept" in state.paused_reason:
        if project.current_concept:
            return "concept_picked"
        # User didn't pick — pause again.
        return "concepts_generated"
    if state.paused_reason and "moment" in state.paused_reason:
        return "complete"
    return state.stage


def _run_loop(project_root: Path, state: AutoState) -> None:
    """Drive the stages forward, persisting after each transition."""
    try:
        while state.stage not in {"complete", "paused", "failed"}:
            next_stage = _step(project_root, state)
            if next_stage is None:
                break
            state.stage = next_stage
            save_state(project_root, state)
        if state.stage == "complete":
            click.echo("\n✓ Auto-pipeline complete.")
            append_log(project_root, "auto_completed")
    except click.ClickException:
        raise
    except Exception as e:
        state.stage = "failed"
        state.error = f"{type(e).__name__}: {e}"
        save_state(project_root, state)
        append_log(project_root, "auto_failed", error=state.error)
        raise


def _step(project_root: Path, state: AutoState) -> Stage | None:
    """Run one stage and return the next. None means we paused inside."""
    stage = state.stage
    cfg = state.config
    project = load_project(project_root)

    if stage == "init":
        click.echo(f"[init] auto-pipeline for {state.project_slug}")
        return "init" if False else _stage_concepts(project_root, state, cfg, project)

    if stage == "concepts_generated":
        if _gate("concept", state):
            _pause(project_root, state, "concept review — pick a concept then resume")
            return None
        return _stage_pick_concept(project_root, state, project)

    if stage == "concept_picked":
        return _stage_scenes(project_root, state, cfg, project)

    if stage == "scenes_generated":
        return _stage_media(project_root, state, cfg, project)

    if stage == "media_done":
        return _stage_analyze(project_root, state)

    if stage == "analyzed":
        return _stage_suggest(project_root, state, cfg, project)

    if stage == "moments_suggested":
        if _gate("final", state):
            _pause(project_root, state, "moment review — approve/reject moments then resume")
            return None
        return "complete"

    return None


# ---------------------------------------------------------------------------
# Stage implementations
# ---------------------------------------------------------------------------


def _stage_concepts(project_root: Path, state: AutoState, cfg: AutoConfig, project) -> Stage:
    from solypsizm_moment_studio.commands import concepts as cmd_concepts

    if list_concepts(project_root):
        click.echo("[concepts] existing concepts found, skipping brainstorm")
        return "concepts_generated"

    click.echo(f"[concepts] brainstorming via {cfg.text_model}...")
    cmd_concepts.run_brainstorm(count=cfg.concept_count, copy=False, api=True, model=cfg.text_model)
    return "concepts_generated"


def _stage_pick_concept(project_root: Path, state: AutoState, project) -> Stage:
    """When the gate is off, auto-pick the first concept. (A real
    implementation would score concepts via the judge; v1 simplification.)"""
    if project.current_concept:
        return "concept_picked"
    concepts = list_concepts(project_root)
    if not concepts:
        raise click.ClickException("No concepts to pick from after brainstorm.")
    chosen = concepts[0]
    project.current_concept = chosen.id
    save_project(project_root, project)
    click.echo(f"[concepts] auto-picked {chosen.id}")
    append_log(project_root, "auto_concept_picked", id=chosen.id)
    return "concept_picked"


def _stage_scenes(project_root: Path, state: AutoState, cfg: AutoConfig, project) -> Stage:
    from solypsizm_moment_studio.commands import scenes as cmd_scenes

    existing = list_scenes(project_root, concept_id=project.current_concept)
    if existing:
        click.echo(f"[scenes] existing scenes for {project.current_concept}, skipping")
        return "scenes_generated"

    click.echo(f"[scenes] breaking down {project.current_concept} via {cfg.text_model}...")
    cmd_scenes.run_scenes(copy=False, api=True, model=cfg.text_model)
    return "scenes_generated"


def _stage_media(project_root: Path, state: AutoState, cfg: AutoConfig, project) -> Stage:
    """For each scene: start frame, end frame, motion clip. Skips scenes
    already complete on disk so resume picks up where it left off."""
    from solypsizm_moment_studio.commands import scenes as cmd_scenes

    scenes = list_scenes(project_root, concept_id=project.current_concept)
    if not scenes:
        raise click.ClickException("No scenes to generate media for.")
    state.stage = "media_in_progress"
    save_state(project_root, state)

    for scene in scenes:
        if scene.id in state.completed_scene_ids:
            continue
        if scene.clip_takes:
            # Already has clips — skip.
            state.completed_scene_ids.append(scene.id)
            save_state(project_root, state)
            continue
        click.echo(f"[media] {scene.id}...")
        state.current_scene_id = scene.id
        save_state(project_root, state)
        cmd_scenes.run_prompts(
            scene_id=scene.id,
            copy=False,
            api=True,
            image_model=cfg.image_model,
            video_model=cfg.video_model,
        )
        state.completed_scene_ids.append(scene.id)
        state.current_scene_id = None
        save_state(project_root, state)

    return "media_done"


def _stage_analyze(project_root: Path, state: AutoState) -> Stage:
    from solypsizm_moment_studio.commands import audio as cmd_audio
    from solypsizm_moment_studio.state import song_analysis_path

    if song_analysis_path(project_root).is_file():
        click.echo("[analyze] song analysis already present, skipping")
        return "analyzed"
    click.echo("[analyze] running librosa pipeline...")
    cmd_audio.run_analyze(force=False)
    return "analyzed"


def _stage_suggest(project_root: Path, state: AutoState, cfg: AutoConfig, project) -> Stage:
    from solypsizm_moment_studio.commands import moments as cmd_moments
    from solypsizm_moment_studio.state import list_moments

    if list_moments(project_root):
        click.echo("[suggest] moments already present, skipping")
        return "moments_suggested"

    click.echo(f"[suggest] generating {cfg.target_moments} moments...")
    cmd_moments.run_suggest_moments(count=cfg.target_moments, strategy="section_focus")
    return "moments_suggested"
