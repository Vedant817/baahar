"""Optional live CPCB/WAQI station readings.

Forecast data tells you what the *air is expected to be like*. A monitoring
station tells you what it *is*, right now. For a "should I walk out the door in
the next twenty minutes?" question, now beats average.

WAQI (World Air Quality Index, aqicn.org) needs a free token, so this is
strictly optional: with no ``WAQI_TOKEN`` the whole module is inert and the rest
of Baahar does not know it exists.

Endpoint: https://api.waqi.info/feed/geo:{lat};{lon}/  -> observations
Token is passed as a query parameter, per WAQI's documented API.

Honesty note: WAQI reports the **US EPA** AQI scale. Converting an EPA AQI back
into a concentration to derive Indian NAQI would be a lossy round trip through a
different standard. So a station reading is surfaced as `station_us_aqi` and
clearly labelled as the EPA scale, never as Indian NAQI, and it is only ever
used as a *directional cross-check* on the forecast -- never as the number
Baahar prints.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .config import get_settings
from .http_client import UpstreamError, get_json

log = logging.getLogger(__name__)

WAQI_URL = "https://api.waqi.info/feed/geo:{lat};{lon}/"


@dataclass(frozen=True)
class StationReading:
    """One live station observation. ``us_aqi`` is the EPA scale."""

    us_aqi: int | None
    pm25: float | None
    pm10: float | None
    station: str | None
    city: str | None
    observed_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "us_aqi": self.us_aqi,
            "pm25_ug_m3": self.pm25,
            "pm10_ug_m3": self.pm10,
            "station": self.station,
            "city": self.city,
            "observed_at": self.observed_at,
            "scale": "US EPA AQI -- for cross-checking the forecast only",
        }


def fetch_station(
    *, lat: float | None = None, lon: float | None = None, timeout: float | None = None
) -> StationReading | None:
    """Fetch a live station reading, or ``None`` if unavailable.

    Returns ``None`` -- never raises -- for every ordinary condition: no token
    configured, station too far away, HTTP error, malformed payload. A missing
    station must never break a walk decision.
    """
    settings = get_settings()
    token = settings.waqi_token
    if not token:
        log.debug("WAQI_TOKEN not set; skipping live station cross-check")
        return None

    lat = settings.lat if lat is None else lat
    lon = settings.lon if lon is None else lon

    try:
        payload = get_json(
            WAQI_URL.format(lat=lat, lon=lon),
            {"token": token},
            timeout=timeout or min(settings.http_timeout, 8.0),
            retries=1,
        )
    except UpstreamError as exc:
        log.warning("WAQI station fetch failed: %s", exc)
        return None

    data = payload.get("data")
    if not isinstance(data, dict):
        log.warning("WAQI payload had no 'data' object")
        return None
    if data.get("status") == "error":
        log.warning("WAQI returned an error: %s", data.get("data"))
        return None

    iaqi = data.get("iaqi") or {}
    return StationReading(
        us_aqi=_as_int(data.get("aqi")),
        pm25=_as_float(iaqi.get("pm25")),
        pm10=_as_float(iaqi.get("pm10")),
        station=_as_str((data.get("city") or [{}])[0].get("name"))
        if isinstance(data.get("city"), list) and data.get("city")
        else None,
        city=_as_str(data.get("city", {}).get("name"))
        if isinstance(data.get("city"), dict)
        else None,
        observed_at=_as_str(data.get("time", {}).get("iso"))
        if isinstance(data.get("time"), dict)
        else None,
    )


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None