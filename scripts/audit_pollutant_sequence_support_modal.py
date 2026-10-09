"""Read-only fixed-window gas sequence support audit on recorded Modal fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "eval/raw/pollutant_sequence_support"
GASES = {"pm2_5": "pm25", "pm10": "pm10", "nitrogen_dioxide": "no2",
         "ozone": "o3", "sulphur_dioxide": "so2", "carbon_monoxide": "co"}
WINDOWS = {"train": ["2023-01-01", "2025-04-01"],
           "development": ["2025-04-01", "2025-06-01"],
           "diagnostic_pollution": ["2026-02-01", "2026-05-01"],
           "diagnostic_other_seasons": ["2026-05-01", "2026-10-01"]}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def audit(protocol):
    import math
    import sys
    from collections import Counter
    from datetime import datetime, timedelta

    sys.path.insert(0, "/opt/src")
    from baahar.naqi import compute_naqi

    base = Path("/artifacts/forecast_risk_v3")
    raw, metadata = {}, []
    for source in protocol["source_fixtures"]:
        path = base / source["path"]
        if digest(path) != source["sha256"]:
            raise ValueError("Source SHA mismatch: " + source["path"])
        payload = json.loads(path.read_text())
        metadata.append({**source, "timezone": payload.get("timezone"),
                         "timezone_abbreviation": payload.get("timezone_abbreviation"),
                         "utc_offset_seconds": payload.get("utc_offset_seconds"),
                         "hourly_units": payload.get("hourly_units"),
                         "latitude": payload.get("latitude"), "longitude": payload.get("longitude")})
        if not path.name.startswith("archival_aq"):
            continue
        hourly = payload["hourly"]
        for i, stamp in enumerate(hourly["time"]):
            dt = datetime.fromisoformat(stamp)
            value = {key: hourly[var][i] for var, key in GASES.items()}
            if dt in raw:
                raise ValueError("Duplicate source gas timestamp")
            raw[dt] = value
    rows_path = base / "rows.jsonl"
    if digest(rows_path) != protocol["rows_sha256"]:
        raise ValueError("Pinned row SHA mismatch")
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]

    def finite(value):
        return isinstance(value, (float, int)) and math.isfinite(value)

    verified = 0
    for row in rows:
        dt = datetime.fromisoformat(row["time"]) + timedelta(hours=6)
        actual = compute_naqi(raw[dt])
        if actual.band.value != row["target_band"] or round(actual.index, 2) != row["target_naqi"]:
            raise ValueError("Canonical exact t+6 target mismatch")
        verified += 1

    def episodes(stamps):
        groups = []
        for dt in sorted(stamps):
            if not groups or dt - groups[-1][-1] > timedelta(hours=6):
                groups.append([])
            groups[-1].append(dt)
        return [{"first_target_time": g[0].isoformat(), "last_target_time": g[-1].isoformat(),
                 "positive_hours": len(g)} for g in groups]

    support = {}
    for name, bounds in protocol["windows"].items():
        start, end = map(datetime.fromisoformat, bounds)
        candidates = [r for r in rows if start <= datetime.fromisoformat(r["time"]) < end]
        eligible, missing = [], Counter()
        boundary, absent = 0, 0
        for row in candidates:
            dt = datetime.fromisoformat(row["time"])
            if dt - timedelta(hours=23) < start or dt + timedelta(hours=6) >= end:
                boundary += 1
                continue
            stamps = [dt + timedelta(hours=h) for h in range(-23, 7)]
            if any(t not in raw for t in stamps):
                absent += 1
                continue
            bad = [gas for gas in GASES.values() if any(not finite(raw[t][gas]) for t in stamps)]
            missing.update(bad)
            if not bad:
                eligible.append(row)
        future = [(datetime.fromisoformat(r["time"]) + timedelta(hours=6), r) for r in eligible]
        # Legacy raw category ordinal 4 means CPCB Very Poor (301-400).
        very_poor = [t for t, r in future if r["target_band"] in ("severe", "hazardous")]
        severe = [t for t, r in future if r["target_band"] == "hazardous"]
        support[name] = {"candidate_rows": len(candidates), "boundary_exclusions": boundary,
                         "absent_timestamp_exclusions": absent, "missing_sequence_by_gas": dict(missing),
                         "eligible_rows": len(eligible),
                         "legacy_band_support": dict(Counter(r["target_band"] for r in eligible)),
                         "cpcb_very_poor_or_worse_hours": len(very_poor), "cpcb_severe_hours": len(severe),
                         "very_poor_or_worse_episodes": episodes(very_poor),
                         "severe_episodes": episodes(severe)}
    return {"protocol": protocol, "source_metadata": metadata, "canonical_target_checks": verified,
            "support": support,
            "limitations": ["Modeled archive proxy, not official station AQI",
                            "Diagnostic windows previously consumed; development support counts inspected adaptively",
                            "Episodes group positive target hours separated by at most six hours"]}


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
            print("COMPLETED: preserving saved result")
            return
        try:
            result = modal.FunctionCall.from_id(manifest["call_id"]).get(timeout=5)
        except TimeoutError:
            print("PENDING")
            return
        write(result_path, result)
        manifest["status"] = "COMPLETED"
        write(manifest_path, manifest)
        print(json.dumps(result["support"]))
        return
    if manifest_path.exists():
        raise SystemExit("Existing manifest; refusing duplicate submission")
    reference = json.loads((ROOT / "eval/raw/forecast_risk_v3_results.json").read_text())
    protocol = {"source_fixtures": reference["dataset"]["source_fixtures"],
                "rows_sha256": reference["dataset"]["rows_sha256"], "windows": WINDOWS,
                "eligibility": "All six gases finite at each hourly t-23..t and t+1..t+6; full sequence within phase"}
    manifest = {"status": "PREREGISTERED", "protocol": protocol, "audit_sha256": digest(Path(__file__))}
    write(manifest_path, manifest)
    image = modal.Image.debian_slim(python_version="3.12")
    for name in ("__init__.py", "naqi.py"):
        image = image.add_local_file(str(ROOT / "src/baahar" / name), "/opt/src/baahar/" + name)
    app = modal.App("baahar-pollutant-sequence-support", image=image)
    function = app.function(cpu=1, memory=2048, timeout=300, retries=0,
                            volumes={"/artifacts": modal.Volume.from_name("baahar-training")})(audit)
    with app.run(detach=True):
        call = function.spawn(protocol)
        manifest.update(status="SUBMITTED", call_id=call.object_id, app_id=app.app_id)
        write(manifest_path, manifest)
        print(json.dumps({"call_id": call.object_id, "app_id": app.app_id}))


if __name__ == "__main__":
    main()
