"""Curated Bengaluru parks.

Baahar ships a hand-maintained list rather than calling a places API. That is a
deliberate trade: it keeps the repo keyless, the disk tiny, and the diff
reviewable, and a park's *character* (shade, surface, crowd pattern) is not
something a POI database returns anyway.

Coordinates are approximate centroids of the walkable green area. Gate-hour and
crowd notes are nudges, never claims -- see `gate_note` in the JSON.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache

from .config import PARKS_FILE
from .models import Park

EARTH_RADIUS_KM = 6371.0088


@lru_cache(maxsize=1)
def load_parks() -> list[Park]:
    """All curated parks, in file order."""
    raw = json.loads(PARKS_FILE.read_text(encoding="utf-8"))
    return [Park(**entry) for entry in raw["parks"]]


@lru_cache(maxsize=1)
def parks_metadata() -> dict[str, str]:
    raw = json.loads(PARKS_FILE.read_text(encoding="utf-8"))
    return {
        "city": raw["city"],
        "city_lat": str(raw["city_lat"]),
        "city_lon": str(raw["city_lon"]),
        "tz": raw["tz"],
    }


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def nearest_parks(
    lat: float, lon: float, *, limit: int = 3, max_km: float | None = None
) -> list[Park]:
    """Parks closest to a point, optionally capped at ``max_km``."""
    parks = load_parks()
    ranked = sorted(
        parks, key=lambda p: haversine_km(lat, lon, p.lat, p.lon)
    )
    if max_km is not None:
        ranked = [p for p in ranked if haversine_km(lat, lon, p.lat, p.lon) <= max_km]
    return ranked[:limit]


def distance_to(lat: float, lon: float, park: Park) -> float:
    return haversine_km(lat, lon, park.lat, park.lon)


def park_by_id(park_id: str) -> Park | None:
    for park in load_parks():
        if park.id == park_id:
            return park
    return None


def describe(park: Park, distance_km: float | None = None) -> str:
    """One-line, phone-readable description."""
    base = f"{park.name} -- {park.vibe}"
    if distance_km is not None:
        base = f"{distance_km:.1f} km away. {base}"
    return base


def pick_park(
    *,
    lat: float,
    lon: float,
    shade_preferred: bool = False,
    max_km: float | None = 25.0,
) -> Park | None:
    """Choose a park for the plan.

    Deliberately simple: nearest park, with shade breaking ties when the user
    is walking at midday. Baahar's job is to get someone outside; sending them
    across the city to a "better" park would defeat the point.
    """
    candidates = nearest_parks(lat, lon, limit=len(load_parks()), max_km=max_km)
    if not candidates:
        return None
    if not shade_preferred:
        return candidates[0]

    by_distance = sorted(
        candidates, key=lambda p: (p.shade != "high", distance_to(lat, lon, p))
    )
    # Only prefer shade if it is not a wild detour.
    best_any = by_distance[0]
    for park in by_distance:
        if park.shade == "high":
            if distance_to(lat, lon, park) <= distance_to(lat, lon, best_any) + 6.0:
                return park
            break
    return best_any