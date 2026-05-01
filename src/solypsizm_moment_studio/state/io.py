import json
import os
from pathlib import Path
from typing import Any

from solypsizm_moment_studio.models import BrandKit, Concept, Project, Scene
from solypsizm_moment_studio.utils import now_iso


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json_atomic(path: Path, data: Any) -> None:
    """Write to <path>.tmp and rename, so a crash mid-write can't corrupt the target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


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
        paths = sorted((folder / concept_id).glob("*.json")) if (folder / concept_id).is_dir() else []
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


def append_log(root: Path, event_type: str, **fields: Any) -> None:
    """Append a JSON line to .state/log.jsonl for traceability."""
    log_path = root / ".state" / "log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": now_iso(), "event": event_type, **fields}
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
