"""Open-Meteo air-quality forecast + Indian NAQI conversion.

Endpoint: https://air-quality-api.open-meteo.com/v1/air-quality  (keyless)

This module is where Baahar earns its honesty claim. Two things are deliberate:

* **Indian NAQI, not US AQI.** Open-Meteo returns ``us_aqi`` (the EPA scale).
  Baahar never shows that number as "AQI". It recomputes the CPCB Indian NAQI
  from raw concentrations via :mod:`baahar.naqi`, and keeps ``us_aqi`` only as a
  hidden comparison field.
* **Missing is missing.** If PM2.5 is ``null`` for an hour, that hour's NAQI is
  ``None`` and the scorer is told the hour is unusable. It does not get filled
  with a cheerful 0.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from .config import get_settings
from .http_client import UpstreamError, get_json, load_sample
from .models import DataSource, HourlyAir, slice_from_now
from .naqi import NAQI_BASIS, compute_naqi

log = logging.getLogger(__name__)

AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
FIXTURE_NAME = "openmeteo_air.json"

HOURLY_VARS = [
    "pm10",
    "pm2_5",
    "carbon_monoxide",
    "nitrogen_dioxide",
    "sulphur_dioxide",
    "ozone",
    "ammonia",
]

#: Open-Meteo air-quality variable -> Baahar pollutant key
VAR_TO_KEY = {
    "pm2_5": "pm25",
    "pm10": "pm10",
    "carbon_monoxide": "co",
    "nitrogen_dioxide": "no2",
    "sulphur_dioxide": "so2",
    "ozone": "o3",
    "ammonia": "nh3",
}


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


def parse_air(payload: dict[str, Any]) -> list[HourlyAir]:
    """Turn a raw Open-Meteo air-quality payload into NAQI-bearing hours."""
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    us_aqi = hourly.get("us_aqi")

    out: list[HourlyAir] = []
    for i, raw_time in enumerate(times):
        readings: dict[str, Any] = {}
        values: dict[str, float | None] = {}
        for var, key in VAR_TO_KEY.items():
            val = _num(hourly.get(var), i)
            values[key] = val
            if val is not None:
                readings[key] = val

        naqi = compute_naqi(readings) if readings else compute_naqi({})

        out.append(
            HourlyAir(
                time=datetime.fromisoformat(raw_time),
                **values,
                naqi=None if not naqi.is_usable else round(naqi.index, 1),
                naqi_band=naqi.band.value if naqi.band else None,
                naqi_band_label=naqi.band_label if naqi.is_usable else None,
                naqi_health_impact=naqi.health_impact if naqi.is_usable else None,
                dominant_pollutant=naqi.dominant_pollutant if naqi.is_usable else None,
                dominant_label=naqi.dominant_label if naqi.is_usable else None,
                naqi_basis=NAQI_BASIS,
                us_aqi_reference=_num(us_aqi, i),
            )
        )
    return out


def fetch_air(
    *,
    lat: float | None = None,
    lon: float | None = None,
    hours: int | None = None,
    timezone: str | None = None,
    offline: bool | None = None,
) -> tuple[list[HourlyAir], DataSource]:
    """Fetch hourly air quality, falling back to the recorded sample on failure."""
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
            "hourly": ",".join(HOURLY_VARS + ["us_aqi"]),
            "forecast_days": max(2, -(-hours // 24) + 1),
            "timezone": timezone,
            "past_days": 1,
        }
        try:
            payload = get_json(AIR_URL, params)
            hours_data = parse_air(payload)
            if hours_data:
                return slice_from_now(hours_data, hours), DataSource.LIVE
            log.warning("Open-Meteo AQ returned no hourly rows; using fixture")
        except UpstreamError as exc:
            log.warning("air-quality live fetch failed (%s); falling back to fixture", exc)

    payload = load_sample(FIXTURE_NAME)
    if payload is None:
        raise UpstreamError(
            "Open-Meteo air-quality is unreachable and no recorded fixture exists. "
            "Run `uv run python scripts/record_samples.py` once you have network."
        )
    return slice_from_now(parse_air(payload), hours), DataSource.FIXTURE
