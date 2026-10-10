"""Preregistered hosted rare-air experiment. Only small reports are fetched locally."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "eval/raw/forecast_risk_v1"
MANIFEST = PREFIX.with_name(PREFIX.name + "_manifest.json")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def remote_train(manifest):
    import math
    import time
    from collections import Counter
    from dataclasses import asdict
    from datetime import datetime, timedelta
    from importlib.metadata import version

    import joblib
    import lightgbm as lgb
    import numpy as np
    from sklearn.linear_model import LogisticRegression

    sys.path[:0] = ["/opt/src", "/opt/scripts"]
    import build_dataset as bd
    import forecast_risk as risk
    import run_eval as ev

    for name, sha in manifest["source_sha256"].items():
        if digest(Path("/opt") / name) != sha:
            raise ValueError("Source hash mismatch: " + name)
    directory = Path("/artifacts") / manifest.get("run_name", "forecast_risk_v1")
    directory.mkdir(parents=True, exist_ok=True)
    # Persist actual upstream responses as fixtures. Repeated execution uses the
    # exact recorded bytes; a first-fetch failure aborts instead of substituting dates.
    bd.CACHE_DIR = directory / "data/samples"
    if manifest.get("run_name") in ("forecast_risk_v2", "forecast_risk_v3", "forecast_risk_v4"):
        import shutil

        bd.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cached = {
            "forecast_risk_v2": "forecast_risk_v1",
            "forecast_risk_v3": "forecast_risk_v2",
            "forecast_risk_v4": "forecast_risk_v3",
        }[manifest["run_name"]]
        for recorded in (Path("/artifacts") / cached / "data/samples").glob("*.json"):
            target = bd.CACHE_DIR / recorded.name
            if not target.exists():
                shutil.copyfile(recorded, target)
    rows = []
    if "replay_dataset" in manifest:
        pinned = manifest["replay_dataset"]
        previous_rows = Path(pinned["rows_path"])
        if digest(previous_rows) != pinned["rows_sha256"]:
            raise ValueError("Pinned archive rows changed")
        rows = [json.loads(line) for line in previous_rows.read_text().splitlines()]
    else:
        for start, end in manifest["archive_ranges"]:
            chunk = bd.build_rows(start, end, force=False)
            bd.assert_no_leakage(chunk)
            bd.assert_feature_is_effective(chunk)
            rows.extend(asdict(row) for row in chunk)
    rows.sort(key=lambda r: r["time"])
    if len({r["time"] for r in rows}) != len(rows):
        raise ValueError("Duplicate archive timestamps")
    sources = []
    raw_air, raw_weather = {}, {}
    for path in sorted(bd.CACHE_DIR.glob("*.json")):
        payload = json.loads(path.read_text())
        hours = payload["hourly"]
        for i, stamp in enumerate(hours["time"]):
            target = raw_air if path.name.startswith("archival_aq") else raw_weather
            target[stamp] = {k: values[i] for k, values in hours.items() if k != "time"}
        sources.append({"path": str(path.relative_to(directory)), "sha256": digest(path)})
    if "replay_dataset" in manifest and sources != manifest["replay_dataset"]["source_fixtures"]:
        raise ValueError("Pinned source fixtures changed")

    def finite(value):
        return isinstance(value, (int, float)) and math.isfinite(value)

    times = [datetime.fromisoformat(row["time"]) for row in rows]
    history_ok, quality_ok = [], []
    for i, stamp in enumerate(times):
        history_ok.append(
            i >= 6 and all(times[i - j] == stamp - timedelta(hours=j) for j in range(1, 7))
        )
        stamps = [
            stamp.isoformat(timespec="minutes"),
            (stamp + timedelta(hours=6)).isoformat(timespec="minutes"),
        ]
        quality_ok.append(
            all(
                all(finite(raw_air.get(t, {}).get(k)) for k in ("pm2_5", "pm10"))
                and all(
                    finite(raw_weather.get(t, {}).get(k))
                    for k in ("temperature_2m", "apparent_temperature", "precipitation")
                )
                for t in stamps
            )
        )
    x, y = ev.to_matrix(rows)
    cleaned = [
        {k: None if isinstance(v, float) and not math.isfinite(v) else v for k, v in r.items()}
        for r in rows
    ]
    rows_path = directory / "rows.jsonl"
    rows_path.write_text(
        "".join(json.dumps(r, allow_nan=False) + "\n" for r in cleaned), encoding="utf-8"
    )
    if manifest.get("experiment") == "coverage_ablation":
        return remote_coverage(
            manifest,
            rows,
            x,
            y,
            times,
            history_ok,
            quality_ok,
            raw_air,
            directory,
            sources,
        )
    if manifest.get("experiment") == "target_feature_ablation":
        return remote_target_features(
            manifest, rows, x, y, times, history_ok, quality_ok, raw_air, directory, sources
        )
    resolved_partitions = dict(manifest["partitions"])
    if "support_protocol" in manifest:
        protocol = manifest["support_protocol"]
        resolved_partitions.update(
            risk.support_aware_partitions(
                times,
                y.tolist(),
                [h and q for h, q in zip(history_ok, quality_ok, strict=True)],
                protocol["start"],
                protocol["end"],
                min_positive=protocol["min_positive"],
                min_negative=protocol["min_negative"],
                gap_hours=manifest["label_gap_hours"],
            )
        )

    def partition(name):
        start, end = resolved_partitions[name]
        return [
            i for i in risk.window_indices(times, start, end) if history_ok[i] and quality_ok[i]
        ]

    parts = {name: partition(name) for name in resolved_partitions}
    if any(not indices for indices in parts.values()):
        raise ValueError("An archive partition is empty")
    train, dev, calibration, selection = [
        parts[k] for k in ("train", "development", "calibration", "threshold_selection")
    ]
    support = {
        name: {
            "n": len(parts[name]),
            "poor_or_worse": int(sum(y[parts[name]] >= 3)),
            "below_poor": int(sum(y[parts[name]] < 3)),
            "window": resolved_partitions[name],
        }
        for name in ("train", "development", "calibration", "threshold_selection")
    }
    write(directory / "pre_fit_support.json", support)
    import modal

    modal.Volume.from_name("baahar-training").commit()
    print("Pre-fit development support: " + json.dumps(support), flush=True)
    if len(set(y[train] >= 3)) != 2 or len(set(y[calibration] >= 3)) != 2:
        raise ValueError("Risk training/calibration lacks both classes; refusing fake calibration")
    if "support_protocol" in manifest:
        for name in ("train", "development", "calibration", "threshold_selection"):
            positive = int(sum(y[parts[name]] >= 3))
            if (
                positive < protocol["min_positive"]
                or len(parts[name]) - positive < protocol["min_negative"]
            ):
                raise ValueError("Insufficient pre-evaluation support for " + name)
    xt, medians = ev.impute(x[train])
    matrices = {name: ev.impute(x[indices], medians=medians)[0] for name, indices in parts.items()}
    model_kwargs = {
        "n_estimators": 450,
        "learning_rate": 0.04,
        "num_leaves": 28,
        "subsample": 0.85,
        "colsample_bytree": 0.85,
        "reg_alpha": 0.5,
        "reg_lambda": 1.0,
        "random_state": 0,
        "verbosity": -1,
        "n_jobs": 2,
    }

    def expanded(model, matrix):
        raw = model.predict_proba(matrix)
        probabilities = np.zeros((len(matrix), 6))
        for j, label in enumerate(model.classes_):
            probabilities[:, int(label)] = raw[:, j]
        return probabilities

    weighted_models, binary_models, trials = {}, {}, []
    baseline_dev_accuracy = None
    for weight in manifest["positive_weights"]:
        started = time.perf_counter()
        model = lgb.LGBMClassifier(**model_kwargs)
        model.fit(xt, y[train], sample_weight=np.where(y[train] >= 3, weight, 1.0))
        weighted_models[weight] = model
        probabilities = expanded(model, matrices["development"])
        predictions = probabilities.argmax(axis=1).tolist()
        metrics = risk.risk_metrics(
            y[dev].tolist(), probabilities[:, 3:].sum(axis=1).tolist(), predictions
        )
        accuracy = risk.band_accuracy(y[dev].tolist(), predictions)
        if weight == 1:
            baseline_dev_accuracy = accuracy
        eligible = (
            metrics["positive_support"] > 0
            and metrics["negative_support"] > 0
            and metrics["false_alarm_rate"] <= 0.10
            and accuracy >= baseline_dev_accuracy - 0.03
        )
        trials.append(
            {
                "kind": "weighted_band",
                "weight": weight,
                "accuracy": accuracy,
                "risk": metrics,
                "eligible": eligible,
                "fit_seconds": time.perf_counter() - started,
            }
        )
        binary = lgb.LGBMClassifier(**model_kwargs)
        binary.fit(
            xt, (y[train] >= 3).astype(int), sample_weight=np.where(y[train] >= 3, weight, 1.0)
        )
        binary_models[weight] = binary
        probability = binary.predict_proba(matrices["development"])[:, 1].tolist()
        choice, threshold_trials = risk.choose_threshold(
            y[dev].tolist(),
            [0] * len(dev),
            probability,
            manifest["thresholds"],
            baseline_accuracy=0,
            max_accuracy_loss=1,
        )
        trials.append(
            {
                "kind": "binary_risk",
                "weight": weight,
                "selected": choice,
                "threshold_trials": threshold_trials,
            }
        )
    band_eligible = [t for t in trials if t["kind"] == "weighted_band" and t["eligible"]]
    selected_band = (
        max(band_eligible, key=lambda t: (t["risk"]["recall"], t["accuracy"], -t["weight"]))
        if band_eligible
        else next(t for t in trials if t["kind"] == "weighted_band" and t["weight"] == 1)
    )
    risk_eligible = [t for t in trials if t["kind"] == "binary_risk" and t["selected"] is not None]
    if not risk_eligible:
        raise ValueError("No binary risk candidate meets development false-alarm constraint")
    selected_risk = max(
        risk_eligible,
        key=lambda t: (
            t["selected"]["metrics"]["recall"],
            -t["selected"]["metrics"]["false_alarm_rate"],
            -t["weight"],
        ),
    )
    band_model, risk_model = (
        weighted_models[selected_band["weight"]],
        binary_models[selected_risk["weight"]],
    )
    calibrator = LogisticRegression(random_state=0)
    calibrator.fit(
        risk.logit(risk_model.predict_proba(matrices["calibration"])[:, 1].tolist()),
        (y[calibration] >= 3).astype(int),
    )
    band_selection = expanded(band_model, matrices["threshold_selection"]).argmax(axis=1).tolist()
    selected_probability = calibrator.predict_proba(
        risk.logit(risk_model.predict_proba(matrices["threshold_selection"])[:, 1].tolist())
    )[:, 1].tolist()
    base_selection = (
        expanded(weighted_models[1], matrices["threshold_selection"]).argmax(axis=1).tolist()
    )
    choice, threshold_trials = risk.choose_threshold(
        y[selection].tolist(),
        band_selection,
        selected_probability,
        manifest["thresholds"],
        risk.band_accuracy(y[selection].tolist(), base_selection),
    )
    threshold = choice["threshold"] if choice else None
    ev.save_ensemble_model = lambda *args, **kwargs: "NOT_SAVED_RESEARCH"
    results = []
    for name in ("locked_pollution", "locked_other_seasons"):
        indices = parts[name]
        labels = y[indices].tolist()
        matrix = matrices[name]
        probabilities = expanded(band_model, matrix)
        base_probabilities = expanded(weighted_models[1], matrix)
        calibrated = calibrator.predict_proba(
            risk.logit(risk_model.predict_proba(matrix)[:, 1].tolist())
        )[:, 1].tolist()
        weighted_pred = probabilities.argmax(axis=1).tolist()
        hybrid_pred = (
            risk.apply_risk_floor(weighted_pred, calibrated, threshold)
            if threshold is not None
            else weighted_pred
        )
        ensemble_pred, _, _ = ev.fit_predict("ensemble", xt, y[train], matrix, medians, seed=0)
        predictions = {
            "instantaneous_persistence": [
                risk.instantaneous_persistence(
                    bd.compute_naqi(
                        {bd.AQ_VAR_TO_KEY[k]: raw_air[rows[i]["time"]].get(k) for k in bd.AQ_VARS}
                    ).index
                )
                for i in indices
            ],
            "conservative_persistence_diagnostic": [
                ev.BAND_ORDINALS[rows[i]["band"]] for i in indices
            ],
            "lightgbm_baseline": base_probabilities.argmax(axis=1).tolist(),
            "ensemble_baseline": ensemble_pred,
            "weighted_lightgbm": weighted_pred,
            "weighted_plus_risk": hybrid_pred,
        }
        model_results = {}
        for model_name, pred in predictions.items():
            risk_p = (
                calibrated
                if model_name == "weighted_plus_risk"
                else (
                    probabilities[:, 3:].sum(axis=1).tolist()
                    if model_name == "weighted_lightgbm"
                    else base_probabilities[:, 3:].sum(axis=1).tolist()
                    if model_name == "lightgbm_baseline"
                    else [float(v >= 3) for v in pred]
                )
            )
            cm = ev.confusion(labels, pred)
            weather = []
            for i in indices:
                target_stamp = (times[i] + timedelta(hours=6)).isoformat(timespec="minutes")
                recorded = raw_weather[target_stamp]
                weather.append(
                    {
                        "precip_mm": recorded["precipitation"],
                        "precip_prob": recorded.get("precipitation_probability"),
                        "apparent_c": recorded["apparent_temperature"],
                    }
                )
            policy = ev.safety_metrics(labels, pred, weather)
            policy["_policy_approximation"] = (
                "Oracle recorded target-hour weather, not a deployed weather forecast"
            )
            model_results[model_name] = {
                "classification": ev.prf(cm),
                "confusion": cm,
                "risk": risk.risk_metrics(labels, risk_p, pred),
                "policy": policy,
                "predictions": pred,
                "risk_probabilities": risk_p,
            }
        results.append(
            {
                "partition": name,
                "n": len(indices),
                "times": [rows[i]["time"] for i in indices],
                "labels": labels,
                "models": model_results,
                "training_unsupported_classes": risk.unsupported_classes(
                    dict(Counter(ev.BANDS[int(v)] for v in y[train])),
                    dict(Counter(ev.BANDS[int(v)] for v in y[indices])),
                ),
            }
        )
    bundle = {
        "forecast_target_contract": risk.FORECAST_TARGET_CONTRACT,
        "training_class_support": dict(Counter(ev.BANDS[int(v)] for v in y[train])),
        "band_model": band_model,
        "risk_model": risk_model,
        "calibrator": calibrator,
        "risk_threshold": threshold,
        "medians": medians,
        "feature_order": ev.FEATURE_COLUMNS,
        "manifest": manifest,
        "rows_sha256": digest(rows_path),
        "disposition": "RESEARCH_ONLY",
    }
    joblib.dump(bundle, directory / "candidate.joblib")
    import modal

    modal.Volume.from_name("baahar-training").commit()
    return {
        "manifest": manifest,
        "forecast_target_contract": risk.FORECAST_TARGET_CONTRACT,
        "dataset": {
            "rows_sha256": digest(rows_path),
            "row_count": len(rows),
            "excluded_history_n": sum(not v for v in history_ok),
            "excluded_quality_n": sum(not v for v in quality_ok),
            "source_fixtures": sources,
            "source_kind": "CAMS archived model output and ERA5 reanalysis; not station observations",
        },
        "partition_support": {
            name: {
                "n": len(idx),
                "bands": dict(Counter(ev.BANDS[int(y[i])] for i in idx)),
                "first_time": rows[idx[0]]["time"],
                "last_time": rows[idx[-1]]["time"],
            }
            for name, idx in parts.items()
        },
        "resolved_partitions": resolved_partitions,
        "selection": {
            "band_weight": selected_band["weight"],
            "band_development_gate_passed": selected_band["eligible"],
            "binary_weight": selected_risk["weight"],
            "threshold": threshold,
            "risk_floor_enabled": threshold is not None,
            "development_trials": trials,
            "threshold_selection_trials": threshold_trials,
        },
        "versions": {n: version(n) for n in ("numpy", "scikit-learn", "lightgbm")},
        "results": results,
        "remote_candidate_path": str(directory / "candidate.joblib"),
        "disposition": "RESEARCH_ONLY_NO_PROMOTION",
    }


def remote_coverage(
    manifest, rows, x, y, times, history_ok, quality_ok, raw_air, directory, sources
):
    """Frozen coverage ablation: no test-based model or threshold selection."""
    from collections import Counter
    from importlib.metadata import version

    import build_dataset as bd
    import forecast_risk as risk
    import joblib
    import lightgbm as lgb
    import modal
    import numpy as np
    import run_eval as ev

    parts = {
        name: [i for i in risk.window_indices(times, *window) if history_ok[i] and quality_ok[i]]
        for name, window in manifest["partitions"].items()
    }
    if any(not ids for ids in parts.values()):
        raise ValueError("An archive partition is empty")

    def support(ids):
        return {
            "n": len(ids),
            "bands": dict(Counter(ev.BANDS[int(y[i])] for i in ids)),
            "first_time": rows[ids[0]]["time"],
            "last_time": rows[ids[-1]]["time"],
            "poor_or_worse_episodes": risk.episode_support([times[i] for i in ids], y[ids]),
            "severe_or_worse_episodes": risk.episode_support([times[i] for i in ids], y[ids], 4),
        }

    supports = {name: support(ids) for name, ids in parts.items()}
    write(directory / "pre_fit_support.json", supports)
    modal.Volume.from_name("baahar-training").commit()
    expanded = supports["expanded_train"]["bands"]
    if expanded.get("severe", 0) < manifest["minimum_severe_train_hours"]:
        raise ValueError("Insufficient pre-evaluation support for severe training")
    ev.save_ensemble_model = lambda *args, **kwargs: "NOT_SAVED_RESEARCH"
    fitted = {}
    for train_name in ("historical_train", "expanded_train"):
        ids = parts[train_name]
        xt, medians = ev.impute(x[ids])
        for weighting in ("ordinary", "risk_weighted"):
            model = lgb.LGBMClassifier(**manifest["model_parameters"])
            weights = (
                np.array(manifest["class_weights"])[y[ids]]
                if weighting == "risk_weighted"
                else None
            )
            model.fit(xt, y[ids], sample_weight=weights)
            fitted[train_name + "_" + weighting] = (model, medians, train_name)
    periods = []
    for name in ("diagnostic_pollution", "diagnostic_other_seasons"):
        ids = parts[name]
        labels = y[ids].tolist()
        predictions, probabilities, training_names = {}, {}, {}
        for model_name, (model, medians, train_name) in fitted.items():
            matrix = ev.impute(x[ids], medians=medians)[0]
            raw = model.predict_proba(matrix)
            p = np.zeros((len(ids), 6))
            for j, label in enumerate(model.classes_):
                p[:, int(label)] = raw[:, j]
            predictions[model_name] = p.argmax(axis=1).tolist()
            probabilities[model_name] = p
            training_names[model_name] = train_name
        train_ids = parts["expanded_train"]
        xt, medians = ev.impute(x[train_ids])
        pred, _, _ = ev.fit_predict(
            "ensemble", xt, y[train_ids], ev.impute(x[ids], medians)[0], medians, seed=0
        )
        predictions["expanded_ensemble"] = pred
        training_names["expanded_ensemble"] = "expanded_train"
        predictions["instantaneous_persistence"] = [
            risk.instantaneous_persistence(
                bd.compute_naqi(
                    {bd.AQ_VAR_TO_KEY[k]: raw_air[rows[i]["time"]].get(k) for k in bd.AQ_VARS}
                ).index
            )
            for i in ids
        ]
        predictions["conservative_persistence_diagnostic"] = [
            ev.BAND_ORDINALS[rows[i]["band"]] for i in ids
        ]
        models = {}
        for model_name, pred in predictions.items():
            p = probabilities.get(model_name)
            poor_p = (
                p[:, 3:].sum(axis=1).tolist() if p is not None else [float(v >= 3) for v in pred]
            )
            severe_p = (
                p[:, 4:].sum(axis=1).tolist() if p is not None else [float(v >= 4) for v in pred]
            )
            severe_metrics = risk.risk_metrics(
                [3 if v >= 4 else 0 for v in labels],
                severe_p,
                [3 if v >= 4 else 0 for v in pred],
            )
            models[model_name] = {
                "classification": ev.prf(ev.confusion(labels, pred)),
                "risk": risk.risk_metrics(labels, poor_p, pred),
                "severe_or_worse": severe_metrics,
                "predictions": pred,
                "risk_probabilities": poor_p,
                "severe_probabilities": severe_p,
                "training_partition": training_names.get(model_name),
                "training_unsupported_classes": risk.unsupported_classes(
                    supports[training_names[model_name]]["bands"], supports[name]["bands"]
                )
                if model_name in training_names
                else {},
                "probability_note": "uncalibrated class probabilities"
                if p is not None
                else "binary band decisions, not calibrated probabilities",
            }
        periods.append(
            {
                "partition": name,
                "n": len(ids),
                "times": [rows[i]["time"] for i in ids],
                "labels": labels,
                "models": models,
            }
        )
    joblib.dump(
        {
            "models": fitted,
            "manifest": manifest,
            "forecast_target_contract": risk.FORECAST_TARGET_CONTRACT,
            "feature_order": ev.FEATURE_COLUMNS,
            "training_support": supports,
            "disposition": "RESEARCH_ONLY_NO_PROMOTION",
        },
        directory / "coverage_candidates.joblib",
    )
    modal.Volume.from_name("baahar-training").commit()
    return {
        "manifest": manifest,
        "forecast_target_contract": risk.FORECAST_TARGET_CONTRACT,
        "dataset": {
            "rows_sha256": digest(directory / "rows.jsonl"),
            "row_count": len(rows),
            "excluded_history_n": sum(not v for v in history_ok),
            "excluded_quality_n": sum(not v for v in quality_ok),
            "source_fixtures": sources,
            "source_kind": "CAMS/ERA5 modelled archive",
        },
        "partition_support": supports,
        "resolved_partitions": manifest["partitions"],
        "selection": {
            "band_weight": "fixed [1,1,1,4,16,16]",
            "binary_weight": None,
            "threshold": None,
            "risk_floor_enabled": False,
            "method": "none; fixed configurations",
        },
        "versions": {n: version(n) for n in ("numpy", "lightgbm", "scikit-learn")},
        "results": periods,
        "disposition": "RESEARCH_ONLY_NO_PROMOTION",
    }


def remote_target_features(
    manifest, rows, x, y, times, history_ok, quality_ok, raw_air, directory, sources
):
    """Fixed 2 x 3 feature/target experiment on exactly replayed v3 data."""
    from collections import Counter
    from datetime import timedelta
    from importlib.metadata import version

    import build_dataset as bd
    import forecast_risk as risk
    import joblib
    import lightgbm as lgb
    import modal
    import numpy as np
    import run_eval as ev

    target = np.array([row["target_naqi"] for row in rows], dtype=float)
    if not np.isfinite(target).all():
        raise ValueError("Missing continuous forecast targets")
    timing_checked = 0
    for i, stamp in enumerate(times):
        future = (stamp + timedelta(hours=6)).isoformat(timespec="minutes")
        if future not in raw_air:
            raise ValueError("Missing exact six-hour target timestamp: " + future)
        actual = bd.compute_naqi({bd.AQ_VAR_TO_KEY[k]: raw_air[future].get(k) for k in bd.AQ_VARS})
        if actual.band is None or ev.BAND_ORDINALS[actual.band.value] != int(y[i]):
            raise ValueError("Target-band timestamp/source mismatch")
        if actual.index is None or round(actual.index, 2) != float(target[i]):
            raise ValueError("Numeric target timestamp/source mismatch")
        timing_checked += 1
    matrices = {
        "base": x,
        "instant_history": np.column_stack((x, risk.instantaneous_history_features(rows))),
    }
    orders = {
        "base": ev.FEATURE_COLUMNS,
        "instant_history": ev.FEATURE_COLUMNS + list(risk.INSTANT_HISTORY_COLUMNS),
    }
    parts = {
        name: [i for i in risk.window_indices(times, *window) if history_ok[i] and quality_ok[i]]
        for name, window in manifest["partitions"].items()
    }
    if any(not ids for ids in parts.values()):
        raise ValueError("An archive partition is empty")
    supports = {
        name: {
            "n": len(ids),
            "bands": dict(Counter(ev.BANDS[int(y[i])] for i in ids)),
            "poor_or_worse_episodes": risk.episode_support([times[i] for i in ids], y[ids]),
            "severe_or_worse_episodes": risk.episode_support([times[i] for i in ids], y[ids], 4),
        }
        for name, ids in parts.items()
    }
    train = parts["expanded_train"]
    if (
        supports["expanded_train"]["bands"].get("severe", 0)
        < manifest["minimum_severe_train_hours"]
    ):
        raise ValueError("Insufficient pre-evaluation support for severe training")
    write(directory / "pre_fit_support.json", supports)
    modal.Volume.from_name("baahar-training").commit()
    fitted = {}
    for feature_name, matrix in matrices.items():
        xt, medians = ev.impute(matrix[train])
        classifier = lgb.LGBMClassifier(**manifest["model_parameters"])
        classifier.fit(xt, y[train], sample_weight=np.array(manifest["class_weights"])[y[train]])
        fitted[feature_name + "_classifier"] = (classifier, medians, feature_name, None)
        for alpha in manifest["quantiles"]:
            model = lgb.LGBMRegressor(
                objective="quantile", alpha=alpha, **manifest["model_parameters"]
            )
            model.fit(xt, target[train])
            fitted[feature_name + "_quantile_" + str(alpha)] = (model, medians, feature_name, alpha)
    periods = []
    for name, ids in parts.items():
        if name == "expanded_train":
            continue
        labels, actual = y[ids].tolist(), target[ids].tolist()
        models = {}
        current = [risk.instantaneous_persistence(rows[i]["naqi_instant"]) for i in ids]
        period_times = [times[i] for i in ids]
        for model_name, (model, medians, feature_name, alpha) in fitted.items():
            matrix = ev.impute(matrices[feature_name][ids], medians)[0]
            if alpha is None:
                p = np.zeros((len(ids), 6))
                raw = model.predict_proba(matrix)
                for j, label in enumerate(model.classes_):
                    p[:, int(label)] = raw[:, j]
                pred = p.argmax(axis=1).tolist()
                numeric, numeric_metrics = None, None
                poor_p, severe_p = p[:, 3:].sum(axis=1).tolist(), p[:, 4:].sum(axis=1).tolist()
            else:
                numeric = model.predict(matrix).tolist()
                pred = [risk.instantaneous_persistence(v) for v in numeric]
                numeric_metrics = risk.numeric_forecast_metrics(actual, numeric, alpha)
                poor_p, severe_p = [float(v >= 3) for v in pred], [float(v >= 4) for v in pred]
            poor = risk.risk_metrics(labels, poor_p, pred)
            severe = risk.risk_metrics(
                [3 if v >= 4 else 0 for v in labels], severe_p, [3 if v >= 4 else 0 for v in pred]
            )
            if alpha is not None:
                for scores in (poor, severe):
                    for key in ("brier", "ece_10_bins", "reliability_bins"):
                        scores[key] = None
            onset_ids = [
                j for j, (t, c) in enumerate(zip(labels, current, strict=True)) if t >= 4 and c < 4
            ]
            models[model_name] = {
                "classification": ev.prf(ev.confusion(labels, pred)),
                "risk": poor,
                "severe_or_worse": severe,
                "numeric": numeric_metrics,
                "numeric_predictions": numeric,
                "predictions": pred,
                "poor_probabilities": poor_p if alpha is None else None,
                "severe_probabilities": severe_p if alpha is None else None,
                "poor_episodes": risk.event_detection_metrics(period_times, labels, pred, 3),
                "severe_episodes": risk.event_detection_metrics(period_times, labels, pred, 4),
                "severe_onset": {
                    "n": len(onset_ids),
                    "misses": sum(pred[j] < 4 for j in onset_ids),
                },
                "feature_set": feature_name,
                "feature_order": orders[feature_name],
                "probability_note": "uncalibrated class probabilities"
                if alpha is None
                else "quantile forecast; no risk probability or Brier/ECE",
            }
        baseline_sha = hashlib.sha256(
            json.dumps(models["base_classifier"]["predictions"]).encode()
        ).hexdigest()
        periods.append(
            {
                "partition": name,
                "n": len(ids),
                "times": [rows[i]["time"] for i in ids],
                "labels": labels,
                "numeric_targets": actual,
                "current_instantaneous_bands": current,
                "rounded_numeric_label_disagreements": sum(
                    risk.instantaneous_persistence(t) != y
                    for t, y in zip(actual, labels, strict=True)
                ),
                "v3_reference_prediction_match": baseline_sha
                == manifest["reference_prediction_sha256"].get(name)
                if name in manifest["reference_prediction_sha256"]
                else None,
                "models": models,
            }
        )
    joblib.dump(
        {
            "models": fitted,
            "feature_orders": orders,
            "manifest": manifest,
            "target_contract": risk.FORECAST_TARGET_CONTRACT,
            "disposition": "RESEARCH_ONLY",
        },
        directory / "target_feature_candidates.joblib",
    )
    modal.Volume.from_name("baahar-training").commit()
    return {
        "manifest": manifest,
        "dataset": {"rows_sha256": digest(directory / "rows.jsonl"), "source_fixtures": sources},
        "source_target_timestamp_checks": timing_checked,
        "feature_orders": orders,
        "partition_support": supports,
        "resolved_partitions": manifest["partitions"],
        "forecast_target_contract": risk.FORECAST_TARGET_CONTRACT,
        "versions": {n: version(n) for n in ("numpy", "lightgbm", "scikit-learn")},
        "results": periods,
        "disposition": "RESEARCH_ONLY_NO_PROMOTION",
    }


def report(results):
    if results["manifest"].get("experiment") == "target_feature_ablation":
        report_target_features(results)
        return
    lines = [
        "# Rare-air forecast experiment",
        "",
        (
            "Research-only coverage ablation on consumed archive diagnostics; no station, prospective or medical-safety claim."
            if results["manifest"].get("experiment") == "coverage_ablation"
            else "Research-only, no automatic promotion. New modelled archive periods; not station-accuracy or medical-safety evidence."
        ),
        "",
        "| Period | Model | N | Accuracy | Macro-F1 | Poor+ misses/support | Recall | False-alarm rate | Precision | Brier | ECE |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for period in results["results"]:
        for name, model in period["models"].items():
            c, r = model["classification"], model["risk"]
            lines.append(
                f"| {period['partition']} | {name} | {period['n']} | {c['accuracy']} | {c['macro_f1']} | {r['misses']}/{r['positive_support']} | {r['recall']} | {r['false_alarm_rate']} | {r['precision']} | {r['brier']:.5f} | {r['ece_10_bins']:.5f} |"
            )
    if results["manifest"].get("experiment") == "coverage_ablation":
        lines += [
            "",
            "## Severe-or-worse diagnostics",
            "",
            "| Period | Model | Misses/support | Recall | False-alarm rate | Precision | Brier | ECE |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
        for period in results["results"]:
            for name, model in period["models"].items():
                r = model["severe_or_worse"]
                lines.append(
                    f"| {period['partition']} | {name} | {r['misses']}/{r['positive_support']} | {r['recall']} | {r['false_alarm_rate']} | {r['precision']} | {r['brier']:.5f} | {r['ece_10_bins']:.5f} |"
                )
    lines += [
        "",
        (
            "Coverage ablation uses fixed configurations without calibration or threshold selection. Persistence/ensemble Brier and ECE use binary decisions; LightGBM uses uncalibrated class probabilities. Periods are consumed diagnostics; no policy or deployment weather accuracy is assessed."
            if results["manifest"].get("experiment") == "coverage_ablation"
            else "Brier/ECE for persistence and ensemble use binary band decisions, not calibrated probabilities. Instantaneous persistence matches the target basis; conservative persistence is a differently defined diagnostic. Target-hour policy weather is oracle recorded data. Calibration and threshold selection precede both locked periods."
        ),
        "",
        "## Selection and support",
        "",
        "```json",
        json.dumps(
            {
                "selection": {
                    k: results["selection"][k]
                    for k in ("band_weight", "binary_weight", "threshold", "risk_floor_enabled")
                },
                "partition_support": results["partition_support"],
                "forecast_target_contract": results.get(
                    "forecast_target_contract",
                    "Historical artifact predates explicit contract; persistence used current effective band",
                ),
                "training_unsupported_classes": {
                    p["partition"]: p.get("training_unsupported_classes", {})
                    for p in results["results"]
                },
            },
            indent=2,
        ),
        "```",
    ]
    PREFIX.with_name(PREFIX.name + "_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def report_target_features(results):
    lines = [
        "# V4 fixed target and feature experiment",
        "",
        "Consumed modeled archive diagnostics; no calibration, threshold tuning or automatic model adoption.",
        "",
        "| Period | Candidate | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ FAR | Severe+ misses/support | Severe+ FAR | MAE | Quantile coverage |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for p in results["results"]:
        for name, m in p["models"].items():
            c, r, s, n = m["classification"], m["risk"], m["severe_or_worse"], m["numeric"]
            lines.append(
                f"| {p['partition']} | {name} | {c['accuracy']} | {c['macro_f1']} | {r['misses']}/{r['positive_support']} | {r['false_alarm_rate']} | {s['misses']}/{s['positive_support']} | {s['false_alarm_rate']} | {n['mae'] if n else 'N/A'} | {n['empirical_quantile_coverage'] if n else 'N/A'} |"
            )
    lines += [
        "",
        "Classifier Brier/ECE use uncalibrated probabilities. Quantile heads do not supply risk probabilities; their Brier/ECE are null. Empirical quantile coverage does not establish calibrated safety. Numeric target labels are preserved, including any rounding discrepancies. Raw output includes feature orders, source checks, episodes, onset misses, numeric predictions, RMSE/pinball loss and all risk metrics. Development reporting does not select candidates.",
    ]
    PREFIX.with_name(PREFIX.name + "_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main():
    global PREFIX, MANIFEST
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--version", choices=("v1", "v2", "v3", "v4"), default="v1")
    args = parser.parse_args()
    PREFIX = ROOT / ("eval/raw/forecast_risk_" + args.version)
    MANIFEST = PREFIX.with_name(PREFIX.name + "_manifest.json")
    if args.submit == args.fetch:
        parser.error("Choose --submit or --fetch")
    import modal

    if args.fetch:
        manifest = json.loads(MANIFEST.read_text())
        if manifest["status"] == "COMPLETED":
            print("Already completed; not refetching")
            return
        if manifest["status"] == "FAILED":
            print("Hosted run failed; see " + PREFIX.name + "_monitor_error.json. No resubmission.")
            return
        try:
            result = modal.FunctionCall.from_id(manifest["call_id"]).get(timeout=5)
        except (TimeoutError, modal.exception.TimeoutError):
            print("Rare-air training/evaluation still running")
            return
        except ValueError as exc:
            # A known terminal data gate is different from a transient fetch error.
            reason = "Risk training/calibration lacks both classes; refusing fake calibration"
            if str(exc) != reason and not str(exc).startswith(
                (
                    "Insufficient pre-evaluation support for ",
                    "No binary risk candidate meets development false-alarm constraint",
                    "An archive partition is empty",
                )
            ):
                raise
            reason = str(exc)
            from datetime import datetime

            observed = datetime.now(UTC).isoformat()
            error = PREFIX.with_name(PREFIX.name + "_monitor_error.json")
            if not error.exists():
                write(
                    error,
                    {
                        "step": "remote_class_support_gate",
                        "consecutive_count": 1,
                        "terminal": True,
                        "call_id": manifest["call_id"],
                        "observed_at": observed,
                        "reason": reason,
                    },
                )
            manifest.update(status="FAILED", failure_reason=reason, failure_observed_at=observed)
            write(MANIFEST, manifest)
            print("Hosted run FAILED at class-support gate; no model metrics or resubmission.")
            return
        output = PREFIX.with_name(PREFIX.name + "_results.json")
        if output.exists():
            raise ValueError("Refusing to overwrite a fetched result")
        write(output, result)
        report(result)
        manifest.update(status="COMPLETED", results=str(output.relative_to(ROOT)))
        write(MANIFEST, manifest)
        print("Fetched results and wrote " + PREFIX.name + "_report.md")
        return
    if MANIFEST.exists():
        raise ValueError("Refusing duplicate submission")
    manifest = {
        "status": "PREREGISTERED",
        "archive_ranges": [["2024-01-01", "2024-12-31"], ["2025-01-01", "2025-10-31"]],
        "partitions": {
            "train": ["2024-01-01", "2024-11-01"],
            "development": ["2024-11-01", "2025-01-01"],
            "calibration": ["2025-01-01", "2025-01-16"],
            "threshold_selection": ["2025-01-16", "2025-02-01"],
            "locked_pollution": ["2025-02-01", "2025-05-01"],
            "locked_other_seasons": ["2025-05-01", "2025-11-01"],
        },
        "positive_weights": [1, 2, 4, 8],
        "thresholds": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9],
        "max_false_alarm": 0.10,
        "max_accuracy_loss": 0.03,
        "label_gap_hours": 6,
        "seed": 0,
        "timeout_seconds": 3600,
        "compute_ceiling_estimate_usd": 3600 * (2 * 0.0000131 + 8 * 0.00000222),
        "limitations": "Configurations inspired by consumed later archive; temporal holdouts are newly acquired historical periods, not prospective independent station evidence. No test-label selection or automatic promotion.",
    }
    if args.version == "v2":
        manifest.update(
            run_name="forecast_risk_v2",
            supersedes="eval/raw/forecast_risk_v1_manifest.json",
            archive_ranges=[
                ["2023-01-01", "2023-12-31"],
                ["2024-01-01", "2024-12-31"],
                ["2025-01-01", "2025-10-31"],
            ],
            partitions={
                "train": ["2023-01-01", "2024-01-01"],
                "locked_pollution": ["2025-02-01", "2025-05-01"],
                "locked_other_seasons": ["2025-05-01", "2025-11-01"],
            },
            support_protocol={
                "start": "2024-01-01",
                "end": "2025-02-01",
                "min_positive": 20,
                "min_negative": 200,
                "cut_rule": "earliest daily end with minimum usable support, development then calibration; remainder threshold selection; abort if any phase lacks support",
                "limitation": "Label-adaptive development windows; hourly supports are correlated, not independent pollution episodes. No locked-label access for boundary selection.",
            },
        )
    if args.version == "v3":
        manifest.update(
            run_name="forecast_risk_v3",
            experiment="coverage_ablation",
            supersedes="eval/raw/forecast_risk_v2_manifest.json",
            archive_ranges=[
                ["2023-01-01", "2023-12-31"],
                ["2024-01-01", "2024-12-31"],
                ["2025-01-01", "2025-10-31"],
                ["2025-11-01", "2025-12-31"],
                ["2026-01-01", "2026-09-30"],
            ],
            partitions={
                "historical_train": ["2023-01-01", "2024-01-01"],
                "expanded_train": ["2023-01-01", "2025-06-01"],
                "diagnostic_pollution": ["2026-02-01", "2026-05-01"],
                "diagnostic_other_seasons": ["2026-05-01", "2026-10-01"],
            },
            class_weights=[1, 1, 1, 4, 16, 16],
            minimum_severe_train_hours=20,
            model_parameters={
                "n_estimators": 450,
                "learning_rate": 0.04,
                "num_leaves": 28,
                "subsample": 0.85,
                "colsample_bytree": 0.85,
                "reg_alpha": 0.5,
                "reg_lambda": 1.0,
                "random_state": 0,
                "verbosity": -1,
                "n_jobs": 2,
            },
            limitations="Consumed archive diagnostics. V2 evaluated 2025 periods now included in training; 2026 archive and windows have informed prior research. No pristine holdout, calibration or automatic promotion. Fixed configurations; hourly severe support is correlated, episode counts must be reported.",
        )
    if args.version == "v4":
        old = json.loads((ROOT / "eval/raw/forecast_risk_v3_results.json").read_text())
        manifest.update(
            run_name="forecast_risk_v4",
            experiment="target_feature_ablation",
            archive_ranges=old["manifest"]["archive_ranges"],
            supersedes="eval/raw/forecast_risk_v3_manifest.json",
            replay_dataset={
                "rows_path": "/artifacts/forecast_risk_v3/rows.jsonl",
                "rows_sha256": old["dataset"]["rows_sha256"],
                "source_fixtures": old["dataset"]["source_fixtures"],
            },
            partitions={
                "expanded_train": ["2023-01-01", "2025-06-01"],
                "development": ["2025-06-01", "2026-02-01"],
                "diagnostic_pollution": ["2026-02-01", "2026-05-01"],
                "diagnostic_other_seasons": ["2026-05-01", "2026-10-01"],
            },
            model_parameters=old["manifest"]["model_parameters"],
            class_weights=old["manifest"]["class_weights"],
            minimum_severe_train_hours=20,
            quantiles=[0.5, 0.9],
            feature_ablation="28 original vs 28+7 timestamp-aligned instantaneous history columns",
            reference_prediction_sha256={
                p["partition"]: hashlib.sha256(
                    json.dumps(p["models"]["expanded_train_risk_weighted"]["predictions"]).encode()
                ).hexdigest()
                for p in old["results"]
            },
            limitations="Research-informed fixed 2x3 factorial ablation on exact consumed v3 archive. All settings fixed; development and diagnostics do not select candidates. Six severe training episodes only. No probability calibration for regressors, no pristine holdout, deployment or medical safety claim.",
        )
        for unused in ("positive_weights", "thresholds", "max_false_alarm", "max_accuracy_loss"):
            manifest.pop(unused, None)
    files = list((ROOT / "src/baahar").glob("*.py")) + [
        ROOT / "scripts" / name
        for name in (
            "run_eval.py",
            "build_dataset.py",
            "forecast_risk.py",
            "train_forecast_risk_modal.py",
        )
    ]
    manifest["source_sha256"] = {p.relative_to(ROOT).as_posix(): digest(p) for p in files}
    image = (
        modal.Image.debian_slim(python_version="3.12")
        .pip_install(
            "numpy==2.2.6",
            "scikit-learn==1.6.1",
            "lightgbm==4.6.0",
            "httpx==0.28.1",
            "pydantic==2.11.7",
            "python-dotenv==1.1.1",
        )
        .env({"OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2"})
    )
    for p in files:
        image = image.add_local_file(str(p), "/opt/" + p.relative_to(ROOT).as_posix())
    write(MANIFEST, manifest)
    app = modal.App("baahar-rare-air-forecast-" + args.version, image=image)
    function = app.function(
        cpu=2,
        memory=8192,
        timeout=3600,
        retries=0,
        max_containers=1,
        volumes={"/artifacts": modal.Volume.from_name("baahar-training")},
    )(remote_train)
    with app.run(detach=True):
        call = function.spawn(manifest)
        manifest.update(status="SUBMITTED", call_id=call.object_id, app_id=app.app_id)
        write(MANIFEST, manifest)
        print(
            json.dumps(
                {
                    "call_id": call.object_id,
                    "url": "https://modal.com/apps/vedantmahajan271/main/" + app.app_id,
                }
            )
        )


if __name__ == "__main__":
    main()
