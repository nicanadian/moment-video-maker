"""Moment suggestion algorithm (PRD §F7, §15).

The algorithm is heuristic and tunable via EditConfig. Two strategies:

- ``section_focus``: stay within one song section. Pick clips by mood + section
  fit + energy match.
- ``tension_release``: same scoring, but if the section is high-energy and
  ``always_lead_with_hook`` is set, lead with one low-energy clip before the
  high-energy run. Mirrors the 'verse-into-chorus' edit feel.

PRD §15 weights are wired through; an internal section-fit weight (0.6) handles
explicit ``song_section_fit`` matches. Both strategies are deterministic given
the same inputs — no randomness — which makes regression testing easy.
"""

from __future__ import annotations

from solypsizm_moment_studio.models import (
    ClipTake,
    EditConfig,
    Moment,
    Project,
    Scene,
    Section,
    Segment,
    SongAnalysis,
    SourceSongSection,
)
from solypsizm_moment_studio.utils import now_iso, slugify

ENERGY_BUCKETS = ["low", "low-mid", "mid", "mid-high", "high"]

# Maps the section *kind* (first word of name, e.g. "chorus 1" → "chorus") to
# moods we'd expect a fitting scene to carry. Free-form for now; tightens to a
# controlled vocabulary in v2 (PRD §21 q6).
SECTION_MOOD_HINTS: dict[str, set[str]] = {
    "intro": {"isolation", "approach", "anticipation", "stillness", "wandering"},
    "verse": {"isolation", "approach", "wandering", "reflection", "drift"},
    "pre-chorus": {"tension", "rising", "approach", "anticipation"},
    "chorus": {"release", "exhilaration", "anthemic", "high"},
    "bridge": {"shift", "reflection", "drift", "transition"},
    "outro": {"departure", "stillness", "fade", "drift"},
}

INTERNAL_SECTION_FIT_WEIGHT = 0.6


def section_kind(name: str) -> str:
    """'chorus 1' → 'chorus', 'pre-chorus 2' → 'pre-chorus'."""
    if not name:
        return ""
    # Trim trailing numeric tokens.
    parts = name.split()
    while parts and parts[-1].isdigit():
        parts.pop()
    return " ".join(parts)


def energy_bucket(value: float) -> str:
    if value < 0.25:
        return "low"
    if value < 0.45:
        return "low-mid"
    if value < 0.60:
        return "mid"
    if value < 0.80:
        return "mid-high"
    return "high"


def filter_sections(sections: list[Section], min_duration: float) -> list[Section]:
    """Filter out sections too short or too quiet to host a moment (PRD §F7 step 2)."""
    out: list[Section] = []
    for s in sections:
        kind = section_kind(s.name)
        duration = s.end - s.start
        if kind == "outro" and duration < 6:
            continue
        if kind == "intro" and s.energy_avg < 0.05:
            continue
        if duration < min_duration:
            continue
        out.append(s)
    return out


def candidate_clips(
    scenes: list[Scene],
    min_rating: int,
) -> list[tuple[Scene, ClipTake]]:
    """Build the clip pool: one (scene, take) per scene with a rating ≥ min and at
    least one mood tag. Falls back to the highest-rated take when no clip is
    explicitly marked selected (PRD §F5).
    """
    out: list[tuple[Scene, ClipTake]] = []
    for scene in scenes:
        if not scene.clip_takes or not scene.mood_tags:
            continue
        chosen = next((c for c in scene.clip_takes if c.selected), None)
        if chosen is None:
            rated = [c for c in scene.clip_takes if c.rating is not None]
            if not rated:
                continue
            chosen = max(rated, key=lambda c: (c.rating or 0, c.imported_at))
        if (chosen.rating or 0) < min_rating:
            continue
        out.append((scene, chosen))
    return out


def score_clip_for_section(
    scene: Scene,
    clip: ClipTake,
    section: Section,
    cfg: EditConfig,
) -> float:
    """Heuristic fit score. Higher = better."""
    kind = section_kind(section.name)
    expected_moods = SECTION_MOOD_HINTS.get(kind, set())

    scene_moods = {m.lower() for m in scene.mood_tags}
    overlap = len(scene_moods & expected_moods)
    mood_score = min(1.0, overlap / 2.0) if expected_moods else 0.0

    fit_score = 0.0
    for fit in scene.song_section_fit:
        fit_lower = fit.lower()
        if fit_lower == section.name.lower():
            fit_score = 1.0
            break
        if kind and kind in fit_lower:
            fit_score = max(fit_score, 0.7)

    target_bucket = energy_bucket(section.energy_avg)
    energy_score = 0.0
    if scene.energy_target in ENERGY_BUCKETS:
        a = ENERGY_BUCKETS.index(scene.energy_target)
        b = ENERGY_BUCKETS.index(target_bucket)
        energy_score = max(0.0, 1.0 - abs(a - b) * 0.3)

    rating_score = (clip.rating - cfg.min_clip_rating) * 0.05 if clip.rating else 0.0

    return (
        cfg.mood_match_weight * mood_score
        + INTERNAL_SECTION_FIT_WEIGHT * fit_score
        + cfg.energy_match_weight * energy_score
        + rating_score
    )


def pick_section(
    sections: list[Section],
    use_count: dict[str, int],
) -> Section:
    """Round-robin: prefer the least-used section; tie-break by song position."""
    return min(sections, key=lambda s: (use_count.get(s.name, 0), s.start))


def _pick_hook_clip(
    pool: list[tuple[Scene, ClipTake]],
    used_files: dict[str, int],
    cfg: EditConfig,
) -> tuple[Scene, ClipTake] | None:
    """Lowest-energy clip in the pool, used to lead a tension_release moment."""
    available = [
        (scene, clip)
        for scene, clip in pool
        if used_files.get(clip.file, 0) < cfg.max_clip_reuse_count
    ]
    if not available:
        return None
    low = [
        (scene, clip)
        for scene, clip in available
        if scene.energy_target in {"low", "low-mid"}
    ]
    return low[0] if low else None


def pick_clips_for_section(
    pool: list[tuple[Scene, ClipTake]],
    section: Section,
    cfg: EditConfig,
    clip_use_count: dict[str, int],
    strategy: str,
) -> list[tuple[Scene, ClipTake]]:
    """Top-scoring clips for a section, with diversity by scene and reuse cap."""
    duration = section.end - section.start
    target_count = max(
        cfg.min_clips_per_moment,
        min(cfg.max_clips_per_moment, round(duration / 6.0)),
    )

    available = [
        (scene, clip)
        for scene, clip in pool
        if clip_use_count.get(clip.file, 0) < cfg.max_clip_reuse_count
    ]
    if not available:
        return []

    scored = [
        (score_clip_for_section(scene, clip, section, cfg), scene, clip)
        for scene, clip in available
    ]
    # Stable ordering: score desc, then by clip filename for determinism.
    scored.sort(key=lambda x: (-x[0], x[2].file))

    picked: list[tuple[Scene, ClipTake]] = []
    seen_scenes: set[str] = set()

    # tension_release: lead with a low-energy hook on high-energy sections.
    if (
        strategy == "tension_release"
        and cfg.always_lead_with_hook
        and energy_bucket(section.energy_avg) in {"mid-high", "high"}
    ):
        hook = _pick_hook_clip(pool, clip_use_count, cfg)
        if hook is not None:
            picked.append(hook)
            seen_scenes.add(hook[0].id)

    # First pass: prefer one clip per scene.
    for _score, scene, clip in scored:
        if len(picked) >= target_count:
            break
        if scene.id in seen_scenes:
            continue
        if (scene, clip) in picked:
            continue
        picked.append((scene, clip))
        seen_scenes.add(scene.id)

    # Second pass: fill remaining slots even if it means scene repeats.
    if len(picked) < target_count:
        for _score, scene, clip in scored:
            if len(picked) >= target_count:
                break
            if (scene, clip) in picked:
                continue
            picked.append((scene, clip))

    return picked[:target_count]


def _select_cut_points(
    start: float,
    end: float,
    n_clips: int,
    grid: list[float],
    min_clip: float,
) -> list[float]:
    """Pick ``n_clips - 1`` cut points spread evenly across [start, end] and
    snapped to the nearest grid value (downbeat / beat) where possible.

    Two-pass design: compute the *ideal* even-distribution cut targets first,
    then snap each to the closest grid value within a window that respects
    floor (`prev + min_clip`) and ceiling (`end - remaining * min_clip`).

    A single forward-greedy walk used to pile all the slack onto the last
    clip; this distributes it.
    """
    if n_clips <= 1:
        return []
    even = (end - start) / n_clips
    targets = [start + i * even for i in range(1, n_clips)]

    cuts: list[float] = []
    prev = start
    for i, target in enumerate(targets):
        remaining = n_clips - i - 1
        floor = prev + min_clip
        ceiling = end - remaining * min_clip
        if floor > ceiling:
            # Section is too short to honor min_clip everywhere; degrade
            # gracefully to even distribution.
            cuts.append(max(prev + min_clip, target))
            prev = cuts[-1]
            continue
        if grid:
            in_window = [t for t in grid if floor <= t <= ceiling]
            if in_window:
                cut = min(in_window, key=lambda t: abs(t - target))
            else:
                cut = max(floor, min(ceiling, target))
        else:
            cut = max(floor, min(ceiling, target))
        cuts.append(cut)
        prev = cut
    return cuts


def build_moment(
    moment_id: str,
    project: Project,
    section: Section,
    clips: list[tuple[Scene, ClipTake]],
    strategy: str,
    beat_grid: list[float] | None = None,
) -> Moment:
    """Assemble a Variant Builder–compatible Moment spec from a section + clips.

    Cut points snap to the nearest downbeat (or beat) ≥ ``audio_offset + min_clip``
    so the visual edit lines up with the music. The title card *overlays* the
    section start — it does not push audio_offset forward (review-feedback,
    editor #4 + #5; QA #critical-6).
    """
    section_duration = section.end - section.start
    title_card_duration = 1.5
    end_card_duration = 2.5
    min_clip_duration = 4.0
    n = len(clips)

    segments: list[Segment] = []
    segments.append(
        Segment(
            type="title_card",
            duration=title_card_duration,
            title=project.song_title,
            subtitle=project.artist,
            footer=f"Release {project.release_date}" if project.release_date else None,
        )
    )

    grid = beat_grid or []
    cuts = _select_cut_points(section.start, section.end, n, grid, min_clip_duration)
    boundaries = [section.start, *cuts, section.end]

    for i, (scene, clip) in enumerate(clips):
        audio_offset = boundaries[i]
        clip_end = boundaries[i + 1]
        clip_duration = max(min_clip_duration, clip_end - audio_offset)
        source = f"scenes/{scene.concept_id}/{scene.id}-clips/{clip.file}"
        segments.append(
            Segment(
                type="clip",
                source=source,
                audio_offset=round(audio_offset, 3),
                duration=round(clip_duration, 3),
                in_point=0.0,
                out_point=round(clip_duration, 3),
            )
        )

    segments.append(
        Segment(
            type="end_card",
            duration=end_card_duration,
        )
    )

    now = now_iso()
    return Moment(
        id=moment_id,
        song_slug=project.song_slug,
        duration_target_seconds=section_duration,
        source_song_section=SourceSongSection(
            name=section.name, start=section.start, end=section.end
        ),
        edit_strategy=strategy,
        segments=segments,
        status="pending_review",
        created_at=now,
        updated_at=now,
    )


def suggest_moments(
    project: Project,
    song_analysis: SongAnalysis,
    scenes: list[Scene],
    cfg: EditConfig,
    count: int,
    strategy: str = "section_focus",
    start_index: int = 1,
    reserved_ids: set[str] | None = None,
) -> tuple[list[Moment], str | None]:
    """Top-level entry: produce up to ``count`` Moment specs.

    Returns ``(moments, stop_reason)`` so callers can explain why fewer than
    ``count`` were produced. ``stop_reason`` is ``None`` on full success.

    ``start_index`` lets callers continue numbering past existing moments
    (so re-running suggest-moments doesn't overwrite previous output).
    ``reserved_ids`` is the set of moment IDs already on disk; if a generated
    id collides we append ``-2`` / ``-3`` to disambiguate.
    """
    pool = candidate_clips(scenes, cfg.min_clip_rating)
    if not pool:
        return [], "no clips with rating ≥ min and at least one mood tag"

    min_section_duration = max(8.0, cfg.min_clips_per_moment * 4.0)
    sections = filter_sections(song_analysis.sections, min_section_duration)
    if not sections:
        return [], "no song sections long enough to host a moment"

    beat_grid = song_analysis.downbeat_seconds or song_analysis.beat_grid_seconds
    reserved = set(reserved_ids or set())

    moments: list[Moment] = []
    section_use_count: dict[str, int] = {}
    clip_use_count: dict[str, int] = {}
    stop_reason: str | None = None

    for i in range(count):
        section = pick_section(sections, section_use_count)
        section_use_count[section.name] = section_use_count.get(section.name, 0) + 1

        clips = pick_clips_for_section(pool, section, cfg, clip_use_count, strategy)
        if len(clips) < cfg.min_clips_per_moment:
            stop_reason = (
                f"clip pool exhausted at {len(moments)} moment(s) — "
                f"each clip can be used at most {cfg.max_clip_reuse_count} times "
                f"and {cfg.min_clips_per_moment} are needed per moment"
            )
            break
        for _scene, clip in clips:
            clip_use_count[clip.file] = clip_use_count.get(clip.file, 0) + 1

        section_slug = slugify(section.name) or "section"
        seq = start_index + i
        base_id = f"moment-{seq:02d}-{section_slug}"
        candidate = base_id
        suffix = 1
        while candidate in reserved:
            suffix += 1
            candidate = f"{base_id}-{suffix}"
        reserved.add(candidate)

        moment = build_moment(candidate, project, section, clips, strategy, beat_grid=beat_grid)
        moments.append(moment)

    return moments, stop_reason
