"""Read-only, source-pinned comparison of hourly and complete-window targets."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "eval/raw/pollutant_target_contract_v1"
MANIFEST = Path(str(PREFIX) + "_manifest.json")
RESULT = Path(str(PREFIX) + "_results.json")
GASES = {
    "pm2_5": "pm25",
    "pm10": "pm10",
    "nitrogen_dioxide": "no2",
    "ozone": "o3",
    "sulphur_dioxide": "so2",
    "carbon_monoxide": "co",
}
WINDOWS = {
    "train": ["2023-01-01", "2025-04-01"],
    "development": ["2025-04-01", "2025-06-01"],
    "diagnostic_pollution": ["2026-02-01", "2026-05-01"],
    "diagnostic_other_seasons": ["2026-05-01", "2026-10-01"],
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def episode_support(times: list[datetime]) -> dict:
    episodes = 0
    previous = None
    for stamp in sorted(times):
        if previous is None or stamp - previous > timedelta(hours=6):
            episodes += 1
        previous = stamp
    return {
        "hours": len(times),
        "episodes": episodes,
        "recall_if_no_support": "UNMEASURED" if not times else None,
    }


def reconstruct_means(past: list[dict], future: list[dict]) -> dict:
    """Known past ends at t; six future entries represent t+1 through t+6."""
    if len(past) != 24 or len(future) != 6:
        raise ValueError("Requires exactly 24 known and six future hourly entries")
    periods = {gas: 8 if gas in ("o3", "co") else 24 for gas in GASES.values()}
    return {
        gas: math.fsum([row[gas] for row in past[-(period - 6) :]] + [row[gas] for row in future])
        / period
        for gas, period in periods.items()
    }


def audit_remote(protocol: dict) -> dict:
    import sys

    sys.path.insert(0, "/opt/src")
    from baahar.naqi import compute_naqi, compute_naqi_trailing

    for name, expected in protocol["code_sha256"].items():
        if digest(Path("/opt") / name) != expected:
            raise ValueError("Pinned code/reference mismatch: " + name)
    base = Path("/artifacts/forecast_risk_v3")
    air = {}
    metadata = []
    for fixture in protocol["source_fixtures"]:
        path = base / fixture["path"]
        if digest(path) != fixture["sha256"]:
            raise ValueError("Pinned source mismatch: " + fixture["path"])
        if not path.name.startswith("archival_aq"):
            continue
        payload = json.loads(path.read_text())
        metadata.append(
            {
                **fixture,
                "hourly_units": payload.get("hourly_units"),
                "timezone": payload.get("timezone"),
                "utc_offset_seconds": payload.get("utc_offset_seconds"),
            }
        )
        hourly = payload["hourly"]
        for i, value in enumerate(hourly["time"]):
            stamp = datetime.fromisoformat(value)
            if stamp in air:
                raise ValueError("Duplicate source timestamp")
            air[stamp] = {gas: hourly[var][i] for var, gas in GASES.items()}
    row_path = base / "rows.jsonl"
    if digest(row_path) != protocol["rows_sha256"]:
        raise ValueError("Pinned rows mismatch")
    rows = [json.loads(line) for line in row_path.read_text().splitlines()]
    if len(rows) != protocol["row_count"]:
        raise ValueError("Pinned row count mismatch")
    for row in rows:
        future = datetime.fromisoformat(row["time"]) + timedelta(hours=6)
        result = compute_naqi(air[future])
        if round(result.index, 2) != row["target_naqi"] or result.band.value != row["target_band"]:
            raise ValueError("Historical instantaneous target mismatch")
    output = {}
    for phase, bounds in protocol["windows"].items():
        start, end = map(datetime.fromisoformat, bounds)
        exclusions, transitions, drivers = Counter(), Counter(), Counter()
        supports = {
            basis: {risk: [] for risk in (201, 301, 401)}
            for basis in ("instantaneous", "complete_trailing", "conservative")
        }
        band_support = {basis: Counter() for basis in supports}
        paired, persistence_errors = [], []
        persistence_counts = Counter()
        max_identity_error = 0.0
        target_deltas = []
        for row in rows:
            t = datetime.fromisoformat(row["time"])
            if not start <= t < end:
                continue
            stamps = [t + timedelta(hours=h) for h in range(-23, 7)]
            if stamps[0] < start or stamps[-1] >= end:
                exclusions["phase_boundary"] += 1
                continue
            if any(stamp not in air for stamp in stamps):
                exclusions["missing_timestamp"] += 1
                continue
            bad = [
                gas
                for gas in GASES.values()
                if any(
                    not isinstance(air[stamp].get(gas), (int, float))
                    or not math.isfinite(air[stamp][gas])
                    or air[stamp][gas] < 0
                    for stamp in stamps
                )
            ]
            if bad:
                exclusions["invalid_concentration"] += 1
                for gas in bad:
                    exclusions["invalid_" + gas] += 1
                continue
            past = [air[stamp] for stamp in stamps[:24]]
            future = [air[stamp] for stamp in stamps[24:]]
            means = reconstruct_means(past, future)
            trailing = compute_naqi(means)
            runtime = compute_naqi_trailing(past + future)
            if runtime is None:
                raise ValueError("Complete history unexpectedly withheld")
            error = abs(runtime.result.index - trailing.index)
            max_identity_error = max(max_identity_error, error)
            if error > 1e-9 or any(
                runtime.hours_used[g] != (8 if g in ("co", "o3") else 24) for g in GASES.values()
            ):
                raise ValueError("Complete-window causal reconstruction mismatch")
            instant = compute_naqi(future[-1])
            conservative = trailing if trailing.index > instant.index else instant
            targets = {
                "instantaneous": instant,
                "complete_trailing": trailing,
                "conservative": conservative,
            }
            target_time = t + timedelta(hours=6)
            for basis, target in targets.items():
                band_support[basis][target.band.value] += 1
                for threshold in supports[basis]:
                    if round(target.index) >= threshold:
                        supports[basis][threshold].append(target_time)
            transitions[instant.band.value + "->" + trailing.band.value] += 1
            drivers[trailing.dominant_pollutant] += 1
            target_deltas.append(trailing.index - instant.index)
            persistence = compute_naqi(reconstruct_means(past, [past[-1]] * 6))
            persistence_errors.append(abs(persistence.index - trailing.index))
            positive, alarm = round(trailing.index) >= 201, round(persistence.index) >= 201
            persistence_counts[
                "tp" if positive and alarm else "fn" if positive else "fp" if alarm else "tn"
            ] += 1
            paired.append(row["time"])
        counts = persistence_counts
        output[phase] = {
            "eligible_rows": len(paired),
            "exclusions": dict(exclusions),
            "origin_times_sha256": hashlib.sha256("\n".join(paired).encode()).hexdigest(),
            "target_band_support": {key: dict(value) for key, value in band_support.items()},
            "target_risk_support": {
                basis: {str(risk): episode_support(times) for risk, times in values.items()}
                for basis, values in supports.items()
            },
            "instantaneous_to_trailing_band_transitions": dict(transitions),
            "trailing_controlling_pollutants": dict(drivers),
            "trailing_minus_instantaneous_index": {
                "mean": math.fsum(target_deltas) / len(paired) if paired else None,
                "min": min(target_deltas, default=None),
                "max": max(target_deltas, default=None),
            },
            "oracle_reconstruction_max_error": max_identity_error,
            "causal_persistence_trailing": {
                "naqi_mae": math.fsum(persistence_errors) / len(paired) if paired else None,
                "poor_plus_counts": dict(counts),
                "poor_plus_recall": counts["tp"] / (counts["tp"] + counts["fn"])
                if counts["tp"] + counts["fn"]
                else None,
                "poor_plus_precision": counts["tp"] / (counts["tp"] + counts["fp"])
                if counts["tp"] + counts["fp"]
                else None,
            },
        }
    return {
        "status": "COMPLETED",
        "canonical_target_checks": len(rows),
        "protocol": protocol,
        "source_metadata": metadata,
        "partitions": output,
        "limitations": [
            "Consumed CAMS modeled archive, not station observations",
            "Full-window period approximation, not official station AQI",
            "Persistence is the only causal forecast scored; oracle identity is arithmetic",
            "Saved neural results retain h6 only, insufficient for averaged reconstruction",
            "Zero-support recall is UNMEASURED; point Brier/ECE unavailable",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--submit", action="store_true")
    modes.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    import modal

    if args.fetch:
        if RESULT.exists():
            print("Saved result exists; preserving it.")
            return
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
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
        raise SystemExit("Existing audit manifest; refusing duplicate submission")
    dataset = json.loads((ROOT / "eval/raw/forecast_risk_v3_results.json").read_text())["dataset"]
    files = [
        Path(__file__),
        ROOT / "src/baahar/naqi.py",
        ROOT / "src/baahar/__init__.py",
        ROOT / "docs/POLLUTANT_TARGET_AUDIT_PROTOCOL.md",
    ]
    protocol = {
        "windows": WINDOWS,
        "source_fixtures": dataset["source_fixtures"],
        "rows_sha256": dataset["rows_sha256"],
        "row_count": dataset["row_count"],
        "code_sha256": {path.relative_to(ROOT).as_posix(): digest(path) for path in files},
    }
    image = modal.Image.debian_slim(python_version="3.12")
    for path in files:
        image = image.add_local_file(str(path), "/opt/" + path.relative_to(ROOT).as_posix())
    write(
        MANIFEST,
        {
            "status": "PREREGISTERED",
            "created_at": datetime.now(UTC).isoformat(),
            "protocol": protocol,
            "timeout_seconds": 600,
            "retries": 0,
        },
    )
    app = modal.App("baahar-pollutant-target-contract-v1", image=image)
    function = app.function(
        cpu=2,
        memory=4096,
        timeout=600,
        retries=0,
        max_containers=1,
        volumes={"/artifacts": modal.Volume.from_name("baahar-training")},
    )(audit_remote)
    with app.run(detach=True):
        call = function.spawn(protocol)
        manifest = json.loads(MANIFEST.read_text())
        manifest.update(status="SUBMITTED", call_id=call.object_id, app_id=app.app_id)
        write(MANIFEST, manifest)
        print(json.dumps({"call_id": call.object_id, "app_id": app.app_id}))


if __name__ == "__main__":
    main()
