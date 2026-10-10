"""Residual forecasts preserve targets, causal reconstruction and error scales."""

import importlib.util
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location(
    "sequence_v4", Path(__file__).parents[1] / "scripts/train_pollutant_sequence_v4_modal.py"
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_zero_residual_repeats_origin_for_all_future_horizons():
    current = np.array([[12.0, 24.0, 8.0, 80.0, 2.0, 300.0]])
    output = np.zeros((1, 6, 6))
    forecast = runner.decode_residual(output, current, np.arange(1, 7))
    np.testing.assert_array_equal(forecast, np.broadcast_to(current[:, None, :], output.shape))


def test_encoding_round_trip_and_development_error_equivalence():
    current = np.array([[12.0, 24.0, 8.0, 80.0, 2.0, 300.0]])
    future = np.arange(36, dtype=float).reshape(1, 6, 6) + current[:, None, :]
    scale = np.arange(1, 7, dtype=float)
    target = runner.encode_residual(future, current, scale).astype(np.float32)
    np.testing.assert_allclose(runner.decode_residual(target, current, scale), future, rtol=2e-6)
    output = target + 0.125
    residual_mae = np.mean(np.abs(output - target))
    absolute_mae = np.mean(np.abs(runner.decode_residual(output, current, scale) - future) / scale)
    np.testing.assert_allclose(residual_mae, absolute_mae, rtol=2e-6)


def test_origin_shift_preserves_encoded_change_and_shifts_forecast():
    current = np.array([[1.0] * 6])
    future = np.arange(36, dtype=float).reshape(1, 6, 6)
    scale = np.arange(1, 7)
    shift = np.array([[10.0, 20.0, 30.0, 40.0, 50.0, 60.0]])
    baseline = runner.encode_residual(future, current, scale)
    shifted = runner.encode_residual(future + shift[:, None, :], current + shift, scale)
    np.testing.assert_allclose(baseline, shifted)
    np.testing.assert_allclose(
        runner.decode_residual(baseline, current + shift, scale), future + shift[:, None, :]
    )
