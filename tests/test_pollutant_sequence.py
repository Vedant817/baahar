"""Offline timestamp and target-isolation checks; torch is hosted-only."""

import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "pollutant_sequence",
    Path(__file__).resolve().parents[1] / "scripts/train_pollutant_sequence_modal.py",
)
sequence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sequence)


def fixture():
    origin = datetime(2025, 1, 1)
    return {
        (origin + timedelta(hours=i)).isoformat(timespec="minutes"): dict.fromkeys(
            sequence.GASES, float(i + 1)
        )
        for i in range(100)
    }


def test_phase_local_context_and_exact_future():
    air = fixture()
    assert not sequence.supported_window("2025-01-01T22:00", "2025-01-01", "2025-01-05", air)
    assert sequence.supported_window("2025-01-01T23:00", "2025-01-01", "2025-01-05", air)
    assert not sequence.supported_window("2025-01-04T18:00", "2025-01-01", "2025-01-05", air)
    del air["2025-01-02T01:00"]
    assert not sequence.supported_window("2025-01-01T23:00", "2025-01-01", "2025-01-05", air)


def test_future_mutation_cannot_change_features():
    air = fixture()
    before = sequence.feature_window("2025-01-01T23:00", air, {})
    air["2025-01-02T00:00"] = dict.fromkeys(sequence.GASES, 9999.0)
    after = sequence.feature_window("2025-01-01T23:00", air, {})
    # Weather NaNs intentionally remain for training-only imputation.
    assert [row[:6] + row[11:] for row in before] == [row[:6] + row[11:] for row in after]
    assert before[0][:6] == [1.0] * 6
    assert before[-1][:6] == [24.0] * 6


def test_episode_any_full_and_onset_are_distinct():
    times = ["2025-01-01T00:00", "2025-01-01T01:00", "2025-01-01T10:00"]
    observed = sequence.event_metrics(times, [302, 302, 302], [200, 310, 310], 301)
    assert observed == {"episodes": 2, "any_hit": 2, "full_hit": 1, "onset_hit": 1}


def test_canonical_rounded_boundary_is_shared_by_risk():
    from baahar.naqi import band_for_index

    assert sequence.BANDS.index(band_for_index(200.5)) == 2
    assert sequence.BANDS.index(band_for_index(200.51)) == 3
    truth = [sequence.BANDS.index(band_for_index(200.51))]
    assert sequence.event_metrics(["2025-01-01T00:00"], truth, truth, 3)["any_hit"] == 1
