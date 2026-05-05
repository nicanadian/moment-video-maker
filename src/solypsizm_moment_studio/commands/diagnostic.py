"""doctor and log commands (PRD §17)."""

from __future__ import annotations

import json

import click

from solypsizm_moment_studio.state import (
    brand_kit_path,
    list_concepts,
    list_scenes,
    load_brand_kit,
    load_project,
    require_project_root,
    song_analysis_path,
)


def _check_environment() -> tuple[list[str], list[str]]:
    """Return (issues, info) about CLI environment: external bins + Python deps + SOLYPSIZM_HOME."""
    import shutil as _sh

    from solypsizm_moment_studio.state import brand_kit_path, solypsizm_home

    issues: list[str] = []
    info: list[str] = []

    home = solypsizm_home()
    info.append(f"SOLYPSIZM_HOME = {home}")
    if not home.exists():
        issues.append(
            f"SOLYPSIZM_HOME ({home}) doesn't exist; run "
            "`solypsizm bootstrap-brand-kit` to populate it."
        )

    bk = brand_kit_path()
    if bk.is_file():
        info.append(f"brand-kit.json ✓ at {bk}")
    else:
        issues.append(
            f"brand-kit.json missing at {bk}; run `solypsizm bootstrap-brand-kit --source <path>`."
        )

    for binary, role in [
        ("ffplay", "audio preview during `review-moment`"),
        ("ffmpeg", "non-WAV audio formats in `analyze`"),
        ("pbcopy", "clipboard copy on macOS"),
        ("open", "launching Finder from `review-clips`"),
    ]:
        path = _sh.which(binary)
        if path:
            info.append(f"{binary} ✓ ({path})")
        else:
            issues.append(f"{binary} not found — needed for {role}.")

    try:
        import librosa  # noqa: F401

        info.append("librosa ✓ installed")
    except ImportError:
        issues.append(
            "librosa not installed — `analyze` won't work. Run `pip install -e '.[audio]'`."
        )

    return issues, info


def run_doctor(check_global: bool = False) -> None:
    if check_global:
        issues, info = _check_environment()
        for line in info:
            click.echo(f"  {line}")
        if not issues:
            click.echo("\n✓ doctor (global): no issues.")
            return
        click.echo(f"\n✗ doctor (global) found {len(issues)} issue(s):")
        for line in issues:
            click.echo(f"  - {line}")
        raise click.exceptions.Exit(1)

    root = require_project_root()
    issues: list[str] = []

    try:
        project = load_project(root)
    except Exception as e:
        raise click.ClickException(f"project.json failed to load: {e}") from e

    # Check core files.
    for label, rel in [("lyrics", project.lyrics_file), ("audio", project.audio_file)]:
        if not (root / rel).is_file():
            issues.append(f"missing {label} file: {rel}")

    # Brand kit resolution.
    bk_target = (root / project.brand_kit_path).resolve()
    if bk_target.is_file():
        try:
            load_brand_kit(bk_target)
        except Exception as e:
            issues.append(f"brand kit at {bk_target} failed validation: {e}")
    else:
        bk_default = brand_kit_path()
        if bk_default.is_file():
            issues.append(
                f"brand_kit_path={project.brand_kit_path!r} doesn't resolve "
                f"(would point at {bk_target}); the canonical kit at {bk_default} does exist."
            )
        else:
            issues.append(
                f"brand kit not found at {bk_target} or {bk_default}. "
                "Run `solypsizm bootstrap-brand-kit`."
            )

    # Concepts and scenes.
    concept_ids = {c.id for c in list_concepts(root)}
    if project.current_concept and project.current_concept not in concept_ids:
        issues.append(f"project.current_concept={project.current_concept!r} not found on disk.")
    for ref in project.concepts:
        if ref not in concept_ids:
            issues.append(f"project.concepts references unknown {ref!r}.")

    scenes_by_concept: dict[str, set[str]] = {}
    for s in list_scenes(root):
        scenes_by_concept.setdefault(s.concept_id, set()).add(s.id)

        # Frame and clip files exist?
        scene_dir = root / "scenes" / s.concept_id
        for slot, frames in s.frames.items():
            for f in frames:
                if not (scene_dir / f"{s.id}-frames" / f.file).is_file():
                    issues.append(f"{s.id}: missing {slot} frame file {f.file}")
        for c in s.clip_takes:
            if not (scene_dir / f"{s.id}-clips" / c.file).is_file():
                issues.append(f"{s.id}: missing clip file {c.file}")

    # Concept ↔ scenes back-references.
    for c in list_concepts(root):
        for sid in c.scenes:
            if sid not in scenes_by_concept.get(c.id, set()):
                issues.append(f"{c.id}: references scene {sid!r} not on disk.")

    # Song analysis is informational only.
    if not song_analysis_path(root).is_file():
        click.echo("ℹ song-analysis.json not present (run `solypsizm analyze` when ready).")

    if not issues:
        click.echo("✓ doctor: no issues.")
        return
    click.echo(f"✗ doctor found {len(issues)} issue(s):")
    for line in issues:
        click.echo(f"  - {line}")
    raise click.exceptions.Exit(1)


def run_log(tail: int, show_all: bool, event: str | None, since: str | None) -> None:
    root = require_project_root()
    log_path = root / ".state" / "log.jsonl"
    if not log_path.is_file():
        click.echo("(no operations logged yet)")
        return
    records: list[dict] = []
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                # Surface the corrupt line; don't drop it silently.
                records.append({"ts": "", "event": "_unparsed", "raw": line})

    # Apply filters.
    if event:
        records = [r for r in records if r.get("event") == event]
    if since:
        records = [r for r in records if str(r.get("ts", "")) >= since]
    if not show_all and tail > 0:
        records = records[-tail:]

    if not records:
        click.echo("(no matching events)")
        return
    for rec in records:
        ts = rec.pop("ts", "")
        evt = rec.pop("event", "")
        extra = " ".join(f"{k}={v}" for k, v in rec.items())
        click.echo(f"{ts}  {evt:<22} {extra}")
