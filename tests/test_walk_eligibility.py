"""Temporal safety regressions use real scoring and walking policy, offline."""

from datetime import timedelta

import pytest

from baahar import brief, walk
from baahar.briefing_contract import build_contract_case, deterministic_fallback
from baahar.models import Briefing, DataSource, Decision
from baahar.parks import park_by_id
from baahar.pocket import build_pocket
from baahar.score import build_plan


def plan_for(hours, **kwargs):
    return build_plan(hours, park=park_by_id("cubbon"), scorer="heuristic", **kwargs)


def forbid_model_and_cache(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Walking policy must gate models and cache before either is invoked")

    monkeypatch.setattr(brief, "_read_cache", forbidden)
    monkeypatch.setattr(brief, "write_gemma", forbidden)


def test_current_hazardous_air_cannot_be_hidden_by_future_go(monkeypatch, slot):
    now, future = slot(0, naqi=350), slot(1, naqi=50)
    plan = plan_for([now, future], generated_at=now.time)
    assert plan.overall is Decision.GO  # the planner may still advertise a forecast
    assert plan.best_time == future.time
    assert plan.current_slot == now
    assert plan.current_decision is Decision.SKIP
    assert walk.eligibility(plan)[0] is False
    forbid_model_and_cache(monkeypatch)
    result = brief.generate(plan, writer="gemma")
    assert result.writer == "template"
    assert result.text.startswith("SKIP.")
    assert "350" in result.text
    assert "walk now" not in result.text.lower()
    assert "Refresh conditions before walking" in result.text
    assert build_pocket(plan).active is False
    assert "350" in build_pocket(plan).safety_note


@pytest.mark.parametrize(
    "kind", ["expired", "future_assessment", "missing_current", "fixture", "unknown_air"]
)
def test_ineligible_plan_bypasses_models_and_cache(monkeypatch, slot, kind):
    hour = slot(0, naqi=50)
    if kind == "unknown_air":
        hour = slot(0, pm25=None, pm10=None)
    assessment_time = hour.time
    hours = [hour]
    kwargs = {}
    if kind == "expired":
        assessment_time -= timedelta(minutes=16)
    elif kind == "future_assessment":
        assessment_time += timedelta(minutes=1)
    elif kind == "missing_current":
        hours = [slot(1, naqi=50)]
    elif kind == "fixture":
        kwargs["air_source"] = DataSource.FIXTURE
    plan = plan_for(hours, generated_at=assessment_time, **kwargs)
    assert walk.eligibility(plan)[0] is False
    forbid_model_and_cache(monkeypatch)
    result = brief.generate(plan, writer="gemma")
    assert result.writer == "template"
    assert not result.text.startswith("GO.")
    assert build_pocket(plan).active is False


def test_hour_boundary_invalidates_even_a_recent_plan(monkeypatch, go_slot):
    assessed = go_slot.time + timedelta(minutes=55)
    plan = plan_for([go_slot], generated_at=assessed)
    assert walk.eligibility(plan, now=assessed)[0] is True
    boundary = go_slot.time + timedelta(hours=1)
    monkeypatch.setattr(walk, "utc_now", lambda: boundary)
    assert walk.eligibility(plan)[0] is False
    assert "current-hour" in walk.eligibility(plan)[1]
    assert build_pocket(plan).active is False


def test_fresh_current_go_allows_pocket_and_model_prose(monkeypatch, go_slot):
    plan = plan_for([go_slot], generated_at=go_slot.time)
    assert walk.eligibility(plan)[0] is True
    assert build_pocket(plan).active is True
    raw = deterministic_fallback(build_contract_case(plan))
    calls = []
    monkeypatch.setenv("GEMINI_API_KEY", "test-placeholder")
    monkeypatch.setenv("BAAHAR_CACHE", "0")
    brief.get_settings.cache_clear()
    monkeypatch.setattr(brief, "write_gemma", lambda *a, **k: calls.append("model") or raw)
    result = brief.generate(plan, writer="gemma")
    assert calls == ["model"]
    assert result.writer != "template"
    assert result.text.startswith("GO.")


def test_fresh_cached_go_is_rechecked_after_expiration(monkeypatch, go_slot):
    plan = plan_for([go_slot], generated_at=go_slot.time)
    raw = deterministic_fallback(build_contract_case(plan))
    cached = Briefing(text=raw, model="hybrid", writer="hybrid", word_count=len(raw.split()))
    calls = []
    monkeypatch.setenv("BAAHAR_CACHE", "1")
    brief.get_settings.cache_clear()
    monkeypatch.setattr(brief, "_read_cache", lambda _: calls.append("cache") or cached)
    assert "served from cache" in brief.generate(plan, writer="gemma").note
    assert calls == ["cache"]
    monkeypatch.setattr(walk, "utc_now", lambda: go_slot.time + timedelta(minutes=16))
    forbid_model_and_cache(monkeypatch)
    result = brief.generate(plan, writer="gemma")
    assert result.writer == "template"
    assert not result.text.startswith("GO.")
    assert build_pocket(plan).active is False


def test_model_generation_cannot_publish_after_plan_expires(monkeypatch, go_slot):
    plan = plan_for([go_slot], generated_at=go_slot.time)
    raw = deterministic_fallback(build_contract_case(plan))
    monkeypatch.setenv("GEMINI_API_KEY", "test-placeholder")
    monkeypatch.setenv("BAAHAR_CACHE", "0")
    brief.get_settings.cache_clear()

    def slow_model(*args, **kwargs):
        monkeypatch.setattr(walk, "utc_now", lambda: go_slot.time + timedelta(minutes=16))
        return raw

    monkeypatch.setattr(brief, "write_gemma", slow_model)
    result = brief.generate(plan, writer="gemma")
    assert result.writer == "template"
    assert not result.text.startswith("GO.")
    assert build_pocket(plan).active is False
