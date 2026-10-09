"""Regression tests for reproduced contradictory drafts and stale cache facts."""

from datetime import timedelta

import pytest

from baahar import brief
from baahar.briefing_contract import build_contract_case, deterministic_fallback
from baahar.models import Briefing
from baahar.parks import park_by_id
from baahar.score import build_plan


def test_skip_marker_cannot_launder_outdoor_invitation(hazardous_slot):
    plan = build_plan([hazardous_slot], park=park_by_id("cubbon"))
    raw = "Go outside now. Do not wait indoors. Indian NAQI 350."
    assert brief.enforce_safety(raw, plan) == deterministic_fallback(build_contract_case(plan))


def test_wrong_naqi_replaces_entire_draft(go_slot):
    plan = build_plan([go_slot], park=park_by_id("cubbon"))
    raw = "GO. Indian NAQI is 999. Head to Cubbon Park."
    assert brief.enforce_safety(raw, plan) == deterministic_fallback(build_contract_case(plan))


def test_invalid_cached_draft_cannot_bypass_model_guard(monkeypatch, hazardous_slot):
    plan = build_plan([hazardous_slot], park=park_by_id("cubbon"))
    malicious = Briefing(
        text="Go outside now. Do not wait indoors.", model="hybrid", writer="hybrid", word_count=8
    )
    monkeypatch.setattr(brief, "_read_cache", lambda _: malicious)
    monkeypatch.setattr(brief, "write_gemma", lambda *a, **k: malicious.text)
    monkeypatch.setenv("GEMINI_API_KEY", "test-placeholder")
    monkeypatch.setenv("BAAHAR_CACHE", "true")
    result = brief.generate(plan, writer="gemma")
    assert result.writer == "template"
    assert "model and cache bypassed" in result.note
    assert result.text == deterministic_fallback(build_contract_case(plan))


def test_cache_identity_includes_day_and_precise_reading(go_slot):
    plan = build_plan([go_slot])
    later = plan.model_copy(
        update={
            "best_time": plan.best_time + timedelta(days=1),
            "best_slot": go_slot.model_copy(update={"time": go_slot.time + timedelta(days=1)}),
        }
    )
    assert brief._cache_key(plan, None, "gemma") != brief._cache_key(later, None, "gemma")


def test_nonfinite_weather_cannot_crash_local_fallback(go_slot):
    slot = go_slot.model_copy(
        update={
            "weather": go_slot.weather.model_copy(
                update={"apparent_c": float("nan"), "humidity": float("nan")}
            )
        }
    )
    plan = build_plan([slot], park=park_by_id("cubbon"), scorer="heuristic")
    result = brief.generate(plan, writer="template")
    assert plan.overall.value == "SKIP"
    assert result.writer == "template"
    assert "nan" not in result.text.lower()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_optional_nonfinite_temperature_is_omitted(go_slot, value):
    slot = go_slot.model_copy(
        update={"weather": go_slot.weather.model_copy(update={"temp_c": value})}
    )
    plan = build_plan([slot], park=park_by_id("cubbon"), scorer="heuristic")
    result = brief.generate(plan, writer="template")
    assert plan.overall.value == "GO"
    assert brief.build_context(plan)["weather"]["temp_c"] is None
    assert "Around" not in result.text
    assert "nanC" not in result.text and "infC" not in result.text


@pytest.mark.parametrize("naqi, decision", [(350, "SKIP"), (220, "WAIT")])
def test_withheld_walk_never_requests_model_prose(monkeypatch, go_slot, naqi, decision):
    slot = go_slot.model_copy(update={"air": go_slot.air.model_copy(update={"naqi": naqi})})
    plan = build_plan([slot], park=park_by_id("cubbon"))
    assert plan.overall.value == decision

    def forbidden(*args, **kwargs):
        raise AssertionError("A withheld walk must not request a model draft or cache")

    monkeypatch.setattr(brief, "_read_cache", forbidden)
    monkeypatch.setattr(brief, "write_gemma", forbidden)
    result = brief.generate(plan, writer="gemma")
    assert result.writer == "template"
    assert result.text == deterministic_fallback(build_contract_case(plan))
    assert "model and cache bypassed" in result.note


def test_postprocessing_cannot_publish_a_contradiction(monkeypatch, go_slot):
    plan = build_plan([go_slot], park=park_by_id("cubbon"))
    raw = deterministic_fallback(build_contract_case(plan))
    monkeypatch.setenv("GEMINI_API_KEY", "test-placeholder")
    monkeypatch.setenv("BAAHAR_CACHE", "0")
    brief.get_settings.cache_clear()
    monkeypatch.setattr(brief, "write_gemma", lambda *a, **k: raw)
    # A repair regression must never turn an accepted draft into published contradiction.
    monkeypatch.setattr(brief, "_ground_park_names", lambda *a: "SKIP. Stay indoors.")
    result = brief.generate(plan, writer="gemma")
    assert result.writer == "template"
    assert result.text == raw
    assert "Final text failed" in result.note
