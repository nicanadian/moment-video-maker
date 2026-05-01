# Phase A implementation

**Date:** 2026-05-01
**Model:** Claude Opus 4.7

## User
> yep [start Phase A implementation]

## Assistant
Built Phase A end-to-end and verified with a full manual smoke test.

### What landed

**Models** (`src/solypsizm_moment_studio/models/`) — pydantic v2 models matching PRD §8 schemas:
- `BrandKit` (with `CharacterSpec`, `Aesthetic`, `SongTheme`)
- `Project`
- `Concept`
- `Scene` (with `FramePrompts`, `Frame`, `ClipTake`)

All use `extra="allow"` so we don't lose data we don't model.

**State** (`src/solypsizm_moment_studio/state/`):
- `paths.py` — `SOLYPSIZM_HOME` env var (default `~/solypsizm`), project root resolution by walking up from CWD, `find_project_root()`, `require_project_root()`.
- `io.py` — atomic JSON writes (write `.tmp`, rename), typed `load_/save_` helpers for project/concept/scene, `list_concepts()`, `list_scenes()`, `append_log()` for `.state/log.jsonl`.

**Prompts** (`src/solypsizm_moment_studio/prompts/`):
- `templates.py` — five generators that all auto-inject the brand kit character spec, aesthetic, and song theme: `brainstorm_prompt`, `scenes_prompt`, `start_frame_prompt`, `end_frame_prompt`, `veo_motion_prompt`, plus `scene_prompts_markdown` that combines the three frame/motion prompts into the `scene-NN-prompts.md` artifact.
- `parsing.py` — tolerant parser for ChatGPT responses. Strips ```json fences, swallows leading prose, balances braces with string-aware skipping (so `{` inside string values doesn't unbalance the count), unwraps `{ "concepts": [...] }` and `{ "scenes": [...] }` envelopes, wraps a single object as a one-item list, raises `ParseError` on unrecoverable input. 11 unit tests in `tests/test_parsing.py` cover plain arrays, fenced/labeled and unlabeled, leading prose, wrapped envelopes, braces-in-strings, single-object, garbage, and empty arrays.

**Commands** (`src/solypsizm_moment_studio/commands/`) — implementations split out from `cli.py`:
- `brand_kit.py` — `bootstrap-brand-kit` validates the source JSON against the BrandKit model before installing, refuses overwrite without `--force`, errors clearly if asked to read a `.docx` (deferred).
- `project.py` — `new` (creates folder layout, copies lyrics + audio preserving extension, writes project.json), `status` (one-screen dashboard), `open` (prints path).
- `concepts.py` — `brainstorm` (emit ChatGPT prompt with lyrics inlined and brand kit injected, `--copy` shells to `pbcopy`), `import-concepts` (parses, writes `concepts/concept-NN-<slug>.json`, on failure dumps raw to `.state/last-import.txt`), `list-concepts`, `pick-concept` (marks current, flips `draft` → `in_progress`), `rate-concept`.
- `scenes.py` — `scenes` (emit prompt for the current concept), `import-scenes` (parses, writes `scenes/<concept>/<scene>.json`), `list-scenes` (grouped by concept), `prompts <scene-id>` (writes `scene-NN-prompts.md`, populates `scene.prompts`, optional `--copy` steps through the three prompts on the clipboard).

**CLI** (`cli.py`) — replaced Phase A stubs with delegations; Phase B/C/D commands still raise "not implemented yet — Phase X" as bookmarks.

**Build/test setup**: created a `.venv/` with Python 3.11, `pip install -e .[dev]` works clean, `solypsizm --help` lists every command, `pytest -q` passes all 11 parser tests.

### End-to-end smoke test

Against a temp `SOLYPSIZM_HOME`:

```
bootstrap-brand-kit --source ./brand-kit.json
new haze --song-title "Haze over the Horizon" --lyrics ... --audio ...
import-concepts /tmp/concepts-resp.json   # 1 concept written
pick-concept concept-01-abandoned-watchtower-at-dawn
import-scenes /tmp/scenes-resp.txt        # 2 scenes written (response had ```json fences + leading prose)
prompts scene-01-wide-approach            # scene-01-wide-approach-prompts.md written
status                                    # dashboard reflects 1 concept / 2 scenes
```

The emitted `scene-NN-prompts.md` contains the full locked character spec block, the scene's environment/camera/lighting, and the watermark disclaimer — zero hand-typing of brand context required, which is the core PRD promise (§11).

### What's deliberately deferred

- `bootstrap-brand-kit` from `.docx` directly. Errors clearly. Workaround: edit `brand-kit.json` by hand. Will revisit if Nic's editing flow makes this painful.
- `--api` mode for direct OpenAI calls (PRD §12.2). Deferred to Phase D.
- All Phase B/C/D commands (`import-frame`, `import-clip`, `analyze`, `suggest-moments`, `render-*`, `trace`, `doctor`, `log`).

### Files

```
src/solypsizm_moment_studio/
  __init__.py         (existing)
  __main__.py         (existing)
  cli.py              (rewritten — delegates to commands/)
  utils.py            (new — now_iso, slugify, clipboard_copy)
  models/             (new — 4 model files + __init__)
  state/              (new — paths.py, io.py, __init__)
  prompts/            (new — templates.py, parsing.py, __init__)
  commands/           (new — brand_kit.py, project.py, concepts.py, scenes.py, __init__)
tests/
  __init__.py
  test_parsing.py     (11 tests, all green)
```
