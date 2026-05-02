# Phase D wrap + panel review

**Date:** 2026-05-02
**Model:** Claude Opus 4.7

## User
> Keep knocking out the remaining phase D dev. Then get a panel of folks to review what has been built, listen to their feedback and address any recommendations that make sense for an initial version of this software, recognizing it is a first cut and can expand in capability later

## Assistant

### Phase D wrap (commit `c031c31`)

- **D1.3 fsync atomic write**: `save_json_atomic` now fsyncs the tmp file before rename and the parent directory after, so APFS power-loss can't leave zero-length project.json.
- **D1.4 append_log lock**: `fcntl.flock` + `os.fsync` so concurrent runs can't interleave bytes mid-line.
- **D1.8 cold_hook strategy**: third option alongside `section_focus` / `tension_release`. On high-energy sections leads with the highest-rated high-energy clip — the chorus-climax-first pattern the editor said TikTok hooks need.
- **D4.6 analyze --force diff**: shows section / tempo / duration changes and prompts for confirm before overwriting hand-edits.
- **D4.7 doctor --global**: checks ffplay / ffmpeg / pbcopy / open / librosa availability + SOLYPSIZM_HOME + brand-kit.json without needing a project root.
- **D4.8 log filtering**: `--tail` (default 50) / `--all` / `--event` / `--since`.
- **D4.9 open stdout/stderr split**: path on stdout, summary on stderr — `cd $(solypsizm open haze)` works cleanly.
- **D4.10 README cold-start**: 5-step from clone → first project.
- **D4.11 render-moment exit-zero-with-spec-path**: prints the spec to stdout and a stderr note; downstream tooling can pipe.
- **D5 parser robustness**: BOM stripped at head; new tests for smart quotes / trailing commas / 1k-item input / doubled fences.

Test suite at 59/59 green.

### Panel review

Spawned three reviewers in parallel against the v1 cut:

**Product manager** — verdict: **ship with caveats.**
- Tool delivers PRD §1's core promise (durable memory + prompt scaffolding). §2 goals 1, 2, 3, 4, dashboard half of 5 all land.
- Riskiest unverified bet: the suggestion algorithm has never seen a real song. PRD §18 #5 (≥70% acceptance) is unfalsifiable until Nic runs Haze through it.
- Mood-tag taxonomy (`SECTION_MOOD_HINTS` in `suggest.py:36-43`) is hardcoded English words; will collide with whatever ChatGPT actually emits. Defer the controlled vocabulary to v1.1 — don't pre-design without real data.
- Highest-leverage next move: run Haze through the tool end-to-end. Everything else in the open backlog is speculation or polish.

**Staff engineer** — verdict: **sign off, with one fix first.**
- Top fix: `Project.brand_kit_path` was dead config — only `doctor` consulted it; `_load_context` ignored it entirely. Either wire or remove.
- Mutable defaults on pydantic models (`Scene.frames = {"start": [], "end": []}`, `concepts: list[str] = []`, etc.) — pydantic v2 deep-copies at validation but the idiom is a footgun. Switch to `Field(default_factory=...)`.
- Substring bug in `score_clip_for_section` (`suggest.py:131`): `"chorus"` matches `"pre-chorus"` via `kind in fit_lower`. Use section-kind equality.
- `run_review_moment` prints `[END  ] None` because `seg.image` is now always `None` after D3.6 removed the hardcoded path.
- Half-wired `--lyrics-aware` flag on `analyze` — does nothing. Either implement or remove.
- Performance: `list_scenes` re-parses everything per command, doubled by `resolve_scene_id`. Fine at v1 scale.
- Architecture and Phase D hardening are appropriate; tests are in the right places.

**Onboarding (fresh user)** — verdict: 5-step cold start works as written.
- `status` `Next:` line walks a fresh user through the entire flow without needing other docs.
- `prompts <scene>` literally inlines the reference-image upload instruction — answers the question at the moment of need.
- `render-moment` v1 stub is clearly flagged in CLI but **not in README**.
- `SOLYPSIZM_HOME` undocumented in README — only learned from `doctor --global` output.
- Brand-kit relationship between repo and `~/solypsizm/` was unclear.
- Backup story silent — no doc tells the freelancer where their work lives or what to back up vs commit.

### Fixes shipped in response (this commit)

Acted on the items that made sense for a v1 first cut:

1. **`_load_context` now uses `project.brand_kit_path`** (resolved relative to project) with fallback to the canonical `~/solypsizm/brand-kit.json`. The field is no longer dead config.
2. **All mutable defaults converted** to `Field(default_factory=...)` across `Scene`, `Project`, `Concept`, `Moment`, `BrandKit`, `Aesthetic`, `VeoPromptConstants`, `SongAnalysis`.
3. **Substring bug fixed**: `score_clip_for_section` now compares `section_kind(fit)` to `kind` exactly, so `"chorus"` no longer matches `"pre-chorus"`.
4. **`[END  ] None` cosmetic fix**: review-moment prints `(default end card)` when no image is configured.
5. **`--lyrics-aware` flag removed** — it did nothing; was rotting on the CLI.
6. **README "Where your work lives" section** explaining `~/solypsizm/`, `SOLYPSIZM_HOME`, the repo-vs-home brand-kit split, backup, and don't-commit. Plus platform note (macOS primary, Linux secondary) and a render-handoff note.

### Deliberately deferred (v1.1 scope)

Per the user's "first cut, can expand later" framing — these are real but not v1-blocking:

- **Mood-tag controlled vocabulary** (PM #2). Per the PM's recommendation: don't predesign without seeing what ChatGPT actually emits on Haze. Land in v1.1 once there's real data.
- **D3 spec completeness** (transitions, lyric overlays, hook_clip_id, lufs/fps/safe_zones). Consumed by the Variant Builder, which doesn't exist. Ship with that tool.
- **Stderr warnings on broken JSON files**: `list_concepts` / `list_scenes` silently skip `except Exception: continue`. `doctor` catches the symptom (missing references) but not the cause. Add a stderr warning in v1.1.
- **Hash-index optimization**: `_find_existing_hash` walks every scene per import. Fine at ~30 scenes; bring up `.state/hashes.json` if it gets slow.
- **`_select_cut_points` degenerate-section test** + `Scene.frames` mutable-default isolation test. Defensive, not load-bearing.
- **Pydantic upper-bound version pinning** (`<3`). Add when cutting v1 release.
- **Strategy simplification**: PM suggested cutting to one strategy. Keeping all three since Nic explicitly wanted choice ("depends on the song and moment").

### Test suite

59/59 green, unchanged.

### Outcome

The PM's "single highest-leverage next move" is **run the tool on Haze**. That's not something I can do; only Nic can. The system is in the best shape I can put it in without that real data. Suggesting that's the next thing Nic does.
