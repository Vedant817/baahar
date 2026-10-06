"""The conservative (trailing-mean) NAQI path.

CPCB defines the Indian NAQI on **24-hour mean** concentrations -- 8-hour for O3
and CO -- and publishes breakpoints that are piecewise-linear and steeper at low
concentrations. Applying them to a single instantaneous hour can only ever
understate a polluted day: an afternoon reading that looks clean because the
night's dust has not settled yet is not clean, and the CPCB day it belongs to may
be Poor.

These tests are the guard rail on that. They would all fail against the old
code, which applied the breakpoints to the instantaneous hour and nothing else.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from baahar.air import parse_air
from baahar.features import features_from_slot, heuristic_decision
from baahar.models import Decision, HourlyAir, HourlyWeather, HourSlot
from baahar.naqi import (
    AVERAGING_PERIOD_HOURS,
    MIN_TRAILING_HOURS,
    NAQI_BASIS,
    NAQI_BASIS_INSTANTANEOUS,
    NAQI_BASIS_TRAILING,
    band_for_index,
    compute_naqi,
    compute_naqi_trailing,
    conservative_naqi,
    naqi_from_pm,
    parse_naqi_basis,
)

WHEN = datetime(2026, 10, 6, 14, 0, tzinfo=UTC)


def row(**values: float | None) -> dict[str, float]:
    """One hour of readings, Baahar keys, Open-Meteo source units."""
    return {k: v for k, v in values.items() if v is not None}


# ---------------------------------------------------------------------------
# The diurnal curve from the bug report
# ---------------------------------------------------------------------------
#
# PM2.5 120 ug/m3 at 07:00 (index 300, Poor), bottoming out at 35 ug/m3 by 14:00
# (index 75.5, Satisfactory). Overnight accumulation followed by an afternoon
# dip is the normal Bengaluru shape, and Pocket Mode suggests exactly the 07:00
# and the 14:00. The 14:00 hour is the one that used to read clean on a day CPCB
# would call Poor.


def diurnal_pm25_curve(hours: int = 24, peak: float = 120.0, trough: float = 35.0):
    """A day of PM2.5: overnight peak, afternoon trough, interpolated between.

    Deliberately simple and smooth -- this is about the averaging window, not
    about Bengaluru's real variance, and a hand-built curve keeps the arithmetic
    in the assertions checkable by hand.
    """
    out = []
    for i in range(hours):
        # Linear from the peak at 00:00 down to the trough at 14:00, then back up.
        if i <= 14:
            value = peak + (trough - peak) * (i / 14.0)
        else:
            value = trough + (peak - trough) * ((i - 14) / 10.0)
        out.append(row(pm25=round(value, 3), pm10=round(value * 2.2, 3)))
    return out


class TestDiurnalCurve:
    def test_instantaneous_afternoon_reads_better_than_the_day(self) -> None:
        """The old behaviour, pinned: the instantaneous afternoon value is lower.

        This is not the bug -- a genuinely calmer afternoon *should* produce a
        lower instantaneous number. It is the input to the rule, and the test
        exists so the assertions below cannot pass for the wrong reason.
        """
        curve = diurnal_pm25_curve()
        assert band_for_index(compute_naqi(curve[14]).index).value == "satisfactory"
        assert band_for_index(compute_naqi(curve[0]).index).value == "poor"

    def test_effective_band_is_the_worse_of_the_two_not_the_instantaneous(self) -> None:
        """The afternoon hour must be reported Moderate, not Satisfactory.

        14:00's own PM2.5 of 35 implies ~75 (Satisfactory). The trailing 24 h
        mean over the same curve is well above the 30 ug/m3 Good boundary and
        lands inside Moderate, which is what CPCB's day average would say. The
        effective value has to be the higher of the two.
        """
        curve = diurnal_pm25_curve()
        for i, readings in enumerate(curve):
            instant = compute_naqi(readings)
            trailing = compute_naqi_trailing(curve[: i + 1])
            assert trailing is not None or i < MIN_TRAILING_HOURS
            effective = conservative_naqi(instant, trailing)
            if trailing is not None:
                assert effective.index >= instant.index

        # Specifically for the afternoon dip, where the bug bites.
        i = 14
        instant = compute_naqi(curve[i])
        trailing = compute_naqi_trailing(curve[: i + 1])
        assert trailing is not None
        assert band_for_index(instant.index).value == "satisfactory"
        assert band_for_index(trailing.index).value == "moderate"
        assert band_for_index(conservative_naqi(instant, trailing).index).value == "moderate"

    def test_effective_is_never_below_instantaneous_across_a_whole_day(self) -> None:
        """The safety property, over every hour of the curve.

        Not a spot check. Any hour where the trailing mean is worse must raise
        the number, and no hour may lower it -- a dip in the curve is exactly
        when a naive "use the trailing value instead" fix would have made the
        product *more* optimistic.
        """
        curve = diurnal_pm25_curve(hours=48)
        raised = 0
        for i in range(len(curve)):
            instant = compute_naqi(curve[i])
            trailing = compute_naqi_trailing(curve[: i + 1])
            effective = conservative_naqi(instant, trailing)
            assert effective.index >= instant.index, (
                f"hour {i}: effective {effective.index} < instantaneous {instant.index}"
            )
            if trailing is not None:
                assert effective.index == max(instant.index, trailing.index)
                raised += effective.index > instant.index
        assert raised > 0, "the curve must actually exercise the conservative rule"

    def test_the_reported_band_matches_the_effective_value(self) -> None:
        """The band shown to a human is the band of the number acted on."""
        curve = diurnal_pm25_curve()
        for i in range(len(curve)):
            instant = compute_naqi(curve[i])
            trailing = compute_naqi_trailing(curve[: i + 1])
            effective = conservative_naqi(instant, trailing)
            assert effective.band == band_for_index(effective.index)


class TestAveragingWindows:
    def test_pm_uses_24_hours_and_o3_co_use_8(self) -> None:
        """CPCB's own averaging periods, not one window for everything."""
        assert AVERAGING_PERIOD_HOURS["pm25"] == 24
        assert AVERAGING_PERIOD_HOURS["pm10"] == 24
        assert AVERAGING_PERIOD_HOURS["o3"] == 8
        assert AVERAGING_PERIOD_HOURS["co"] == 8

    def test_the_two_windows_produce_different_means(self) -> None:
        """A spike 10 hours back is inside PM's window and outside O3's.

        PM2.5 and O3 are given the identical 24-hour curve: 120 at hour 0, then
        35 for the rest. Over 24 h the mean is pulled up by the spike; over 8 h
        it is not. If both pollutants averaged over the same window the two
        sub-indices would have to match, so this test fails the moment the
        window is wrong for either of them.
        """
        curve = [row(pm25=120.0, o3=120.0)] + [row(pm25=35.0, o3=35.0)] * 23
        trailing = compute_naqi_trailing(curve)
        assert trailing is not None

        # PM2.5 saw all 24 hours, so its mean includes the spike.
        # O3 saw only the last 8, none of which held the spike.
        assert trailing.hours_used["pm25"] == 24
        assert trailing.hours_used["o3"] == 8
        pm25_mean = sum(r["pm25"] for r in curve) / len(curve)
        o3_mean = sum(r["o3"] for r in curve[-8:]) / 8
        assert pm25_mean > o3_mean
        # And the sub-indices inherit that difference.
        assert trailing.result.sub_indices["pm25"] > trailing.result.sub_indices["o3"]

    def test_co_uses_its_own_8_hour_window(self) -> None:
        """CO is the other 8-hour pollutant, and it keeps its mg/m3 conversion."""
        curve = [row(co=2000.0)] + [row(co=500.0)] * 23
        trailing = compute_naqi_trailing(curve)
        assert trailing is not None
        assert trailing.hours_used["co"] == 8
        # Mean of the last 8 h = 500 ug/m3 = 0.5 mg/m3, i.e. mid-Good on the
        # 0-1.0 mg/m3 Good band. The 2000 spike 16 hours back is outside CO's
        # window, exactly as it should be.
        assert trailing.result.sub_indices["co"] == pytest.approx(25.0, abs=0.5)

    def test_window_hours_are_reported_for_the_dominant_pollutant(self) -> None:
        """A number and its evidence have to agree."""
        curve = [row(pm25=35.0, o3=120.0)] * 24
        trailing = compute_naqi_trailing(curve)
        assert trailing is not None
        assert trailing.result.dominant_pollutant == "o3"
        assert trailing.window_hours == 8
        assert trailing.hours == 8

    def test_every_pollutant_has_a_window(self) -> None:
        from baahar.naqi import POLLUTANTS

        assert set(AVERAGING_PERIOD_HOURS) == set(POLLUTANTS)


class TestPartialHistory:
    def test_fewer_than_three_hours_returns_none(self) -> None:
        """A mean over one or two samples is arithmetic, not an average."""
        assert compute_naqi_trailing([]) is None
        assert compute_naqi_trailing([row(pm25=100.0)]) is None
        assert compute_naqi_trailing([row(pm25=100.0), row(pm25=100.0)]) is None

    def test_three_hours_is_enough(self) -> None:
        trailing = compute_naqi_trailing([row(pm25=60.0)] * 3)
        assert trailing is not None
        assert trailing.hours_used["pm25"] == 3
        assert trailing.result.index == pytest.approx(compute_naqi({"pm25": 60.0}).index)

    def test_a_partial_window_reports_how_many_hours_it_used(self) -> None:
        """Five hours of history is used in full, and says so."""
        curve = diurnal_pm25_curve(hours=5)
        trailing = compute_naqi_trailing(curve)
        assert trailing is not None
        assert trailing.hours == 5
        assert trailing.window_hours == 24

    def test_missing_hours_are_skipped_not_counted_as_zero(self) -> None:
        """A gap in the feed is not evidence of clean air.

        If a null hour counted as zero the mean would be dragged down and the
        number would improve during an upstream outage -- precisely the failure
        mode AGENTS.md rules out.
        """
        clean = [row(pm25=100.0), row(pm25=60.0), row(pm25=60.0), row(pm25=60.0)]
        # Same day with one hour missing from the feed.
        gapped = [row(pm25=100.0), row(pm25=None), row(pm25=60.0), row(pm25=60.0)]
        with_gap = compute_naqi_trailing(gapped)
        without = compute_naqi_trailing(clean)
        assert with_gap is not None and without is not None
        # The three present hours average 73.3. Counting the hole as zero would
        # give 55 instead -- a *better* number during an upstream outage, which
        # is the failure this rule exists to prevent.
        assert with_gap.hours_used["pm25"] == 3
        assert with_gap.index == pytest.approx(compute_naqi({"pm25": 220 / 3}).index, abs=0.01)
        # Not the 55 ug/m3 a zero-filled window would have averaged to, which
        # would have scored a *better* day than actually happened.
        assert with_gap.index > without.index

    def test_too_little_history_for_any_pollutant_is_none(self) -> None:
        """Long series, but nothing in it: no mean is invented."""
        assert compute_naqi_trailing([row(), row(), row()]) is None

    def test_a_negative_reading_is_clamped_not_averaged_in(self) -> None:
        """A bad sensor value must not drag the mean below what was measured."""
        trailing = compute_naqi_trailing([row(pm25=-50.0), row(pm25=60.0), row(pm25=60.0)])
        assert trailing is not None
        # Clamped to 0, so the mean is 40 rather than 23.3.
        assert trailing.index == pytest.approx(compute_naqi({"pm25": 40.0}).index, abs=0.01)


class TestConservativeRule:
    def test_higher_trailing_wins(self) -> None:
        instant = compute_naqi({"pm25": 20.0})
        trailing = compute_naqi_trailing([row(pm25=20.0)] * 24 + [row(pm25=100.0)])
        assert trailing is not None
        assert conservative_naqi(instant, trailing).index == trailing.index

    def test_lower_trailing_keeps_the_instantaneous_value(self) -> None:
        """A falling curve must not be made to look worse than it is.

        The rule is "take the higher", not "always use the average". Asserting
        this is what stops someone later replacing `max()` with the trailing
        value on the grounds that averages are more correct.
        """
        instant = compute_naqi({"pm25": 120.0})
        trailing = compute_naqi_trailing([row(pm25=120.0)] * 24 + [row(pm25=10.0)])
        assert trailing is not None
        assert conservative_naqi(instant, trailing).index == instant.index

    def test_ties_keep_the_instantaneous_reading(self) -> None:
        """Deterministic, so an agreeing hour is byte-identical to before."""
        instant = compute_naqi({"pm25": 60.0})
        trailing = compute_naqi_trailing([row(pm25=60.0)] * 24)
        assert trailing is not None
        chosen = conservative_naqi(instant, trailing)
        assert chosen.index == instant.index
        assert chosen.basis == instant.basis
        assert chosen.dominant_pollutant == instant.dominant_pollutant

    def test_no_trailing_value_falls_back_to_the_instantaneous_one(self) -> None:
        """Missing history must not mean "no air-quality reading"."""
        instant = compute_naqi({"pm25": 120.0})
        assert conservative_naqi(instant, None) is instant

    def test_unusable_instant_falls_back_to_trailing(self) -> None:
        """Symmetric: a number beats no number."""
        trailing = compute_naqi_trailing([row(pm25=120.0)] * 24)
        assert trailing is not None
        assert conservative_naqi(compute_naqi({}), trailing).index == trailing.index

    def test_compute_naqi_and_naqi_from_pm_are_unchanged(self) -> None:
        """The public entry points other code and the whole suite depend on."""
        assert compute_naqi({"pm25": 30.0}).index == pytest.approx(50.0, abs=0.01)
        assert naqi_from_pm(pm25=30.0, pm10=50.0).index == pytest.approx(50.0, abs=0.01)
        # Basis is unchanged on both, and both still advertise that the 24h-vs-
        # hourly caveat applies -- the pre-existing test in test_naqi.py relies
        # on both of those.
        assert naqi_from_pm().basis == NAQI_BASIS
        assert compute_naqi({"pm25": 30.0}).basis == NAQI_BASIS


class TestProvenance:
    def test_basis_names_both_inputs(self) -> None:
        assert NAQI_BASIS_INSTANTANEOUS in NAQI_BASIS
        assert NAQI_BASIS_TRAILING in NAQI_BASIS

    def test_basis_still_carries_the_original_caveat(self) -> None:
        """The pre-existing test in test_naqi.py asserts these substrings."""
        assert "24h" in NAQI_BASIS
        assert "hourly" in NAQI_BASIS

    def test_basis_is_parseable(self) -> None:
        """Machine-readable means split-able, not just descriptive prose."""
        assert parse_naqi_basis() == (NAQI_BASIS_INSTANTANEOUS, NAQI_BASIS_TRAILING)
        assert parse_naqi_basis("a+b+c") == ("a", "b", "c")

    def test_the_trailing_result_says_it_is_a_trailing_result(self) -> None:
        trailing = compute_naqi_trailing([row(pm25=60.0)] * 24)
        assert trailing is not None
        assert trailing.result.basis == NAQI_BASIS_TRAILING
        payload = trailing.to_dict()
        assert payload["basis"] == NAQI_BASIS_TRAILING
        assert payload["trailing_hours_used"]["pm25"] == 24
        assert payload["trailing_window_hours"] == 24

    def test_us_aqi_is_still_never_mislabelled(self) -> None:
        trailing = compute_naqi_trailing([row(pm25=60.0)] * 24)
        assert trailing is not None
        assert "us_aqi" not in trailing.to_dict()


# ---------------------------------------------------------------------------
# Through the models and the policy, which is where the number is acted on
# ---------------------------------------------------------------------------


def make_slot(air: HourlyAir, *, temp_c: float = 24.0, is_day: int = 1) -> HourSlot:
    return HourSlot(
        weather=HourlyWeather(
            time=WHEN,
            temp_c=temp_c,
            apparent_c=temp_c,
            precip_mm=0.0,
            precip_prob=5.0,
            humidity=60.0,
            wind_kmh=8.0,
            uv_index=3.0,
            weather_code=0,
            is_day=is_day,
        ),
        air=air,
    )


class TestEffectiveValueIsStructural:
    """`naqi_effective` is computed, so no caller can talk the product down.

    Every fixture in the suite, the dataset builder and the eval harness build
    `HourlyAir` directly. A stored "effective" field could be set to anything by
    any of them; a computed `max` cannot.
    """

    def test_effective_is_the_max_of_the_two(self) -> None:
        low = HourlyAir(time=WHEN, naqi=40.0, naqi_trailing=120.0)
        high = HourlyAir(time=WHEN, naqi=120.0, naqi_trailing=40.0)
        assert low.naqi_effective == 120.0
        assert high.naqi_effective == 120.0

    def test_effective_band_follows_the_effective_value(self) -> None:
        air = HourlyAir(time=WHEN, naqi=40.0, naqi_trailing=120.0)
        assert air.naqi_effective_band == "moderate"
        assert air.naqi_effective_band == band_for_index(air.naqi_effective).value

    def test_no_trailing_value_leaves_the_instantaneous_one_alone(self) -> None:
        air = HourlyAir(time=WHEN, naqi=74.0)
        assert air.naqi_effective == 74.0
        assert not air.naqi_uses_trailing_mean

    def test_uses_trailing_mean_is_reported(self) -> None:
        assert HourlyAir(time=WHEN, naqi=40.0, naqi_trailing=120.0).naqi_uses_trailing_mean
        assert not HourlyAir(time=WHEN, naqi=120.0, naqi_trailing=120.0).naqi_uses_trailing_mean

    def test_naive_slot_follows_the_effective_reading(self) -> None:
        weather = HourlyWeather(time=WHEN)
        with_only_trailing = HourSlot(
            weather=weather, air=HourlyAir(time=WHEN, naqi=None, naqi_trailing=180.0)
        )
        assert not with_only_trailing.naive
        assert HourSlot(weather=weather, air=HourlyAir(time=WHEN)).naive

    def test_the_frozen_model_cannot_be_coaxed_into_a_lower_number(self) -> None:
        """A stored field would be settable; this one is not.

        Worth asserting explicitly: `naqi_effective` has no setter, so the safety
        property cannot be quietly bypassed later by someone who finds the
        computed value inconvenient.
        """
        air = HourlyAir(time=WHEN, naqi=40.0, naqi_trailing=120.0)
        with pytest.raises((AttributeError, ValueError)):
            air.naqi_effective = 40.0  # type: ignore[misc]


class TestPolicyUsesTheEffectiveValue:
    def test_a_moderate_hour_on_a_poor_day_is_not_a_go(self) -> None:
        """The end-to-end safety claim, in the scorer's own vocabulary.

        At 07:00 the hour's own PM2.5 of ~98 implies Moderate (index 158.8),
        which the policy is happy to call a GO. The trailing mean over the hours
        behind it is 229.9 -> Poor, and Poor means WAIT. The policy must read
        the trailing one.
        """
        curve = diurnal_pm25_curve()
        trailing = compute_naqi_trailing(curve[:8])
        assert trailing is not None
        instant = compute_naqi(curve[7])
        assert band_for_index(instant.index).value == "moderate"
        assert band_for_index(trailing.index).value == "poor"

        decision_old, _ = heuristic_decision(make_slot(HourlyAir(time=WHEN, naqi=instant.index)))
        decision_new, reasons = heuristic_decision(
            make_slot(HourlyAir(time=WHEN, naqi=instant.index, naqi_trailing=trailing.index))
        )

        assert decision_old is Decision.GO
        assert decision_new is Decision.WAIT
        assert any("NAQI" in r for r in reasons)

    def test_the_afternoon_dip_is_banded_moderate_not_satisfactory(self) -> None:
        """The headline case from the bug report, in band terms.

        14:00 reads Satisfactory on its own hour and Moderate on the preceding
        hours' mean. Moderate is the band Baahar must show, because that is the
        band of the number it acts on.
        """
        curve = diurnal_pm25_curve()
        trailing = compute_naqi_trailing(curve[:15])
        assert trailing is not None
        instant = compute_naqi(curve[14])
        assert band_for_index(instant.index).value == "satisfactory"
        assert band_for_index(trailing.index).value == "moderate"
        assert conservative_naqi(instant, trailing).band.value == "moderate"

    def test_the_policy_is_never_more_permissive_than_before(self) -> None:
        """The threshold values are unchanged, so the rule can only tighten.

        Same slot, same weather, only the air reading differs: whatever the
        policy said for the instantaneous value it must not relax for the
        effective one.
        """
        rank = {Decision.GO: 0, Decision.WAIT: 1, Decision.SKIP: 2}
        for pm25_inst, pm25_trail in [(20.0, 100.0), (60.0, 130.0), (95.0, 96.0), (10.0, 10.0)]:
            old = make_slot(HourlyAir(time=WHEN, naqi=compute_naqi({"pm25": pm25_inst}).index))
            new = make_slot(
                HourlyAir(
                    time=WHEN,
                    naqi=compute_naqi({"pm25": pm25_inst}).index,
                    naqi_trailing=compute_naqi({"pm25": pm25_trail}).index,
                )
            )
            old_decision, _ = heuristic_decision(old)
            new_decision, _ = heuristic_decision(new)
            assert rank[new_decision] >= rank[old_decision], (pm25_inst, pm25_trail)

    def test_features_use_the_effective_value(self) -> None:
        """The model column must not be trained on optimistic air."""
        curve = diurnal_pm25_curve()
        trailing = compute_naqi_trailing(curve[:15])
        assert trailing is not None
        instant = compute_naqi(curve[14])
        slot = make_slot(HourlyAir(time=WHEN, naqi=instant.index, naqi_trailing=trailing.index))
        assert features_from_slot(slot)["naqi"] == trailing.index

    def test_policy_thresholds_are_unchanged(self) -> None:
        """Pinned so a future 'helpful' adjustment has to be a deliberate edit."""
        from baahar.features import (
            APPARENT_WAIT_C,
            HEAT_STRESS_APPARENT_C,
            NAQI_SKIP,
            NAQI_WAIT,
            PRECIP_MIN_MM_FOR_PROB,
            PRECIP_SKIP_MM,
            PRECIP_WAIT_PROB,
            RAIN_PROB_SKIP,
        )

        assert NAQI_SKIP == 300.0
        assert NAQI_WAIT == 200.0
        assert PRECIP_SKIP_MM == 2.5
        assert PRECIP_MIN_MM_FOR_PROB == 0.5
        assert PRECIP_WAIT_PROB == 40.0
        assert APPARENT_WAIT_C == 30.0
        assert HEAT_STRESS_APPARENT_C == 35.0
        assert RAIN_PROB_SKIP == 70.0


# ---------------------------------------------------------------------------
# Through parse_air, so the whole pipeline is covered and not just the library
# ---------------------------------------------------------------------------


def openmeteo_payload(curve: list[dict[str, float]], hours: int = 24) -> dict:
    """Wrap Baahar readings in the Open-Meteo payload shape parse_air expects."""
    start = datetime(2026, 10, 6, 0, 0, tzinfo=UTC)
    return {
        "hourly": {
            "time": [(start + timedelta(hours=i)).isoformat() for i in range(len(curve))],
            "pm2_5": [r.get("pm25") for r in curve],
            "pm10": [r.get("pm10") for r in curve],
        }
    }


class TestParseAir:
    def test_every_hour_carries_both_readings_and_its_history(self) -> None:
        hours = parse_air(openmeteo_payload(diurnal_pm25_curve(hours=30)))
        assert len(hours) == 30
        # The first two hours have too little history for a trailing mean at all.
        assert hours[0].naqi_trailing is None
        assert hours[0].naqi_trailing_hours == 0
        assert hours[1].naqi_trailing is None
        # By hour 24 there is a full 24-hour window behind it.
        assert hours[24].naqi_trailing_hours == 24
        assert hours[24].naqi_trailing is not None
        # Hour 24 is back at the peak, so here the instantaneous reading wins
        # and the trailing mean is the one that is *not* acted on.
        assert hours[24].naqi > hours[24].naqi_trailing
        assert not hours[24].naqi_uses_trailing_mean

    def test_instantaneous_field_is_unchanged_in_shape_and_meaning(self) -> None:
        """`naqi` still holds the breakpoints-on-this-hour value.

        The eval dataset and the recorded artifacts are shaped around this
        field, and downstream code reads it. It must not be quietly repointed
        at the trailing value.
        """
        curve = diurnal_pm25_curve()
        hours = parse_air(openmeteo_payload(curve))
        for i, hour in enumerate(hours):
            # parse_air rounds to one decimal, hence the 0.05 tolerance.
            assert hour.naqi == pytest.approx(compute_naqi(curve[i]).index, abs=0.051)

    def test_effective_is_never_below_instantaneous_over_a_whole_day(self) -> None:
        curve = diurnal_pm25_curve(hours=48)
        hours = parse_air(openmeteo_payload(curve))
        raised = 0
        for hour in hours:
            if hour.naqi is None:
                continue
            assert hour.naqi_effective >= hour.naqi
            if hour.naqi_trailing is not None:
                assert hour.naqi_effective == max(hour.naqi, hour.naqi_trailing)
                raised += hour.naqi_effective > hour.naqi
            # The band shown is the band of the number acted on.
            assert hour.naqi_band == band_for_index(hour.naqi_effective).value
        assert raised > 0, "the day must actually exercise the conservative rule"

    def test_the_afternoon_dip_is_reported_as_moderate_not_satisfactory(self) -> None:
        """The bug report's headline case, end to end through the parser."""
        hours = parse_air(openmeteo_payload(diurnal_pm25_curve()))
        afternoon = hours[14]
        assert afternoon.naqi is not None
        assert band_for_index(afternoon.naqi).value == "satisfactory"
        assert afternoon.naqi_effective_band == "moderate"
        assert afternoon.naqi_uses_trailing_mean

    def test_an_hour_with_no_readings_is_still_none(self) -> None:
        """Missing is missing. No trailing value is invented without history."""
        payload = {
            "hourly": {
                "time": [f"2026-10-06T{h:02d}:00" for h in range(6)],
                "pm2_5": [None] * 6,
                "pm10": [None] * 6,
            }
        }
        hours = parse_air(payload)
        assert all(h.naqi is None for h in hours)
        assert all(h.naqi_trailing is None for h in hours)
        assert all(h.naqi_effective is None for h in hours)

    def test_one_missing_hour_does_not_break_the_window(self) -> None:
        curve = diurnal_pm25_curve(hours=30)
        payload = openmeteo_payload(curve)
        # Drop the whole hour, both variables, so the hour itself is unusable.
        payload["hourly"]["pm2_5"][5] = None
        payload["hourly"]["pm10"][5] = None
        hours = parse_air(payload)
        assert hours[5].naqi is None
        # ...but the six hours behind it still average, so the hour is not
        # reported as having no air-quality history at all.
        assert hours[5].naqi_trailing is not None
        assert hours[5].naqi_effective == hours[5].naqi_trailing
        assert hours[5].naqi_uses_trailing_mean
        assert hours[24].naqi_trailing is not None

    def test_the_offline_fixture_still_produces_both_readings(self) -> None:
        """The recorded fixture is the offline path, so it must go through this too."""
        from baahar.air import FIXTURE_NAME
        from baahar.http_client import load_sample

        payload = load_sample(FIXTURE_NAME)
        assert payload is not None, "the recorded fixture must exist"
        hours = parse_air(payload)
        assert hours
        for hour in hours:
            if hour.naqi is None:
                continue
            assert hour.naqi_effective >= hour.naqi
            assert hour.naqi_band == band_for_index(hour.naqi_effective).value
