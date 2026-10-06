#!/usr/bin/env python
"""Build the go/no-go evaluation dataset from Open-Meteo archives.

Why this dataset exists, and what it deliberately is not
-------------------------------------------------------
The obvious version of this task is circular: define labels with a rule, train
a model to reproduce that rule, and report the accuracy as if the model had
discovered something. We are not doing that.

Instead the task is a genuine **next-step prediction**:

    Given what was known at hour *t* (current air, current weather, time of day,
    seasonality), predict the CPCB NAQI **band six hours ahead**, where the
    target is computed from an independent reading of that future hour.

  * Features come only from hour *t*. Nothing downstream of the split can see
    hour *t+6*. See `assert_no_leakage`.
  * The `naqi` feature is the **effective** (conservative) reading -- the higher
    of the hour's instantaneous value and its trailing-mean value, i.e. what
    `baahar.features.features_from_slot` serves and what the policy acts on. The
    instantaneous reading is kept beside it as `naqi_instant`. Fitting on one and
    serving the other under the same column name is the train/serve skew this
    project already paid for once; see `NAQI_FEATURE_NOTE`.
  * The label is a *band* (6 classes), and the GO/WAIT/SKIP decision is a
    documented policy applied on top of the predicted band by
    `apply_band_policy`. That keeps the safety rule human-readable and stops the
    model from being asked to learn a policy we can write down exactly.
  * Autocorrelation is the whole difficulty: Bengaluru air quality is strongly
    diurnal (traffic peaks, boundary-layer collapse overnight). A random split
    would leak neighbours across the boundary and inflate everything, so
    `time_split` cuts chronologically.

Data sources (both keyless)
  * Air quality: Open-Meteo CAMS archive -- `air-quality-api.open-meteo.com`
    accepts `start_date`/`end_date` for historical hours.
  * Weather: Open-Meteo ERA5 archive -- `archive-api.open-meteo.com/v1/archive`.

Usage
  uv run python scripts/build_dataset.py                 # default window
  uv run python scripts/build_dataset.py --start 2026-06-01 --end 2026-10-05
  uv run python scripts/build_dataset.py --force         # refetch, ignore cache

Output
  data/eval/gono_rows.jsonl      one JSON object per labelled hour
  data/eval/gono_dataset.json    provenance + label distribution
  data/cache/archival_*.json     raw upstream responses (gitignored)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime

from baahar.config import DATA_DIR, get_settings
from baahar.features import NAQI_SKIP, NAQI_WAIT, PRECIP_SKIP_MM
from baahar.http_client import UpstreamError, get_json
from baahar.naqi import (
    assert_chronological,
    band_for_index,
    compute_naqi,
    compute_naqi_trailing,
    conservative_naqi,
)

AQ_ARCHIVE_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
#: ERA5 reanalysis archive. Note the path: the weather archive is
#: `archive-api.open-meteo.com/v1/archive`. The sibling
#: `historical-forecast-api.open-meteo.com/v1/forecast` serves *past model
#: forecasts* instead, and `archive-api.../v1/forecast` returns 404.
WX_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

AQ_VARS = ["pm2_5", "pm10", "nitrogen_dioxide", "ozone", "sulphur_dioxide", "carbon_monoxide"]
WX_VARS = [
    "temperature_2m",
    "apparent_temperature",
    "precipitation",
    "precipitation_probability",
    "relative_humidity_2m",
    "wind_speed_10m",
    "uv_index",
    "weather_code",
]

AQ_VAR_TO_KEY = {
    "pm2_5": "pm25",
    "pm10": "pm10",
    "nitrogen_dioxide": "no2",
    "ozone": "o3",
    "sulphur_dioxide": "so2",
    "carbon_monoxide": "co",
}

CACHE_DIR = DATA_DIR / "cache"
OUT_DIR = DATA_DIR / "eval"

#: How far ahead the model must predict. Six hours is long enough that
#: persistence is not trivially correct and short enough to be actionable.
HORIZON_H = 6

#: What the `naqi` column of this dataset means, in the dataset's own words.
#:
#: Read by `scripts/run_eval.py` so the raw eval artifact states it too. An
#: artifact that does not say what its feature column means is how
#: `baahar.features` and this builder came to disagree about what "naqi" was
#: while both were correct about their own code -- see eval/RESULTS.md C.14.
NAQI_FEATURE_NOTE = (
    "naqi is the EFFECTIVE (conservative) NAQI at hour t: the higher of that "
    "hour's own instantaneous reading and the trailing-mean reading over each "
    "pollutant's CPCB averaging period, i.e. baahar.naqi.conservative_naqi. It "
    "is the same number baahar.features.features_from_slot emits under the key "
    "'naqi', which is what score.py serves to the policy and to TabPFN. The "
    "instantaneous reading is kept beside it as naqi_instant (with "
    "naqi_trailing and naqi_trailing_hours) so the gap is auditable instead of "
    "invisible. band is the band of that effective value."
)

LABEL_NOTE = (
    "target_band and target_naqi are unchanged: the band and index at "
    f"t+{HORIZON_H}h computed from that future hour's own instantaneous reading. "
    "The feature is the effective value; the label is not. That asymmetry is "
    "recorded here rather than left for a reader to discover."
)


@dataclass(frozen=True)
class Row:
    """One labelled training/eval example."""

    time: str
    #: features from hour t
    naqi: float
    """Effective (conservative) NAQI at hour t -- `max(instant, trailing)`.

    This is the column the model is fitted on, and it is the value
    `features_from_slot` serves. See :data:`NAQI_FEATURE_NOTE`.
    """
    naqi_instant: float
    """The hour's own instantaneous reading, kept for audit."""
    naqi_trailing: float
    """The trailing-mean reading behind `naqi`; NaN where there was no history."""
    naqi_trailing_hours: int
    """Hours that actually backed `naqi_trailing`; 0 when there was none."""
    band: str
    pm25: float
    pm10: float
    temp_c: float
    apparent_c: float
    precip_mm: float
    precip_prob: float
    humidity: float
    wind_kmh: float
    uv_index: float
    is_day: int
    hour: int
    month: int
    #: target: band at t + HORIZON_H, from that hour's own instantaneous reading
    target_band: str
    target_naqi: float
    #: policy decision derived from the *target* band (the ground-truth decision)
    decision: str


@dataclass(frozen=True)
class _Hourly:
    """Both readings of one archive hour, plus the bands they imply."""

    #: Band of the effective value -- the band the product would report.
    band: str | None
    #: Band of the instantaneous value. This is what the *label* is built from,
    #: and what decides whether the hour can be a row at all.
    instant_band: str | None
    effective: float
    instant: float
    trailing: float
    trailing_hours: int


def _num(series, i):
    if not isinstance(series, list) or i >= len(series):
        return None
    v = series[i]
    return None if v is None else float(v)


def fetch_series(url: str, params: dict, cache_name: str, *, force: bool) -> dict:
    """Fetch with an on-disk cache so re-runs are cheap and reproducible."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / cache_name
    if path.exists() and not force:
        return json.loads(path.read_text(encoding="utf-8"))
    payload = get_json(url, params, timeout=90, retries=2)
    payload.pop("error", None)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def apply_band_policy(
    band: str | None, precip_mm: float, precip_prob: float, apparent_c: float
) -> str:
    """Map a predicted NAQI band plus weather to GO / WAIT / SKIP.

    This is the same policy the product uses, expressed on the *predicted* band
    so it can be applied to a model output. Anchored to CPCB's own categories:
    Moderate tops out at 200, Poor starts at 201, Severe starts at 301.

    Missing weather is coerced to a safe default rather than raising: an
    unreadable field must never become a silent GO. ``None`` precipitation and
    temperature are treated as "unknown", which routes to WAIT unless the air
    itself is already bad enough to SKIP.
    """
    from baahar.naqi import band_index_range

    if band is None:
        return "SKIP"

    precip_mm = 0.0 if precip_mm is None else float(precip_mm)
    precip_prob = 0.0 if precip_prob is None else float(precip_prob)
    apparent_c = 30.0 if apparent_c is None else float(apparent_c)

    low, _ = band_index_range(band)
    if low >= NAQI_SKIP:
        return "SKIP"
    if precip_mm >= PRECIP_SKIP_MM or precip_prob >= 70:
        return "SKIP"
    if apparent_c >= 35:
        return "SKIP"
    if apparent_c is None or precip_prob is None:
        return "WAIT"
    if low >= NAQI_WAIT:
        return "WAIT"
    if apparent_c >= 30 or precip_prob >= 40:
        return "WAIT"
    return "GO"


def build_rows(start: str, end: str, *, force: bool) -> list[Row]:
    settings = get_settings()
    common = {
        "latitude": settings.lat,
        "longitude": settings.lon,
        "start_date": start,
        "end_date": end,
        "hourly": ",".join(AQ_VARS),
        "timezone": settings.timezone,
    }
    aq = fetch_series(AQ_ARCHIVE_URL, common, f"archival_aq_{start}_{end}.json", force=force)
    aq_h = aq.get("hourly") or {}
    aq_times = aq_h.get("time") or []
    if not aq_times:
        raise SystemExit("air-quality archive returned no rows")
    assert_chronological(aq_times, where=f"air-quality archive {start}..{end}")

    wx_params = dict(common)
    wx_params["hourly"] = ",".join(WX_VARS)
    wx = fetch_series(WX_ARCHIVE_URL, wx_params, f"archival_wx_{start}_{end}.json", force=force)
    wx_h = wx.get("hourly") or {}
    wx_by_time = {t: i for i, t in enumerate(wx_h.get("time") or [])}

    def readings_at(i: int) -> dict:
        return {AQ_VAR_TO_KEY[v]: _num(aq_h.get(v), i) for v in AQ_VARS}

    # One history list, built exactly the way `air.parse_air` builds it, and one
    # trailing mean per hour computed by `compute_naqi_trailing` over that list.
    #
    # This used to be `compute_naqi(readings_at(i))` -- the instantaneous
    # reading only. So the eval fitted a model on the `naqi` column while the app
    # served the conservative value under that same column name: a train/serve
    # skew one layer above the one `score_tabpfn` now guards against. The
    # archive has every hour, so the trailing mean is computable here exactly as
    # it is live.
    history: list[dict] = []
    for i, ts in enumerate(aq_times):
        readings = {k: v for k, v in readings_at(i).items() if v is not None}
        # Stamped so `compute_naqi_trailing` refuses a mis-ordered series rather
        # than averaging across hours that are not in sequence.
        readings["time"] = ts
        history.append(readings)

    band_at: list[_Hourly] = []
    for i in range(len(aq_times)):
        rd = history[i]
        instant = compute_naqi(rd)
        trailing = compute_naqi_trailing(history[: i + 1])
        effective = conservative_naqi(instant, trailing)
        band_at.append(
            _Hourly(
                band=effective.band.value if effective.band and effective.is_usable else None,
                instant_band=(instant.band.value if instant.band and instant.is_usable else None),
                effective=float(effective.index) if effective.is_usable else float("nan"),
                instant=float(instant.index) if instant.is_usable else float("nan"),
                trailing=float("nan") if trailing is None else float(trailing.index),
                trailing_hours=trailing.hours if trailing is not None else 0,
            )
        )

    rows: list[Row] = []
    for i, ts in enumerate(aq_times):
        j = i + HORIZON_H
        if j >= len(aq_times):
            break
        wi = wx_by_time.get(ts)
        if wi is None:
            continue

        now = band_at[i]
        target = band_at[j]
        # The label is the *instantaneous* band at t+6h, unchanged. A row still
        # needs a usable instantaneous reading at t as well, so the dataset has
        # exactly the same hours in it as it did before the feature changed.
        if now.instant_band is None or target.instant_band is None:
            continue
        # The feature must be a real number, whatever the label is made of.
        if now.band is None:
            continue

        pm25 = _num(aq_h.get("pm2_5"), i)
        pm10 = _num(aq_h.get("pm10"), i)
        temp_c = _num(wx_h.get("temperature_2m"), wi)
        apparent_c = _num(wx_h.get("apparent_temperature"), wi)
        precip_mm = _num(wx_h.get("precipitation"), wi)
        precip_prob = _num(wx_h.get("precipitation_probability"), wi)
        humidity = _num(wx_h.get("relative_humidity_2m"), wi)
        wind = _num(wx_h.get("wind_speed_10m"), wi)
        uv = _num(wx_h.get("uv_index"), wi)
        if None in (temp_c, apparent_c, precip_mm, humidity, wind):
            continue

        # Target weather for the policy uses the *forecast* hour's own weather,
        # which is what a real plan would have. Using hour t's weather would
        # mislabel rain six hours out.
        wj = wx_by_time.get(aq_times[j])
        if wj is not None:
            t_precip = _num(wx_h.get("precipitation"), wj) or 0.0
            t_prob = _num(wx_h.get("precipitation_probability"), wj) or 0.0
            t_apparent = _num(wx_h.get("apparent_temperature"), wj) or apparent_c
        else:
            t_precip, t_prob, t_apparent = precip_mm, precip_prob, apparent_c

        dt = datetime.fromisoformat(ts)
        rows.append(
            Row(
                time=ts,
                naqi=round(now.effective, 2),
                naqi_instant=round(now.instant, 2),
                naqi_trailing=round(now.trailing, 2),
                naqi_trailing_hours=now.trailing_hours,
                band=now.band,
                pm25=pm25 if pm25 is not None else float("nan"),
                pm10=pm10 if pm10 is not None else float("nan"),
                temp_c=temp_c,
                apparent_c=apparent_c,
                precip_mm=precip_mm,
                precip_prob=precip_prob,
                humidity=humidity,
                wind_kmh=wind,
                uv_index=uv if uv is not None else float("nan"),
                is_day=1 if dt.hour >= 6 and dt.hour < 19 else 0,
                hour=dt.hour,
                month=dt.month,
                target_band=target.instant_band,
                target_naqi=round(target.instant, 2),
                decision=apply_band_policy(target.instant_band, t_precip, t_prob, t_apparent),
            )
        )
    return rows


def assert_feature_is_effective(rows: list[Row]) -> None:
    """The fitted feature must be the effective reading, and must say so.

    Two invariants, both of which the dataset used to break:

    * ``naqi`` is never below ``naqi_instant`` -- a model fitted on a lower
      number than the one served would be trained on optimistic air.
    * ``band`` is the band of ``naqi``, so the row cannot describe an hour two
      different ways.
    """
    for row in rows:
        assert row.naqi >= row.naqi_instant, f"{row.time}: effective < instantaneous"
        assert row.band == band_for_index(row.naqi).value, (
            f"{row.time}: band {row.band!r} is not the band of naqi {row.naqi}"
        )


def assert_no_leakage(rows: list[Row]) -> None:
    """Belt-and-braces check that no row's features contain its own answer.

    Features are sourced from hour ``t`` only; the target from ``t + HORIZON``.
    If someone later adds a "target" column to the feature builder, the dataset
    would silently produce a meaningless accuracy of 1.0. This asserts the
    structural invariant instead of trusting the reader to notice.
    """
    from dataclasses import fields

    feature_names = {f.name for f in fields(Row)} - {"target_band", "target_naqi", "decision"}
    # Every non-target column must describe hour t. `time` is the anchor; the
    # rest are all measured at t by construction.
    assert "time" in feature_names
    assert not feature_names & {"target_band", "target_naqi", "decision"}
    if len(rows) < HORIZON_H + 1:
        return
    # Monotonic timestamps, so "later" really is later and the split is honest.
    times = [datetime.fromisoformat(r.time) for r in rows]
    assert all(b > a for a, b in zip(times, times[1:], strict=False)), "rows are not chronological"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2026-06-01", help="inclusive start date")
    parser.add_argument("--end", default="2026-10-05", help="inclusive end date")
    parser.add_argument("--force", action="store_true", help="refetch, ignore cache")
    args = parser.parse_args(argv)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"building go/no-go rows for {args.start} .. {args.end}")
    try:
        rows = build_rows(args.start, args.end, force=args.force)
    except UpstreamError as exc:
        print(f"upstream fetch failed: {exc}", file=sys.stderr)
        return 1

    assert_no_leakage(rows)
    assert_feature_is_effective(rows)

    rows_path = OUT_DIR / "gono_rows.jsonl"
    with rows_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(asdict(row)) + "\n")

    bands = Counter(r.target_band for r in rows)
    decisions = Counter(r.decision for r in rows)
    raised = sum(1 for r in rows if r.naqi > r.naqi_instant)
    meta = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "start": args.start,
        "end": args.end,
        "horizon_hours": HORIZON_H,
        "city": get_settings().city,
        "lat": get_settings().lat,
        "lon": get_settings().lon,
        "n_rows": len(rows),
        "target_band_distribution": dict(bands),
        "decision_distribution": dict(decisions),
        "sources": {
            "air_quality": AQ_ARCHIVE_URL,
            "weather": WX_ARCHIVE_URL,
            "naqi_method": "CPCB 2014 sub-index breakpoints; overall = worst sub-index",
        },
        "feature_semantics": {
            "naqi": NAQI_FEATURE_NOTE,
            "target": LABEL_NOTE,
            "rows_where_effective_exceeds_instantaneous": raised,
            "trailing_note": (
                "naqi_trailing is NaN for the first hours of the window, where there "
                "is not enough history for a mean, and naqi_trailing_hours records "
                "how many hours actually backed each value."
            ),
        },
        "label_policy": "GO/WAIT/SKIP derived from the target band via apply_band_policy",
        "leakage_note": (
            f"Features are hour t only; target band is measured at t+{HORIZON_H}h. "
            "No feature column contains the target."
        ),
    }
    (OUT_DIR / "gono_dataset.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"wrote {len(rows)} rows -> {rows_path}")
    print(f"naqi feature is the effective reading ({raised} rows above instantaneous)")
    print("target band distribution:")
    for band, count in sorted(bands.items()):
        print(f"  {band:<14} {count:5}  ({100 * count / max(1, len(rows)):.1f}%)")
    print("ground-truth decision distribution:")
    for decision, count in sorted(decisions.items()):
        print(f"  {decision:<14} {count:5}  ({100 * count / max(1, len(rows)):.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
