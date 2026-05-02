"""Moment commands: suggest, review, render, render-all, trace (PRD §F7-§F8)."""

from __future__ import annotations

import shutil
import subprocess

import click

from solypsizm_moment_studio.state import (
    append_log,
    list_moments,
    list_scenes,
    load_edit_config,
    load_moment,
    load_project,
    load_song_analysis,
    require_project_root,
    save_moment,
)
from solypsizm_moment_studio.suggest import suggest_moments


def run_suggest_moments(count: int, strategy: str | None) -> None:
    root = require_project_root()
    project = load_project(root)
    try:
        song_analysis = load_song_analysis(root)
    except FileNotFoundError as e:
        raise click.ClickException(
            "No song-analysis.json found. Run `solypsizm analyze` first."
        ) from e

    cfg = load_edit_config()
    scenes = list_scenes(root)
    chosen_strategy = strategy or "section_focus"

    # Existing moments stay put — running suggest-moments again continues the
    # numbering past whatever's already on disk and never overwrites approved
    # work.
    existing = list_moments(root)
    existing_ids = {m.id for m in existing}
    start_index = len(existing) + 1

    moments, stop_reason = suggest_moments(
        project=project,
        song_analysis=song_analysis,
        scenes=scenes,
        cfg=cfg,
        count=count,
        strategy=chosen_strategy,
        start_index=start_index,
        reserved_ids=existing_ids,
    )

    if not moments:
        reason = stop_reason or "unknown"
        raise click.ClickException(
            "Couldn't generate any moments. Need at least "
            f"{cfg.min_clips_per_moment} clips rated ≥ {cfg.min_clip_rating} "
            f"with mood tags, plus a song analysis. Reason: {reason}."
        )

    for m in moments:
        save_moment(root, m)

    append_log(
        root,
        "moments_suggested",
        count=len(moments),
        strategy=chosen_strategy,
        ids=[m.id for m in moments],
    )

    if existing:
        click.echo(
            f"({len(existing)} existing moment(s) preserved; numbering continues from "
            f"moment-{start_index:02d})",
            err=True,
        )
    click.echo(f"✓ Generated {len(moments)} new moment spec(s):")
    click.echo("")
    click.echo(f"{'id':<40} {'section':<14} {'clips':<6} {'duration':<9}")
    click.echo("-" * 75)
    for m in moments:
        clip_count = sum(1 for s in m.segments if s.type == "clip")
        click.echo(
            f"{m.id:<40} {m.source_song_section.name:<14} "
            f"{clip_count:<6} {m.duration_target_seconds:.1f}s"
        )
    if len(moments) < count:
        click.echo("")
        click.echo(
            f"⚠ Requested {count}, produced {len(moments)}. "
            f"Reason: {stop_reason or 'see clip pool / section coverage'}."
        )
    click.echo("")
    click.echo("Run `solypsizm review-moment <id>` to approve or reject each.")


def run_list_moments() -> None:
    root = require_project_root()
    moments = list_moments(root)
    if not moments:
        click.echo("No moments yet. Run `solypsizm suggest-moments` to start.")
        return
    click.echo(f"{'id':<40} {'status':<16} {'section':<14} clips")
    click.echo("-" * 80)
    for m in moments:
        clip_count = sum(1 for s in m.segments if s.type == "clip")
        click.echo(
            f"{m.id:<40} {m.status:<16} {m.source_song_section.name:<14} {clip_count}"
        )


def run_review_moment(moment_id: str, approve: bool, reject: bool) -> None:
    root = require_project_root()
    try:
        moment = load_moment(root, moment_id)
    except FileNotFoundError as e:
        raise click.ClickException(f"No moment {moment_id!r}.") from e

    project = load_project(root)
    section = moment.source_song_section

    click.echo(f"Moment: {moment.id}")
    click.echo(f"Status: {moment.status}")
    click.echo(f"Strategy: {moment.edit_strategy}")
    click.echo(
        f"Section: {section.name}  ({section.start:.1f}s — {section.end:.1f}s, "
        f"{section.end - section.start:.1f}s)"
    )
    click.echo("")
    click.echo("Segments:")
    for i, seg in enumerate(moment.segments, 1):
        if seg.type == "title_card":
            click.echo(f"  {i}. [TITLE] {seg.title} / {seg.subtitle} ({seg.duration:.1f}s)")
        elif seg.type == "clip":
            click.echo(
                f"  {i}. [CLIP ] {seg.source} @ {seg.audio_offset:.1f}s ({seg.duration:.1f}s)"
            )
        elif seg.type == "end_card":
            click.echo(f"  {i}. [END  ] {seg.image} ({seg.duration:.1f}s)")
    click.echo("")

    if approve and reject:
        raise click.ClickException("Pass one of --approve or --reject, not both.")

    decision: str | None = None
    if approve:
        decision = "approve"
    elif reject:
        decision = "reject"
    else:
        # Try to play the audio range so the artist can listen before deciding.
        _try_play_audio_range(root, project, section.start, section.end - section.start)
        decision = click.prompt(
            "Decision",
            type=click.Choice(["approve", "reject", "skip"], case_sensitive=False),
            default="skip",
        ).lower()

    if decision == "approve":
        moment.status = "approved"
        save_moment(root, moment)
        append_log(root, "moment_approved", id=moment.id)
        click.echo(f"✓ {moment.id} approved.")
    elif decision == "reject":
        moment.status = "rejected"
        save_moment(root, moment)
        append_log(root, "moment_rejected", id=moment.id)
        click.echo(f"✓ {moment.id} rejected.")
    else:
        click.echo("(skipped — no change)")


def _try_play_audio_range(root, project, start: float, duration: float) -> None:
    audio_path = root / project.audio_file
    if not audio_path.is_file():
        click.echo(f"(audio file missing: {audio_path})", err=True)
        return
    ffplay = shutil.which("ffplay")
    if ffplay is None:
        click.echo(
            f"(ffplay not found; play manually: ffplay -ss {start} -t {duration} "
            f"-nodisp -autoexit '{audio_path}')",
            err=True,
        )
        return
    click.echo(
        f"Playing audio {start:.1f}s — {start + duration:.1f}s "
        "(ffplay; close window or wait for autoexit to stop)...",
        err=True,
    )
    try:
        subprocess.run(
            [
                ffplay,
                "-loglevel",
                "warning",
                "-ss",
                str(start),
                "-t",
                str(duration),
                "-nodisp",
                "-autoexit",
                str(audio_path),
            ],
            check=False,
        )
    except OSError as e:
        click.echo(f"(ffplay failed: {e})", err=True)


def run_render_moment(moment_id: str) -> None:
    root = require_project_root()
    try:
        moment = load_moment(root, moment_id)
    except FileNotFoundError as e:
        raise click.ClickException(f"No moment {moment_id!r}.") from e

    if moment.status != "approved":
        raise click.ClickException(
            f"{moment.id} status is {moment.status!r}, not 'approved'. "
            "Approve via `solypsizm review-moment` first."
        )

    spec_path = root / "moments" / f"{moment.id}.json"
    raise click.ClickException(
        "Variant Builder integration is not wired yet. The moment spec is ready at "
        f"{spec_path}; once Variant Builder ships, this command will hand it off."
    )


def run_render_all() -> None:
    root = require_project_root()
    moments = list_moments(root)
    approved = [m for m in moments if m.status == "approved"]
    if not approved:
        click.echo("No approved moments to render.")
        return
    click.echo(f"{len(approved)} approved moment(s) waiting on Variant Builder:")
    for m in approved:
        click.echo(f"  {m.id}")
    raise click.ClickException(
        "Variant Builder integration is not wired yet. Specs are ready in moments/."
    )


def run_trace(clip: str) -> None:
    """Find every moment that uses a given clip filename or path fragment."""
    root = require_project_root()
    moments = list_moments(root)
    matches: list[tuple[str, str]] = []  # (moment_id, source path)
    for m in moments:
        for seg in m.segments:
            if seg.type == "clip" and seg.source and clip in seg.source:
                matches.append((m.id, seg.source))
                break
    if not matches:
        click.echo(f"{clip} is not used in any moment.")
        return
    click.echo(f"{clip} appears in {len(matches)} moment(s):")
    for mid, src in matches:
        click.echo(f"  {mid}  ({src})")
