"""solypsizm auto / auto-resume / auto-status commands."""

from __future__ import annotations

import click

from solypsizm_moment_studio.auto import (
    AutoConfig,
    clear_state,
    load_state,
    run_auto,
    run_resume,
)
from solypsizm_moment_studio.state import require_project_root


def run_auto_cmd(
    moments: int,
    review_gates: str,
    threshold: float,
    budget: float,
    text_model: str,
    image_model: str,
    video_model: str,
    reset: bool,
) -> None:
    root = require_project_root()
    if reset:
        clear_state(root)
        click.echo("✓ Cleared previous auto-pipeline state.")
    gates = (
        []
        if review_gates.lower() == "none"
        else [g.strip() for g in review_gates.split(",") if g.strip()]
    )
    config = AutoConfig(
        target_moments=moments,
        review_gates=gates,
        auto_approve_threshold=threshold,
        budget_usd=budget,
        text_model=text_model,
        image_model=image_model,
        video_model=video_model,
    )
    run_auto(root, config)


def run_auto_resume_cmd() -> None:
    root = require_project_root()
    run_resume(root)


def run_auto_status_cmd() -> None:
    root = require_project_root()
    state = load_state(root)
    if state is None:
        click.echo("(no auto-pipeline running for this project)")
        return
    click.echo(f"Project: {state.project_slug}")
    click.echo(f"Stage:   {state.stage}")
    if state.paused_reason:
        click.echo(f"Paused:  {state.paused_reason}")
    if state.error:
        click.echo(f"Error:   {state.error}")
    if state.current_scene_id:
        click.echo(f"Current: {state.current_scene_id}")
    if state.completed_scene_ids:
        click.echo(f"Scenes done: {len(state.completed_scene_ids)}")
    click.echo("")
    click.echo(f"Config: {state.config.model_dump()}")
