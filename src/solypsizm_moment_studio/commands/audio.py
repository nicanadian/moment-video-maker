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
    has_existing = out_path.exists()
    if has_existing and not force:
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
    try:
        analysis = analyze_audio(audio_file, project.audio_file)
    except Exception as e:
        raise click.ClickException(
            f"Audio analysis failed: {type(e).__name__}: {e}. "
            "Check the audio file is valid and ffmpeg is installed for non-WAV formats."
        ) from e

    # If we're overwriting and the user has --force, show a diff and confirm
    # before destroying their hand-edits (PRD §14.3).
    if has_existing and force:
        existing = load_song_analysis(root)
        click.echo("")
        click.echo("Changes to song-analysis.json:")
        click.echo(_diff_analysis(existing, analysis))
        if not click.confirm("Overwrite?", default=False):
            click.echo("Aborted; existing analysis kept.")
            return

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


def _diff_analysis(old, new) -> str:
    """Compact human-readable diff between two SongAnalysis objects."""
    lines: list[str] = []
    if abs(old.tempo_bpm - new.tempo_bpm) > 0.01:
        lines.append(f"  tempo: {old.tempo_bpm} → {new.tempo_bpm} BPM")
    if abs(old.duration_seconds - new.duration_seconds) > 0.1:
        lines.append(f"  duration: {old.duration_seconds:.1f}s → {new.duration_seconds:.1f}s")
    old_names = {s.name: s for s in old.sections}
    new_names = {s.name: s for s in new.sections}
    removed = sorted(old_names.keys() - new_names.keys())
    added = sorted(new_names.keys() - old_names.keys())
    if removed:
        lines.append(f"  removed sections: {', '.join(removed)}")
    if added:
        lines.append(f"  new sections: {', '.join(added)}")
    for name in sorted(old_names.keys() & new_names.keys()):
        a, b = old_names[name], new_names[name]
        if abs(a.start - b.start) > 0.5 or abs(a.end - b.end) > 0.5:
            lines.append(
                f"  {name}: {a.start:.1f}-{a.end:.1f}s → {b.start:.1f}-{b.end:.1f}s"
            )
    if not lines:
        lines.append("  (no significant changes)")
    return "\n".join(lines)


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
