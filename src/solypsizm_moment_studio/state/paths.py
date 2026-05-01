import os
from pathlib import Path


def solypsizm_home() -> Path:
    """Root for projects and the shared brand kit. Defaults to ~/solypsizm."""
    raw = os.environ.get("SOLYPSIZM_HOME")
    return Path(raw).expanduser() if raw else Path.home() / "solypsizm"


def brand_kit_path() -> Path:
    return solypsizm_home() / "brand-kit.json"


def project_dir(slug: str) -> Path:
    return solypsizm_home() / slug


def find_project_root(start: Path | None = None) -> Path | None:
    """Walk up from `start` (default CWD) looking for a project.json."""
    cur = (start or Path.cwd()).resolve()
    while True:
        if (cur / "project.json").is_file():
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent


def require_project_root(start: Path | None = None) -> Path:
    """Find a project root or raise. Caller can also pass a slug via --project."""
    root = find_project_root(start)
    if root is None:
        raise FileNotFoundError(
            "No project.json found in the current directory or its parents. "
            "Run `solypsizm new <slug>` first or cd into a project."
        )
    return root
