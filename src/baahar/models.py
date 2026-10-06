"""Typed data shapes shared by the CLI, the HTTP API and the eval harness.

Pydantic v2 models are used purely as schemas here -- every one of them
round-trips to plain JSON, which is what the web UI and `eval/raw/*.json`
consume.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .naqi import NAQI_BASIS


class Decision(StrEnum):
    """What Baahar tells the user to do about this hour."""

    GO = "GO"
    WAIT = "WAIT"
    SKIP = "SKIP"


class DataSource(StrEnum):
    """Where a number came from. Never lie about this in the UI."""

    LIVE = "live"
    FIXTURE = "fixture"
    UNAVAILABLE = "unavailable"


class WeatherSeverity(StrEnum):
    CLEAR = "clear"
    CLOUD = "cloud"
    FOG = "fog"
    DRIZZLE = "drizzle"
    RAIN = "rain"
    SNOW = "snow"
    SHOWERS = "showers"
    THUNDERSTORM = "thunderstorm"


class HourlyWeather(BaseModel):
    """One forecast hour of weather, exactly as Baahar uses it."""

    model_config = ConfigDict(frozen=True)

    time: datetime
    temp_c: float | None = None
    apparent_c: float | None = None
    precip_mm: float | None = None
    precip_prob: float | None = None
    humidity: float | None = None
    wind_kmh: float | None = None
    uv_index: float | None = None
    weather_code: int | None = None
    is_day: int | None = None


class HourlyAir(BaseModel):
    """One forecast hour of air quality, with Indian NAQI attached."""

    model_config = ConfigDict(frozen=True)

    time: datetime
    pm25: float | None = None
    pm10: float | None = None
    no2: float | None = None
    o3: float | None = None
    co: float | None = None
    so2: float | None = None
    nh3: float | None = None
    pb: float | None = None

    naqi: float | None = None
    naqi_band: str | None = None
    naqi_band_label: str | None = None
    naqi_health_impact: str | None = None
    dominant_pollutant: str | None = None
    dominant_label: str | None = None
    naqi_basis: str = NAQI_BASIS

    #: Open-Meteo's own US-EPA scale, kept for comparison only and never shown
    #: as "AQI". CPCB and EPA scales differ, so mixing them would be a lie.
    us_aqi_reference: float | None = None


class HourSlot(BaseModel):
    """A weather hour joined to its air-quality hour on the same timestamp."""

    model_config = ConfigDict(frozen=True)

    #: Shorthand for the weather hour's timestamp, mirroring `weather.time`. Set
    #: automatically on construction so the two can never drift apart.
    time: datetime
    weather: HourlyWeather
    air: HourlyAir
    weather_source: DataSource = DataSource.LIVE
    air_source: DataSource = DataSource.LIVE

    @property
    def naive(self) -> bool:
        """True when Baahar could not find usable air data for this hour."""
        return self.air.naqi is None

    @model_validator(mode="before")
    @classmethod
    def _derive_time(cls, data: Any) -> Any:
        """Fill `time` from `weather.time` before field validation runs."""
        if isinstance(data, dict) and not data.get("time"):
            weather = data.get("weather")
            if isinstance(weather, HourlyWeather):
                data = {**data, "time": weather.time}
        return data


class SlotScore(BaseModel):
    """A scored hour: the decision, why, and the evidence behind it."""

    time: datetime
    decision: Decision
    #: 0-100, higher is better for a gentle walk. Comparable only within a run.
    comfort: float
    reasons: list[str] = Field(default_factory=list)
    #: The signals that drove the decision, for the "show your work" panel.
    signals: dict[str, Any] = Field(default_factory=dict)
    #: Name of the scorer that produced this decision.
    scorer: str = "heuristic"


class Park(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    area: str
    lat: float
    lon: float
    vibe: str
    good_for: list[str] = Field(default_factory=list)
    shade: str = "medium"
    surface: str = ""
    water_feature: str | None = None
    crowding_hint: str = ""
    gate_note: str = ""
    size_hint: str = ""


class OutdoorPlan(BaseModel):
    """The scored answer to "when should I go outside?"."""

    city: str
    generated_at: datetime
    window_hours: int
    overall: Decision
    best_slot: HourSlot | None
    best_time: datetime | None
    headline: str
    slots: list[SlotScore] = Field(default_factory=list)
    park: Park | None = None
    #: Which scorer actually produced these numbers.
    scorer: str = "heuristic"
    #: Why the scorer chose that path (missing key, import failure, ...).
    scorer_note: str = ""
    #: Set when the run used recorded fixtures or lost part of its inputs.
    degraded: list[str] = Field(default_factory=list)
    weather_source: DataSource = DataSource.LIVE
    air_source: DataSource = DataSource.LIVE


class Briefing(BaseModel):
    """A generated park briefing."""

    text: str
    model: str
    #: "gemma" | "tinker" | "template" | "hybrid"
    writer: str
    word_count: int
    #: Human-readable note about how this was produced, e.g. key missing.
    note: str = ""
    #: Optional ElevenLabs audio URL, when voice was requested and available.
    audio_url: str | None = None
    #: Seconds spent producing the briefing.
    latency_ms: int | None = None


class PocketMode(BaseModel):
    """Everything the Pocket Mode screen needs. Deliberately tiny."""

    active: bool = False
    headline: str
    subline: str = ""
    walk_minutes: int = 20
    #: One concrete thing to look for. The whole point of the walk.
    notice_this: str = ""
    park_name: str | None = None
    #: Shown small at the bottom, so the user is not anxious about missing out.
    safety_note: str = ""
    #: Provenance line for the current cue, when it came from a recorded dataset
    #: rather than from a person who wrote it by hand. Empty for hand-written
    #: cues, because claiming a data source for a hand-written line would be a lie.
    seasonal_note: str = ""


class BriefResponse(BaseModel):
    """The single payload the web UI renders. Two screens, one object."""

    plan: OutdoorPlan
    briefing: Briefing
    pocket: PocketMode
    disclaimer: str = (
        "Informational outdoor planning only. Not medical advice, and not a "
        "replacement for the official CPCB advisory."
    )
    meta: dict[str, Any] = Field(default_factory=dict)


#: Copy is centralised so the safety wording cannot drift between CLI and web.
DISCLAIMER = BriefResponse.model_fields["disclaimer"].default


class _HasTime(Protocol):
    time: datetime


_T = TypeVar("_T", bound=_HasTime)


def slice_from_now[T: _HasTime](
    items: Sequence[T], hours: int, *, now: datetime | None = None
) -> list[T]:
    """Return up to ``hours`` entries starting at or after *now*.

    Open-Meteo is queried with ``past_days=1`` so that "now" is always inside
    the returned series -- which means positional slicing is wrong: index 0 is
    yesterday, not today. Anchor on the timestamp instead.

    If every entry is in the past -- replaying a recorded fixture on a later
    day -- the entries are returned as-is rather than emptying the product.
    Baahar would rather show a clearly-labelled stale day than no answer.
    """
    if not items:
        return []
    tz = items[0].time.tzinfo
    cutoff = now or datetime.now(tz=tz)
    future = [item for item in items if item.time >= cutoff]
    if future:
        return future[:hours]
    return list(items[:hours])


SKIP_COPY = {
    Decision.SKIP: "Stay in. Baahar is not sending you out in this.",
    Decision.WAIT: "Not yet -- but there is a window coming.",
    Decision.GO: "Go now.",
}
