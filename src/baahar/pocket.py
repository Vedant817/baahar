"""Pocket Mode -- the part that makes the product mean something.

Every other module exists to get a person to this screen. The screen itself is
almost empty on purpose:

* near-black background, because a phone at 3% brightness in a park at dawn
  should not become the brightest object in your field of view;
* one line of instruction, in large type;
* one concrete thing to look for, because "notice your surroundings" is a
  useless instruction and "listen for the second bird, not the traffic" is not;
* a walk timer, so the session *ends* rather than scrolling forever;
* no badges, no streak, no feed, no notification hooks.

The success metric is the user leaving. Anything on this screen that makes them
stay and read is a bug.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import get_settings
from .models import Decision, OutdoorPlan, PocketMode

#: Sensory cues tied to conditions. Written as concrete instructions because a
#: generic "enjoy nature" does not make anyone look up from the phone.
#: Keyed by band + hour phase so the cue fits the actual conditions.
_CUES_CLEAR_MORNING = [
    "Listen for the first two birds, then ignore the traffic.",
    "Find one leaf with a hole in it and picture the insect that made it.",
    "Notice how the light changes between two trees, ten metres apart.",
]
_CUES_CLEAR_EVENING = [
    "Stand still for thirty seconds and count how many sounds you can name.",
    "Find the first artificial light, then find the last one you can see.",
    "Watch one patch of sky for a full minute. Something will change.",
]
_CUES_HOT = [
    "Find the coolest patch of shade within fifty metres and stay in it.",
    "Notice which surfaces hold heat: paving, dust, leaves, water.",
    "Listen for the sound the heat makes. Mostly, none. Notice that.",
]
_CUES_RAIN_ADJACENT = [
    "Count how many different smells the rain left behind.",
    "Find a puddle and look at what the reflection shows you.",
    "Notice the gap between the sound of rain on a roof and on a tree.",
]
_CUES_POOR_AIR = [
    "Stay on the quieter paths where the trees do the work.",
    "Notice what your nose tells you before any app does.",
    "Take the long way round the lake instead of the straight line.",
]
_CUES_DEFAULT = [
    "Find the oldest tree within sight and imagine how old that is.",
    "Listen for the furthest sound you can hear, then walk toward it.",
    "Notice three things that would not exist in your office.",
]


@dataclass(frozen=True)
class Cue:
    """One sensory instruction."""

    text: str
    tag: str


def _cues_for(plan: OutdoorPlan) -> list[Cue]:
    slot = plan.best_slot
    air = slot.air if slot else None
    weather = slot.weather if slot else None

    if air is not None and air.naqi is not None and air.naqi >= 200:
        return [Cue(t, "air") for t in _CUES_POOR_AIR]

    if weather is not None:
        if weather.apparent_c is not None and weather.apparent_c >= 33:
            return [Cue(t, "heat") for t in _CUES_HOT]
        if weather.precip_prob is not None and weather.precip_prob >= 30:
            return [Cue(t, "rain") for t in _CUES_RAIN_ADJACENT]

    if slot is not None and 4 <= slot.weather.time.hour < 11:
        return [Cue(t, "morning") for t in _CUES_CLEAR_MORNING]
    return [Cue(t, "evening") for t in _CUES_CLEAR_EVENING]


def _headline_for(decision: Decision, park_name: str | None) -> tuple[str, str]:
    if decision is Decision.GO:
        return ("Phone in pocket.", f"Look up. Walk {park_name or 'the park'}")
    if decision is Decision.WAIT:
        return ("Not yet.", f"Rest until {_next_hint()}. Then outside.")
    return ("Stay in.", "Baahar is not sending you out today.")


def _next_hint() -> str:
    return "the window opens"


def _subline_for(plan: OutdoorPlan) -> str:
    slot = plan.best_slot
    if slot is None:
        return "No usable hours in this window."
    air, weather = slot.air, slot.weather
    parts: list[str] = []
    if air.naqi is not None:
        band = (air.naqi_band or "").capitalize()
        parts.append(f"NAQI {air.naqi:.0f} ({band})")
    if weather.temp_c is not None:
        feels = (
            f", feels {weather.apparent_c:.0f}"
            if weather.apparent_c is not None and abs(weather.apparent_c - weather.temp_c) >= 1.5
            else ""
        )
        parts.append(f"{weather.temp_c:.0f}°C{feels}")
    return " · ".join(parts)


def _safety_note(plan: OutdoorPlan) -> str:
    slot = plan.best_slot
    if slot is None:
        return "No air reading for this hour."
    air, weather = slot.air, slot.weather
    notes: list[str] = []
    if air.naqi is not None and air.naqi >= 200:
        notes.append(f"Air is {air.naqi_band} today (NAQI {air.naqi:.0f})")
    elif air.naqi is not None and air.naqi >= 100:
        notes.append("Air is moderate")
    if weather.apparent_c is not None and weather.apparent_c >= 35:
        notes.append(f"feels like {weather.apparent_c:.0f}°C")
    if weather.precip_prob is not None and weather.precip_prob >= 40:
        notes.append(f"{weather.precip_prob:.0f}% rain chance")
    return " · ".join(notes) if notes else "Nothing unusual. Go enjoy it."


def build_pocket(plan: OutdoorPlan, walk_minutes: int | None = None) -> PocketMode:
    """Assemble the Pocket Mode payload for a plan."""
    settings = get_settings()
    minutes = walk_minutes or settings.walk_minutes
    park_name = plan.park.name if plan.park else None
    headline, subline = _headline_for(plan.overall, park_name)
    cues = _cues_for(plan)
    notice = cues[0].text if cues else _CUES_DEFAULT[0]

    return PocketMode(
        active=plan.overall is not Decision.SKIP,
        headline=headline,
        subline=subline or (_next_hint() if plan.overall is Decision.WAIT else ""),
        walk_minutes=minutes,
        notice_this=notice,
        park_name=park_name,
        safety_note=_safety_note(plan),
    )


def alternate_cues(plan: OutdoorPlan, count: int = 2) -> list[str]:
    """The next `count` sensory cues, for the Pocket Mode shuffle button."""
    cues = _cues_for(plan)
    return [c.text for c in cues[1 : 1 + count]] or _CUES_DEFAULT[1 : 1 + count]


def walk_timer_seconds(minutes: int | None = None) -> int:
    settings = get_settings()
    return (minutes or settings.walk_minutes) * 60


def ensure_walk_minutes(minutes: int | None) -> int:
    """Clamp a user-supplied walk length into something sensible."""
    if minutes is None:
        return get_settings().walk_minutes
    return max(5, min(180, int(minutes)))


def format_window(plan: OutdoorPlan) -> str:
    """`06:00-07:00`-style window for the best slot, for CLI output."""
    if plan.best_time is None:
        return "no window"
    start = plan.best_time.strftime("%H:%M")
    end_hour = plan.best_time.hour + 1
    return f"{start}-{end_hour:02d}:00"
