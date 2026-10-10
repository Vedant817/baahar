"""Tabular features for the go/no-go model.

Design notes (the eval discipline starts here, not in the write-up):

* **No target leakage.** Features are built from hour *t* and past hours t-1..t-6 only.
  The label for hour *t* is assigned at *t* too. Nothing downstream of the split may read
  hour *t+1*.
* **Time-based split, never shuffled.** Air quality is strongly autocorrelated;
  a random shuffle puts neighbouring hours on both sides of the split and
  inflates every metric. :func:`time_split` cuts chronologically.
* **Physical units, documented.** Baahar stores SI (µg/m³, °C, mm). Only the
  cyclic *hour of day* gets sin/cos encoding, because a raw 0-23 integer
  implies a false distance between 23:00 and 00:00.

The scorer consumes these rows; see :mod:`baahar.score`.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .models import Decision, HourSlot
from .weather import weather_category

#: Base 13 columns.
BASE_FEATURE_NAMES: tuple[str, ...] = (
    "naqi",
    "pm25",
    "pm10",
    "temp_c",
    "apparent_c",
    "precip_mm",
    "precip_prob",
    "humidity",
    "wind_kmh",
    "uv_index",
    "is_day",
    "hour",
    "month",
)

#: 15 lag and difference features derived strictly from hours t-1 .. t-6.
LAG_FEATURE_NAMES: tuple[str, ...] = (
    "naqi_lag1",
    "naqi_lag3",
    "naqi_lag6",
    "naqi_diff1",
    "naqi_diff3",
    "naqi_diff6",
    "naqi_rate6",
    "pm25_lag1",
    "pm25_diff3",
    "pm10_diff3",
    "temp_diff3",
    "wind_lag1",
    "wind_diff1",
    "naqi_rolling3",
    "naqi_rolling6",
)

#: Column order for model feature vectors (13 base + 15 lag/difference features).
FEATURE_NAMES: tuple[str, ...] = BASE_FEATURE_NAMES + LAG_FEATURE_NAMES

#: Column order for the TabPFN X matrix. Same as :data:`FEATURE_NAMES`; named
#: separately because "the model's column contract" is a different idea from
#: "every feature this module can compute".
TABPFN_FEATURE_ORDER: tuple[str, ...] = FEATURE_NAMES

#: Compact 17-feature architecture for 6h-ahead NAQI forecasting.
#: Prunes collinear thermodynamic variables, dead NaN columns, and degenerate diurnal duplicates.
COMPACT_FEATURE_NAMES: tuple[str, ...] = (
    "naqi",
    "pm25",
    "pm10",
    "temp_c",
    "precip_mm",
    "humidity",
    "wind_kmh",
    "is_day",
    "month",
    "vpd",
    "stagnation",
    "pm_ratio",
    "naqi_gap",
    "hour_sin",
    "hour_cos",
    "month_sin",
    "month_cos",
)

#: Default imputation medians computed strictly from the training partition
#: (first 80% chronologically). Shared by fit and serve to eliminate skew on
#: edge cases (e.g. the first 6 hours of any forecast window).
DEFAULT_IMPUTATION_MEDIANS: dict[str, float] = {
    "naqi": 95.1,
    "pm25": 23.9,
    "pm10": 28.1,
    "temp_c": 23.7,
    "apparent_c": 24.6,
    "precip_mm": 0.0,
    "precip_prob": 0.0,
    "humidity": 63.0,
    "wind_kmh": 10.4,
    "uv_index": 0.0,
    "is_day": 1.0,
    "hour": 11.5,
    "month": 5.0,
    "naqi_lag1": 95.1,
    "naqi_lag3": 95.1,
    "naqi_lag6": 95.1,
    "naqi_diff1": -1.47,
    "naqi_diff3": -5.15,
    "naqi_diff6": -7.23,
    "naqi_rate6": -1.205,
    "pm25_lag1": 23.9,
    "pm25_diff3": -0.1,
    "pm10_diff3": 0.0,
    "temp_diff3": -0.7,
    "wind_lag1": 10.4,
    "wind_diff1": 0.0,
    "naqi_rolling3": 96.4067,
    "naqi_rolling6": 98.7467,
}

#: Ordinal encoding of NAQI bands, worst last.
BAND_ORDINALS: dict[str, int] = {
    "good": 0,
    "satisfactory": 1,
    "moderate": 2,
    "poor": 3,
    "severe": 4,
    "hazardous": 5,
}

#: Apparent temperature above which a gentle walk is treated as heat stress.
#: Chosen for "a healthy adult, 20 minutes, unacclimatised", not for athletes.
HEAT_STRESS_APPARENT_C = 35.0

#: A probability above this with non-trivial precipitation is not a GO.
RAIN_PROB_SKIP = 70.0


def heat_index_flag(apparent_c: float | None) -> float:
    return 1.0 if apparent_c is not None and apparent_c >= HEAT_STRESS_APPARENT_C else 0.0


def _f(value: float | None) -> float:
    """Coerce to float, with a sentinel for unknown rather than a fake zero.

    Using 0.0 for a missing temperature would read as "freezing". A sentinel
    keeps "we do not know" distinguishable from "we measured a real number".
    """
    return float("nan") if value is None else float(value)


def compact_features_from_row(row: dict[str, Any]) -> dict[str, float]:
    """Derive compact columns from hour-t values, shared by eval and serving."""
    temp = _f(row.get("temp_c"))
    humidity = _f(row.get("humidity"))
    wind = _f(row.get("wind_kmh"))
    pm25 = _f(row.get("pm25"))
    pm10 = _f(row.get("pm10"))
    naqi_effective = _f(row.get("naqi"))
    naqi_instant = _f(row.get("naqi_instant"))
    hour = _f(row.get("hour"))
    month = _f(row.get("month"))
    # 1. Magnus-Tetens Vapor Pressure Deficit (kPa)
    if not math.isnan(temp) and not math.isnan(humidity):
        rh_clamped = max(min(humidity, 100.0), 0.01)
        es = 0.61078 * math.exp((17.27 * temp) / (temp + 237.3))
        ea = es * (rh_clamped / 100.0)
        vpd = es - ea
    else:
        vpd = float("nan")

    # 2. Atmospheric Stagnation Index: (RH / 100) / max(wind, 1.0)
    stagnation = (
        (humidity / 100.0) / max(wind, 1.0)
        if not (math.isnan(humidity) or math.isnan(wind))
        else float("nan")
    )

    # 3. Combustion PM ratio: clip(pm25 / max(pm10, 1.0), 0.0, 1.0)
    if not math.isnan(pm25) and not math.isnan(pm10):
        pm_ratio = min(max(pm25 / max(pm10, 1.0), 0.0), 1.0)
    else:
        pm_ratio = float("nan")

    # 4. NAQI velocity gap: effective minus instantaneous reading
    naqi_gap = (
        naqi_effective - naqi_instant
        if not (math.isnan(naqi_effective) or math.isnan(naqi_instant))
        else 0.0
    )

    # 5. Month cyclical encoding
    month_sin = math.sin(2.0 * math.pi * month / 12.0)
    month_cos = math.cos(2.0 * math.pi * month / 12.0)

    # 6. Hour cyclical encoding
    hour_sin = math.sin(2.0 * math.pi * hour / 24.0)
    hour_cos = math.cos(2.0 * math.pi * hour / 24.0)
    return {
        "vpd": vpd,
        "stagnation": stagnation,
        "pm_ratio": pm_ratio,
        "naqi_gap": naqi_gap,
        "hour_sin": hour_sin,
        "hour_cos": hour_cos,
        "month_sin": month_sin,
        "month_cos": month_cos,
    }


def features_from_rows(
    rows: Sequence[dict[str, Any]],
    *,
    impute_missing: bool = False,
) -> list[dict[str, float]]:
    """Derive base, compact, and lag features across an ordered sequence of row dicts.

    Lag and difference features read strictly from hours t-1 .. t-6 (past hours,
    before the hour being predicted - strictly no leakage into future hours).
    """
    n = len(rows)
    if n == 0:
        return []

    naqis = [
        _f(r.get("naqi")) if r.get("naqi") is not None else _f(r.get("naqi_effective"))
        for r in rows
    ]
    pm25s = [_f(r.get("pm25")) for r in rows]
    pm10s = [_f(r.get("pm10")) for r in rows]
    temps = [_f(r.get("temp_c")) for r in rows]
    winds = [_f(r.get("wind_kmh")) for r in rows]

    out: list[dict[str, float]] = []
    for i, r in enumerate(rows):
        temp = temps[i]
        humidity = _f(r.get("humidity"))
        wind = winds[i]
        pm25 = pm25s[i]
        pm10 = pm10s[i]
        naqi_val = naqis[i]
        naqi_instant = _f(r.get("naqi_instant", naqi_val))
        hour = _f(r.get("hour"))
        month = _f(r.get("month"))
        band = r.get("naqi_effective_band") or ""

        compact = compact_features_from_row(
            {
                "temp_c": temp,
                "humidity": humidity,
                "wind_kmh": wind,
                "pm25": pm25,
                "pm10": pm10,
                "naqi": naqi_val,
                "naqi_instant": naqi_instant,
                "hour": hour,
                "month": month,
            }
        )

        n_now = naqi_val
        l1 = naqis[i - 1] if i >= 1 else float("nan")
        l3 = naqis[i - 3] if i >= 3 else float("nan")
        l6 = naqis[i - 6] if i >= 6 else float("nan")

        d1 = n_now - l1 if not math.isnan(l1) and not math.isnan(n_now) else float("nan")
        d3 = n_now - l3 if not math.isnan(l3) and not math.isnan(n_now) else float("nan")
        d6 = n_now - l6 if not math.isnan(l6) and not math.isnan(n_now) else float("nan")
        r6 = (n_now - l6) / 6.0 if not math.isnan(l6) and not math.isnan(n_now) else float("nan")

        p25_l1 = pm25s[i - 1] if i >= 1 else float("nan")
        p25_d3 = (
            pm25 - pm25s[i - 3]
            if i >= 3 and not math.isnan(pm25) and not math.isnan(pm25s[i - 3])
            else float("nan")
        )
        p10_d3 = (
            pm10 - pm10s[i - 3]
            if i >= 3 and not math.isnan(pm10) and not math.isnan(pm10s[i - 3])
            else float("nan")
        )
        t_d3 = (
            temp - temps[i - 3]
            if i >= 3 and not math.isnan(temp) and not math.isnan(temps[i - 3])
            else float("nan")
        )
        w_l1 = winds[i - 1] if i >= 1 else float("nan")
        w_d1 = (
            wind - winds[i - 1]
            if i >= 1 and not math.isnan(wind) and not math.isnan(winds[i - 1])
            else float("nan")
        )

        sub3 = [naqis[j] for j in range(max(0, i - 2), i + 1) if not math.isnan(naqis[j])]
        roll3 = sum(sub3) / len(sub3) if sub3 else float("nan")

        sub6 = [naqis[j] for j in range(max(0, i - 5), i + 1) if not math.isnan(naqis[j])]
        roll6 = sum(sub6) / len(sub6) if sub6 else float("nan")

        lags: dict[str, float] = {
            "naqi_lag1": l1,
            "naqi_lag3": l3,
            "naqi_lag6": l6,
            "naqi_diff1": d1,
            "naqi_diff3": d3,
            "naqi_diff6": d6,
            "naqi_rate6": r6,
            "pm25_lag1": p25_l1,
            "pm25_diff3": p25_d3,
            "pm10_diff3": p10_d3,
            "temp_diff3": t_d3,
            "wind_lag1": w_l1,
            "wind_diff1": w_d1,
            "naqi_rolling3": roll3,
            "naqi_rolling6": roll6,
        }

        if impute_missing:
            for k, v in lags.items():
                if math.isnan(v):
                    lags[k] = DEFAULT_IMPUTATION_MEDIANS.get(k, 0.0)

        row_dict: dict[str, float] = {
            "naqi": naqi_val,
            "pm25": pm25,
            "pm10": pm10,
            "temp_c": temp,
            "apparent_c": _f(r.get("apparent_c")),
            "precip_mm": _f(r.get("precip_mm")),
            "precip_prob": _f(r.get("precip_prob")),
            "humidity": humidity,
            "wind_kmh": wind,
            "uv_index": _f(r.get("uv_index")),
            "is_day": float(r.get("is_day") or 0.0),
            "hour": float(hour),
            "month": month,
            **lags,
            **compact,
            "naqi_band_ordinal": float(BAND_ORDINALS.get(band, -1)),
            "heat_index_flag": heat_index_flag(r.get("apparent_c")),
        }
        out.append(row_dict)

    return out


def _row_dict_from_slot(slot: HourSlot) -> dict[str, Any]:
    air = slot.air
    weather = slot.weather
    return {
        "naqi": _f(air.naqi_effective),
        "naqi_instant": _f(air.naqi),
        "pm25": _f(air.pm25),
        "pm10": _f(air.pm10),
        "temp_c": _f(weather.temp_c),
        "apparent_c": _f(weather.apparent_c),
        "precip_mm": _f(weather.precip_mm),
        "precip_prob": _f(weather.precip_prob),
        "humidity": _f(weather.humidity),
        "wind_kmh": _f(weather.wind_kmh),
        "uv_index": _f(weather.uv_index),
        "is_day": float(weather.is_day or 0),
        "hour": float(weather.time.hour),
        "month": float(weather.time.month),
        "naqi_effective_band": air.naqi_effective_band or "",
    }


def features_from_slots(
    slots: Sequence[HourSlot],
    history: Sequence[HourSlot] | None = None,
    *,
    impute_missing: bool = False,
) -> list[dict[str, float]]:
    """Derive features across an ordered sequence of HourSlot objects."""
    hist = list(history or ())
    combined = hist + list(slots)
    rows = [_row_dict_from_slot(s) for s in combined]
    derived = features_from_rows(rows, impute_missing=impute_missing)
    return derived[len(hist) :]


def features_from_slot(
    slot: HourSlot,
    history: Sequence[HourSlot] | None = None,
) -> dict[str, float]:
    """Build one feature row from a joined hour.

    When no history is provided, missing lag values are explicitly imputed using
    DEFAULT_IMPUTATION_MEDIANS.
    """
    return features_from_slots([slot], history=history, impute_missing=True)[0]


def row_from_slot(
    slot: HourSlot,
    order: Sequence[str] = TABPFN_FEATURE_ORDER,
    history: Sequence[HourSlot] | None = None,
) -> list[float]:
    feats = features_from_slot(slot, history=history)
    return [feats[name] for name in order]


def matrix_from_slots(
    slots: Sequence[HourSlot],
    order: Sequence[str] = TABPFN_FEATURE_ORDER,
    history: Sequence[HourSlot] | None = None,
) -> list[list[float]]:
    """Extract ordered feature matrix from a sequence of HourSlots."""
    feats = features_from_slots(slots, history=history, impute_missing=False)
    return [[f[name] for name in order] for f in feats]


# ---------------------------------------------------------------------------
# The heuristic policy: the documented label rule
# ---------------------------------------------------------------------------
#
# This is the ground truth for the tabular task, so it has to be stated in one
# place, in plain terms, and cited by both the scorer and RESULTS.md.
#
#   SKIP  if  NAQI >= 300 (Severe+)
#         or apparent temp >= 35 C
#         or precipitation >= 2.5 mm/h
#         or precipitation probability >= 70 % with >= 0.5 mm expected
#         or thunderstorm
#
#   WAIT  if  NAQI >= 200 (Poor) and < 300
#         or apparent temp in [30, 35)
#         or precipitation probability >= 40 %
#
#   GO    otherwise, and only in daylight hours
#
# The bands follow CPCB's own category boundaries (Poor = 201-300,
# Severe = 301-400), so the policy is anchored to published health guidance
# rather than to numbers tuned on our own data. Tuning these on the holdout
# would be the single easiest way to fake a good score, so we do not do it.
#
# NONE of these thresholds moved. What changed is the *input*: the policy reads
# `naqi_effective`, the higher of the hour's instantaneous reading and its
# trailing-mean reading, where it used to read the instantaneous value alone.
# The skip path is therefore strictly less permissive than before -- it can only
# fire on hours it would not have fired on before, never the reverse.

NAQI_SKIP = 300.0
NAQI_WAIT = 200.0
PRECIP_SKIP_MM = 2.5
PRECIP_MIN_MM_FOR_PROB = 0.5
PRECIP_WAIT_PROB = 40.0
APPARENT_WAIT_C = 30.0


def heuristic_decision(slot: HourSlot) -> tuple[Decision, list[str]]:
    """Apply the documented policy to one hour. Returns decision + reasons."""
    reasons: list[str] = []
    air, weather = slot.air, slot.weather

    # The conservative reading. `naqi_effective` is never lower than the
    # instantaneous value, so this call is never *more* permissive than the
    # policy was before it started reading the trailing mean too.
    value = air.naqi_effective
    if value is None:
        reasons.append("No air-quality reading for this hour -- not guessing.")

    naqi = value
    if naqi is not None and naqi >= NAQI_SKIP:
        reasons.append(f"NAQI {naqi:.0f} is Severe or worse.")

    apparent = weather.apparent_c
    if apparent is not None and apparent >= HEAT_STRESS_APPARENT_C:
        reasons.append(f"Feels like {apparent:.0f} C.")

    precip = weather.precip_mm
    if precip is not None and precip >= PRECIP_SKIP_MM:
        reasons.append(f"{precip:.1f} mm rain in the hour.")

    prob = weather.precip_prob
    if (
        prob is not None
        and prob >= RAIN_PROB_SKIP
        and precip is not None
        and precip >= PRECIP_MIN_MM_FOR_PROB
    ):
        reasons.append(f"{prob:.0f}% chance of rain.")

    category = weather_category(weather.weather_code)
    if category is not None and category.value == "thunderstorm":
        reasons.append("Thunderstorm forecast.")

    def _with_night(rs: list[str]) -> list[str]:
        text = " ".join(rs).lower()
        if not weather.is_day and not any(
            tok in text for tok in ("night", "gate", "shut", "closed")
        ):
            rs = rs + ["Night-time; park gates may be shut."]
        return rs

    if reasons:
        return Decision.SKIP, _with_night(reasons)

    if naqi >= NAQI_WAIT:
        reasons.append(f"NAQI {naqi:.0f} is Poor -- fine if you must, not ideal.")
    if apparent is not None and apparent >= APPARENT_WAIT_C:
        reasons.append(f"Feels like {apparent:.0f} C.")
    if prob is not None and prob >= PRECIP_WAIT_PROB:
        reasons.append(f"{prob:.0f}% chance of rain.")

    if reasons:
        return Decision.WAIT, _with_night(reasons)

    if air.naqi_uses_trailing_mean:
        # Say so rather than letting a number that disagrees with the
        # concentration on screen look like an error.
        reasons.append(
            f"NAQI {naqi:.0f}, from the last {air.naqi_trailing_hours} h of air, "
            "not just this hour."
        )

    if not weather.is_day:
        band = air.naqi_effective_band or air.naqi_band
        band_name = getattr(band, "value", band) or "unrated"
        return Decision.WAIT, [f"Night-time. Air is {band_name}, but park gates may be shut."]

    if not reasons:
        reasons.append(
            f"NAQI {naqi:.0f}"
            + (f", feels like {apparent:.0f} C" if apparent is not None else "")
            + "."
        )
    return Decision.GO, reasons


@dataclass(frozen=True)
class LabelledRow:
    """A feature row plus its ground-truth label."""

    features: dict[str, float]
    label: str
    time: str
    meta: dict[str, Any]


def build_dataset(slots: Sequence[HourSlot]) -> list[LabelledRow]:
    """Feature rows + policy labels for a chronological run of hours."""
    rows: list[LabelledRow] = []
    feats_list = features_from_slots(slots)
    for slot, feats in zip(slots, feats_list, strict=True):
        decision, reasons = heuristic_decision(slot)
        rows.append(
            LabelledRow(
                features=feats,
                label=decision.value,
                time=slot.weather.time.isoformat(),
                meta={
                    "naqi": slot.air.naqi_effective,
                    "naqi_band": slot.air.naqi_effective_band,
                    "naqi_instant": slot.air.naqi,
                    "naqi_trailing": slot.air.naqi_trailing,
                    "naqi_trailing_hours": slot.air.naqi_trailing_hours,
                    "apparent_c": slot.weather.apparent_c,
                    "precip_mm": slot.weather.precip_mm,
                    "reasons": reasons,
                },
            )
        )
    return rows


def time_split(
    rows: Sequence[LabelledRow], holdout_fraction: float = 0.2
) -> tuple[list[LabelledRow], list[LabelledRow]]:
    """Chronological split. Never shuffle air-quality time series.

    Returns ``(train, test)`` where ``test`` is the final
    ``holdout_fraction`` of the timeline.
    """
    if not rows:
        return [], []
    ordered = sorted(rows, key=lambda r: r.time)
    cut = max(1, int(len(ordered) * (1 - holdout_fraction)))
    return ordered[:cut], ordered[cut:]


def comfort_from_features(features: dict[str, float]) -> float:
    """Map features to a 0-100 walk comfort score.

    Deliberately simple and monotone: worse air, worse heat, more rain = lower.
    Only meaningful *within* a run, which is how the UI uses it.
    """
    naqi = features.get("naqi")
    if naqi is None or math.isnan(naqi):
        return 0.0
    air_component = max(0.0, min(100.0, 100.0 - (naqi / NAQI_SKIP) * 100.0))

    apparent = features.get("apparent_c")
    if apparent is None or math.isnan(apparent):
        heat_component = 80.0
    else:
        # 24 C feels perfect, 40 C feels awful.
        heat_component = max(0.0, min(100.0, 100.0 - max(0.0, apparent - 24.0) * 6.0))

    precip = features.get("precip_mm")
    precip_component = (
        100.0 if precip is None or math.isnan(precip) else max(0.0, 100.0 - precip * 25.0)
    )

    return round(0.55 * air_component + 0.3 * heat_component + 0.15 * precip_component, 1)


def decision_rank(decision: Decision) -> int:
    return {Decision.GO: 0, Decision.WAIT: 1, Decision.SKIP: 2}[decision]
