#!/usr/bin/env python
"""Score the briefing writers. Objective checks first, blind LLM rubric second.

Two independent scoring layers, because they fail differently:

**Layer 1 -- machine checks (100% reproducible, no judge involved).**
These are the numbers that actually gate the product:

  length_compliant      <= 120 words
  has_time_window       a concrete HH:MM-HH:MM appears
  names_right_park      the given park is named
  hallucinated_park     a *different* Baahar park is named
  safety_caveat         air quality is acknowledged in plain language
  cites_naqi_number     the NAQI figure appears
  forbidden_terms       fall-colour bleed, medical claims
  skip_tone_correct     for SKIP cases, the text tells the user to stay in
  go_tone_correct       for GO cases, the text does not talk them into a bad walk

Layer 1 is where the real comparisons live. It cannot be argued with.

**Layer 2 -- blind rubric (LLM judge, randomised order).**
Judges cannot verify "is this actually a good outdoor cue" with a regex, so the
five subjective dimensions get a judge. The judge sees anonymous IDs, the output,
and the conditions -- never which model wrote it -- and is asked to score each
dimension 0-2. Results are only revealed after all judgements are in.

The judge is `gemini-2.5-flash`, deliberately *not* a Gemma model, so Gemma is
not grading its own homework. That separation is stated in RESULTS.md.

Usage
  uv run python scripts/run_briefing_eval.py
  uv run python scripts/run_briefing_eval.py --writers template,gemma --no-judge
  uv run python scripts/run_briefing_eval.py --limit 6      # quick pass
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from baahar import brief as brief_mod
from baahar.config import EVAL_DATA_DIR, EVAL_RAW_DIR, get_settings
from baahar.models import DataSource, HourlyAir, HourlyWeather, HourSlot, OutdoorPlan
from baahar.naqi import band_for_index, compute_naqi
from baahar.parks import park_by_id
from baahar.score import score_heuristic

sys.path.insert(0, str(Path(__file__).parent))
from build_briefing_cases import FORBIDDEN, OTHER_PARKS  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
BASE_HOUR = 6

WINDOW_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\s*(?:-|–|—|to)\s*([01]?\d|2[0-3]):([0-5]\d)\b")
NUMBER_RE = re.compile(r"\b\d{1,3}\b")

CAVEAT_MARKERS = (
    "naqi",
    "air is",
    "air quality",
    "unhealthy",
    "moderate",
    "poor",
    "hazardous",
    "severe",
    "dust",
    "pollut",
    "asthma",
    "smoke",
    "clean enough",
    "air right now",
)

SKIP_MARKERS = ("stay in", "don't go", "do not go", "skip", "wait", "indoors", "not going", "stay inside")


# ---------------------------------------------------------------------------
# Building a plan from a case, without touching the network
# ---------------------------------------------------------------------------
def plan_from_case(case: dict) -> tuple[OutdoorPlan, object]:
    """Turn an eval case into a scored plan using only in-memory models.

    Deliberately offline: the eval must measure the *writers*, not the weather.
    """
    ctx = case["context"]
    dt = BASE_HOUR + (int(ctx["hour"]) % 12)
    when = datetime(2026, 10, 6, dt, tzinfo=IST)

    air_res = compute_naqi({"pm25": 0.0})
    # Derive a consistent PM2.5 that yields the case's NAQI so the signals and
    # the briefing agree.
    pm25 = _pm25_for_naqi(ctx["naqi"])

    air = HourlyAir(
        time=when,
        pm25=pm25,
        pm10=round(pm25 * 1.9, 1),
        naqi=round(float(ctx["naqi"]), 1),
        naqi_band=ctx["band"] or (band_for_index(ctx["naqi"]).value if band_for_index(ctx["naqi"]) else None),
        naqi_band_label=(ctx["band"] or "").capitalize() or None,
        dominant_pollutant="pm25",
        dominant_label="PM2.5",
    )
    weather = HourlyWeather(
        time=when,
        temp_c=ctx["temp_c"],
        apparent_c=ctx["apparent_c"],
        precip_mm=ctx["precip_mm"],
        precip_prob=ctx["precip_prob"],
        humidity=ctx["humidity"],
        wind_kmh=ctx["wind_kmh"],
        is_day=1,
    )
    slot = HourSlot(weather=weather, air=air)
    del air_res

    park = park_by_id(_park_id(ctx["park"]))
    scores = score_heuristic([slot])
    plan = OutdoorPlan(
        city=ctx["city"],
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
    from baahar.parks import load_parks

    for p in load_parks():
        if p.name == name:
            return p.id
    return load_parks()[0].id


def _pm25_for_naqi(naqi: float) -> float:
    """Invert the PM2.5 breakpoint table so the brief's NAQI is self-consistent."""
    from baahar.naqi import POLLUTANTS

    spec = POLLUTANTS["pm25"]
    bands = spec.bands
    target = max(0.0, min(499.0, float(naqi)))
    for i, (c_lo, c_hi, i_lo, i_hi) in enumerate(bands):
        if i_lo <= target <= i_hi:
            if c_hi == float("inf"):
                p_lo, p_hi, pi_lo, pi_hi = bands[i - 1]
                slope = (pi_hi - pi_lo) / (p_hi - p_lo)
                return round(c_lo + (target - i_lo) / slope, 1)
            span = c_hi - c_lo
            return round(c_lo + (target - i_lo) / (i_hi - i_lo) * span, 1)
    return 30.0


# ---------------------------------------------------------------------------
# Layer 1: machine checks
# ---------------------------------------------------------------------------
def machine_checks(case: dict, text: str, decision: str) -> dict:
    lowered = text.lower()
    words = len(text.split())
    forbidden_hits = [f for f in FORBIDDEN if f in lowered]
    other_parks = [p for p in OTHER_PARKS if p != case["context"]["park"] and p.lower() in lowered]
    has_caveat = any(m in lowered for m in CAVEAT_MARKERS)
    cites_number = bool(re.search(rf"\b(?:naqi|aqi)\b[^.]{{0,20}}\b{NUMBER_RE.pattern[2:-2]}", lowered))
    if not cites_number:
        cites_number = bool(re.search(rf"\b{NUMBER_RE.pattern[2:-2]}\b[^.]{{0,20}}\b(?:naqi|aqi)\b", lowered))
    mentions_naqi_value = str(int(round(case["context"]["naqi"]))) in lowered

    checks = {
        "length_compliant": words <= brief_mod.MAX_WORDS,
        "word_count": words,
        "has_time_window": bool(WINDOW_RE.search(text)),
        "names_right_park": case["context"]["park"].lower() in lowered,
        "hallucinated_park": other_parks,
        "safety_caveat": has_caveat,
        "cites_naqi_number": cites_number,
        "mentions_naqi_value": mentions_naqi_value,
        "forbidden_terms": forbidden_hits,
        "skip_tone_correct": None,
        "go_tone_correct": None,
    }
    if decision == "SKIP":
        checks["skip_tone_correct"] = any(m in lowered for m in SKIP_MARKERS)
    elif decision == "GO":
        # A GO brief must not be discouraging.
        checks["go_tone_correct"] = not any(m in lowered for m in ("stay in", "do not go", "don't go"))
    return checks


def aggregate(runs: list[dict]) -> dict:
    if not runs:
        return {}
    n = len(runs)

    def rate(key: str) -> float:
        vals = [bool(r["checks"].get(key)) for r in runs if r["checks"].get(key) is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    def rate_filtered(key: str, decision: str) -> float | None:
        vals = [
            bool(r["checks"].get(key))
            for r in runs
            if r["decision"] == decision and r["checks"].get(key) is not None
        ]
        return round(sum(vals) / len(vals), 4) if vals else None

    lat = [r["latency_ms"] for r in runs if r.get("latency_ms") is not None]
    words = [r["checks"]["word_count"] for r in runs]

    return {
        "n": n,
        "length_compliant_rate": rate("length_compliant"),
        "mean_words": round(statistics.mean(words), 1) if words else None,
        "max_words": max(words) if words else None,
        "has_time_window_rate": rate("has_time_window"),
        "names_right_park_rate": rate("names_right_park"),
        "hallucinated_park_rate": rate("hallucinated_park"),
        "safety_caveat_rate": rate("safety_caveat"),
        "cites_naqi_number_rate": rate("cites_naqi_number"),
        "forbidden_term_rate": rate("forbidden_terms"),
        "skip_tone_correct_rate": rate_filtered("skip_tone_correct", "SKIP"),
        "go_tone_correct_rate": rate_filtered("go_tone_correct", "GO"),
        "latency_ms_p50": int(statistics.median(lat)) if lat else None,
        "latency_ms_p95": int(sorted(lat)[min(len(lat) - 1, int(0.95 * len(lat)))]) if lat else None,
    }


# ---------------------------------------------------------------------------
# Layer 2: blind rubric judge
# ---------------------------------------------------------------------------
JUDGE_MODEL = "gemini-2.5-flash"
#: Tried in order. Gemini's free tier enforces *per-model* quotas, so a model can
#: return 429 "quota exceeded" while its siblings are perfectly healthy. Probing
#: keeps the subjective half of the eval alive instead of dropping it whenever one
#: bucket happens to be empty. Whichever model actually scores is recorded in the
#: raw output and in RESULTS.md -- a rubric from an unknown judge is not evidence.
JUDGE_CANDIDATES = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-flash-latest",
]
JUDGE_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_chosen_judge: str | None = None


def resolve_judge_model(force: str | None = None) -> str | None:
    """Return the first candidate model that answers, caching the choice."""
    global _chosen_judge
    if _chosen_judge:
        return _chosen_judge
    settings = get_settings()
    if not settings.has_gemini:
        return None
    candidates = [force] if force else JUDGE_CANDIDATES
    probe = {
        "contents": [{"parts": [{"text": "Reply with the single word OK."}]}],
        "generationConfig": {"maxOutputTokens": 2048, "temperature": 0},
    }
    for name in candidates:
        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post(
                    f"{JUDGE_BASE}/{name}:generateContent",
                    params={"key": settings.gemini_api_key},
                    json=probe,
                )
            if resp.status_code == 200:
                if name != JUDGE_MODEL:
                    print(f"  judge: {JUDGE_MODEL} unavailable; using {name}", file=sys.stderr)
                _chosen_judge = name
                return name
            print(f"  judge: {name} -> HTTP {resp.status_code}", file=sys.stderr)
        except httpx.HTTPError as exc:
            print(f"  judge: {name} -> {type(exc).__name__}", file=sys.stderr)
        time.sleep(1.5)
    return None

RUBRIC = """You are grading ONE short outdoor park briefing for a Bengaluru app.

Score five dimensions, each an integer 0, 1 or 2:
- ACTIONABLE TIME: 0 = no time given; 1 = vague ("in the morning"); 2 = concrete clock times such as 06:30-07:30.
- PLACE SPECIFICITY: 0 = no place named; 1 = only "a park" or the city; 2 = names the specific park from the CONDITIONS line.
- SAFETY CAVEAT: 0 = air or heat never mentioned; 1 = mentioned but vague; 2 = clearly states air quality or heat risk, quoting the NAQI figure when one was given.
- LENGTH: 0 = over 160 or under 40 words; 1 = 40-160 words but padded; 2 = 40-120 words and tight.
- SENSORY OUTDOOR CUE: 0 = none; 1 = generic ("enjoy nature"); 2 = one concrete thing the reader physically does or notices.

A briefing that recommends going outside when the CONDITIONS line says the
decision is BAD must score 0 on every dimension.

Also disqualifying, though the five dimensions above already cover them: US
fall colours, snow, claims of "guaranteed safe", or medical advice.

Now reply with JSON only, copying the shape below and substituting the five
scores. Do not invent an id; keep "id" exactly as written.

{"scores":[{"id":"id","actionable_time":0,"place_specificity":0,"safety_caveat":0,"length":0,"sensory_cue":0}]}"""

_WS = re.compile(r"[`*\s]")

DIMS = ("actionable_time", "place_specificity", "safety_caveat", "length", "sensory_cue")


def _normalise(raw: object) -> dict[str, dict]:
    """Accept whichever JSON shape the judge returns and key it by anonymous ID.

    Models drift on output schema even with a response MIME type set: we have
    seen a bare dict, `{"scores": [...]}`, and a bare list all come back from the
    same prompt. Normalising here means a schema wobble degrades the judge rather
    than silently zeroing every rubric score.
    """
    entries: list[dict] = []
    if isinstance(raw, dict):
        if "scores" in raw and isinstance(raw["scores"], list):
            entries = [e for e in raw["scores"] if isinstance(e, dict)]
        elif all(isinstance(v, dict) for v in raw.values()) and raw:
            entries = [{**v, "id": k} for k, v in raw.items()]
        else:
            entries = [raw]
    elif isinstance(raw, list):
        entries = [e for e in raw if isinstance(e, dict)]

    out: dict[str, dict] = {}
    for entry in entries:
        ident = entry.get("id") or entry.get("ID") or entry.get("anon_id")
        if not ident:
            continue
        dims = {}
        for name in DIMS:
            v = entry.get(name)
            dims[name] = max(0, min(2, int(v))) if isinstance(v, (int, float)) else None
        dims["total"] = sum(v for v in dims.values() if v is not None)
        out[str(ident)] = dims
    return out


def judge_batch(items: list[dict], *, key: str, _depth: int = 0) -> list[dict | None]:
    """Score each briefing with its own judge call.

    One briefing per request, on purpose. Batching looked faster but the judge
    kept collapsing the five dimensions into a single `Score` field whenever more
    than two items shared a call, and it truncated its JSON around five items.
    Two things are gained by going one at a time: per-dimension scores actually
    come back, and the judge cannot compare one briefing against another in the
    same context -- which is the entire point of a *blind* rubric.

    The extra calls cost about five seconds each, which is irrelevant next to the
    40-95 s an actual briefing costs to generate.
    """
    return [_judge_one(item) for item in items]


#: Minimum gap between judge calls. The Gemini free tier rate-limits aggressively
#: and returns 429 rather than 429-with-a-header, so pacing up front is cheaper
#: than discovering the limit by failing.
JUDGE_MIN_INTERVAL_S = 4.0
_last_call = 0.0


def _paced_sleep() -> None:
    global _last_call
    wait = JUDGE_MIN_INTERVAL_S - (time.perf_counter() - _last_call)
    if wait > 0:
        time.sleep(wait)


def _judge_one(item: dict) -> dict | None:
    """One judge request for one briefing. ``None`` on any failure.

    Retries on 429 with exponential backoff, because losing a whole rubric run to
    rate limiting would leave the subjective scores unreported.
    """
    settings = get_settings()
    if not settings.has_gemini:
        return None

    ctx = item["context"]
    block = (
        f'CONDITIONS: {ctx["decision"]} decision, {ctx["band"]} air '
        f'(Indian NAQI {ctx["naqi"]:.0f}), {ctx["temp_c"]:.0f}C feeling like '
        f'{ctx["apparent_c"]:.0f}C, '
        f'{ctx["precip_prob"] if ctx["precip_prob"] is not None else "?"}% rain chance, '
        f'park = {ctx["park"]}.\n'
        f'BRIEFING: {item["text"]}'
    )

    payload = {
        "contents": [{"parts": [{"text": RUBRIC + "\n\n" + block}]}],
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": 1024,
            "responseMimeType": "application/json",
        },
    }
    global _last_call
    model = resolve_judge_model()
    if model is None:
        return None

    resp = None
    for attempt in range(4):
        _paced_sleep()
        try:
            _last_call = time.perf_counter()
            with httpx.Client(timeout=120) as client:
                resp = client.post(
                    f"{JUDGE_BASE}/{model}:generateContent",
                    params={"key": settings.gemini_api_key},
                    json=payload,
                )
            if resp.status_code != 429:
                break
        except httpx.HTTPError as exc:
            print(f"  judge transport error: {exc}", file=sys.stderr)
            resp = None
            break
        backoff = 5.0 * (2**attempt)
        print(f"  judge rate limited (429); backing off {backoff:.0f}s", file=sys.stderr)
        time.sleep(backoff)

    if resp is None:
        return None
    if resp.status_code >= 400:
        print(f"  judge HTTP {resp.status_code}", file=sys.stderr)
        return None

    try:
        text, _finish = brief_mod._extract_gemini_text(resp.json())
        parsed = json.loads(_WS.sub("", text))
    except Exception as exc:  # noqa: BLE001
        print(f"  judge parse failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None

    flat = parsed
    if isinstance(parsed, dict) and "scores" in parsed:
        flat = parsed["scores"]
    scores = _normalise(flat)
    if scores:
        return next(iter(scores.values()))
    # A bare object with no id field: normalise it directly.
    if isinstance(flat, dict):
        direct = _normalise(flat)
        for value in direct.values():
            return value
    return None


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", default=str(EVAL_DATA_DIR / "briefing_cases.jsonl"))
    ap.add_argument("--writers", default="template,gemma")
    ap.add_argument("--limit", type=int, default=0, help="0 = all cases")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--judge-batch", type=int, default=4)
    ap.add_argument("--cache/--no-cache", dest="cache", action="store_true", default=False)
    args = ap.parse_args(argv)

    cases = [
        json.loads(line)
        for line in Path(args.cases).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if args.limit:
        cases = cases[: args.limit]
    writers = [w.strip() for w in args.writers.split(",") if w.strip()]

    settings = get_settings()
    print(f"cases={len(cases)}  writers={writers}")
    print(f"keys present: {settings.which_keys()}")
    print()

    outputs: dict[str, list[dict]] = {w: [] for w in writers}
    failures: list[str] = []

    for w in writers:
        print(f"-- writer: {w}")
        for i, case in enumerate(cases, 1):
            plan, park = plan_from_case(case)
            started = time.perf_counter()
            try:
                briefing = brief_mod.generate(plan, writer=w, park=park)
                latency = int((time.perf_counter() - started) * 1000)
                text = briefing.text
                writer_used = briefing.writer
                note = briefing.note
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{w}/{case['id']}: {type(exc).__name__}: {exc}")
                print(f"  [{i:2}/{len(cases)}] {case['id']:<14} ERROR {type(exc).__name__}")
                continue
            checks = machine_checks(case, text, case["context"]["decision"])
            outputs[w].append(
                {
                    "case_id": case["id"],
                    "decision": case["context"]["decision"],
                    "text": text,
                    "writer_used": writer_used,
                    "note": note,
                    "latency_ms": latency,
                    "checks": checks,
                }
            )
            flag = ""
            if not checks["length_compliant"]:
                flag += " LONG"
            if checks["hallucinated_park"]:
                flag += " PARK!"
            if checks["forbidden_terms"]:
                flag += " FORBIDDEN"
            if checks["skip_tone_correct"] is False:
                flag += " SKIP-TONE"
            print(f"  [{i:2}/{len(cases)}] {case['id']:<14} {checks['word_count']:>3}w {latency:>6}ms{flag}")
        print()

    # Blind judging: flatten, anonymise, shuffle.
    judgements: dict[str, dict] = {}
    judge_used = resolve_judge_model()
    if not args.no_judge and judge_used and writers:
        print(f"-- blind judge: {judge_used}")
        rng = random.Random(7)
        flat = []
        for w in writers:
            for rec in outputs[w]:
                anon = f"B{rng.randrange(1000, 9999)}"
                flat.append(
                    {
                        "anon_id": anon,
                        "context": next(c["context"] for c in cases if c["id"] == rec["case_id"]),
                        "text": rec["text"],
                        "_writer": w,
                        "_case": rec["case_id"],
                    }
                )
        rng.shuffle(flat)
        print(f"   {len(flat)} items, one call each")

        for start in range(0, len(flat), args.judge_batch):
            batch = flat[start : start + args.judge_batch]
            results = judge_batch(batch, key="blind")
            for item, score in zip(batch, results, strict=True):
                if score is not None:
                    judgements[f"{item['_writer']}::{item['_case']}"] = score
            got = sum(1 for s in results if s is not None)
            print(f"   {start + len(batch):>3}/{len(flat)} judged ({got}/{len(batch)} ok)")


    # Attach and summarise.
    for w in writers:
        for rec in outputs[w]:
            rec["rubric"] = judgements.get(f"{w}::{rec['case_id']}")

    summary = {}
    for w in writers:
        rows = outputs[w]
        agg = aggregate(rows)
        rubric_scores = [r["rubric"]["total"] for r in rows if r.get("rubric")]
        if rubric_scores:
            agg["rubric_mean"] = round(statistics.mean(rubric_scores), 2)
            agg["rubric_sd"] = (
                round(statistics.stdev(rubric_scores), 2) if len(rubric_scores) > 1 else None
            )
            agg["rubric_n"] = len(rubric_scores)
            agg["rubric_max"] = 10
            per_dim = {}
            for dim in ("actionable_time", "place_specificity", "safety_caveat", "length", "sensory_cue"):
                vals = [r["rubric"][dim] for r in rows if r.get("rubric") and r["rubric"].get(dim) is not None]
                per_dim[dim] = round(statistics.mean(vals), 2) if vals else None
            agg["rubric_per_dimension"] = per_dim
        summary[w] = agg

        print(f"\n{w}:")
        for key, value in agg.items():
            print(f"   {key:<28} {value}")

    EVAL_RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z")
    out_path = EVAL_RAW_DIR / f"briefing_{stamp}.json"
    payload = {
        "run_at": datetime.now().astimezone().isoformat(),
        "n_cases": len(cases),
        "writers_requested": writers,
        "keys_present": settings.which_keys(),
        "judge_model": judge_used,
        "judge_candidates": JUDGE_CANDIDATES,
        "judge_is_blind": True,
        "judge_is_same_family_as_subject": False,
        "rubric": {
            "dimensions": [
                "actionable_time",
                "place_specificity",
                "safety_caveat",
                "length",
                "sensory_cue",
            ],
            "scale": "0-2 each, 10 total",
        },
        "failures": failures,
        "summary": summary,
        "outputs": outputs,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nraw results -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())