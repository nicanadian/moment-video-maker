# Moment Studio v1

**Status:** in-progress (Phases A + B + C landed, D pending; render handoff blocked on Variant Builder)
**Owner:** Nic
**Started:** 2026-05-01
**Shipped:** —
**Source PRD:** `ref-docs/Solypsizm Moment Studio - PRD.md`

## Progress log

- **2026-05-01** — Phase A landed end-to-end: `bootstrap-brand-kit`, `new`, `status`, `open`, `brainstorm`, `import-concepts`, `list-concepts`, `pick-concept`, `rate-concept`, `scenes`, `import-scenes`, `list-scenes`, `prompts <scene-id>`. Pydantic models for Project / Concept / Scene / BrandKit. Atomic JSON writes + `.state/log.jsonl` operation log. Tolerant ChatGPT response parser (11 unit tests passing). Manual end-to-end smoke test green: brand-kit install → new project → concept brainstorm → scene breakdown → scene-NN-prompts.md emitted with full character spec auto-injected.
- **2026-05-01** — Phase C landed end-to-end: `suggest-moments` (heuristic algorithm in `suggest.py`, deterministic given inputs, two strategies — `section_focus` and `tension_release`), `review-moment` (prints spec, plays the audio range via `ffplay` if available, prompts for approve/reject; `--approve`/`--reject` flags for non-interactive use), `trace <clip>` (reverse lookup), `render-moment` and `render-all` (clear "Variant Builder integration not wired yet" error pointing at the ready spec). Coverage view in `status` lists every section with a moment count and prints `GAPS: <list>` for sections with zero. Adds Moment / Segment / SourceSongSection / EditConfig pydantic models, `~/solypsizm/edit-config.json` loading with PRD §15 defaults, and 13 unit tests for the algorithm (filtering, scoring, diversity, reuse cap, tension-release hook). Test suite is now 29/29 green. End-to-end smoke against synthesized 90s audio + 9 hand-rolled scenes: 4 moments produced, round-robin across sections, hook clip lands first under tension_release on high-energy targets, trace/coverage/status all line up.
- **2026-05-01** — Phase B landed end-to-end: `import-frame`, `select-frame`, `import-clip`, `select-clip`, `review-clips`, `analyze`, `sections`, `doctor`, `log`. Frame/clip imports move (not copy), auto-rename to `start-vN.png`/`take-NN.mp4`, hash for SHA-256-based duplicate detection across the project. `analyze` runs a librosa pipeline (load → beat track → agglomerative segmentation on chroma+MFCC → per-section RMS energy → 3-bucket label heuristic), refuses to overwrite without `--force`, lazy-imports librosa so non-audio commands don't pay its cost. `doctor` validates project schema, file references, and brand kit resolution. 5 new unit tests for the labeler bring the suite to 16 green. End-to-end smoke against synthesized 60s audio: 4 sections detected (intro/verse/chorus/outro), tempo 117 BPM; frame and clip imports work with duplicate detection; `select-clip` flips scene status to `complete`. Phase C (`suggest-moments`, `review-moment`, `render-*`, `trace`) still stubbed.

## Goal

Build a Python CLI (`solypsizm`) that turns the Moment Studio PRD into a working tool: durable per-song project state, ChatGPT/Veo prompt scaffolding with brand-kit injection, song analysis, and music-aware moment edit suggestions. The tool does not generate frames or clips itself — it organizes the workflow around the artist running ChatGPT and Veo.

## Phasing

PRD §21 q10 lists four scopes. We build in this order; each phase ships an independently usable tool.

### Phase A — Prompt scaffolding (target: working draft in ~1 day of focused build)

Just enough to replace the "retype brand context into ChatGPT" pain.

- `solypsizm new <slug>` — folder + `project.json` + copy lyrics/audio into the project.
- `solypsizm bootstrap-brand-kit` — produces `~/solypsizm/brand-kit.json` from the docx (or accepts a hand-edited one).
- `solypsizm brainstorm` — emits ChatGPT brainstorm prompt to stdout + macOS clipboard.
- `solypsizm import-concepts` — parses ChatGPT's JSON-ish reply into `concepts/concept-NN-*.json`.
- `solypsizm pick-concept`, `list-concepts`.
- `solypsizm scenes` / `import-scenes` — same pattern at the scene level.
- `solypsizm prompts <scene-id>` — emits the three prompts (ChatGPT start, ChatGPT end-continuation, Veo motion) with brand kit auto-injected, written to `scene-NN-prompts.md` and optionally piped to clipboard one at a time.
- `solypsizm status` — minimal view: concepts, scenes, prompt-readiness.

### Phase B — Asset library + song analysis

- `solypsizm import-frame` / `select-frame`.
- `solypsizm import-clip` / `select-clip` / `review-clips`.
- `solypsizm analyze` — librosa pipeline → `song-analysis.json` (sections, tempo, beat grid, downbeats).
- `solypsizm sections`.
- Atomic writes + `.state/log.jsonl` operation log.
- `solypsizm doctor` — schema + reference validation.

### Phase C — Moment suggestion + render handoff

- `solypsizm suggest-moments` per PRD §15 (heuristic, configurable via `~/solypsizm/edit-config.json`).
- `solypsizm review-moment` (plays audio range via `afplay`).
- `solypsizm render-moment` / `render-all` — handoff to Variant Builder (separate tool).
- `solypsizm trace <clip>` — reverse lookup: which moments use this clip.
- Coverage view in `status` (gaps by song section).

### Phase D — Polish for v1

- Edge-case handling for ChatGPT response parse failures (preserve raw input in `.state/last-import.txt`).
- `--api` mode opt-in for OpenAI (PRD §12.2). Disabled by default.
- Performance pass against PRD §16.3 targets.
- Hit PRD §18 success criteria.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | matches PRD §16.1, ecosystem fit for librosa |
| CLI framework | `click` | matches PRD; ergonomic subcommand groups |
| Schema validation | `pydantic` v2 | matches PRD; clean JSON I/O |
| Audio analysis | `librosa`, optionally `madmom` | matches PRD §14.1 |
| Audio I/O | `pydub` (+ ffmpeg) | matches PRD §14.1 |
| Build/packaging | `hatchling` via `pyproject.toml` | simple, modern, no setup.py |
| State format | JSON files on disk | PRD §21 q3 default; version-controllable |
| Tests | `pytest` | standard |
| Lint/format | `ruff` (lint + format) | one tool |

Install path per PRD §16.2: `pip install solypsizm-moment-studio` once published. Dev install: `pip install -e .[dev]`.

## Package layout

```
src/solypsizm_moment_studio/
  __init__.py
  __main__.py                 # python -m solypsizm_moment_studio
  cli.py                      # click root + group registration
  commands/
    project.py                # new, status, open
    concepts.py               # brainstorm, import-concepts, list, pick, rate
    scenes.py                 # scenes, import-scenes, list, prompts
    media.py                  # import-frame, import-clip, select-*, review-clips
    audio.py                  # analyze, sections
    moments.py                # suggest, review, render
    diagnostic.py             # doctor, log
    brand_kit.py              # bootstrap-brand-kit
  models/
    project.py                # Project, schema per PRD §8.1
    concept.py                # Concept, §8.2
    scene.py                  # Scene + Prompts + Frame + ClipTake, §8.3
    song.py                   # SongAnalysis, §8.4
    moment.py                 # Moment, §8.5
    brand_kit.py              # BrandKit
  prompts/
    chatgpt.py                # brainstorm + scenes + start/end frame templates
    veo.py                    # Veo 3 motion-prompt template
    parsing.py                # tolerant JSON-from-ChatGPT parser
  state/
    paths.py                  # project root resolution
    io.py                     # atomic JSON write, hashes, log.jsonl
  audio/
    analyze.py                # librosa pipeline
  suggest/
    algorithm.py              # PRD §15 heuristics
tests/
  ...
pyproject.toml
```

## Open-question decisions (PRD §21)

PRD §21 lists 10 questions. Defaults locked for v1; revisit if/when Nic flags:

| # | Question | v1 default |
|---|---|---|
| 1 | ChatGPT prompt format | Reverse-engineer from brand kit's templates (PRD §5 of brand kit). Iterate after the first real concept run. |
| 2 | Where the tool lives | Local install on Nic's Mac via `pip install -e .` from this repo; no Cowork/server component for v1. |
| 3 | State format | JSON files on disk (PRD's own default). |
| 4 | Concept count default | 5 per song. Configurable via `--count`. |
| 5 | Clip rating scale | 1–5 integers. Internal; UI can display emoji. |
| 6 | Mood tag taxonomy | Free-form for Phase A; controlled vocabulary lands in Phase C alongside the suggestion algorithm. |
| 7 | "Approved" definition | Always require human approval (`solypsizm review-moment` → accept/reject). |
| 8 | Lyrics format | Plain text default; LRC-with-timestamps accepted in Phase B `analyze --lyrics-aware`. |
| 9 | Bootstrap brand kit from docx | Yes — `solypsizm bootstrap-brand-kit` in Phase A. v1 ships with a checked-in `brand-kit.json` produced from the v1 docx so we have a baseline. |
| 10 | Build sequence | Phase A → B → C → D as above. |

## Brand kit (concrete)

The brand kit is the source-of-truth for character + aesthetic injected into every generated prompt. We extract the docx's locked character spec (visor, jacket piping, pants, boots, etc.) and palette into a structured JSON. See `brand-kit.json` at the repo root for the canonical machine-readable form.

**Always-include negative-prompt items** (assembled from the docx):
- `no slow motion, no morphing, no distorted face, no text, no watermark, no logos, no Veo/Sora watermark`

**Color palette** (locked):
- Cyan `#00D4FF` (dominant)
- Violet `#8A2BE2` (secondary)
- Purple `#5B2A86` (brand purple — title cards, end cards)
- Black `#0A0A12`
- Mid Grey `#3A3A42`
- White `#FFFFFF`

## Out of scope for v1

Per PRD §3 and §19:
- AI image/video generation (the tool drives the human running ChatGPT/Veo).
- Final video rendering (handoff to Variant Builder).
- Posting / scheduling / analytics ingestion.
- Modern Musician contest tooling — separate "Performance Clip Studio" tool.
- Tauri/Electron GUI.
- Cross-song clip reuse.
- Auto-rating clips against keyframes via vision model.
- Kling/Sora integrations.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| ChatGPT response format drifts and breaks parsing | Tolerant parser with fallback to `.state/last-import.txt`; a manual edit-and-retry loop. |
| librosa section detection is wrong on Solypsizm tracks | PRD §14.3 manual override; `analyze --force` only on demand; diff before overwrite. |
| Suggestion algorithm produces uninspired moments | Heuristic is configurable via `edit-config.json`; multiple strategies; artist can hand-edit any spec. |
| Veo / Flow Labs has no API → stays manual | Already factored in (PRD §13). v2 picks up an API path if Google ships one. |
| Brand drift if docx and JSON diverge | `bootstrap-brand-kit` is authoritative one-way; future edits are made to the JSON, not the docx, with the docx flagged "human-readable companion only". |

## Definition of done (v1)

PRD §18 in full. Specifically:

1. Cold start (`solypsizm new`) → 9 approved moment specs in ≤ 4 hours of human work.
2. Re-opening after 48h surfaces full state via `status`.
3. Zero hand-typed brand context — every prompt auto-injects.
4. `solypsizm trace <clip>` answers "which moment uses this clip" instantly.
5. `suggest-moments` produces 9 specs accepted with minor edits ≥ 70%.
6. Variant Builder produces a valid MP4 from any approved spec without manual editing.
