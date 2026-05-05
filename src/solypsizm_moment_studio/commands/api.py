"""Top-level commands for managing API mode: secrets, budget, cache."""

from __future__ import annotations

import shutil
import subprocess

import click

from solypsizm_moment_studio.providers import cache as _cache
from solypsizm_moment_studio.providers import cost, secrets
from solypsizm_moment_studio.state import find_project_root


def run_secrets_status() -> None:
    out = secrets.status()
    rows = [(k, v) for k, v in sorted(out.items())]
    click.echo(f"{'provider':<12} {'source':<10}")
    click.echo("-" * 24)
    for name, source in rows:
        marker = "✓" if source != "missing" else "·"
        click.echo(f"{marker} {name:<10} {source}")


def run_secrets_login_openai() -> None:
    """OAuth login via the openai CLI. We just shell out — the SDK handles
    the token cache."""
    cli = shutil.which("openai")
    if cli is None:
        raise click.ClickException(
            "`openai` CLI not found on PATH. Install with `pip install openai` "
            "(already pulled by `pip install -e '.[api]'`)."
        )
    click.echo("Launching `openai` OAuth flow — follow the prompt to authorize.")
    try:
        subprocess.run([cli, "auth", "login"], check=True)
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"openai auth login failed: {e}") from e


def run_secrets_set(name: str) -> None:
    if name not in {"gemini", "openrouter", "openai"}:
        raise click.ClickException(
            f"Unknown provider {name!r}. Use one of: gemini, openrouter, openai."
        )
    value = click.prompt(f"Paste your {name} API key", hide_input=True)
    if not value.strip():
        raise click.ClickException("Empty value; nothing saved.")
    secrets.set_(name, value.strip())
    click.echo(f"✓ Stored {name} key at {secrets.CREDENTIALS_PATH} (chmod 600).")


def run_secrets_remove(name: str) -> None:
    if secrets.remove(name):
        click.echo(f"✓ Removed {name}.")
    else:
        click.echo(f"(no stored value for {name})")


def run_budget_show() -> None:
    spent = cost.today_total_usd()
    cap = cost.cap_usd()
    pct = (spent / cap * 100) if cap else 0
    click.echo(f"Today: ${spent:.4f} / ${cap:.2f}  ({pct:.1f}%)")
    click.echo(f"Remaining: ${cost.remaining_budget_usd():.4f}")
    history = cost.history(days=14)
    if history:
        click.echo("")
        click.echo(f"{'date':<12} {'spend':>10} {'calls':>6}")
        click.echo("-" * 32)
        for row in history:
            click.echo(f"{row['date']:<12} ${row['total_usd']:>8.4f} {row['calls']:>6}")


def run_cache_prune(older_than_days: int) -> None:
    root = find_project_root()
    if root is None:
        raise click.ClickException("Run from inside a project. Cache is per-project.")
    removed = _cache.prune(root, older_than_days=older_than_days)
    click.echo(f"✓ Pruned {removed} cached artifact(s) older than {older_than_days} day(s).")
