"""Scene commands: scenes, import-scenes, list-scenes, prompts."""

from __future__ import annotations

import contextlib
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


def _load_context() -> tuple[Path, BrandKit, Project]:  # noqa: F821
    # Mirrors commands/concepts.py — keeps project.brand_kit_path live.
    root = require_project_root()
    project = load_project(root)
    candidate = (root / project.brand_kit_path).resolve()
    bk_path = candidate if candidate.is_file() else brand_kit_path()
    if not bk_path.is_file():
        raise click.ClickException(
            f"Brand kit not found at {candidate} or {brand_kit_path()}. "
            "Run `solypsizm bootstrap-brand-kit` first."
        )
    bk = load_brand_kit(bk_path)
    return root, bk, project


def _require_current_concept(root: Path, project) -> Concept:  # noqa: F821
    if not project.current_concept:
        raise click.ClickException("No current concept. Run `solypsizm pick-concept <id>` first.")
    return load_concept(root, project.current_concept)


def run_scenes(copy: bool, api: bool, model: str | None) -> None:
    root, bk, project = _load_context()
    concept = _require_current_concept(root, project)
    prompt = scenes_prompt(bk, project, concept)

    if api:
        from solypsizm_moment_studio.providers import dispatch, registry
        from solypsizm_moment_studio.providers.exceptions import (
            BudgetExceeded,
            ProviderError,
        )

        spec = model or registry.DEFAULT_TEXT
        click.echo(f"Calling {spec}...", err=True)
        try:
            result = dispatch.call_text(
                root,
                spec,
                system="You are breaking concepts into scenes for short-form music videos. "
                "Reply with strict JSON only — no markdown fences, no prose.",
                user=prompt,
            )
        except BudgetExceeded as e:
            raise click.ClickException(str(e)) from e
        except ProviderError as e:
            raise click.ClickException(f"Provider call failed: {e}") from e

        cache_marker = " [cache]" if result.cache_hit else ""
        click.echo(
            f"✓ {spec}{cache_marker}: {result.latency_ms}ms, ${result.cost_usd:.4f}",
            err=True,
        )
        try:
            items = parse_scenes_response(result.text)
        except ParseError as e:
            last_import = root / ".state" / "last-import.txt"
            last_import.parent.mkdir(parents=True, exist_ok=True)
            last_import.write_text(result.text, encoding="utf-8")
            raise click.ClickException(
                f"API response didn't parse: {e}. Raw saved to {last_import}."
            ) from e

        _persist_scenes(root, project, concept, items, source="api")
        append_log(root, "scenes_api", concept_id=concept.id, model=spec, cache=result.cache_hit)
        return

    click.echo(prompt)
    if copy:
        if clipboard_copy(prompt):
            click.echo("\n— copied to clipboard —", err=True)
        else:
            click.echo("\n— pbcopy unavailable; prompt printed above only —", err=True)
    append_log(root, "scenes_emitted", concept_id=concept.id)


def _persist_scenes(root, project, concept, items, source: str) -> None:
    """Shared body for `import-scenes` and `scenes --api` paths."""
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
    append_log(
        root,
        "scenes_imported",
        concept_id=concept.id,
        count=len(created),
        ids=created,
        source=source,
    )
    click.echo(f"✓ Imported {len(created)} scenes for {concept.id}:")
    for sid in created:
        click.echo(f"  {sid}")


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

    _persist_scenes(root, project, concept, items, source="paste")


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


def _run_prompts_api(
    root, bk, project, scene, image_model, video_model, dry_run: bool = False
) -> None:
    """Direct generation: start frame → end frame → motion clip, scored and
    imported into the scene as the selected take."""
    from solypsizm_moment_studio.commands.media import (
        run_import_clip,
        run_import_frame,
    )
    from solypsizm_moment_studio.prompts import (
        end_frame_prompt,
        start_frame_prompt,
        veo_motion_prompt,
    )
    from solypsizm_moment_studio.providers import dispatch, registry
    from solypsizm_moment_studio.providers.exceptions import (
        BudgetExceeded,
        ProviderError,
    )

    image_spec = image_model or registry.DEFAULT_IMAGE
    video_spec = video_model or registry.DEFAULT_VIDEO

    # Resolve the canonical reference image once.
    from solypsizm_moment_studio.state import brand_kit_path

    bk_dir = brand_kit_path().parent
    reference = (bk_dir / bk.character.reference_image).resolve()
    if not reference.is_file():
        raise click.ClickException(
            f"Reference image not found at {reference}. "
            "Run `solypsizm bootstrap-brand-kit` to install character-reference/."
        )

    scene_dir = root / "scenes" / scene.concept_id

    start_prompt = start_frame_prompt(bk, project, scene)
    end_prompt = end_frame_prompt(bk, project, scene)
    veo_prompt = veo_motion_prompt(bk, project, scene)

    if dry_run:
        plan_path = scene_dir / f"{scene.id}-api-dry-run.md"
        plan = (
            f"# API dry run — {scene.id}\n\n"
            f"Image model: `{image_spec}`\n\n"
            f"Video model: `{video_spec}`\n\n"
            "## 1. Start frame prompt\n\n"
            f"```\n{start_prompt}\n```\n\n"
            "## 2. End frame prompt\n\n"
            f"```\n{end_prompt}\n```\n\n"
            "## 3. Motion prompt\n\n"
            f"```\n{veo_prompt}\n```\n"
        )
        plan_path.write_text(plan, encoding="utf-8")
        click.echo(f"DRY RUN: wrote API generation plan to {plan_path}")
        return

    staging = scene_dir / f"{scene.id}-staging"
    staging.mkdir(parents=True, exist_ok=True)
    start_path = staging / "start.png"
    end_path = staging / "end.png"
    clip_path = staging / "motion.mp4"

    try:
        click.echo(f"[1/3] start frame via {image_spec}...", err=True)
        start = dispatch.call_image(
            root,
            image_spec,
            prompt=start_prompt,
            out_path=start_path,
            reference=reference,
        )
        start_cache = " [cache]" if start.cache_hit else ""
        click.echo(
            f"      ✓ {start.latency_ms}ms, ${start.cost_usd:.4f}{start_cache}",
            err=True,
        )

        click.echo(f"[2/3] end frame via {image_spec}...", err=True)
        end = dispatch.call_image(
            root,
            image_spec,
            prompt=end_prompt,
            out_path=end_path,
            reference=start_path,  # end-frame uses start as the seed
        )
        click.echo(
            f"      ✓ {end.latency_ms}ms, ${end.cost_usd:.4f}{' [cache]' if end.cache_hit else ''}",
            err=True,
        )

        click.echo(f"[3/3] motion clip via {video_spec} (~30-90s)...", err=True)
        motion = dispatch.call_video(
            root,
            video_spec,
            prompt=veo_prompt,
            out_path=clip_path,
            start_frame=start_path,
            end_frame=end_path,
            duration_seconds=float(scene.duration_target_seconds or 6.0),
        )
        motion_cache = " [cache]" if motion.cache_hit else ""
        click.echo(
            f"      ✓ {motion.latency_ms}ms, ${motion.cost_usd:.4f}{motion_cache}",
            err=True,
        )
    except BudgetExceeded as e:
        raise click.ClickException(str(e)) from e
    except ProviderError as e:
        raise click.ClickException(f"Provider call failed: {e}") from e
    except ValueError as e:
        raise click.ClickException(str(e)) from e

    # Hand off to the existing import pipeline (move-mode so we don't
    # duplicate the staged files into the scene folder + the cache).
    run_import_frame(str(start_path), scene_id=scene.id, frame_type="start", move=True)
    run_import_frame(str(end_path), scene_id=scene.id, frame_type="end", move=True)
    run_import_clip(
        str(clip_path), scene_id=scene.id, rating=None, notes="auto-generated", move=True
    )
    # Clean up staging.
    with contextlib.suppress(OSError):
        staging.rmdir()

    append_log(
        root,
        "prompts_api",
        scene_id=scene.id,
        image_model=image_spec,
        video_model=video_spec,
        total_cost_usd=round(start.cost_usd + end.cost_usd + motion.cost_usd, 4),
    )
    click.echo(
        f"✓ Generated start + end + motion for {scene.id} via API "
        f"(total ${start.cost_usd + end.cost_usd + motion.cost_usd:.4f})",
        err=True,
    )


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


def run_prompts(
    scene_id: str | None,
    copy: bool,
    api: bool = False,
    image_model: str | None = None,
    video_model: str | None = None,
    dry_run: bool = False,
) -> None:
    root, bk, project = _load_context()
    resolved = resolve_scene_id(root, scene_id)
    try:
        scene = _load_scene(root, resolved)
    except FileNotFoundError as e:
        raise click.ClickException(str(e)) from e

    if api:
        _run_prompts_api(root, bk, project, scene, image_model, video_model, dry_run=dry_run)
        return
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
