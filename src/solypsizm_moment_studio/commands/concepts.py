"""Concept commands: brainstorm, import-concepts, list, pick, rate."""

from __future__ import annotations

from pathlib import Path

import click

from solypsizm_moment_studio.models import Concept
from solypsizm_moment_studio.prompts import (
    ParseError,
    brainstorm_prompt,
    parse_concepts_response,
)
from solypsizm_moment_studio.state import (
    append_log,
    brand_kit_path,
    list_concepts,
    load_brand_kit,
    load_concept,
    load_project,
    require_project_root,
    save_concept,
    save_project,
)
from solypsizm_moment_studio.utils import clipboard_copy, coerce_str_list, resolve_id, slugify


def _load_context() -> tuple[Path, "BrandKit", "Project"]:  # noqa: F821
    from solypsizm_moment_studio.models import BrandKit, Project  # noqa: F401

    root = require_project_root()
    project = load_project(root)
    # Prefer project.brand_kit_path (resolved relative to project dir); fall
    # back to the canonical ~/solypsizm/brand-kit.json. This was previously
    # dead config that the doctor checked but no command actually consulted.
    candidate = (root / project.brand_kit_path).resolve()
    bk_path = candidate if candidate.is_file() else brand_kit_path()
    if not bk_path.is_file():
        raise click.ClickException(
            f"Brand kit not found at {candidate} or {brand_kit_path()}. "
            "Run `solypsizm bootstrap-brand-kit` first."
        )
    bk = load_brand_kit(bk_path)
    return root, bk, project


def run_brainstorm(count: int, copy: bool) -> None:
    root, bk, project = _load_context()
    lyrics_path = root / project.lyrics_file
    if not lyrics_path.is_file():
        raise click.ClickException(f"Missing {lyrics_path}.")
    lyrics = lyrics_path.read_text(encoding="utf-8")
    prompt = brainstorm_prompt(bk, project, lyrics, count=count)
    click.echo(prompt)
    if copy:
        if clipboard_copy(prompt):
            click.echo("\n— copied to clipboard —", err=True)
        else:
            click.echo("\n— pbcopy unavailable; prompt printed above only —", err=True)
    append_log(root, "brainstorm_emitted", count=count)


def _next_concept_index(root: Path) -> int:
    existing = list_concepts(root)
    return len(existing) + 1


def run_import_concepts(input_file) -> None:
    root, _bk, project = _load_context()
    text = input_file.read()
    try:
        items = parse_concepts_response(text)
    except ParseError as e:
        last_import = root / ".state" / "last-import.txt"
        last_import.parent.mkdir(parents=True, exist_ok=True)
        last_import.write_text(text, encoding="utf-8")
        raise click.ClickException(
            f"Could not parse response: {e}. Raw input saved to {last_import}."
        ) from e

    next_idx = _next_concept_index(root)
    created: list[str] = []
    for offset, raw in enumerate(items):
        idx = next_idx + offset
        # Preserve the artist's display title verbatim (even unicode-only) and
        # only fall back the slug when slugify would yield empty.
        title_raw = str(raw.get("title", "")).strip()
        title = title_raw or f"Concept {idx}"
        concept_id = f"concept-{idx:02d}-{slugify(title, max_words=4, fallback='untitled')}"
        concept = Concept(
            id=concept_id,
            title=title,
            summary=str(raw.get("summary", "")),
            song_themes_referenced=coerce_str_list(raw.get("song_themes_referenced")),
            brand_alignment_notes=str(raw.get("brand_alignment_notes", "")),
            estimated_runtime_seconds=int(raw.get("estimated_runtime_seconds", 22) or 22),
            scene_count=int(raw.get("scene_count", 4) or 4),
        )
        save_concept(root, concept)
        created.append(concept_id)

    project.concepts = sorted(set(project.concepts) | set(created))
    save_project(root, project)
    append_log(root, "concepts_imported", count=len(created), ids=created)

    click.echo(f"✓ Imported {len(created)} concepts:")
    for cid in created:
        click.echo(f"  {cid}")


def run_list_concepts() -> None:
    root, _bk, project = _load_context()
    concepts = list_concepts(root)
    if not concepts:
        click.echo("No concepts yet. Run `solypsizm brainstorm` to start.")
        return
    for c in concepts:
        marker = "*" if c.id == project.current_concept else " "
        rating = f" ★{c.rating}" if c.rating else ""
        click.echo(f"{marker} {c.id}  [{c.status}{rating}]  {c.title}")
    click.echo("\n* = current concept")


def run_pick_concept(concept_id: str) -> None:
    root, _bk, project = _load_context()
    candidate_ids = [c.id for c in list_concepts(root)]
    try:
        resolved = resolve_id(concept_id, candidate_ids, kind="concept")
    except ValueError as e:
        raise click.ClickException(str(e)) from e
    concept = load_concept(root, resolved)
    project.current_concept = resolved
    if concept.status == "draft":
        concept.status = "in_progress"
        save_concept(root, concept)
    save_project(root, project)
    append_log(root, "concept_picked", id=resolved)
    click.echo(f"✓ Current concept set to {resolved} — {concept.title}")


def run_rate_concept(concept_id: str, rating: int, notes: str) -> None:
    root, _bk, _project = _load_context()
    candidate_ids = [c.id for c in list_concepts(root)]
    try:
        resolved = resolve_id(concept_id, candidate_ids, kind="concept")
    except ValueError as e:
        raise click.ClickException(str(e)) from e
    concept = load_concept(root, resolved)
    concept.rating = rating
    if notes:
        concept.notes = notes
    save_concept(root, concept)
    append_log(root, "concept_rated", id=resolved, rating=rating)
    click.echo(f"✓ Rated {resolved}: ★{rating}")
