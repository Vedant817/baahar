"""Offline and failure-mode behaviour.

`AGENTS.md` requires that a failing upstream never produces a cheerful empty
answer. These tests kill the network and assert that Baahar still returns real,
clearly-labelled data rather than an empty 200 or a traceback.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from baahar.air import FIXTURE_NAME as AIR_FIXTURE
from baahar.air import fetch_air, parse_air
from baahar.config import SAMPLES_DIR
from baahar.forecast import fetch_joined, join_slots
from baahar.http_client import UpstreamError, get_json, load_sample, record_sample, sample_meta
from baahar.models import DataSource, WeatherSeverity
from baahar.weather import FIXTURE_NAME as WX_FIXTURE
from baahar.weather import fetch_weather, parse_weather, weather_category


class TestRecordedFixtures:
    """The offline path is only trustworthy if the fixtures are real."""

    def test_forecast_fixture_exists(self) -> None:
        assert (SAMPLES_DIR / WX_FIXTURE).exists(), (
            f"{WX_FIXTURE} missing -- run `uv run python scripts/record_samples.py`"
        )

    def test_air_fixture_exists(self) -> None:
        assert (SAMPLES_DIR / AIR_FIXTURE).exists()

    def test_fixtures_carry_provenance(self) -> None:
        for name in (WX_FIXTURE, AIR_FIXTURE):
            meta = sample_meta(name)
            assert meta.get("recorded_at_utc"), f"{name} has no recording timestamp"
            assert meta.get("source_url", "").startswith("https://")

    def test_fixtures_contain_real_rows(self) -> None:
        payload = load_sample(WX_FIXTURE)
        assert payload is not None
        times = payload["hourly"]["time"]
        assert len(times) >= 24
        # A hand-written stub would not have a plausible Bengaluru temperature.
        temps = [t for t in payload["hourly"]["temperature_2m"] if t is not None]
        assert any(20 <= t <= 45 for t in temps), "fixture temperatures look fabricated"

    def test_meta_is_stripped_on_load(self) -> None:
        payload = load_sample(AIR_FIXTURE)
        assert payload is not None
        assert not any(k.startswith("_baahar") for k in payload)

    def test_missing_sample_returns_none(self) -> None:
        assert load_sample("does_not_exist.json") is None


class TestOfflineMode:
    def test_offline_forecast_uses_the_fixture(self) -> None:
        hours, source = fetch_weather(offline=True)
        assert source is DataSource.FIXTURE
        assert hours
        assert all(h.temp_c is not None for h in hours)

    def test_offline_air_uses_the_fixture(self) -> None:
        hours, source = fetch_air(offline=True)
        assert source is DataSource.FIXTURE
        assert hours
        assert any(h.naqi is not None for h in hours)

    def test_offline_forecast_has_naqi(self) -> None:
        """Offline mode must produce a complete, real plan."""
        hours, _ = fetch_air(offline=True)
        with_naqi = [h for h in hours if h.naqi is not None]
        assert with_naqi, "offline air data has no NAQI at all"
        assert all(0 <= h.naqi <= 500 for h in with_naqi)

    def test_joined_offline_run_is_usable(self) -> None:
        slots, wsrc, asrc = fetch_joined(offline=True)
        assert slots
        assert wsrc is DataSource.FIXTURE
        assert asrc is DataSource.FIXTURE


class TestNetworkFailure:
    @pytest.fixture(autouse=True)
    def _unreachable_transport(self, monkeypatch):
        # A transport failure needs no DNS lookup or actual network request.
        def fail_get(self, url, **kwargs):
            raise httpx.ConnectError("upstream unavailable", request=httpx.Request("GET", url))

        monkeypatch.setattr(httpx.Client, "get", fail_get)

    def test_unreachable_upstream_raises_rather_than_returning_empty(self) -> None:
        with pytest.raises(UpstreamError):
            get_json(
                "https://nonexistent.invalid/endpoint",
                {"a": "b"},
                timeout=1.0,
                retries=0,
            )

    def test_upstream_error_mentions_the_url(self) -> None:
        with pytest.raises(UpstreamError, match="nonexistent.invalid"):
            get_json("https://nonexistent.invalid/x", {}, timeout=1.0, retries=0)

    def test_missing_fixture_and_no_network_raises_clearly(self, monkeypatch, tmp_path) -> None:
        """If there is no fixture either, say so -- do not invent data."""
        from baahar import air as air_mod

        monkeypatch.setattr(air_mod, "load_sample", lambda name: None)
        with pytest.raises(UpstreamError, match="recorded fixture"):
            air_mod.fetch_air(offline=True)


class TestParsing:
    def test_weather_parses_all_requested_variables(self) -> None:
        payload = load_sample(WX_FIXTURE)
        hours = parse_weather(payload)
        first = hours[0]
        for attr in ("temp_c", "apparent_c", "precip_mm", "humidity", "wind_kmh", "weather_code"):
            assert getattr(first, attr) is not None, attr

    def test_air_parses_and_computes_naqi(self) -> None:
        payload = load_sample(AIR_FIXTURE)
        hours = parse_air(payload)
        scored = [h for h in hours if h.naqi is not None]
        assert scored
        assert scored[0].naqi_band in {
            "good",
            "satisfactory",
            "moderate",
            "poor",
            "severe",
            "hazardous",
        }

    def test_nulls_parse_to_none_not_zero(self) -> None:
        payload = {
            "hourly": {
                "time": ["2026-10-06T00:00"],
                "pm2_5": [None],
                "pm10": [None],
            }
        }
        hours = parse_air(payload)
        assert hours[0].pm25 is None
        assert hours[0].naqi is None

    def test_weather_codes_map_to_severity(self) -> None:
        assert weather_category(0) is WeatherSeverity.CLEAR
        assert weather_category(95) is WeatherSeverity.THUNDERSTORM
        assert weather_category(99) is WeatherSeverity.THUNDERSTORM
        assert weather_category(65) is WeatherSeverity.RAIN
        assert weather_category(None) is None
        assert weather_category(1234) is None


class TestJoin:
    def test_hours_are_joined_on_timestamp_not_position(
        self, make_weather_fixture, make_air_fixture
    ) -> None:
        """A positional zip would silently pair the wrong air with the weather.

        The AQ series here starts an hour later than the weather series, so the
        first slot must have no air data -- not a PM reading from the wrong hour.
        """
        weather = [make_weather_fixture(h) for h in range(3)]
        air = [make_air_fixture(h + 1) for h in range(2)]  # deliberately offset
        slots, notes = join_slots(weather, air)

        assert len(slots) == 3
        assert slots[0].air.naqi is None, "misaligned join produced a bogus NAQI"
        assert notes and "unusable" in notes[0]
        assert slots[1].air.naqi is not None

    def test_a_fully_aligned_pair_joins_cleanly(
        self, make_weather_fixture, make_air_fixture
    ) -> None:
        weather = [make_weather_fixture(h) for h in range(3)]
        air = [make_air_fixture(h) for h in range(3)]
        slots, notes = join_slots(weather, air)
        assert not notes
        assert all(s.air.naqi is not None for s in slots)

    def test_slot_time_mirrors_weather_time(self, make_weather_fixture, make_air_fixture) -> None:
        w, a = make_weather_fixture(5), make_air_fixture(5)
        slot = join_slots([w], [a])[0][0]
        assert slot.time == w.time == a.time


class TestRecordSample:
    def test_round_trip_preserves_the_body(self, tmp_path, monkeypatch) -> None:
        from baahar import http_client

        monkeypatch.setattr(http_client, "SAMPLES_DIR", tmp_path)
        payload = {"hourly": {"time": ["2026-10-06T00:00"], "temperature_2m": [23.4]}}
        record_sample("unit_test.json", payload, url="https://example.invalid/x")
        loaded = load_sample("unit_test.json")
        assert loaded == payload

    def test_provenance_is_recorded(self, tmp_path, monkeypatch) -> None:
        from baahar import http_client

        monkeypatch.setattr(http_client, "SAMPLES_DIR", tmp_path)
        record_sample("unit_test2.json", {"a": 1}, url="https://example.invalid/y")
        meta = sample_meta("unit_test2.json")
        assert meta["source_url"] == "https://example.invalid/y"
        assert meta["recorded_at_utc"].endswith("Z")
        assert Path(tmp_path / "unit_test2.json").exists()

    def test_recorded_file_is_valid_json(self) -> None:
        for name in (WX_FIXTURE, AIR_FIXTURE):
            raw = json.loads((SAMPLES_DIR / name).read_text(encoding="utf-8"))
            assert "hourly" in raw
