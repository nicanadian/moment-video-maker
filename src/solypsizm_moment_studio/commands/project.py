"""Project lifecycle: new, status, open."""

from __future__ import annotations

import shutil
from pathlib import Path

import click

from solypsizm_moment_studio.models import Project
from solypsizm_moment_studio.state import (
    append_log,
    brand_kit_path,
    list_concepts,
    list_moments,
    list_scenes,
    load_project,
    load_song_analysis,
    project_dir,
    require_project_root,
    save_project,
    solypsizm_home,
)
from solypsizm_moment_studio.utils import now_iso


def run_new(slug: str, song_title: str, lyrics: str, audio: str) -> None:
    target = project_dir(slug)
    if target.exists():
        raise click.ClickException(f"{target} already exists.")

    lyrics_src = Path(lyrics).expanduser().resolve()
    audio_src = Path(audio).expanduser().resolve()

    target.mkdir(parents=True)
    (target / "audio").mkdir()
    (target / "concepts").mkdir()
    (target / "scenes").mkdir()
    (target / "moments").mkdir()
    (target / "moments" / "output").mkdir()
    (target / ".state").mkdir()

    # Copy lyrics as plain text.
    shutil.copy2(lyrics_src, target / "lyrics.txt")

    # Copy audio preserving its extension under audio/master.<ext>.
    audio_ext = audio_src.suffix.lower() or ".wav"
    audio_dest = target / "audio" / f"master{audio_ext}"
    shutil.copy2(audio_src, audio_dest)

    now = now_iso()
    project = Project(
        song_title=song_title,
        song_slug=slug,
        lyrics_file="lyrics.txt",
        audio_file=f"audio/master{audio_ext}",
        created_at=now,
        updated_at=now,
    )
    save_project(target, project)
    append_log(target, "project_created", slug=slug, song_title=song_title)

    bk_path = brand_kit_path()
    click.echo(f"✓ Created project at {target}")
    if not bk_path.exists():
        click.echo(
            f"⚠ Brand kit not found at {bk_path}. Run `solypsizm bootstrap-brand-kit` next."
        )


def run_status(slug: str | None) -> None:
    if slug is not None:
        root = project_dir(slug)
        if not (root / "project.json").is_file():
            raise click.ClickException(f"No project at {root}.")
    else:
        try:
            root = require_project_root()
        except FileNotFoundError as e:
            raise click.ClickException(str(e)) from e

    project = load_project(root)
    concepts = list_concepts(root)
    scenes = list_scenes(root)
    moments = list_moments(root)

    in_progress_concepts = [c for c in concepts if c.status == "in_progress"]
    scenes_with_clips = [s for s in scenes if s.clip_takes]
    scenes_complete = [s for s in scenes if s.status == "complete"]

    by_status: dict[str, int] = {}
    for m in moments:
        by_status[m.status] = by_status.get(m.status, 0) + 1

    click.echo(f"Project: {project.song_slug}")
    click.echo(f"Title: {project.song_title}")
    click.echo(f"Path: {root}")
    click.echo(f"Brand kit: {project.brand_kit_path}")
    click.echo("")
    click.echo(f"Concepts: {len(concepts)} created ({len(in_progress_concepts)} in progress)")
    if project.current_concept:
        click.echo(f"  Current: {project.current_concept}")
    click.echo(
        f"Scenes: {len(scenes)} created "
        f"({len(scenes_with_clips)} with clips, {len(scenes_complete)} complete)"
    )

    if moments:
        parts = ", ".join(f"{n} {s}" for s, n in sorted(by_status.items()))
        click.echo(
            f"Moments: {len(moments)} of target {project.target_moment_count} ({parts})"
        )
    else:
        click.echo(f"Moments: 0 of target {project.target_moment_count}")

    # Coverage by song section (PRD §F9). Quiet if there's no analysis yet.
    try:
        analysis = load_song_analysis(root)
    except FileNotFoundError:
        return

    use_count: dict[str, int] = {}
    for m in moments:
        use_count[m.source_song_section.name] = (
            use_count.get(m.source_song_section.name, 0) + 1
        )
    if analysis.sections:
        click.echo("")
        click.echo("Section coverage:")
        gaps: list[str] = []
        for s in analysis.sections:
            n = use_count.get(s.name, 0)
            marker = "✓" if n > 0 else "·"
            click.echo(f"  {marker} {s.name:<14} {n} moment(s)")
            if n == 0:
                gaps.append(s.name)
        if gaps:
            click.echo(f"GAPS: {', '.join(gaps)}")


def run_open(slug: str) -> None:
    root = project_dir(slug)
    if not (root / "project.json").is_file():
        raise click.ClickException(f"No project at {root}.")
    # Print the path so the artist can `cd $(solypsizm open <slug>)`.
    click.echo(str(root))
    run_status(slug)
