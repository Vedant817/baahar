"""Finite report gates preserve denominator and paired episode semantics."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "report_pollutant_sequence", Path(__file__).parents[1] / "scripts/report_pollutant_sequence.py"
)
reporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reporter)
evaluate_gate, paired_new_hits = reporter.evaluate_gate, reporter.paired_new_hits


def risk(support=10, recall=0.5, far=0.01, misses=5, hits=1):
    return {"support": support, "recall": recall, "false_alarm_rate": far,
            "misses": misses, "episodes": {"any_hit": hits}}


def period(name, gain=False):
    ref = {"accuracy": 0.8, "risk": {"poor_or_worse": risk(),
           "very_poor_or_worse": risk(0, None, 0.0, 0, 0), "severe": risk(0, None, 0.0, 0, 0)},
           "predicted_legacy_bands": [2, 2]}
    cand = {"accuracy": 0.8, "risk": {"poor_or_worse": risk(recall=0.6 if gain else 0.5),
            "very_poor_or_worse": risk(0, None, 0.0, 0, 0), "severe": risk(0, None, 0.0, 0, 0)},
            "predicted_legacy_bands": [2, 2]}
    return {"partition": name, "times": ["2026-02-01T00:00", "2026-02-01T01:00"],
            "actual_legacy_bands": [2, 2], "models": {"paired_lightgbm": ref, "tcn_fixed_mean": cand}}


def test_two_new_hits_must_occur_in_one_reference_missed_episode():
    result = paired_new_hits(["2026-02-01T00:00", "2026-02-01T08:00"], [4, 4], [3, 3], [4, 4])
    assert result["new_hits_in_fully_missed_reference_episodes"] == 2
    assert result["maximum_new_hits_in_one_reference_missed_episode"] == 1
    same_episode = paired_new_hits(["2026-02-01T00:00", "2026-02-01T06:00"], [4, 4], [3, 3], [4, 4])
    assert same_episode["maximum_new_hits_in_one_reference_missed_episode"] == 2


def test_finite_research_gain_keeps_missing_official_severe_support_explicit():
    report = evaluate_gate([period("diagnostic_pollution", True), period("diagnostic_other_seasons")], "tcn_fixed_mean")
    assert report["research_utility_gate_passed"]
    assert len(report["unsupported_claims"]) == 4
    assert report["disposition"] == "RESEARCH_ONLY_NO_AUTOMATIC_PROMOTION"


def test_false_alarm_regression_fails_even_when_recall_improves():
    first = period("diagnostic_pollution", True)
    first["models"]["tcn_fixed_mean"]["risk"]["poor_or_worse"]["false_alarm_rate"] = 0.03
    report = evaluate_gate([first, period("diagnostic_other_seasons")], "tcn_fixed_mean")
    assert not report["guardrails_passed"]
    assert not report["research_utility_gate_passed"]
