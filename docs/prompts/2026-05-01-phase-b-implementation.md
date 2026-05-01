# Phase B implementation

**Date:** 2026-05-01
**Model:** Claude Opus 4.7

## User
> sure [start Phase B implementation]

## Assistant
Built Phase B: asset library (frame/clip imports + selection), librosa-based song analysis, and project diagnostics. All commands wired into `cli.py`; smoke-tested end-to-end against a synthesized 60s audio file.

### What landed

**Models** (additive):
- `models/song_analysis.py` — `Section` and `SongAnalysis` matching PRD §8.4.
- `models/scene.py` — added `hash: str = ""` to `Frame` and `ClipTake` for SHA-256-based idempotency tracking.

**State**:
- `state/io.py` — added `file_hash()`, `load_song_analysis()`, `save_song_analysis()`, `song_analysis_path()`. Re-exported through `state/__init__.py`.

**Analysis pipeline** (`src/solypsizm_moment_studio/analysis.py`):
- `analyze_audio(path, rel)` — librosa `load` → `beat_track` for tempo + beat grid → every-4th-beat heuristic for downbeats → `agglomerative` clustering on chroma+MFCC features for section boundaries → per-section RMS energy → labeler.
- `label_sections(raw)` — pure function over `(start, end, energy_avg, energy_peak)` tuples. Three-bucket heuristic: bottom third → verse, top third → chorus, middle → pre-chorus (if between verse-like and chorus) or bridge. First/last get intro/outro only when *strictly* below the median energy, so loud openers don't get mislabeled. Falls back to top/bottom split when fewer than 3 middle sections.
- librosa import is lazy inside `analyze_audio` so the rest of the CLI stays snappy.

**Commands** (`src/solypsizm_moment_studio/commands/`):
- `media.py` — `import-frame` validates extension (.png/.jpg/.jpeg/.webp), hashes the source, refuses if the same hash exists anywhere in the project, moves into `<scene-id>-frames/` with auto-numbered names. `select-frame` flips a single frame's `selected=True` and clears the others. Same pattern for `import-clip` (.mp4/.mov/.webm), `select-clip`. `review-clips` prints a ratings table and `open`s the clips folder in Finder.
- `audio.py` — `analyze` refuses overwrite without `--force` (preserves manual edits per PRD §14.3), lazy-imports librosa with a clear error if the `[audio]` extra isn't installed. `sections` prints a table from `song-analysis.json`.
- `diagnostic.py` — `doctor` walks the project: validates project.json, checks lyrics/audio/brand kit files exist, validates concept ↔ scene back-references, checks that referenced frame/clip files actually exist on disk. Reports issues as bullets and exits non-zero. `log` pretty-prints `.state/log.jsonl` with `ts  event  k=v...` rows.

**CLI**: removed Phase B stubs from `cli.py`, replaced with delegations to the new command modules. Phase C commands (`suggest-moments`, `review-moment`, `render-*`, `trace`) still stubbed.

### Test suite

Added `tests/test_section_labeling.py` (5 tests) covering: intro/outro labels chosen only when first/last energies are below median, loud opener doesn't get "intro", pre-chorus inserted when mid-energy sits between verse-like and chorus, empty input returns empty list, start/end/energy values preserved verbatim. **16 tests total, all green.**

The first iteration of the labeler had two bugs caught by tests:
- Median comparison was `<=` instead of `<`, so a loud opener whose energy equaled the median got labeled "intro".
- Top/bottom half-split with no third bucket meant 5-section songs always assigned mid-energy as "pre-chorus" with no "verse" surviving.

Both fixed in the same edit; tests went from 14/16 to 16/16.

### End-to-end smoke test

Synthesized a 60s WAV (sine waves at 4 amplitudes — quiet 8s / mid 18s / loud 8s / louder 18s / quiet 8s) and ran the full Phase B flow:

```
analyze              → 4 sections detected (intro/verse 1/chorus 1/outro), 117 BPM
sections             → table renders cleanly
doctor               → no issues
import-frame x3      → start-v1.png, start-v2.png, end-v1.png
select-frame start   → start-v2.png marked selected
import-clip x2       → take-01.mp4 ★3, take-02.mp4 ★4
review-clips         → ratings table + opened Finder
select-clip          → take-02.mp4 selected, scene status → complete
import-frame (dupe)  → refused with "already imported at scene-01-wide-approach/start/start-v1.png"
log                  → all 11 ops printed with timestamps
status               → "1 with clips, 1 complete"
doctor               → no issues
```

The labeler called the merged pre-chorus+chorus segment "chorus 1" instead of splitting them, because the synthesized signal had identical frequencies in both — librosa's chroma features can't distinguish them. Real music with chord changes will segment differently. PRD §14.3 expects hand-correction anyway.

### Deliberately deferred

- `analyze --lyrics-aware` (PRD §F6) — Phase D.
- madmom-based downbeat detection — current heuristic is "every 4th beat from the beat grid". Good enough for v1; revisit if the suggestion algorithm wants real downbeats.
- `.state/hashes.json` as a separate index — currently we walk all scenes to dedup, which is O(scenes × frames+clips). Fine for a few hundred files; switch to an index if it gets slow.
- Phase C (`suggest-moments`, `review-moment`, `render-*`, `trace`).
