"""Indian NAQI correctness.

These tests are the guard rail on the single most safety-relevant number in the
product. They check three things:

1. Breakpoint boundaries land exactly where CPCB's table says they do.
2. The overall index is the *worst* sub-index, per CPCB -- not an average.
3. Unit conversions are right, especially CO (µg/m³ in, mg/m³ breakpoints).
"""

from __future__ import annotations

import math

import pytest

from baahar.naqi import (
    NAQI_BASIS,
    POLLUTANTS,
    band_for_index,
    band_index_range,
    compute_naqi,
    naqi_from_pm,
    pollutant_table,
)


class TestBreakpoints:
    @pytest.mark.parametrize(
        ("pm25", "expected_index"),
        [
            (0, 0),
            (30, 50),  # Good / Satisfactory boundary
            (60, 100),  # Satisfactory / Moderate
            (90, 200),  # Moderate / Poor
            (120, 300),  # Poor / Severe
            (250, 400),  # Severe / Hazardous
        ],
    )
    def test_pm25_boundaries_are_exact(self, pm25: float, expected_index: float) -> None:
        """CPCB boundaries must not be off by rounding."""
        assert compute_naqi({"pm25": pm25}).index == pytest.approx(expected_index, abs=0.01)

    @pytest.mark.parametrize(
        ("pm10", "expected_index"),
        [(0, 0), (50, 50), (100, 100), (250, 200), (350, 300), (430, 400)],
    )
    def test_pm10_boundaries_are_exact(self, pm10: float, expected_index: float) -> None:
        assert compute_naqi({"pm10": pm10}).index == pytest.approx(expected_index, abs=0.01)

    def test_linear_interpolation_inside_a_band(self) -> None:
        # PM2.5 45 sits midway between 30 (->50) and 60 (->100).
        assert compute_naqi({"pm25": 45}).index == pytest.approx(75.5, abs=0.1)

    def test_above_top_breakpoint_saturates_at_500(self) -> None:
        """CPCB publishes no band above 250 ug/m3 for PM2.5; we clamp at 500."""
        result = compute_naqi({"pm25": 10_000})
        assert result.index == 500.0
        assert result.band.value == "hazardous"

    def test_monotonic_in_concentration(self) -> None:
        """A higher concentration must never lower the index."""
        previous = -1.0
        for pm25 in range(0, 400, 5):
            index = compute_naqi({"pm25": float(pm25)}).index
            assert index >= previous, f"index dropped at pm2.5={pm25}"
            previous = index


class TestWorstSubIndex:
    def test_overall_is_the_max_sub_index_not_the_mean(self) -> None:
        # PM2.5 implies ~200; PM10 implies ~20. CPCB takes the worse of the two.
        result = compute_naqi({"pm25": 90.0, "pm10": 10.0})
        assert result.index == pytest.approx(200.0, abs=0.01)
        assert result.sub_indices["pm25"] > result.sub_indices["pm10"]

    def test_dominant_pollutant_is_named(self) -> None:
        result = compute_naqi({"pm25": 20.0, "pm10": 400.0})
        assert result.dominant_pollutant == "pm10"
        assert result.dominant_label == "PM10"

    def test_dominant_is_deterministic_on_ties(self) -> None:
        """Two equal sub-indices must always resolve the same way."""
        first = compute_naqi({"pm25": 30.0, "pm10": 50.0})
        second = compute_naqi({"pm10": 50.0, "pm25": 30.0})
        assert first.dominant_pollutant == second.dominant_pollutant


class TestUnits:
    def test_co_is_converted_from_ugm3_to_mgm3(self) -> None:
        """Open-Meteo reports CO in ug/m3; CPCB breakpoints are mg/m3.

        2000 ug/m3 == 2.0 mg/m3, which is the top of the Satisfactory band
        (index 100). Without the /1000 conversion this would have read as
        2 000 mg/m3 and saturated at 500.
        """
        result = compute_naqi({"co": 2000.0})
        assert POLLUTANTS["co"].source_unit == "µg/m³"
        assert POLLUTANTS["co"].cpcb_unit == "mg/m³"
        assert result.sub_indices["co"] == pytest.approx(100.0, abs=0.01)
        assert result.index < 200, "CO conversion must not saturate the index"

    def test_uncorrected_co_would_have_saturated(self) -> None:
        """Guards the regression that motivated the unit conversion."""
        assert compute_naqi({"co": 2000.0}).index != 500.0

    def test_a_plausible_bengaluru_reading(self) -> None:
        """A clean-ish October Bengaluru hour is Good on the Indian scale.

        PM2.5 of 28 sits inside the CPCB Good band (0-30), so the honest answer
        is "Good", not "Moderate" -- a reminder that these are Indian
        breakpoints and not US ones, which would rate the same reading worse.
        """
        result = compute_naqi({"pm25": 28.0, "pm10": 45.0, "no2": 22.0})
        assert result.band.value == "good"
        assert result.sub_indices["pm25"] == pytest.approx(46.7, abs=0.1)
        assert result.sub_indices["pm10"] == pytest.approx(45.0, abs=0.1)
        assert result.sub_indices["no2"] == pytest.approx(27.5, abs=0.1)
        assert result.dominant_pollutant == "pm25"

    def test_a_dirty_bengaluru_reading_is_poor(self) -> None:
        result = compute_naqi({"pm25": 100.0, "pm10": 260.0})
        assert result.band.value in {"poor", "severe"}
        assert result.index >= 200


class TestBands:
    @pytest.mark.parametrize(
        ("index", "band"),
        [
            (0, "good"),
            (50, "good"),
            (51, "satisfactory"),
            (100, "satisfactory"),
            (101, "moderate"),
            (200, "moderate"),
            (201, "poor"),
            (300, "poor"),
            (301, "severe"),
            (400, "severe"),
            (401, "hazardous"),
            (500, "hazardous"),
        ],
    )
    def test_band_boundaries(self, index: int, band: str) -> None:
        assert band_for_index(index).value == band

    def test_out_of_range_clamps(self) -> None:
        assert band_for_index(900).value == "hazardous"
        assert band_for_index(-5).value == "good"
        assert band_for_index(None) is None
        assert band_for_index(float("nan")) is None

    def test_band_ranges_round_trip(self) -> None:
        for band in ("good", "moderate", "hazardous"):
            low, high = band_index_range(band)
            assert band_for_index(low).value == band
            assert band_for_index(high).value == band


class TestMissingData:
    def test_no_readings_is_unusable_not_a_fake_zero(self) -> None:
        result = compute_naqi({})
        assert not result.is_usable
        assert math.isnan(result.index)
        assert result.band is None

    def test_nulls_are_treated_as_missing(self) -> None:
        result = compute_naqi({"pm25": None, "pm10": None})
        assert not result.is_usable

    def test_partial_readings_are_labelled(self) -> None:
        result = compute_naqi({"pm25": 20.0})
        assert result.is_usable
        assert "PM10" in result.missing

    def test_unknown_pollutants_are_ignored(self) -> None:
        result = compute_naqi({"pm25": 20.0, "unobtainium": 999.0})
        assert result.is_usable


class TestProvenance:
    def test_basis_is_carried_on_every_result(self) -> None:
        """The 24h-vs-hourly caveat must travel with the number."""
        assert "24h" in NAQI_BASIS
        assert "hourly" in NAQI_BASIS
        assert naqi_from_pm(pm25=30.0).basis == NAQI_BASIS
        assert naqi_from_pm(pm25=30.0).to_dict()["basis"] == NAQI_BASIS

    def test_us_aqi_is_never_mislabelled(self) -> None:
        """A US AQI number must not survive anywhere in our payload."""
        payload = naqi_from_pm(pm25=30.0).to_dict()
        assert "us_aqi" not in payload
        assert "aqi" not in {k for k in payload if k != "naqi"}

    def test_pollutant_table_exposes_eight_cpcb_pollutants(self) -> None:
        assert len(pollutant_table()) == 8
        keys = {row["key"] for row in pollutant_table()}
        assert keys == {"pm25", "pm10", "no2", "o3", "co", "so2", "nh3", "pb"}

    def test_every_table_has_six_bands(self) -> None:
        for row in pollutant_table():
            assert len(row["breakpoints"]) == 6, row["key"]