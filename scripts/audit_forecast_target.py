"""Audit consumed forecast artifacts against recorded source bytes, without fitting."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import forecast_risk as risk

from baahar.naqi import compute_naqi

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "eval/raw/forecast_risk_v2_target_audit.json"


def classification(labels, predictions):
    counts = Counter(labels)
    f1s = []
    for label in counts:
        tp = sum(t == label and p == label for t, p in zip(labels, predictions, strict=True))
        predicted = sum(p == label for p in predictions)
        f1s.append(2 * tp / (counts[label] + predicted))
    return {
        "accuracy": round(risk.band_accuracy(labels, predictions), 4),
        "macro_f1": round(sum(f1s) / len(f1s), 4),
    }


def audit(result, rows, air):
    by_time = {row["time"]: row for row in rows}
    keymap = {
        "pm2_5": "pm25", "pm10": "pm10", "nitrogen_dioxide": "no2",
        "ozone": "o3", "sulphur_dioxide": "so2", "carbon_monoxide": "co",
    }
    # Keep the same pollutant-unit/NAQI computation used by the dataset builder.
    def instant(stamp):
        return risk.instantaneous_persistence(compute_naqi({
            keymap[k]: air[stamp].get(k) for k in keymap
        }).index)

    periods = []
    train = result["partition_support"]["train"]["bands"]
    for period in result["results"]:
        labels, times = period["labels"], period["times"]
        for stamp, label in zip(times, labels, strict=True):
            future = (datetime.fromisoformat(stamp) + timedelta(hours=6)).isoformat(timespec="minutes")
            if instant(future) != label:
                raise ValueError("Archived source does not reproduce target label at " + stamp)
        matching = [instant(t) for t in times]
        effective = [risk.BAND_NAMES.index(by_time[t]["band"]) for t in times]
        if effective != period["models"]["persistence"]["predictions"]:
            raise ValueError("Archived rows do not reproduce v2 conservative persistence")
        baselines = {}
        for name, pred in (
            ("instantaneous_persistence", matching),
            ("conservative_persistence_diagnostic", effective),
        ):
            baselines[name] = {
                "classification": classification(labels, pred),
                "risk": risk.risk_metrics(labels, [float(p >= 3) for p in pred], pred),
                "probability_note": "Binary decisions; not calibrated probabilities",
                "predictions": pred,
            }
        periods.append({
            "partition": period["partition"], "n": len(labels),
            "baseline_disagreements": sum(a != b for a, b in zip(matching, effective, strict=True)),
            "rounded_current_index_band_disagreements": sum(
                risk.instantaneous_persistence(by_time[t]["naqi_instant"]) != p
                for t, p in zip(times, matching, strict=True)
            ),
            "training_unsupported_classes": risk.unsupported_classes(
                train, result["partition_support"][period["partition"]]["bands"]
            ),
            "learned_model_severe_diagnostics": {
                name: {
                    "severe_support": sum(t == 4 for t in labels),
                    "severe_predicted_below_severe": sum(
                        t == 4 and p < 4 for t, p in zip(labels, model["predictions"], strict=True)
                    ),
                    "predicted_severe_or_hazardous": sum(p >= 4 for p in model["predictions"]),
                } for name, model in period["models"].items() if name != "persistence"
            },
            "baselines": baselines,
        })
    return {
        "forecast_target_contract": risk.FORECAST_TARGET_CONTRACT,
        "status": "COMPLETED_NO_FITTING", "periods": periods,
        "training_class_support": train,
        "limitation": "Consumed historical diagnostics, not a new holdout. Matching source definition does not establish live safety. Model outputs are unchanged.",
    }


def main():
    if OUTPUT.exists():
        raise ValueError("Refusing to overwrite existing target audit")
    import modal

    raw_path = ROOT / "eval/raw/forecast_risk_v2_results.json"
    result = json.loads(raw_path.read_text(encoding="utf-8"))
    volume = modal.Volume.from_name("baahar-training")

    def read_verified(path, sha):
        content = b"".join(volume.read_file("/forecast_risk_v2/" + path))
        if hashlib.sha256(content).hexdigest() != sha:
            raise ValueError("Recorded volume hash mismatch: " + path)
        return content

    rows_bytes = read_verified("rows.jsonl", result["dataset"]["rows_sha256"])
    rows = [json.loads(line) for line in rows_bytes.splitlines()]
    air = {}
    source_hashes = {}
    for fixture in result["dataset"]["source_fixtures"]:
        if "archival_aq_2025-" not in fixture["path"]:
            continue
        hourly = json.loads(read_verified(fixture["path"], fixture["sha256"]))["hourly"]
        source_hashes[fixture["path"]] = fixture["sha256"]
        for i, stamp in enumerate(hourly["time"]):
            air[stamp] = {k: values[i] for k, values in hourly.items() if k != "time"}
    report = audit(result, rows, air)
    report.update(
        original_result_sha256=hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        rows_sha256=result["dataset"]["rows_sha256"], source_sha256=source_hashes,
        audit_code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        contract_code_sha256=hashlib.sha256((ROOT / "scripts/forecast_risk.py").read_bytes()).hexdigest(),
    )
    OUTPUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT), "periods": [
            {k: v for k, v in p.items() if k != "baselines"} | {
                "baselines": {name: {k: v for k, v in b.items() if k != "predictions"}
                              for name, b in p["baselines"].items()}
            } for p in report["periods"]
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
