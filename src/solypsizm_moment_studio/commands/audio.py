"""Song analysis commands (PRD §F6)."""

from __future__ import annotations

import click

from solypsizm_moment_studio.state import (
    append_log,
    load_project,
    load_song_analysis,
    require_project_root,
    save_song_analysis,
    song_analysis_path,
)


def run_analyze(force: bool, lyrics_aware: bool) -> None:
    root = require_project_root()
    project = load_project(root)
    audio_file = root / project.audio_file
    if not audio_file.is_file():
        raise click.ClickException(f"Audio file not found: {audio_file}")

    out_path = song_analysis_path(root)
    if out_path.exists() and not force:
        raise click.ClickException(
            f"{out_path.relative_to(root)} already exists. Pass --force to regenerate "
            "(your manual edits will be lost)."
        )

    if lyrics_aware:
        click.echo("⚠ --lyrics-aware not implemented yet; running standard pipeline.", err=True)

    try:
        from solypsizm_moment_studio.analysis import analyze_audio
    except ImportError as e:
        raise click.ClickException(
            "librosa not installed. Run `pip install -e '.[audio]'` first."
        ) from e

    click.echo(f"Analyzing {project.audio_file}...", err=True)
    analysis = analyze_audio(audio_file, project.audio_file)
    save_song_analysis(root, analysis)
    append_log(
        root,
        "song_analyzed",
        sections=len(analysis.sections),
        tempo=analysis.tempo_bpm,
        duration=analysis.duration_seconds,
    )
    click.echo(
        f"✓ Detected {len(analysis.sections)} sections, "
        f"BPM {analysis.tempo_bpm}, "
        f"duration {analysis.duration_seconds:.1f}s."
    )


def run_sections() -> None:
    root = require_project_root()
    try:
        analysis = load_song_analysis(root)
    except FileNotFoundError as e:
        raise click.ClickException("No song analysis. Run `solypsizm analyze` first.") from e

    click.echo(f"Tempo: {analysis.tempo_bpm} BPM | Duration: {analysis.duration_seconds:.1f}s")
    click.echo("")
    click.echo(f"{'name':<14} {'start':>7}  {'end':>7}  {'len':>6}  {'energy':>10}")
    click.echo("-" * 55)
    for s in analysis.sections:
        click.echo(
            f"{s.name:<14} {s.start:>7.2f}  {s.end:>7.2f}  "
            f"{s.end - s.start:>5.1f}s  avg {s.energy_avg:.3f}"
        )
