# Phase D — correctness + prompt fidelity

**Date:** 2026-05-01
**Model:** Claude Opus 4.7

## User
Answered the five open questions:
> 1. no veo audio
> 2. look in the brand kit, i can drop some pngs somewhere too
> 3. uh, probably depends on the song and moment
> 4. wherever
> 5. copy

## Assistant

Locked the answers and shipped D1 (correctness P0) + D2 (prompt fidelity P0) + D4.5 (copy default).

### What landed

**Reference image flow (D2.2)**
- Extracted the canonical front-view PNG embedded in the docx → `character-reference/front.png` (768×1344, ~1.1 MB).
- Added `character.reference_image` + `character.reference_images` dict to `brand-kit.json` and the `CharacterSpec` model. Nic can drop additional poses (back / 3-4-right / walking-side / etc.) into the same folder later and add entries to `reference_images`.
- `start_frame_prompt` now leads with: `>>> BEFORE PASTING: upload the reference image at character-reference/front.png as the seed.` This is the only thing that holds character lock across DALL-E regenerations — text-only prompts drift visor → goggles every time.
- `bootstrap-brand-kit` mirrors the sibling `character-reference/` folder into `~/solypsizm/` so paths resolve relative to the installed kit.

**CRITICAL anti-patterns (D2.3)**
- Visor: `"NOT goggles, NOT sunglasses, NOT a helmet visor, NOT a Cyclops/Geordi-style frame. No upper or lower edge visible."`
- Piping: `"HEXAGONAL — NOT zigzag, NOT racing stripes, NOT diagonals."`
- Echoed in `end_frame_prompt`'s preserve-detail clause.

**Veo prompt (D2.1)**
Reformatted from a flat 7-line to:
```
Subject: ...
Action: ...
Environment: ...
Lighting: ...
Camera: ...
Aspect: vertical 9:16, 1080x1920
Duration: ~6 seconds, continuous take, locked framing, no cuts
Audio: silent video — no music, no dialogue, no foley, no SFX
Style: cinematic anime, 24fps cel-shaded animation, ...

Avoid:
- no slow motion
- no morphing
- no distorted face
- ...
```
Audio direction is the load-bearing fix — Veo 3 generates audio by default and would dub random music over the master. Aspect line ensures we get 9:16 returns, not 16:9. New `BrandKit.veo_prompt` config holds these constants so they're editable without touching Python.

**End-frame prompt (D2.4)**
- Now takes `project` (was just `scene`).
- Injects `bk.aesthetic.lighting_cues` + the song theme's color accent / mood, so the second generation has a palette anchor and doesn't drift from the start frame.

**Audio-offset math fix (D1.1)**
- First clip's `audio_offset = section.start` (not `section.start + 1.5s`). Title card overlays the music; chorus downbeat lands on time.
- Last clip clamps to `section.end`.

**Downbeat-snap algorithm (D1.2)**
- New `_select_cut_points(start, end, n_clips, grid, min_clip)` is two-pass: compute ideal even-distribution targets, then snap each to the nearest grid value within a floor/ceiling window. Distributes slack across all clips rather than dumping it on the last.
- Cuts snap to `song_analysis.downbeat_seconds` (preferred) or `beat_grid_seconds` (fallback). Empty grid falls back to even-duration slicing.
- Verified against a 92 BPM downbeat grid (every 2.6s) on a 24s chorus with 4 clips: cuts at 25.20 / 33.00 / 38.20, durations 5.20 / 7.80 / 5.20 / 5.80. All three cuts are real downbeats; spread is reasonable.

**Import safety (D1.5, D1.6, D4.5)**
- `--copy` is default; `--move` is opt-in. Success line says "Copied" or "Moved".
- `_find_existing_hash` now ignores records whose on-disk file no longer exists — delete-then-reimport works without hand-editing scene JSON.
- After a successful `_stage_and_commit`, if `save_scene` raises, we `target_path.unlink()` to roll back the file landing. Avoids orphan imports.

**Slug fallback (D1.7)**
- `slugify("好")`, `slugify("!!!")`, `slugify("")` → `"untitled"` (configurable via `fallback`). No more empty-slug ID collisions on unicode-only or punctuation-only titles.

**Moment spec field (D3.1, D3.6)**
- Added `Segment.in_point` / `Segment.out_point` (Veo gives ~8s; spec must say which slice).
- Removed hardcoded `image="../shared/end-cards/stream-now.png"` and `captions_source="captions/main.srt"`. Variant Builder can fill from a brand-kit reference later.

### Tests

40/40 green. New cases:
- `test_first_clip_audio_offset_equals_section_start`
- `test_last_clip_ends_at_section_end`
- `test_clips_snap_to_downbeat_grid_when_provided`
- `test_clips_have_in_point_and_out_point`
- `test_slugify_unicode_only_returns_fallback` + 6 other slugify edge cases

### Still open in Phase D

- **D1.3** `save_json_atomic` fsync hardening
- **D1.4** `append_log` lock + crash-safe append
- **D1.8** `cold_hook` strategy (per Nic's "depends on the song and moment", keeping `tension_release` as-is and adding the cold-hook variant alongside)
- **D3** Remaining moment-spec fields: `transition`, lyric-overlay segments, `hook_clip_id`, lufs/fps/res/safe_zones propagation
- **D4** Operator UX: `--project` flag, "Next:" line in status, `pick-scene`, fuzzy IDs, `analyze --force` diff, `doctor --global`, `log --tail`/`--filter`, `open` stdout/stderr split, README cold-start
- **D5** Test gaps: smart quotes / trailing commas in parser, label-tie behavior, large inputs, empty analysis, mutable-default audit
- **D6** Originally-deferred: `--lyrics-aware`, `--api`, `madmom`

### Worth flagging

The downbeat-snap test against synthetic data revealed a real algorithm bug — greedy walk-forward dumps slack onto the last clip. Caught and fixed by switching to two-pass cut selection. That's exactly the kind of issue a real song run will surface; the algorithm is now ready for Haze.
