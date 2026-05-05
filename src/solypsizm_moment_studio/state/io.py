import hashlib
import json
import os
from pathlib import Path
from typing import Any

from solypsizm_moment_studio.models import (
    BrandKit,
    Concept,
    EditConfig,
    Moment,
    Project,
    Scene,
    SongAnalysis,
)
from solypsizm_moment_studio.state.paths import edit_config_path
from solypsizm_moment_studio.utils import now_iso


def file_hash(path: Path) -> str:
    """SHA-256 of a file's contents, used for import-idempotency tracking."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json_atomic(path: Path, data: Any) -> None:
    """Crash-safe write: fsync(tmp) → rename → fsync(parent dir).

    Without the fsyncs, a power loss between the rename and the kernel
    flushing dirty pages can leave a zero-length project.json on APFS / ext4.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    # fsync the directory so the rename itself is durable.
    try:
        dir_fd = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def load_brand_kit(path: Path) -> BrandKit:
    return BrandKit.model_validate(load_json(path))


def load_project(root: Path) -> Project:
    return Project.model_validate(load_json(root / "project.json"))


def save_project(root: Path, project: Project) -> None:
    project.updated_at = now_iso()
    save_json_atomic(root / "project.json", project.model_dump(exclude_none=False))


def _concept_path(root: Path, concept_id: str) -> Path:
    return root / "concepts" / f"{concept_id}.json"


def load_concept(root: Path, concept_id: str) -> Concept:
    return Concept.model_validate(load_json(_concept_path(root, concept_id)))


def save_concept(root: Path, concept: Concept) -> None:
    save_json_atomic(_concept_path(root, concept.id), concept.model_dump())


def list_concepts(root: Path) -> list[Concept]:
    folder = root / "concepts"
    if not folder.is_dir():
        return []
    out: list[Concept] = []
    for path in sorted(folder.glob("*.json")):
        try:
            out.append(Concept.model_validate(load_json(path)))
        except Exception:
            continue
    return out


def _scene_path(root: Path, concept_id: str, scene_id: str) -> Path:
    return root / "scenes" / concept_id / f"{scene_id}.json"


def load_scene(root: Path, scene_id: str) -> Scene:
    """Find a scene by id without requiring its concept folder up front."""
    folder = root / "scenes"
    for concept_folder in folder.iterdir() if folder.is_dir() else []:
        candidate = concept_folder / f"{scene_id}.json"
        if candidate.is_file():
            return Scene.model_validate(load_json(candidate))
    raise FileNotFoundError(f"Scene not found: {scene_id}")


def save_scene(root: Path, scene: Scene) -> None:
    scene.updated_at = now_iso()
    save_json_atomic(_scene_path(root, scene.concept_id, scene.id), scene.model_dump())


def list_scenes(root: Path, concept_id: str | None = None) -> list[Scene]:
    folder = root / "scenes"
    if not folder.is_dir():
        return []
    paths: list[Path] = []
    if concept_id is not None:
        paths = (
            sorted((folder / concept_id).glob("*.json")) if (folder / concept_id).is_dir() else []
        )
    else:
        for sub in sorted(folder.iterdir()):
            if sub.is_dir():
                paths.extend(sorted(sub.glob("*.json")))
    out: list[Scene] = []
    for path in paths:
        try:
            out.append(Scene.model_validate(load_json(path)))
        except Exception:
            continue
    return out


def song_analysis_path(root: Path) -> Path:
    return root / "audio" / "song-analysis.json"


def load_song_analysis(root: Path) -> SongAnalysis:
    return SongAnalysis.model_validate(load_json(song_analysis_path(root)))


def save_song_analysis(root: Path, analysis: SongAnalysis) -> None:
    save_json_atomic(song_analysis_path(root), analysis.model_dump())


def _moment_path(root: Path, moment_id: str) -> Path:
    return root / "moments" / f"{moment_id}.json"


def load_moment(root: Path, moment_id: str) -> Moment:
    return Moment.model_validate(load_json(_moment_path(root, moment_id)))


def save_moment(root: Path, moment: Moment) -> None:
    moment.updated_at = now_iso()
    save_json_atomic(_moment_path(root, moment.id), moment.model_dump())


def list_moments(root: Path) -> list[Moment]:
    folder = root / "moments"
    if not folder.is_dir():
        return []
    out: list[Moment] = []
    for path in sorted(folder.glob("moment-*.json")):
        try:
            out.append(Moment.model_validate(load_json(path)))
        except Exception:
            continue
    return out


def load_edit_config() -> EditConfig:
    """Load ~/solypsizm/edit-config.json, or return default config if absent."""
    path = edit_config_path()
    if path.is_file():
        return EditConfig.model_validate(load_json(path))
    return EditConfig()


def append_log(root: Path, event_type: str, **fields: Any) -> None:
    """Append a JSON line to .state/log.jsonl for traceability.

    Uses an exclusive flock so two `solypsizm` invocations writing at the
    same time can't interleave bytes mid-line. fsync after write so a crash
    doesn't lose the just-recorded event.
    """
    import fcntl

    log_path = root / ".state" / "log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": now_iso(), "event": event_type, **fields}
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with log_path.open("a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
