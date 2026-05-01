import click

from solypsizm_moment_studio import __version__


@click.group(help="Solypsizm Moment Studio — organize concepts, scenes, prompts, clips, and edits.")
@click.version_option(__version__, prog_name="solypsizm")
def main() -> None:
    pass


@main.command("new", help="Create a new project for a song.")
@click.argument("slug")
@click.option("--song-title", required=True, help="Human-readable song title.")
@click.option("--lyrics", type=click.Path(exists=True, dir_okay=False), required=True)
@click.option("--audio", type=click.Path(exists=True, dir_okay=False), required=True)
def new_cmd(slug: str, song_title: str, lyrics: str, audio: str) -> None:
    raise click.ClickException("not implemented yet — Phase A")


@main.command("status", help="Print project dashboard.")
@click.argument("slug", required=False)
def status_cmd(slug: str | None) -> None:
    raise click.ClickException("not implemented yet — Phase A")


@main.command("open", help="cd-friendly summary of a project.")
@click.argument("slug")
def open_cmd(slug: str) -> None:
    raise click.ClickException("not implemented yet — Phase A")


@main.command("bootstrap-brand-kit", help="Produce brand-kit.json from the docx source.")
@click.option("--source", type=click.Path(exists=True, dir_okay=False), required=True)
@click.option("--out", type=click.Path(dir_okay=False), default="brand-kit.json")
def bootstrap_brand_kit_cmd(source: str, out: str) -> None:
    raise click.ClickException("not implemented yet — Phase A")


@main.command("brainstorm", help="Emit ChatGPT brainstorm prompt for the current project.")
@click.option("--count", default=5, show_default=True, help="Number of concept ideas to request.")
@click.option("--copy/--no-copy", default=True, help="Copy to macOS clipboard.")
def brainstorm_cmd(count: int, copy: bool) -> None:
    raise click.ClickException("not implemented yet — Phase A")


@main.command("import-concepts", help="Parse a ChatGPT brainstorm response into concept JSONs.")
@click.argument("input", type=click.File("r"))
def import_concepts_cmd(input) -> None:
    raise click.ClickException("not implemented yet — Phase A")


@main.command("list-concepts")
def list_concepts_cmd() -> None:
    raise click.ClickException("not implemented yet — Phase A")


@main.command("pick-concept")
@click.argument("concept_id")
def pick_concept_cmd(concept_id: str) -> None:
    raise click.ClickException("not implemented yet — Phase A")


@main.command("rate-concept")
@click.argument("concept_id")
@click.option("--rating", type=click.IntRange(1, 5), required=True)
@click.option("--notes", default="")
def rate_concept_cmd(concept_id: str, rating: int, notes: str) -> None:
    raise click.ClickException("not implemented yet — Phase A")


@main.command("scenes", help="Emit ChatGPT scene-breakdown prompt for the current concept.")
@click.option("--copy/--no-copy", default=True)
def scenes_cmd(copy: bool) -> None:
    raise click.ClickException("not implemented yet — Phase A")


@main.command("import-scenes")
@click.argument("input", type=click.File("r"))
def import_scenes_cmd(input) -> None:
    raise click.ClickException("not implemented yet — Phase A")


@main.command("list-scenes")
def list_scenes_cmd() -> None:
    raise click.ClickException("not implemented yet — Phase A")


@main.command("prompts", help="Emit the 3 ready-to-paste prompts for a scene.")
@click.argument("scene_id")
@click.option("--copy/--no-copy", default=False, help="Step through prompts via clipboard.")
def prompts_cmd(scene_id: str, copy: bool) -> None:
    raise click.ClickException("not implemented yet — Phase A")


@main.command("import-frame")
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option("--scene", "scene_id", required=True)
@click.option("--type", "frame_type", type=click.Choice(["start", "end"]), required=True)
def import_frame_cmd(file: str, scene_id: str, frame_type: str) -> None:
    raise click.ClickException("not implemented yet — Phase B")


@main.command("select-frame")
@click.option("--scene", "scene_id", required=True)
@click.option("--type", "frame_type", type=click.Choice(["start", "end"]), required=True)
@click.argument("filename")
def select_frame_cmd(scene_id: str, frame_type: str, filename: str) -> None:
    raise click.ClickException("not implemented yet — Phase B")


@main.command("import-clip")
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option("--scene", "scene_id", required=True)
@click.option("--rating", type=click.IntRange(1, 5))
@click.option("--notes", default="")
def import_clip_cmd(file: str, scene_id: str, rating: int | None, notes: str) -> None:
    raise click.ClickException("not implemented yet — Phase B")


@main.command("select-clip")
@click.option("--scene", "scene_id", required=True)
@click.argument("filename")
def select_clip_cmd(scene_id: str, filename: str) -> None:
    raise click.ClickException("not implemented yet — Phase B")


@main.command("review-clips")
@click.argument("scene_id")
def review_clips_cmd(scene_id: str) -> None:
    raise click.ClickException("not implemented yet — Phase B")


@main.command("analyze", help="Run librosa-based song analysis.")
@click.option("--force", is_flag=True, help="Overwrite manual edits to song-analysis.json.")
@click.option("--lyrics-aware", is_flag=True)
def analyze_cmd(force: bool, lyrics_aware: bool) -> None:
    raise click.ClickException("not implemented yet — Phase B")


@main.command("sections")
def sections_cmd() -> None:
    raise click.ClickException("not implemented yet — Phase B")


@main.command("suggest-moments")
@click.option("--count", default=9, show_default=True)
@click.option("--strategy", type=click.Choice(["tension_release", "section_focus"]))
def suggest_moments_cmd(count: int, strategy: str | None) -> None:
    raise click.ClickException("not implemented yet — Phase C")


@main.command("review-moment")
@click.argument("moment_id")
def review_moment_cmd(moment_id: str) -> None:
    raise click.ClickException("not implemented yet — Phase C")


@main.command("render-moment")
@click.argument("moment_id")
def render_moment_cmd(moment_id: str) -> None:
    raise click.ClickException("not implemented yet — Phase C")


@main.command("render-all")
def render_all_cmd() -> None:
    raise click.ClickException("not implemented yet — Phase C")


@main.command("trace", help="Show which moments use a given clip.")
@click.argument("clip")
def trace_cmd(clip: str) -> None:
    raise click.ClickException("not implemented yet — Phase C")


@main.command("doctor", help="Validate project structure and references.")
def doctor_cmd() -> None:
    raise click.ClickException("not implemented yet — Phase B")


@main.command("log", help="Tail the project operation log.")
def log_cmd() -> None:
    raise click.ClickException("not implemented yet — Phase B")


if __name__ == "__main__":
    main()
