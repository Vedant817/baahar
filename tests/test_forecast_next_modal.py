"""Offline causal feature and fixed-floor regression checks."""

import math
import sys
from datetime import datetime, timedelta
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = spec_from_file_location("forecast_next_modal", SCRIPTS / "forecast_next_modal.py")
runner = module_from_spec(spec)
spec.loader.exec_module(runner)


def test_gas_history_uses_exact_causal_timestamps():
    now = datetime(2025, 1, 1, 12)
    archive = {}
    for hours, value in ((0, 10), (1, 7), (3, 4), (6, 2), (-1, 999)):
        archive[(now - timedelta(hours=hours)).isoformat(timespec="minutes")] = dict.fromkeys(
            runner.GASES, value
        )
    vector = runner.gas_history_features([now], archive)[0]
    assert len(vector) == len(runner.GAS_COLUMNS) == 28
    assert vector[:7] == [10, 7, 4, 2, 3, 6, 8]
    assert 999 not in vector


def test_missing_gas_lag_is_not_replaced_by_adjacent_hour():
    now = datetime(2025, 1, 1, 12)
    archive = {
        now.isoformat(timespec="minutes"): dict.fromkeys(runner.GASES, 5),
        (now - timedelta(hours=2)).isoformat(timespec="minutes"): dict.fromkeys(runner.GASES, 4),
    }
    vector = runner.gas_history_features([now], archive)[0]
    assert vector[0] == 5
    assert all(math.isnan(value) for value in vector[1:7])


def test_quantile_floor_uses_shared_rounded_boundary_and_preserves_severe():
    # band_for_index uses Python rounding: 200.5 rounds to 200 (moderate).
    assert runner.quantile_poor_floor([0, 1, 4, 5], [200.5, 200.51, 10, 301]) == [0, 3, 4, 5]


def test_prediction_hash_is_order_sensitive():
    assert runner.prediction_digest([1, 2]) != runner.prediction_digest([2, 1])
