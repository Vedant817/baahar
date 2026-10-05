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
    """Counts and the one number worth reporting: phone reach count."""
    counts: dict[str, int] = {o.value: 0 for o in Outcome}
    reached = 0
    minutes = 0
    for entry in entries:
        counts[entry.outcome] = counts.get(entry.outcome, 0) + 1
        reached += entry.reached_for_phone or 0
        minutes += entry.minutes_walked or 0
    walked = counts.get(Outcome.WENT.value, 0) + counts.get(Outcome.SHORTENED.value, 0)
    return {
        "n_entries": len(entries),
        "counts": counts,
        "walks_recorded": walked,
        "total_minutes_walked": minutes,
        "times_reached_for_phone": reached,
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
    if not entries:
        return (
            "_No walks recorded yet._\n\n"
            "Record one with:\n\n"
            '```bash\nuv run baahar journal --outcome went --note "looked up more than usual"\n```'
        )

    chosen = entries if include_all else entries[-1:]
    lines: list[str] = []
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
    return "\n".join(lines).strip() + "\n"
