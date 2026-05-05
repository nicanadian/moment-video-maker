"""Built-in repeatable smoke workflow for Moment Studio.

The smoke harness creates tiny synthetic inputs under a caller-provided
SOLYPSIZM_HOME and drives the public Click CLI through the core happy path.
It intentionally avoids provider calls and media decoding so it can run in CI.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from solypsizm_moment_studio.cli import main


@dataclass(frozen=True)
class SmokeResult:
    home: Path
    project_root: Path
    moment_id: str
    commands_run: int
    project_status: dict[str, Any]


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _write_inputs(inputs: Path) -> dict[str, Path]:
    inputs.mkdir(parents=True, exist_ok=True)
    lyrics = inputs / "lyrics.txt"
    lyrics.write_text(
        "Verse: neon tower wakes.\nChorus: signal cuts through static.\n",
        encoding="utf-8",
    )
    audio = inputs / "master.wav"
    audio.write_bytes(b"RIFF0000WAVEfmt ")
    concepts = inputs / "concepts.json"
    _write_json(
        concepts,
        [
            {
                "title": "Signal Tower at Dawn",
                "logline": "Solypsizm wakes a neon tower above a silent city.",
                "visual_hook": "cyan visor flare over violet clouds",
                "emotional_arc": "isolation to resolve",
                "scene_count": 3,
            }
        ],
    )
    scenes = inputs / "scenes.json"
    _write_json(
        scenes,
        [
            {
                "title": "Tower Wakeup",
                "description": "Solypsizm stands on a broadcast tower.",
                "duration_target_seconds": 6,
                "shot_type": "wide",
                "camera_motion": "slow push in",
                "subject_motion": "turns toward dawn",
                "environment": "neon tower",
                "lighting": "cyan rim light",
                "mood_tags": ["isolation", "awakening"],
                "song_section_fit": ["intro"],
                "energy_target": "low-mid",
            },
            {
                "title": "Static Ascent",
                "description": "The signal climbs through violet static.",
                "duration_target_seconds": 6,
                "shot_type": "medium",
                "camera_motion": "tilt up",
                "subject_motion": "raises one hand",
                "environment": "antenna platform",
                "lighting": "violet lightning",
                "mood_tags": ["tension", "rise"],
                "song_section_fit": ["verse 1"],
                "energy_target": "mid",
            },
            {
                "title": "Horizon Answer",
                "description": "The horizon answers with cyan light.",
                "duration_target_seconds": 6,
                "shot_type": "wide",
                "camera_motion": "orbit",
                "subject_motion": "steps forward",
                "environment": "glowing skyline",
                "lighting": "cyan sunrise",
                "mood_tags": ["release", "resolve"],
                "song_section_fit": ["chorus 1"],
                "energy_target": "mid-high",
            },
        ],
    )
    for idx in range(1, 4):
        (inputs / f"scene{idx}-start.png").write_bytes(b"fake-png-start" + bytes([idx]))
        (inputs / f"scene{idx}-end.png").write_bytes(b"fake-png-end" + bytes([idx]))
        (inputs / f"scene{idx}-clip.mp4").write_bytes(b"fake-mp4" + bytes([idx]))
    return {"lyrics": lyrics, "audio": audio, "concepts": concepts, "scenes": scenes}


def run_cli_smoke_workflow(home: Path, brand_kit_source: Path) -> SmokeResult:
    """Run the no-provider happy-path workflow and return key artifacts."""
    runner = CliRunner()
    home = home.resolve()
    inputs = home / ".smoke-inputs"
    paths = _write_inputs(inputs)
    env = {"SOLYPSIZM_HOME": str(home), "SOLYPSIZM_PROJECT": "haze"}
    commands_run = 0

    def run(args: list[str]) -> None:
        nonlocal commands_run
        result = runner.invoke(main, args, env=env)
        commands_run += 1
        if result.exit_code != 0:
            raise AssertionError(f"solypsizm {' '.join(args)} failed:\n{result.output}")

    run(["bootstrap-brand-kit", "--source", str(brand_kit_source)])
    run(
        [
            "new",
            "haze",
            "--song-title",
            "Haze Over The Horizon",
            "--lyrics",
            str(paths["lyrics"]),
            "--audio",
            str(paths["audio"]),
        ]
    )
    run(["import-concepts", str(paths["concepts"])])
    run(["pick-concept", "concept-01-signal-tower-dawn"])
    run(["import-scenes", str(paths["scenes"])])
    run(["prompts", "scene-01-tower-wakeup", "--no-copy"])

    scene_ids = ["scene-01-tower-wakeup", "scene-02-static-ascent", "scene-03-horizon-answer"]
    for idx, scene_id in enumerate(scene_ids, start=1):
        run(
            [
                "import-frame",
                str(inputs / f"scene{idx}-start.png"),
                "--scene",
                scene_id,
                "--type",
                "start",
            ]
        )
        run(
            [
                "import-frame",
                str(inputs / f"scene{idx}-end.png"),
                "--scene",
                scene_id,
                "--type",
                "end",
            ]
        )
        run(
            [
                "import-clip",
                str(inputs / f"scene{idx}-clip.mp4"),
                "--scene",
                scene_id,
                "--rating",
                "5",
            ]
        )

    project_root = home / "haze"
    _write_json(
        project_root / "audio" / "song-analysis.json",
        {
            "audio_file": "audio/master.wav",
            "duration_seconds": 45.0,
            "tempo_bpm": 120.0,
            "sections": [
                {"name": "intro", "start": 0.0, "end": 12.0, "energy_avg": 0.2},
                {"name": "verse 1", "start": 12.0, "end": 28.0, "energy_avg": 0.5},
                {"name": "chorus 1", "start": 28.0, "end": 45.0, "energy_avg": 0.8},
            ],
        },
    )
    _write_json(
        home / "edit-config.json",
        {
            "min_clip_rating": 3,
            "min_clips_per_moment": 1,
            "max_clips_per_moment": 2,
            "moment_duration_target_seconds": 6.0,
            "moment_duration_tolerance_pct": 100.0,
            "max_clip_reuse_count": 3,
            "section_diversity_weight": 0.6,
            "mood_match_weight": 0.4,
            "energy_match_weight": 0.5,
            "always_lead_with_hook": True,
        },
    )

    run(["suggest-moments", "--count", "2", "--strategy", "section_focus"])
    run(["review-moment", "moment-01-intro", "--approve"])
    run(["trace", "take-01.mp4"])
    run(["doctor"])

    moment = json.loads((project_root / "moments" / "moment-01-intro.json").read_text())
    scenes = list((project_root / "scenes" / "concept-01-signal-tower-dawn").glob("scene-*.json"))
    moments = list((project_root / "moments").glob("moment-*.json"))
    approved = sum(
        1 for path in moments if json.loads(path.read_text()).get("status") == "approved"
    )
    return SmokeResult(
        home=home,
        project_root=project_root,
        moment_id=moment["id"],
        commands_run=commands_run,
        project_status={"approved_moments": approved, "scene_count": len(scenes)},
    )
