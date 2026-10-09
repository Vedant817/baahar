"""A loss ablation must refuse mismatched paired evaluation origins/targets."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "sequence_v2", Path(__file__).parents[1] / "scripts/train_pollutant_sequence_v2_modal.py"
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.mark.parametrize("key", ["times", "actual_naqi", "actual_legacy_bands", "actual_pollutants"])
def test_changed_paired_origin_or_target_is_rejected(key):
    actual = {"times": ["2026-02-02T00:00"], "actual_naqi": [210.0],
              "actual_legacy_bands": ["poor"], "actual_pollutants": [[1.0] * 6]}
    runner.validate_pair(actual, actual["times"], actual["actual_naqi"],
                         actual["actual_legacy_bands"], actual["actual_pollutants"])
    changed = dict(actual)
    changed[key] = []
    with pytest.raises(ValueError, match="Paired reference"):
        runner.validate_pair(changed, actual["times"], actual["actual_naqi"],
                             actual["actual_legacy_bands"], actual["actual_pollutants"])
