"""Benchmark harness: runs N (provider, model) × T takes against a canonical
prompt set, scores each artifact via the judge, writes a leaderboard.

Outputs land in ``$SOLYPSIZM_HOME/benchmarks/runs/<timestamp>/`` so they're
brand-wide (not per-project). Each run keeps its own manifest + artifacts +
scores so re-running the same set against new models stays comparable.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from solypsizm_moment_studio.judge import JudgeScore, judge_image, judge_video
from solypsizm_moment_studio.providers import dispatch
from solypsizm_moment_studio.providers.exceptions import ProviderError
from solypsizm_moment_studio.state import brand_kit_path, load_brand_kit, solypsizm_home


class PromptSet(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    modality: str  # "image" | "video"
    description: str = ""
    reference: str  # path relative to solypsizm_home
    prompt: str
    size: str = "1024x1792"
    duration_seconds: float = 6.0


class BenchmarkRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    spec: str
    take: int
    artifact_path: str
    cost_usd: float
    latency_ms: int
    score: JudgeScore | None = None
    error: str | None = None


def load_prompt_set(name_or_path: str, search_dir: Path | None = None) -> PromptSet:
    """Resolve a prompt set by short name or full path."""
    candidates: list[Path] = []
    if search_dir:
        candidates.extend([search_dir / f"{name_or_path}.yaml", search_dir / name_or_path])
    candidates.append(Path(name_or_path))
    for c in candidates:
        if c.is_file():
            return _parse_prompt_set(c)
    raise FileNotFoundError(f"Prompt set not found: {name_or_path}")


def _parse_prompt_set(path: Path) -> PromptSet:
    """Tiny YAML-ish parser. Avoids adding pyyaml as a dep — our prompt-set
    files are simple key:value with one block-scalar 'prompt: |' field."""
    text = path.read_text(encoding="utf-8")
    data: dict[str, object] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        m = re.match(r"^([a-zA-Z_][\w]*):\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key, value = m.group(1), m.group(2).strip()
        if value == "|":
            # Block scalar: collect indented lines until indent breaks.
            i += 1
            block: list[str] = []
            while i < len(lines):
                nxt = lines[i]
                if not nxt:
                    block.append("")
                    i += 1
                    continue
                if nxt[0] not in (" ", "\t"):
                    break
                # Strip leading 2-space indent.
                block.append(nxt[2:] if nxt.startswith("  ") else nxt.lstrip())
                i += 1
            data[key] = "\n".join(block).strip()
            continue
        # Strip surrounding quotes.
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        # Coerce a few known numeric fields.
        if key in {"duration_seconds"}:
            try:
                data[key] = float(value)
            except ValueError:
                data[key] = value
        else:
            data[key] = value
        i += 1
    return PromptSet.model_validate(data)


def estimate_cost(specs: list[str], takes: int, prompt_set: PromptSet) -> float:
    """Conservative pre-run estimate so we can refuse over-budget runs."""
    from solypsizm_moment_studio.providers import pricing

    per_artifact = 0.0
    if prompt_set.modality == "image":
        per_artifact = max(
            (pricing.image_cost(spec.replace(":", "/")) for spec in specs), default=0.20
        )
    else:
        per_artifact = max(
            (
                pricing.video_cost(spec.replace(":", "/"), prompt_set.duration_seconds)
                for spec in specs
            ),
            default=3.00,
        )
    judge_cost_per_artifact = 0.005  # rough Gemini Flash vision call estimate
    return (per_artifact + judge_cost_per_artifact) * len(specs) * takes


def run(
    prompt_set: PromptSet,
    specs: list[str],
    *,
    takes: int = 1,
    judge_model: str = "gemini-2.5-flash",
    out_dir: Path | None = None,
    budget_usd: float | None = None,
) -> Path:
    """Execute the benchmark. Returns the path to the run directory."""
    home = solypsizm_home()
    if out_dir is None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        out_dir = home / "benchmarks" / "runs" / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    bk = load_brand_kit(brand_kit_path())
    reference_path = (home / prompt_set.reference).resolve()
    if not reference_path.is_file():
        raise FileNotFoundError(
            f"Reference not found at {reference_path}. Run "
            "`solypsizm bootstrap-brand-kit` to install the kit + character-reference/."
        )

    if budget_usd is not None:
        est = estimate_cost(specs, takes, prompt_set)
        if est > budget_usd:
            raise ProviderError(
                f"Estimated cost ${est:.2f} exceeds --budget ${budget_usd:.2f}. "
                "Reduce --takes or trim the model list."
            )

    records: list[BenchmarkRecord] = []
    for spec in specs:
        for take in range(1, takes + 1):
            safe_spec = spec.replace("/", "__").replace(":", "__")
            suffix = ".png" if prompt_set.modality == "image" else ".mp4"
            artifact_path = out_dir / f"{safe_spec}__take-{take:02d}{suffix}"
            record = BenchmarkRecord(
                spec=spec, take=take, artifact_path=str(artifact_path),
                cost_usd=0.0, latency_ms=0,
            )
            try:
                if prompt_set.modality == "image":
                    result = dispatch.call_image(
                        out_dir,
                        spec,
                        prompt=prompt_set.prompt,
                        out_path=artifact_path,
                        reference=reference_path,
                        size=prompt_set.size,
                    )
                else:
                    result = dispatch.call_video(
                        out_dir,
                        spec,
                        prompt=prompt_set.prompt,
                        out_path=artifact_path,
                        start_frame=reference_path,
                        duration_seconds=prompt_set.duration_seconds,
                    )
                record.cost_usd = result.cost_usd
                record.latency_ms = result.latency_ms

                # Score it.
                if prompt_set.modality == "image":
                    score = judge_image(
                        bk, reference_path, artifact_path, prompt_set.prompt,
                        model=judge_model,
                    )
                else:
                    score = judge_video(
                        bk, reference_path, artifact_path, prompt_set.prompt,
                        model=judge_model,
                    )
                record.score = score
            except Exception as e:
                record.error = f"{type(e).__name__}: {e}"
            records.append(record)

    manifest = {
        "prompt_set": prompt_set.model_dump(),
        "judge_model": judge_model,
        "takes": takes,
        "specs": specs,
        "records": [r.model_dump() for r in records],
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "report.md").write_text(_build_report(records, prompt_set), encoding="utf-8")
    return out_dir


def _build_report(records: list[BenchmarkRecord], prompt_set: PromptSet) -> str:
    """Markdown leaderboard sorted by score; ties broken by lower cost."""
    by_spec: dict[str, list[BenchmarkRecord]] = {}
    for r in records:
        by_spec.setdefault(r.spec, []).append(r)

    rows: list[tuple[str, float, float, int, int, int]] = []
    for spec, group in by_spec.items():
        total_cost = sum(r.cost_usd for r in group)
        total_latency = sum(r.latency_ms for r in group)
        scored = [r for r in group if r.score is not None]
        avg_score = (
            sum(r.score.total for r in scored) / len(scored) if scored else 0.0
        )
        errors = sum(1 for r in group if r.error)
        rows.append(
            (spec, avg_score, total_cost, total_latency // max(1, len(group)), len(group), errors)
        )

    rows.sort(key=lambda row: (-row[1], row[2]))

    lines = [
        f"# Benchmark report — {prompt_set.name}",
        "",
        f"Modality: **{prompt_set.modality}**.",
        "Score is weighted (character 40%, prompt 25%, aesthetic 25%, quality 10%) scaled to 0-40.",
        "",
        "| spec | avg score | total cost | avg latency | takes | errors |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for spec, score, total_cost, avg_lat, n, errs in rows:
        lines.append(
            f"| `{spec}` | {score:.1f} / 40 | ${total_cost:.4f} | {avg_lat}ms | {n} | {errs} |"
        )
    if rows:
        winner = rows[0][0]
        lines.append("")
        lines.append(f"**Recommended default for {prompt_set.modality}: `{winner}`**.")
    return "\n".join(lines) + "\n"
