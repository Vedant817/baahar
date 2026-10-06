"""Seasonal "worth a look for" cues, grounded in real observations.

Why this exists
---------------
Pocket Mode's whole argument is that you should go outside and *look at
something*. "Find one thing you have never noticed before" is a decent
instruction. "Look for a Common Kingfisher on the lake edge" is a better one,
because it gives the eye a specific target and most people walk past one without
registering it.

Where the data comes from
-------------------------
[iNaturalist](https://www.inaturalist.org/) observation records, filtered to:

* a radius around the chosen park (default 5 km),
* ``quality_grade=research`` -- the community-verified grade, i.e. IDs that other
  observers have agreed with,
* the current calendar month.

This module does **not** call iNaturalist at request time. It reads a recorded
snapshot under ``data/seasonal/`` produced by
``scripts/refresh_seasonal.py``. Three reasons:

1. Pocket Mode must never wait on a third-party API. The product's whole premise
   is that the briefing is ready before you ask for it.
2. A snapshot is auditable. The counts and the query that produced them are
   committed, so a claim in the write-up can be traced to a file.
3. It degrades for free. No snapshot for this month means the hand-written
   sensory cues are used unchanged, which is what ships today anyway.

Honesty rules, enforced here rather than requested in a prompt
--------------------------------------------------------------
* **Never a promise of a sighting.** A cue says a species is *recorded nearby
  this month*, not that you will see one. Most park visitors will not.
* **Never a confidence claim.** No "you'll definitely spot". The species name and
  the count are facts about the observation record, not about the reader's luck.
* **"Nearby", never "in this park".** The query is a radius around the park, so
  the wording says "nearby" and the radius is stated.
* **Research grade only.** Casual/casual-grade IDs are excluded, because a
  species list built from unverified IDs is exactly the fake-confidence failure
  this project refuses.
* **Verifiable.** Every cue carries the observation count, the taxon id, and the
  month the snapshot covers, so any claim can be checked against the source.

Attribution: observation data from iNaturalist, contributed by its community,
available under CC0 / CC-BY per record. Species names are iNaturalist taxonomy.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import DATA_DIR

log = logging.getLogger(__name__)

SEASONAL_DIR = DATA_DIR / "seasonal"

#: Attribution string, repeated in the UI so the data source is never invisible.
INAT_URL = "https://www.inaturalist.org"
API_URL = "https://api.inaturalist.org/v1"

#: Radius around the city anchor, in km. Small enough that "nearby" is honest.
DEFAULT_RADIUS_KM = 5.0

#: Words that would make a cue collide with the hand-written sensory cues.
#: "look for a bird" is not a specific instruction.
STOPWORDS = ("bird", "birds", "unknown", "unidentified", "plant", "insect")

#: How many cues to keep in hand when resolving a cue's evidence. Larger than the
#: number shown on screen, because the shuffle button can walk the whole pool.
_POOL = 8


def tally(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Count agreeing research-grade records per taxon, most-seen first.

    Lives in the library rather than the recording script because it is pure and
    it is where the honesty decision is made. Two records get dropped here:

    * anything with fewer than one agreeing identification. iNaturalist's
      research grade already means the ID was confirmed, but a record that
      reached us without that field is not evidence of anything, and a species
      list built from unverified IDs is exactly the fake-confidence failure this
      project refuses to ship.
    * anything whose common name contains a :data:`STOPWORDS` word, so the
      seasonal cues do not just restate the hand-written ones.
    """
    counts: dict[int, dict[str, Any]] = {}
    for obs in observations:
        taxon = obs.get("taxon") or {}
        name = str(taxon.get("name") or "").strip()
        common = str(taxon.get("preferred_common_name") or "").strip()
        if not name or not common:
            continue
        agree = int(obs.get("num_identification_agreements") or 0)
        if agree < 1:
            continue
        taxon_id = int(taxon.get("id") or 0)
        if taxon_id <= 0:
            continue
        entry = counts.setdefault(
            taxon_id,
            {
                "id": taxon_id,
                "name": name,
                "preferred_common_name": common,
                "taxon_rank": taxon.get("rank"),
                "observations": 0,
                "best_agreements": 0,
            },
        )
        entry["observations"] += 1
        entry["best_agreements"] = max(int(entry["best_agreements"]), agree)

    ordered = sorted(
        counts.values(),
        key=lambda e: (-e["observations"], -e["best_agreements"], e["name"]),
    )
    return [
        e for e in ordered if not any(w in e["preferred_common_name"].lower() for w in STOPWORDS)
    ]


@dataclass(frozen=True)
class SeasonalCue:
    """One evidence-backed "worth a look for" suggestion."""

    #: The instruction shown in large type. Short on purpose.
    text: str
    #: The provenance, shown in small type underneath it. Carries the count, the
    #: radius, the source, and the caveat. Keeping these out of `text` is what
    #: lets the instruction stay one line.
    evidence: str
    common_name: str
    scientific_name: str
    taxon_id: int
    observations: int
    month: int
    year: int
    radius_km: float
    #: The place the radius was measured from, so "nearby" has a referent.
    anchor: str
    #: Where a reader can check the claim themselves.
    source_url: str
    tag: str = "seasonal"

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "evidence": self.evidence,
            "common_name": self.common_name,
            "scientific_name": self.scientific_name,
            "taxon_id": self.taxon_id,
            "observations": self.observations,
            "month": self.month,
            "year": self.year,
            "radius_km": self.radius_km,
            "anchor": self.anchor,
            "source_url": self.source_url,
            "tag": self.tag,
            "source": "iNaturalist, research grade",
        }


@lru_cache(maxsize=24)
def load_snapshot(year: int, month: int) -> dict | None:
    """Load a recorded seasonal snapshot, or ``None`` if there isn't one."""
    path = SEASONAL_DIR / f"blr_{year}_{month:02d}.json"
    if not path.exists():
        log.info("no seasonal snapshot for %04d-%02d", year, month)
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("unreadable seasonal snapshot %s: %s", path, exc)
        return None


def available_snapshots() -> list[str]:
    """Snapshot filenames present, for `baahar check` and the docs."""
    if not SEASONAL_DIR.is_dir():
        return []
    return sorted(p.name for p in SEASONAL_DIR.glob("blr_*.json"))


def _article(word: str) -> str:
    """ "a Brahminy Kite" but "an Indian Red Bug"."""
    return "an" if word[:1].lower() in "aeiou" else "a"


def _fmt_count(n: int) -> str:
    """Word a record count without over- or under-claiming.

    Deliberately vague-but-true. Saying "a few" when there are 200 records would
    undersell it; saying "dozens" when there are three would be a small lie in a
    product whose selling point is not overstating anything.
    """
    if n >= 100:
        return "over a hundred"
    if n >= 20:
        return "dozens of"
    if n >= 10:
        return "around a dozen"
    if n >= 4:
        return "several"
    if n >= 2:
        return "a couple of"
    return "at least one"


def cues_for(
    *,
    year: int | None = None,
    month: int | None = None,
    limit: int = 2,
    radius_km: float = DEFAULT_RADIUS_KM,
) -> list[SeasonalCue]:
    """Seasonal cues for the configured city, or ``[]`` when nothing is recorded.

    Note there is no ``lat``/``lon`` parameter, and that is deliberate rather than
    an oversight. A snapshot is anchored to one city-centre point, so accepting a
    caller's coordinates would invite the caller to believe the radius was
    measured from *their* park. It was not. Passing the park's coordinates here
    would have been the easy lie; the signature makes the truth the only option.

    ``[]`` is a normal, fully-supported outcome: the product falls back to its
    hand-written sensory cues, which is not a degraded state.
    """
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    snapshot = load_snapshot(year, month)
    if not snapshot:
        return []

    candidates = snapshot.get("species") or []
    if not candidates:
        return []

    anchor = str(snapshot.get("city") or "this city")
    snap_radius = float(snapshot.get("radius_km") or radius_km)
    # Clamp rather than trust the caller's radius: a snapshot only measured 5 km
    # around the anchor, so a caller asking for 50 km gets 5 km of honest cue
    # instead of a 50 km claim resting on 5 km of evidence.
    effective_radius = min(radius_km, snap_radius)

    out: list[SeasonalCue] = []
    for entry in candidates:
        common = (entry.get("preferred_common_name") or "").strip()
        sci = (entry.get("name") or "").strip()
        count = int(entry.get("observations") or 0)
        taxon_id = int(entry.get("id") or 0)
        if not common or not sci or count <= 0 or taxon_id <= 0:
            continue

        # The instruction is kept to a single short line. The evidence -- count,
        # radius, source, and the "a record is not a promise" caveat -- lives in
        # `evidence`, which the UI shows underneath in small type. Putting the
        # statistics in the instruction itself made it four lines long, which
        # defeats the whole point of the screen: the reader is supposed to be
        # looking at a tree, not reading a footnote.
        text = f"Look for {_article(common)} {common}."
        evidence = (
            f"iNaturalist research grade: {_fmt_count(count)} recorded within "
            f"{effective_radius:.0f} km of {anchor} this month. A record means "
            f"someone logged it nearby, not that you will see it."
        )
        out.append(
            SeasonalCue(
                text=text,
                evidence=evidence,
                common_name=common,
                scientific_name=sci,
                taxon_id=taxon_id,
                observations=count,
                month=month,
                year=year,
                radius_km=effective_radius,
                anchor=anchor,
                source_url=f"{INAT_URL}/taxa/{taxon_id}",
            )
        )
        if len(out) >= limit:
            break
    return out


def evidence_for(plan_cue: str) -> str:
    """The provenance line for a given seasonal cue text, or ``""``.

    Keyed by cue text because the evidence differs per species: a dozen records
    is a different claim from six. A single global sentence would either repeat
    a number that applies to a different species or drop the numbers entirely.
    """
    for cue in cues_for(limit=_POOL):
        if cue.text == plan_cue:
            return cue.evidence
    return ""


def snapshot_path(year: int, month: int) -> Path:
    return SEASONAL_DIR / f"blr_{year}_{month:02d}.json"
