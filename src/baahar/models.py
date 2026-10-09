"""Typed data shapes shared by the CLI, the HTTP API and the eval harness.

Pydantic v2 models are used purely as schemas here -- every one of them
round-trips to plain JSON, which is what the web UI and `eval/raw/*.json`
consume.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from .naqi import NAQI_BASIS, band_for_index


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

    #: CPCB breakpoints applied to this hour's *instantaneous* concentrations.
    #:
    #: Deliberately kept, unrenamed and unchanged: the eval dataset and the
    #: recorded artifacts are shaped around it, and downstream code reads it.
    #: It is no longer the number the product acts on -- see
    #: :attr:`naqi_effective`.
    naqi: float | None = None

    #: CPCB breakpoints applied to a *trailing mean* over each pollutant's own
    #: averaging period (24 h; 8 h for O3 and CO). This is the closer match to
    #: official NAQI, because the breakpoints were defined on averaged
    #: concentrations. ``None`` when there was too little history to average:
    #: see :data:`baahar.naqi.MIN_TRAILING_HOURS`.
    naqi_trailing: float | None = None

    #: Hours of history that actually backed :attr:`naqi_trailing`, for the
    #: pollutant that drove it. Recorded so a partial window is auditable
    #: rather than passed off as a full 24-hour mean. ``0`` when there was no
    #: trailing value at all.
    naqi_trailing_hours: int = 0

    # The remaining band fields describe the *effective* (conservative) index,
    # because health copy that understates the risk is the exact failure this
    # module exists to prevent. `naqi` above stays the raw instantaneous number.

    naqi_band: str | None = None
    naqi_band_label: str | None = None
    naqi_health_impact: str | None = None
    dominant_pollutant: str | None = None
    dominant_label: str | None = None
    naqi_basis: str = NAQI_BASIS

    #: Open-Meteo's own US-EPA scale, kept for comparison only and never shown
    #: as "AQI". CPCB and EPA scales differ, so mixing them would be a lie.
    us_aqi_reference: float | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def naqi_effective(self) -> float | None:
        """The NAQI everything downstream acts on: the more conservative reading.

        Always ``max(naqi, naqi_trailing)``, so it can never be lower than the
        instantaneous value the product used to act on. Computed rather than
        stored, which is the point: a stored field could be filled in with
        something lower by any caller that constructs `HourlyAir` directly --
        and the test suite, the dataset builder and the eval harness all do
        exactly that. The guarantee has to hold by construction, not by
        discipline.

        Non-finite readings are excluded from the comparison rather than
        poisoning it. ``max([nan, 120.0])`` is ``nan``, so a single ``nan``
        placed in either field -- something only a direct constructor can do,
        since ``parse_air`` cannot produce one -- would take the whole hour's
        safety number down to *no number at all* while looking like data. An
        hour whose only readings are non-finite is treated the same as an hour
        with no readings: ``None``, i.e. ``SKIP``, not a guess.

        ``None`` only when both readings are absent or non-finite, i.e. genuinely
        no data.
        """
        known = [v for v in (self.naqi, self.naqi_trailing) if v is not None and math.isfinite(v)]
        return max(known) if known else None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def naqi_effective_band(self) -> str | None:
        """CPCB band of :attr:`naqi_effective`."""
        band = band_for_index(self.naqi_effective)
        return band.value if band else None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def naqi_uses_trailing_mean(self) -> bool:
        """True when the trailing mean, not the hour's own reading, is the one acted on.

        Surfaced so the UI can say why a number is higher than the
        concentration on screen would suggest. Compares against the same
        finite-only reading of ``naqi`` that :attr:`naqi_effective` uses, so
        the flag and the number can never disagree about which one won.
        """
        trailing = self.naqi_trailing
        if trailing is None or not math.isfinite(trailing):
            return False
        instant = self.naqi
        if instant is None or not math.isfinite(instant):
            return True
        return trailing > instant


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
        """True when Baahar could not find usable air data for this hour.

        Keyed on the effective reading, not the instantaneous one: an hour
        whose own sensor values are missing still has a trailing mean behind it,
        and that mean is a real number we can act on.
        """
        return self.air.naqi_effective is None

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
    current_slot: HourSlot | None = None
    current_decision: Decision | None = None
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
