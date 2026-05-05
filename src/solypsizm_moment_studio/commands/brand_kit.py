"""bootstrap-brand-kit: install or refresh ~/solypsizm/brand-kit.json.

Phase A scope: copy a hand-authored JSON source into the canonical location.
Future scope: extract structure from the .docx (PRD §11). For now a clear error
points the artist at the JSON source they should edit.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import click

from solypsizm_moment_studio.models import BrandKit
from solypsizm_moment_studio.state import brand_kit_path, solypsizm_home


def run(source: str | None, out: str | None, force: bool) -> None:
    src_path = Path(source) if source else Path.cwd() / "brand-kit.json"
    out_path = Path(out) if out else brand_kit_path()

    if not src_path.is_file():
        raise click.ClickException(
            f"Source not found: {src_path}. Pass --source to point at your brand-kit.json."
        )
    if src_path.suffix.lower() == ".docx":
        raise click.ClickException(
            "Direct .docx extraction isn't implemented yet. Edit brand-kit.json by hand "
            "(use the repo's checked-in copy as a starting point) and re-run with --source "
            "pointing at that file."
        )
    if src_path.suffix.lower() != ".json":
        raise click.ClickException(f"Expected a .json source, got {src_path.suffix}.")

    # Validate before installing so we never overwrite with garbage.
    try:
        BrandKit.model_validate(json.loads(src_path.read_text(encoding="utf-8")))
    except Exception as e:
        raise click.ClickException(f"Source brand kit failed validation: {e}") from e

    if out_path.exists() and not force:
        raise click.ClickException(f"{out_path} already exists. Pass --force to overwrite.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_path, out_path)

    # Mirror sibling character-reference/ folder into the same destination so the
    # paths in the brand kit (e.g. character.reference_image) resolve relative
    # to the installed brand-kit.json.
    src_refs = src_path.parent / "character-reference"
    if src_refs.is_dir():
        dest_refs = out_path.parent / "character-reference"
        if dest_refs.exists() and not force:
            click.echo(f"⚠ {dest_refs} already exists; not overwriting (use --force).", err=True)
        else:
            if dest_refs.exists():
                shutil.rmtree(dest_refs)
            shutil.copytree(src_refs, dest_refs)
            click.echo(f"✓ Installed character-reference/ to {dest_refs}")

    home = solypsizm_home()
    click.echo(f"✓ Installed brand kit to {out_path}")
    if out_path.parent == home:
        click.echo(f"  SOLYPSIZM_HOME = {home}")
