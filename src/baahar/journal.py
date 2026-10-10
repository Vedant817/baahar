"""The after-walk journal.

The walk is the part of Baahar a human has to do, and the notes from it are the
part an agent must never invent. So the product's job is to make writing those
notes take ten seconds.

Three taps, one optional line:

    went  ·  shortened  ·  skipped

That is deliberately the smallest possible set of answers. A richer form would
produce richer data and would not get filled in.

Design constraints
------------------
* **Local only.** Entries live in a JSONL file (CLI) or ``localStorage`` (web).
  No account, no server, no sync. A journal about where you walk is exactly the
  data a privacy-first tool should not be collecting anywhere.
* **Append-only.** Never rewritten, so the history of what you actually did is
  not something a bug can tidy away.
* **Markdown out.** :func:`render_markdown` produces the field-test block used in
  `docs/FIELD_TEST.md` and `post.md`, so the human is pasting real notes rather
  than writing prose from memory.

An entry with no outcome recorded is a *missed walk*, which is itself data. It is
stored, not discarded: "I did not go out on a SKIP day" is exactly the
confirmation that the safety advice was respected.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from .config import DATA_DIR

log = logging.getLogger(__name__)

#: India Standard Time. Baahar is Bengaluru-only, and hard-coding the offset
#: avoids depending on the machine's own timezone being set correctly.
IST = timezone(timedelta(hours=5, minutes=30), name="IST")

DEFAULT_PATH = DATA_DIR / "journal.jsonl"


class Outcome(StrEnum):
    """What actually happened. Three options, on purpose."""

    WENT = "went"
    SHORTENED = "shortened"
    SKIPPED = "skipped"
    MISSED = "missed"
    """No record at all. Inferred by absence, never stored as a tap."""


OUTCOME_LABELS: dict[str, str] = {
    Outcome.WENT.value: "went",
    Outcome.SHORTENED.value: "shortened",
    Outcome.SKIPPED.value: "skipped",
}

#: What the walker did about the seasonal species cue.
#:
#: `unrecognised` is deliberately a separate answer from `no`. A cue the walker
#: could not act on failed before the wildlife did, and lumping it in with "did
#: not see it" would hide the more actionable failure.
SPECIES_SEEN_VALUES: tuple[str, ...] = ("yes", "no", "unrecognised", "not-looked")

SPECIES_SEEN_LABELS: dict[str, str] = {
    "yes": "saw it",
    "no": "did not see it",
    "unrecognised": "did not recognise the name",
    "not-looked": "did not look",
}


def normalise_species_seen(value: str | None) -> str | None:
    """Canonicalise a species sighting answer, or ``None`` if absent.

    Accepts a few spellings because this is typed by a human on a phone after a
    walk. Anything unrecognised returns ``None`` rather than being stored
    verbatim, so a typo cannot quietly become a data point.
    """
    if value is None:
        return None
    cleaned = value.strip().lower().replace("_", "-").replace(" ", "-")
    if not cleaned:
        return None
    if cleaned in SPECIES_SEEN_VALUES:
        return cleaned
    aliases = {
        "y": "yes",
        "true": "yes",
        "seen": "yes",
        "n": "no",
        "false": "no",
        "not-seen": "no",
        "didnt-recognise": "unrecognised",
        "did-not-recognise": "unrecognised",
        "unknown-name": "unrecognised",
        "skipped": "not-looked",
        "didnt-look": "not-looked",
    }
    return aliases.get(cleaned)


@dataclass
class Entry:
    """One walk attempt."""

    walked_at: str
    outcome: str
    planned_decision: str | None = None
    planned_window: str | None = None
    park: str | None = None
    naqi: float | None = None
    naqi_band: str | None = None
    felt_c: float | None = None
    minutes_planned: int | None = None
    minutes_walked: int | None = None
    reached_for_phone: int | None = None
    #: The species Baahar suggested, if a seasonal cue was shown.
    species_suggested: str | None = None
    #: What the walker actually did about it. This is the one claim in the
    #: project with a denominator only a human can supply, so it is a first-class
    #: field rather than something to bury in the free-text note.
    species_seen: str | None = None
    note: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Entry:
        known = set(cls.__dataclass_fields__)
        payload = {k: v for k, v in data.items() if k in known}
        extra = {k: v for k, v in data.items() if k not in known}
        entry = cls(**payload)
        entry.extra = extra
        return entry


def journal_path(path: Path | str | None = None) -> Path:
    """Resolve the journal file, honouring ``BAAHAR_JOURNAL``."""
    env = os.getenv("BAAHAR_JOURNAL")
    if env:
        return Path(env)
    return Path(path) if path else DEFAULT_PATH


def append(entry: Entry, path: Path | str | None = None) -> Path:
    """Append one entry. Creates the file and parent directory if needed."""
    target = journal_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(entry.to_json() + "\n")
    return target


def record(
    outcome: str | Outcome,
    *,
    planned_decision: str | None = None,
    planned_window: str | None = None,
    park: str | None = None,
    naqi: float | None = None,
    naqi_band: str | None = None,
    felt_c: float | None = None,
    minutes_planned: int | None = None,
    minutes_walked: int | None = None,
    reached_for_phone: int | None = None,
    species_suggested: str | None = None,
    species_seen: str | None = None,
    note: str = "",
    when: datetime | None = None,
    path: Path | str | None = None,
) -> Path:
    """Create and store an entry. Returns the journal path."""
    value = Outcome(outcome).value if outcome != Outcome.MISSED else Outcome.MISSED.value
    stamp = when or datetime.now(tz=IST)
    entry = Entry(
        walked_at=stamp.isoformat(),
        outcome=value,
        planned_decision=planned_decision,
        planned_window=planned_window,
        park=park,
        naqi=naqi,
        naqi_band=naqi_band,
        felt_c=felt_c,
        minutes_planned=minutes_planned,
        minutes_walked=minutes_walked,
        reached_for_phone=reached_for_phone,
        species_suggested=(species_suggested or None),
        species_seen=normalise_species_seen(species_seen),
        note=note.strip(),
    )
    return append(entry, path)


def load(path: Path | str | None = None) -> list[Entry]:
    """Read every entry, oldest first. Unparseable lines are skipped loudly."""
    target = journal_path(path)
    if not target.exists():
        return []
    entries: list[Entry] = []
    for lineno, line in enumerate(target.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(Entry.from_dict(json.loads(line)))
        except (json.JSONDecodeError, TypeError) as exc:
            log.warning("skipping unreadable journal line %d: %s", lineno, exc)
    return entries


def summarise(entries: list[Entry]) -> dict[str, Any]:
    """Counts and the numbers worth reporting."""
    counts: dict[str, int] = {o.value: 0 for o in Outcome}
    reached = 0
    minutes = 0
    species_asked = 0
    species: dict[str, int] = {}
    for entry in entries:
        counts[entry.outcome] = counts.get(entry.outcome, 0) + 1
        reached += entry.reached_for_phone or 0
        minutes += entry.minutes_walked or 0
        if entry.species_suggested:
            species_asked += 1
            key = entry.species_seen or "unrecorded"
            species[key] = species.get(key, 0) + 1
    walked = counts.get(Outcome.WENT.value, 0) + counts.get(Outcome.SHORTENED.value, 0)
    return {
        "n_entries": len(entries),
        "counts": counts,
        "walks_recorded": walked,
        "total_minutes_walked": minutes,
        "times_reached_for_phone": reached,
        "species_asked": species_asked,
        "species_sightings": species,
        "honesty_note": (
            "A 'skipped' entry recorded on a day Baahar said GO is the most "
            "interesting entry in this journal."
        ),
    }


def render_markdown(entries: list[Entry], *, include_all: bool = False) -> str:
    """Render entries as the field-test block used in FIELD_TEST.md and post.md.

    ``include_all=False`` (the default) emits the *latest* walk, which is what
    someone pasting into the post wants. ``include_all=True`` emits the full
    history.
    """
    honesty = (
        "_Local journal only. This is not the field test. "
        "`docs/FIELD_TEST.md` stays NOT YET DONE until a human fills it._\n\n"
    )
    if not entries:
        return (
            honesty + "_No walks recorded yet._\n\n"
            "Record one with:\n\n"
            '```bash\nuv run baahar journal --outcome went --note "looked up more than usual"\n```'
        )

    chosen = entries if include_all else entries[-1:]
    lines: list[str] = [honesty.rstrip(), ""]
    for entry in chosen:
        when = entry.walked_at
        with contextlib.suppress(ValueError):
            # Portable format: "%-d" is a GNU strftime extension and raises
            # ValueError on Windows, which silently left raw ISO strings in the
            # rendered markdown.
            dt = datetime.fromisoformat(entry.walked_at)
            when = f"{dt.day} {dt.strftime('%b %Y')}, {dt.strftime('%H:%M')} IST"

        lines.append(f"### The walk — {when}")
        lines.append("")
        if entry.park:
            lines.append(f"- **Where:** {entry.park}")
        lines.append(
            f"- **Baahar said:** {entry.planned_decision or '—'}"
            + (f", window {entry.planned_window}" if entry.planned_window else "")
        )
        if entry.naqi is not None:
            band = f" ({entry.naqi_band})" if entry.naqi_band else ""
            lines.append(f"- **NAQI shown:** {entry.naqi:.0f}{band}")
        if entry.felt_c is not None:
            lines.append(f"- **Weather felt like:** {entry.felt_c:.0f}°C")
        if entry.minutes_planned:
            walked = entry.minutes_walked
            detail = f"{walked} min" if walked is not None else "unknown"
            lines.append(f"- **Walked:** {detail} of {entry.minutes_planned} planned")
        if entry.reached_for_phone is not None:
            times = entry.reached_for_phone
            plural = "time" if times == 1 else "times"
            lines.append(f"- **Reached for the phone:** {times} {plural}")
        if entry.species_suggested:
            outcome_label = SPECIES_SEEN_LABELS.get(entry.species_seen or "", "no answer recorded")
            lines.append(f"- **Species cue:** {entry.species_suggested} — {outcome_label}")
        lines.append(f"- **Outcome:** {OUTCOME_LABELS.get(entry.outcome, entry.outcome)}")
        if entry.note:
            lines.append(f"- **Note:** {entry.note}")
        lines.append("")

    stats = summarise(entries)
    if len(entries) > 1:
        lines.append(
            f"_{stats['n_entries']} entries · {stats['walks_recorded']} walks recorded · "
            f"{stats['times_reached_for_phone']} phone reaches._"
        )

    # Aggregate the species cues when there are enough of them to mean anything.
    # One walk is an anecdote; three is a rate. Never a percentage from n=1 --
    # that is the exact "rate" fabrication eval/RESULTS.md refuses elsewhere.
    if stats["species_asked"] >= 3:
        seen = stats["species_sightings"].get("yes", 0)
        asked = stats["species_asked"]
        breakdown = ", ".join(
            f"{SPECIES_SEEN_LABELS.get(k, k)}: {v}"
            for k, v in sorted(stats["species_sightings"].items())
        )
        lines.append(
            f"_{asked} walks were shown a species cue. Seen on {seen} of them "
            f"({seen / asked:.0%}). Breakdown: {breakdown}._"
        )
        lines.append(
            "_A small denominator. Treat this as a first reading of whether the "
            "radius and the phrasing are calibrated, not as a benchmark._"
        )
    return "\n".join(lines).strip() + "\n"
