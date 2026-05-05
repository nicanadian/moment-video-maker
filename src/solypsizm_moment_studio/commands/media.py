"""Frame and clip imports + selection (PRD §F4, §F5)."""

from __future__ import annotations

import contextlib
import shutil
import subprocess
from pathlib import Path

import click

from solypsizm_moment_studio.models import ClipTake, Frame, Scene
from solypsizm_moment_studio.state import (
    append_log,
    file_hash,
    list_scenes,
    load_scene,
    require_project_root,
    save_scene,
)
from solypsizm_moment_studio.utils import now_iso


def _scene_dir(root: Path, scene: Scene) -> Path:
    return root / "scenes" / scene.concept_id


def _frames_dir(root: Path, scene: Scene) -> Path:
    return _scene_dir(root, scene) / f"{scene.id}-frames"


def _clips_dir(root: Path, scene: Scene) -> Path:
    return _scene_dir(root, scene) / f"{scene.id}-clips"


def _find_existing_hash(root: Path, hash_value: str) -> str | None:
    """Search every scene's frames + clips for a file with this hash.

    Skips records whose on-disk file no longer exists — that lets the artist
    delete a bad take and re-import the same content without hand-editing the
    scene JSON (review-feedback, QA #critical-1).
    """
    for s in list_scenes(root):
        scene_dir = root / "scenes" / s.concept_id
        for slot, frames in s.frames.items():
            for f in frames:
                if (
                    f.hash
                    and f.hash == hash_value
                    and (scene_dir / f"{s.id}-frames" / f.file).is_file()
                ):
                    return f"{s.id}/{slot}/{f.file}"
        for clip in s.clip_takes:
            if (
                clip.hash
                and clip.hash == hash_value
                and (scene_dir / f"{s.id}-clips" / clip.file).is_file()
            ):
                return f"{s.id}/clips/{clip.file}"
    return None


def _next_frame_filename(scene: Scene, slot: str, suffix: str) -> str:
    existing = scene.frames.get(slot, [])
    return f"{slot}-v{len(existing) + 1}{suffix.lower()}"


def _next_take_filename(scene: Scene, suffix: str) -> str:
    return f"take-{len(scene.clip_takes) + 1:02d}{suffix.lower()}"


# ---------------------------------------------------------------------------
# import-frame
# ---------------------------------------------------------------------------


def _stage_and_commit(src: Path, target_path: Path, move: bool) -> None:
    """Place the source at target_path. Defaults to copy so a rejected
    re-import doesn't delete the source from ~/Downloads. ``--move`` opt-in
    matches the original PRD §F4 wording for users who want a clean Downloads.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if move:
        shutil.move(str(src), target_path)
    else:
        shutil.copy2(str(src), target_path)


def run_import_frame(file: str, scene_id: str | None, frame_type: str, move: bool = False) -> None:
    root = require_project_root()
    from solypsizm_moment_studio.commands.scenes import resolve_scene_id

    resolved = resolve_scene_id(root, scene_id)
    try:
        scene = load_scene(root, resolved)
    except FileNotFoundError as e:
        raise click.ClickException(str(e)) from e

    src = Path(file).expanduser().resolve()
    suffix = src.suffix
    if suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise click.ClickException(
            f"Unexpected frame extension {suffix!r}. Expected .png/.jpg/.jpeg/.webp."
        )

    h = file_hash(src)
    duplicate_at = _find_existing_hash(root, h)
    if duplicate_at:
        raise click.ClickException(
            f"This file is already imported at {duplicate_at}. Skipping to avoid duplicate frames."
        )

    target_dir = _frames_dir(root, scene)
    target_name = _next_frame_filename(scene, frame_type, suffix)
    target_path = target_dir / target_name
    _stage_and_commit(src, target_path, move)
    try:
        scene.frames.setdefault(frame_type, []).append(
            Frame(file=target_name, imported_at=now_iso(), hash=h)
        )
        if scene.status == "draft" or scene.status == "prompts_ready":
            scene.status = "frames_imported"
        save_scene(root, scene)
    except Exception:
        # Roll back the file landing so we don't orphan the import.
        if target_path.is_file():
            target_path.unlink()
        raise
    append_log(root, "frame_imported", scene_id=scene.id, type=frame_type, file=target_name)
    op = "Moved" if move else "Copied"
    click.echo(f"✓ {op} as {target_name} → {target_path.relative_to(root)}")


# ---------------------------------------------------------------------------
# select-frame
# ---------------------------------------------------------------------------


def run_select_frame(scene_id: str | None, frame_type: str, filename: str) -> None:
    root = require_project_root()
    from solypsizm_moment_studio.commands.scenes import resolve_scene_id

    resolved = resolve_scene_id(root, scene_id)
    scene = load_scene(root, resolved)
    frames = scene.frames.get(frame_type, [])
    match = next((f for f in frames if f.file == filename), None)
    if match is None:
        raise click.ClickException(f"No {frame_type} frame named {filename} on {scene_id}.")
    for f in frames:
        f.selected = f is match
    save_scene(root, scene)
    append_log(root, "frame_selected", scene_id=scene.id, type=frame_type, file=filename)
    click.echo(f"✓ Selected {frame_type} frame: {filename}")


# ---------------------------------------------------------------------------
# import-clip
# ---------------------------------------------------------------------------


def run_import_clip(
    file: str,
    scene_id: str | None,
    rating: int | None,
    notes: str,
    move: bool = False,
) -> None:
    root = require_project_root()
    from solypsizm_moment_studio.commands.scenes import resolve_scene_id

    resolved = resolve_scene_id(root, scene_id)
    try:
        scene = load_scene(root, resolved)
    except FileNotFoundError as e:
        raise click.ClickException(str(e)) from e

    src = Path(file).expanduser().resolve()
    suffix = src.suffix
    if suffix.lower() not in {".mp4", ".mov", ".webm"}:
        raise click.ClickException(
            f"Unexpected clip extension {suffix!r}. Expected .mp4/.mov/.webm."
        )

    h = file_hash(src)
    duplicate_at = _find_existing_hash(root, h)
    if duplicate_at:
        raise click.ClickException(
            f"This file is already imported at {duplicate_at}. Skipping to avoid duplicate clips."
        )

    target_dir = _clips_dir(root, scene)
    target_name = _next_take_filename(scene, suffix)
    target_path = target_dir / target_name
    _stage_and_commit(src, target_path, move)
    try:
        scene.clip_takes.append(
            ClipTake(
                file=target_name,
                imported_at=now_iso(),
                rating=rating,
                notes=notes,
                hash=h,
            )
        )
        if scene.status in {"draft", "prompts_ready", "frames_imported"}:
            scene.status = "clips_imported"
        save_scene(root, scene)
    except Exception:
        if target_path.is_file():
            target_path.unlink()
        raise
    append_log(
        root,
        "clip_imported",
        scene_id=scene.id,
        file=target_name,
        rating=rating,
        notes=notes,
    )
    rating_str = f" ★{rating}" if rating else ""
    op = "Moved" if move else "Copied"
    click.echo(f"✓ {op} as {target_name}{rating_str} → {target_path.relative_to(root)}")


# ---------------------------------------------------------------------------
# select-clip
# ---------------------------------------------------------------------------


def run_select_clip(scene_id: str | None, filename: str) -> None:
    root = require_project_root()
    from solypsizm_moment_studio.commands.scenes import resolve_scene_id

    resolved = resolve_scene_id(root, scene_id)
    scene = load_scene(root, resolved)
    match = next((c for c in scene.clip_takes if c.file == filename), None)
    if match is None:
        raise click.ClickException(f"No clip named {filename} on {scene_id}.")
    for c in scene.clip_takes:
        c.selected = c is match
    if scene.status != "complete":
        scene.status = "complete"
    save_scene(root, scene)
    append_log(root, "clip_selected", scene_id=scene.id, file=filename)
    click.echo(f"✓ Selected clip: {filename}")


# ---------------------------------------------------------------------------
# review-clips
# ---------------------------------------------------------------------------


def run_review_clips(scene_id: str | None) -> None:
    root = require_project_root()
    from solypsizm_moment_studio.commands.scenes import resolve_scene_id

    resolved = resolve_scene_id(root, scene_id)
    scene = load_scene(root, resolved)
    if not scene.clip_takes:
        click.echo(f"No clips on {scene.id} yet.")
        return

    folder = _clips_dir(root, scene)
    click.echo(f"{scene.id} — {scene.title}")
    click.echo(f"Folder: {folder}")
    click.echo("")
    click.echo(f"{'sel':<4} {'file':<24} {'rating':<7} notes")
    click.echo("-" * 70)
    for c in scene.clip_takes:
        sel = "★" if c.selected else " "
        rating = f"{c.rating}/5" if c.rating else "-"
        click.echo(f" {sel}   {c.file:<24} {rating:<7} {c.notes}")

    # Open in Finder so the artist can preview side-by-side.
    if folder.is_dir():
        with contextlib.suppress(FileNotFoundError):
            subprocess.run(["open", str(folder)], check=False)
