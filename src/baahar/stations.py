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
import math
from dataclasses import dataclass
from typing import Any

from .config import get_settings
from .http_client import UpstreamError, get_json

log = logging.getLogger(__name__)

WAQI_URL = "https://api.waqi.info/feed/geo:{lat};{lon}/"

#: How far the returned station may be from the requested point, in km.
#:
#: This guard exists because of a real observation on 2026-10-06: querying
#: ``geo:12.9716;77.5946/`` (Bengaluru) returned "Dr. Karni Singh Shooting Range,
#: Delhi" at 28.499727, 77.267095 -- roughly 1,700 km away -- with a perfectly
#: plausible-looking AQI of 89. Accepting it would have put a Delhi air-quality
#: number on a Bengaluru screen next to the park name, labelled as a local
#: cross-check. A station that far away is not a cross-check of anything, it is a
#: different city, so it is discarded rather than shown with a caveat nobody
#: would read.
MAX_STATION_KM = 60.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two points."""
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class StationReading:
    """One live station observation. ``us_aqi`` is the EPA scale."""

    us_aqi: int | None
    pm25: float | None
    pm10: float | None
    station: str | None
    city: str | None
    observed_at: str | None
    #: Distance from the requested point, when WAQI reported coordinates.
    distance_km: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "us_aqi": self.us_aqi,
            "pm25_ug_m3": self.pm25,
            "pm10_ug_m3": self.pm10,
            "station": self.station,
            "city": self.city,
            "observed_at": self.observed_at,
            "distance_km": (round(self.distance_km, 1) if self.distance_km is not None else None),
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

    if not isinstance(payload, dict):
        log.warning("WAQI returned a non-object payload")
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        log.warning("WAQI payload had no 'data' object")
        return None
    if data.get("status") == "error":
        log.warning("WAQI returned an error: %s", data.get("data"))
        return None

    # `city` is an object for the geo feed, and a list for some search feeds.
    city_obj: dict[str, Any] = {}
    raw_city = data.get("city")
    if isinstance(raw_city, dict):
        city_obj = raw_city
    elif isinstance(raw_city, list) and raw_city and isinstance(raw_city[0], dict):
        city_obj = raw_city[0]

    # Reject a station in a different city. See MAX_STATION_KM for why.
    distance_km: float | None = None
    geo = city_obj.get("geo")
    if isinstance(geo, (list, tuple)) and len(geo) == 2:
        slat, slon = _as_float(geo[0]), _as_float(geo[1])
        if slat is not None and slon is not None:
            distance_km = haversine_km(lat, lon, slat, slon)
            if distance_km > MAX_STATION_KM:
                log.warning(
                    "WAQI returned a station %.0f km away (%s); discarding it as a "
                    "cross-check for %s",
                    distance_km,
                    city_obj.get("name"),
                    settings.city,
                )
                return None

    iaqi = data.get("iaqi") if isinstance(data.get("iaqi"), dict) else {}
    us_aqi = _as_int(data.get("aqi"))
    pm25 = _as_float(iaqi.get("pm25"))
    pm10 = _as_float(iaqi.get("pm10"))

    # A payload with no usable number in it is not a reading. Returning an
    # all-None StationReading would show a station name and a timestamp with
    # nothing to report, which reads as a broken sensor rather than absent data.
    if us_aqi is None and pm25 is None and pm10 is None:
        log.warning("WAQI payload carried no usable AQI or PM values")
        return None

    time_obj = data.get("time") if isinstance(data.get("time"), dict) else {}
    return StationReading(
        us_aqi=us_aqi,
        pm25=pm25,
        pm10=pm10,
        station=_as_str(city_obj.get("name")),
        city=_as_str(city_obj.get("name")),
        observed_at=_as_str(time_obj.get("iso")),
        distance_km=distance_km,
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
