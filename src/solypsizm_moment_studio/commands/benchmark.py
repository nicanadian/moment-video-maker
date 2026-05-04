"""solypsizm benchmark <prompt-set> command."""

from __future__ import annotations

from pathlib import Path

import click

from solypsizm_moment_studio.benchmark import load_prompt_set, run


def run_benchmark(
    prompt_set_name: str,
    models: tuple[str, ...],
    takes: int,
    judge: str,
    budget: float | None,
) -> None:
    if not models:
        raise click.ClickException(
            "Pass at least one --model. Example: "
            "--model gemini:imagen-4 --model openai:gpt-image-1"
        )

    repo_prompt_dir = Path(__file__).parent.parent.parent.parent / "benchmarks" / "prompt-sets"
    try:
        prompt_set = load_prompt_set(prompt_set_name, search_dir=repo_prompt_dir)
    except FileNotFoundError as e:
        raise click.ClickException(str(e)) from e

    click.echo(f"Running benchmark '{prompt_set.name}' (modality: {prompt_set.modality})...")
    click.echo(f"  models: {list(models)}")
    click.echo(f"  takes:  {takes}")
    click.echo(f"  judge:  {judge}")
    if budget:
        click.echo(f"  budget: ${budget:.2f}")
    click.echo("")

    out_dir = run(
        prompt_set=prompt_set,
        specs=list(models),
        takes=takes,
        judge_model=judge,
        budget_usd=budget,
    )

    click.echo(f"\n✓ Run complete: {out_dir}")
    click.echo(f"  manifest.json + report.md + per-spec artifacts")
    click.echo(f"\n--- report.md ---\n")
    click.echo((out_dir / "report.md").read_text(encoding="utf-8"))
