#!/usr/bin/env python
"""Record verbatim Open-Meteo responses as offline fixtures.

Run this whenever the upstream API shape might have changed, or to refresh
fixtures before a demo. The recorded files are committed, which is what lets
`baahar brief` work with the network unplugged and lets `pytest` run offline.

    uv run python scripts/record_samples.py

Never hand-edit the output. Fixtures are evidence.
"""

from __future__ import annotations

import logging
import sys

from baahar.air import AIR_URL
from baahar.air import FIXTURE_NAME as AIR_FIXTURE
from baahar.air import HOURLY_VARS as AIR_VARS
from baahar.config import get_settings
from baahar.http_client import UpstreamError, get_json, record_sample, sample_meta
from baahar.weather import FIXTURE_NAME as WX_FIXTURE
from baahar.weather import FORECAST_URL
from baahar.weather import HOURLY_VARS as WX_VARS

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("record_samples")


def record_forecast() -> bool:
    settings = get_settings()
    params = {
        "latitude": settings.lat,
        "longitude": settings.lon,
        "hourly": ",".join(WX_VARS),
        "forecast_days": 2,
        "timezone": settings.timezone,
        "past_days": 1,
    }
    payload = get_json(FORECAST_URL, params, timeout=30, retries=2)
    path = record_sample(
        WX_FIXTURE,
        payload,
        url=FORECAST_URL,
        note=f"Open-Meteo forecast for {settings.city} ({settings.lat},{settings.lon})",
    )
    log.info("wrote %s (%d bytes)", path.name, path.stat().st_size)
    return True


def record_air() -> bool:
    settings = get_settings()
    params = {
        "latitude": settings.lat,
        "longitude": settings.lon,
        "hourly": ",".join(AIR_VARS + ["us_aqi"]),
        "forecast_days": 2,
        "timezone": settings.timezone,
        "past_days": 1,
    }
    payload = get_json(AIR_URL, params, timeout=30, retries=2)
    path = record_sample(
        AIR_FIXTURE,
        payload,
        url=AIR_URL,
        note=f"Open-Meteo CAMS air quality for {settings.city}",
    )
    log.info("wrote %s (%d bytes)", path.name, path.stat().st_size)
    return True


def main() -> int:
    failures = 0
    for label, fn in (("forecast", record_forecast), ("air-quality", record_air)):
        try:
            fn()
        except UpstreamError as exc:
            log.error("%s recording failed: %s", label, exc)
            failures += 1

    for name in (WX_FIXTURE, AIR_FIXTURE):
        meta = sample_meta(name)
        if meta:
            log.info(
                "%s recorded %s from %s",
                name,
                meta.get("recorded_at_utc"),
                meta.get("source_url"),
            )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
