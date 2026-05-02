"""Parser tests. The parser is the most fragile part of the manual ChatGPT loop —
it has to swallow the formatting variations the web app likes to introduce.
"""

from __future__ import annotations

import pytest

from solypsizm_moment_studio.prompts.parsing import (
    ParseError,
    parse_concepts_response,
    parse_scenes_response,
)

# ---------------------------------------------------------------------------
# parse_concepts_response
# ---------------------------------------------------------------------------


def test_plain_array() -> None:
    text = """
[
  {"title": "A", "summary": "first"},
  {"title": "B", "summary": "second"}
]
"""
    items = parse_concepts_response(text)
    assert [c["title"] for c in items] == ["A", "B"]


def test_array_in_json_code_fence() -> None:
    text = """```json
[
  {"title": "A", "summary": "first"}
]
```"""
    items = parse_concepts_response(text)
    assert items[0]["title"] == "A"


def test_array_in_unlabeled_code_fence() -> None:
    text = """```
[{"title": "A", "summary": "first"}]
```"""
    items = parse_concepts_response(text)
    assert items[0]["title"] == "A"


def test_leading_prose_then_array() -> None:
    text = (
        "Here are five concept ideas based on the lyrics:\n\n"
        '[{"title": "A", "summary": "first"}, {"title": "B", "summary": "second"}]\n\n'
        "Hope that works!"
    )
    items = parse_concepts_response(text)
    assert len(items) == 2


def test_concepts_wrapped_in_object() -> None:
    text = '{"concepts": [{"title": "A", "summary": "first"}]}'
    items = parse_concepts_response(text)
    assert items[0]["title"] == "A"


def test_braces_inside_string_dont_unbalance() -> None:
    text = (
        '[{"title": "A", "summary": "uses {curly} braces in summary"},'
        ' {"title": "B", "summary": "second"}]'
    )
    items = parse_concepts_response(text)
    assert len(items) == 2
    assert "{curly}" in items[0]["summary"]


def test_single_object_wraps_to_list() -> None:
    text = '{"title": "Solo", "summary": "only one"}'
    items = parse_concepts_response(text)
    assert len(items) == 1
    assert items[0]["title"] == "Solo"


def test_garbage_raises_parse_error() -> None:
    with pytest.raises(ParseError):
        parse_concepts_response("This is just prose, no JSON at all.")


def test_empty_array_raises_parse_error() -> None:
    with pytest.raises(ParseError):
        parse_concepts_response("[]")


# ---------------------------------------------------------------------------
# parse_scenes_response
# ---------------------------------------------------------------------------


def test_scenes_array() -> None:
    text = """[
      {"title": "wide approach", "description": "...", "shot_type": "wide"},
      {"title": "tower base",    "description": "...", "shot_type": "low angle"}
    ]"""
    items = parse_scenes_response(text)
    assert len(items) == 2
    assert items[0]["shot_type"] == "wide"


def test_scenes_wrapped_under_scenes_key() -> None:
    text = '{"scenes": [{"title": "a"}, {"title": "b"}, {"title": "c"}]}'
    items = parse_scenes_response(text)
    assert len(items) == 3


# ---------------------------------------------------------------------------
# Robustness — formatting variations ChatGPT introduces
# ---------------------------------------------------------------------------


def test_smart_quotes_inside_string_values_parse_fine() -> None:
    """Curly quotes are just unicode characters inside JSON string literals;
    the JSON parser should handle them. No special unescape needed.
    """
    text = '[{"title": "She said “hi”", "summary": "x"}]'
    items = parse_concepts_response(text)
    assert items[0]["title"] == "She said “hi”"


def test_trailing_commas_rejected_with_parse_error() -> None:
    """ChatGPT sometimes emits trailing commas; standard JSON rejects.
    We surface that as a clean ParseError so the artist can fix and retry,
    rather than crashing with a low-level JSONDecodeError trace.
    """
    with pytest.raises(ParseError):
        parse_concepts_response('[{"title": "A", "summary": "x",}]')


def test_bom_at_start_is_stripped() -> None:
    text = "﻿" + '[{"title": "A", "summary": "x"}]'
    items = parse_concepts_response(text)
    assert items[0]["title"] == "A"


def test_large_input_does_not_blow_up() -> None:
    """A 1k-item array (~50KB) parses in well under a second."""
    items_in = ", ".join(f'{{"title": "C{i}"}}' for i in range(1000))
    text = "[" + items_in + "]"
    out = parse_concepts_response(text)
    assert len(out) == 1000


def test_doubled_fences_uses_first_block() -> None:
    """ChatGPT occasionally wraps the response twice. Take the first block."""
    text = """```json
[{"title": "A"}]
```

```
extra prose
```"""
    items = parse_concepts_response(text)
    assert items[0]["title"] == "A"
