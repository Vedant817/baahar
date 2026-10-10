"""Offline integrity checks for the fixed full-origin linear comparator."""

import ast
import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_flattened_features_are_causal_and_equal_probe():
    runner = load("train_pollutant_linear_modal")
    probe = load("probe_pollutant_lag_modal")
    base = load("train_pollutant_sequence_v3_modal")
    stamp = datetime(2025, 1, 3, 0)
    air, weather = {}, {}
    for h in range(-23, 7):
        t = (stamp + timedelta(hours=h)).isoformat(timespec="minutes")
        air[t] = {g: float(h + 30) for g in runner.GASES}
        weather[t] = {g: float(h + 50) for g in probe.WEATHER}
    key = stamp.isoformat(timespec="minutes")
    observed = runner.features(key, air, weather, 24)
    assert len(observed) == 360
    assert observed == [v for hour in base.feature_window(key, air, weather) for v in hour]
    for h in range(1, 7):
        air[(stamp + timedelta(hours=h)).isoformat(timespec="minutes")] = dict.fromkeys(
            runner.GASES, 1000000000000.0
        )
    assert runner.features(key, air, weather, 24) == observed


def test_full_origin_support_and_pairing_guard():
    runner = load("train_pollutant_linear_modal")
    origin = datetime(2025, 1, 2, 0)
    air = {
        (origin + timedelta(hours=h)).isoformat(timespec="minutes"): dict.fromkeys(
            runner.GASES, 1.0
        )
        for h in range(-23, 7)
    }
    key = origin.isoformat(timespec="minutes")
    assert runner.supported_window(key, "2025-01-01", "2025-01-03", air)
    assert not runner.supported_window(key, "2025-01-02", "2025-01-03", air)
    del air[(origin + timedelta(hours=5)).isoformat(timespec="minutes")]
    assert not runner.supported_window(key, "2025-01-01", "2025-01-03", air)
    reference = {
        "times": [key],
        "actual_naqi": [1.0],
        "actual_legacy_bands": ["good"],
        "actual_pollutants": [[1.0] * 6],
    }
    runner.validate_pair(reference, [key], [1.0], ["good"], [[1.0] * 6])
    with pytest.raises(ValueError, match="Paired"):
        runner.validate_pair(reference, [key], [1.0], ["good"], [[2.0] * 6])


def test_frozen_gate_ast_is_unchanged():
    def gate(path):
        tree = ast.parse(path.read_text())
        return ast.dump(
            next(
                n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "evaluate_gate"
            )
        )

    assert gate(ROOT / "scripts/report_pollutant_linear.py") == gate(
        ROOT / "scripts/report_pollutant_sequence_v5.py"
    )
