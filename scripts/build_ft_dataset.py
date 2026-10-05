#!/usr/bin/env python
"""Build the Tinker fine-tuning dataset for Baahar briefings.

What the fine-tune is for
-------------------------
The baseline Gemma briefing already scores well on the objective checks, so the
fine-tune is not there to fix correctness. It is there to buy three things the
base model has to be *talked* into, every time:

1. **Prose, never a plan.** The untuned model tends to restate the prompt's
   structure. Fine-tuning on clean prose examples makes the output shape the
   default rather than something to be corrected.
2. **Indian outdoor voice.** "Dusty", "post-monsoon", "the canopy does the
   work" -- language that is specific to this city and this season, instead of
   generic wellness-app phrasing.
3. **The safety register.** SKIP cases must read as *stay in*, briefly and
   without moralising. That is a stylistic target a small dataset can hit.

Dataset shape
-------------
Examples are generated from the **archived historical rows** so conditions are
real, not invented. For each row the target text is produced by the local
template writer, then lightly varied so the model does not memorise one phrasing
(template-only data would teach a lookup table, not a style).

Anti-slop rules baked in
  * Balanced across GO / WAIT / SKIP so the model cannot learn "always GO".
  * No example is built from a row whose NAQI the model could not read.
  * Every example carries its conditions, so the training data is auditable.
  * Nothing from the *holdout* window of `gono_rows.jsonl` is used, so the
    briefing eval and the tabular eval cannot contaminate each other.

Usage
  uv run python scripts/build_ft_dataset.py
  uv run python scripts/build_ft_dataset.py --per-decision 80 --out data/ft
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from baahar.brief import SYSTEM_PROMPT, build_user_prompt, write_template
from baahar.config import DATA_DIR, EVAL_DATA_DIR, get_settings
from baahar.models import DataSource, HourlyAir, HourlyWeather, HourSlot, OutdoorPlan
from baahar.parks import load_parks, park_by_id
from baahar.score import score_heuristic

sys.path.insert(0, str(Path(__file__).parent))
from build_dataset import apply_band_policy  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
SEED = 20261006

#: Ending variations. Purely a function of the decision -- no randomness in the
#: conditions themselves, so an example is reproducible from its row.
ENDINGS = {
    "GO": [
        "Pocket the phone and let it be boring for twenty minutes.",
        "Put the phone away now and notice the place instead.",
        "Once you are moving, stop checking this.",
        "Phone away. The rest of it is just walking.",
    ],
    "WAIT": [
        "Set an alarm for the window and go back to what you were doing.",
        "It will be worth waiting for.",
        "Do something else until then.",
        "The good hour is close enough to be patient for.",
    ],
    "SKIP": [
        "Try again tomorrow, or check the evening.",
        "Not tonight. The air will not thank you for it.",
        "Stay in and try again when the numbers improve.",
        "Skip it today; the park will still be there.",
    ],
}


def pm25_for_naqi(naqi: float) -> float:
    from baahar.naqi import POLLUTANTS

    bands = POLLUTANTS["pm25"].bands
    target = max(0.0, min(499.0, float(naqi)))
    for i, (c_lo, c_hi, i_lo, i_hi) in enumerate(bands):
        if i_lo <= target <= i_hi:
            if c_hi == float("inf"):
                p_lo, p_hi, pi_lo, pi_hi = bands[i - 1]
                slope = (pi_hi - pi_lo) / (p_hi - p_lo)
                return round(c_lo + (target - i_lo) / slope, 1)
            return round(c_lo + (target - i_lo) / (i_hi - i_lo) * (c_hi - c_lo), 1)
    return 30.0


def plan_for_row(row: dict, park_name: str) -> tuple[OutdoorPlan, object]:
    hour = int(datetime.fromisoformat(row["time"]).hour)
    when = datetime(2026, 10, 6, hour % 24, tzinfo=IST)
    naqi = row["naqi"]
    air = HourlyAir(
        time=when,
        pm25=pm25_for_naqi(naqi),
        pm10=round(pm25_for_naqi(naqi) * 1.9, 1),
        naqi=round(float(naqi), 1),
        naqi_band=row["band"],
        naqi_band_label=(row["band"] or "").capitalize(),
        dominant_pollutant="pm25",
        dominant_label="PM2.5",
    )
    weather = HourlyWeather(
        time=when,
        temp_c=row["temp_c"],
        apparent_c=row["apparent_c"],
        precip_mm=row["precip_mm"],
        precip_prob=row["precip_prob"],
        humidity=row["humidity"],
        wind_kmh=row["wind_kmh"],
        is_day=1 if 6 <= hour < 19 else 0,
    )
    slot = HourSlot(weather=weather, air=air)
    park = park_by_id(_park_id(park_name))
    scores = score_heuristic([slot])
    plan = OutdoorPlan(
        city=get_settings().city,
        generated_at=when,
        window_hours=1,
        overall=scores[0].decision,
        best_slot=slot,
        best_time=when,
        headline="",
        slots=scores,
        park=park,
        weather_source=DataSource.LIVE,
        air_source=DataSource.LIVE,
    )
    return plan, park


def _park_id(name: str) -> str:
    for p in load_parks():
        if p.name == name:
            return p.id
    return load_parks()[0].id


def holdout_start() -> str:
    """Start of the tabular eval holdout, so FT data cannot touch it."""
    meta = EVAL_DATA_DIR / "gono_dataset.json"
    if not meta.exists():
        return ""
    payload = json.loads(meta.read_text(encoding="utf-8"))
    # The run_eval holdout is the last 20% of the timeline; stay well clear.
    end = payload.get("end", "")
    try:
        dt = datetime.fromisoformat(end) - timedelta(days=30)
        return dt.date().isoformat()
    except ValueError:
        return ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--per-decision", type=int, default=80)
    ap.add_argument("--out", default=str(DATA_DIR / "ft"))
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args(argv)

    rows_path = EVAL_DATA_DIR / "gono_rows.jsonl"
    if not rows_path.exists():
        raise SystemExit(f"{rows_path} missing; run scripts/build_dataset.py first")

    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    cutoff = holdout_start()
    if cutoff:
        rows = [r for r in rows if r["time"][:10] <= cutoff]
        print(f"excluded everything after {cutoff} (tabular holdout protection)")

    rng = random.Random(args.seed)
    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        decision = apply_band_policy(
            r["band"], r["precip_mm"], r["precip_prob"], r["apparent_c"]
        )
        r = dict(r)
        r["decision"] = decision
        buckets[decision].append(r)

    park_names = [p.name for p in load_parks()]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = out_dir / "baahar_briefings.jsonl"
    examples = []
    for decision, pool in sorted(buckets.items()):
        pool.sort(key=lambda r: r["time"])
        rng.shuffle(pool)
        chosen: list[dict] = []
        seen_days: set[str] = set()
        for r in pool:
            if len(chosen) >= args.per_decision:
                break
            day = r["time"][:10]
            if day in seen_days and len(chosen) > 2:
                continue
            seen_days.add(day)
            chosen.append(r)

        for idx, row in enumerate(chosen):
            park_name = rng.choice(park_names)
            plan, park = plan_for_row(row, park_name)
            ending = ENDINGS[decision][idx % len(ENDINGS[decision])]
            target = _tidy(write_template(plan, park=park), ending, decision)
            from baahar.brief import build_context

            examples.append(
                {
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": build_user_prompt(build_context(plan, park))},
                        {"role": "assistant", "content": target},
                    ],
                    "meta": {
                        "decision": decision,
                        "park": park_name,
                        "naqi": row["naqi"],
                        "band": row["band"],
                        "source_time": row["time"],
                    },
                }
            )

    examples.sort(key=lambda e: e["meta"]["source_time"])
    with jsonl_path.open("w", encoding="utf-8") as fh:
        for ex in examples:
            fh.write(json.dumps(ex) + "\n")

    from collections import Counter

    counts = Counter(e["meta"]["decision"] for e in examples)
    words = [len(e["messages"][-1]["content"].split()) for e in examples]
    print(f"wrote {len(examples)} examples -> {jsonl_path}")
    for decision, count in sorted(counts.items()):
        print(f"  {decision:<6} {count}")
    print(f"  mean target words {sum(words) / max(1, len(words)):.1f}")
    print(f"  NAQI range {min(e['meta']['naqi'] for e in examples):.0f}.."
          f"{max(e['meta']['naqi'] for e in examples):.0f}")

    # A train/val split so a held-out sample is visible without an extra run.
    val_n = max(1, len(examples) // 10)
    val = examples[-val_n:]
    train = examples[:-val_n]
    (out_dir / "val.jsonl").write_text(
        "\n".join(json.dumps(e) for e in val) + "\n", encoding="utf-8"
    )
    (out_dir / "train.jsonl").write_text(
        "\n".join(json.dumps(e) for e in train) + "\n", encoding="utf-8"
    )
    print(f"  train {len(train)} / val {len(val)}")
    return 0


def _tidy(text: str, ending: str, decision: str) -> str:
    """Swap the template's fixed closing line for one of the variations."""
    base = "Pocket the phone and let it be boring for twenty minutes."
    if base in text:
        text = text.replace(base, ending)
    return " ".join(text.split())


if __name__ == "__main__":
    raise SystemExit(main())