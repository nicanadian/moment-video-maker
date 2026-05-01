# moment-video-maker

Solypsizm Moment Studio — a Python CLI that organizes the workflow of producing short-form "moment" videos for Solypsizm music releases. Concepts → scenes → ChatGPT/Veo prompts → frame & clip library → music-aware edit suggestions, all linked in one project per song.

The tool does **not** generate frames or clips itself. It scaffolds prompts, holds durable state across ChatGPT sessions, and tells the artist what's still missing. Frame/clip generation happens in ChatGPT and Google Flow Labs (Veo 3); final rendering is handed off to the separate Variant Builder.

See `ref-docs/Solypsizm Moment Studio - PRD.md` for the full spec, and `docs/projects/01-moment-studio-v1.md` for the build plan.

## Status

v0.1.0 — scaffolding only. CLI surface defined; commands raise "not implemented yet". Phase A (prompt scaffolding) is the next build target.

## Install (dev)

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
solypsizm --help
```

Optional extras:

```sh
pip install -e ".[dev,audio]"   # adds librosa + pydub for `analyze`
pip install -e ".[dev,api]"     # adds OpenAI client for --api mode
```

## Repo layout

- `src/solypsizm_moment_studio/` — Python package.
- `brand-kit.json` — locked Solypsizm character spec, palette, typography, per-song themes. Auto-injected into every generated prompt.
- `ref-docs/` — source PRD and brand-kit docx.
- `docs/projects/` — one markdown file per feature/initiative.
- `docs/prompts/` — markdown logs of AI ↔ user conversations driving the work.
