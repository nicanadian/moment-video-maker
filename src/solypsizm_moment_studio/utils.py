import re
import shutil
import subprocess
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_slug_re = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_words: int | None = None) -> str:
    s = _slug_re.sub("-", text.lower()).strip("-")
    if max_words is not None:
        s = "-".join(s.split("-")[:max_words])
    return s


def clipboard_copy(text: str) -> bool:
    """Copy text to the macOS clipboard via pbcopy. Returns True on success."""
    pbcopy = shutil.which("pbcopy")
    if not pbcopy:
        return False
    try:
        subprocess.run([pbcopy], input=text.encode("utf-8"), check=True)
        return True
    except subprocess.CalledProcessError:
        return False
