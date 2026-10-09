"""Explicit synthetic algorithm cases; no invented upstream fixtures."""

import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "forecast_risk", Path(__file__).parents[1] / "scripts/forecast_risk.py"
)
risk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(risk)


def test_label_gap_excludes_cross_boundary_target():
    times = [datetime(2024, 10, 31, hour) for hour in (16, 17, 18, 23)]
    assert risk.window_indices(times, "2024-01-01", "2024-11-01") == [0, 1]


def test_selection_rejects_recall_obtained_by_alerting_everyone():
    labels = [0, 0, 0, 3]
    selected, trials = risk.choose_threshold(
        labels,
        [0] * 4,
        [0.3, 0.4, 0.5, 0.9],
        [0.2, 0.8],
        baseline_accuracy=0.75,
        max_false_alarm=0.1,
        max_accuracy_loss=0.03,
    )
    assert not trials[0]["eligible"]
    assert selected["threshold"] == 0.8
    assert selected["metrics"]["recall"] == 1
    assert selected["metrics"]["false_alarm_rate"] == 0


def test_absent_risk_cases_are_unmeasured_and_block_selection():
    metrics = risk.risk_metrics([0, 1], [0.1, 0.2], [0, 1])
    assert metrics["recall"] is None
    assert metrics["brier"] == pytest.approx(0.025)
    selected, _ = risk.choose_threshold([0, 1], [0, 1], [0.1, 0.2], [0.5], 1)
    assert selected is None


def test_risk_floor_never_downgrades_a_more_severe_prediction():
    assert risk.apply_risk_floor([0, 4, 5], [0.9, 0.9, 0.1], 0.5) == [3, 4, 5]


def test_persistence_matches_instantaneous_target_and_refuses_missing_data():
    assert risk.instantaneous_persistence(45) == 0
    assert risk.instantaneous_persistence(350) == 4
    with pytest.raises(ValueError, match="Missing instantaneous"):
        risk.instantaneous_persistence(None)
    with pytest.raises(ValueError, match="Missing instantaneous"):
        risk.instantaneous_persistence(float("nan"))


def test_absent_training_classes_are_reported_without_treating_them_as_supported():
    assert risk.unsupported_classes(
        {"good": 100, "poor": 20}, {"poor": 12, "severe": 13, "hazardous": 0}
    ) == {"severe": 13}


def test_correlated_risk_hours_are_counted_as_episodes_not_independent_cases():
    origin = datetime(2025, 3, 1)
    times = [origin + timedelta(hours=i) for i in (0, 1, 7, 14, 15)]
    support = risk.episode_support(times, [4, 4, 3, 4, 4])
    assert support["episode_count"] == 2
    assert support["episode_sizes"] == [3, 2]
    assert support["positive_hours"] == 5
    severe = risk.episode_support(times, [4, 4, 3, 4, 4], 4)
    assert severe["episode_sizes"] == [2, 2]


def test_instant_history_uses_exact_past_timestamps_and_no_future_targets():
    rows = [
        {"time": "2025-01-01T00:00", "naqi_instant": 50, "target_naqi": 999},
        {"time": "2025-01-01T02:00", "naqi_instant": 80, "target_naqi": 0},
        {"time": "2025-01-01T03:00", "naqi_instant": 100, "target_naqi": 0},
    ]
    features = risk.instantaneous_history_features(rows)
    assert features[2][:3] == [100, 80, 50]
    assert features[2][4:6] == [20, 50]
    # Row adjacency must not pretend the absent 01:00 hour exists.
    assert features[1][1] != features[1][1]  # NaN
    rows[2]["naqi_instant"] = 999
    rows[0]["target_naqi"] = -100
    after = risk.instantaneous_history_features(rows)
    assert after[1][0] == features[1][0]
    assert after[0][0] == features[0][0]


def test_quantile_metrics_and_episode_hits_preserve_their_denominators():
    metrics = risk.numeric_forecast_metrics([10, 30], [20, 20], 0.9)
    assert metrics["mae"] == 10
    assert metrics["pinball_loss"] == pytest.approx(5)
    assert metrics["empirical_quantile_coverage"] == 0.5
    origin = datetime(2025, 1, 1)
    events = risk.event_detection_metrics(
        [origin + timedelta(hours=h) for h in (0, 1, 20)], [4, 4, 4], [4, 3, 3], 4
    )
    assert events["episode_count"] == 2
    assert events["any_hit_count"] == 1
    assert events["full_hit_count"] == 0
    assert events["fully_missed_count"] == 1


def test_adaptive_splits_exclude_locked_labels_and_embargo_targets():
    times = [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(24 * 8)]
    labels = [3 if t.hour < 9 else 0 for t in times]
    phases = risk.support_aware_partitions(
        times, labels, [True] * len(times), "2024-01-01", "2024-01-07",
        min_positive=8, min_negative=8,
    )
    # Jan 7-8 is locked; changing its labels must never change phase boundaries.
    changed = [y if t < datetime(2024, 1, 7) else 5 for t, y in zip(times, labels, strict=True)]
    assert phases == risk.support_aware_partitions(
        times, changed, [True] * len(times), "2024-01-01", "2024-01-07",
        min_positive=8, min_negative=8,
    )
    seen = set()
    for start, end in phases.values():
        ids = risk.window_indices(times, start, end)
        assert seen.isdisjoint(ids)
        seen.update(ids)
        assert all(times[i] + timedelta(hours=6) < datetime.fromisoformat(end) for i in ids)


def test_adaptive_splits_refuse_insufficient_selection_support():
    times = [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(24 * 4)]
    labels = [3 if t.day < 3 and t.hour < 9 else 0 for t in times]
    with pytest.raises(ValueError, match="threshold_selection"):
        risk.support_aware_partitions(
            times, labels, [True] * len(times), "2024-01-01", "2024-01-05",
            min_positive=8, min_negative=8,
        )
