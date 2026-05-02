"""Tests for the moment-suggestion algorithm.

The algorithm is heuristic but deterministic — same inputs, same outputs.
We assert the structural guarantees the PRD demands (clip pool filtering,
diversity, reuse cap, segment composition) rather than scoring exact values,
so future weight-tuning doesn't churn the test suite.
"""

from __future__ import annotations

from solypsizm_moment_studio.models import (
    ClipTake,
    EditConfig,
    Project,
    Scene,
    Section,
    SongAnalysis,
)
from solypsizm_moment_studio.suggest import (
    candidate_clips,
    energy_bucket,
    filter_sections,
    pick_clips_for_section,
    score_clip_for_section,
    section_kind,
    suggest_moments,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _project() -> Project:
    return Project(
        song_title="Haze over the Horizon",
        song_slug="haze",
        artist="Solypsizm",
        release_date="2026-01-09",
        created_at="2026-05-01T00:00:00+00:00",
        updated_at="2026-05-01T00:00:00+00:00",
    )


def _scene(
    sid: str,
    *,
    moods: list[str],
    energy: str = "low-mid",
    section_fit: list[str] | None = None,
    rating: int = 4,
    selected: bool = True,
    clip_file: str | None = None,
) -> Scene:
    return Scene(
        id=sid,
        concept_id="concept-01-watchtower",
        title=sid,
        description="",
        duration_target_seconds=6,
        shot_type="wide",
        camera_motion="dolly",
        subject_motion="walks",
        environment="foggy field",
        lighting="horizon backlight",
        mood_tags=moods,
        song_section_fit=section_fit or [],
        energy_target=energy,
        clip_takes=[
            ClipTake(
                file=clip_file or f"{sid}-take.mp4",
                imported_at="2026-05-01T00:00:00+00:00",
                rating=rating,
                notes="",
                selected=selected,
            )
        ],
        created_at="2026-05-01T00:00:00+00:00",
        updated_at="2026-05-01T00:00:00+00:00",
    )


def _song() -> SongAnalysis:
    return SongAnalysis(
        audio_file="audio/master.wav",
        duration_seconds=120.0,
        tempo_bpm=92.0,
        sections=[
            Section(name="intro", start=0.0, end=8.0, energy_avg=0.10),
            Section(name="verse 1", start=8.0, end=26.0, energy_avg=0.30),
            Section(name="pre-chorus 1", start=26.0, end=33.0, energy_avg=0.55),
            Section(name="chorus 1", start=33.0, end=55.0, energy_avg=0.78),
            Section(name="verse 2", start=55.0, end=80.0, energy_avg=0.32),
            Section(name="chorus 2", start=80.0, end=110.0, energy_avg=0.82),
            Section(name="outro", start=110.0, end=120.0, energy_avg=0.15),
        ],
    )


# ---------------------------------------------------------------------------
# unit tests for the helpers
# ---------------------------------------------------------------------------


def test_section_kind_strips_trailing_number() -> None:
    assert section_kind("chorus 1") == "chorus"
    assert section_kind("pre-chorus 2") == "pre-chorus"
    assert section_kind("intro") == "intro"
    assert section_kind("") == ""


def test_energy_buckets_cover_known_thresholds() -> None:
    assert energy_bucket(0.10) == "low"
    assert energy_bucket(0.35) == "low-mid"
    assert energy_bucket(0.55) == "mid"
    assert energy_bucket(0.78) == "mid-high"
    assert energy_bucket(0.95) == "high"


def test_filter_sections_drops_short_outro_and_silent_intro() -> None:
    sections = [
        Section(name="intro", start=0.0, end=4.0, energy_avg=0.0),  # too quiet
        Section(name="verse 1", start=4.0, end=24.0, energy_avg=0.4),
        Section(name="chorus 1", start=24.0, end=44.0, energy_avg=0.8),
        Section(name="outro", start=44.0, end=46.0, energy_avg=0.2),  # too short
    ]
    out = filter_sections(sections, min_duration=12.0)
    names = [s.name for s in out]
    assert "intro" not in names
    assert "outro" not in names
    assert "verse 1" in names and "chorus 1" in names


def test_candidate_clips_requires_rating_and_mood_tag() -> None:
    scenes = [
        _scene("s1", moods=["isolation"], rating=4),
        _scene("s2", moods=[], rating=5),  # no mood tag → excluded
        _scene("s3", moods=["release"], rating=2),  # too low rating → excluded
        _scene("s4", moods=["approach"], rating=5),
    ]
    pool = candidate_clips(scenes, min_rating=3)
    ids = [scene.id for scene, _ in pool]
    assert "s1" in ids and "s4" in ids
    assert "s2" not in ids and "s3" not in ids


def test_candidate_clips_falls_back_to_highest_rated_when_none_selected() -> None:
    scene = Scene(
        id="s1",
        concept_id="c1",
        title="s1",
        mood_tags=["isolation"],
        clip_takes=[
            ClipTake(file="t1.mp4", imported_at="x", rating=3, selected=False),
            ClipTake(file="t2.mp4", imported_at="x", rating=5, selected=False),  # highest
            ClipTake(file="t3.mp4", imported_at="x", rating=4, selected=False),
        ],
        created_at="x",
        updated_at="x",
    )
    pool = candidate_clips([scene], min_rating=3)
    assert len(pool) == 1
    assert pool[0][1].file == "t2.mp4"


def test_score_rewards_section_fit_match() -> None:
    section = Section(name="chorus 1", start=0, end=10, energy_avg=0.78)
    cfg = EditConfig()
    matched = _scene("s1", moods=["release"], energy="high", section_fit=["chorus 1"])
    unmatched = _scene("s2", moods=["release"], energy="high", section_fit=[])
    s_matched = score_clip_for_section(matched, matched.clip_takes[0], section, cfg)
    s_unmatched = score_clip_for_section(unmatched, unmatched.clip_takes[0], section, cfg)
    assert s_matched > s_unmatched


def test_score_rewards_energy_match() -> None:
    section = Section(name="chorus 1", start=0, end=10, energy_avg=0.78)  # high
    cfg = EditConfig()
    high_scene = _scene("s1", moods=["release"], energy="high")
    low_scene = _scene("s2", moods=["release"], energy="low")
    assert score_clip_for_section(high_scene, high_scene.clip_takes[0], section, cfg) > \
           score_clip_for_section(low_scene, low_scene.clip_takes[0], section, cfg)


# ---------------------------------------------------------------------------
# integration: suggest_moments
# ---------------------------------------------------------------------------


def _diverse_scene_pool() -> list[Scene]:
    """A pool of 10 scenes spanning low/mid/high energy and varied moods, all rated ≥ 4."""
    scenes = [
        _scene("scene-01-tower", moods=["isolation", "approach"], energy="low",
               section_fit=["verse 1"], clip_file="t1.mp4"),
        _scene("scene-02-walk", moods=["wandering"], energy="low-mid",
               section_fit=["verse 1"], clip_file="t2.mp4"),
        _scene("scene-03-rise", moods=["tension", "rising"], energy="mid",
               section_fit=["pre-chorus 1"], clip_file="t3.mp4"),
        _scene("scene-04-summit", moods=["release", "anthemic"], energy="high",
               section_fit=["chorus 1"], clip_file="t4.mp4"),
        _scene("scene-05-leap", moods=["exhilaration"], energy="high",
               section_fit=["chorus 1"], clip_file="t5.mp4"),
        _scene("scene-06-mirror", moods=["reflection"], energy="low-mid",
               section_fit=["verse 2"], clip_file="t6.mp4"),
        _scene("scene-07-fall", moods=["drift"], energy="low",
               section_fit=["bridge"], clip_file="t7.mp4"),
        _scene("scene-08-flames", moods=["release"], energy="mid-high",
               section_fit=["chorus 2"], clip_file="t8.mp4"),
        _scene("scene-09-sky", moods=["anthemic", "release"], energy="high",
               section_fit=["chorus 2"], clip_file="t9.mp4"),
        _scene("scene-10-fade", moods=["departure", "stillness"], energy="low",
               section_fit=["outro"], clip_file="t10.mp4"),
    ]
    return scenes


def test_suggest_moments_produces_requested_count_when_pool_is_rich() -> None:
    moments = suggest_moments(
        project=_project(),
        song_analysis=_song(),
        scenes=_diverse_scene_pool(),
        cfg=EditConfig(),
        count=4,
        strategy="section_focus",
    )
    assert len(moments) == 4
    # All have title + clips + end card.
    for m in moments:
        types = [s.type for s in m.segments]
        assert types[0] == "title_card"
        assert types[-1] == "end_card"
        assert types.count("clip") >= 3


def test_suggest_moments_rotates_song_sections() -> None:
    moments = suggest_moments(
        project=_project(),
        song_analysis=_song(),
        scenes=_diverse_scene_pool(),
        cfg=EditConfig(),
        count=4,
        strategy="section_focus",
    )
    section_names = [m.source_song_section.name for m in moments]
    # No section should be picked twice before every other eligible section is used once.
    seen: set[str] = set()
    for name in section_names:
        seen.add(name)
    assert len(seen) >= 4  # 4 distinct sections in the first 4 moments


def test_suggest_moments_respects_max_clip_reuse() -> None:
    cfg = EditConfig(max_clip_reuse_count=2)
    moments = suggest_moments(
        project=_project(),
        song_analysis=_song(),
        scenes=_diverse_scene_pool(),
        cfg=cfg,
        count=6,
        strategy="section_focus",
    )
    counts: dict[str, int] = {}
    for m in moments:
        for seg in m.segments:
            if seg.type == "clip" and seg.source:
                counts[seg.source] = counts.get(seg.source, 0) + 1
    assert all(n <= cfg.max_clip_reuse_count for n in counts.values()), counts


def test_suggest_moments_returns_empty_when_pool_too_small() -> None:
    # Only 1 candidate clip; min_clips_per_moment=3 → can't build any moment.
    scenes = [_scene("s1", moods=["release"], energy="high")]
    moments = suggest_moments(
        project=_project(),
        song_analysis=_song(),
        scenes=scenes,
        cfg=EditConfig(),
        count=4,
        strategy="section_focus",
    )
    assert moments == []


def test_pick_clips_diversifies_across_scenes_first() -> None:
    """When picking clips for a section, prefer different scenes before reusing one."""
    cfg = EditConfig(min_clips_per_moment=3, max_clips_per_moment=4)
    pool = [(s, s.clip_takes[0]) for s in _diverse_scene_pool()]
    section = Section(name="chorus 1", start=33.0, end=55.0, energy_avg=0.78)
    picks = pick_clips_for_section(pool, section, cfg, {}, "section_focus")
    scene_ids = [scene.id for scene, _ in picks]
    assert len(set(scene_ids)) == len(scene_ids), f"got duplicates in {scene_ids}"


def test_first_clip_audio_offset_equals_section_start() -> None:
    """The title card overlays the music; the first clip starts exactly at section.start
    (no +1.5s shift). This was the load-bearing audio-alignment bug.
    """
    moments = suggest_moments(
        project=_project(),
        song_analysis=_song(),
        scenes=_diverse_scene_pool(),
        cfg=EditConfig(),
        count=1,
        strategy="section_focus",
    )
    assert moments
    first_clip = next(seg for seg in moments[0].segments if seg.type == "clip")
    section = moments[0].source_song_section
    assert first_clip.audio_offset == section.start, (
        f"first clip starts at {first_clip.audio_offset}, expected {section.start}"
    )


def test_last_clip_ends_at_section_end() -> None:
    """Sum of clip durations covers exactly the section duration — never overruns."""
    moments = suggest_moments(
        project=_project(),
        song_analysis=_song(),
        scenes=_diverse_scene_pool(),
        cfg=EditConfig(),
        count=1,
        strategy="section_focus",
    )
    m = moments[0]
    section = m.source_song_section
    clips = [s for s in m.segments if s.type == "clip"]
    last = clips[-1]
    end_time = (last.audio_offset or 0) + (last.duration or 0)
    assert abs(end_time - section.end) < 0.01, (
        f"last clip ends at {end_time}, expected {section.end}"
    )


def test_clips_snap_to_downbeat_grid_when_provided() -> None:
    """When the analysis has downbeats, cuts should land on them."""
    song = SongAnalysis(
        audio_file="audio/master.wav",
        duration_seconds=120.0,
        tempo_bpm=92.0,
        sections=[Section(name="chorus 1", start=20.0, end=40.0, energy_avg=0.78)],
        beat_grid_seconds=[],
        # 4 downbeats inside the section: 24.0 / 28.5 / 33.0 / 37.5
        downbeat_seconds=[20.0, 24.0, 28.5, 33.0, 37.5, 40.0],
    )
    moments = suggest_moments(
        project=_project(),
        song_analysis=song,
        scenes=_diverse_scene_pool(),
        cfg=EditConfig(min_clips_per_moment=3, max_clips_per_moment=3),
        count=1,
        strategy="section_focus",
    )
    m = moments[0]
    clips = [s for s in m.segments if s.type == "clip"]
    # First two clip ends should be downbeats (the third clamps to section.end).
    cut_times = [(c.audio_offset or 0) + (c.duration or 0) for c in clips[:-1]]
    for cut in cut_times:
        assert any(abs(cut - db) < 0.01 for db in song.downbeat_seconds), (
            f"cut at {cut} doesn't snap to any downbeat in {song.downbeat_seconds}"
        )


def test_clips_have_in_point_and_out_point() -> None:
    moments = suggest_moments(
        project=_project(),
        song_analysis=_song(),
        scenes=_diverse_scene_pool(),
        cfg=EditConfig(),
        count=1,
        strategy="section_focus",
    )
    for seg in moments[0].segments:
        if seg.type == "clip":
            assert seg.in_point == 0.0
            assert seg.out_point is not None and seg.out_point > 0


def test_tension_release_leads_with_low_energy_clip_on_chorus() -> None:
    cfg = EditConfig()
    pool = [(s, s.clip_takes[0]) for s in _diverse_scene_pool()]
    section = Section(name="chorus 1", start=33.0, end=55.0, energy_avg=0.78)
    picks = pick_clips_for_section(pool, section, cfg, {}, "tension_release")
    first_scene = picks[0][0]
    assert first_scene.energy_target in {"low", "low-mid"}, (
        f"expected hook clip at start for tension_release, got {first_scene.energy_target}"
    )
