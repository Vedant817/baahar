"""Fixed, train/development-only 24h versus 48h temporal information probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "eval/raw/pollutant_lag_probe_v1"
MANIFEST = Path(str(PREFIX) + "_manifest.json")
RESULT = Path(str(PREFIX) + "_results.json")
GASES = ("pm2_5", "pm10", "nitrogen_dioxide", "ozone", "sulphur_dioxide", "carbon_monoxide")
WEATHER = ("temperature_2m", "apparent_temperature", "precipitation",
           "relative_humidity_2m", "wind_speed_10m")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def origins_digest(times):
    if len(times) != len(set(times)):
        raise ValueError("Duplicate origins")
    return hashlib.sha256("\n".join(sorted(times)).encode()).hexdigest()


def eligible(stamp, start, end, air):
    t = datetime.fromisoformat(stamp)
    if t - timedelta(hours=47) < datetime.fromisoformat(start) or t + timedelta(
        hours=6
    ) >= datetime.fromisoformat(end):
        return False
    for offset in range(-47, 7):
        record = air.get((t + timedelta(hours=offset)).isoformat(timespec="minutes"))
        if record is None or any(record.get(g) is None or not math.isfinite(record[g]) for g in GASES):
            return False
    return True


def features(stamp, air, weather, context):
    if context not in (24, 48):
        raise ValueError("Only the frozen 24h/48h comparison is allowed")
    t = datetime.fromisoformat(stamp)
    out = []
    for offset in range(1 - context, 1):
        hour = t + timedelta(hours=offset)
        key = hour.isoformat(timespec="minutes")
        values = [air[key][g] for g in GASES] + [weather.get(key, {}).get(g) for g in WEATHER]
        out.extend(float(v) if v is not None and math.isfinite(v) else float("nan") for v in values)
        # Keep the recent block identical; duplicated older calendar columns
        # would change Ridge's effective penalty without adding source information.
        if offset >= -23:
            out.extend((math.sin(2 * math.pi * hour.hour / 24), math.cos(2 * math.pi * hour.hour / 24),
                        math.sin(2 * math.pi * (hour.month - 1) / 12),
                        math.cos(2 * math.pi * (hour.month - 1) / 12)))
    return out


def remote_probe(manifest):
    import sys
    sys.path[:0] = ["/opt/src", "/opt/scripts"]
    import numpy as np
    import train_pollutant_sequence_v3_modal as base
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge
    from sklearn.metrics import f1_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    from baahar.naqi import compute_naqi

    for name, sha in manifest["source_sha256"].items():
        if digest(Path("/opt") / name) != sha:
            raise ValueError("Pinned implementation/reference mismatch: " + name)
    protocol = manifest["protocol"]
    directory = Path("/artifacts/forecast_risk_v3")
    if digest(directory / "rows.jsonl") != protocol["rows_sha256"]:
        raise ValueError("Pinned row hash mismatch")
    rows = [json.loads(line) for line in (directory / "rows.jsonl").read_text().splitlines()]
    air, weather = {}, {}
    for fixture in protocol["source_fixtures"]:
        path = directory / fixture["path"]
        if digest(path) != fixture["sha256"]:
            raise ValueError("Pinned source fixture mismatch")
        hourly = json.loads(path.read_text())["hourly"]
        destination = air if "archival_aq_" in path.name else weather
        for i, stamp in enumerate(hourly["time"]):
            if stamp in destination:
                raise ValueError("Duplicate source timestamp")
            destination[stamp] = {key: values[i] for key, values in hourly.items() if key != "time"}
    keys = ("pm25", "pm10", "no2", "o3", "so2", "co")

    def canonical(values):
        reading = compute_naqi(dict(zip(keys, map(float, values), strict=True)))
        return reading.index, base.BANDS.index(reading.band.value)

    parts = {}
    checks = 0
    for name, (start, end) in protocol["partitions"].items():
        selected = sorted([r for r in rows if start <= r["time"] < end and eligible(r["time"], start, end, air)],
                          key=lambda r: r["time"])
        times = [r["time"] for r in selected]
        expected = protocol["expected_support"][name]
        if len(times) != expected["eligible_rows"] or origins_digest(times) != expected["eligible_origin_times_sha256"]:
            raise ValueError("Audited 48h origin set changed: " + name)
        target = np.asarray([[air[(datetime.fromisoformat(t) + timedelta(hours=6)).isoformat(
            timespec="minutes")][g] for g in GASES] for t in times], dtype=np.float64)
        labels, indices = [], []
        for row, values in zip(selected, target, strict=True):
            index, ordinal = canonical(values)
            if round(index, 2) != row["target_naqi"] or base.BANDS[ordinal] != row["target_band"]:
                raise ValueError("Canonical target mismatch")
            indices.append(index)
            labels.append(ordinal)
            checks += 1
        parts[name] = {"times": times, "target": target, "labels": np.asarray(labels), "actual_naqi": indices}
    train, dev = parts["train"], parts["development"]
    target_mean = train["target"].mean(axis=0)
    target_scale = np.maximum(train["target"].std(axis=0), 1e-6)
    weights = np.asarray([base.training_origin_weight(int(v)) for v in train["labels"]])
    if int((weights > 1).sum()) != 296:
        raise ValueError("Training Poor+ weighting support changed")

    def metrics(actual, predicted, truth_labels, pred_labels, times):
        error = np.abs(predicted - actual)
        risk = {}
        for threshold, name in ((3, "poor_or_worse"), (4, "very_poor_or_worse"), (5, "official_severe")):
            positive, alarm = truth_labels >= threshold, pred_labels >= threshold
            support = int(positive.sum())
            tp = int((positive & alarm).sum())
            fp = int((~positive & alarm).sum())
            risk[name] = {"support": support, "misses": support - tp, "false_alarms": fp,
                          "recall": tp / support if support else None,
                          "precision": tp / int(alarm.sum()) if alarm.sum() else None,
                          "false_alarm_rate": fp / int((~positive).sum()) if (~positive).sum() else None,
                          "episodes": base.event_metrics(times, truth_labels.tolist(), pred_labels.tolist(), threshold)}
        return {"rows": len(times), "normalized_mae": float((error / target_scale).mean()),
                "pollutant_mae": dict(zip(GASES, error.mean(axis=0).tolist(), strict=True)),
                "accuracy": float((truth_labels == pred_labels).mean()),
                "macro_f1": float(f1_score(truth_labels, pred_labels, average="macro", zero_division=0)),
                "risk": risk}

    results = {}
    for context in protocol["contexts"]:
        xtrain = np.asarray([features(t, air, weather, context) for t in train["times"]])
        xdev = np.asarray([features(t, air, weather, context) for t in dev["times"]])
        if not np.isfinite(np.nanmedian(xtrain, axis=0)).all():
            raise ValueError("Entirely missing training channel")
        model = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                              Ridge(alpha=protocol["ridge_alpha"], solver="cholesky"))
        model.fit(xtrain, (train["target"] - target_mean) / target_scale, ridge__sample_weight=weights)
        pred_unclipped = model.predict(xdev) * target_scale + target_mean
        pred = np.maximum(pred_unclipped, 0)
        pred_labels = np.asarray([canonical(v)[1] for v in pred])
        monthly = {}
        for month in ("2025-04", "2025-05"):
            mask = np.asarray([t.startswith(month) for t in dev["times"]])
            monthly[month] = metrics(dev["target"][mask], pred[mask], dev["labels"][mask],
                                     pred_labels[mask], [t for t, take in zip(dev["times"], mask, strict=True) if take])
        results[str(context)] = {"overall": metrics(dev["target"], pred, dev["labels"], pred_labels, dev["times"]),
                                 "monthly": monthly, "predicted_pollutants": pred.tolist(),
                                 "negative_raw_predictions": int((pred_unclipped < 0).sum())}
    baseline, extended = results["24"]["overall"], results["48"]["overall"]
    gain = 1 - extended["normalized_mae"] / baseline["normalized_mae"]
    criteria = {"overall_normalized_mae_gain_at_least_1pct": gain >= 0.01,
                "neither_month_normalized_mae_worse": all(results["48"]["monthly"][m]["normalized_mae"] <=
                                                         results["24"]["monthly"][m]["normalized_mae"] for m in ("2025-04", "2025-05")),
                "poor_misses_not_worse": extended["risk"]["poor_or_worse"]["misses"] <= baseline["risk"]["poor_or_worse"]["misses"],
                "poor_false_alarms_not_worse": extended["risk"]["poor_or_worse"]["false_alarms"] <= baseline["risk"]["poor_or_worse"]["false_alarms"],
                "poor_episode_hits_not_worse": extended["risk"]["poor_or_worse"]["episodes"]["any_hit"] >= baseline["risk"]["poor_or_worse"]["episodes"]["any_hit"],
                "very_poor_misses_not_worse": extended["risk"]["very_poor_or_worse"]["misses"] <= baseline["risk"]["very_poor_or_worse"]["misses"],
                "very_poor_false_alarms_not_worse": extended["risk"]["very_poor_or_worse"]["false_alarms"] <= baseline["risk"]["very_poor_or_worse"]["false_alarms"]}
    return {"status": "COMPLETED", "canonical_target_checks": checks, "protocol": protocol,
            "target_scale_training_only": target_scale.tolist(), "training_weighted_origins": int((weights > 1).sum()),
            "origin_hashes": {k: origins_digest(v["times"]) for k, v in parts.items()},
            "development_times": dev["times"], "actual_pollutants": dev["target"].tolist(),
            "actual_naqi": dev["actual_naqi"], "actual_ordinals": dev["labels"].tolist(), "results": results,
            "normalized_mae_relative_gain": gain, "criteria": criteria, "context_followup_supported": all(criteria.values()),
            "limitations": ["Adaptive consumed development archive; no independent significance claim",
                            "Fixed Ridge probe; failure cannot exclude nonlinear older-history signal",
                            "No 2026 diagnostic labels used for fitting or selection; no deployment or safety qualification"]}


def main():
    import modal
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--submit", action="store_true")
    mode.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    if args.fetch:
        manifest = json.loads(MANIFEST.read_text())
        if RESULT.exists():
            print("Saved result exists; preserving it")
            return
        try:
            result = modal.FunctionCall.from_id(manifest["call_id"]).get(timeout=5)
        except (TimeoutError, modal.exception.TimeoutError):
            print("PENDING " + manifest["call_id"])
            return
        write(RESULT, result)
        manifest.update(status="COMPLETED", result_sha256=digest(RESULT), completed_at=datetime.now(UTC).isoformat())
        write(MANIFEST, manifest)
        print(json.dumps({"status": "COMPLETED", "criteria": result["criteria"], "gain": result["normalized_mae_relative_gain"]}))
        return
    if MANIFEST.exists():
        raise SystemExit("Existing manifest; refusing duplicate submission")
    audit_manifest = ROOT / "eval/raw/pollutant_context_support_v1_manifest.json"
    audit_result = ROOT / "eval/raw/pollutant_context_support_v1_results.json"
    frozen = json.loads(audit_manifest.read_text())
    if frozen["status"] != "COMPLETED" or digest(audit_result) != frozen["result_sha256"]:
        raise ValueError("Completed support result hash mismatch")
    audit = json.loads(audit_result.read_text())
    files = [Path(__file__), ROOT / "scripts/train_pollutant_sequence_v3_modal.py",
             ROOT / "src/baahar/naqi.py", ROOT / "src/baahar/__init__.py", audit_result,
             ROOT / "docs/POLLUTANT_LAG_PROBE_V1_PROTOCOL.md"]
    protocol = {"contexts": [24, 48], "ridge_alpha": 10.0,
                "partitions": {k: frozen["protocol"]["windows"][k] for k in ("train", "development")},
                "expected_support": {k: audit["support"][k]["48"] for k in ("train", "development")},
                "rows_sha256": frozen["protocol"]["rows_sha256"],
                "source_fixtures": frozen["protocol"]["source_fixtures"],
                "support_result_sha256": digest(audit_result), "feature_order": list(GASES + WEATHER) + ["sin_hour", "cos_hour", "sin_month", "cos_month"]}
    manifest = {"status": "PREREGISTERED", "created_at": datetime.now(UTC).isoformat(), "protocol": protocol,
                "source_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in files},
                "timeout_seconds": 1800, "retries": 0, "gpu": None}
    image = modal.Image.debian_slim(python_version="3.12").pip_install("numpy==2.2.6", "scikit-learn==1.6.1")
    for path in files:
        image = image.add_local_file(str(path), "/opt/" + path.relative_to(ROOT).as_posix())
    write(MANIFEST, manifest)
    app = modal.App("baahar-pollutant-lag-probe-v1", image=image)
    function = app.function(cpu=2, memory=8192, timeout=1800, retries=0, max_containers=1,
                            volumes={"/artifacts": modal.Volume.from_name("baahar-training")})(remote_probe)
    with app.run(detach=True):
        call = function.spawn(manifest)
        manifest.update(status="SUBMITTED", call_id=call.object_id, app_id=app.app_id)
        write(MANIFEST, manifest)
        print(json.dumps({"call_id": call.object_id, "app_id": app.app_id}))


if __name__ == "__main__":
    main()
