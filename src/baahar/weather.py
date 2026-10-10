"""Open-Meteo hourly forecast client.

Endpoint: https://api.open-meteo.com/v1/forecast  (keyless, CC BY 4.0)

Two properties matter more than features here:

1. **It never blocks.** Every call has a timeout and a bounded retry count.
2. **It never lies about being offline.** If the network fails we fall back to a
   *recorded* response under ``data/samples/`` and label the result
   ``DataSource.FIXTURE`` all the way up to the UI, so nobody mistakes replayed
   data for a live forecast.
"""

from __future__ import annotations

import logging
from typing import Any

from .config import get_settings
from .http_client import UpstreamError, get_json, load_sample
from .models import (
    DataSource,
    HourlyWeather,
    WeatherSeverity,
    as_payload_time,
    payload_timezone,
    slice_from_now,
)

log = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FIXTURE_NAME = "openmeteo_forecast.json"

HOURLY_VARS = [
    "temperature_2m",
    "apparent_temperature",
    "precipitation",
    "precipitation_probability",
    "relative_humidity_2m",
    "wind_speed_10m",
    "uv_index",
    "weather_code",
    "is_day",
]

#: WMO 4677 weather codes, collapsed to the categories Baahar actually acts on.
WMO_CATEGORIES: dict[int, WeatherSeverity] = {
    0: WeatherSeverity.CLEAR,
    1: WeatherSeverity.CLEAR,
    2: WeatherSeverity.CLOUD,
    3: WeatherSeverity.CLOUD,
    45: WeatherSeverity.FOG,
    48: WeatherSeverity.FOG,
    51: WeatherSeverity.DRIZZLE,
    53: WeatherSeverity.DRIZZLE,
    55: WeatherSeverity.DRIZZLE,
    56: WeatherSeverity.DRIZZLE,
    57: WeatherSeverity.DRIZZLE,
    61: WeatherSeverity.RAIN,
    63: WeatherSeverity.RAIN,
    65: WeatherSeverity.RAIN,
    66: WeatherSeverity.RAIN,
    67: WeatherSeverity.RAIN,
    71: WeatherSeverity.SNOW,
    73: WeatherSeverity.SNOW,
    75: WeatherSeverity.SNOW,
    77: WeatherSeverity.SNOW,
    80: WeatherSeverity.SHOWERS,
    81: WeatherSeverity.SHOWERS,
    82: WeatherSeverity.SHOWERS,
    85: WeatherSeverity.SNOW,
    86: WeatherSeverity.SNOW,
    95: WeatherSeverity.THUNDERSTORM,
    96: WeatherSeverity.THUNDERSTORM,
    99: WeatherSeverity.THUNDERSTORM,
}

WMO_LABELS: dict[int, str] = {
    0: "clear",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "freezing fog",
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    56: "freezing drizzle",
    57: "freezing drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    66: "freezing rain",
    67: "freezing rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    77: "snow grains",
    80: "light showers",
    81: "showers",
    82: "violent showers",
    85: "snow showers",
    86: "snow showers",
    95: "thunderstorm",
    96: "thunderstorm with hail",
    99: "thunderstorm with hail",
}


def weather_category(code: int | None) -> WeatherSeverity | None:
    """Collapse a WMO code to a Baahar severity category."""
    if code is None:
        return None
    return WMO_CATEGORIES.get(int(code))


def weather_label(code: int | None) -> str:
    if code is None:
        return "unknown"
    return WMO_LABELS.get(int(code), f"code {code}")


def _num(series: Any, i: int) -> float | None:
    if not isinstance(series, list) or i >= len(series):
        return None
    val = series[i]
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def parse_weather(payload: dict[str, Any]) -> list[HourlyWeather]:
    """Turn a raw Open-Meteo forecast payload into typed hours."""
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    tz = payload_timezone(payload)
    out: list[HourlyWeather] = []
    for i, raw_time in enumerate(times):
        code = _num(hourly.get("weather_code"), i)
        out.append(
            HourlyWeather(
                time=as_payload_time(raw_time, tz),
                temp_c=_num(hourly.get("temperature_2m"), i),
                apparent_c=_num(hourly.get("apparent_temperature"), i),
                precip_mm=_num(hourly.get("precipitation"), i),
                precip_prob=_num(hourly.get("precipitation_probability"), i),
                humidity=_num(hourly.get("relative_humidity_2m"), i),
                wind_kmh=_num(hourly.get("wind_speed_10m"), i),
                uv_index=_num(hourly.get("uv_index"), i),
                weather_code=int(code) if code is not None else None,
                is_day=int(_num(hourly.get("is_day"), i) or 0),
            )
        )
    return out


def fetch_weather(
    *,
    lat: float | None = None,
    lon: float | None = None,
    hours: int | None = None,
    timezone: str | None = None,
    offline: bool | None = None,
) -> tuple[list[HourlyWeather], DataSource]:
    """Fetch hourly forecast, falling back to the recorded sample on failure."""
    settings = get_settings()
    lat = settings.lat if lat is None else lat
    lon = settings.lon if lon is None else lon
    hours = settings.forecast_hours if hours is None else hours
    timezone = settings.timezone if timezone is None else timezone
    offline = settings.offline if offline is None else offline

    if not offline:
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(HOURLY_VARS),
            "forecast_days": max(2, -(-hours // 24) + 1),
            "timezone": timezone,
            "past_days": 1,  # keep "now" inside the series for slot alignment
        }
        try:
            payload = get_json(FORECAST_URL, params)
            hours_data = parse_weather(payload)
            if hours_data:
                return slice_from_now(hours_data, hours), DataSource.LIVE
            log.warning("Open-Meteo forecast returned no hourly rows; using fixture")
        except UpstreamError as exc:
            log.warning("forecast live fetch failed (%s); falling back to fixture", exc)

    payload = load_sample(FIXTURE_NAME)
    if payload is None:
        raise UpstreamError(
            "Open-Meteo forecast is unreachable and no recorded fixture exists. "
            "Run `uv run python scripts/record_samples.py` once you have network."
        )
    return slice_from_now(parse_weather(payload), hours), DataSource.FIXTURE
