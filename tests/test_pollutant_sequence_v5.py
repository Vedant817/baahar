"""Endpoint priority must preserve trajectory supervision and gate contracts."""

import ast
import importlib.util
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("sequence_v5", ROOT / "scripts/train_pollutant_sequence_v5_modal.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_endpoint_priority_matches_frozen_mixture_and_keeps_earlier_supervision():
    errors = np.arange(72, dtype=float).reshape(2, 6, 6)
    expected = 0.5 * errors.mean(axis=1) + 0.5 * errors[:, -1, :]
    np.testing.assert_allclose(runner.horizon_priority(errors), expected)
    assert sum(runner.HORIZON_WEIGHTS) == pytest.approx(1)
    earlier, endpoint = np.zeros((1, 6, 6)), np.zeros((1, 6, 6))
    earlier[:, 0, :] = 1
    endpoint[:, -1, :] = 1
    assert runner.horizon_priority(earlier).mean() > 0
    assert runner.horizon_priority(endpoint).mean() == pytest.approx(7 * runner.horizon_priority(earlier).mean())
    with pytest.raises(ValueError, match="six-horizons"):
        runner.horizon_priority(np.zeros((1, 1, 6)))


def test_v3_comparison_gate_is_preserved_verbatim_from_v4():
    def gate(name):
        tree = ast.parse((ROOT / "scripts" / name).read_text(encoding="utf-8"))
        return ast.dump(next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "evaluate_gate"))
    assert gate("report_pollutant_sequence_v5.py") == gate("report_pollutant_sequence_v4.py")
