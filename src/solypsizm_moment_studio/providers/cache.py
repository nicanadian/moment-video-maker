"""Per-project idempotent cache for provider calls.

Cache hits don't count against the daily budget — they cost $0. Re-running
the same prompt against the same provider/model with the same params
returns the original artifact.

Layout::

    <project>/.cache/api/<sha256-prefix>.json     # CompletionResult / metadata
    <project>/.cache/api/<sha256-prefix>.png      # Image bytes (if any)
    <project>/.cache/api/<sha256-prefix>.mp4      # Video bytes (if any)
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


def cache_dir(project_root: Path) -> Path:
    return project_root / ".cache" / "api"


def _hash_inputs(
    *,
    provider: str,
    model: str,
    kind: str,
    prompt: str,
    params: dict[str, Any] | None = None,
    reference_path: Path | None = None,
) -> str:
    h = hashlib.sha256()
    h.update(provider.encode())
    h.update(b"\x00")
    h.update(model.encode())
    h.update(b"\x00")
    h.update(kind.encode())
    h.update(b"\x00")
    h.update(prompt.encode())
    h.update(b"\x00")
    if params:
        h.update(json.dumps(params, sort_keys=True).encode())
    if reference_path is not None and reference_path.is_file():
        with reference_path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    return h.hexdigest()


def lookup_text(
    project_root: Path,
    *,
    provider: str,
    model: str,
    prompt: str,
    params: dict[str, Any] | None = None,
) -> dict | None:
    """Return the stored CompletionResult dict if cached, else None."""
    key = _hash_inputs(provider=provider, model=model, kind="text", prompt=prompt, params=params)
    path = cache_dir(project_root) / f"{key}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def store_text(
    project_root: Path,
    *,
    provider: str,
    model: str,
    prompt: str,
    result: dict,
    params: dict[str, Any] | None = None,
) -> None:
    folder = cache_dir(project_root)
    folder.mkdir(parents=True, exist_ok=True)
    key = _hash_inputs(provider=provider, model=model, kind="text", prompt=prompt, params=params)
    path = folder / f"{key}.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")


def lookup_artifact(
    project_root: Path,
    *,
    provider: str,
    model: str,
    kind: str,  # "image" or "video"
    prompt: str,
    params: dict[str, Any] | None = None,
    reference_path: Path | None = None,
) -> tuple[Path, dict] | None:
    """Return (artifact_path, metadata_dict) if cached."""
    key = _hash_inputs(
        provider=provider,
        model=model,
        kind=kind,
        prompt=prompt,
        params=params,
        reference_path=reference_path,
    )
    folder = cache_dir(project_root)
    meta_path = folder / f"{key}.json"
    if kind == "image":
        artifact_path = folder / f"{key}.png"
    elif kind == "video":
        artifact_path = folder / f"{key}.mp4"
    else:
        return None
    if not (meta_path.is_file() and artifact_path.is_file()):
        return None
    return artifact_path, json.loads(meta_path.read_text(encoding="utf-8"))


def store_artifact(
    project_root: Path,
    *,
    provider: str,
    model: str,
    kind: str,
    prompt: str,
    artifact_source: Path,
    metadata: dict,
    params: dict[str, Any] | None = None,
    reference_path: Path | None = None,
) -> Path:
    """Copy the artifact into the cache and persist its metadata. Returns
    the cached artifact's path so the caller can hand it to the import
    pipeline."""
    folder = cache_dir(project_root)
    folder.mkdir(parents=True, exist_ok=True)
    key = _hash_inputs(
        provider=provider,
        model=model,
        kind=kind,
        prompt=prompt,
        params=params,
        reference_path=reference_path,
    )
    suffix = ".png" if kind == "image" else ".mp4"
    artifact_dest = folder / f"{key}{suffix}"
    shutil.copy2(artifact_source, artifact_dest)
    meta_path = folder / f"{key}.json"
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return artifact_dest


def prune(project_root: Path, *, older_than_days: int = 30) -> int:
    """Drop cached artifacts older than ``older_than_days``. Returns number
    of files removed."""
    import time

    folder = cache_dir(project_root)
    if not folder.is_dir():
        return 0
    cutoff = time.time() - older_than_days * 86400
    removed = 0
    for path in folder.iterdir():
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed
