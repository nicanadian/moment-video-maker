# moment-video-maker

Solypsizm Moment Studio — a Python CLI that organizes the workflow of producing short-form "moment" videos for Solypsizm music releases. Concepts → scenes → ChatGPT/Veo prompts → frame & clip library → music-aware edit suggestions, all linked in one project per song.

The tool does **not** generate frames or clips itself. It scaffolds prompts, holds durable state across ChatGPT sessions, and tells the artist what's still missing. Frame/clip generation happens in ChatGPT and Google Flow Labs (Veo 3); final rendering is handed off to the separate Variant Builder.

See `ref-docs/Solypsizm Moment Studio - PRD.md` for the full spec, and `docs/projects/01-moment-studio-v1.md` for the build plan.

## Status

v0.1.0 — Phases A + B + C + D landed. End-to-end workflow runs; rendering hands off to a Variant Builder that doesn't exist yet. Test suite at 59/59.

## Cold start

```sh
# 1. Install
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,audio]"     # audio extras pull in librosa for `analyze`

# 2. Install the brand kit into ~/solypsizm/
solypsizm bootstrap-brand-kit --source ./brand-kit.json

# 3. Sanity-check the environment (binaries, librosa, brand kit)
solypsizm doctor --global

# 4. Create your first project
solypsizm new haze \
  --song-title "Haze over the Horizon" \
  --lyrics ./haze-lyrics.txt \
  --audio ./haze-master.wav

# 5. Let the tool tell you what to do next
solypsizm --project haze status
```

The `Next:` line in `status` names the concrete next command — start there and follow the trail through `brainstorm` → `import-concepts` → `pick-concept` → `scenes` → `import-scenes` → `prompts <scene>` → `import-frame` / `import-clip` → `analyze` → `suggest-moments` → `review-moment`.

## Install variations

```sh
pip install -e ".[dev]"           # core + tests, no audio
pip install -e ".[dev,audio]"     # adds librosa + pydub for `analyze`
pip install -e ".[dev,api]"       # adds OpenAI client (planned for v2)
```

## Where your work lives

The repo holds the **tool** + the **brand kit source**. Your **project state** lives outside the repo, under `~/solypsizm/`:

```
~/solypsizm/                   # default; override with SOLYPSIZM_HOME
  brand-kit.json               # mirrored from this repo by `bootstrap-brand-kit`
  character-reference/         # canonical avatar PNGs (front, etc.)
  haze/                        # one folder per song
    project.json
    lyrics.txt
    audio/master.{wav,mp3,...}
    concepts/, scenes/, moments/
    .state/log.jsonl
```

- **Back up `~/solypsizm/`** — that's where your concepts, scenes, prompts, and moment specs live. The repo doesn't carry it.
- **Don't commit `~/solypsizm/`** — it's outside the repo on purpose.
- **Brand kit edits**: change `brand-kit.json` in this repo (it's source-of-truth), then `solypsizm bootstrap-brand-kit --source ./brand-kit.json --force` to refresh `~/solypsizm/brand-kit.json`. The CLI reads from `~/solypsizm/`, not the repo.
- **Override the home** via `export SOLYPSIZM_HOME=/path/to/throwaway` (useful for testing).

## Platform

- **macOS** (primary): everything works. Clipboard via `pbcopy`, audio playback via `ffplay`, `review-clips` opens Finder.
- **Linux** (secondary): core commands work; `pbcopy`/`open` are macOS-only and silently no-op there.

## Render handoff

`solypsizm render-moment <id>` and `render-all` print the spec path with exit zero and a stderr note. **No actual rendering happens yet** — that's the separate Variant Builder tool (PRD §20). The spec on disk is the artifact downstream consumes when that ships.

## Daily-use tips

- Set `SOLYPSIZM_PROJECT=haze` (or pass `--project haze`) to operate on a project from any directory.
- `solypsizm pick-scene <id>` sets a current scene; `--scene` is then optional on `import-frame` / `import-clip` / `prompts`.
- IDs accept fuzzy matching: `solypsizm pick-concept watch` resolves to `concept-01-abandoned-watchtower-dawn`.
- `solypsizm log --tail 20` for recent ops; `--event clip_imported` filters; `--all` dumps everything.

## Repo layout

- `src/solypsizm_moment_studio/` — Python package.
- `brand-kit.json` + `character-reference/` — locked Solypsizm character spec and the canonical reference PNG. Auto-injected into every generated prompt; `bootstrap-brand-kit` mirrors both into `~/solypsizm/`.
- `ref-docs/` — source PRD and brand-kit docx.
- `docs/projects/` — one markdown file per feature/initiative.
- `docs/prompts/` — markdown logs of AI ↔ user conversations driving the work.
