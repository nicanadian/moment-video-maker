# Phase C implementation

**Date:** 2026-05-01
**Model:** Claude Opus 4.7

## User
> cool, go ahead start building phase C

## Assistant
Built Phase C: moment suggestion + review + render handoff + trace + coverage view in status. Algorithm is deterministic and unit-tested independently from the click commands.

### What landed

**Models** (additive):
- `models/moment.py` — `Moment`, `Segment` (title_card / clip / end_card), `SourceSongSection`, matches PRD §8.5.
- `models/edit_config.py` — `EditConfig` with PRD §15 fields and defaults.

**State**:
- `state/paths.py` — `edit_config_path()` → `~/solypsizm/edit-config.json`.
- `state/io.py` — `load_moment`, `save_moment`, `list_moments`, `load_edit_config` (returns defaults when absent).

**Algorithm** (`src/solypsizm_moment_studio/suggest.py`) — pure, testable:
- `candidate_clips(scenes, min_rating)` — clip pool: per scene, the selected take or the highest-rated, must have a mood tag and rating ≥ min.
- `filter_sections(sections, min_duration)` — drops short outros (<6s), pure-silence intros (<0.05 energy), and sections too short to host `min_clips × 4s`.
- `score_clip_for_section(scene, clip, section, cfg)` — heuristic combining mood overlap, explicit `song_section_fit` match, energy-bucket proximity, and a small rating-above-floor bonus. Weights are PRD §15 (`mood_match_weight`, `energy_match_weight`); section-fit weight is internal at 0.6.
- `pick_section(sections, use_count)` — round-robin, lowest use count + earliest start as tie-breaker.
- `pick_clips_for_section(...)` — top-scored clips with diversity-by-scene first pass, then fill-up if short. Respects `max_clip_reuse_count` and a stable secondary sort on filename so the output is deterministic.
- `tension_release` strategy: when targeting a high-energy section (mid-high or high) with `always_lead_with_hook=True`, picks one low-energy clip first as the hook before the high-energy run.
- `build_moment(...)` — assembles `[title_card, clip×N, end_card]`. Clip `audio_offset` starts at `section.start + 1.5s` (after the title card) and advances by each clip's duration.

**Commands** (`src/solypsizm_moment_studio/commands/moments.py`):
- `suggest-moments` loads project + analysis + scenes + edit config, runs the algorithm, persists `moment-NN-<section-slug>.json` files, prints a summary table.
- `review-moment <id>` prints the full spec (TITLE / CLIP entries with audio offsets / END), tries `ffplay -ss <start> -t <dur>` to play the audio range, prompts for approve / reject / skip. `--approve` / `--reject` flags bypass the prompt for scripts/tests.
- `render-moment <id>` and `render-all` are the Variant Builder handoff. Variant Builder doesn't exist yet, so both raise a clear error pointing at the ready spec path. When that tool ships, this is a 5-line wire-up.
- `trace <clip>` walks every moment's clip segments and prints which moments reference a given filename or path fragment.

**Status dashboard** (`commands/project.py`): augmented with moment counts by status (`approved` / `pending_review` / `rejected` / `rendered`) and a per-section coverage block listing each section's moment count with `GAPS: <list>` for sections that have zero — directly answering PRD §F9 ("which song sections still need coverage").

### Tests

`tests/test_suggest.py` adds 13 cases covering: section_kind tokenizing, energy bucket boundaries, filter_sections drops short/silent edges, candidate_clips requires both rating + mood tag, fallback to highest-rated when nothing's selected, score rewards section_fit and energy match, integration: requested count produced from a rich pool, sections rotate, max_clip_reuse_count is respected, empty pool returns empty, scene diversity in the first pass, tension_release leads with a low-energy clip on choruses. **Test suite: 29/29 green.**

### End-to-end smoke

Synthesized a 90s WAV with 5 amplitude-stepped tones, hand-rolled 9 scenes (varied mood / energy / section_fit, all rated 4) inside the project. Then:

```
analyze            → 4 sections detected (intro, verse 1 (8s), chorus 1, outro)
suggest-moments    → 4 moments rotated across 3 eligible sections (verse 1 was filtered as <12s)
review-moment      → spec printed with audio offsets, --approve flips status
review-moment      → --reject also works
trace              → "scene-04-summit-take-01.mp4 appears in 1 moment(s): moment-02-chorus-1"
render-moment      → "Variant Builder integration not wired yet. The moment spec is ready at ..."
render-all         → "1 approved moment(s) waiting on Variant Builder"
status             → "Moments: 4 of target 9 (1 approved, 2 pending_review, 1 rejected)"
                  → coverage block + "GAPS: verse 1"
```

The verse-1-as-gap behavior is correct: librosa segmented it short, the filter caught it, and round-robin reused intro to fill the 4th moment slot. PRD §14.3 expects hand-correction of `song-analysis.json` for cases like this — the surfaced gap tells the artist exactly where to look.

### Deliberately deferred to Phase D

- `--api` mode for OpenAI (PRD §12.2).
- `analyze --lyrics-aware`.
- madmom downbeat detection.
- Variant Builder integration (separate tool).
- Performance pass against PRD §16.3 targets.

After D the v1 success criteria from PRD §18 should be reachable.
