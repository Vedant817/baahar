#!/usr/bin/env python
"""Fine-tuned tabular research optimization."""

from __future__ import annotations

import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.utils.class_weight import compute_sample_weight

sys.path.insert(0, str(Path(__file__).parent))
from experiment_tabular import BAND_ORDINALS, evaluate, extract_features, impute, load_rows


def main():
    repo_root = Path(__file__).resolve().parents[1]
    rows = load_rows(repo_root / "data" / "eval" / "gono_rows.jsonl")
    cut = int(len(rows) * 0.8)
    train_rows, test_rows = rows[:cut], rows[cut:]
    y_train = np.array([BAND_ORDINALS.get(r["target_band"], -1) for r in train_rows], dtype="int64")
    y_test = np.array([BAND_ORDINALS.get(r["target_band"], -1) for r in test_rows], dtype="int64")

    x_tr = np.array([extract_features(r, mode="enhanced") for r in train_rows], dtype="float64")
    x_te = np.array([extract_features(r, mode="enhanced") for r in test_rows], dtype="float64")
    x_tr, medians = impute(x_tr)
    x_te, _ = impute(x_te, medians)

    sw = compute_sample_weight("balanced", y_train)

    # 1. HistGB balanced
    hgb = HistGradientBoostingClassifier(random_state=42, max_iter=300)
    hgb.fit(x_tr, y_train, sample_weight=sw)
    p_hgb = hgb.predict_proba(x_te)

    # 2. LightGBM balanced
    lgbm_bal = lgb.LGBMClassifier(
        random_state=42,
        n_estimators=350,
        learning_rate=0.03,
        num_leaves=24,
        class_weight="balanced",
        subsample=0.85,
        colsample_bytree=0.85,
        verbosity=-1,
    )
    lgbm_bal.fit(x_tr, y_train)
    p_lgb = lgbm_bal.predict_proba(x_te)

    # 3. LightGBM unweighted
    lgbm_raw = lgb.LGBMClassifier(
        random_state=42,
        n_estimators=450,
        learning_rate=0.04,
        num_leaves=28,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_alpha=0.5,
        reg_lambda=1.0,
        verbosity=-1,
    )
    lgbm_raw.fit(x_tr, y_train)
    p_lgb_raw = lgbm_raw.predict_proba(x_te)

    def expand(p, classes):
        full = np.zeros((p.shape[0], 6))
        for idx, c in enumerate(classes):
            full[:, c] = p[:, idx]
        return full

    p1 = expand(p_hgb, hgb.classes_)
    p2 = expand(p_lgb, lgbm_bal.classes_)
    p3 = expand(p_lgb_raw, lgbm_raw.classes_)

    for w_hgb, w_bal, w_raw in [
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
        (0.5, 0.5, 0.0),
        (0.4, 0.2, 0.4),
        (0.3, 0.1, 0.6),
        (0.2, 0.1, 0.7),
        (0.5, 0.0, 0.5),
    ]:
        blend = w_hgb * p1 + w_bal * p2 + w_raw * p3
        preds = np.argmax(blend, axis=1)
        res = evaluate(y_test, preds, test_rows)
        print(
            f"Weights ({w_hgb:.1f}, {w_bal:.1f}, {w_raw:.1f}) -> Acc={res['accuracy']:.4f} | Macro-F1={res['macro_f1']:.4f} | ModF1={res['per_class']['moderate']['f1']:.4f} (Rec={res['per_class']['moderate']['recall']:.4f})"
        )


if __name__ == "__main__":
    main()
