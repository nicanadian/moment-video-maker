"""Tests for the section-labeling heuristic.

Section detection in librosa is approximate; the labeler turns boundary+energy
tuples into human-readable names. We test the labeling logic in isolation so
section-name regressions surface without needing a real audio file.
"""

from __future__ import annotations

from solypsizm_moment_studio.analysis import label_sections


def test_intro_outro_chosen_when_low_energy_at_ends() -> None:
    raw = [
        (0.0, 8.0, 0.10, 0.18),   # very low — intro
        (8.0, 26.0, 0.35, 0.40),  # low-mid — verse
        (26.0, 33.0, 0.55, 0.65), # mid — pre-chorus
        (33.0, 50.0, 0.78, 0.92), # high — chorus
        (50.0, 60.0, 0.20, 0.28), # very low — outro
    ]
    sections = label_sections(raw)
    names = [s.name for s in sections]
    assert names[0] == "intro"
    assert names[-1] == "outro"
    assert "chorus 1" in names
    assert any(n.startswith("verse") for n in names)


def test_intro_skipped_when_first_section_is_loud() -> None:
    # Synth track that starts with a slam — first section is high energy.
    raw = [
        (0.0, 4.0, 0.80, 0.95),
        (4.0, 20.0, 0.40, 0.50),
        (20.0, 36.0, 0.85, 0.99),
        (36.0, 50.0, 0.10, 0.18),
    ]
    sections = label_sections(raw)
    names = [s.name for s in sections]
    assert names[0] != "intro"  # loud opener doesn't get the "intro" label


def test_pre_chorus_labels_when_mid_energy_precedes_chorus() -> None:
    raw = [
        (0.0, 8.0, 0.10, 0.15),    # intro
        (8.0, 24.0, 0.30, 0.38),   # verse 1 (low)
        (24.0, 32.0, 0.55, 0.68),  # pre-chorus 1 (mid)
        (32.0, 50.0, 0.80, 0.92),  # chorus 1 (high)
        (50.0, 56.0, 0.15, 0.22),  # outro
    ]
    sections = label_sections(raw)
    names = [s.name for s in sections]
    assert "pre-chorus 1" in names


def test_empty_input_returns_empty_list() -> None:
    assert label_sections([]) == []


def test_preserves_start_end_and_energy_values() -> None:
    raw = [
        (0.0, 10.0, 0.2, 0.3),
        (10.0, 30.0, 0.7, 0.85),
        (30.0, 40.0, 0.15, 0.22),
    ]
    sections = label_sections(raw)
    assert [s.start for s in sections] == [0.0, 10.0, 30.0]
    assert [s.end for s in sections] == [10.0, 30.0, 40.0]
    assert sections[1].energy_avg == 0.7
    assert sections[1].energy_peak == 0.85
