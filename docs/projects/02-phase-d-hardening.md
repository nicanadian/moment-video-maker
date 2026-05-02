# Phase D: hardening + feedback response

**Status:** in-progress (D1 partial + D2 + D3.1 + D4.1/2/3/4/5 + agent-found bug fixes landed; D1.3/D1.4/D1.8/D3 remainder/D4.6+ remaining)
**Owner:** Nic
**Started:** 2026-05-01
**Trigger:** three-reviewer audit (video editing expert / QA engineer / system operator)
**Source PRD:** `ref-docs/Solypsizm Moment Studio - PRD.md`
**Predecessor:** `docs/projects/01-moment-studio-v1.md` (Phases A + B + C)

## Progress log

- **2026-05-01** — Locked answers to the open questions (no Veo audio, character-reference embedded, `tension_release` stays as-is, `~/solypsizm/shared/` for end cards, copy by default). Landed:
  - **D2.1** Veo prompt: explicit `Aspect`, `Duration`, `Audio: silent video — no music, no dialogue, no foley, no SFX`, negatives reformatted as a separate `Avoid:` newline-stanza.
  - **D2.2** Extracted canonical front-view PNG from the docx into `character-reference/front.png`. Added `character.reference_image` + `reference_images` dict to brand-kit.json + BrandKit model. `start_frame_prompt` now leads with a "BEFORE PASTING: upload the reference image at <path>" instruction. `bootstrap-brand-kit` mirrors the `character-reference/` folder into `~/solypsizm/`.
  - **D2.3** CRITICAL anti-patterns added inline to the visor and jacket descriptions: "single thin cyan strip — NOT goggles, NOT sunglasses, NOT a helmet visor"; "HEXAGONAL — NOT zigzag, NOT racing stripes, NOT diagonals". Echoed in the end-frame prompt's preserve-detail line.
  - **D2.4** `end_frame_prompt` now takes `project` + `scene` and re-anchors palette/grade with `bk.aesthetic.lighting_cues` and `bk.song_theme(project.song_slug)`.
  - **D1.1** `audio_offset` math fixed: title card overlays section start instead of pushing music forward; first clip starts at exactly `section.start`.
  - **D1.2** Cuts snap to `song_analysis.downbeat_seconds` (falling back to `beat_grid_seconds`). New two-pass `_select_cut_points` picks ideal even-distribution targets first, then snaps each to the nearest grid value within a floor/ceiling window — distributes slack across all clips instead of dumping it on the last.
  - **D1.5** `import-frame`/`import-clip` rollback: if `save_scene` fails after the file lands, the destination is unlinked.
  - **D1.6** Hash dedup check now skips records whose on-disk file no longer exists, so deleting and re-importing the same content works.
  - **D1.7** `slugify` returns `"untitled"` (configurable) for unicode-only / punctuation-only / empty inputs. No more empty-slug ID collisions.
  - **D4.5** Frame/clip imports default to `--copy`; `--move` is opt-in. The success line says "Copied" or "Moved".
  - **D3.1** Added `in_point` / `out_point` to `Segment` (start at 0.0, equal to clip duration by default — Variant Builder can override per-take).
  - **D3.6** Removed hardcoded `image="../shared/end-cards/stream-now.png"` and `captions_source="captions/main.srt"` from `build_moment` — both now omitted when not configured. Will surface as brand-kit-driven config in a follow-up.

  Test suite is now 40/40 green (added 4 suggest tests for new audio_offset / downbeat snap / clip in/out + 7 utils.slugify tests). End-to-end smoke confirms: prompts emit reference-image instruction at top + Veo `Audio: silent video` + CRITICAL anti-patterns; cut points 25.20 / 33.00 / 38.20 against 92-BPM downbeat grid; copy-default preserves the source in `~/Downloads`; `--move` removes it; reimport after delete works.
- **2026-05-02** — Two reviewer agents ran the full workflow E2E and surfaced flow blockers. All addressed in two commits:
  - **moment ID sequencing**: `suggest-moments` now numbers from `len(existing) + 1`, never overwrites approved/rejected work, appends `-2`/`-3` for genuine collisions, returns a `(moments, stop_reason)` tuple so callers can explain when fewer than `--count` were produced.
  - **`analyze` traceback**: wrapped librosa pipeline in try/except; bad audio files now produce a clean ClickException naming the underlying error type instead of a Python traceback.
  - **parser shape validation**: every concept / scene item must now have a non-empty `'title'` field; `{"data": "not concepts"}` is rejected instead of silently fabricating `concept-01-untitled`.
  - **`coerce_str_list` helper**: replaced naive `list(raw[...])` calls in import-concepts and import-scenes that were char-iterating ChatGPT-string-as-list (`"intro"` → `["i","n","t","r","o"]`). Now wraps a string as a one-item list and splits comma-separated strings.
  - **title preservation**: empty / unicode / punctuation titles preserve the displayed value (`"好"`, `"!!!"`) and only the slug falls back to `untitled` for the ID.
  - **D4.1 — "Next:" line in `status`** based on project state. Reads concepts → current concept → scenes → prompts → frames/clips → analysis → moments → review and recommends the next concrete command.
  - **`list-moments`** for parity with `list-concepts` / `list-scenes`.
  - **slug stopword filter** drops `the / a / of / to / and / or / in / on / at / by / for / with` so `concept-01-abandoned-watchtower-at-dawn` becomes `concept-01-abandoned-watchtower-dawn`.
  - **D4.2 — `--project <slug>` flag** (also `SOLYPSIZM_PROJECT` env var) routes through `require_project_root`. Lets the artist `solypsizm --project haze status` from anywhere.
  - **D4.3 — `pick-scene` + `current_scene`** field on Project. `--scene` is now optional on `import-frame`, `import-clip`, `select-frame`, `select-clip`, `review-clips`, `prompts`; defaults to the current scene if set.
  - **D4.4 — fuzzy / prefix / substring ID matching** via `resolve_id`: `pick-concept watch` resolves to `concept-01-watchtower`. Ambiguous matches list all candidates so the user can disambiguate.
  - **D3.1 — `Segment.in_point` / `out_point`** populated; Variant Builder now knows which slice of an 8s Veo output to use.

  Test suite is now 53/53 green (added 13 new tests: sequential ID continuation, collision suffix, stop_reason, parser title-required, `coerce_str_list` shape coverage, slug stopwords).

## Why this exists

After A/B/C landed, three independent agents reviewed the system end-to-end. Each found enough load-bearing problems that the original Phase D scope ("polish") is replaced by this plan. The reviews are summarized below; full text is preserved in `docs/prompts/2026-05-01-review-feedback.md`.

## Top findings, by reviewer

### Video editing expert

1. **Veo prompt is missing the load-bearing fields and will produce music-dubbed clips** (`prompts/templates.py:183-199`). No aspect ratio (returns 16:9), no audio direction (Veo 3 generates audio by default and will dub random music over the master — catastrophic for a music promo), no clip duration, weak negative-prompt formatting.
2. **DALL-E doesn't hold cel-shaded character lock without a reference image.** `end_frame_prompt` says "the previous image" — that's wishful thinking outside Sora/gpt-image-edit. Need an explicit `character.reference_image` declared in the brand kit, uploaded once to ChatGPT, referenced by every prompt.
3. **Moment spec is missing fields a Resolve editor can't guess**: per-clip `in_point`/`out_point` (Veo gives ~8s, the spec must say which slice), `transition`, `lyric_overlay` segments, `hook_clip_id`, `safe_zones`, `target_lufs`/`fps`/`resolution`. Hardcoded paths `../shared/end-cards/stream-now.png` and `captions/main.srt` aren't in PRD §7's folder structure.
4. **Cuts don't align to the beat grid.** `analysis.py` computes `downbeat_seconds` and `beat_grid_seconds` but `suggest.py` never imports them. Clip ends advance by `scene.duration_target_seconds` (often a guess). This is the difference between "feels like an edit" and "feels like a slideshow."
5. **`audio_offset` math is wrong.** `suggest.py:269` shifts the first clip's offset by `+1.5s` for the title card — but the title card overlays the section start; the music shouldn't move. The chorus downbeat lands 1.5s late under current code. Same path also doesn't clamp the cumulative duration to `section.end`.
6. **`tension_release` hook is upside-down.** `_pick_hook_clip` leads with a *low-energy* clip; on TikTok the 1.5s hook needs the most arresting visual cold — the chorus climax frame, not the verse calm. Current behavior is the "slow-build" version that gets thumbed past.
7. **End-frame prompt drops the brand kit and song theme** (`templates.py:164-180`) — palette and grade drift across regenerations.
8. **Visor description isn't promoted to CRITICAL with anti-patterns.** Image-gen reverts to goggles/sunglasses/helmet visor by default; the brand kit says "horizontal LED strip with no upper or lower frame" once, at parity with other fields. Needs to be loud.

### QA engineer

1. **`save_json_atomic` isn't actually atomic on power loss** (`state/io.py:34-41`). `os.replace` is atomic for the directory entry, but the tmp file's data isn't fsynced and the directory isn't fsynced after rename. APFS power-loss can leave zero-length project.json.
2. **`append_log` is not crash-safe.** Plain `f.write` on append mode; concurrent runs interleave bytes; partial writes leave torn JSON lines that `run_log` silently echoes.
3. **`import-frame`/`import-clip` move the source before saving the scene.** If `save_scene` fails (disk full, validation, permission) the source file is gone and no record exists. No rollback.
4. **Hash-based dedup blocks reimport of replaced files.** A frame record persists after the file on disk is deleted; same-content reimport is rejected pointing at a missing file. No test.
5. **Tolerant parser fails on smart quotes and trailing commas** (`prompts/parsing.py:37-91`) — both are ChatGPT-emit-by-default. `_find_balanced` can't detect Unicode quote variants as string boundaries.
6. **Scene ID collision when `slugify(title)` returns empty** (`commands/scenes.py:85`, `commands/concepts.py:82`) — unicode-only or punctuation-only titles yield IDs like `scene-01-`, two collide, `_scene_path` overwrites silently.
7. **`label_sections` median tie behavior is unstable** at boundary energies. No boundary-tie test.
8. **`open <slug>` writes status to stdout** so `cd $(solypsizm open haze)` captures everything, not just the path.
9. **Missing tests** for: parser against smart quotes / trailing commas / large inputs / BOM / doubled fences; label_sections with ties / all-equal / 2-section input; ID collisions on empty/unicode slugs; concurrent log writes; `analyze --force` overwriting hand-edits; `Scene.frames` shared-mutable-default check.

### System operator

1. **No `--project <slug>` flag** despite PRD §9 promising it. With 3 songs in flight the artist must `cd` between trees constantly.
2. **`status` doesn't tell the user what to do next.** PRD §18 success criterion #2 explicitly requires this. Today it lists counts and gaps but never names the next command.
3. **No `pick-scene` / current-scene state.** Every scene-targeted command demands the full scene id; the artist will be re-typing `scene-01-wide-approach` dozens of times per day.
4. **Frame/clip imports use `shutil.move`.** If rejected (duplicate hash, wrong scene, typo'd `--type`) the source file is already gone from `~/Downloads`. No undo.
5. **`render-moment` always errors** with "Variant Builder not wired" — burns the artist every time. Either a `--dry-run` success path or hide from `--help` until wired.
6. **`doctor` doesn't check the failure modes that actually happen** — ffplay/ffmpeg/pbcopy availability, librosa-extras installed, `SOLYPSIZM_HOME` resolution, `.state/` write-perms. Add `solypsizm doctor --global`.
7. **`analyze --force` doesn't diff** — PRD §14.3 explicitly requires "diff-shows what would change before overwriting." Currently overwrites without preview.
8. **`pick-concept`, `trace`, etc. accept only the full id.** Typing `pick-concept 1` or `pick-concept watchtower` should work. Same for every `<id>` argument.
9. **`log` reads the whole jsonl into stdout.** After 3 weeks of work this is unreadable. Default to last 50 lines; add `--all`, `--event`, `--scene`.
10. **`bootstrap-brand-kit` requires the user to already have a JSON source.** Cold-start freelancer can't get to a first action in 10 minutes. Default `--source` to the repo's checked-in `brand-kit.json`; expand README cold-start.

## Phase D plan

Six sub-phases. D1–D2 are correctness and prompt fidelity; without these the tool produces objectively wrong output. D3–D5 are feature completeness and ergonomics. D6 is the previously-deferred polish.

### D1 — Correctness (P0, ship before any real song run)

| Task | Source | Files |
|---|---|---|
| D1.1 Fix `audio_offset` math: title card overlaps section start, don't shift; clamp clip durations to `section.end - section.start` | editor #5, QA #1 | `suggest.py` |
| D1.2 Snap clip boundaries to nearest downbeat from `song_analysis.downbeat_seconds` (fall back to beat grid, then nominal duration if no beats in window) | editor #4 | `suggest.py`, `analysis.py` |
| D1.3 `save_json_atomic` does fsync(tmp) → rename → fsync(parent dir) | QA #1 | `state/io.py` |
| D1.4 `append_log` uses `O_APPEND` open with single-write boundary, file lock for concurrent safety, JSONL line written atomically | QA #2 | `state/io.py` |
| D1.5 Rollback on import: stage to `<scene-dir>/.staging/<name>` first, save_scene, then move into final position; on save failure, move source back | QA #3 | `commands/media.py` |
| D1.6 Hash dedup ignores stale records: when a hash matches but the recorded file no longer exists on disk, drop the record and allow reimport | QA #4 | `commands/media.py` |
| D1.7 Slug fallback: when `slugify(title)` is empty, use a counter-based id (`scene-01-untitled`) and warn | QA #6 | `utils.py`, callers |
| D1.8 Fix `tension_release`: lead with a chorus-climax-energy clip on the 1.5s hook, then verse, then climb back. Or rename current behavior to `slow_build` and add `cold_hook` as a separate strategy | editor #6 | `suggest.py` |
| D1.9 `_pick_hook_clip` scores against the upcoming section, not just energy | editor #6 | `suggest.py` |

### D2 — Prompt fidelity (P0; without these the clips are wrong)

| Task | Source | Files |
|---|---|---|
| D2.1 Veo prompt: add explicit `Aspect: 9:16, 1080x1920` line; `Audio: silent video, no music, no dialogue, no foley`; `Duration: ~6s continuous take, no cuts`; reformat negatives as a separate `Avoid:` stanza, one per line | editor #1 | `prompts/templates.py`, `brand-kit.json` |
| D2.2 Add `character.reference_image` field to brand-kit.json + a `bootstrap-character-reference` flow; emit "use the uploaded reference image as the seed" instruction in `start_frame_prompt` | editor #2 | `models/brand_kit.py`, `brand-kit.json`, `prompts/templates.py` |
| D2.3 Promote visor / jacket-piping descriptions: tag them `CRITICAL` in the character block with explicit anti-patterns ("NOT goggles, NOT sunglasses, NOT a helmet visor; NOT zigzag, NOT racing stripes") | editor #8 | `prompts/templates.py` |
| D2.4 `end_frame_prompt` injects brand kit aesthetic + song theme to anchor palette/grade | editor #7 | `prompts/templates.py` |

### D3 — Moment spec completeness (P1; before Variant Builder lands)

| Task | Source | Files |
|---|---|---|
| D3.1 Add per-clip `in_point` / `out_point` to `Segment`; default to `[0, scene.duration_target_seconds]`; populated in `build_moment` | editor #3 | `models/moment.py`, `suggest.py` |
| D3.2 Add per-segment `transition` (`hard_cut` default, `crossfade`, `dip_to_black`); algorithm picks based on energy delta | editor #3 | `models/moment.py`, `suggest.py` |
| D3.3 Add `lyric_overlay` segment type; populate from `captions_source` if present (timed lyric range over each clip) | editor #3 | `models/moment.py`, `suggest.py` |
| D3.4 Add `hook_clip_id` (or `hook` boolean per segment) flagging which clip lands in the first 1.5s | editor #3 | `models/moment.py`, `suggest.py` |
| D3.5 Propagate `target_lufs`, `fps`, `resolution`, `safe_zones` from brand kit into the moment header | editor #3 | `models/moment.py`, `suggest.py` |
| D3.6 Replace hardcoded `../shared/end-cards/stream-now.png` and `captions/main.srt` with brand-kit-driven paths or omit when missing | editor #10 | `suggest.py`, `brand-kit.json` |

### D4 — Operator UX (P1; daily-use friction)

| Task | Source | Files |
|---|---|---|
| D4.1 Add "Next:" recommendation line to `status` based on project state (no concepts → brainstorm; current concept has no scenes → scenes; etc.) | operator #2 | `commands/project.py` |
| D4.2 Add top-level `--project <slug>` flag (also `SOLYPSIZM_PROJECT` env) routed through `require_project_root()` | operator #1 | `cli.py`, `state/paths.py` |
| D4.3 Add `pick-scene <id>` + `current_scene` field on Project; make `--scene` optional defaulting to current | operator #3 | `models/project.py`, `commands/scenes.py`, `commands/media.py` |
| D4.4 Fuzzy / prefix ID matching for `pick-concept`, `pick-scene`, `review-moment`, `trace`, etc. | operator #8 | shared resolver helper |
| D4.5 Frame/clip import: `--copy` (default) vs `--move`. Doctor can recommend `--move` once trust is established | operator #4 | `commands/media.py` |
| D4.6 `analyze --force` shows a diff of changing fields and prompts before overwriting | operator #7 | `commands/audio.py` |
| D4.7 `doctor` extends to check ffplay / ffmpeg / pbcopy / librosa availability + `SOLYPSIZM_HOME` resolution + `.state/` write-perms; `doctor --global` runs without a project root | operator #6 | `commands/diagnostic.py` |
| D4.8 `log` defaults to last 50 lines; flags `--all`, `--event <type>`, `--scene <id>`, `--since <iso>` | operator #9 | `commands/diagnostic.py` |
| D4.9 `open <slug>` prints path to stdout, status to stderr (so `cd $(solypsizm open haze)` works) | QA #robust | `commands/project.py` |
| D4.10 `bootstrap-brand-kit` defaults `--source` to the repo's checked-in JSON; README adds 3-line cold start | operator #10 | `commands/brand_kit.py`, `README.md` |
| D4.11 `render-moment` either succeeds with "spec at <path> ready for Variant Builder" (zero exit) or is hidden from `--help` until wired | operator #5 | `commands/moments.py`, `cli.py` |
| D4.12 `review-clips --no-open` flag for headless / SSH | operator #12 | `commands/media.py` |

### D5 — Test gaps (P2; raise confidence)

| Task | Source |
|---|---|
| D5.1 Parser: smart quotes, trailing commas, BOM, NUL bytes, doubled fences, very large inputs (10MB) | QA #5 |
| D5.2 `label_sections`: median ties, all-equal energies, 1- and 2-section inputs | QA #7 |
| D5.3 Slug collisions on empty / unicode-only titles | QA #6 |
| D5.4 `import-frame` after delete-and-reimport | QA #4 |
| D5.5 `suggest_moments` with empty / single-section analysis | QA |
| D5.6 Concurrent `append_log` interleaving | QA #2 |
| D5.7 `analyze --force` against a hand-edited song-analysis.json | QA |
| D5.8 `Scene.frames` shared-mutable-default audit | QA nit |

### D6 — Originally-deferred (P3)

- `analyze --lyrics-aware` (PRD §F6).
- `--api` mode for OpenAI (PRD §12.2).
- `madmom`-based downbeat detection.
- Performance pass against PRD §16.3 targets.

## Open questions for Nic

1. **Veo audio direction.** Editor flagged Veo 3 dubs music by default. Confirm: should every Veo prompt include `Audio: silent video, no music`? Or do we want Veo's ambient SFX (wind, footsteps) to bed under the master?
2. **Reference image for character lock.** Editor recommends a single locked PNG of the avatar uploaded once to ChatGPT. Do you already have a canonical reference (the brand kit's "Required reference images" list mentions "front, full-body, hands at sides")? If so, drop the path; we'll wire `character.reference_image` to it.
3. **`tension_release` semantics.** Current implementation is "slow build" (low-energy hook → chorus). Editor says short-form needs cold-hook (chorus-climax 1.5s → drop to verse → build back). Want the cold-hook version to replace `tension_release`, or co-exist as a new `cold_hook` strategy?
4. **`shared/end-cards/`.** PRD §8.5 example references it but PRD §7 folder structure doesn't define it. Where should that asset folder live? `~/solypsizm/shared/`? In-repo? Per-project?
5. **`captions/main.srt`.** Same — undefined location. Will captions be hand-generated by Resolve Speech-to-Text per the brand kit's pre-production checklist, or auto-generated by the tool?
6. **`--move` vs `--copy` default for imports.** Operator says default-copy is safer (Downloads stays clean). Veo outputs are files Nic might want to keep around in Downloads anyway. Confirm: copy by default?

## Out of scope for Phase D

- Variant Builder integration (separate tool; D4.11 is just the handoff polish).
- Tauri/Electron GUI.
- Cross-song clip reuse.
- Performance dashboard / analytics ingestion.
- Sora / Kling alternatives.
- Auto-rating of clips.

## Definition of done

- All P0 (D1, D2) closed.
- All P1 (D3, D4) closed except items the open questions defer.
- Test suite ≥ 50 cases; all green.
- A real run on the Haze song produces 9 moment specs that the artist accepts with minor edits ≥ 70% (PRD §18 success criterion #5).
- A freelancer can clone the repo, run `pip install -e ".[dev,audio]"`, run `solypsizm bootstrap-brand-kit`, and reach the first useful action in ≤ 10 minutes.
