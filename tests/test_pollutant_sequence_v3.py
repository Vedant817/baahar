"""Training priorities use the canonical rounded category boundary."""

import importlib.util
from pathlib import Path

import pytest

from baahar.naqi import band_for_index

spec = importlib.util.spec_from_file_location(
    "sequence_v3", Path(__file__).parents[1] / "scripts/train_pollutant_sequence_v3_modal.py"
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_training_priority_obeys_shared_rounding_and_includes_high_categories():
    def weight(index):
        return runner.training_origin_weight(runner.BANDS.index(band_for_index(index)))

    assert weight(200.5) == 1.0
    assert weight(200.51) == 2.0
    assert weight(300.51) == 2.0
    assert weight(400.51) == 2.0
    with pytest.raises(ValueError, match="Unknown canonical ordinal"):
        runner.training_origin_weight(6)
