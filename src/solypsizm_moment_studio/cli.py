import os

import click

from solypsizm_moment_studio import __version__
from solypsizm_moment_studio.commands import api as cmd_api
from solypsizm_moment_studio.commands import audio as cmd_audio
from solypsizm_moment_studio.commands import benchmark as cmd_benchmark
from solypsizm_moment_studio.commands import brand_kit as cmd_brand_kit
from solypsizm_moment_studio.commands import concepts as cmd_concepts
from solypsizm_moment_studio.commands import diagnostic as cmd_diagnostic
from solypsizm_moment_studio.commands import media as cmd_media
from solypsizm_moment_studio.commands import moments as cmd_moments
from solypsizm_moment_studio.commands import project as cmd_project
from solypsizm_moment_studio.commands import scenes as cmd_scenes


@click.group(help="Solypsizm Moment Studio — organize concepts, scenes, prompts, clips, and edits.")
@click.version_option(__version__, prog_name="solypsizm")
@click.option(
    "--project",
    "project_slug",
    metavar="SLUG",
    help="Operate on this project regardless of CWD. Equivalent to setting SOLYPSIZM_PROJECT.",
)
def main(project_slug: str | None) -> None:
    if project_slug:
        os.environ["SOLYPSIZM_PROJECT"] = project_slug


# --- Project lifecycle ------------------------------------------------------

@main.command("new", help="Create a new project for a song.")
@click.argument("slug")
@click.option("--song-title", required=True)
@click.option("--lyrics", type=click.Path(exists=True, dir_okay=False), required=True)
@click.option("--audio", type=click.Path(exists=True, dir_okay=False), required=True)
def new_cmd(slug: str, song_title: str, lyrics: str, audio: str) -> None:
    cmd_project.run_new(slug, song_title, lyrics, audio)


@main.command("status", help="Print project dashboard.")
@click.argument("slug", required=False)
def status_cmd(slug: str | None) -> None:
    cmd_project.run_status(slug)


@main.command("open", help="Print project path and summary.")
@click.argument("slug")
def open_cmd(slug: str) -> None:
    cmd_project.run_open(slug)


# --- Brand kit --------------------------------------------------------------

@main.command("bootstrap-brand-kit", help="Install brand-kit.json into ~/solypsizm/.")
@click.option("--source", type=click.Path(exists=True, dir_okay=False))
@click.option("--out", type=click.Path(dir_okay=False))
@click.option("--force", is_flag=True, help="Overwrite an existing brand kit.")
def bootstrap_brand_kit_cmd(source: str | None, out: str | None, force: bool) -> None:
    cmd_brand_kit.run(source, out, force)


# --- Concepts ---------------------------------------------------------------

@main.command("brainstorm", help="Emit a ChatGPT brainstorm prompt for the current project.")
@click.option("--count", default=5, show_default=True)
@click.option("--copy/--no-copy", default=True)
@click.option("--api", is_flag=True, help="Run the API call directly instead of paste-back.")
@click.option("--model", help="Override the default text model (e.g. openrouter:openai/gpt-5).")
def brainstorm_cmd(count: int, copy: bool, api: bool, model: str | None) -> None:
    cmd_concepts.run_brainstorm(count, copy, api, model)


@main.command("import-concepts", help="Parse a ChatGPT brainstorm response into concept JSONs.")
@click.argument("input", type=click.File("r"))
def import_concepts_cmd(input) -> None:
    cmd_concepts.run_import_concepts(input)


@main.command("list-concepts")
def list_concepts_cmd() -> None:
    cmd_concepts.run_list_concepts()


@main.command("pick-concept")
@click.argument("concept_id")
def pick_concept_cmd(concept_id: str) -> None:
    cmd_concepts.run_pick_concept(concept_id)


@main.command("rate-concept")
@click.argument("concept_id")
@click.option("--rating", type=click.IntRange(1, 5), required=True)
@click.option("--notes", default="")
def rate_concept_cmd(concept_id: str, rating: int, notes: str) -> None:
    cmd_concepts.run_rate_concept(concept_id, rating, notes)


# --- Scenes -----------------------------------------------------------------

@main.command("pick-scene", help="Set the current scene (used when --scene is omitted).")
@click.argument("scene_id")
def pick_scene_cmd(scene_id: str) -> None:
    cmd_scenes.run_pick_scene(scene_id)


@main.command("scenes", help="Emit ChatGPT scene-breakdown prompt for the current concept.")
@click.option("--copy/--no-copy", default=True)
def scenes_cmd(copy: bool) -> None:
    cmd_scenes.run_scenes(copy)


@main.command("import-scenes")
@click.argument("input", type=click.File("r"))
def import_scenes_cmd(input) -> None:
    cmd_scenes.run_import_scenes(input)


@main.command("list-scenes")
def list_scenes_cmd() -> None:
    cmd_scenes.run_list_scenes()


@main.command("prompts", help="Emit the 3 ready-to-paste prompts for a scene (current if omitted).")
@click.argument("scene_id", required=False)
@click.option("--copy/--no-copy", default=False, help="Step through prompts via clipboard.")
def prompts_cmd(scene_id: str | None, copy: bool) -> None:
    cmd_scenes.run_prompts(scene_id, copy)


# --- Frames and clips -------------------------------------------------------

@main.command("import-frame", help="Import a frame PNG into a scene (copies by default).")
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option("--scene", "scene_id", help="Scene id (defaults to current scene if set).")
@click.option("--type", "frame_type", type=click.Choice(["start", "end"]), required=True)
@click.option("--move", is_flag=True, help="Move the source file instead of copying.")
def import_frame_cmd(file: str, scene_id: str, frame_type: str, move: bool) -> None:
    cmd_media.run_import_frame(file, scene_id, frame_type, move)


@main.command("select-frame", help="Mark one frame as the selected start/end for a scene.")
@click.option("--scene", "scene_id", help="Scene id (defaults to current scene if set).")
@click.option("--type", "frame_type", type=click.Choice(["start", "end"]), required=True)
@click.argument("filename")
def select_frame_cmd(scene_id: str, frame_type: str, filename: str) -> None:
    cmd_media.run_select_frame(scene_id, frame_type, filename)


@main.command("import-clip", help="Import a Veo output clip into a scene (copies by default).")
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option("--scene", "scene_id", help="Scene id (defaults to current scene if set).")
@click.option("--rating", type=click.IntRange(1, 5))
@click.option("--notes", default="")
@click.option("--move", is_flag=True, help="Move the source file instead of copying.")
def import_clip_cmd(
    file: str, scene_id: str, rating: int | None, notes: str, move: bool
) -> None:
    cmd_media.run_import_clip(file, scene_id, rating, notes, move)


@main.command("select-clip", help="Mark one clip as the chosen take for a scene.")
@click.option("--scene", "scene_id", help="Scene id (defaults to current scene if set).")
@click.argument("filename")
def select_clip_cmd(scene_id: str, filename: str) -> None:
    cmd_media.run_select_clip(scene_id, filename)


@main.command("review-clips", help="Open a scene's clips folder + show ratings table.")
@click.argument("scene_id")
def review_clips_cmd(scene_id: str) -> None:
    cmd_media.run_review_clips(scene_id)


# --- Song analysis ----------------------------------------------------------

@main.command("analyze", help="Run librosa song analysis → audio/song-analysis.json.")
@click.option("--force", is_flag=True, help="Regenerate (shows a diff and confirms before overwriting).")
def analyze_cmd(force: bool) -> None:
    cmd_audio.run_analyze(force)


@main.command("sections", help="Print the detected sections table.")
def sections_cmd() -> None:
    cmd_audio.run_sections()


# --- Diagnostics ------------------------------------------------------------

# --- API mode (v2) ----------------------------------------------------------

@main.group("secrets", help="Manage provider credentials (OpenAI / Gemini / OpenRouter).")
def secrets_group() -> None:
    pass


@secrets_group.command("status")
def secrets_status_cmd() -> None:
    cmd_api.run_secrets_status()


@secrets_group.command("login", help="OAuth login (currently only OpenAI).")
@click.argument("provider", type=click.Choice(["openai"]))
def secrets_login_cmd(provider: str) -> None:
    if provider == "openai":
        cmd_api.run_secrets_login_openai()


@secrets_group.command("set", help="Set an API key for a provider.")
@click.argument("provider", type=click.Choice(["gemini", "openrouter", "openai"]))
def secrets_set_cmd(provider: str) -> None:
    cmd_api.run_secrets_set(provider)


@secrets_group.command("remove", help="Remove a stored API key.")
@click.argument("provider", type=click.Choice(["gemini", "openrouter", "openai"]))
def secrets_remove_cmd(provider: str) -> None:
    cmd_api.run_secrets_remove(provider)


@main.command("benchmark", help="Run an image/video model benchmark with VLM-judge scoring.")
@click.argument("prompt_set")
@click.option("--model", "models", multiple=True, required=True,
              help="Model spec, e.g. gemini:imagen-4 (repeatable).")
@click.option("--takes", default=1, show_default=True, type=int,
              help="Independent generations per model (independent seeds).")
@click.option("--judge", default="gemini-2.5-flash", show_default=True,
              help="Gemini model to use for scoring.")
@click.option("--budget", type=float, default=None,
              help="Per-run cost cap in USD (independent of daily cap).")
def benchmark_cmd(prompt_set: str, models: tuple[str, ...], takes: int, judge: str, budget: float | None) -> None:
    cmd_benchmark.run_benchmark(prompt_set, models, takes, judge, budget)


@main.command("budget", help="Show today's API spend against the daily cap.")
def budget_cmd() -> None:
    cmd_api.run_budget_show()


@main.command("cache-prune", help="Drop cached API artifacts older than N days (per-project).")
@click.option("--older-than", default=30, show_default=True, type=int)
def cache_prune_cmd(older_than: int) -> None:
    cmd_api.run_cache_prune(older_than)


# --- Diagnostics ------------------------------------------------------------

@main.command("doctor", help="Validate project structure, file references, and brand kit.")
@click.option("--global", "check_global", is_flag=True, help="Check CLI environment (binaries + brand kit) without a project.")
def doctor_cmd(check_global: bool) -> None:
    cmd_diagnostic.run_doctor(check_global=check_global)


@main.command("log", help="Print the project's operation log.")
@click.option("--tail", default=50, type=int, show_default=True, help="Show last N lines.")
@click.option("--all", "show_all", is_flag=True, help="Show every logged event.")
@click.option("--event", help="Filter to a single event type (e.g. clip_imported).")
@click.option("--since", help="Only show events at or after this ISO timestamp.")
def log_cmd(tail: int, show_all: bool, event: str | None, since: str | None) -> None:
    cmd_diagnostic.run_log(tail, show_all, event, since)


# --- Moments ----------------------------------------------------------------

@main.command("suggest-moments", help="Generate moment edit specs from clips + sections.")
@click.option("--count", default=9, show_default=True)
@click.option(
    "--strategy",
    type=click.Choice(["tension_release", "section_focus", "cold_hook"]),
    default="section_focus",
    show_default=True,
    help="section_focus = even diversity. tension_release = low→high build. cold_hook = climax-first.",
)
def suggest_moments_cmd(count: int, strategy: str) -> None:
    cmd_moments.run_suggest_moments(count, strategy)


@main.command("list-moments", help="List all moment specs and their status.")
def list_moments_cmd() -> None:
    cmd_moments.run_list_moments()


@main.command("review-moment", help="Review a moment, hear its audio range, approve or reject.")
@click.argument("moment_id")
@click.option("--approve", is_flag=True, help="Skip the prompt and approve.")
@click.option("--reject", is_flag=True, help="Skip the prompt and reject.")
def review_moment_cmd(moment_id: str, approve: bool, reject: bool) -> None:
    cmd_moments.run_review_moment(moment_id, approve, reject)


@main.command("render-moment", help="(Pending Variant Builder) hand off an approved moment to render.")
@click.argument("moment_id")
def render_moment_cmd(moment_id: str) -> None:
    cmd_moments.run_render_moment(moment_id)


@main.command("render-all", help="(Pending Variant Builder) render every approved moment.")
def render_all_cmd() -> None:
    cmd_moments.run_render_all()


@main.command("trace", help="Find every moment that uses a given clip.")
@click.argument("clip")
def trace_cmd(clip: str) -> None:
    cmd_moments.run_trace(clip)


if __name__ == "__main__":
    main()
