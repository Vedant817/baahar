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

from . import seasonal
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

    if air is not None and air.naqi_effective is not None and air.naqi_effective >= 200:
        return [Cue(t, "air") for t in _CUES_POOR_AIR]

    if weather is not None:
        if weather.apparent_c is not None and weather.apparent_c >= 33:
            return [Cue(t, "heat") for t in _CUES_HOT]
        if weather.precip_prob is not None and weather.precip_prob >= 30:
            return [Cue(t, "rain") for t in _CUES_RAIN_ADJACENT]

    if slot is not None and 4 <= slot.weather.time.hour < 11:
        return [Cue(t, "morning") for t in _CUES_CLEAR_MORNING]
    return [Cue(t, "evening") for t in _CUES_CLEAR_EVENING]


def _seasonal_for(plan: OutdoorPlan, limit: int = 2) -> list[Cue]:
    """Seasonal cues for the configured city, as ordinary :class:`Cue` objects.

    Every one of these is already hedged in its own text ("researchers have
    logged", never "you will see"), because the module that builds them is
    responsible for the honesty and the display layer should not have to
    remember it.

    Deliberately city-anchored rather than park-anchored: the snapshot was
    recorded around the city centre, so a cue that said "in this park" would be
    claiming a precision the data does not have.
    """
    try:
        found = seasonal.cues_for(limit=limit)
    except Exception:  # pragma: no cover - defensive
        # A missing or malformed snapshot must never break the screen. The
        # hand-written cues are a complete, shippable experience on their own.
        found = []
    return [Cue(c.text, c.tag) for c in found]


#: Condition cues that exist to keep someone safe or comfortable. When one of
#: these is showing, every remaining slot on the screen should serve that goal,
#: so the seasonal suggestions step aside.
_SAFETY_TAGS = frozenset({"air", "heat"})


def _seasonal_allowed(plan: OutdoorPlan, condition_tags: set[str]) -> bool:
    """Whether novelty cues belong on screen at all right now.

    Suppressed on two independent grounds, either of which is enough:

    * The plan is not a GO. There is no walk to have a species cue about.
    * The active condition cue is a safety one. "Find the coolest patch of shade
      within fifty metres and stay in it" is doing real work in 34 degree heat.
      A butterfly suggestion sitting three taps away from it is a distraction
      from the one instruction that matters, which is the opposite of what a
      safety cue is for.

    Rain is intentionally not in that set. Wet-weather cues are atmospheric
    rather than protective, and the screen is not short on space.
    """
    if plan.overall is not Decision.GO:
        return False
    return not (condition_tags & _SAFETY_TAGS)


def _cue_pool(plan: OutdoorPlan) -> list[Cue]:
    """All cues for this plan: hand-written sensory ones, then seasonal ones.

    The ordering matters. Hand-written cues come first because they are the ones
    written to match *this* hour's conditions. Seasonal cues are appended, so
    they surface on shuffle without ever displacing a safety-relevant
    instruction, and they are withheld entirely when safety cues are showing.
    """
    conditions = _cues_for(plan)
    if not _seasonal_allowed(plan, {c.tag for c in conditions}):
        return conditions
    return conditions + _seasonal_for(plan)


def _headline_for(plan: OutdoorPlan, park_name: str | None) -> tuple[str, str]:
    if plan.overall is Decision.GO:
        return ("Phone in pocket.", f"Look up. Walk {park_name or 'the park'}")
    if plan.overall is Decision.WAIT:
        when = _next_hint(plan)
        if when:
            return ("Not yet.", f"Rest until {when}. Then outside.")
        # `pick_best` ranks GO above WAIT across the full scored window.
        # A planner-produced WAIT therefore has no clean hour to promise.
        return ("Not yet.", "No clean hour left in this window.")
    return ("Stay in.", "Baahar is not sending you out today.")


def _next_hint(plan: OutdoorPlan) -> str:
    """Name an explicitly recorded future GO, never guess an opening time.

    `%H:%M` is deliberate and matches every other hour in the product --
    `score._headline`, `brief.build_context`, `pocket.format_window`, the CLI and
    `journal.py`. This line sits directly under a brief that renders the same
    hours the same way, so a second format here would be a visible contradiction
    rather than a nicety.

    `build_plan` ranks every GO above WAIT before truncating the display list,
    so a planner-produced WAIT has no GO anywhere in the full scored window.
    This branch only serves externally constructed plans that explicitly carry
    a later GO. `plan.slots` is a display subset, not a full forecast search.
    """
    candidates = [s.time for s in plan.slots if s.decision is Decision.GO]
    if plan.best_time is not None:
        candidates = [t for t in candidates if t > plan.best_time]
    if not candidates:
        return ""
    return min(candidates).strftime("%H:%M")


def _subline_for(plan: OutdoorPlan) -> str:
    slot = plan.best_slot
    if slot is None:
        return "No usable hours in this window."
    air, weather = slot.air, slot.weather
    parts: list[str] = []
    if air.naqi_effective is not None:
        band = (air.naqi_band or "").capitalize()
        parts.append(f"NAQI {air.naqi_effective:.0f} ({band})")
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
    if air.naqi_effective is not None and air.naqi_effective >= 200:
        notes.append(f"Air is {air.naqi_band} today (NAQI {air.naqi_effective:.0f})")
    elif air.naqi_effective is not None and air.naqi_effective >= 100:
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
    headline, subline = _headline_for(plan, park_name)
    pool = _cue_pool(plan)
    notice = pool[0].text if pool else _CUES_DEFAULT[0]

    return PocketMode(
        active=plan.overall is not Decision.SKIP,
        headline=headline,
        # No fallback needed: every branch of `_headline_for` returns a subline,
        # including the WAIT one that has no hour to name. The old `or _next_hint()`
        # here was the other half of the vague promise, and it could only have
        # fired if `_headline_for` had returned an empty string.
        subline=subline,
        walk_minutes=minutes,
        notice_this=notice,
        park_name=park_name,
        safety_note=_safety_note(plan),
        # Provenance of `notice_this` and nothing else. Empty for a hand-written
        # cue, because claiming a data source for a line the author wrote would be
        # a lie. The front end uses `cue_evidence` for the shuffle button, since
        # the cue on screen changes without the payload being rebuilt.
        seasonal_note=seasonal.evidence_for(notice),
    )


def cue_pool(plan: OutdoorPlan) -> list[Cue]:
    """Public view of the cue pool, so the API can label each cue's provenance."""
    return _cue_pool(plan)


def cue_evidence(plan: OutdoorPlan) -> dict[str, str]:
    """Cue text -> provenance line, for the cues that have one.

    Hand-written cues are absent rather than mapped to ``""``, so the front end
    can test for presence rather than for an empty string.
    """
    # Scoped to this plan's pool, so the payload does not carry provenance for
    # species that were suppressed (hazardous air, extreme heat) and are not on
    # screen. Sending them anyway would be harmless but would misreport what the
    # product is showing.
    shown = {c.text for c in _cue_pool(plan)}
    return {c.text: c.evidence for c in seasonal.cues_for(limit=seasonal._POOL) if c.text in shown}


def briefing_cue(plan: OutdoorPlan) -> str:
    """The cue the *briefing writer* should quote.

    Always a hand-written condition cue, never a seasonal one. Two reasons:

    1. An LLM asked to "include this" will restate a species claim in its own
       words and can turn "researchers have logged around a dozen within 5 km"
       into "you will definitely see a Chocolate Pansy". Keeping species out of
       the briefing prompt removes the temptation instead of policing the output.
    2. It leaves the 36-case briefing evaluation in ``eval/RESULTS.md`` section B
       describing the prompt that actually ships. Adding an untested variable to
       that prompt would quietly invalidate a published result.
    """
    cues = _cues_for(plan)
    return cues[0].text if cues else _CUES_DEFAULT[0]


def alternate_cues(plan: OutdoorPlan, count: int | None = None) -> list[str]:
    """The cues after the first, for the Pocket Mode shuffle button.

    ``count=None`` returns the whole remainder, which is what the web UI asks
    for: it cycles through them as the reader taps, so the seasonal
    suggestions are actually reachable after the condition-matched cues have
    been seen. Truncating to two would have left them permanently off-screen.
    """
    pool = _cue_pool(plan)
    remaining = [c.text for c in pool[1:]]
    if not remaining:
        remaining = list(_CUES_DEFAULT[1:])
    return remaining if count is None else remaining[:count]


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
