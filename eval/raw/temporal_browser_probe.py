"""Serve the real API/UI with explicitly synthetic forecast inputs for QA."""
from datetime import UTC, datetime, timedelta

import uvicorn

from baahar import app as app_module
from baahar.models import DataSource, HourlyAir, HourlyWeather, HourSlot


def synthetic_forecast(*, hours=None, **kwargs):
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    scenario = hours or 2
    values = [(0, 50)] if scenario == 1 else [(0, 350), (2, 50)]
    slots = [HourSlot(
        weather=HourlyWeather(time=now + timedelta(hours=h), apparent_c=25,
                              temp_c=25, precip_mm=0, precip_prob=0, is_day=1),
        air=HourlyAir(time=now + timedelta(hours=h), naqi=n),
    ) for h, n in values]
    return slots, DataSource.LIVE, DataSource.LIVE


if __name__ == "__main__":
    app_module.forecast_mod.fetch_joined = synthetic_forecast
    uvicorn.run(app_module.app, host="127.0.0.1", port=8766, log_level="warning")
