"""Read-only fixed-partition support audit of pinned v3 raw sources and rows."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "eval/raw/forecast_fixed_episode_audit"
WINDOWS = {
    "train": ["2023-01-01", "2025-04-01"],
    "development": ["2025-04-01", "2025-06-01"],
    "consumed_pollution": ["2026-02-01", "2026-05-01"],
    "consumed_other_seasons": ["2026-05-01", "2026-10-01"],
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def remote_audit(protocol):
    import math
    import sys
    from collections import Counter
    from datetime import datetime, timedelta

    sys.path.insert(0, "/opt/src")
    from baahar.naqi import compute_naqi

    directory = Path("/artifacts/forecast_risk_v3")
    raw, weather = {}, {}
    mapping = {
        "pm2_5": "pm25",
        "pm10": "pm10",
        "nitrogen_dioxide": "no2",
        "ozone": "o3",
        "sulphur_dioxide": "so2",
        "carbon_monoxide": "co",
    }
    for record in protocol["sources"]:
        path = directory / record["path"]
        if digest(path) != record["sha256"]:
            raise ValueError("Pinned source mismatch: " + record["path"])
        hourly = json.loads(path.read_text())["hourly"]
        lookup = raw if path.name.startswith("archival_aq") else weather
        for i, stamp in enumerate(hourly["time"]):
            lookup[stamp] = {key: values[i] for key, values in hourly.items() if key != "time"}
    path = directory / "rows.jsonl"
    if digest(path) != protocol["rows_sha256"]:
        raise ValueError("Pinned rows changed")
    rows = [json.loads(line) for line in path.read_text().splitlines()]

    def finite(value):
        return isinstance(value, (int, float)) and math.isfinite(value)

    times, usable, reasons = [], [], Counter()
    for row in rows:
        stamp = datetime.fromisoformat(row["time"])
        times.append(stamp)
        future = (stamp + timedelta(hours=6)).isoformat(timespec="minutes")
        actual = compute_naqi({key: raw.get(future, {}).get(var) for var, key in mapping.items()})
        if (
            actual.band is None
            or actual.band.value != row["target_band"]
            or round(actual.index, 2) != row["target_naqi"]
        ):
            raise ValueError("Exact six-hour label reconstruction mismatch")
        history = [(stamp - timedelta(hours=h)).isoformat(timespec="minutes") for h in range(24)]
        history_finite = all(
            all(finite(raw.get(t, {}).get(var)) for var in mapping) for t in history
        )
        future_finite = all(finite(raw.get(future, {}).get(var)) for var in mapping)
        current_weather = all(
            finite(weather.get(row["time"], {}).get(var))
            for var in (
                "temperature_2m",
                "apparent_temperature",
                "precipitation",
                "relative_humidity_2m",
                "wind_speed_10m",
            )
        )
        usable.append(history_finite and future_finite and current_weather)
        reasons["incomplete_24h_six_pollutant_history"] += not history_finite
        reasons["incomplete_future_six_pollutants"] += not future_finite
        reasons["incomplete_current_weather"] += not current_weather

    partitions = {}
    for name, window in protocol["partitions"].items():
        start, end = map(datetime.fromisoformat, window)
        ids = [
            i
            for i, stamp in enumerate(times)
            if start <= stamp and stamp + timedelta(hours=6) < end and usable[i]
        ]
        episodes, previous = [], None
        for i in ids:
            if rows[i]["target_band"] not in ("severe", "hazardous"):
                continue
            if previous is None or times[i] - previous > timedelta(hours=6):
                episodes.append(
                    {
                        "feature_start": rows[i]["time"],
                        "feature_end": rows[i]["time"],
                        "target_start": (times[i] + timedelta(hours=6)).isoformat(
                            timespec="minutes"
                        ),
                        "target_end": (times[i] + timedelta(hours=6)).isoformat(timespec="minutes"),
                        "hours": 0,
                    }
                )
            episodes[-1].update(
                feature_end=rows[i]["time"],
                target_end=(times[i] + timedelta(hours=6)).isoformat(timespec="minutes"),
            )
            episodes[-1]["hours"] += 1
            previous = times[i]
        partitions[name] = {
            "n": len(ids),
            "legacy_bands": dict(Counter(rows[i]["target_band"] for i in ids)),
            "official_band_note": "Legacy severe is CPCB very poor; legacy hazardous is CPCB severe",
            "band4_or_worse_episodes": episodes,
            "first_feature_time": rows[ids[0]]["time"] if ids else None,
            "last_feature_time": rows[ids[-1]]["time"] if ids else None,
        }
    return {
        "protocol": protocol,
        "verified_sources": len(protocol["sources"]),
        "source_target_timestamp_checks": len(rows),
        "excluded_reasons": dict(reasons),
        "partition_support": partitions,
        "limitation": "Consumed modeled archive feasibility only; no fitting, adaptive cuts or new holdout.",
    }


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
            print("Already fetched; preserving raw metadata")
            return
        try:
            result = modal.FunctionCall.from_id(manifest["call_id"]).get(timeout=5)
        except TimeoutError:
            print("PENDING")
            return
        result_path.write_text(json.dumps(result, indent=2) + "\n")
        manifest["status"] = "COMPLETED"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "partition_support": result["partition_support"],
                    "excluded_reasons": result["excluded_reasons"],
                }
            )
        )
        return
    if manifest_path.exists():
        raise SystemExit("Existing audit manifest; refusing duplicate launch")
    reference = json.loads((ROOT / "eval/raw/forecast_risk_v3_results.json").read_text())
    protocol = {
        "partitions": WINDOWS,
        "history_hours": 24,
        "horizon_hours": 6,
        "episode_separation_hours": 6,
        "sources": reference["dataset"]["source_fixtures"],
        "rows_sha256": reference["dataset"]["rows_sha256"],
    }
    image = modal.Image.debian_slim(python_version="3.12")
    for name in ("__init__.py", "naqi.py"):
        image = image.add_local_file(str(ROOT / "src/baahar" / name), "/opt/src/baahar/" + name)
    app = modal.App("baahar-read-only-episode-support", image=image)
    function = app.function(
        cpu=1,
        memory=1024,
        timeout=180,
        retries=0,
        volumes={"/artifacts": modal.Volume.from_name("baahar-training")},
    )(remote_audit)
    with app.run(detach=True):
        call = function.spawn(protocol)
        manifest = {
            "status": "SUBMITTED",
            "protocol": protocol,
            "call_id": call.object_id,
            "app_id": app.app_id,
            "inspector_sha256": digest(Path(__file__)),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(json.dumps({"call_id": call.object_id, "app_id": app.app_id}))


if __name__ == "__main__":
    main()
