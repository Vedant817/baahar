#!/usr/bin/env python
"""Record a seasonal species snapshot from iNaturalist.

Writes ``data/seasonal/blr_<year>_<month>.json``. The product reads that
snapshot rather than calling the API at request time, so Pocket Mode never waits
on a third party and every claim in the write-up is traceable to a committed
file.

Method
------
1. Query research-grade observations within a radius of Bengaluru.
2. Group by taxon, keeping the species with the most *agreeing* observations.
3. Drop anything with a common name containing a word we already use ("bird"),
   so the seasonal cues do not duplicate the hand-written ones.
4. Write the query, the counts, and the timestamp alongside the data.

No API key is needed. Be polite: this is 3 requests, run by hand.

Usage
    uv run python scripts/refresh_seasonal.py
    uv run python scripts/refresh_seasonal.py --year 2026 --month 10 --limit 8
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

import httpx

from baahar.config import get_settings
from baahar.seasonal import (
    API_URL,
    DEFAULT_RADIUS_KM,
    INAT_URL,
    SEASONAL_DIR,
    snapshot_path,
    tally,
)

UA = {"User-Agent": "Baahar/0.1 (HF26 Touch Grass; https://github.com/Vedant817/baahar)"}


def fetch_research_observations(
    lat: float,
    lon: float,
    radius_km: float,
    month: int | None,
    per_page: int = 200,
    max_pages: int = 3,
) -> list[dict]:
    """Research-grade observations near a point, optionally for one month.

    Paginated, because one page is 200 records and the resulting counts decide
    how a cue is worded ("a few" vs "dozens"). One page made every species look
    equally rare, which would have made the wording meaningless.
    """
    results: list[dict] = []
    params: dict = {
        "lat": lat,
        "lng": lon,
        "radius": max(1, int(radius_km)),
        "quality_grade": "research",
        "per_page": per_page,
        "order_by": "obs_date",
        "identifications": "most_agree",
    }
    if month:
        params["month"] = month

    with httpx.Client(timeout=60, headers=UA) as client:
        for page in range(1, max_pages + 1):
            resp = client.get(f"{API_URL}/observations", params={**params, "page": page})
            resp.raise_for_status()
            payload = resp.json()
            batch = payload.get("results") or []
            results.extend(batch)
            if len(batch) < per_page:
                break
    return results


def fetch_taxon_details(taxon_id: int) -> dict:
    """Order and reference link for one taxon.

    The observations payload carries no taxonomic order, and order is what lets
    the snapshot avoid suggesting three butterflies in a row -- which reads as a
    bug even when each sighting is real. Eight extra requests is cheap for a
    script run by hand.
    """
    with httpx.Client(timeout=30, headers=UA) as client:
        resp = client.get(f"{API_URL}/taxa/{taxon_id}")
    resp.raise_for_status()
    results = resp.json().get("results") or []
    if not results:
        return {}
    t = results[0]
    return {
        "order": t.get("order") or t.get("iconic_taxon_name") or "unknown",
        "wikipedia_url": t.get("wikipedia_url"),
        "iconic_group": t.get("iconic_taxon_name"),
    }


def diversify(species: list[dict], limit: int, *, pool: int = 16) -> list[dict]:
    """Keep the best-documented species from each distinct taxonomic order.

    Taking the top N by raw count produced three butterflies and a dragonfly,
    which is a worse walk than one of each. Grouping by order keeps the cue list
    varied without cherry-picking: the most-recorded species of each group wins,
    and the groups are chosen by the data, not by taste.
    """
    shortlist = species[:pool]
    seen: set[str] = set()
    out: list[dict] = []
    for entry in shortlist:
        try:
            details = fetch_taxon_details(int(entry["id"]))
        except httpx.HTTPError as exc:
            print(f"  taxon lookup failed for {entry['name']}: {exc}", file=sys.stderr)
            details = {}
        entry = {**entry, **details}
        order = str(entry.get("order") or "unknown")
        if order in seen:
            continue
        seen.add(order)
        out.append(entry)
        if len(out) >= limit:
            break
    return out


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    now = datetime.now()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int, default=now.year)
    ap.add_argument("--month", type=int, default=now.month)
    ap.add_argument("--radius-km", type=float, default=DEFAULT_RADIUS_KM)
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--all-months", action="store_true", help="ignore --month")
    args = ap.parse_args(argv)

    month = None if args.all_months else args.month
    label = "all months" if month is None else f"month {month:02d}"

    print(
        f"querying iNaturalist: research grade, {args.radius_km:.0f} km around "
        f"{settings.city} ({settings.lat}, {settings.lon}), {label}"
    )

    try:
        observations = fetch_research_observations(
            settings.lat, settings.lon, args.radius_km, month
        )
    except httpx.HTTPError as exc:
        print(f"iNaturalist request failed: {exc}", file=sys.stderr)
        return 1

    if not observations:
        print("no research-grade observations returned; not writing a snapshot", file=sys.stderr)
        return 1

    species = diversify(tally(observations), args.limit)
    if not species:
        print("nothing survived the common-name filter", file=sys.stderr)
        return 1

    payload = {
        "recorded_at": datetime.now().astimezone().isoformat(),
        "city": settings.city,
        "lat": settings.lat,
        "lon": settings.lon,
        "radius_km": args.radius_km,
        "year": args.year,
        "month": None if month is None else month,
        "query": {
            "source": INAT_URL,
            "api": f"{API_URL}/observations",
            "params": {
                "lat": settings.lat,
                "lng": settings.lon,
                "radius": max(1, int(args.radius_km)),
                "quality_grade": "research",
                "month": month,
                "identifications": "most_agree",
            },
        },
        "observations_examined": len(observations),
        "species_found": len(species),
        "honesty_note": (
            "Research grade means other observers agreed with the identification. "
            "A record means someone logged the species within this radius, NOT "
            "that a visitor will see it."
        ),
        "licence": (
            "Observation data contributed to iNaturalist by its community; "
            "record licences are CC0 or CC-BY per record."
        ),
        "species": species,
    }

    out = SEASONAL_DIR / "blr_all_months.json" if month is None else snapshot_path(args.year, month)
    SEASONAL_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"\nexamined {len(observations)} research-grade records -> {out.name}")
    print(f"kept {len(species)} species:\n")
    for entry in species:
        print(
            f"  {entry['observations']:>4}x  {entry['preferred_common_name']:<34} "
            f"{entry['name']:<30} [{entry.get('order') or '?'}]"
        )
    print(
        "\nCues will say 'recorded nearby', never 'you will see'. "
        "Verify a claim with: "
        f"{INAT_URL}/observations?lat={settings.lat}&lng={settings.lon}"
        f"&radius={max(1, int(args.radius_km))}&quality_grade=research"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
