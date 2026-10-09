"""Causal indexing and immutable comparison contract, using abstract arrays."""

import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "lag_probe", Path(__file__).parents[1] / "scripts/probe_pollutant_lag_modal.py"
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_extended_features_have_identical_recent_suffix_and_never_read_future():
    t = datetime(2025, 4, 3)
    air = {(t + timedelta(hours=h)).isoformat(timespec="minutes"):
           dict.fromkeys(runner.GASES, h) for h in range(-47, 1)}
    recent = runner.features(t.isoformat(), air, {}, 24)
    extended = runner.features(t.isoformat(), air, {}, 48)
    assert len(recent) == 360
    assert len(extended) == 624
    # Missing-weather NaNs cannot compare directly.
    assert [v for v in extended[-360:] if v == v] == [v for v in recent if v == v]
    assert extended[0] == -47
    assert recent[0] == -23
    with pytest.raises(ValueError, match="frozen"):
        runner.features(t.isoformat(), air, {}, 72)


def test_phase_local_eligibility_requires_all_exact_future_hours():
    start, end = "2025-04-01", "2025-05-01"
    t = datetime(2025, 4, 3)
    air = {(t + timedelta(hours=h)).isoformat(timespec="minutes"):
           dict.fromkeys(runner.GASES, 1.0) for h in range(-47, 7)}
    assert runner.eligible(t.isoformat(), start, end, air)
    assert not runner.eligible("2025-04-01T23:00", start, end, air)
    del air[(t + timedelta(hours=3)).isoformat(timespec="minutes")]
    assert not runner.eligible(t.isoformat(), start, end, air)


def test_origin_digest_is_order_independent_but_rejects_duplicates():
    assert runner.origins_digest(["b", "a"]) == runner.origins_digest(["a", "b"])
    assert runner.origins_digest(["a"]) != runner.origins_digest(["b"])
    with pytest.raises(ValueError, match="Duplicate"):
        runner.origins_digest(["a", "a"])
