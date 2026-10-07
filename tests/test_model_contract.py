"""Regression tests for the fitted artifact's feature contract."""

from types import SimpleNamespace

import numpy as np
import pytest

from baahar import score
from baahar.features import (
    COMPACT_FEATURE_NAMES,
    TABPFN_FEATURE_ORDER,
    _row_dict_from_slot,
    features_from_slot,
    features_from_slots,
    matrix_from_slots,
)


class RecordingModel:
    def __init__(self, width):
        self.n_features_in_ = width
        self.classes_ = np.arange(6)
        self.seen = None

    def predict_proba(self, x):
        self.seen = x.copy()
        return np.tile([[1.0, 0.0, 0.0, 0.0, 0.0, 0.0]], (len(x), 1))


def bundle(width, order=None):
    result = {key: RecordingModel(width) for key in ("lgb", "hgb", "rf")}
    if order is not None:
        result["feature_order"] = list(order)
    return result


@pytest.mark.parametrize("scorer", [score.score_ensemble, score.score_lgbm])
def test_recorded_order_is_authoritative(go_slot, scorer):
    # Same width as compact, deliberately different order: width alone cannot detect this.
    order = tuple(reversed(COMPACT_FEATURE_NAMES))
    model = bundle(len(order), order)
    scorer([go_slot], model=model)
    values = features_from_slot(go_slot)
    np.testing.assert_allclose(model["lgb"].seen[0], [values[n] for n in order])


def test_ensemble_legacy_component_width(go_slot):
    model = bundle(len(TABPFN_FEATURE_ORDER))
    scores = score.score_ensemble([go_slot], model=model)
    assert scores[0].scorer == "ensemble"
    assert model["lgb"].seen.shape[1] == len(TABPFN_FEATURE_ORDER)


@pytest.mark.parametrize("scorer", [score.score_ensemble, score.score_lgbm])
@pytest.mark.parametrize("component", ["lgb", "hgb", "rf"])
def test_width_mismatch_names_contract_and_fix(go_slot, scorer, component):
    model = bundle(len(TABPFN_FEATURE_ORDER), COMPACT_FEATURE_NAMES)
    for key in ("lgb", "hgb", "rf"):
        if key != component:
            model[key].n_features_in_ = len(COMPACT_FEATURE_NAMES)
    with pytest.raises(ValueError) as caught:
        scorer([go_slot], model=model)
    message = str(caught.value)
    for required in (
        "Feature width mismatch",
        component,
        f"expects {len(TABPFN_FEATURE_ORDER)}",
        f"matrix has {len(COMPACT_FEATURE_NAMES)}",
        "_model.pkl",
        "scripts/run_eval.py",
        "feature_order",
    ):
        assert required in message
    assert all(model[key].seen is None for key in ("lgb", "hgb", "rf"))


@pytest.mark.parametrize("scorer", [score.score_ensemble, score.score_lgbm])
def test_unknown_contract_is_not_guessed(go_slot, scorer):
    with pytest.raises(ValueError, match="no feature_order or component n_features_in_"):
        scorer([go_slot], model=SimpleNamespace())


def test_save_load_keeps_exact_feature_order(tmp_path, go_slot):
    order = tuple(reversed(TABPFN_FEATURE_ORDER))
    model = bundle(len(order))
    path = tmp_path / "ensemble.pkl"
    score.save_ensemble_model(model, path, feature_order=order)
    loaded = score.load_ensemble_model(path)
    assert loaded["feature_order"] == list(order)
    score.score_ensemble([go_slot], model=loaded)
    np.testing.assert_allclose(
        loaded["lgb"].seen[0], [features_from_slot(go_slot)[n] for n in order]
    )


def test_bare_lgbm_round_trip(tmp_path, go_slot):
    path = tmp_path / "lgbm.pkl"
    score.save_lgbm_model(RecordingModel(len(TABPFN_FEATURE_ORDER)), path)
    loaded = score.load_lgbm_model(path)
    scores = score.score_lgbm([go_slot], model=loaded)
    assert scores[0].scorer == "lgbm"
    assert loaded.seen.shape[1] == len(TABPFN_FEATURE_ORDER)


def test_eval_compact_matrix_uses_serving_derivation(go_slot, monkeypatch):
    from pathlib import Path

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    import run_eval

    from conftest import make_slot

    values = features_from_slot(go_slot)
    row = {name: values[name] for name in TABPFN_FEATURE_ORDER}
    row.update(naqi_instant=go_slot.air.naqi, target_band="good")
    x, _ = run_eval.to_matrix([row], COMPACT_FEATURE_NAMES)
    np.testing.assert_allclose(x[0], [values[n] for n in COMPACT_FEATURE_NAMES])

    # 1. Train/Serve Identity: run_eval.to_matrix and matrix_from_slots produce identical 28 features
    slots = [make_slot(i, temp_c=22.0 + i, pm25=25.0 + 3.0 * i) for i in range(12)]
    eval_rows = [_row_dict_from_slot(s) for s in slots]
    for r in eval_rows:
        r["target_band"] = "good"
    x_eval, _ = run_eval.to_matrix(eval_rows, TABPFN_FEATURE_ORDER)
    x_serve = np.array(matrix_from_slots(slots, TABPFN_FEATURE_ORDER), dtype="float64")
    np.testing.assert_allclose(x_eval, x_serve, equal_nan=True)

    # 2. Strict No-Leakage Guard: modifying future hours t+1..t+6 does not alter features at hour t
    t = 5
    slots_perturbed = [
        make_slot(
            i,
            temp_c=(99.0 if i > t else 22.0 + i),
            pm25=(250.0 if i > t else 25.0 + 3.0 * i),
            wind_kmh=(50.0 if i > t else 8.0),
        )
        for i in range(12)
    ]
    orig_t = matrix_from_slots(slots, TABPFN_FEATURE_ORDER)[t]
    perturbed_t = matrix_from_slots(slots_perturbed, TABPFN_FEATURE_ORDER)[t]
    np.testing.assert_allclose(orig_t, perturbed_t, equal_nan=True)

    # 3. No-History Edge Cases: single slot and short window impute finite defaults cleanly
    single_dict = features_from_slot(go_slot)
    for name in TABPFN_FEATURE_ORDER:
        assert not np.isnan(single_dict[name]), f"{name} is NaN in single slot"
    short_feats = features_from_slots(slots[:2], impute_missing=True)
    for row_f in short_feats:
        for name in TABPFN_FEATURE_ORDER:
            assert not np.isnan(row_f[name]), f"{name} is NaN in short imputed window"
