"""Foundation tests for the v2 provider layer.

Mocks the SDK calls — no real provider traffic. Covers the wrappers (cost
guard, cache, dispatch) which are where logic lives; adapters themselves
get tested when there's recorded fixture coverage.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from solypsizm_moment_studio.providers import cache, cost, pricing, registry, secrets
from solypsizm_moment_studio.providers.exceptions import (
    BudgetExceeded,
    ProviderError,
    ProviderUnavailable,
)
from solypsizm_moment_studio.providers.results import CompletionResult


# ---------------------------------------------------------------------------
# pricing
# ---------------------------------------------------------------------------


def test_text_cost_known_model() -> None:
    # gemini-2.5-flash is in the table; 1K input + 1K output should be tiny.
    cost_usd = pricing.text_cost("gemini/gemini-2.5-flash", 1000, 1000)
    assert 0 < cost_usd < 0.01


def test_text_cost_unknown_model_returns_zero() -> None:
    assert pricing.text_cost("openai/imaginary-future-model", 1000, 1000) == 0.0


def test_image_cost_lookup() -> None:
    assert pricing.image_cost("openai/gpt-image-1-med") > 0
    assert pricing.image_cost("openai/imaginary-image-model") == 0.0


def test_video_cost_respects_min_duration() -> None:
    # Veo 3 has a 4s minimum; calling with 2s should still cost the 4s rate.
    short = pricing.video_cost("gemini/veo-3", 2.0)
    short_floor = pricing.video_cost("gemini/veo-3", 4.0)
    assert short == short_floor


# ---------------------------------------------------------------------------
# cost guard / budget tracker
# ---------------------------------------------------------------------------


def test_budget_reserve_refuses_over_cap(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SOLYPSIZM_HOME", str(tmp_path))
    monkeypatch.setenv("SOLYPSIZM_DAILY_BUDGET", "1.00")
    # Spend $0.99 first.
    cost.record(0.99, model="test:m", kind="text", latency_ms=100)
    assert cost.today_total_usd() == pytest.approx(0.99)
    # A $0.05 reservation pushes over $1.00 cap.
    with pytest.raises(BudgetExceeded):
        cost.reserve(0.05, model="test:m", kind="text")


def test_budget_record_accumulates(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SOLYPSIZM_HOME", str(tmp_path))
    cost.record(0.10, model="test:m", kind="text", latency_ms=100)
    cost.record(0.20, model="test:m", kind="image", latency_ms=2000)
    cost.record(0.05, model="test:m", kind="text", latency_ms=80)
    assert cost.today_total_usd() == pytest.approx(0.35)


def test_budget_remaining(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SOLYPSIZM_HOME", str(tmp_path))
    monkeypatch.setenv("SOLYPSIZM_DAILY_BUDGET", "10.00")
    cost.record(3.50, model="x", kind="text", latency_ms=100)
    assert cost.remaining_budget_usd() == pytest.approx(6.50)


# ---------------------------------------------------------------------------
# cache
# ---------------------------------------------------------------------------


def test_cache_text_round_trip(tmp_path) -> None:
    payload = {"text": "hello", "cost_usd": 0.01, "latency_ms": 100,
               "provider": "p", "model_id": "m", "raw_response": {}}
    miss = cache.lookup_text(tmp_path, provider="p", model="m", prompt="q", params={"t": 0.5})
    assert miss is None
    cache.store_text(tmp_path, provider="p", model="m", prompt="q",
                     result=payload, params={"t": 0.5})
    hit = cache.lookup_text(tmp_path, provider="p", model="m", prompt="q", params={"t": 0.5})
    assert hit is not None
    assert hit["text"] == "hello"


def test_cache_text_distinguishes_params(tmp_path) -> None:
    """Same prompt, different params → different cache keys."""
    payload = {"text": "v1", "cost_usd": 0.01, "latency_ms": 100,
               "provider": "p", "model_id": "m", "raw_response": {}}
    cache.store_text(tmp_path, provider="p", model="m", prompt="q", result=payload, params={"t": 0.1})
    payload2 = dict(payload, text="v2")
    cache.store_text(tmp_path, provider="p", model="m", prompt="q", result=payload2, params={"t": 0.9})
    a = cache.lookup_text(tmp_path, provider="p", model="m", prompt="q", params={"t": 0.1})
    b = cache.lookup_text(tmp_path, provider="p", model="m", prompt="q", params={"t": 0.9})
    assert a["text"] == "v1" and b["text"] == "v2"


def test_cache_artifact_round_trip(tmp_path) -> None:
    src = tmp_path / "src.png"
    src.write_bytes(b"PNG-fake")
    metadata = {"latency_ms": 1234, "raw_response": {"size": "1024x1792"}}
    out = cache.store_artifact(
        tmp_path,
        provider="p", model="m", kind="image", prompt="cat",
        artifact_source=src,
        metadata=metadata,
    )
    assert out.is_file()
    hit = cache.lookup_artifact(
        tmp_path, provider="p", model="m", kind="image", prompt="cat",
    )
    assert hit is not None
    cached_path, meta = hit
    assert cached_path.read_bytes() == b"PNG-fake"
    assert meta["latency_ms"] == 1234


def test_cache_prune_removes_old(tmp_path) -> None:
    folder = cache.cache_dir(tmp_path)
    folder.mkdir(parents=True)
    old = folder / "old.json"
    old.write_text("{}")
    # Backdate to 60 days ago.
    import time
    sixty_days_ago = time.time() - 60 * 86400
    os.utime(old, (sixty_days_ago, sixty_days_ago))
    new = folder / "new.json"
    new.write_text("{}")
    removed = cache.prune(tmp_path, older_than_days=30)
    assert removed == 1
    assert not old.is_file()
    assert new.is_file()


# ---------------------------------------------------------------------------
# secrets
# ---------------------------------------------------------------------------


def test_secrets_status_reports_env_when_set(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    # Force re-resolve of CREDENTIALS_PATH which is module-level.
    from solypsizm_moment_studio.providers import secrets as s2
    monkeypatch.setattr(s2, "CREDENTIALS_PATH", tmp_path / ".solypsizm" / "credentials.json")
    status = s2.status()
    assert status["gemini"] == "env"
    assert status["openrouter"] == "missing"


def test_secrets_set_and_get(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    from solypsizm_moment_studio.providers import secrets as s2
    monkeypatch.setattr(s2, "CREDENTIALS_PATH", tmp_path / ".solypsizm" / "credentials.json")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    s2.set_("gemini", "secret-value")
    assert s2.gemini_credential() == "secret-value"


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------


def test_registry_rejects_bad_spec() -> None:
    with pytest.raises(ValueError):
        registry.resolve_text("nope-no-colon")


def test_registry_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError):
        registry.resolve_text("madeup:model-x")


# ---------------------------------------------------------------------------
# dispatch — mocked end-to-end (cache hit avoids hitting the SDK at all)
# ---------------------------------------------------------------------------


def test_dispatch_call_text_cache_hit_skips_adapter(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SOLYPSIZM_HOME", str(tmp_path))
    # Pre-populate the cache.
    cache.store_text(
        tmp_path,
        provider="gemini",
        model="gemini-2.5-flash",
        prompt="sys-text\n\nuser-text",
        result={
            "text": "from-cache", "cost_usd": 0.01, "latency_ms": 50,
            "provider": "gemini", "model_id": "gemini-2.5-flash", "raw_response": {},
        },
        params={"temperature": 0.7, "max_tokens": None},
    )

    from solypsizm_moment_studio.providers import dispatch
    with patch("solypsizm_moment_studio.providers.registry.resolve_text") as resolve:
        result = dispatch.call_text(
            tmp_path,
            "gemini:gemini-2.5-flash",
            system="sys-text",
            user="user-text",
        )
    # Adapter should not have been resolved at all.
    resolve.assert_not_called()
    assert result.cache_hit is True
    assert result.text == "from-cache"
    assert result.cost_usd == 0.0


def test_dispatch_call_text_records_cost_on_miss(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SOLYPSIZM_HOME", str(tmp_path))

    fake_result = CompletionResult(
        text="generated", cost_usd=0.012, latency_ms=300,
        provider="gemini", model_id="gemini-2.5-flash",
    )

    class FakeAdapter:
        provider = "gemini"
        model_id = "gemini-2.5-flash"
        def complete(self, **kwargs):
            return fake_result

    from solypsizm_moment_studio.providers import dispatch
    with patch("solypsizm_moment_studio.providers.registry.resolve_text", return_value=FakeAdapter()):
        result = dispatch.call_text(
            tmp_path,
            "gemini:gemini-2.5-flash",
            system="sys",
            user="user",
        )
    assert result.text == "generated"
    assert result.cache_hit is False
    # Subsequent call should hit the cache and cost $0.
    with patch("solypsizm_moment_studio.providers.registry.resolve_text") as resolve:
        cached = dispatch.call_text(
            tmp_path,
            "gemini:gemini-2.5-flash",
            system="sys",
            user="user",
        )
    resolve.assert_not_called()
    assert cached.cache_hit is True
    assert cached.cost_usd == 0.0
    # Only the first call counted toward the budget.
    assert cost.today_total_usd() == pytest.approx(0.012)
