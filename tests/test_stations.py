"""Tests for the optional WAQI station cross-check.

The module is inert without a token, so the interesting behaviour is entirely in
the parsing and the guards. The one guard that earns its own test is the
distance check: on 2026-10-06 a query for Bengaluru returned a station 1,727 km
away in Delhi, with a plausible AQI and a plausible-looking payload. Nothing
about it looked broken except the coordinates.

No test here touches the network.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from baahar import config
from baahar.http_client import UpstreamError
from baahar.stations import (
    MAX_STATION_KM,
    StationReading,
    fetch_station,
    haversine_km,
)

BENGALURU = (12.9716, 77.5946)
#: The station WAQI actually returned for the Bengaluru coordinates.
DELHI = (28.499727, 77.267095)


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """`get_settings` is memoised; clearing the env var alone is not enough."""
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


@pytest.fixture
def with_token(monkeypatch):
    monkeypatch.setenv("WAQI_TOKEN", "test-token-not-real")
    config.get_settings.cache_clear()
    return "test-token-not-real"


def _payload(
    *,
    aqi: int = 89,
    geo: list[float] | None = None,
    name: str = "Bengaluru, Karnataka, India",
    pm25: float | None = 22.0,
) -> dict[str, Any]:
    return {
        "status": "ok",
        "data": {
            "aqi": aqi,
            "city": {"name": name, "geo": geo if geo is not None else list(BENGALURU)},
            "time": {"iso": "2026-10-06T12:00:00+05:30", "s": "1788000000"},
            "iaqi": {"pm25": pm25, "pm10": 48.0},
        },
    }


def _patch_get_json(monkeypatch, payload: Any, error: Exception | None = None):
    """Replace the module's `get_json` so no request is attempted."""

    def fake(url: str, params: dict | None = None, **kwargs: Any) -> dict:
        if error is not None:
            raise error
        return payload

    monkeypatch.setattr("baahar.stations.get_json", fake)
    return fake


# ── Distance ─────────────────────────────────────────────────────────────────


class TestHaversine:
    def test_known_distance(self) -> None:
        # Bengaluru to Delhi is roughly 1,400 km; allow generous slack.
        assert 1400 < haversine_km(*BENGALURU, *DELHI) < 1800

    def test_zero_distance(self) -> None:
        assert haversine_km(12.0, 77.0, 12.0, 77.0) == pytest.approx(0.0)

    def test_short_walk_distance(self) -> None:
        # Cubbon Park to Lalbagh, ~5 km apart in reality.
        d = haversine_km(12.9767, 77.6050, 12.9507, 77.5848)
        assert 3.0 < d < 8.0

    def test_antipodes(self) -> None:
        assert haversine_km(0.0, 0.0, 0.0, 180.0) == pytest.approx(20015, rel=0.01)

    def test_symmetric(self) -> None:
        assert haversine_km(*BENGALURU, *DELHI) == pytest.approx(haversine_km(*DELHI, *BENGALURU))


class TestDistanceGuard:
    def test_far_station_is_discarded(self, with_token, monkeypatch) -> None:
        """The real 2026-10-06 response, verbatim in shape.

        A 1,727 km station carrying a plausible AQI is the failure this guards:
        a Delhi number on a Bengaluru screen, labelled as a local cross-check.
        """
        _patch_get_json(
            monkeypatch,
            _payload(geo=list(DELHI), name="Dr. Karni Singh Shooting Range, Delhi"),
        )
        assert fetch_station(lat=BENGALURU[0], lon=BENGALURU[1]) is None

    def test_nearby_station_is_kept(self, with_token, monkeypatch) -> None:
        _patch_get_json(monkeypatch, _payload())
        reading = fetch_station(lat=BENGALURU[0], lon=BENGALURU[1])
        assert reading is not None
        assert reading.us_aqi == 89
        assert reading.distance_km is not None
        assert reading.distance_km < 1.0

    def test_distance_is_reported(self, with_token, monkeypatch) -> None:
        # Cubbon Park from the city centre: ~1.3 km.
        _patch_get_json(monkeypatch, _payload(geo=[12.9767, 77.6050]))
        reading = fetch_station(lat=BENGALURU[0], lon=BENGALURU[1])
        assert reading is not None
        assert 1.0 < reading.distance_km < 2.0

    def test_guard_boundary_is_generous_enough_for_real_parks(
        self, with_token, monkeypatch
    ) -> None:
        """A Bengaluru park with no station of its own must not lose the cross-check.

        60 km covers the whole city plus a wide margin, so a station at the edge
        of the metro area still counts. The guard is there to catch a different
        city, not to demand a sensor in the park.
        """
        assert MAX_STATION_KM >= 40
        # 30 km away is accepted.
        _patch_get_json(monkeypatch, _payload(geo=[13.17, 77.44]))
        assert fetch_station(lat=BENGALURU[0], lon=BENGALURU[1]) is not None

    def test_missing_geo_is_not_rejected(self, with_token, monkeypatch) -> None:
        """No coordinates means no distance check, not a broken reading.

        Rejecting on absent data would silently disable the feature for any
        payload shape that omits `geo`.
        """
        payload = _payload()
        payload["data"]["city"].pop("geo")
        _patch_get_json(monkeypatch, payload)
        reading = fetch_station(lat=BENGALURU[0], lon=BENGALURU[1])
        assert reading is not None
        assert reading.distance_km is None

    def test_malformed_geo_is_ignored(self, with_token, monkeypatch) -> None:
        for bad in ([1.0], ["a", "b"], {}, None):
            payload = _payload()
            payload["data"]["city"]["geo"] = bad
            _patch_get_json(monkeypatch, payload)
            reading = fetch_station(lat=BENGALURU[0], lon=BENGALURU[1])
            assert reading is not None, f"geo={bad!r} should not reject the reading"
            assert reading.distance_km is None


# ── Payload shapes ───────────────────────────────────────────────────────────


class TestPayloadShapes:
    def test_city_object_is_parsed(self, with_token, monkeypatch) -> None:
        _patch_get_json(monkeypatch, _payload(name="Bengaluru, Karnataka, India"))
        reading = fetch_station()
        assert reading is not None
        assert reading.city == "Bengaluru, Karnataka, India"
        assert reading.station == "Bengaluru, Karnataka, India"

    def test_city_list_is_parsed(self, with_token, monkeypatch) -> None:
        """Some WAQI feeds return `city` as a list; the old code only read the
        object form, so the station name silently vanished."""
        payload = _payload()
        payload["data"]["city"] = [{"name": "KR Market, Bengaluru"}]
        payload["data"]["city"].append("ignored-non-dict")
        _patch_get_json(monkeypatch, payload)
        reading = fetch_station()
        assert reading is not None
        assert reading.station == "KR Market, Bengaluru"

    def test_pollutants_are_parsed(self, with_token, monkeypatch) -> None:
        _patch_get_json(monkeypatch, _payload())
        reading = fetch_station()
        assert reading.pm25 == 22.0
        assert reading.pm10 == 48.0

    def test_observed_time_is_parsed(self, with_token, monkeypatch) -> None:
        _patch_get_json(monkeypatch, _payload())
        reading = fetch_station()
        assert reading.observed_at == "2026-10-06T12:00:00+05:30"

    def test_missing_iaqi_is_tolerated(self, with_token, monkeypatch) -> None:
        payload = _payload()
        payload["data"].pop("iaqi")
        _patch_get_json(monkeypatch, payload)
        reading = fetch_station()
        assert reading is not None
        assert reading.pm25 is None

    def test_non_numeric_pollutant_becomes_none(self, with_token, monkeypatch) -> None:
        payload = _payload(pm25="-")
        _patch_get_json(monkeypatch, payload)
        reading = fetch_station()
        assert reading is not None
        assert reading.pm25 is None

    def test_to_dict_states_the_scale(self, with_token, monkeypatch) -> None:
        """A bare number next to a park name invites the reader to treat it as
        the same scale as the NAQI above it. The dict must say otherwise."""
        _patch_get_json(monkeypatch, _payload())
        d = fetch_station().to_dict()
        assert "US EPA" in d["scale"]
        assert "cross-checking" in d["scale"]

    def test_distance_is_serialised(self, with_token, monkeypatch) -> None:
        _patch_get_json(monkeypatch, _payload(geo=[12.9767, 77.6050]))
        d = fetch_station().to_dict()
        assert d["distance_km"] is not None
        assert isinstance(d["distance_km"], float)


# ── Silent, safe failure ─────────────────────────────────────────────────────


class TestGracefulFailure:
    def test_no_token_means_no_request(self, monkeypatch) -> None:
        monkeypatch.delenv("WAQI_TOKEN", raising=False)
        config.get_settings.cache_clear()
        monkeypatch.setattr(
            "baahar.stations.get_json",
            lambda *a, **k: pytest.fail("must not call WAQI without a token"),
        )
        assert fetch_station() is None

    def test_http_error_returns_none(self, with_token, monkeypatch) -> None:
        _patch_get_json(monkeypatch, None, error=UpstreamError("boom"))
        assert fetch_station() is None

    def test_error_status_returns_none(self, with_token, monkeypatch) -> None:
        _patch_get_json(monkeypatch, {"status": "error", "data": "invalid token"})
        assert fetch_station() is None

    def test_missing_data_returns_none(self, with_token, monkeypatch) -> None:
        _patch_get_json(monkeypatch, {})
        assert fetch_station() is None

    def test_data_that_is_not_a_dict(self, with_token, monkeypatch) -> None:
        _patch_get_json(monkeypatch, {"data": ["unexpected"]})
        assert fetch_station() is None

    def test_never_raises_is_the_contract(self, with_token, monkeypatch) -> None:
        """A missing station must never break a walk decision."""
        for payload in (None, {}, {"data": None}, {"data": 42}, {"data": {"aqi": "x"}}):
            _patch_get_json(monkeypatch, payload)
            assert fetch_station() is None


def test_reading_is_immutable() -> None:
    """Frozen, so a reading cannot be edited after the decision used it."""
    r = StationReading(us_aqi=50, pm25=10.0, pm10=20.0, station=None, city=None, observed_at=None)
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.us_aqi = 60  # type: ignore[misc]
