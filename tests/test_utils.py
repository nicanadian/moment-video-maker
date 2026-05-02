"""Tests for utils.slugify — guards against empty IDs from unicode-only or
punctuation-only titles, which would otherwise produce colliding scene/concept
filenames (review-feedback, QA #high-1).
"""

from solypsizm_moment_studio.utils import slugify


def test_slugify_basic() -> None:
    assert slugify("Wide Approach") == "wide-approach"


def test_slugify_unicode_only_returns_fallback() -> None:
    assert slugify("好") == "untitled"


def test_slugify_punctuation_only_returns_fallback() -> None:
    assert slugify("!!!") == "untitled"


def test_slugify_empty_returns_fallback() -> None:
    assert slugify("") == "untitled"


def test_slugify_max_words_truncates() -> None:
    # Stopword filter drops "the", then max_words=3 keeps the first three remaining.
    assert slugify("the quick brown fox jumps", max_words=3) == "quick-brown-fox"


def test_slugify_drops_stopwords() -> None:
    assert slugify("Abandoned Watchtower at Dawn") == "abandoned-watchtower-dawn"
    assert slugify("Empty Highway with Headlights") == "empty-highway-headlights"


def test_slugify_custom_fallback() -> None:
    assert slugify("***", fallback="scene") == "scene"


def test_slugify_mixed_strips_non_ascii() -> None:
    # Mixed unicode + ASCII keeps the ASCII portion.
    assert slugify("café 1") == "caf-1"
