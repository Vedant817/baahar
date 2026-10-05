#!/usr/bin/env python
"""Build the briefing eval cases from the historical dataset.

The cases are *sampled from real Bengaluru conditions* rather than invented, so
the eval exercises the range the product actually meets: clean October mornings,
dusty afternoons, monsoon rain, and the genuinely bad winter days.

Sampling is stratified on the ground-truth decision so that SKIP cases are
represented. Naive sampling from the raw distribution would give roughly one SKIP
case in fifty, which is not enough to measure the failure mode that matters.

Two kinds of check are attached to every case:

  must_include  substrings a correct briefing must contain (e.g. the park name,
                or an NAQI figure). Machine-checkable.
  must_not      strings a correct briefing must not contain -- hallucinated
                parks, US-foliage bleed, medical claims. Machine-checkable.

The subjective rubric (clarity, place specificity, sensory cue) is scored
separately by a blind judge in `run_briefing_eval.py`.

Usage
  uv run python scripts/build_briefing_cases.py
  uv run python scripts/build_briefing_cases.py --per-decision 12
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from baahar.config import EVAL_DATA_DIR, get_settings
from baahar.parks import load_parks

sys.path.insert(0, str(Path(__file__).parent))
from build_dataset import apply_band_policy  # noqa: E402

OUT_PATH = EVAL_DATA_DIR / "briefing_cases.jsonl"
SEED = 20261006

#: Words that must never appear in a Bengaluru briefing. These are the
#: hallucination classes actually observed in early testing.
FORBIDDEN = [
    "fall colors",
    "fall colours",
    "fall foliage",
    "new england",
    "autumn leaves",
    "snow",
    "frost",
    "blizzard",
    "guaranteed safe",
    "guaranteed",
    "medical cure",
    "you will be fine",
    "completely safe",
]

#: Park names Baahar must not mention unless that is the chosen park.
OTHER_PARKS = [p.name for p in load_parks()]


def choose_park(rng: random.Random, decision: str) -> str:
    """Pick a plausible park. SKIP cases lean toward the outer trips, which is
    where people are most likely to have made the mistake of driving out."""
    parks = load_parks()
    if decision == "SKIP":
        outer = [p for p in parks if p.area in {"north", "east"}] or parks
        return rng.choice(outer).name
    return rng.choice(parks).name


def build_cases(per_decision: int, seed: int) -> list[dict]:
    rows_path = EVAL_DATA_DIR / "gono_rows.jsonl"
    if not rows_path.exists():
        raise SystemExit(f"{rows_path} missing; run scripts/build_dataset.py first")

    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rng = random.Random(seed)

    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        # Recompute the decision with the row's own hour-t weather so the case
        # matches the conditions we actually hand the writer.
        dec = apply_band_policy(r["target_band"], r["precip_mm"], r["precip_prob"], r["apparent_c"])
        r = dict(r)
        r["decision"] = dec
        buckets[dec].append(r)

    cases: list[dict] = []
    for decision, pool in sorted(buckets.items()):
        if len(pool) < per_decision:
            print(f"  warning: only {len(pool)} {decision} rows available", file=sys.stderr)
        # Prefer well-separated timestamps so the cases are not 36 views of one
        # bad afternoon.
        pool.sort(key=lambda r: r["time"])
        picked: list[dict] = []
        used_days: set[str] = set()
        for r in pool:
            if len(picked) >= per_decision:
                break
            day = r["time"][:10]
            if day in used_days and len(picked) > 1:
                continue
            used_days.add(day)
            picked.append(r)
        for r in picked[:per_decision]:
            park = choose_park(rng, decision)
            must_include = [park]
            must_not = [
                p for p in OTHER_PARKS if p != park
            ] + FORBIDDEN
            dt = datetime.fromisoformat(r["time"])
            cases.append(
                {
                    "id": f"{decision.lower()}-{dt.strftime('%m%d-%H')}",
                    "source_row_time": r["time"],
                    "context": {
                        "city": get_settings().city,
                        "decision": decision,
                        "hour": dt.hour,
                        "park": park,
                        "naqi": r["naqi"],
                        "band": r["band"],
                        "temp_c": r["temp_c"],
                        "apparent_c": r["apparent_c"],
                        "precip_mm": r["precip_mm"],
                        "precip_prob": r["precip_prob"],
                        "humidity": r["humidity"],
                        "wind_kmh": r["wind_kmh"],
                    },
                    "must_include": must_include,
                    "must_not": must_not,
                }
            )
    return cases


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--per-decision", type=int, default=12)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args(argv)

    cases = build_cases(args.per_decision, args.seed)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as fh:
        for case in cases:
            fh.write(json.dumps(case) + "\n")

    from collections import Counter

    counts = Counter(c["context"]["decision"] for c in cases)
    naqis = [c["context"]["naqi"] for c in cases]
    print(f"wrote {len(cases)} cases -> {OUT_PATH}")
    for decision, count in sorted(counts.items()):
        print(f"  {decision:<6} {count}")
    print(f"  NAQI range {min(naqis):.0f}..{max(naqis):.0f}")
    print(f"  distinct parks {len({c['context']['park'] for c in cases})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())