"""Tolerant parsers for ChatGPT responses to brainstorm and scene-breakdown prompts.

ChatGPT often wraps JSON in code fences or includes a leading sentence ("Here are 5
concepts:"). Both are tolerated. On failure the caller is expected to dump the raw
input to .state/last-import.txt per PRD §17.
"""

from __future__ import annotations

import json
import re
from typing import Any


class ParseError(ValueError):
    pass


_FENCE_RE = re.compile(r"^```(?:json|JSON)?\s*\n(.*?)\n```\s*$", re.DOTALL | re.MULTILINE)


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    if text.startswith("```"):
        # Stripped form: leading fence, possibly no trailing fence.
        first_nl = text.find("\n")
        if first_nl != -1:
            text = text[first_nl + 1 :]
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def _find_balanced(text: str, open_ch: str, close_ch: str) -> str | None:
    """Return the first balanced span starting at the first `open_ch` in `text`.

    Skips characters inside double-quoted strings (with backslash escapes) so braces
    inside string values don't unbalance the count.
    """
    start = text.find(open_ch)
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _parse_json_lenient(text: str) -> Any:
    text = _strip_code_fences(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try the first balanced array.
    arr = _find_balanced(text, "[", "]")
    if arr is not None:
        try:
            return json.loads(arr)
        except json.JSONDecodeError:
            pass
    # Try the first balanced object.
    obj = _find_balanced(text, "{", "}")
    if obj is not None:
        try:
            return json.loads(obj)
        except json.JSONDecodeError:
            pass
    raise ParseError("Could not extract JSON from the response.")


def _coerce_to_list(parsed: Any, list_keys: tuple[str, ...]) -> list[dict]:
    if isinstance(parsed, list):
        items = parsed
    elif isinstance(parsed, dict):
        items = None
        for k in list_keys:
            if k in parsed and isinstance(parsed[k], list):
                items = parsed[k]
                break
        if items is None:
            # Single object — wrap as a one-item list (artist may have asked for 1).
            items = [parsed]
    else:
        raise ParseError(f"Expected a JSON array or object, got {type(parsed).__name__}.")

    out: list[dict] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ParseError(f"Item {i} is not a JSON object.")
        out.append(item)
    if not out:
        raise ParseError("Response had no items.")
    return out


def _require_titled(items: list[dict], kind: str) -> list[dict]:
    """Each item must have a non-empty 'title' field, otherwise it's almost
    certainly garbage that the wrap-as-list code branch swallowed."""
    for i, item in enumerate(items):
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ParseError(
                f"{kind} item {i} is missing a non-empty 'title' field."
            )
    return items


def parse_concepts_response(text: str) -> list[dict]:
    """Parse a ChatGPT brainstorm response into a list of concept dicts."""
    items = _coerce_to_list(_parse_json_lenient(text), ("concepts",))
    return _require_titled(items, "Concept")


def parse_scenes_response(text: str) -> list[dict]:
    """Parse a ChatGPT scene-breakdown response into a list of scene dicts."""
    items = _coerce_to_list(_parse_json_lenient(text), ("scenes",))
    return _require_titled(items, "Scene")
