# Phase D — E2E review fixes + multi-project ergonomics

**Date:** 2026-05-02
**Model:** Claude Opus 4.7

## User
> Okay, start works on Phase D. Get some operators and tests to run ETE workflows through the system to make sure everything works clean and is able to progress from step to step through the full worklfow

## Assistant

Spawned two reviewer agents in parallel to drive the full PRD §6 workflow against the live system. Then implemented fixes in two commits.

### Reviewer findings

**Operator (happy path)** — full workflow runs without crashes; brand-kit injection, status dashboard, and trace work as PRD describes. Critical gaps:
1. `[BLOCKER]` `suggest-moments` reuses moment IDs and silently overwrites approved work. Run twice → both produce `moment-01-intro.json`; the second clobbers the first.
2. `[FRICTION]` Hash-dedup blocks legitimate cross-scene reuse of the same source file (no `--force` override).
3. `[FRICTION]` No "next command" hint after most state changes (only `status` does it via section gaps).
4. `[POLISH]` Slugs include filler words: `concept-01-abandoned-watchtower-at-dawn`.
5. `[POLISH]` `analyze` reports nonsense BPM (8.57) on synthetic data — sanity-check warning would help.
6. `[POLISH]` No `list-moments` parity.

**Tester (adversarial)** — bug cluster around exit codes and shape validation:
1. `[BUG]` `analyze` on corrupted WAV dumps `audioread.exceptions.NoBackendError` traceback to user.
2. `[BUG]` `import-concepts` with `{"data":"not concepts"}` succeeds, fabricating `concept-01-untitled`.
3. `[BUG]` `import-scenes` accepts `"intro"` (string) for `song_section_fit: list[str]` and char-iterates it to `["i","n","t","r","o"]`.
4. `[BUG]` Empty / whitespace title silently rewrites the displayed title to `"untitled-3"` — data loss.
5. `[BUG]` `--approve --reject` together not always rejected (depends on flag order — already protected, verified).
6. `[BUG]` Many error paths exit 0 when they should exit non-zero.
7. Confirmed working: smart-quote handling in JSON; `prompts --copy < /dev/null`; missing-file detection; `pick-concept` / `prompts` with bad IDs; reimport-after-delete.

### Fixes shipped

**Commit 1 — flow blockers** (`Phase D part 2: fix agent-found flow blockers`):
- `suggest_moments(...)` now returns `(moments, stop_reason)`; caller (`run_suggest_moments`) reads existing moments first, passes `start_index = len(existing) + 1` and `reserved_ids`, never touches approved work, appends `-2` / `-3` for true collisions, prints why if fewer than `--count` produced.
- `analyze` wraps the librosa pipeline in try/except → clean ClickException naming the failure.
- Parser requires non-empty `title` per item — wrong-shape JSON rejected before it can fabricate concepts.
- `coerce_str_list` helper replaces naive `list(...)` in import-concepts / import-scenes — wraps string as one-item list, splits comma-separated, passes through actual lists.
- Empty / unicode titles preserve displayed value (`"好"`, `"!!!"`) — only the slug falls back to `untitled`.
- `status` grew a `Next:` line that names the next concrete command based on project state.
- `list-moments` added.
- Slug stopword filter trims fillers.

**Commit 2 — multi-project ergonomics** (this commit):
- `--project <slug>` top-level flag (also `SOLYPSIZM_PROJECT` env var) routes through `require_project_root`. Run `solypsizm --project haze status` from anywhere.
- `pick-scene` command + `current_scene` field on Project.
- `--scene` is now optional on `import-frame`, `import-clip`, `select-frame`, `select-clip`, `review-clips`, `prompts`; defaults to current scene.
- `resolve_id` helper provides exact → prefix → substring fallback for concept / scene / moment IDs. `pick-concept watch` resolves to `concept-01-watchtower`. Ambiguous matches list candidates.

### Tests

53 / 53 green. Added 13 new cases:
- `suggest_moments` sequential numbering, collision suffix, stop_reason
- Parser rejects title-less items
- `coerce_str_list` wraps / splits / passes through
- Slug stopword behavior

### E2E re-verification (post-fix)

Same workflow the operator ran:
- Wrong-shape JSON `{"data":"not concepts"}` → `ParseError`, raw saved to `.state/last-import.txt`.
- Unicode titles preserved: `[draft] 好`, `[draft] !!!`.
- String for `song_section_fit` becomes `["intro", "verse 1"]` (split on comma).
- First `suggest-moments --count 2` → `moment-01-intro` + `moment-02-chorus-1`. Approve `moment-01-intro`. Second run → `moment-03-intro` + `moment-04-chorus-1`; first stays `approved`.
- `--project haze` works from `/tmp`.
- `pick-concept watch` resolves to full id; `pick-scene approach` ditto.
- `solypsizm prompts` (no scene id) uses current scene.
- Ambiguous `pick-scene scene-0` errors with both candidates listed.

### Still open in Phase D

- D1.3 / D1.4 atomic-write hardening (fsync + lock for `append_log`).
- D1.8 `cold_hook` strategy (per Nic's "depends on the song and moment", will keep `tension_release` and add this alongside).
- D3 remaining moment-spec fields: `transition`, lyric-overlay segments, `hook_clip_id`, lufs/fps/safe_zones propagation.
- D4.6 `analyze --force` diff before overwrite.
- D4.7 `doctor --global` with binary checks.
- D4.8 `log --tail` / `--filter` / `--since`.
- D4.9 `open <slug>` stdout/stderr split.
- D4.10 README cold-start.
- D4.11 `render-moment` exit-zero-with-spec-path alternative.
- D5 test gaps: smart quotes / trailing commas in parser, label-tie behavior, large inputs.
- D6 deferred extras: `--lyrics-aware`, `--api`, `madmom`.
