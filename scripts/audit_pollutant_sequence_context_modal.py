"""Audit phase-local 24/48/72-hour gas support without training a model."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "eval/raw/pollutant_context_support_v1"
MANIFEST = Path(str(PREFIX) + "_manifest.json")
RESULT = Path(str(PREFIX) + "_results.json")
WINDOWS = {
    "train": ["2023-01-01", "2025-04-01"],
    "development": ["2025-04-01", "2025-06-01"],
    "diagnostic_pollution": ["2026-02-01", "2026-05-01"],
    "diagnostic_other_seasons": ["2026-05-01", "2026-10-01"],
}
GASES = {"pm2_5": "pm25", "pm10": "pm10", "nitrogen_dioxide": "no2",
         "ozone": "o3", "sulphur_dioxide": "so2", "carbon_monoxide": "co"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def episode_counts(stamps: list[datetime]) -> dict:
    groups: list[list[datetime]] = []
    for stamp in sorted(stamps):
        if not groups or stamp - groups[-1][-1] > timedelta(hours=6):
            groups.append([])
        groups[-1].append(stamp)
    return {"hours": len(stamps), "episodes": len(groups),
            "episode_hours": [len(group) for group in groups]}


def audit_remote(protocol: dict) -> dict:
    import sys
    sys.path.insert(0, "/opt/src")
    from baahar.naqi import compute_naqi

    base = Path("/artifacts/forecast_risk_v3")
    code_paths = {"scripts/audit_pollutant_sequence_context_modal.py": Path(
        "/opt/scripts/audit_pollutant_sequence_context_modal.py"
    ), "src/baahar/naqi.py": Path("/opt/src/baahar/naqi.py"),
        "src/baahar/__init__.py": Path("/opt/src/baahar/__init__.py"),
        "eval/raw/pollutant_sequence_support_results.json": Path(
            "/opt/eval/raw/pollutant_sequence_support_results.json"
        ), "eval/raw/pollutant_sequence_v3_results.json": Path(
            "/opt/eval/raw/pollutant_sequence_v3_results.json"
        ), "eval/raw/pollutant_sequence_v4_results.json": Path(
            "/opt/eval/raw/pollutant_sequence_v4_results.json"
        )}
    for name, path in code_paths.items():
        if digest(path) != protocol["code_sha256"][name]:
            raise ValueError("Pinned code or reference hash mismatch: " + name)
    air = {}
    metadata = []
    for source in protocol["source_fixtures"]:
        path = base / source["path"]
        if digest(path) != source["sha256"]:
            raise ValueError("Source fixture hash mismatch: " + source["path"])
        payload = json.loads(path.read_text())
        metadata.append({**source, "timezone": payload.get("timezone"),
                         "utc_offset_seconds": payload.get("utc_offset_seconds"),
                         "hourly_units": payload.get("hourly_units"),
                         "latitude": payload.get("latitude"), "longitude": payload.get("longitude")})
        if not path.name.startswith("archival_aq"):
            continue
        hourly = payload["hourly"]
        for i, stamp in enumerate(hourly["time"]):
            dt = datetime.fromisoformat(stamp)
            if dt in air:
                raise ValueError("Duplicate source gas timestamp")
            air[dt] = {key: hourly[var][i] for var, key in GASES.items()}

    rows_path = base / "rows.jsonl"
    if digest(rows_path) != protocol["rows_sha256"]:
        raise ValueError("Pinned source row hash mismatch")
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    if len(rows) != protocol["row_count"]:
        raise ValueError("Pinned source row count mismatch")

    def finite(x):
        return isinstance(x, (int, float)) and math.isfinite(x)

    verified = 0
    for row in rows:
        origin = datetime.fromisoformat(row["time"])
        future = origin + timedelta(hours=6)
        if future not in air:
            raise ValueError("Missing exact t+6 canonical target")
        actual = compute_naqi(air[future])
        if round(actual.index, 2) != row["target_naqi"] or actual.band.value != row["target_band"]:
            raise ValueError("Canonical t+6 target mismatch")
        verified += 1

    report = {}
    for name, bounds in protocol["windows"].items():
        start, end = map(datetime.fromisoformat, bounds)
        candidates = [row for row in rows if start <= datetime.fromisoformat(row["time"]) < end]
        lengths = {}
        support_sets = {}
        origin_hashes = {}
        for context in (24, 48, 72):
            eligible = []
            boundary, absent, missing = 0, 0, Counter()
            for row in candidates:
                t = datetime.fromisoformat(row["time"])
                first = t - timedelta(hours=context - 1)
                if first < start or t + timedelta(hours=6) >= end:
                    boundary += 1
                    continue
                stamps = [t + timedelta(hours=h) for h in range(-(context - 1), 7)]
                if any(stamp not in air for stamp in stamps):
                    absent += 1
                    continue
                bad = [gas for gas in GASES.values()
                       if any(not finite(air[stamp].get(gas)) for stamp in stamps)]
                missing.update(bad)
                if not bad:
                    eligible.append(row)
            support_sets[context] = {row["time"] for row in eligible}
            origin_hashes[str(context)] = hashlib.sha256(
                "\n".join(sorted(support_sets[context])).encode("utf-8")
            ).hexdigest()
            poor = [row for row in eligible if row["target_band"] in ("poor", "severe", "hazardous")]
            very = [row for row in eligible if row["target_band"] in ("severe", "hazardous")]
            severe = [row for row in eligible if row["target_band"] == "hazardous"]
            lengths[str(context)] = {
                "candidate_rows": len(candidates), "boundary_exclusions": boundary,
                "absent_timestamp_exclusions": absent, "missing_sequence_by_gas": dict(missing),
                "eligible_rows": len(eligible), "poor_or_worse": episode_counts(
                    [datetime.fromisoformat(row["time"]) + timedelta(hours=6) for row in poor]),
                "very_poor_or_worse": episode_counts(
                    [datetime.fromisoformat(row["time"]) + timedelta(hours=6) for row in very]),
                "official_severe": episode_counts(
                    [datetime.fromisoformat(row["time"]) + timedelta(hours=6) for row in severe]),
            }
        for context in (48, 72):
            lost = support_sets[24] - support_sets[context]
            gained = support_sets[context] - support_sets[24]
            if gained:
                raise ValueError("Longer context unexpectedly added origin rows")
            lengths[str(context)]["paired_24h_origin_intersection"] = len(support_sets[context])
            lengths[str(context)]["excluded_from_24h_origins"] = len(lost)
            lengths[str(context)]["eligible_origin_times_sha256"] = origin_hashes[str(context)]
        lengths["24"]["eligible_origin_times_sha256"] = origin_hashes["24"]
        if name == "train" and lengths["24"]["eligible_rows"] != protocol["expected_24h_train"]:
            raise ValueError("24h training support differs from frozen study")
        report[name] = lengths
    return {"status": "COMPLETED", "manifest": protocol["manifest_name"],
            "canonical_target_checks": verified, "row_count": len(rows),
            "source_metadata": metadata, "support": report,
            "limitations": ["Support audit only; no model training or forecast claims",
                            "All categories come from consumed CAMS/ERA5 modeled archive",
                            "Episode counts are correlated hourly intervals, not independent trials"]}


def main() -> None:
    import modal
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--submit", action="store_true")
    mode.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    if args.fetch:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if RESULT.exists():
            print("Saved support result exists; preserving it.")
            return
        try:
            result = modal.FunctionCall.from_id(manifest["call_id"]).get(timeout=5)
        except (TimeoutError, modal.exception.TimeoutError):
            print("PENDING " + manifest["call_id"])
            return
        write(RESULT, result)
        manifest.update(status="COMPLETED", result_sha256=digest(RESULT))
        write(MANIFEST, manifest)
        print("COMPLETED " + str(RESULT))
        return
    if MANIFEST.exists():
        raise SystemExit("Existing support manifest; refusing duplicate submission")
    v3m = json.loads((ROOT / "eval/raw/pollutant_sequence_v3_manifest.json").read_text(encoding="utf-8"))
    v4m = json.loads((ROOT / "eval/raw/pollutant_sequence_v4_manifest.json").read_text(encoding="utf-8"))
    v4raw = ROOT / "eval/raw/pollutant_sequence_v4_results.json"
    if v3m["status"] != "COMPLETED" or v4m["status"] != "COMPLETED" or digest(v4raw) != v4m["result_sha256"]:
        raise ValueError("Frozen v3/v4 results are not complete and hash-valid")
    dataset = json.loads((ROOT / "eval/raw/forecast_risk_v3_results.json").read_text(encoding="utf-8"))["dataset"]
    files = [Path(__file__), ROOT / "src/baahar/naqi.py", ROOT / "src/baahar/__init__.py",
             ROOT / "eval/raw/pollutant_sequence_support_results.json",
             ROOT / "eval/raw/pollutant_sequence_v3_results.json", v4raw]
    protocol = {"manifest_name": "eval/raw/pollutant_context_support_v1_manifest.json",
                "source_fixtures": dataset["source_fixtures"], "rows_sha256": dataset["rows_sha256"],
                "row_count": dataset["row_count"], "windows": WINDOWS,
                "expected_24h_train": 19663, "contexts_hours": [24, 48, 72],
                "v3_manifest_sha256": digest(ROOT / "eval/raw/pollutant_sequence_v3_manifest.json"),
                "v4_result_sha256": digest(v4raw),
                "code_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in files}}
    image = modal.Image.debian_slim(python_version="3.12")
    for path in files:
        image = image.add_local_file(str(path), "/opt/" + path.relative_to(ROOT).as_posix())
    write(MANIFEST, {"status": "PREREGISTERED", "created_at": datetime.now(UTC).isoformat(),
                     "protocol": protocol, "source_sha256": protocol["code_sha256"], "timeout_seconds": 600})
    app = modal.App("baahar-pollutant-context-support-v1", image=image)
    function = app.function(cpu=2, memory=4096, timeout=600, retries=0, max_containers=1,
                            volumes={"/artifacts": modal.Volume.from_name("baahar-training")})(audit_remote)
    with app.run(detach=True):
        call = function.spawn(protocol)
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest.update(status="SUBMITTED", call_id=call.object_id, app_id=app.app_id)
        write(MANIFEST, manifest)
        print(json.dumps({"call_id": call.object_id, "app_id": app.app_id,
                          "url": "https://modal.com/apps/vedantmahajan271/main/" + app.app_id}))


if __name__ == "__main__":
    main()
