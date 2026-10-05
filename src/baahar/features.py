"""Tabular features for the go/no-go model.

Design notes (the eval discipline starts here, not in the write-up):

* **No target leakage.** Features are built from hour *t* only. The label for
  hour *t* is assigned at *t* too. Nothing downstream of the split may read
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

from .models import Decision, HourSlot, SlotScore
from .naqi import band_for_index
from .weather import weather_category

#: Ordered feature names. Frozen because a trained TabPFN model's column
#: ordering is part of its contract -- appending is safe, reordering is not.
FEATURE_NAMES: tuple[str, ...] = (
    "naqi",
    "pm25",
    "pm10",
    "naqi_band_ordinal",
    "temp_c",
    "apparent_c",
    "heat_index_flag",
    "precip_mm",
    "precip_prob",
    "humidity",
    "wind_kmh",
    "uv_index",
    "is_day",
    "hour_sin",
    "hour_cos",
)

#: Column order for the TabPFN X matrix.
TABPFN_FEATURE_ORDER: tuple[str, ...] = FEATURE_NAMES

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


def features_from_slot(slot: HourSlot) -> dict[str, float]:
    """Build one feature row from a joined hour."""
    air = slot.air
    weather = slot.weather
    hour = weather.time.hour
    # radians for sin/cos encoding
    angle = 2 * math.pi * hour / 24.0
    band = air.naqi_band or ""
    return {
        "naqi": _f(air.naqi),
        "pm25": _f(air.pm25),
        "pm10": _f(air.pm10),
        "naqi_band_ordinal": float(BAND_ORDINALS.get(band, -1)),
        "temp_c": _f(weather.temp_c),
        "apparent_c": _f(weather.apparent_c),
        "heat_index_flag": heat_index_flag(weather.apparent_c),
        "precip_mm": _f(weather.precip_mm),
        "precip_prob": _f(weather.precip_prob),
        "humidity": _f(weather.humidity),
        "wind_kmh": _f(weather.wind_kmh),
        "uv_index": _f(weather.uv_index),
        "is_day": float(weather.is_day or 0),
        "hour_sin": math.sin(angle),
        "hour_cos": math.cos(angle),
    }


def row_from_slot(slot: HourSlot, order: Sequence[str] = TABPFN_FEATURE_ORDER) -> list[float]:
    feats = features_from_slot(slot)
    return [feats[name] for name in order]


def matrix_from_slots(
    slots: Sequence[HourSlot], order: Sequence[str] = TABPFN_FEATURE_ORDER
) -> list[list[float]]:
    return [row_from_slot(slot, order) for slot in slots]


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

    if air.naqi is None:
        return Decision.SKIP, ["No air-quality reading for this hour -- not guessing."]

    naqi = air.naqi
    if naqi >= NAQI_SKIP:
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

    if reasons:
        return Decision.SKIP, reasons

    if naqi >= NAQI_WAIT:
        reasons.append(f"NAQI {naqi:.0f} is Poor -- fine if you must, not ideal.")
    if apparent is not None and apparent >= APPARENT_WAIT_C:
        reasons.append(f"Feels like {apparent:.0f} C.")
    if prob is not None and prob >= PRECIP_WAIT_PROB:
        reasons.append(f"{prob:.0f}% chance of rain.")

    if reasons:
        return Decision.WAIT, reasons

    if not weather.is_day:
        return Decision.WAIT, ["Night-time. Good air, but park gates may be shut."]

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
    for slot in slots:
        decision, reasons = heuristic_decision(slot)
        rows.append(
            LabelledRow(
                features=features_from_slot(slot),
                label=decision.value,
                time=slot.weather.time.isoformat(),
                meta={
                    "naqi": slot.air.naqi,
                    "naqi_band": slot.air.naqi_band,
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
    precip_component = 100.0 if precip is None or math.isnan(precip) else max(
        0.0, 100.0 - precip * 25.0
    )

    return round(0.55 * air_component + 0.3 * heat_component + 0.15 * precip_component, 1)


def decision_rank(decision: Decision) -> int:
    return {Decision.GO: 0, Decision.WAIT: 1, Decision.SKIP: 2}[decision]


def scores_to_slots(scores: Sequence[SlotScore]) -> list[SlotScore]:
    """No-op passthrough kept for a readable call site in score.build_plan."""
    return list(scores)


def band_from_naqi(naqi: float | None) -> str | None:
    band = band_for_index(naqi)
    return band.value if band else None