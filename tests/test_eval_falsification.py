"""Falsification tests for eval safety metrics: skip_as_go_rate and decision_accuracy.

A research audit found:
1. `skip_as_go_rate` is 0.0 for EVERY model in eval/RESULTS.md, including majority class.
2. `decision_accuracy` is ~0.9975 for every model.

These tests prove:
- `skip_as_go_rate` is mathematically unreachable from 0.0 on this holdout dataset:
  all 24 true-SKIP hours are triggered by rain (22) or heat (2), and zero by air
  quality. Because the evaluation harness feeds the same weather features to both
  truth and prediction, `apply_band_policy` returns "SKIP" for any predicted band,
  making a false "GO" impossible for any model whatsoever (even always-good).
- `decision_accuracy` cannot discriminate a trained model from a catastrophic model
  that always predicts "good": always-good scores 0.9982 (1623/1626), outscoring
  the tuned consensus ensemble (0.9975).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_dataset  # noqa: E402
import run_eval  # noqa: E402

from baahar.features import BAND_ORDINALS  # noqa: E402

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "eval" / "gono_rows.jsonl"
RAW_DIR = Path(__file__).resolve().parents[1] / "eval" / "raw"


@pytest.fixture(scope="module")
def holdout_data():
    """Load the identical 20% chronological holdout used by scripts/run_eval.py."""
    assert DATA_PATH.exists(), f"Missing eval data at {DATA_PATH}"
    rows = run_eval.load_rows(DATA_PATH)
    cut = int(len(rows) * 0.8)
    test_rows = rows[cut:]
    y_test = [BAND_ORDINALS.get(r["target_band"], -1) for r in test_rows]
    return test_rows, y_test


def test_catastrophic_always_good_scores_high_decision_acc_and_zero_skip_as_go(holdout_data):
    """A model predicting 'good' (air is always clean) gets 0.0 skip_as_go and 0.9982 acc.

    This is catastrophic failure in the unsafe direction: telling the user air is
    pristine when it is moderate or poor. Yet it scores 0.9982 on decision accuracy
    and 0.0 on skip_as_go_rate, looking like a flawless safety result.
    """
    test_rows, y_test = holdout_data
    n_rows = len(test_rows)
    assert n_rows == 1626

    # Catastrophic model: always predicts "good" (band ordinal 0)
    preds = [run_eval.BANDS.index("good")] * n_rows
    metrics = run_eval.safety_metrics(y_test, preds, test_rows)

    assert metrics["skip_as_go_rate"] == 0.0
    assert metrics["skip_as_go_count"] == 0
    assert metrics["n_true_skip"] == 24
    # Exact match: 1623 / 1626 = 0.998155... rounded to 0.9982
    assert metrics["decision_accuracy"] == 0.9982


def test_catastrophic_always_hazardous_scores_zero_skip_as_go(holdout_data):
    """A model predicting 'hazardous' (air is always deadly) still gets 0.0 skip_as_go.

    This proves skip_as_go_rate does not move even under maximal pessimism.
    Decision accuracy drops to 0.0148 because only 24 hours are true SKIP.
    """
    test_rows, y_test = holdout_data
    n_rows = len(test_rows)

    # Catastrophic model: always predicts "hazardous" (band ordinal 5)
    preds = [run_eval.BANDS.index("hazardous")] * n_rows
    metrics = run_eval.safety_metrics(y_test, preds, test_rows)

    assert metrics["skip_as_go_rate"] == 0.0
    assert metrics["skip_as_go_count"] == 0
    assert metrics["n_true_skip"] == 24
    # Exact match: 24 / 1626 = 0.01476... rounded to 0.0148
    assert metrics["decision_accuracy"] == 0.0148


def test_catastrophic_always_poor_and_severe_metrics(holdout_data):
    """Verify metrics across intermediate catastrophic baselines."""
    test_rows, y_test = holdout_data
    n_rows = len(test_rows)

    # Always severe (band ordinal 4)
    preds_sev = [run_eval.BANDS.index("severe")] * n_rows
    metrics_sev = run_eval.safety_metrics(y_test, preds_sev, test_rows)
    assert metrics_sev["skip_as_go_rate"] == 0.0
    assert metrics_sev["decision_accuracy"] == 0.0148

    # Always poor (band ordinal 3)
    preds_poor = [run_eval.BANDS.index("poor")] * n_rows
    metrics_poor = run_eval.safety_metrics(y_test, preds_poor, test_rows)
    assert metrics_poor["skip_as_go_rate"] == 0.0
    # Exact match: 259 / 1626 = 0.15928... rounded to 0.1593
    assert metrics_poor["decision_accuracy"] == 0.1593


def test_majority_baseline_matches_always_good(holdout_data):
    """The majority class baseline (satisfactory) scores identically to always-good."""
    test_rows, y_test = holdout_data
    n_rows = len(test_rows)

    preds = [run_eval.BANDS.index("satisfactory")] * n_rows
    metrics = run_eval.safety_metrics(y_test, preds, test_rows)

    assert metrics["skip_as_go_rate"] == 0.0
    assert metrics["decision_accuracy"] == 0.9982


def test_skip_as_go_rate_is_structurally_unreachable_on_holdout(holdout_data):
    """Prove WHY skip_as_go_rate is 0.0 for EVERY model: non-zero is unreachable.

    Mechanism:
    1. In this holdout, all 24 true-SKIP hours have precipitation >= 2.5mm / >= 70%
       or apparent temperature >= 35C. ZERO true-SKIP hours are caused by air quality
       (severe or hazardous air).
    2. In `scripts/run_eval.py:safety_metrics`, `p_dec` is computed with the same
       `row["precip_mm"]`, `row["precip_prob"]`, and `row["apparent_c"]` as `t_dec`.
    3. Therefore, `apply_band_policy` encounters the same rain/heat threshold and
       returns "SKIP" for every true-SKIP row regardless of the predicted band.
    4. Since `p_dec` is always "SKIP" when `t_dec` is "SKIP", `p_dec == 'GO'` is
       impossible. `skip_as_go` is strictly 0 for ANY predicted band.
    """
    test_rows, y_test = holdout_data

    # Identify true SKIP rows
    skip_indices = []
    for idx, (tb, row) in enumerate(zip(y_test, test_rows, strict=True)):
        t_band = run_eval.BANDS[tb] if 0 <= tb < len(run_eval.BANDS) else None
        dec = build_dataset.apply_band_policy(
            t_band, row["precip_mm"], row["precip_prob"], row["apparent_c"]
        )
        if dec == "SKIP":
            skip_indices.append(idx)

    assert len(skip_indices) == 24

    # Verify that air quality NEVER caused SKIP on any holdout row
    for idx in skip_indices:
        tb = y_test[idx]
        t_band = run_eval.BANDS[tb]
        # Target band is never severe or hazardous
        assert t_band not in {"severe", "hazardous"}

    # Prove that for EVERY possible predicted band, `apply_band_policy` returns SKIP
    all_possible_bands = [*run_eval.BANDS, None]
    for idx in skip_indices:
        row = test_rows[idx]
        for candidate_band in all_possible_bands:
            pred_dec = build_dataset.apply_band_policy(
                candidate_band, row["precip_mm"], row["precip_prob"], row["apparent_c"]
            )
            assert pred_dec == "SKIP", (
                f"Row {idx} returned {pred_dec} instead of SKIP for band {candidate_band}"
            )


def test_decision_accuracy_fails_to_discriminate_real_models_from_always_good(holdout_data):
    """Prove that decision_accuracy cannot discriminate good models from always-good.

    Always-good achieves 0.9982, which is GREATER than or equal to:
    - Consensus ensemble: 0.9975
    - LightGBM: 0.9975
    - Logistic regression: 0.9969
    """
    test_rows, y_test = holdout_data
    n_rows = len(test_rows)

    preds_good = [run_eval.BANDS.index("good")] * n_rows
    sm_good = run_eval.safety_metrics(y_test, preds_good, test_rows)
    always_good_acc = sm_good["decision_accuracy"]
    assert always_good_acc == 0.9982

    # Load the recorded consensus ensemble seed 0 metrics from the raw artifact
    raw_file = sorted(RAW_DIR.glob("gono_20261007T145138+0530.json"))[0]
    payload = json.loads(raw_file.read_text(encoding="utf-8"))
    ensemble_safety = payload["results"]["ensemble"]["safety"]
    ensemble_decision_acc = ensemble_safety["decision_accuracy"]

    assert ensemble_decision_acc == 0.9975
    # The catastrophic always-good baseline scores higher than the best model!
    assert always_good_acc >= ensemble_decision_acc
