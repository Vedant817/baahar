"""Shared test fixtures.

Every fixture here is either recorded from a real upstream response (see
`data/samples/`) or constructed explicitly. No test depends on the network:
`pytest` must pass on a plane.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from baahar.models import HourlyAir, HourlyWeather, HourSlot, Park

IST = timezone(timedelta(hours=5, minutes=30))
BASE = datetime(2026, 10, 6, 5, 0, tzinfo=IST)


def make_weather(
    offset_hours: int = 0,
    *,
    temp_c: float = 24.0,
    apparent_c: float | None = None,
    precip_mm: float = 0.0,
    precip_prob: float = 5.0,
    humidity: float = 60.0,
    wind_kmh: float = 8.0,
    uv_index: float = 3.0,
    weather_code: int = 0,
    is_day: int = 1,
) -> HourlyWeather:
    return HourlyWeather(
        time=BASE + timedelta(hours=offset_hours),
        temp_c=temp_c,
        apparent_c=temp_c if apparent_c is None else apparent_c,
        precip_mm=precip_mm,
        precip_prob=precip_prob,
        humidity=humidity,
        wind_kmh=wind_kmh,
        uv_index=uv_index,
        weather_code=weather_code,
        is_day=is_day,
    )


def make_air(
    offset_hours: int = 0,
    *,
    pm25: float | None = 20.0,
    pm10: float | None = 40.0,
    naqi: float | None = None,
    band: str | None = None,
    dominant: str | None = None,
) -> HourlyAir:
    """Build an air hour. `naqi` defaults to the value `pm25` implies."""
    if naqi is None and pm25 is not None:
        from baahar.naqi import naqi_from_pm

        computed = naqi_from_pm(pm25=pm25, pm10=pm10)
        naqi = round(computed.index, 1)
        band = computed.band.value if computed.band else None
        dominant = computed.dominant_label
    return HourlyAir(
        time=BASE + timedelta(hours=offset_hours),
        pm25=pm25,
        pm10=pm10,
        naqi=naqi,
        naqi_band=band,
        naqi_band_label=(band or "").capitalize() or None,
        dominant_pollutant=dominant.lower() if dominant else None,
        dominant_label=dominant,
    )


def make_slot(offset_hours: int = 0, **kwargs) -> HourSlot:
    """Build a joined hour. Keyword args are split between weather and air."""
    air_kwargs = {
        k: kwargs.pop(k) for k in ("pm25", "pm10", "naqi", "band", "dominant") if k in kwargs
    }
    return HourSlot(
        weather=make_weather(offset_hours, **kwargs), air=make_air(offset_hours, **air_kwargs)
    )


@pytest.fixture
def make_weather_fixture():
    """`make_weather` as a fixture, for tests that build raw hours."""
    return make_weather


@pytest.fixture
def make_air_fixture():
    """`make_air` as a fixture, for tests that build raw hours."""
    return make_air


@pytest.fixture
def slot():
    """Factory fixture: ``slot(3, pm25=200, temp_c=30)`` builds a joined hour.

    Exposed as a fixture rather than imported from `conftest` so the helpers
    stay a single source of truth without tests depending on the `tests`
    directory being an importable package.
    """
    return make_slot


@pytest.fixture
def go_slot() -> HourSlot:
    """Clean early morning: low PM, mild, dry, daylight."""
    return make_slot(
        0, temp_c=23.0, apparent_c=24.0, precip_prob=5.0, pm25=18.0, pm10=32.0, is_day=1
    )


@pytest.fixture
def hazardous_slot() -> HourSlot:
    """Hazardous air (PM2.5 260 ug/m3 -> NAQI ~409) plus dangerous heat."""
    return make_slot(0, temp_c=37.0, apparent_c=41.0, pm25=260.0, pm10=500.0, is_day=1)


@pytest.fixture
def rain_slot() -> HourSlot:
    return make_slot(
        0, temp_c=26.0, apparent_c=28.0, precip_mm=6.0, precip_prob=95.0, pm25=20.0, is_day=1
    )


@pytest.fixture
def thunder_slot() -> HourSlot:
    return make_slot(
        0, temp_c=26.0, apparent_c=28.0, precip_mm=1.0, precip_prob=80.0, weather_code=95, is_day=1
    )


@pytest.fixture
def night_slot() -> HourSlot:
    return make_slot(0, temp_c=20.0, apparent_c=20.0, pm25=15.0, pm10=25.0, is_day=0)


@pytest.fixture
def missing_air_slot() -> HourSlot:
    return make_slot(0, temp_c=24.0, apparent_c=25.0, pm25=None, pm10=None)


@pytest.fixture
def cubbon() -> Park:
    from baahar.parks import park_by_id

    park = park_by_id("cubbon")
    assert park is not None
    return park
