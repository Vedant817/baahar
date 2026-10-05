#!/usr/bin/env python
"""Run the go/no-go tabular eval and write raw results.

What is being measured
----------------------
Task: predict the CPCB NAQI **band six hours ahead** from hour-*t* features
(current air quality, current weather, hour of day, month). Built by
`scripts/build_dataset.py` from Open-Meteo CAMS + ERA5 archives.

Why the band and not GO/WAIT/SKIP directly: the safety rule is a policy we can
write down exactly, so it should *be* code, not something a model has to
approximate. The model predicts the observable physical quantity (air-quality
band); `apply_band_policy` turns that into the user-facing decision. This keeps
the interesting part of the problem -- forecasting a polluted subcontinent --
in the model, and the boring, auditable part in a reviewed function.

Models compared
  majority    Predict the training set's most common band. The floor.
  persistence Predict band(t) as band(t+6). A real meteorological baseline,
              not a strawman: air quality is persistent, so this is strong.
  logreg      Multinomial logistic regression. A conventional tabular model,
              to show what the foundation model is actually buying.
  tabpfn      TabPFN, the model under test (requires `--group ml`).

Reported metrics
  accuracy, macro-F1, per-class precision/recall/F1, full confusion matrix,
  and the safety metric that actually matters:
      skip_as_go_rate = P(predicted GO | true SKIP)
  reported with a Wilson 95% interval, because n(SKIP) is small and a bare
  rate on a few dozen cases would be misleading.

Anti-slop rules enforced here
  * Chronological split, never shuffled.
  * No threshold or hyperparameter is tuned on the holdout.
  * Every number is written to eval/raw/*.json with package versions and an
    ISO timestamp, so RESULTS.md is auditable.
  * If TabPFN is not installed, the run is marked SKIPPED, not faked.

Usage
  uv run python scripts/run_eval.py
  uv run python scripts/run_eval.py --holdout 0.2 --repeat 3
"""

from __future__ import annotations

import argparse
import importlib.metadata as md
import json
import platform
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from baahar.config import EVAL_DATA_DIR, EVAL_RAW_DIR, get_settings
from baahar.features import BAND_ORDINALS, NAQI_SKIP, PRECIP_SKIP_MM
from baahar.score import save_tabpfn_model

sys.path.insert(0, str(Path(__file__).parent))
from build_dataset import apply_band_policy  # noqa: E402

BANDS = ["good", "satisfactory", "moderate", "poor", "severe", "hazardous"]
DECISIONS = ["GO", "WAIT", "SKIP"]

FEATURE_COLUMNS = [
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


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
def load_rows(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        raise SystemExit(f"no rows in {path}; run scripts/build_dataset.py first")
    rows.sort(key=lambda r: r["time"])  # chronological, always
    return rows


def _coerce(value) -> float:
    """JSON null and missing keys both become NaN, never a fake 0.0.

    Reading a missing air-quality value as zero would tell the model the air was
    perfectly clean, which is the same class of bug as Baahar's own.
    """
    if value is None:
        return float("nan")
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def to_matrix(rows: list[dict]):
    import numpy as np

    x = np.array([[_coerce(r.get(c)) for c in FEATURE_COLUMNS] for r in rows], dtype="float64")
    y = np.array([BAND_ORDINALS.get(r["target_band"], -1) for r in rows], dtype="int64")
    return x, y


def impute(x, medians=None):
    """Median-impute NaNs. TabPFN rejects NaN; sklearn pipelines want it too."""
    import numpy as np

    if medians is None:
        medians = np.nanmedian(x, axis=0)
        medians = np.where(np.isnan(medians), 0.0, medians)
    inds = np.where(np.isnan(x))
    x = x.copy()
    x[inds] = np.take(medians, inds[1])
    return x, medians


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------
def confusion(y_true, y_pred, k: int = 6) -> list[list[int]]:
    cm = [[0] * k for _ in range(k)]
    for t, p in zip(y_true, y_pred, strict=True):
        if 0 <= t < k and 0 <= p < k:
            cm[t][p] += 1
    return cm


def prf(cm) -> dict:
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
    return {
        "accuracy": round(correct / total, 4) if total else 0.0,
        "macro_f1": round(sum(f1s) / len(f1s), 4) if f1s else 0.0,
        "per_class": per,
        "n": total,
    }


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval. Honest for the small n(SKIP) case."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (round((centre - margin) / denom, 4), round((centre + margin) / denom, 4))


def safety_metrics(y_true_band: list[int], y_pred_band: list[int], rows: list[dict]) -> dict:
    """Turn band predictions into user-facing decisions and count the failure mode.

    skip_as_go_rate is the headline: of the hours a human should have been told to
    stay in, how often did Baahar tell them to go for a walk?

    Also breaks down *why* an hour was a SKIP. This turned out to matter a lot:
    the holdout window contains no Severe or Hazardous air hours at all, so
    every SKIP in the test set is caused by heat or rain, not by pollution.
    Reporting skip_as_go_rate without that breakdown would imply the metric was
    testing air-quality safety when it was not.
    """
    true_dec, pred_dec = [], []
    causes = Counter()
    for tb, pb, row in zip(y_true_band, y_pred_band, rows, strict=True):
        t_band = BANDS[tb] if 0 <= tb < len(BANDS) else None
        p_band = BANDS[pb] if 0 <= pb < len(BANDS) else None
        # Use the hour-t weather the row carries. That is an approximation for
        # the +6h target hour and is recorded as such in the output.
        t_dec = apply_band_policy(t_band, row["precip_mm"], row["precip_prob"], row["apparent_c"])
        p_dec = apply_band_policy(p_band, row["precip_mm"], row["precip_prob"], row["apparent_c"])
        true_dec.append(t_dec)
        pred_dec.append(p_dec)

        if t_dec == "SKIP":
            from baahar.naqi import band_index_range

            low, _ = band_index_range(t_band)
            air_bad = low >= NAQI_SKIP
            heat_bad = row["apparent_c"] is not None and row["apparent_c"] >= 35
            rain_bad = (row["precip_mm"] or 0) >= PRECIP_SKIP_MM or (row["precip_prob"] or 0) >= 70
            reasons = [
                name
                for name, active in (
                    ("air", air_bad),
                    ("heat", heat_bad),
                    ("rain", rain_bad),
                )
                if active
            ]
            causes["+".join(reasons) if reasons else "unknown"] += 1

    n_true_skip = sum(1 for d in true_dec if d == "SKIP")
    skip_as_go = sum(
        1 for t, p in zip(true_dec, pred_dec, strict=True) if t == "SKIP" and p == "GO"
    )
    skip_as_skip = sum(
        1 for t, p in zip(true_dec, pred_dec, strict=True) if t == "SKIP" and p == "SKIP"
    )
    n_true_go = sum(1 for d in true_dec if d == "GO")
    go_as_skip = sum(
        1 for t, p in zip(true_dec, pred_dec, strict=True) if t == "GO" and p == "SKIP"
    )

    lo, hi = wilson(skip_as_go, n_true_skip)
    return {
        "n_true_skip": n_true_skip,
        "skip_as_go_count": skip_as_go,
        "skip_as_go_rate": round(skip_as_go / n_true_skip, 4) if n_true_skip else None,
        "skip_as_go_wilson95": [lo, hi],
        "skip_recall": round(skip_as_skip / n_true_skip, 4) if n_true_skip else None,
        "n_true_go": n_true_go,
        "go_as_skip_count": go_as_skip,
        "go_as_skip_rate": round(go_as_skip / n_true_go, 4) if n_true_go else None,
        "decision_confusion": confusion(
            [DECISIONS.index(d) for d in true_dec],
            [DECISIONS.index(d) for d in pred_dec],
            k=3,
        ),
        "decision_accuracy": round(
            sum(1 for t, p in zip(true_dec, pred_dec, strict=True) if t == p) / len(true_dec),
            4,
        )
        if true_dec
        else None,
        "skip_cause_breakdown": dict(causes),
        "skip_cause_note": (
            "Which signal put each true-SKIP hour into SKIP. Read this before "
            "interpreting skip_as_go_rate: if 'air' is absent, the metric is "
            "measuring heat and rain handling, not air-quality safety."
        ),
        "_policy_approximation": (
            "apply_band_policy was fed hour-t weather rather than hour-t+6 weather; "
            "the dataset does not store the target hour's weather separately."
        ),
    }


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------
def fit_predict(
    name: str, x_train, y_train, x_test, medians, seed: int = 0
) -> tuple[list[int], float, str]:
    """Return ``(predictions, fit_seconds, note)``. Raises to signal SKIPPED."""
    t0 = time.perf_counter()

    if name == "majority":
        import numpy as np

        counts = np.bincount(y_train, minlength=6)
        majority = int(counts.argmax())
        return (
            [majority] * len(x_test),
            time.perf_counter() - t0,
            "always predicts the training majority",
        )

    if name == "persistence":
        # Band(t) -> band(t+6) is literally "predict the current band".
        return list(y_train[:0]) or None, 0.0, "unused"

    if name == "logreg":
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler

        clf = make_pipeline(
            StandardScaler(),
            # `multi_class` was removed in scikit-learn 1.5+; lbfgs multinomial
            # is the default for >2 classes, so the parameter is simply gone.
            LogisticRegression(max_iter=2000, random_state=seed),
        )
        clf.fit(x_train, y_train)
        preds = clf.predict(x_test)
        return [int(p) for p in preds], time.perf_counter() - t0, "multinomial logistic regression"

    if name == "histgb":
        # Gradient boosting is the honest conventional strong baseline for
        # tabular data. If a foundation model cannot beat this, it should not be
        # shipped, and we would rather find that out now than in the write-up.
        from sklearn.ensemble import HistGradientBoostingClassifier

        clf = HistGradientBoostingClassifier(random_state=seed, max_iter=300)
        clf.fit(x_train, y_train)
        preds = clf.predict(x_test)
        return [int(p) for p in preds], time.perf_counter() - t0, "HistGradientBoostingClassifier"

    if name == "rf":
        from sklearn.ensemble import RandomForestClassifier

        clf = RandomForestClassifier(
            n_estimators=300, random_state=seed, n_jobs=-1, class_weight="balanced_subsample"
        )
        clf.fit(x_train, y_train)
        preds = clf.predict(x_test)
        return [int(p) for p in preds], time.perf_counter() - t0, "RandomForestClassifier(300)"

    if name == "tabpfn":
        try:
            from tabpfn import TabPFNClassifier
        except ImportError as exc:
            raise RuntimeError(
                f"tabpfn not installed ({exc}); run `uv sync --group dev --group ml`"
            ) from exc
        if not get_settings().has_tabpfn_license:
            raise RuntimeError(
                "tabpfn refuses to download weights until a Prior Labs licence "
                "acceptance is recorded in TABPFN_TOKEN, even though the weights "
                "are public on Hugging Face. We do not bypass a licence gate. "
                "See docs/NEEDS_HUMAN.md for the 3 steps."
            )
        clf = TabPFNClassifier(device="cpu", random_state=seed)
        clf.fit(x_train, y_train)
        probs = clf.predict_proba(x_test)
        # TabPFN may not predict every class if some are absent from train;
        # map its column order back onto our global class indices.
        classes = list(getattr(clf, "classes_", range(probs.shape[1])))
        preds = [int(classes[int(np.argmax(row))]) for row in probs]
        # Persist the fitted classifier so the web app scores with the *exact*
        # model this table reports, rather than refitting something different at
        # request time.
        try:
            artifact = save_tabpfn_model(clf)
            print(f"  fitted model saved -> {artifact}")
        except Exception as exc:  # noqa: BLE001
            print(f"  could not save the fitted model: {exc}", file=sys.stderr)
        return preds, time.perf_counter() - t0, f"TabPFN {md.version('tabpfn')}, cpu"

    raise ValueError(f"unknown model {name}")


def fit_predict_persistence(y_train_bands: list[int], n_test: int) -> list[int]:
    """Persistence: predict band(t) as band(t+6).

    Implemented from the *train* rows' current band so it never peeks at the
    holdout's target column. The holdout's current bands are legitimately known
    at prediction time (they are features), so using them is not leakage.
    """
    raise NotImplementedError  # replaced by caller which has the rows


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def package_versions() -> dict:
    out = {"python": platform.python_version(), "platform": platform.platform()}
    for pkg in ("numpy", "pandas", "scikit-learn", "tabpfn", "torch"):
        try:
            out[pkg] = md.version(pkg)
        except md.PackageNotFoundError:
            out[pkg] = None
    return out


def holdout_support(rows: list[dict]) -> dict:
    """Per-class support in the holdout, including classes with zero rows.

    Explicitly reporting the zero-support classes matters: a macro-F1 that
    silently averages over only the classes that happen to be present reads as
    broader coverage than it is.
    """
    counts = Counter(r["target_band"] for r in rows)
    return {band: {"n": counts.get(band, 0), "present": counts.get(band, 0) > 0} for band in BANDS}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rows", default=str(EVAL_DATA_DIR / "gono_rows.jsonl"))
    ap.add_argument("--holdout", type=float, default=0.2)
    ap.add_argument("--repeat", type=int, default=1, help="seeds to average over")
    ap.add_argument(
        "--models",
        default="majority,persistence,logreg,rf,histgb,tabpfn",
        help="comma-separated model list",
    )
    args = ap.parse_args(argv)

    rows = load_rows(Path(args.rows))

    x_all, y_all = to_matrix(rows)
    x_all, medians = impute(x_all)

    # Chronological cut. The holdout is the *most recent* slice, which is the
    # only split that resembles deployment: train on the past, predict the future.
    cut = int(len(rows) * (1 - args.holdout))
    x_train, x_test = x_all[:cut], x_all[cut:]
    y_train, y_test = y_all[:cut], y_all[cut:]
    train_rows, test_rows = rows[:cut], rows[cut:]

    # The persistence baseline needs the *current* band of each holdout hour.
    # That is a feature -- known at prediction time -- not the target column, so
    # reading it here is not leakage.
    test_band_now = [BAND_ORDINALS.get(r["band"], -1) for r in test_rows]

    print(f"rows={len(rows)}  features={len(FEATURE_COLUMNS)}  horizon=6h")
    print(f"train={len(x_train)} ({train_rows[0]['time']} .. {train_rows[-1]['time']})")
    print(f"test ={len(x_test)} ({test_rows[0]['time']} .. {test_rows[-1]['time']})")
    print(f"holdout fraction={args.holdout}  (chronological, not shuffled)\n")

    print("train band distribution:")
    for band, count in sorted(Counter(r["band"] for r in train_rows).items()):
        print(f"  {band:<14}{count:6}")
    print("\ntest band distribution:")
    for band, count in sorted(Counter(r["band"] for r in test_rows).items()):
        print(f"  {band:<14}{count:6}")
    print()

    results: dict[str, dict] = {}
    for name in [m.strip() for m in args.models.split(",") if m.strip()]:
        runs: list[dict] = []
        skipped_reason = None
        for seed in range(args.repeat):
            try:
                if name == "persistence":
                    t0 = time.perf_counter()
                    preds = test_band_now  # band(t) -> band(t+6); a real baseline
                    elapsed = time.perf_counter() - t0
                    note = "predict band(t) as band(t+6)"
                else:
                    preds, elapsed, note = fit_predict(
                        name, x_train, y_train, x_test, medians, seed
                    )
            except RuntimeError as exc:
                skipped_reason = str(exc)
                break

            cm = confusion(list(y_test), preds)
            metrics = prf(cm)
            safety = safety_metrics(list(y_test), preds, test_rows)
            runs.append(
                {
                    "seed": seed,
                    **metrics,
                    "confusion": cm,
                    "safety": safety,
                    "fit_seconds": round(elapsed, 3),
                    "note": note,
                }
            )

        if skipped_reason:
            results[name] = {"status": "SKIPPED", "reason": skipped_reason}
            print(f"{name:<12} SKIPPED -- {skipped_reason}")
            continue

        def mean(runs_: list[dict], key: str):
            vals = [r[key] for r in runs_ if r.get(key) is not None]
            return round(sum(vals) / len(vals), 4) if vals else None

        def stdev(runs_: list[dict], key: str):
            vals = [r[key] for r in runs_ if r.get(key) is not None]
            if len(vals) < 2:
                return None
            m = sum(vals) / len(vals)
            return round((sum((v - m) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5, 4)

        agg = {
            "status": "OK",
            "runs": len(runs),
            "accuracy_mean": mean(runs, "accuracy"),
            "accuracy_sd": stdev(runs, "accuracy"),
            "macro_f1_mean": mean(runs, "macro_f1"),
            "macro_f1_sd": stdev(runs, "macro_f1"),
            "per_class": runs[0]["per_class"],
            "confusion": runs[0]["confusion"],
            "safety": {
                k: runs[0]["safety"][k]
                for k in (
                    "n_true_skip",
                    "skip_as_go_count",
                    "skip_as_go_rate",
                    "skip_as_go_wilson95",
                    "skip_recall",
                    "n_true_go",
                    "go_as_skip_count",
                    "go_as_skip_rate",
                    "decision_confusion",
                    "decision_accuracy",
                    "skip_cause_breakdown",
                    "skip_cause_note",
                    "_policy_approximation",
                )
            },
            "fit_seconds_mean": mean(runs, "fit_seconds"),
            "note": runs[0]["note"],
        }
        results[name] = agg

        s = agg["safety"]
        print(
            f"{name:<12} acc={agg['accuracy_mean']:.4f}  macroF1={agg['macro_f1_mean']:.4f}  "
            f"skip_as_go={s['skip_as_go_rate']} (n={s['n_true_skip']}, "
            f"95% CI {s['skip_as_go_wilson95']})  decision_acc={s['decision_accuracy']}"
        )

    absent = [b for b, v in holdout_support(test_rows).items() if not v["present"]]
    if absent:
        print(f"\n! no holdout rows for: {', '.join(absent)}")
        print("  macro-F1 therefore averages over fewer than 6 classes, and those")
        print("  bands are not validated by this run at all.")
    print("\nwhy each true-SKIP hour was a SKIP:")
    for model, r in results.items():
        if r.get("status") == "OK" and r["safety"].get("skip_cause_breakdown"):
            print(f"  {model:<12} {r['safety']['skip_cause_breakdown']}")

    EVAL_RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z")
    out_path = EVAL_RAW_DIR / f"gono_{stamp}.json"
    payload = {
        "run_at": datetime.now().astimezone().isoformat(),
        "city": get_settings().city,
        "task": "predict CPCB NAQI band +6h from hour-t features",
        "horizon_hours": 6,
        "dataset": {
            "path": str(Path(args.rows).name),
            "n_rows": len(rows),
            "n_train": len(x_train),
            "n_test": len(x_test),
            "train_time_range": [train_rows[0]["time"], train_rows[-1]["time"]],
            "test_time_range": [test_rows[0]["time"], test_rows[-1]["time"]],
            "split": f"chronological, last {args.holdout:.0%} held out",
            "feature_columns": FEATURE_COLUMNS,
            "classes": BANDS,
            "test_band_support": holdout_support(test_rows),
            "absent_from_holdout": [
                b for b, v in holdout_support(test_rows).items() if not v["present"]
            ],
        },
        "keys_present": get_settings().which_keys(),
        "versions": package_versions(),
        "results": results,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nraw results -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
