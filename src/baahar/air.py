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
* **Two readings, one conservative decision.** CPCB's breakpoints are defined on
  24-hour mean concentrations (8-hour for O3 and CO), but this module is handed
  hourly values. Applying the breakpoints to a single hour can only ever
  understate a polluted day -- the CPCB bands are piecewise-linear and steeper at
  low concentrations, so a calm afternoon hour reads "Good" while the day it
  belongs to is Poor. So every hour gets both an instantaneous reading and a
  trailing-mean reading, and the product acts on the higher of the two.
  See :func:`baahar.naqi.conservative_naqi`.
* **Hours are in order or the run stops.** ``parse_air`` refuses a payload whose
  ``hourly.time`` is not strictly ascending, because a trailing mean over
  shuffled hours can come out lower than the hours it was measured from.
"""

from __future__ import annotations

import logging
from typing import Any

from .config import get_settings
from .http_client import UpstreamError, get_json, load_sample
from .models import (
    DataSource,
    HourlyAir,
    as_payload_time,
    payload_timezone,
    slice_from_now,
)
from .naqi import (
    NAQI_BASIS,
    assert_chronological,
    compute_naqi,
    compute_naqi_trailing,
    conservative_naqi,
)

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
    """Turn a raw Open-Meteo air-quality payload into NAQI-bearing hours.

    Each hour carries **two** NAQI readings and the product acts on the more
    conservative of them:

    * ``naqi`` -- CPCB breakpoints applied to the hour's own instantaneous
      concentrations. Kept for provenance and because the recorded eval dataset
      is shaped around it.
    * ``naqi_trailing`` -- CPCB breakpoints applied to a trailing mean over each
      pollutant's own CPCB averaging period, which is what the breakpoints were
      defined against in the first place.

    :attr:`HourlyAir.naqi_effective` is their maximum, and it is what the scorer
    reads. ``naqi_trailing_hours`` records how many hours actually backed the
    trailing value, so a short window is visible instead of being passed off as a
    full 24-hour mean.

    This needs no extra network request: the caller already asks for
    ``past_days=1``, so the series carries a day of history ahead of "now".

    Raises ``ValueError`` if the payload's ``hourly.time`` is not strictly
    ascending. A trailing mean over an out-of-order series is silently wrong
    and can come out *lower* than the hours it was measured from, so an
    upstream that returns hours shuffled is a loud failure, not a better day.
    """
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    us_aqi = hourly.get("us_aqi")
    assert_chronological(times, where="Open-Meteo air-quality payload hourly.time")

    # Two passes, because the trailing mean needs the hours *before* the hour
    # being scored. Collecting the readings first turns the second pass into a
    # slice rather than a nested re-parse of the payload per hour.
    history: list[dict[str, Any]] = []
    all_values: list[dict[str, float | None]] = []
    for i, raw_time in enumerate(times):
        readings: dict[str, Any] = {}
        values: dict[str, float | None] = {}
        for var, key in VAR_TO_KEY.items():
            val = _num(hourly.get(var), i)
            values[key] = val
            if val is not None:
                readings[key] = val
        # The hour's own timestamp travels with its readings so
        # `compute_naqi_trailing` can refuse an out-of-order slice instead of
        # averaging across hours that are not in sequence. `compute_naqi`
        # ignores unknown keys, so this costs the instantaneous path nothing.
        readings["time"] = raw_time
        history.append(readings)
        all_values.append(values)

    out: list[HourlyAir] = []
    tz = payload_timezone(payload)
    for i, raw_time in enumerate(times):
        # An hour with no readings at all still gets an (unusable) instantaneous
        # result and no trailing value: `compute_naqi({})` is exactly the
        # "we measured nothing" answer, not a cheerful zero.
        instant = compute_naqi(history[i])
        trailing = compute_naqi_trailing(history[: i + 1])
        effective = conservative_naqi(instant, trailing)

        out.append(
            HourlyAir(
                time=as_payload_time(raw_time, tz),
                **all_values[i],
                naqi=None if not instant.is_usable else round(instant.index, 1),
                naqi_trailing=None if trailing is None else round(trailing.index, 1),
                naqi_trailing_hours=trailing.hours if trailing else 0,
                naqi_band=effective.band.value if effective.band else None,
                naqi_band_label=effective.band_label if effective.is_usable else None,
                naqi_health_impact=effective.health_impact if effective.is_usable else None,
                dominant_pollutant=effective.dominant_pollutant if effective.is_usable else None,
                dominant_label=effective.dominant_label if effective.is_usable else None,
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
