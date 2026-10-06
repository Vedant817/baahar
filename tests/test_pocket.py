"""Tests for Pocket Mode payload generation and honesty guarantees.

Pins the behavioural contracts introduced in WP3:
1. SKIP plans disable pocket mode (active=False) with an honest subline.
2. WAIT plans without a future clean hour honestly state no clean hour remains,
   rather than making vague promises ("until the window opens").
3. WAIT plans with a future clean hour name the exact HH:MM timestamp.
4. GO plans enable pocket mode (active=True).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from baahar.models import Decision, DataSource, HourlyAir, HourlyWeather, HourSlot, OutdoorPlan, Park, SlotScore
from baahar.parks import park_by_id
from baahar.pocket import _headline_for, _next_hint, build_pocket


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
        generated_at=datetime(2026, 10, 6, 8, 0, tzinfo=timezone.utc),
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

        assert pocket.active is True
        assert pocket.headline == "Not yet."
        assert pocket.subline == "No clean hour left in this window."

    def test_wait_plan_with_future_go_names_time(self) -> None:
        t0 = datetime(2026, 10, 6, 10, 0)
        t1 = datetime(2026, 10, 6, 11, 0)
        t2 = datetime(2026, 10, 6, 12, 0)
        slots = [
            _make_slot_score(t0, Decision.WAIT),
            _make_slot_score(t1, Decision.WAIT),
            _make_slot_score(t2, Decision.GO),
        ]
        plan = _make_plan(Decision.WAIT, slots, best_time=t0)
        pocket = build_pocket(plan)

        assert pocket.active is True
        assert pocket.headline == "Not yet."
        assert "Rest until 12:00. Then outside." == pocket.subline

    def test_go_plan_is_active_with_park_invitation(self) -> None:
        t0 = datetime(2026, 10, 6, 10, 0)
        slot = _make_slot_score(t0, Decision.GO)
        plan = _make_plan(Decision.GO, [slot], best_time=t0)
        pocket = build_pocket(plan)

        assert pocket.active is True
        assert pocket.headline == "Phone in pocket."
        assert "Cubbon Park" in pocket.subline


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
