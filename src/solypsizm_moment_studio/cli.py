import click

from solypsizm_moment_studio import __version__
from solypsizm_moment_studio.commands import brand_kit as cmd_brand_kit
from solypsizm_moment_studio.commands import concepts as cmd_concepts
from solypsizm_moment_studio.commands import project as cmd_project
from solypsizm_moment_studio.commands import scenes as cmd_scenes


@click.group(help="Solypsizm Moment Studio — organize concepts, scenes, prompts, clips, and edits.")
@click.version_option(__version__, prog_name="solypsizm")
def main() -> None:
    pass


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
def brainstorm_cmd(count: int, copy: bool) -> None:
    cmd_concepts.run_brainstorm(count, copy)


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


@main.command("prompts", help="Emit the 3 ready-to-paste prompts for a scene.")
@click.argument("scene_id")
@click.option("--copy/--no-copy", default=False, help="Step through prompts via clipboard.")
def prompts_cmd(scene_id: str, copy: bool) -> None:
    cmd_scenes.run_prompts(scene_id, copy)


# --- Phase B/C/D placeholders (still stubbed) -------------------------------

def _not_yet(phase: str) -> None:
    raise click.ClickException(f"not implemented yet — Phase {phase}")


@main.command("import-frame")
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option("--scene", "scene_id", required=True)
@click.option("--type", "frame_type", type=click.Choice(["start", "end"]), required=True)
def import_frame_cmd(file, scene_id, frame_type):
    _not_yet("B")


@main.command("select-frame")
@click.option("--scene", "scene_id", required=True)
@click.option("--type", "frame_type", type=click.Choice(["start", "end"]), required=True)
@click.argument("filename")
def select_frame_cmd(scene_id, frame_type, filename):
    _not_yet("B")


@main.command("import-clip")
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option("--scene", "scene_id", required=True)
@click.option("--rating", type=click.IntRange(1, 5))
@click.option("--notes", default="")
def import_clip_cmd(file, scene_id, rating, notes):
    _not_yet("B")


@main.command("select-clip")
@click.option("--scene", "scene_id", required=True)
@click.argument("filename")
def select_clip_cmd(scene_id, filename):
    _not_yet("B")


@main.command("review-clips")
@click.argument("scene_id")
def review_clips_cmd(scene_id):
    _not_yet("B")


@main.command("analyze")
@click.option("--force", is_flag=True)
@click.option("--lyrics-aware", is_flag=True)
def analyze_cmd(force, lyrics_aware):
    _not_yet("B")


@main.command("sections")
def sections_cmd():
    _not_yet("B")


@main.command("suggest-moments")
@click.option("--count", default=9, show_default=True)
@click.option("--strategy", type=click.Choice(["tension_release", "section_focus"]))
def suggest_moments_cmd(count, strategy):
    _not_yet("C")


@main.command("review-moment")
@click.argument("moment_id")
def review_moment_cmd(moment_id):
    _not_yet("C")


@main.command("render-moment")
@click.argument("moment_id")
def render_moment_cmd(moment_id):
    _not_yet("C")


@main.command("render-all")
def render_all_cmd():
    _not_yet("C")


@main.command("trace")
@click.argument("clip")
def trace_cmd(clip):
    _not_yet("C")


@main.command("doctor")
def doctor_cmd():
    _not_yet("B")


@main.command("log")
def log_cmd():
    _not_yet("B")


if __name__ == "__main__":
    main()
