"""Tests for Pocket Mode payload generation and honesty guarantees.

Pins the behavioural contracts introduced in WP3:
1. SKIP plans disable pocket mode (active=False) with an honest subline.
2. WAIT plans without a future clean hour honestly state no clean hour remains,
   rather than making vague promises ("until the window opens").
3. WAIT plans with a future clean hour name the exact human-readable time (constructed plans only).
4. Only a fresh current-hour GO with live inputs enables pocket mode.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from baahar.models import (
    DataSource,
    Decision,
    HourlyAir,
    HourlyWeather,
    HourSlot,
    OutdoorPlan,
    Park,
    SlotScore,
)
from baahar.parks import park_by_id
from baahar.pocket import _next_hint, build_pocket, now_action, now_headline_for, now_lead
from baahar.score import build_plan, score_heuristic


def _make_slot_score(dt: datetime, decision: Decision, comfort: float = 85.0) -> SlotScore:
    return SlotScore(
        time=dt,
        decision=decision,
        comfort=comfort,
        reasons=["Test reason"],
    )


def _make_hour_slot(dt: datetime) -> HourSlot:
    weather = HourlyWeather(
        time=dt,
        temp_c=25.0,
        apparent_c=25.0,
        precip_mm=0.0,
        precip_prob=0.0,
        humidity=60.0,
        wind_kmh=10.0,
        uv_index=3.0,
        is_day=True,
    )
    air = HourlyAir(
        time=dt,
        pm2_5=35.0,
        pm10=60.0,
        no2=20.0,
        so2=10.0,
        co=500.0,
        o3=30.0,
        naqi=75.0,
    )
    return HourSlot(
        time=dt,
        weather=weather,
        air=air,
        weather_source=DataSource.LIVE,
        air_source=DataSource.LIVE,
    )


def _make_plan(
    overall: Decision,
    slots: list[SlotScore],
    best_time: datetime | None = None,
    park: Park | None = None,
) -> OutdoorPlan:
    if park is None:
        park = park_by_id("cubbon")
    best_slot = _make_hour_slot(best_time) if best_time else None
    return OutdoorPlan(
        city="Bengaluru",
        generated_at=datetime(2026, 10, 6, 10, 0, tzinfo=UTC),
        window_hours=len(slots),
        overall=overall,
        best_slot=best_slot,
        best_time=best_time,
        park=park,
        slots=slots,
        headline="Test headline",
        weather_source=DataSource.LIVE,
        air_source=DataSource.LIVE,
    )


class TestPocketHonesty:
    @pytest.fixture(autouse=True)
    def clock(self, monkeypatch):
        from baahar import walk

        monkeypatch.setattr(walk, "utc_now", lambda: datetime(2026, 10, 6, 10, 0, tzinfo=UTC))

    def test_skip_plan_is_not_active(self) -> None:
        t0 = datetime(2026, 10, 6, 10, 0)
        slot = _make_slot_score(t0, Decision.SKIP)
        plan = _make_plan(Decision.SKIP, [slot], best_time=t0)
        pocket = build_pocket(plan)

        assert pocket.active is False
        assert pocket.headline == "Stay in."
        assert pocket.subline == "Baahar is not sending you out today."

    def test_wait_plan_with_no_future_go_states_no_clean_hour(self) -> None:
        t0 = datetime(2026, 10, 6, 10, 0)
        t1 = datetime(2026, 10, 6, 11, 0)
        slots = [_make_slot_score(t0, Decision.WAIT), _make_slot_score(t1, Decision.WAIT)]
        plan = _make_plan(Decision.WAIT, slots, best_time=t0)
        pocket = build_pocket(plan)

        assert pocket.active is False
        assert pocket.headline == "Not yet."
        assert pocket.subline == "No clean hour left in this window."

    def test_wait_plan_with_future_go_names_time(self) -> None:
        t0 = datetime(2026, 10, 6, 10, 0)
        t1 = datetime(2026, 10, 6, 11, 0)
        t2 = datetime(2026, 10, 6, 19, 20)
        slots = [
            _make_slot_score(t0, Decision.WAIT),
            _make_slot_score(t1, Decision.WAIT),
            _make_slot_score(t2, Decision.GO),
        ]
        plan = _make_plan(Decision.WAIT, slots, best_time=t0)
        pocket = build_pocket(plan)

        assert pocket.active is False
        assert pocket.headline == "Not yet."
        assert pocket.subline == "Next GO hour is 19:20. Recheck conditions before walking."

    def test_go_plan_is_active_with_park_invitation(self) -> None:
        t0 = datetime(2026, 10, 6, 10, 0, tzinfo=UTC)
        slot = _make_slot_score(t0, Decision.GO)
        plan = _make_plan(Decision.GO, [slot], best_time=t0)
        pocket = build_pocket(plan)

        assert pocket.active is True
        assert pocket.headline == "Phone in pocket."
        assert pocket.subline == "Look up. Walk Cubbon Park"


class TestNextHint:
    def test_ignores_go_hours_at_or_before_best_time(self) -> None:
        t0 = datetime(2026, 10, 6, 9, 0)
        t1 = datetime(2026, 10, 6, 10, 0)
        slots = [_make_slot_score(t0, Decision.GO), _make_slot_score(t1, Decision.WAIT)]
        plan = _make_plan(Decision.WAIT, slots, best_time=t1)

        assert _next_hint(plan) == ""

    def test_picks_earliest_future_go_hour(self) -> None:
        t0 = datetime(2026, 10, 6, 10, 0)
        t1 = datetime(2026, 10, 6, 14, 0)
        t2 = datetime(2026, 10, 6, 16, 0)
        slots = [
            _make_slot_score(t0, Decision.WAIT),
            _make_slot_score(t1, Decision.GO),
            _make_slot_score(t2, Decision.GO),
        ]
        plan = _make_plan(Decision.WAIT, slots, best_time=t0)

        assert _next_hint(plan) == "14:00"


class TestPlannerWaitInvariant:
    def test_later_go_outside_initial_display_makes_overall_go(self, slot):
        hours = [slot(i, is_day=0) for i in range(20)]
        later_go = slot(20, is_day=1)
        hours.append(later_go)
        scores = score_heuristic(hours)
        assert all(s.decision is Decision.WAIT for s in scores[:-1])
        assert scores[-1].decision is Decision.GO

        plan = build_plan(hours, window_hours=2, scorer="heuristic")
        assert len(plan.slots) < len(scores)
        assert plan.overall is Decision.GO
        assert plan.best_time == later_go.time
        pocket = build_pocket(plan)
        assert pocket.headline == "Not yet."
        assert pocket.active is False
        assert "Refresh conditions" in pocket.subline

    def test_real_wait_has_no_go_in_full_scored_window(self, slot):
        hours = [slot(i, is_day=0) for i in range(24)]
        scores = score_heuristic(hours)
        assert all(s.decision is Decision.WAIT for s in scores)
        plan = build_plan(hours, window_hours=2, scorer="heuristic")
        assert plan.overall is Decision.WAIT
        assert len(plan.slots) < len(scores)
        pocket = build_pocket(plan)
        assert pocket.headline == "Not yet."
        assert pocket.subline == "No clean hour left in this window."
        assert _next_hint(plan) == ""


class TestNowLead:
    def test_wait_badge_does_not_say_go_at(self) -> None:
        t0 = datetime(2026, 10, 6, 10, 0)
        t2 = datetime(2026, 10, 6, 19, 20)
        plan = _make_plan(
            Decision.WAIT,
            [_make_slot_score(t0, Decision.WAIT), _make_slot_score(t2, Decision.GO)],
            best_time=t2,
        )
        lead = now_lead(plan, allowed=False, action=Decision.WAIT)
        assert lead == "Next GO hour is 19:20."
        assert "Go at" not in lead

    def test_now_headline_matches_the_blocked_badge(self, monkeypatch) -> None:
        from baahar import walk

        monkeypatch.setattr(walk, "utc_now", lambda: datetime(2026, 10, 6, 10, 0, tzinfo=UTC))
        t0 = datetime(2026, 10, 6, 10, 0, tzinfo=UTC)
        plan = _make_plan(
            Decision.GO,
            [_make_slot_score(t0, Decision.GO)],
            best_time=t0,
        )
        plan = plan.model_copy(
            update={
                "headline": "Go at 10:00.",
                "weather_source": DataSource.FIXTURE,
                "air_source": DataSource.FIXTURE,
                "current_decision": Decision.WAIT,
            }
        )
        assert now_action(plan, allowed=False) is Decision.WAIT
        assert now_headline_for(plan) == "Next GO hour is 10:00."
