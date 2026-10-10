"""Paired counterfactual and finite improvement gates."""

from datetime import datetime, timedelta
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

SPEC = spec_from_file_location(
    "report_forecast_next", Path(__file__).resolve().parents[1] / "scripts/report_forecast_next.py"
)
report = module_from_spec(SPEC)
SPEC.loader.exec_module(report)


def test_new_severe_hits_excludes_episodes_already_detected():
    start = datetime(2026, 1, 1)
    times = [
        start,
        start + timedelta(hours=1),
        start + timedelta(hours=12),
        start + timedelta(hours=13),
    ]
    measured = report.new_severe_hits(times, [4] * 4, [4, 0, 0, 0], [0, 4, 4, 4])
    assert measured["newly_captured_previously_missed_episodes"] == 1
    assert measured["new_severe_hours_in_previously_missed_episodes"] == 2
    assert measured["newly_detected_times"] == [t.isoformat() for t in times[2:]]


def result(positives, hits):
    start = datetime(2026, 1, 1)
    labels = [1] * 200 + [3] * positives
    reference = [1] * len(labels)
    challenger = [1] * 200 + [3] * hits + [1] * (positives - hits)
    return {
        "results": [
            {
                "partition": name,
                "labels": labels,
                "times": [(start + timedelta(hours=i)).isoformat() for i in range(len(labels))],
                "models": {
                    "incumbent": {"predictions": reference},
                    "challenger": {"predictions": challenger},
                },
            }
            for name in report.PERIODS
        ]
    }


def test_one_hour_gain_among_23_positives_does_not_reach_frozen_minimum():
    measured = report.evaluate(result(23, 1), "incumbent", "challenger")
    assert measured["utility_gates_passed"]
    assert not measured["meaningful_gain"]


def test_poor_recall_gain_meets_frozen_minimum():
    measured = report.evaluate(result(20, 1), "incumbent", "challenger")
    assert measured["meaningful_gain"]
    assert measured["poor_recall_gain_criterion"]


def test_episode_hit_regression_blocks_hourly_recall_gain():
    measured_result = result(20, 1)
    period = measured_result["results"][0]
    period["times"][205:] = [
        (datetime.fromisoformat(period["times"][205]) + timedelta(hours=12 + i)).isoformat()
        for i in range(15)
    ]
    period["models"]["incumbent"]["predictions"][205] = 3
    period["models"]["incumbent"]["predictions"][200] = 3
    period["models"]["challenger"]["predictions"][200:205] = [3] * 5
    measured = report.evaluate(measured_result, "incumbent", "challenger")
    assert not measured["periods"][0]["gates"]["poor_episode_any_hits"]
    assert not measured["meaningful_gain"]
