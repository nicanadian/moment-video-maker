"""Repeatable smoke harness for the CLI happy path."""

from __future__ import annotations

from pathlib import Path

from solypsizm_moment_studio.smoke import run_cli_smoke_workflow


def test_cli_smoke_workflow_reaches_approved_moment(tmp_path: Path) -> None:
    result = run_cli_smoke_workflow(
        home=tmp_path / "soly-home",
        brand_kit_source=Path("brand-kit.json").resolve(),
    )

    assert result.project_root.name == "haze"
    assert result.moment_id == "moment-01-intro"
    assert (result.project_root / "moments" / "moment-01-intro.json").is_file()
    assert result.project_status["approved_moments"] == 1
    assert result.project_status["scene_count"] == 3
    assert result.commands_run >= 12
