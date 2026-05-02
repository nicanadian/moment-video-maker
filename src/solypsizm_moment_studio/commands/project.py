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
    has_analysis = False
    try:
        analysis = load_song_analysis(root)
        has_analysis = True
    except FileNotFoundError:
        analysis = None

    if has_analysis and analysis is not None and analysis.sections:
        use_count: dict[str, int] = {}
        for m in moments:
            use_count[m.source_song_section.name] = (
                use_count.get(m.source_song_section.name, 0) + 1
            )
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

    next_hint = _next_action_hint(
        project, concepts, scenes, scenes_with_clips, scenes_complete, moments,
        has_analysis=has_analysis,
    )
    if next_hint:
        click.echo("")
        click.echo(f"Next: {next_hint}")


def _next_action_hint(
    project,
    concepts,
    scenes,
    scenes_with_clips,
    scenes_complete,
    moments,
    has_analysis: bool,
) -> str | None:
    """Pick the most relevant next-step suggestion based on project state.

    PRD §18 success criterion #2: 'status tells the artist exactly what to do
    next'. The check order matches the workflow funnel.
    """
    if not concepts:
        return "run `solypsizm brainstorm`, paste the prompt to ChatGPT, then `solypsizm import-concepts <response>`"
    if not project.current_concept:
        return f"`solypsizm pick-concept <id>` (you have {len(concepts)} concept(s))"
    current_scenes = [s for s in scenes if s.concept_id == project.current_concept]
    if not current_scenes:
        return f"run `solypsizm scenes` for {project.current_concept}, then `solypsizm import-scenes <response>`"
    scenes_without_prompts = [s for s in current_scenes if s.status == "draft"]
    if scenes_without_prompts:
        target = scenes_without_prompts[0].id
        return f"`solypsizm prompts {target}` to emit ChatGPT/Veo prompts"
    if not scenes_with_clips:
        return "import frames + clips: `solypsizm import-frame --scene <id> --type {start|end} <file>` and `solypsizm import-clip --scene <id> --rating N <file>`"
    if not has_analysis:
        return "`solypsizm analyze` to detect song sections"
    if not moments:
        return f"`solypsizm suggest-moments --count {project.target_moment_count}` to draft edit specs"
    pending = [m for m in moments if m.status == "pending_review"]
    if pending:
        return f"`solypsizm review-moment {pending[0].id}` (you have {len(pending)} pending)"
    if len(moments) < project.target_moment_count:
        return f"`solypsizm suggest-moments --count {project.target_moment_count - len(moments)}` to fill the remaining slots"
    return None


def run_open(slug: str) -> None:
    """Print path to stdout and a status summary to stderr.

    Stdout-only path means `cd $(solypsizm open haze)` works cleanly — the
    summary lands on the terminal (stderr) but doesn't pollute the cd target.
    """
    root = project_dir(slug)
    if not (root / "project.json").is_file():
        raise click.ClickException(f"No project at {root}.")
    click.echo(str(root))
    project = load_project(root)
    click.echo(f"# {project.song_slug} — {project.song_title}", err=True)
    click.echo(f"# {root}", err=True)
    click.echo("# (run `solypsizm status` for details)", err=True)
