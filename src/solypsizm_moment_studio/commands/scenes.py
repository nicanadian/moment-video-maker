"""Scene commands: scenes, import-scenes, list-scenes, prompts."""

from __future__ import annotations

from pathlib import Path

import click

from solypsizm_moment_studio.models import FramePrompts, Scene
from solypsizm_moment_studio.prompts import (
    ParseError,
    parse_scenes_response,
    scene_prompts_markdown,
    scenes_prompt,
)
from solypsizm_moment_studio.state import (
    append_log,
    brand_kit_path,
    list_scenes,
    load_brand_kit,
    load_concept,
    load_project,
    require_project_root,
    save_concept,
    save_scene,
)
from solypsizm_moment_studio.state.io import load_scene as _load_scene
from solypsizm_moment_studio.utils import (
    clipboard_copy,
    coerce_str_list,
    now_iso,
    resolve_id,
    slugify,
)


def _load_context() -> tuple[Path, "BrandKit", "Project"]:  # noqa: F821
    root = require_project_root()
    bk_path = brand_kit_path()
    if not bk_path.is_file():
        raise click.ClickException(
            f"Brand kit not found at {bk_path}. Run `solypsizm bootstrap-brand-kit` first."
        )
    bk = load_brand_kit(bk_path)
    project = load_project(root)
    return root, bk, project


def _require_current_concept(root: Path, project) -> "Concept":  # noqa: F821
    if not project.current_concept:
        raise click.ClickException(
            "No current concept. Run `solypsizm pick-concept <id>` first."
        )
    return load_concept(root, project.current_concept)


def run_scenes(copy: bool) -> None:
    root, bk, project = _load_context()
    concept = _require_current_concept(root, project)
    prompt = scenes_prompt(bk, project, concept)
    click.echo(prompt)
    if copy:
        if clipboard_copy(prompt):
            click.echo("\n— copied to clipboard —", err=True)
        else:
            click.echo("\n— pbcopy unavailable; prompt printed above only —", err=True)
    append_log(root, "scenes_emitted", concept_id=concept.id)


def run_import_scenes(input_file) -> None:
    root, _bk, project = _load_context()
    concept = _require_current_concept(root, project)
    text = input_file.read()
    try:
        items = parse_scenes_response(text)
    except ParseError as e:
        last_import = root / ".state" / "last-import.txt"
        last_import.parent.mkdir(parents=True, exist_ok=True)
        last_import.write_text(text, encoding="utf-8")
        raise click.ClickException(
            f"Could not parse response: {e}. Raw input saved to {last_import}."
        ) from e

    existing_for_concept = list_scenes(root, concept_id=concept.id)
    next_idx = len(existing_for_concept) + 1
    now = now_iso()
    created: list[str] = []
    for offset, raw in enumerate(items):
        idx = next_idx + offset
        title_raw = str(raw.get("title", "")).strip()
        title = title_raw or f"Scene {idx}"
        scene_id = f"scene-{idx:02d}-{slugify(title, max_words=4, fallback='untitled')}"
        scene = Scene(
            id=scene_id,
            concept_id=concept.id,
            title=title,
            description=str(raw.get("description", "")),
            duration_target_seconds=int(raw.get("duration_target_seconds", 6) or 6),
            shot_type=str(raw.get("shot_type", "")),
            camera_motion=str(raw.get("camera_motion", "")),
            subject_motion=str(raw.get("subject_motion", "")),
            environment=str(raw.get("environment", "")),
            lighting=str(raw.get("lighting", "")),
            mood_tags=coerce_str_list(raw.get("mood_tags")),
            song_section_fit=coerce_str_list(raw.get("song_section_fit")),
            energy_target=str(raw.get("energy_target", "low-mid") or "low-mid"),
            prompts=FramePrompts(),
            created_at=now,
            updated_at=now,
        )
        save_scene(root, scene)
        created.append(scene_id)

    concept.scenes = sorted(set(concept.scenes) | set(created))
    save_concept(root, concept)
    append_log(root, "scenes_imported", concept_id=concept.id, count=len(created), ids=created)

    click.echo(f"✓ Imported {len(created)} scenes for {concept.id}:")
    for sid in created:
        click.echo(f"  {sid}")


def run_list_scenes() -> None:
    root, _bk, _project = _load_context()
    scenes = list_scenes(root)
    if not scenes:
        click.echo("No scenes yet. Pick a concept and run `solypsizm scenes`.")
        return
    by_concept: dict[str, list[Scene]] = {}
    for s in scenes:
        by_concept.setdefault(s.concept_id, []).append(s)
    for cid, group in sorted(by_concept.items()):
        click.echo(f"{cid}:")
        for s in group:
            click.echo(f"  {s.id}  [{s.status}]  {s.title}")


def run_pick_scene(scene_id: str) -> None:
    root, _bk, project = _load_context()
    candidate_ids = [s.id for s in list_scenes(root)]
    try:
        resolved = resolve_id(scene_id, candidate_ids, kind="scene")
    except ValueError as e:
        raise click.ClickException(str(e)) from e
    project.current_scene = resolved
    save_scene_pick(root, project)
    append_log(root, "scene_picked", id=resolved)
    click.echo(f"✓ Current scene set to {resolved}")


def save_scene_pick(root, project) -> None:
    from solypsizm_moment_studio.state import save_project
    save_project(root, project)


def resolve_scene_id(root, scene_id: str | None) -> str:
    """Resolve a scene argument: explicit id (with fuzzy match) → current scene.

    Used by import-frame, import-clip, prompts, select-frame, select-clip,
    review-clips so the artist doesn't retype the full id every time.
    """
    candidates = [s.id for s in list_scenes(root)]
    if scene_id:
        try:
            return resolve_id(scene_id, candidates, kind="scene")
        except ValueError as e:
            raise click.ClickException(str(e)) from e
    project = load_project(root)
    if project.current_scene:
        if project.current_scene in candidates:
            return project.current_scene
        raise click.ClickException(
            f"Current scene {project.current_scene!r} no longer exists. "
            "Run `solypsizm pick-scene <id>` to set a new one."
        )
    raise click.ClickException(
        "No scene specified and no current scene picked. "
        "Pass --scene <id> or run `solypsizm pick-scene <id>` first."
    )


def run_prompts(scene_id: str | None, copy: bool) -> None:
    root, bk, project = _load_context()
    resolved = resolve_scene_id(root, scene_id)
    try:
        scene = _load_scene(root, resolved)
    except FileNotFoundError as e:
        raise click.ClickException(str(e)) from e
    md = scene_prompts_markdown(bk, project, scene)
    out_path = root / "scenes" / scene.concept_id / f"{scene.id}-prompts.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")

    # Update the scene's stored prompts so future commands can read them back.
    from solypsizm_moment_studio.prompts import (
        end_frame_prompt,
        start_frame_prompt,
        veo_motion_prompt,
    )

    scene.prompts = FramePrompts(
        start_frame=start_frame_prompt(bk, project, scene),
        end_frame=end_frame_prompt(bk, project, scene),
        veo_motion=veo_motion_prompt(bk, project, scene),
    )
    if scene.status == "draft":
        scene.status = "prompts_ready"
    save_scene(root, scene)
    append_log(root, "prompts_emitted", scene_id=scene.id)

    if not copy:
        click.echo(md)
        click.echo(f"\n✓ Wrote {out_path}", err=True)
        return

    # Step through the three prompts on the clipboard.
    steps = [
        ("Start frame (ChatGPT image)", scene.prompts.start_frame),
        ("End frame (ChatGPT continuation)", scene.prompts.end_frame),
        ("Veo 3 motion prompt", scene.prompts.veo_motion),
    ]
    for label, body in steps:
        if not clipboard_copy(body):
            click.echo("pbcopy unavailable; falling back to stdout.", err=True)
            click.echo(f"\n--- {label} ---\n{body}\n")
        else:
            click.echo(f"[{label}] copied to clipboard", err=True)
        click.pause(info="Press Enter for the next prompt...", err=True)
    click.echo(f"\n✓ Wrote {out_path}", err=True)
