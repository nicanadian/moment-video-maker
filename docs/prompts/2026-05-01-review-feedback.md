# Review feedback session

**Date:** 2026-05-01
**Model:** Claude Opus 4.7

## User
> can you get a video editing expert, system tester and system operator to review the system? provide feedback, then come up with project plan to address feedback

## Assistant
Spawned three reviewer agents in parallel, each with a different lens. Full reports below; synthesized priorities and plan in `docs/projects/02-phase-d-hardening.md`.

---

## Review 1 — Video editing expert

> Ordered by impact. File paths and line refs are concrete.

**1. Veo prompt is missing the load-bearing fields, in the wrong dialect.** `templates.py:183-199` emits a flat 7-line "Subject/Action/Environment/..." block. Real Veo 3 prompts that hold character consistency need: a duration ("4-second shot"), explicit shot framing in the camera line ("locked wide, no zoom" — or Veo will invent dolly), audio direction ("no music, ambient wind only" — Veo 3 generates audio by default and will dub random music over your tracks, which is catastrophic for a music promo), pacing ("continuous take, no cuts"), and aspect/format ("vertical 9:16, 1080x1920"). The `Style` field is comma-glued ("cinematic anime, 24fps, no text overlay, no UI") which Veo treats as low-signal. `negative_prompt_string()` is dumped on one line — Veo respects negatives much better as a separate "Avoid:" stanza with newline-delimited items. Add `9:16` to `always_include_in_veo_prompts` (`brand-kit.json:105-110`); right now no prompt tells Veo the aspect ratio at all and you'll get 16:9 returns.

**2. ChatGPT image-gen cannot hold cel-shaded character consistency across many frames — and the pipeline relies on it doing so.** GPT-image-1 / DALL-E 3 do not accept reference images for character lock; "the previous image" in `end_frame_prompt` (`templates.py:172`) is wishful — continuation works for Sora/gpt-image edits but not vanilla DALL-E. Visor color (`#00D4FF`), jacket hex piping, and "horizontal LED strip with no frame" will drift on every regen. Two fixes: (a) a single locked reference PNG of the avatar, uploaded to ChatGPT first (`brand-kit.json` should declare `character.reference_image: "reference/avatar-locked.png"` and `start_frame_prompt` should say "match the uploaded reference exactly"); (b) a "from this exact pose, change only X" pattern for end-frames. Without (a), drift is the default outcome.

**3. The moment spec is missing fields a freelancer in Resolve cannot guess.** `models/moment.py` and `suggest.py:258-289` produce segments with only `audio_offset` and `duration`. Missing: per-clip `in_point`/`out_point` (Veo gives ~8s; the spec must say which slice), `transition` between segments (cut vs. crossfade vs. dip-to-black — title-card to clip is currently an implicit hard cut at 1.5s, which on a hopeful-melancholy song reads jarring), `speed_ramp`, `audio_fade_in/out`, `lyric_overlay` segment data (the brand kit defines `typography.lyric_overlay` placement at `bottom 22%`, but moments emit no overlay segments — just a `captions_source: "captions/main.srt"` reference that does not exist in the project structure §7), `hook_clip_id` flag (which clip should land in the first 1.5s window per `video_specs.hook_window_seconds`), and `safe_zones` (TikTok UI eats top 14% / bottom 22%). Also: `audio_offset` is computed from `section.start + 1.5s` (`suggest.py:269`), but the title card overlays the music — that 1.5s should *overlap* the section start, not push the music forward. As written, the chorus downbeat lands 1.5s late. **This is the biggest mechanical bug.**

**4. Suggestion algorithm doesn't align cuts to the beat grid — defeats the whole point of `librosa.beat.beat_track`.** `suggest.py:270-281` walks `audio_offset += clip_duration` using each scene's `duration_target_seconds` (often a guess, defaulting 6.0). Editors snap cuts to downbeats; this snaps to whatever number was typed in scene JSON. `analysis.py:124` computes `downbeat_times` and `beat_grid_seconds`, but `suggest.py` never imports them. Fix: quantize each clip's end to the nearest downbeat ≥ `audio_offset + clip_min`. This alone is the difference between "feels like an edit" and "feels like a slideshow."

**5. Hook landing logic is upside-down.** `_pick_hook_clip` (`suggest.py:159-177`) leads tension_release with a *low-energy* clip — but TikTok's 1.5s hook window (`brand-kit.json:83`) needs the most arresting visual immediately, not the calmest. Real tension_release on short-form: hook = 1.5s of the chorus's *climax frame* cold, then drop to the verse, then build back. Current code does the slow-build version that gets thumbed past. Also `always_lead_with_hook` only fires for `mid-high`/`high` sections (`suggest.py:217`); a `section_focus` chorus-only moment never gets a hook treatment.

**6. Section labeler will mis-label the bridge as chorus (and vice-versa) routinely.** `analysis.py:50-61` buckets by energy thirds — bridges in Solypsizm-style anthemic tracks often have *higher* RMS than verse 2 because of pads/atmospherics, so they get tagged `chorus 2` and feed `SECTION_MOOD_HINTS["chorus"] = {release, exhilaration, anthemic, high}` (`suggest.py:40`), pulling the wrong scenes. Lyrics-aware mode is mentioned in PRD §F6 but not implemented here.

**7. Pre-chorus detection is too narrow.** `analysis.py:83-85` tags pre-chorus only if `last_label in {"intro","verse"}` AND next is chorus. A common structure (verse → pre-chorus → pre-chorus 2 → chorus) gets the second pre-chorus mislabeled `bridge`.

**8. Brand drift the kit cannot prevent, but the prompt could call out:** visor "horizontal LED strip, no frame above/below" (`brand-kit.json:10`) is the #1 thing image-gen reverts to goggles/sunglasses. The character block in `_character_block` (`templates.py:10-25`) lists this once at parity with skin tone. Promote it: "CRITICAL: visor is a single horizontal cyan strip, NOT goggles, NOT sunglasses, NOT a helmet visor — no upper or lower frame." Same for jacket piping ("hexagonal angular pattern, NOT zigzag, NOT racing stripes"). Negative prompts in image-gen are weak; positive over-specification is what works.

**9. End-frame prompt `_aesthetic_block` and `theme_block` are dropped.** `end_frame_prompt` (`templates.py:164-180`) takes only `scene` — no brand kit, no song theme. Continuation drifts on palette and grade across regens because the second prompt has no anchor beyond "same character, same environment."

**10. Smaller but real:**
- `Segment.image` for `end_card` (`suggest.py:287`) hardcodes `"../shared/end-cards/stream-now.png"` — that path isn't in PRD §7's folder structure; freelancer will hit a missing file.
- `captions_source: "captions/main.srt"` (`suggest.py:301`) — same; nothing creates that folder.
- `release_date` is f-string concatenated raw (`suggest.py:265`), no formatting.
- No `target_lufs` (-14) or output `fps`/`resolution` propagated into the moment spec — freelancer guesses.
- `min_duration` for filter is `min_clips_per_moment * 4.0` (`suggest.py:324`) — fine, but excludes any short-and-punchy 8s pre-chorus you'd want as a moment.

**Biggest win to fix first:** snap every cut in `suggest.py:270-281` to the nearest downbeat from `song_analysis.downbeat_seconds` and remove the `+1.5s` title-card offset shift on `audio_offset`. These two changes turn "AI clip slideshow" into "edit that lands."

---

## Review 2 — QA engineer

### CRITICAL

- **[BUG] `_find_existing_hash` blocks reimport of replaced files** (`commands/media.py:35-48`). Record persists after file deletion; same-content reimport rejected pointing at a missing file. No test.
- **[BUG] `import-frame`/`import-clip` move source then crash on `save_scene`** (`media.py:90-97`). Asymmetric failure: source gone, no record. No rollback.
- **[BUG] `append_log` is not atomic and not crash-safe** (`state/io.py:167-173`). Partial writes during crash leave torn JSON; concurrent runs interleave bytes.
- **[BUG] `save_json_atomic` is not actually atomic on power loss** (`state/io.py:34-41`). No fsync of tmp file before rename, no fsync of directory after. APFS power-loss can leave zero-length project.json.
- **[BUG] `label_sections` median is unstable at boundary energies** (`analysis.py:35-39`). Ties don't resolve consistently; no boundary-tie test.
- **[BUG] Moment `audio_offset` math is wrong** (`suggest.py:269-281`). Title-card shift offsets the music 1.5s; nothing clamps total clip duration to `section.end`.

### HIGH

- **[BUG] Scene id collision when `slugify(title)` returns empty string** (`commands/scenes.py:85`, `commands/concepts.py:82`). Unicode-only or punctuation-only titles yield `scene-01-`; collisions overwrite silently.
- **[BUG] `_next_frame_filename` race after deletion** (`media.py:51-57`). `len(existing) + 1` ignores deleted entries; reimport name collides.
- **[BUG] `_find_balanced` doesn't handle smart quotes / Unicode quote variants** (`prompts/parsing.py:37-68`). ChatGPT's curly quotes still flip string-state on a regular ASCII `"` inside.
- **[BUG] Tolerant parser silently fails on trailing-comma JSON** (common ChatGPT output).
- **[ROBUSTNESS] librosa empty/silent audio path** (`analysis.py:116-137`). `tempo=0`, `beat_frames=[]` silently saved; `agglomerative` raises if `target_k >= frames`.
- **[ROBUSTNESS] `analyze` mid-pipeline failure → stack trace not click error** (`commands/audio.py:34-43`).
- **[ROBUSTNESS] `clipboard_copy` doesn't catch `FileNotFoundError`** if pbcopy disappears between `which` and `run`.
- **[ROBUSTNESS] `find_project_root` walks past user home** (`state/paths.py:23-31`); could bind onto an unrelated `project.json`. Consider also requiring `.state/`.
- **[ROBUSTNESS] `run_open` writes status to stdout** (`commands/project.py:141-147`); breaks `cd $(solypsizm open <slug>)`.
- **[ROBUSTNESS] `run_review_clips` always opens Finder**; no `--no-open` flag.

### MEDIUM / MISSING TESTS

- `save_json_atomic` with non-ASCII content; `parse_concepts_response` against trailing comma / smart quotes / BOM / NUL / doubled fences; very large input (10MB); `import-frame` duplicate / missing source / broken symlink / permission denied / cross-filesystem; `suggest_moments` with empty / single-section analysis; `label_sections` ties / all-equal / 2-section; concept import duplicate-title slug collisions; `_find_existing_hash` after delete-and-reimport; concurrent log writes; `analyze --force` with hand-edits already in JSON; `target_count` rounding edge cases; `Section.energy_peak` migration for older JSONs.

### NITS

- `Project.brand_kit_path` resolves relative to project (fragile when moved); `_load_context` uses `solypsizm_home()` instead — silent inconsistency.
- `now_iso` uses `timespec="seconds"`; ties make `max(..., key=...)` unstable.
- `EditConfig.section_diversity_weight` declared but never read.
- `INTERNAL_SECTION_FIT_WEIGHT = 0.6` hardcoded; PRD says configurable.
- `Scene.frames: dict[str, list[Frame]] = {"start": [], "end": []}` — verify pydantic v2 deep-copies the default.

**Fix this first:** make `append_log` and `save_json_atomic` truly crash-safe (lock + fsync), and rollback `import-frame`/`import-clip` so `shutil.move` is reverted if the subsequent `save_scene` fails — those three together protect project state against the kinds of mid-run interrupts the artist will actually hit.

---

## Review 3 — System operator

> Ordered by impact on daily use.

1. **[WORKFLOW GAP] No `--project <slug>` flag despite PRD §9 promising it.** Only `status`/`open` accept a slug; every other command requires CWD inside the project. With 3 songs in flight the artist must `cd` between trees constantly.
2. **[DISCOVERABILITY] `status` doesn't tell the user what to do next.** PRD §18 success criterion #2 says "status tells the artist exactly what to do next." Today it lists counts and gaps but never names the next command.
3. **[WORKFLOW GAP] No `pick-scene` / current-scene state.** The artist will be re-typing `scene-01-wide-approach` dozens of times per day. No shell completion either.
4. **[RECOVERY] `import-concepts` / `import-scenes` can't be retried partial-state.** No dedupe and no `--replace`/`--dry-run`.
5. **[RECOVERY] Frame/clip imports use `shutil.move` and reject duplicates by hash.** Source file gone from `~/Downloads` even on rejection. No undo. Default to copy with `--move` opt-in, or add `delete-clip` / `select-frame --remove`.
6. **[ERROR HANDLING] `render-moment` / `render-all` always fail with "Variant Builder not wired."** Either gate with a `--dry-run-only` success path, or hide from `--help` until wired.
7. **[DISCOVERABILITY] `doctor` doesn't check the failure modes that actually happen.** Missing: ffplay/ffmpeg/pbcopy availability, librosa-extras installed, `audio/master.{wav,mp3,m4a}` matches `project.audio_file`, `SOLYPSIZM_HOME` resolution, `.state/` write-perms. Add `solypsizm doctor --global`.
8. **[WORKFLOW GAP] No `trace` from concept/scene direction.** Add `solypsizm gaps` listing scenes with status != complete; `solypsizm trace --scene <id>` / `--concept <id>`.
9. **[ERROR HANDLING] `pick-concept` accepts only the full id.** Typing `pick-concept 1` or `pick-concept watchtower` should work. Same for every other `<id>` argument.
10. **[RECOVERY] `analyze --force` warns "manual edits will be lost" but doesn't diff.** PRD §14.3 explicitly requires "diff-shows what would change before overwriting."
11. **[NIT] `log` has no `--tail`/`--since`/`--filter event=` and no pager.** After 3 weeks unreadable.
12. **[NIT] `review-clips` opens Finder unconditionally**; breaks SSH / Linux secondary platform.
13. **[NIT] `prompts <scene-id> --copy` uses `click.pause`** — stdin-bound, breaks if anything is piped.
14. **[NIT] `SOLYPSIZM_HOME` env override is undocumented in README.** No "Backup & sync" note; no `.gitignore` template in `solypsizm new`.
15. **[DISCOVERABILITY] Onboarding gap.** `bootstrap-brand-kit` requires the user to already have a `brand-kit.json` source. Cold-start freelancer will not get to a first action in 10 minutes. Default `--source` to the repo's checked-in `brand-kit.json`; expand README cold-start.

**Biggest daily-use win:** Add a "Next:" recommendation line to `status` plus a `pick-scene` current-scene pointer — together they eliminate the two highest-frequency frictions (remembering the next command, and re-typing scene ids) for every session.

---

## Synthesis & plan

The plan is in `docs/projects/02-phase-d-hardening.md`. Six sub-phases:

- **D1 Correctness** (P0): downbeat alignment, atomic writes, import rollback, `audio_offset` fix, hash-after-delete, slug fallback, hook-strategy fix.
- **D2 Prompt fidelity** (P0): Veo aspect / audio / duration / negative formatting; `character.reference_image`; CRITICAL visor + piping anti-patterns; end-frame brand-kit injection.
- **D3 Moment spec completeness** (P1): `in_point`/`out_point`, transitions, lyric overlay segments, `hook_clip_id`, lufs/fps/res/safe_zones; remove hardcoded paths.
- **D4 Operator UX** (P1): `--project` flag, "Next:" in status, `pick-scene`, fuzzy IDs, copy-not-move default, `analyze --force` diff, `doctor --global`, log filtering, `open` stdout/stderr split, README cold-start.
- **D5 Test gaps** (P2): smart quotes, label-tie, slug collisions, dedup-after-delete, large inputs, empty analysis, mutable-default audit.
- **D6 Originally-deferred** (P3): `--lyrics-aware`, `--api`, `madmom`, perf pass.

Open questions surfaced for Nic:
1. Veo audio direction: silent video or ambient SFX bed?
2. Reference image for character lock — do we already have a canonical PNG?
3. `tension_release` semantics — replace with cold-hook or keep both?
4. `shared/end-cards/` and `captions/` location.
5. `--move` vs `--copy` default for imports.
