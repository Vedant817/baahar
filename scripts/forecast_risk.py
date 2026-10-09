"""Research-only forecast selection and metrics; no serving or network side effects."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from baahar.naqi import band_for_index

FORECAST_TARGET_CONTRACT = {
    "target_basis": "instantaneous_naqi",
    "horizon_hours": 6,
    "target_column": "target_band",
    "current_effective_naqi": "conservative feature and policy diagnostic; not matching persistence",
}
BAND_NAMES = ("good", "satisfactory", "moderate", "poor", "severe", "hazardous")
INSTANT_HISTORY_COLUMNS = (
    "instant_naqi", "instant_naqi_lag1", "instant_naqi_lag3", "instant_naqi_lag6",
    "instant_naqi_diff1", "instant_naqi_diff3", "instant_naqi_diff6",
)


def instantaneous_history_features(rows):
    """Timestamp-based causal history; missing hours stay missing, never shift."""
    stamps = [datetime.fromisoformat(row["time"]) for row in rows]
    if len(set(stamps)) != len(stamps):
        raise ValueError("Duplicate feature timestamps")

    def number(row):
        value = row.get("naqi_instant")
        return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else math.nan

    lookup = {stamp: number(row) for stamp, row in zip(stamps, rows, strict=True)}
    values = []
    for stamp in stamps:
        now = lookup[stamp]
        lag = [lookup.get(stamp - timedelta(hours=h), math.nan) for h in (1, 3, 6)]
        values.append([now, *lag, *(now - v for v in lag)])
    return values


def numeric_forecast_metrics(actual, predicted, alpha):
    """Quantile loss/coverage are not probability-calibration measurements."""
    errors = [y - p for y, p in zip(actual, predicted, strict=True)]
    return {
        "mae": sum(abs(e) for e in errors) / len(errors),
        "rmse": math.sqrt(sum(e * e for e in errors) / len(errors)),
        "pinball_loss": sum(max(alpha * e, (alpha - 1) * e) for e in errors) / len(errors),
        "empirical_quantile_coverage": sum(e <= 0 for e in errors) / len(errors),
        "alpha": alpha,
    }


def event_detection_metrics(times, labels, predictions, minimum_band):
    """Descriptive any-hit/full-hit rates among target episodes, not field evidence."""
    positives = sorted(
        (t, p >= minimum_band) for t, y, p in zip(times, labels, predictions, strict=True)
        if y >= minimum_band
    )
    episodes = []
    previous = None
    for stamp, hit in positives:
        if previous is None or stamp - previous > timedelta(hours=6):
            episodes.append([])
        episodes[-1].append(hit)
        previous = stamp
    return {
        "episode_count": len(episodes),
        "any_hit_count": sum(any(e) for e in episodes),
        "full_hit_count": sum(all(e) for e in episodes),
        "fully_missed_count": sum(not any(e) for e in episodes),
        "episode_sizes": [len(e) for e in episodes],
    }


def instantaneous_persistence(index):
    """Persist current instantaneous NAQI for the instantaneous t+6 target."""
    band = band_for_index(index)
    if band is None:
        raise ValueError("Missing instantaneous NAQI; cannot construct persistence baseline")
    return BAND_NAMES.index(band.value)


def unsupported_classes(training_support, target_support):
    """Explicitly identify evaluated classes absent from model training."""
    return {
        name: count for name, count in target_support.items()
        if count > 0 and training_support.get(name, 0) == 0
    }


def episode_support(times, labels, minimum_band=3, separation_hours=6):
    """Group positive hours separated by at most six hours into episodes."""
    positive = sorted(t for t, y in zip(times, labels, strict=True) if y >= minimum_band)
    sizes = []
    previous = None
    for stamp in positive:
        if previous is None or stamp - previous > timedelta(hours=separation_hours):
            sizes.append(0)
        sizes[-1] += 1
        previous = stamp
    return {
        "positive_hours": len(positive), "episode_count": len(sizes),
        "episode_sizes": sizes,
        "largest_episode_fraction": max(sizes) / len(positive) if positive else None,
        "separation_hours": separation_hours,
    }


def window_indices(times, start, end, gap_hours=6):
    """Keep features and their labels strictly before the next phase boundary."""
    start, end = datetime.fromisoformat(start), datetime.fromisoformat(end)
    gap = timedelta(hours=gap_hours)
    return [i for i, t in enumerate(times) if start <= t and t + gap < end]


def support_aware_partitions(
    times, labels, usable, start, end, min_positive=20, min_negative=200, gap_hours=6
):
    """Earliest daily cuts using ONLY pre-evaluation labels; never shuffle episodes.

    Counts are hourly support, not independent pollution episodes. This adaptive
    design is development research and does not create independent holdouts.
    """
    if not (len(times) == len(labels) == len(usable)):
        raise ValueError("Partition inputs have different lengths")
    finish = datetime.fromisoformat(end)
    cursor = datetime.fromisoformat(start)
    phases = {}

    def supported(begin, stop):
        ids = [
            i for i in window_indices(times, begin.isoformat(), stop.isoformat(), gap_hours)
            if usable[i]
        ]
        positive = sum(labels[i] >= 3 for i in ids)
        return positive >= min_positive and len(ids) - positive >= min_negative

    for name in ("development", "calibration"):
        stop = cursor + timedelta(days=1)
        while stop < finish and not supported(cursor, stop):
            stop += timedelta(days=1)
        if stop >= finish:
            raise ValueError("Insufficient pre-evaluation support for " + name)
        phases[name] = [cursor.date().isoformat(), stop.date().isoformat()]
        cursor = stop
    if not supported(cursor, finish):
        raise ValueError("Insufficient pre-evaluation support for threshold_selection")
    phases["threshold_selection"] = [cursor.date().isoformat(), finish.date().isoformat()]
    return phases


def risk_metrics(labels, probabilities, predictions):
    """Poor-or-worse risk, including false alarms and probability reliability."""
    truth = [int(y >= 3) for y in labels]
    predicted = [int(y >= 3) for y in predictions]
    tp = sum(t and p for t, p in zip(truth, predicted, strict=True))
    positives, alarms = sum(truth), sum(predicted)
    fp = alarms - tp
    negatives = len(truth) - positives
    bins = []
    for i in range(10):
        values = [
            (p, t)
            for p, t in zip(probabilities, truth, strict=True)
            if i / 10 <= p < (i + 1) / 10 or (i == 9 and p == 1)
        ]
        if values:
            bins.append(
                {
                    "n": len(values),
                    "probability": sum(p for p, _ in values) / len(values),
                    "observed": sum(t for _, t in values) / len(values),
                }
            )
    return {
        "n": len(truth),
        "positive_support": positives,
        "negative_support": negatives,
        "misses": positives - tp,
        "recall": tp / positives if positives else None,
        "false_alarms": fp,
        "false_alarm_rate": fp / negatives if negatives else None,
        "precision": tp / alarms if alarms else None,
        "brier": sum((p - t) ** 2 for p, t in zip(probabilities, truth, strict=True)) / len(truth),
        "ece_10_bins": sum(b["n"] * abs(b["probability"] - b["observed"]) for b in bins)
        / len(truth),
        "reliability_bins": bins,
    }


def band_accuracy(labels, predictions):
    return sum(a == b for a, b in zip(labels, predictions, strict=True)) / len(labels)


def apply_risk_floor(predictions, probabilities, threshold):
    return [
        max(int(y), 3) if p >= threshold else int(y)
        for y, p in zip(predictions, probabilities, strict=True)
    ]


def choose_threshold(
    labels,
    predictions,
    probabilities,
    thresholds,
    baseline_accuracy,
    max_false_alarm=0.10,
    max_accuracy_loss=0.03,
):
    """Selection is permitted only on the caller's development partition."""
    trials = []
    for threshold in thresholds:
        proposed = apply_risk_floor(predictions, probabilities, threshold)
        metrics = risk_metrics(labels, probabilities, proposed)
        accuracy = band_accuracy(labels, proposed)
        eligible = (
            metrics["positive_support"] > 0
            and metrics["negative_support"] > 0
            and metrics["false_alarm_rate"] <= max_false_alarm
            and accuracy >= baseline_accuracy - max_accuracy_loss
        )
        trials.append(
            {"threshold": threshold, "metrics": metrics, "accuracy": accuracy, "eligible": eligible}
        )
    eligible = [t for t in trials if t["eligible"]]
    selected = (
        max(eligible, key=lambda t: (t["metrics"]["recall"], t["accuracy"], t["threshold"]))
        if eligible
        else None
    )
    return selected, trials


def logit(probabilities):
    return [
        [math.log(max(1e-6, min(1 - 1e-6, p)) / (1 - max(1e-6, min(1 - 1e-6, p))))]
        for p in probabilities
    ]
