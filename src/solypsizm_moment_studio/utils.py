import re
import shutil
import subprocess
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_slug_re = re.compile(r"[^a-z0-9]+")

# Drop common filler tokens so IDs read like "abandoned-watchtower-dawn" rather
# than "abandoned-watchtower-at-dawn".
_SLUG_STOPWORDS = frozenset(
    {"a", "an", "the", "of", "to", "and", "or", "in", "on", "at", "by", "for", "with"}
)


def slugify(text: str, max_words: int | None = None, fallback: str = "untitled") -> str:
    """Lowercase, ASCII-letter/digit, dash-separated, stopword-filtered.
    Returns ``fallback`` when the input has no slug-able characters."""
    s = _slug_re.sub("-", text.lower()).strip("-")
    if not s:
        return fallback
    parts = [p for p in s.split("-") if p and p not in _SLUG_STOPWORDS]
    if not parts:
        return fallback
    if max_words is not None:
        parts = parts[:max_words]
    return "-".join(parts)


def coerce_str_list(value) -> list[str]:
    """Defensively coerce a value to a list of strings.

    ChatGPT will sometimes return a single string where a list is expected
    (``"intro"`` instead of ``["intro"]``). The naive ``list(value)`` would
    char-iterate the string into ``["i", "n", "t", "r", "o"]``, silently
    corrupting data. This wraps a string as a one-item list and otherwise
    coerces list elements to strings.
    """
    if value is None:
        return []
    if isinstance(value, str):
        # Could be a comma-separated string ("intro, verse 1") — split on
        # commas to be even more defensive about ChatGPT's output shape.
        parts = [p.strip() for p in value.split(",")]
        return [p for p in parts if p]
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


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
