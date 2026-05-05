"""Tests for coerce_str_list and parser shape checks (review-feedback fixes:
silent char-iteration of ChatGPT-string-as-list, and wrong-shape JSON
falsely succeeding as a one-item concept).
"""

import pytest

from solypsizm_moment_studio.prompts.parsing import (
    ParseError,
    parse_concepts_response,
    parse_scenes_response,
)
from solypsizm_moment_studio.utils import coerce_str_list

# ---------------------------------------------------------------------------
# coerce_str_list — fixes the "intro" → ["i","n","t","r","o"] bug
# ---------------------------------------------------------------------------


def test_coerce_str_list_passes_lists_through() -> None:
    assert coerce_str_list(["a", "b"]) == ["a", "b"]


def test_coerce_str_list_wraps_string_as_single_item() -> None:
    """The bug: list("intro") char-iterated. Now we wrap it."""
    assert coerce_str_list("intro") == ["intro"]


def test_coerce_str_list_splits_comma_separated_string() -> None:
    """ChatGPT often returns a comma-separated string instead of a list."""
    assert coerce_str_list("intro, verse 1, chorus") == ["intro", "verse 1", "chorus"]


def test_coerce_str_list_handles_none_and_empty() -> None:
    assert coerce_str_list(None) == []
    assert coerce_str_list([]) == []
    assert coerce_str_list("") == []


def test_coerce_str_list_stringifies_non_string_items() -> None:
    assert coerce_str_list([1, 2.5, "three"]) == ["1", "2.5", "three"]


# ---------------------------------------------------------------------------
# parser shape checks — fixes the "{'data': '...'}" silently succeeds bug
# ---------------------------------------------------------------------------


def test_parse_concepts_rejects_object_without_title() -> None:
    """Wrong-shape JSON (missing 'title') used to succeed as a one-item list,
    fabricating concept-01-untitled. Now it raises ParseError.
    """
    with pytest.raises(ParseError):
        parse_concepts_response('{"data": "not concepts"}')


def test_parse_concepts_rejects_array_with_missing_titles() -> None:
    with pytest.raises(ParseError):
        parse_concepts_response('[{"summary": "..."}]')


def test_parse_concepts_rejects_empty_title() -> None:
    with pytest.raises(ParseError):
        parse_concepts_response('[{"title": "   ", "summary": "x"}]')


def test_parse_scenes_requires_titles() -> None:
    with pytest.raises(ParseError):
        parse_scenes_response('[{"description": "no title here"}]')
