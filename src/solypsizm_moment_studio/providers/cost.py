"""Daily-budget guard.

Persists daily spend at ``~/solypsizm/.budget/<YYYY-MM-DD>.json``. Each call
checks the running total before spending; refuses with ``BudgetExceeded``
when the cap is hit. Cache hits are NOT counted (they cost $0).

Concurrent runs are safe: writes go through ``state.io.save_json_atomic``
which fsyncs and renames atomically.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from pathlib import Path

from solypsizm_moment_studio.providers.exceptions import BudgetExceeded
from solypsizm_moment_studio.state import save_json_atomic, solypsizm_home

DEFAULT_DAILY_CAP_USD = 40.0


def _cap_usd() -> float:
    """Daily cap. Default $40. Override via ``SOLYPSIZM_DAILY_BUDGET``."""
    raw = os.environ.get("SOLYPSIZM_DAILY_BUDGET")
    if raw:
        try:
            return float(raw)
        except ValueError:
            return DEFAULT_DAILY_CAP_USD
    return DEFAULT_DAILY_CAP_USD


def _budget_dir() -> Path:
    return solypsizm_home() / ".budget"


def _today_path(d: date | None = None) -> Path:
    d = d or datetime.now(timezone.utc).date()
    return _budget_dir() / f"{d.isoformat()}.json"


def _load_today() -> dict:
    path = _today_path()
    if not path.is_file():
        return {"date": datetime.now(timezone.utc).date().isoformat(), "calls": [], "total_usd": 0.0}
    import json
    return json.loads(path.read_text(encoding="utf-8"))


def today_total_usd() -> float:
    return float(_load_today().get("total_usd", 0.0))


def remaining_budget_usd() -> float:
    return max(0.0, _cap_usd() - today_total_usd())


def cap_usd() -> float:
    return _cap_usd()


def reserve(estimated_cost_usd: float, *, model: str, kind: str) -> None:
    """Pre-call check. Raises ``BudgetExceeded`` if this call would push us
    past the daily cap. Doesn't actually charge — that happens in ``record``
    after the call completes."""
    cap = _cap_usd()
    spent = today_total_usd()
    if spent + estimated_cost_usd > cap:
        raise BudgetExceeded(
            f"Daily budget would be exceeded: spent ${spent:.2f} + "
            f"estimated ${estimated_cost_usd:.4f} > cap ${cap:.2f} "
            f"(call: {kind} via {model})."
        )


def record(actual_cost_usd: float, *, model: str, kind: str, latency_ms: int) -> None:
    """Append a completed call to today's ledger. Idempotent against the
    file rename (atomic write)."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": kind,
        "model": model,
        "cost_usd": round(actual_cost_usd, 6),
        "latency_ms": latency_ms,
    }
    data = _load_today()
    data["calls"].append(record)
    data["total_usd"] = round(float(data.get("total_usd", 0.0)) + actual_cost_usd, 6)
    save_json_atomic(_today_path(), data)


def history(days: int = 30) -> list[dict]:
    """Last N days of ledger files (most recent first), summarized."""
    folder = _budget_dir()
    if not folder.is_dir():
        return []
    out: list[dict] = []
    for path in sorted(folder.glob("*.json"), reverse=True)[:days]:
        import json
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        out.append(
            {
                "date": data.get("date") or path.stem,
                "total_usd": float(data.get("total_usd", 0.0)),
                "calls": len(data.get("calls", [])),
            }
        )
    return out
