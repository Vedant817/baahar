"""Bounded, source-pinned Modal research on the already consumed v3 archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GASES = ("nitrogen_dioxide", "ozone", "sulphur_dioxide", "carbon_monoxide")
GAS_COLUMNS = tuple(
    gas + "_" + suffix
    for gas in GASES
    for suffix in ("now", "lag1", "lag3", "lag6", "diff1", "diff3", "diff6")
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def prediction_digest(predictions):
    return hashlib.sha256(json.dumps(predictions).encode()).hexdigest()


def gas_history_features(times, raw_air):
    """Exact timestamp lookup; missing values stay missing and no future is read."""

    def number(stamp, gas):
        value = raw_air.get(stamp.isoformat(timespec="minutes"), {}).get(gas)
        return (
            float(value) if isinstance(value, (int, float)) and math.isfinite(value) else math.nan
        )

    features = []
    for stamp in times:
        vector = []
        for gas in GASES:
            now = number(stamp, gas)
            lag = [number(stamp - timedelta(hours=h), gas) for h in (1, 3, 6)]
            vector.extend((now, *lag, *(now - v for v in lag)))
        features.append(vector)
    return features


def quantile_poor_floor(predictions, numeric):
    import forecast_risk as risk

    return [
        max(int(pred), 3) if risk.instantaneous_persistence(value) >= 3 else int(pred)
        for pred, value in zip(predictions, numeric, strict=True)
    ]


def remote_run(manifest):
    """Replay the existing Volume without fetching or replacing archive fixtures."""
    from collections import Counter
    from importlib.metadata import version

    import joblib
    import lightgbm as lgb
    import modal
    import numpy as np

    sys.path[:0] = ["/opt/src", "/opt/scripts"]
    import build_dataset as bd
    import forecast_risk as risk
    import run_eval as ev

    if any(gas not in bd.AQ_VARS or gas not in bd.AQ_VAR_TO_KEY for gas in GASES):
        raise ValueError("Gas feature contract absent from recorded AQ source contract")
    for name, sha in manifest["source_sha256"].items():
        if digest(Path("/opt") / name) != sha:
            raise ValueError("Pinned source mismatch: " + name)
    replay = Path("/artifacts/forecast_risk_v3")
    if digest(replay / "rows.jsonl") != manifest["dataset"]["rows_sha256"]:
        raise ValueError("Pinned archive rows mismatch")
    raw_air, raw_weather = {}, {}
    for source in manifest["dataset"]["source_fixtures"]:
        path = replay / source["path"]
        if digest(path) != source["sha256"]:
            raise ValueError("Pinned fixture mismatch: " + source["path"])
        hourly = json.loads(path.read_text())["hourly"]
        lookup = raw_air if path.name.startswith("archival_aq") else raw_weather
        for j, stamp in enumerate(hourly["time"]):
            lookup[stamp] = {k: values[j] for k, values in hourly.items() if k != "time"}
    rows = ev.load_rows(replay / "rows.jsonl")
    times = [datetime.fromisoformat(row["time"]) for row in rows]
    if len(set(times)) != len(times):
        raise ValueError("Duplicate archive timestamps")
    usable = []
    for i, stamp in enumerate(times):
        history = i >= 6 and all(times[i - h] == stamp - timedelta(hours=h) for h in range(1, 7))
        stamps = [
            stamp.isoformat(timespec="minutes"),
            (stamp + timedelta(hours=6)).isoformat(timespec="minutes"),
        ]
        quality = all(
            all(
                isinstance(raw_air.get(t, {}).get(k), (int, float)) and math.isfinite(raw_air[t][k])
                for k in ("pm2_5", "pm10")
            )
            and all(
                isinstance(raw_weather.get(t, {}).get(k), (int, float))
                and math.isfinite(raw_weather[t][k])
                for k in ("temperature_2m", "apparent_temperature", "precipitation")
            )
            for t in stamps
        )
        usable.append(history and quality)
        future = stamps[1]
        actual = bd.compute_naqi({bd.AQ_VAR_TO_KEY[k]: raw_air[future].get(k) for k in bd.AQ_VARS})
        if (
            actual.band is None
            or actual.band.value != rows[i]["target_band"]
            or actual.index is None
            or round(actual.index, 2) != rows[i]["target_naqi"]
        ):
            raise ValueError("Exact source target mismatch")
    x, y = ev.to_matrix(rows)
    incumbent_x = np.column_stack((x, risk.instantaneous_history_features(rows)))
    incumbent_order = ev.FEATURE_COLUMNS + list(risk.INSTANT_HISTORY_COLUMNS)
    matrices = {"incumbent": incumbent_x}
    orders = {"incumbent": incumbent_order}
    if manifest["approach"] == "gas_history":
        matrices["challenger"] = np.column_stack(
            (incumbent_x, gas_history_features(times, raw_air))
        )
        orders["challenger"] = incumbent_order + list(GAS_COLUMNS)
    else:
        matrices["challenger"] = incumbent_x
        orders["challenger"] = incumbent_order
    parts = {
        name: [i for i in risk.window_indices(times, *window) if usable[i]]
        for name, window in manifest["partitions"].items()
    }
    if any(not ids for ids in parts.values()):
        raise ValueError("Empty archive partition")
    supports = {
        name: {
            "n": len(ids),
            "bands": dict(Counter(ev.BANDS[int(y[i])] for i in ids)),
            "poor_or_worse_episodes": risk.episode_support([times[i] for i in ids], y[ids]),
            "severe_or_worse_episodes": risk.episode_support([times[i] for i in ids], y[ids], 4),
        }
        for name, ids in parts.items()
    }
    missingness = {
        partition: {
            candidate: {
                column: {
                    "finite": int(np.isfinite(matrix[ids, j]).sum()),
                    "missing": int((~np.isfinite(matrix[ids, j])).sum()),
                }
                for j, column in enumerate(orders[candidate])
            }
            for candidate, matrix in matrices.items()
        }
        for partition, ids in parts.items()
    }
    if supports["expanded_train"]["bands"].get("severe", 0) < 20:
        raise ValueError("Severe training support gate failed")
    directory = Path("/artifacts") / manifest["run_name"]
    directory.mkdir(exist_ok=False)
    write(directory / "pre_fit_support.json", supports)
    modal.Volume.from_name("baahar-training").commit()
    train = parts["expanded_train"]
    fitted = {}
    bundle_metadata = None
    if manifest["approach"] == "quantile_floor":
        bundle_path = Path(manifest["reused_model_path"])
        bundle_sha = digest(bundle_path)
        bundle = joblib.load(bundle_path)
        if digest(bundle_path) != bundle_sha:
            raise ValueError("Reused model bundle changed during read")
        original = bundle["manifest"]
        for key in ("model_parameters", "class_weights", "partitions", "source_sha256"):
            expected = manifest["reused_model_contract"][key]
            if original[key] != expected:
                raise ValueError("Reused V4 model contract mismatch: " + key)
        if bundle["feature_orders"]["instant_history"] != incumbent_order:
            raise ValueError("Reused V4 model feature order mismatch")
        for candidate, key, expected_alpha in (
            ("incumbent", "instant_history_classifier", None),
            ("challenger", "instant_history_quantile_0.9", 0.9),
        ):
            model, medians, feature_name, alpha = bundle["models"][key]
            if feature_name != "instant_history" or alpha != expected_alpha:
                raise ValueError("Reused V4 model head contract mismatch")
            for parameter, expected in manifest["model_parameters"].items():
                if model.get_params()[parameter] != expected:
                    raise ValueError("Reused model parameter mismatch: " + parameter)
            if expected_alpha is not None and (
                model.get_params()["alpha"] != 0.9 or model.get_params()["objective"] != "quantile"
            ):
                raise ValueError("Reused quantile head settings mismatch")
            fitted[candidate] = (model, medians)
        bundle_metadata = {
            "path": str(bundle_path),
            "sha256": bundle_sha,
            "hash_observed_at_read": True,
            "model_contract_verified": True,
            "no_refitting": True,
        }
    else:
        for name, matrix in matrices.items():
            xt, medians = ev.impute(matrix[train])
            model = lgb.LGBMClassifier(**manifest["model_parameters"])
            model.fit(xt, y[train], sample_weight=np.array(manifest["class_weights"])[y[train]])
            fitted[name] = (model, medians)
    periods = []
    for name, ids in parts.items():
        if name == "expanded_train":
            continue
        labels, current = (
            y[ids].tolist(),
            [risk.instantaneous_persistence(rows[i]["naqi_instant"]) for i in ids],
        )
        period_times = [times[i] for i in ids]
        models = {}
        for candidate, (model, medians) in fitted.items():
            matrix = ev.impute(matrices[candidate][ids], medians)[0]
            numeric, numeric_metrics = None, None
            no_probabilities = (
                candidate == "challenger" and manifest["approach"] == "quantile_floor"
            )
            if no_probabilities:
                numeric = model.predict(matrix).tolist()
                if (
                    prediction_digest(numeric)
                    != manifest["reference_quantile_prediction_sha256"][name]
                ):
                    raise ValueError("V4 quantile numeric prediction replay mismatch: " + name)
                pred = quantile_poor_floor(models["incumbent"]["predictions"], numeric)
                numeric_metrics = risk.numeric_forecast_metrics(
                    [rows[i]["target_naqi"] for i in ids], numeric, 0.9
                )
                poor_p, severe_p = [float(p >= 3) for p in pred], [float(p >= 4) for p in pred]
            else:
                raw = model.predict_proba(matrix)
                probs = np.zeros((len(ids), 6))
                for j, label in enumerate(model.classes_):
                    probs[:, int(label)] = raw[:, j]
                pred = probs.argmax(axis=1).tolist()
                poor_p, severe_p = (
                    probs[:, 3:].sum(axis=1).tolist(),
                    probs[:, 4:].sum(axis=1).tolist(),
                )
            poor = risk.risk_metrics(labels, poor_p, pred)
            severe = risk.risk_metrics(
                [3 if v >= 4 else 0 for v in labels], severe_p, [3 if v >= 4 else 0 for v in pred]
            )
            if no_probabilities:
                for scores in (poor, severe):
                    for key in ("brier", "ece_10_bins", "reliability_bins"):
                        scores[key] = None
            onset = [
                j
                for j, (label, now) in enumerate(zip(labels, current, strict=True))
                if label >= 4 and now < 4
            ]
            models[candidate] = {
                "classification": ev.prf(ev.confusion(labels, pred)),
                "risk": poor,
                "severe_or_worse": severe,
                "predictions": pred,
                "poor_probabilities": None if no_probabilities else poor_p,
                "severe_probabilities": None if no_probabilities else severe_p,
                "poor_episodes": risk.event_detection_metrics(period_times, labels, pred, 3),
                "severe_episodes": risk.event_detection_metrics(period_times, labels, pred, 4),
                "severe_onset": {"n": len(onset), "misses": sum(pred[j] < 4 for j in onset)},
                "numeric": numeric_metrics,
                "numeric_predictions": numeric,
                "feature_order": orders[candidate],
                "probability_note": "no hybrid risk probability"
                if no_probabilities
                else "uncalibrated class probabilities",
            }
        if (
            prediction_digest(models["incumbent"]["predictions"])
            != manifest["reference_prediction_sha256"][name]
        ):
            raise ValueError("V4 incumbent prediction replay mismatch: " + name)
        periods.append(
            {
                "partition": name,
                "n": len(ids),
                "labels": labels,
                "times": [rows[i]["time"] for i in ids],
                "models": models,
                "current_instantaneous_bands": current,
                "numeric_targets": [rows[i]["target_naqi"] for i in ids],
                "incumbent_replay_match": True,
            }
        )
    if bundle_metadata is None:
        joblib.dump(
            {
                "models": fitted,
                "feature_orders": orders,
                "manifest": manifest,
                "disposition": "RESEARCH_ONLY_NO_PROMOTION",
            },
            directory / "candidates.joblib",
        )
    else:
        write(directory / "reused_model_audit.json", bundle_metadata)
    modal.Volume.from_name("baahar-training").commit()
    return {
        "manifest": manifest,
        "dataset": manifest["dataset"],
        "partition_support": supports,
        "comparison": {"reference_model": "incumbent", "candidate_model": "challenger"},
        "pre_imputation_support": missingness,
        "inference_only": bundle_metadata is not None,
        "reused_model": bundle_metadata,
        "resolved_partitions": manifest["partitions"],
        "feature_orders": orders,
        "source_target_timestamp_checks": len(rows),
        "results": periods,
        "versions": {n: version(n) for n in ("numpy", "lightgbm", "scikit-learn")},
        "disposition": "RESEARCH_ONLY_NO_PROMOTION",
    }


def report(result, prefix):
    lines = [
        "# Bounded forecast research " + result["manifest"]["version"],
        "",
        "Consumed CAMS/ERA5 modeled archive; adaptive research choice informed by previous diagnostics. No adoption.",
        "",
        "| Period | Model | Accuracy | Macro-F1 | Poor+ misses | Poor+ FAR | Severe+ misses | Severe+ FAR |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for period in result["results"]:
        for name, model in period["models"].items():
            c, p, s = model["classification"], model["risk"], model["severe_or_worse"]
            lines.append(
                f"| {period['partition']} | {name} | {c['accuracy']} | {c['macro_f1']} | {p['misses']}/{p['positive_support']} | {p['false_alarm_rate']} | {s['misses']}/{s['positive_support']} | {s['false_alarm_rate']} |"
            )
    lines += [
        "",
        "Class probabilities are uncalibrated; hybrid quantile floor has no risk probability. Support is correlated hourly archive data. No prospective, station, field, medical or billing claim.",
    ]
    prefix.with_name(prefix.name + "_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", choices=("v5", "v6"), required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--submit", action="store_true")
    action.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    import modal

    prefix = ROOT / ("eval/raw/forecast_risk_" + args.version)
    manifest_path, output = [
        prefix.with_name(prefix.name + suffix) for suffix in ("_manifest.json", "_results.json")
    ]
    if args.fetch:
        manifest = json.loads(manifest_path.read_text())
        if manifest["status"] in ("COMPLETED", "FAILED"):
            print("Run already " + manifest["status"] + "; no refetch")
            return
        if output.exists():
            print("Saved result exists; repairing manifest without fetching")
            report(json.loads(output.read_text()), prefix)
        else:
            try:
                result = modal.FunctionCall.from_id(manifest["call_id"]).get(timeout=5)
            except (TimeoutError, modal.exception.TimeoutError):
                print("Hosted " + args.version + " still pending")
                return
            except ValueError as exc:
                write(
                    prefix.with_name(prefix.name + "_monitor_error.json"),
                    {
                        "step": "remote_integrity_or_support_gate",
                        "consecutive_count": 1,
                        "terminal": True,
                        "reason": str(exc),
                        "call_id": manifest["call_id"],
                        "observed_at": datetime.now(UTC).isoformat(),
                    },
                )
                manifest.update(status="FAILED", failure_reason=str(exc))
                write(manifest_path, manifest)
                print("Hosted run failed; preserved call and no performance claim")
                return
            write(output, result)
            report(result, prefix)
        manifest.update(status="COMPLETED", results=str(output.relative_to(ROOT)))
        write(manifest_path, manifest)
        print("Fetched " + args.version + " results")
        return
    if manifest_path.exists() or output.exists():
        raise ValueError("Refusing duplicate submission")
    state_path = ROOT / "eval/raw/forecast_next_loop_state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if state.get("completed_iterations", 0) >= min(
            7, state.get("max_iterations", 7)
        ) or state.get("consecutive_no_gain", 0) >= min(2, state.get("plateau_patience", 2)):
            raise ValueError("Bounded series stopping condition reached; no submission")
    if args.version == "v6":
        previous = ROOT / "eval/raw/forecast_risk_v5_manifest.json"
        if not previous.exists() or json.loads(previous.read_text())["status"] != "COMPLETED":
            raise ValueError("V6 requires completed V5 before a separate review")
    reference = json.loads((ROOT / "eval/raw/forecast_risk_v4_results.json").read_text())
    v3 = json.loads((ROOT / "eval/raw/forecast_risk_v3_results.json").read_text())
    approach = "gas_history" if args.version == "v5" else "quantile_floor"
    manifest = {
        "version": args.version,
        "run_name": "forecast_risk_" + args.version,
        "status": "PENDING_SUBMISSION",
        "approach": approach,
        "created_at": datetime.now(UTC).isoformat(),
        "dataset": v3["dataset"],
        "partitions": reference["resolved_partitions"],
        "model_parameters": reference["manifest"]["model_parameters"],
        "class_weights": reference["manifest"]["class_weights"],
        "reference_prediction_sha256": {
            p["partition"]: prediction_digest(
                p["models"]["instant_history_classifier"]["predictions"]
            )
            for p in reference["results"]
        },
        "reference": "eval/raw/forecast_risk_v4_results.json",
        "reference_sha256": digest(ROOT / "eval/raw/forecast_risk_v4_results.json"),
        "protocol_sha256": digest(ROOT / "docs/FORECAST_NEXT_ITERATION_PROTOCOL.md"),
        "gate_reporter_sha256": digest(ROOT / "scripts/report_forecast_next.py"),
        "selection_disclosure": "Approach motivated by previously consumed diagnostics; no pristine evaluation or proof of global optimum",
        "plateau_criterion": {
            "accuracy_loss_max": 0.01,
            "poor_far_increase_max": 0.01,
            "poor_far_max": 0.05,
            "severe_far_increase_max": 0.0025,
            "severe_far_max": 0.01,
            "poor_recall_gain_min": 0.05,
            "new_severe_hours_min": 2,
            "no_more_severe_misses": True,
            "no_fewer_poor_or_severe_episode_any_hits": True,
        },
        "stop_rule": "Maximum 7 research cycles or 2 consecutive no useful improvement; no automatic serving adoption",
    }
    if approach == "quantile_floor":
        manifest.update(
            inference_only=True,
            execution_mode="evaluate_reused_v4_models_no_fitting",
            reused_model_path="/artifacts/forecast_risk_v4/target_feature_candidates.joblib",
            reused_model_contract={
                key: reference["manifest"][key]
                for key in ("model_parameters", "class_weights", "partitions", "source_sha256")
            },
            reference_quantile_prediction_sha256={
                p["partition"]: prediction_digest(
                    p["models"]["instant_history_quantile_0.9"]["numeric_predictions"]
                )
                for p in reference["results"]
            },
            bundle_hash_protocol="Observe SHA256 before/after load; verify preregistered source/config/order and every stored prediction digest; return actual bundle hash. No prior recorded bundle hash exists.",
        )
    files = list((ROOT / "src/baahar").glob("*.py")) + [
        ROOT / "scripts" / name
        for name in (
            "forecast_next_modal.py",
            "forecast_risk.py",
            "run_eval.py",
            "build_dataset.py",
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
    for path in files:
        image = image.add_local_file(str(path), "/opt/" + path.relative_to(ROOT).as_posix())
    write(manifest_path, manifest)
    app = modal.App("baahar-bounded-forecast-" + args.version, image=image)
    function = app.function(
        cpu=2,
        memory=8192,
        timeout=3600,
        retries=0,
        max_containers=1,
        volumes={"/artifacts": modal.Volume.from_name("baahar-training")},
    )(remote_run)
    with app.run(detach=True):
        call = function.spawn(manifest)
        manifest.update(status="SUBMITTED", call_id=call.object_id, app_id=app.app_id)
        write(manifest_path, manifest)
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
