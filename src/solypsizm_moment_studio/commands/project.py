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
    list_scenes,
    load_project,
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

    in_progress_concepts = [c for c in concepts if c.status == "in_progress"]
    scenes_with_clips = [s for s in scenes if s.clip_takes]
    scenes_complete = [s for s in scenes if s.status == "complete"]

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
    click.echo(f"Moments target: {project.target_moment_count}")
    click.echo(f"Moments completed: {project.moments_completed}")


def run_open(slug: str) -> None:
    root = project_dir(slug)
    if not (root / "project.json").is_file():
        raise click.ClickException(f"No project at {root}.")
    # Print the path so the artist can `cd $(solypsizm open <slug>)`.
    click.echo(str(root))
    run_status(slug)
