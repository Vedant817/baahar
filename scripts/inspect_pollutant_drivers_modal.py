"""Read-only hosted audit of consumed severe targets; returns small metadata only."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "eval/raw/forecast_risk_v4_pollutant_drivers"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def remote_inspect(protocol):
    import sys
    from collections import Counter
    from datetime import datetime, timedelta

    sys.path.insert(0, "/opt/src")
    from baahar.naqi import compute_naqi

    directory = Path("/artifacts/forecast_risk_v3")
    mapping = {"pm2_5": "pm25", "pm10": "pm10", "nitrogen_dioxide": "no2",
               "ozone": "o3", "sulphur_dioxide": "so2", "carbon_monoxide": "co"}
    raw = {}
    for source in protocol["source_fixtures"]:
        path = directory / source["path"]
        if digest(path) != source["sha256"]:
            raise ValueError("Recorded source hash mismatch: " + source["path"])
        if not path.name.startswith("archival_aq"):
            continue
        hourly = json.loads(path.read_text())["hourly"]
        for i, stamp in enumerate(hourly["time"]):
            raw[stamp] = {key: hourly[var][i] for var, key in mapping.items()}
    rows_path = directory / "rows.jsonl"
    if digest(rows_path) != protocol["rows_sha256"]:
        raise ValueError("Recorded derived row hash mismatch")
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    start, end = map(datetime.fromisoformat, protocol["training_partition"])
    train_counts = Counter()
    train_n = 0
    for row in rows:
        stamp = datetime.fromisoformat(row["time"])
        if start <= stamp and stamp + timedelta(hours=6) < end and row["target_band"] in ("severe", "hazardous"):
            future = (stamp + timedelta(hours=6)).isoformat(timespec="minutes")
            result = compute_naqi(raw[future])
            if result.band.value != row["target_band"]:
                raise ValueError("Training target reconstruction mismatch")
            train_counts[result.dominant_pollutant] += 1
            train_n += 1
    cases, target_counts, current_counts = [], Counter(), Counter()
    for case in protocol["evaluation_cases"]:
        stamp = datetime.fromisoformat(case["time"])
        future = (stamp + timedelta(hours=6)).isoformat(timespec="minutes")
        current, target = compute_naqi(raw[case["time"]]), compute_naqi(raw[future])
        if target.band.value != case["target_band"]:
            raise ValueError("Evaluation target reconstruction mismatch")
        target_counts[target.dominant_pollutant] += 1
        current_counts[current.dominant_pollutant] += 1
        cases.append({**case, "target_time": future,
                      "current": current.to_dict(), "target": target.to_dict(),
                      "current_pollutants": raw[case["time"]]})
    return {"protocol": protocol, "verified_source_count": len(protocol["source_fixtures"]),
            "training_severe_n": train_n, "training_severe_dominant_counts": dict(train_counts),
            "evaluation_severe_n": len(cases), "evaluation_target_dominant_counts": dict(target_counts),
            "evaluation_current_dominant_counts": dict(current_counts), "cases": cases,
            "limitation": "Read-only explanatory audit of consumed modeled archive; no fitting or independent validation."}


def main():
    import modal

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    manifest_path = PREFIX.with_name(PREFIX.name + "_manifest.json")
    result_path = PREFIX.with_name(PREFIX.name + "_results.json")
    if args.fetch:
        manifest = json.loads(manifest_path.read_text())
        if result_path.exists():
            print("Already fetched; preserving metadata")
            return
        try:
            result = modal.FunctionCall.from_id(manifest["call_id"]).get(timeout=5)
        except TimeoutError:
            print("PENDING")
            return
        result_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
        manifest["status"] = "COMPLETED"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(json.dumps({k: v for k, v in result.items() if k not in ("protocol", "cases")}))
        return
    if manifest_path.exists():
        raise SystemExit("Existing diagnostic manifest; refusing duplicate launch")
    reference = json.loads((ROOT / "eval/raw/forecast_risk_v3_results.json").read_text())
    cases = [{"partition": period["partition"], "time": stamp,
              "target_band": ("severe" if label == 4 else "hazardous")}
             for period in reference["results"]
             for stamp, label in zip(period["times"], period["labels"], strict=True) if label >= 4]
    protocol = {"source_fixtures": reference["dataset"]["source_fixtures"],
                "rows_sha256": reference["dataset"]["rows_sha256"],
                "training_partition": reference["resolved_partitions"]["expanded_train"],
                "evaluation_cases": cases}
    image = modal.Image.debian_slim(python_version="3.12")
    for name in ("__init__.py", "naqi.py"):
        image = image.add_local_file(str(ROOT / "src/baahar" / name), "/opt/src/baahar/" + name)
    app = modal.App("baahar-read-only-pollutant-drivers", image=image)
    function = app.function(cpu=1, memory=1024, timeout=180, retries=0,
                            volumes={"/artifacts": modal.Volume.from_name("baahar-training")})(remote_inspect)
    with app.run(detach=True):
        call = function.spawn(protocol)
        manifest = {"status": "SUBMITTED", "call_id": call.object_id, "app_id": app.app_id,
                    "protocol": protocol, "inspector_sha256": digest(Path(__file__)),
                    "naqi_sha256": digest(ROOT / "src/baahar/naqi.py")}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(json.dumps({"call_id": call.object_id, "app_id": app.app_id}))


if __name__ == "__main__":
    main()
