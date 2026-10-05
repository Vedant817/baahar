"""Join weather and air-quality hours into one timeline.

Weather and air quality come from two different Open-Meteo endpoints. They
share a timezone and a grid, so their timestamps normally line up exactly -- but
"normally" is not a guarantee, so alignment is explicit here.

Two failure modes this module exists to prevent:

* **Silent misalignment.** If the AQ series starts an hour later, a positional
  zip would pair 06:00 weather with 07:00 air. Everything downstream would look
  plausible and be wrong. Joining on timestamp makes that impossible.
* **Half-empty hours.** If one source is missing an hour, the slot is kept with
  a ``None`` NAQI so the scorer reports it as unusable, rather than dropping the
  hour and quietly shifting the timeline.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from .air import fetch_air
from .models import DataSource, HourSlot
from .weather import fetch_weather

log = logging.getLogger(__name__)


def join_slots(
    weather: Sequence, air: Sequence
) -> tuple[list[HourSlot], list[str]]:
    """Join weather and air hours on timestamp.

    Returns the joined slots plus a list of human-readable notes about anything
    imperfect, which the caller surfaces as ``degraded``.
    """
    notes: list[str] = []
    air_by_time = {slot.time: slot for slot in air}
    weather_times = {slot.time for slot in weather}

    unpaired_air = [t for t in air_by_time if t not in weather_times]
    if unpaired_air:
        log.info("%d air-quality hours had no weather counterpart", len(unpaired_air))

    slots: list[HourSlot] = []
    missing_air: list[str] = []
    for w in weather:
        a = air_by_time.get(w.time)
        if a is None:
            missing_air.append(w.time.strftime("%H:%M"))
            # Placeholder air hour: NAQI is None, so the scorer treats it as
            # unusable instead of inventing a value.
            from .models import HourlyAir

            a = HourlyAir(time=w.time)
        slots.append(HourSlot(weather=w, air=a))

    if missing_air:
        shown = ", ".join(missing_air[:4])
        more = f" (+{len(missing_air) - 4} more)" if len(missing_air) > 4 else ""
        notes.append(f"no air-quality data for {shown}{more}; those hours are treated as unusable")
    return slots, notes


def fetch_joined(
    *,
    lat: float | None = None,
    lon: float | None = None,
    hours: int | None = None,
    offline: bool | None = None,
) -> tuple[list[HourSlot], DataSource, DataSource]:
    """Fetch both sources and join them. Returns ``(slots, weather_src, air_src)``."""
    weather, wsrc = fetch_weather(lat=lat, lon=lon, hours=hours, offline=offline)
    air, asrc = fetch_air(lat=lat, lon=lon, hours=hours, offline=offline)
    slots, notes = join_slots(weather, air)
    if notes:
        log.info("join notes: %s", "; ".join(notes))
    return slots, wsrc, asrc