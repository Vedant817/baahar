#!/usr/bin/env python
"""Experiment research runner for tabular 6-hour ahead NAQI band forecasting.

Tests:
1. Feature engineering:
   - Baseline 13 features
   - + Cyclic diurnal encoding (hour_sin, hour_cos, month_sin, month_cos)
   - + Domain physical ratios (pm25/pm10 ratio, naqi_gap, dispersion proxy)
2. Class balancing strategies:
   - None (default)
   - Balanced class weights / sample weights
   - Custom heuristic weighting (giving moderate and poor higher weight)
3. Model architectures:
   - Tuned HistGradientBoosting
   - LightGBM (LGBMClassifier)
   - Tuned RandomForest
   - Calibrated / Stacking / Soft Voting Ensemble
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.utils.class_weight import compute_sample_weight

try:
    import lightgbm as lgb

    HAS_LGB = True
except ImportError:
    HAS_LGB = False

sys.path.insert(0, str(Path(__file__).parent))
from build_dataset import apply_band_policy

BANDS = ["good", "satisfactory", "moderate", "poor", "severe", "hazardous"]
BAND_ORDINALS = {b: i for i, b in enumerate(BANDS)}
DECISIONS = ["GO", "WAIT", "SKIP"]

BASE_FEATURE_NAMES = [
    "naqi",
    "pm25",
    "pm10",
    "temp_c",
    "apparent_c",
    "precip_mm",
    "precip_prob",
    "humidity",
    "wind_kmh",
    "uv_index",
    "is_day",
    "hour",
    "month",
]


def load_rows(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    rows.sort(key=lambda r: r["time"])
    return rows


def _f(v) -> float:
    if v is None:
        return float("nan")
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def extract_features(row: dict, mode: str = "base") -> list[float]:
    base = [_f(row.get(c)) for c in BASE_FEATURE_NAMES]
    if mode == "base":
        return base

    # Enhanced feature set
    hour = _f(row.get("hour"))
    month = _f(row.get("month"))
    pm25 = _f(row.get("pm25"))
    pm10 = _f(row.get("pm10"))
    naqi = _f(row.get("naqi"))
    naqi_instant = _f(row.get("naqi_instant"))
    wind = _f(row.get("wind_kmh"))
    temp = _f(row.get("temp_c"))
    humidity = _f(row.get("humidity"))

    # Cyclic time
    hour_sin = math.sin(2 * math.pi * hour / 24.0) if not math.isnan(hour) else 0.0
    hour_cos = math.cos(2 * math.pi * hour / 24.0) if not math.isnan(hour) else 0.0
    month_sin = math.sin(2 * math.pi * month / 12.0) if not math.isnan(month) else 0.0
    month_cos = math.cos(2 * math.pi * month / 12.0) if not math.isnan(month) else 0.0

    # Physical ratios & interactions
    # 1. PM ratio (fine combustion vs coarse dust)
    if not math.isnan(pm25) and not math.isnan(pm10) and pm10 > 0:
        pm_ratio = min(max(pm25 / pm10, 0.0), 1.0)
    else:
        pm_ratio = float("nan")

    # 2. NAQI gap: trailing conservative memory vs instant reading
    naqi_gap = naqi - naqi_instant if not math.isnan(naqi) and not math.isnan(naqi_instant) else 0.0

    # 3. Atmospheric stagnation proxy: low wind * high humidity
    if not math.isnan(wind) and not math.isnan(humidity):
        stagnation = (humidity / 100.0) / (wind + 1.0)
    else:
        stagnation = float("nan")

    # 4. Temperature-humidity spread (dew point depression proxy)
    if not math.isnan(temp) and not math.isnan(humidity):
        dew_depression = (100.0 - humidity) / 5.0
    else:
        dew_depression = float("nan")

    extras = [
        hour_sin,
        hour_cos,
        month_sin,
        month_cos,
        pm_ratio,
        naqi_gap,
        stagnation,
        dew_depression,
    ]
    return base + extras


def impute(x, medians=None):
    if medians is None:
        medians = np.nanmedian(x, axis=0)
        medians = np.where(np.isnan(medians), 0.0, medians)
    inds = np.where(np.isnan(x))
    x = x.copy()
    x[inds] = np.take(medians, inds[1])
    return x, medians


def evaluate(y_true, y_pred, rows):
    cm = [[0] * 6 for _ in range(6)]
    for t, p in zip(y_true, y_pred, strict=True):
        if 0 <= t < 6 and 0 <= p < 6:
            cm[t][p] += 1

    per = {}
    for i in range(len(cm)):
        tp = cm[i][i]
        fp = sum(cm[r][i] for r in range(len(cm)) if r != i)
        fn = sum(cm[i][c] for c in range(len(cm)) if c != i)
        support = sum(cm[i])
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per[BANDS[i]] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": support,
        }

    correct = sum(cm[i][i] for i in range(len(cm)))
    total = sum(sum(row) for row in cm)
    f1s = [v["f1"] for v in per.values() if v["support"] > 0]
    acc = round(correct / total, 4) if total else 0.0
    mf1 = round(sum(f1s) / len(f1s), 4) if f1s else 0.0

    # Decision accuracy & skip_as_go
    true_dec, pred_dec = [], []
    for tb, pb, row in zip(y_true, y_pred, rows, strict=True):
        t_band = BANDS[tb] if 0 <= tb < len(BANDS) else None
        p_band = BANDS[pb] if 0 <= pb < len(BANDS) else None
        t_dec = apply_band_policy(t_band, row["precip_mm"], row["precip_prob"], row["apparent_c"])
        p_dec = apply_band_policy(p_band, row["precip_mm"], row["precip_prob"], row["apparent_c"])
        true_dec.append(t_dec)
        pred_dec.append(p_dec)

    dec_acc = round(
        sum(1 for t, p in zip(true_dec, pred_dec, strict=True) if t == p) / len(true_dec), 4
    )
    n_skip = sum(1 for d in true_dec if d == "SKIP")
    skip_as_go = sum(
        1 for t, p in zip(true_dec, pred_dec, strict=True) if t == "SKIP" and p == "GO"
    )

    return {
        "accuracy": acc,
        "macro_f1": mf1,
        "decision_acc": dec_acc,
        "skip_as_go": skip_as_go,
        "n_skip": n_skip,
        "per_class": per,
        "cm": cm,
    }


def main():
    repo_root = Path(__file__).resolve().parents[1]
    rows = load_rows(repo_root / "data" / "eval" / "gono_rows.jsonl")
    cut = int(len(rows) * 0.8)
    train_rows, test_rows = rows[:cut], rows[cut:]
    y_train = np.array([BAND_ORDINALS.get(r["target_band"], -1) for r in train_rows], dtype="int64")
    y_test = np.array([BAND_ORDINALS.get(r["target_band"], -1) for r in test_rows], dtype="int64")

    print(f"Total rows: {len(rows)} | Train: {len(train_rows)} | Test: {len(test_rows)}")
    print("=" * 70)

    modes = ["base", "enhanced"]
    for mode in modes:
        x_tr = np.array([extract_features(r, mode=mode) for r in train_rows], dtype="float64")
        x_te = np.array([extract_features(r, mode=mode) for r in test_rows], dtype="float64")
        x_tr, medians = impute(x_tr)
        x_te, _ = impute(x_te, medians)

        print(f"\n--- FEATURE MODE: {mode.upper()} ({x_tr.shape[1]} features) ---")

        # 1. Baseline HistGB
        clf = HistGradientBoostingClassifier(random_state=42, max_iter=300)
        clf.fit(x_tr, y_train)
        preds = clf.predict(x_te)
        res = evaluate(y_test, preds, test_rows)
        print(
            f"HistGB default:        Acc={res['accuracy']:.4f} | Macro-F1={res['macro_f1']:.4f} | DecAcc={res['decision_acc']:.4f} | ModF1={res['per_class']['moderate']['f1']:.4f} (Rec={res['per_class']['moderate']['recall']:.4f})"
        )

        # 2. HistGB with sample weights (balanced)
        sw = compute_sample_weight("balanced", y_train)
        clf_w = HistGradientBoostingClassifier(random_state=42, max_iter=300)
        clf_w.fit(x_tr, y_train, sample_weight=sw)
        preds_w = clf_w.predict(x_te)
        res_w = evaluate(y_test, preds_w, test_rows)
        print(
            f"HistGB balanced:       Acc={res_w['accuracy']:.4f} | Macro-F1={res_w['macro_f1']:.4f} | DecAcc={res_w['decision_acc']:.4f} | ModF1={res_w['per_class']['moderate']['f1']:.4f} (Rec={res_w['per_class']['moderate']['recall']:.4f})"
        )

        # 3. HistGB with tuned parameters
        clf_tune = HistGradientBoostingClassifier(
            random_state=42,
            max_iter=400,
            learning_rate=0.08,
            min_samples_leaf=20,
            l2_regularization=1.5,
        )
        clf_tune.fit(x_tr, y_train)
        preds_tune = clf_tune.predict(x_te)
        res_tune = evaluate(y_test, preds_tune, test_rows)
        print(
            f"HistGB tuned:          Acc={res_tune['accuracy']:.4f} | Macro-F1={res_tune['macro_f1']:.4f} | DecAcc={res_tune['decision_acc']:.4f} | ModF1={res_tune['per_class']['moderate']['f1']:.4f}"
        )

        # 4. LightGBM (if available)
        if HAS_LGB:
            lgb_clf = lgb.LGBMClassifier(
                random_state=42,
                n_estimators=300,
                learning_rate=0.05,
                num_leaves=31,
                verbosity=-1,
            )
            lgb_clf.fit(x_tr, y_train)
            preds_lgb = lgb_clf.predict(x_te)
            res_lgb = evaluate(y_test, preds_lgb, test_rows)
            print(
                f"LightGBM default:      Acc={res_lgb['accuracy']:.4f} | Macro-F1={res_lgb['macro_f1']:.4f} | DecAcc={res_lgb['decision_acc']:.4f} | ModF1={res_lgb['per_class']['moderate']['f1']:.4f}"
            )

            # LightGBM tuned
            lgb_tune = lgb.LGBMClassifier(
                random_state=42,
                n_estimators=450,
                learning_rate=0.04,
                num_leaves=25,
                subsample=0.85,
                colsample_bytree=0.85,
                reg_alpha=0.5,
                reg_lambda=1.0,
                verbosity=-1,
            )
            lgb_tune.fit(x_tr, y_train)
            preds_lgbt = lgb_tune.predict(x_te)
            res_lgbt = evaluate(y_test, preds_lgbt, test_rows)
            print(
                f"LightGBM tuned:        Acc={res_lgbt['accuracy']:.4f} | Macro-F1={res_lgbt['macro_f1']:.4f} | DecAcc={res_lgbt['decision_acc']:.4f} | ModF1={res_lgbt['per_class']['moderate']['f1']:.4f}"
            )

            # 5. Soft-Voting Ensemble (HistGB + LightGBM + RF)
            rf = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
            rf.fit(x_tr, y_train)

            p_hist = clf.predict_proba(x_te)
            p_lgb = lgb_clf.predict_proba(x_te)
            p_rf = rf.predict_proba(x_te)

            # Align probability dimensions (in case some classes are 0)
            def expand_probs(p, clf_classes, n_classes=6):
                full = np.zeros((p.shape[0], n_classes))
                for idx, c in enumerate(clf_classes):
                    full[:, c] = p[:, idx]
                return full

            p1 = expand_probs(p_hist, clf.classes_)
            p2 = expand_probs(p_lgb, lgb_clf.classes_)
            p3 = expand_probs(p_rf, rf.classes_)

            p_ens = 0.4 * p1 + 0.4 * p2 + 0.2 * p3
            preds_ens = np.argmax(p_ens, axis=1)
            res_ens = evaluate(y_test, preds_ens, test_rows)
            print(
                f"Ensemble (HGB+LGB+RF): Acc={res_ens['accuracy']:.4f} | Macro-F1={res_ens['macro_f1']:.4f} | DecAcc={res_ens['decision_acc']:.4f} | ModF1={res_ens['per_class']['moderate']['f1']:.4f}"
            )


if __name__ == "__main__":
    main()
