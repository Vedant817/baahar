"""Hosted station support audit; no fitting or December acquisition."""

from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import math
import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "eval/raw/station_support_v1_manifest.json"
RESULT = ROOT / "eval/raw/station_support_v1_results.json"
BASE = "https://airquality.xkdr.org"
DOCUMENT = "https://raw.githubusercontent.com/xKDR/Air-Quality-Database/main/README.md"
PARAMETERS = {
    "PM2.5": "pm25",
    "PM10": "pm10",
    "NO2": "no2",
    "SO2": "so2",
    "Ozone": "o3",
    "CO": "co",
}
WINDOWS = {"train": ["2024-01-01", "2024-10-01"], "development": ["2024-10-01", "2024-12-01"]}
MASS_UNITS = {"µg/m³", "μg/m³"}
CO_UNITS = {"mg/m³"}


def normalize_value(parameter, unit, value):
    if unit not in (CO_UNITS if parameter == "CO" else MASS_UNITS):
        raise ValueError("Unrecognized parameter-specific unit")
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value < 0
    ):
        return None
    return value * (1000 if parameter == "CO" else 1)


def eligible_window(t, start, end, indexed):
    if t - timedelta(hours=23) < start or t + timedelta(hours=6) >= end:
        return "phase_boundary"
    stamps = [t + timedelta(hours=h) for h in range(-23, 7)]
    if any(indexed.get((s, gas)) is None for s in stamps for gas in PARAMETERS.values()):
        return "incomplete_or_invalid_sequence"
    return None


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)


def episodes(stamps):
    groups = []
    for stamp in sorted(stamps):
        if not groups or stamp - groups[-1][-1] > timedelta(hours=6):
            groups.append([])
        groups[-1].append(stamp)
    return {"hours": len(stamps), "episodes": len(groups), "recall": None}


def audit_remote(protocol):
    import sys

    sys.path.insert(0, "/opt/src")
    import modal

    from baahar.naqi import AVERAGING_PERIOD_HOURS, compute_naqi

    for rel, expected in protocol["source_sha256"].items():
        if digest(Path("/opt") / rel) != expected:
            raise ValueError("Pinned source hash mismatch")
    volume = modal.Volume.from_name("baahar-training")
    destination = Path("/artifacts/station_support_v1")
    destination.mkdir(exist_ok=False)
    request = Request(DOCUMENT, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        document = response.read().decode("utf-8")
    match = re.search(r"aqi_demo_[A-Za-z0-9_-]+", document)
    if match is None:
        raise RuntimeError("Publisher documented public demo unavailable")
    credential = match.group()
    records, sources = [], []
    for month in range(1, 12):
        last = calendar.monthrange(2024, month)[1]
        query = "&".join("parameter=" + name for name in PARAMETERS)
        url = (
            BASE
            + "/v1/measurements?station=site_162&"
            + query
            + f"&start=2024-{month:02d}-01&end=2024-{month:02d}-{last:02d}"
            + "&agg=raw&format=json&limit=4464"
        )
        request = Request(
            url,
            headers={
                "Authorization": "Bearer " + credential,
                "User-Agent": "Baahar station support audit",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read(4_000_001)
                truncated = response.headers.get("X-Truncated")
        except Exception:
            raise RuntimeError(f"Station HTTP request failed month={month}; no retry") from None
        if len(raw) > 4_000_000:
            raise ValueError("Oversized monthly response")
        path = destination / f"source_2024_{month:02d}.json"
        with path.open("xb") as handle:
            handle.write(raw)
        volume.commit()
        payload = json.loads(raw)
        meta, data = payload["meta"], payload["data"]
        if meta.get("truncated") or str(truncated).lower() == "true":
            raise ValueError("Truncated monthly response")
        if meta.get("timezone") != "IST (UTC+05:30), naive timestamps":
            raise ValueError("Unexpected source timestamp interpretation")
        if len(data) > 4464 or meta["rows"] != len(data):
            raise ValueError("Response count mismatch")
        sources.append(
            {"url": url, "volume_path": str(path), "sha256": digest(path), "rows": len(data)}
        )
        records.extend(data)
    del credential, document, match
    indexed, duplicates, negatives, nonfinite, units = (
        {},
        Counter(),
        Counter(),
        Counter(),
        Counter(),
    )
    for record in records:
        if record["station_id"] != "site_162" or record["parameter_name"] not in PARAMETERS:
            raise ValueError("Unexpected station or parameter")
        stamp = datetime.fromisoformat(record["collected_at"])
        if (
            stamp.tzinfo is not None
            or stamp.minute
            or stamp.second
            or stamp.microsecond
            or not datetime(2024, 1, 1) <= stamp < datetime(2024, 12, 1)
        ):
            raise ValueError("Unexpected hourly IST timestamp or reserved December record")
        parameter, unit, value = record["parameter_name"], record["unit"], record["value"]
        normalized = normalize_value(parameter, unit, value)
        units[parameter + ":" + unit] += 1
        key = (stamp, PARAMETERS[parameter])
        if key in indexed:
            duplicates[parameter] += 1
            indexed[key] = None
        elif (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
        ):
            nonfinite[parameter] += 1
            indexed[key] = None
        elif value < 0:
            negatives[parameter] += 1
            indexed[key] = None
        else:
            indexed[key] = normalized
    support = {}
    for name, bounds in WINDOWS.items():
        start, end = map(datetime.fromisoformat, bounds)
        times = [
            start + timedelta(hours=h) for h in range(int((end - start).total_seconds() / 3600))
        ]
        missing = {gas: sum((t, gas) not in indexed for t in times) for gas in PARAMETERS.values()}
        invalid = {
            gas: sum((t, gas) in indexed and indexed[t, gas] is None for t in times)
            for gas in PARAMETERS.values()
        }
        eligible, indices = [], {"instantaneous": [], "strict_trailing": []}
        excluded = Counter()
        for t in times:
            reason = eligible_window(t, start, end, indexed)
            if reason:
                excluded[reason] += 1
                continue
            target = t + timedelta(hours=6)
            instantaneous = {gas: indexed[target, gas] for gas in PARAMETERS.values()}
            trailing = {
                gas: sum(
                    indexed[target - timedelta(hours=h), gas]
                    for h in range(AVERAGING_PERIOD_HOURS[gas])
                )
                / AVERAGING_PERIOD_HOURS[gas]
                for gas in PARAMETERS.values()
            }
            eligible.append(t)
            indices["instantaneous"].append((target, compute_naqi(instantaneous).index))
            indices["strict_trailing"].append((target, compute_naqi(trailing).index))
        support[name] = {
            "candidate_origins": len(times),
            "eligible_origins": len(eligible),
            "exclusions": dict(excluded),
            "missing_values": missing,
            "invalid_values": invalid,
            "origins_sha256": hashlib.sha256(
                "\n".join(t.isoformat() for t in eligible).encode()
            ).hexdigest(),
            "targets": {
                basis: {
                    label: episodes([t for t, index in values if int(round(index)) >= threshold])
                    for label, threshold in [
                        ("poor_or_worse", 201),
                        ("very_poor_or_worse", 301),
                        ("official_severe", 401),
                    ]
                }
                for basis, values in indices.items()
            },
        }
    result = {
        "status": "COMPLETED",
        "station": "site_162",
        "timezone": "Asia/Kolkata",
        "sources": sources,
        "raw_rows": len(records),
        "duplicates_by_parameter": dict(duplicates),
        "negative_by_parameter": dict(negatives),
        "nonfinite_by_parameter": dict(nonfinite),
        "raw_unit_counts": dict(units),
        "support": support,
        "reserved_period": "December 2024 excluded before fetch",
        "limitations": [
            "Preliminary station-derived source; no prospective/medical qualification",
            "Only six pollutants; NH3/Pb absent",
            "Complete trailing windows do not prove official station AQI qualification",
            "No fitting; recalls unmeasured; correlated six-hour-gap episodes",
        ],
    }
    write_new(destination / "summary.json", result)
    volume.commit()
    return result


def main():
    import modal

    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--submit", action="store_true")
    mode.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    if args.fetch:
        if RESULT.exists():
            print("Saved result exists; preserving it")
            return
        manifest = json.loads(MANIFEST.read_text())
        if manifest.get("status") != "SUBMITTED":
            raise SystemExit("No submitted call; refusing fetch")
        try:
            result = modal.FunctionCall.from_id(manifest["call_id"]).get(timeout=5)
        except (TimeoutError, modal.exception.TimeoutError):
            print("PENDING " + manifest["call_id"])
            return
        write_new(RESULT, result)
        manifest.update(status="COMPLETED", result_sha256=digest(RESULT))
        MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print("COMPLETED " + str(RESULT))
        return
    if MANIFEST.exists():
        raise SystemExit("Existing manifest; refusing duplicate submission")
    files = [
        Path(__file__),
        ROOT / "src/baahar/naqi.py",
        ROOT / "src/baahar/__init__.py",
        ROOT / "data/samples/station_source_probe_v1.json",
        ROOT / "docs/STATION_SUPPORT_V1_PROTOCOL.md",
    ]
    protocol = {
        "station": "site_162",
        "windows": WINDOWS,
        "months": list(range(1, 12)),
        "source_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in files},
        "public_document": DOCUMENT,
        "license_url": BASE + "/",
        "unit_documentation_url": BASE + "/#about",
    }
    image = modal.Image.debian_slim(python_version="3.12")
    for path in files:
        image = image.add_local_file(str(path), "/opt/" + path.relative_to(ROOT).as_posix())
    write_new(
        MANIFEST,
        {
            "status": "PREREGISTERED",
            "created_at": datetime.now(UTC).isoformat(),
            "protocol": protocol,
            "timeout_seconds": 1800,
            "retries": 0,
        },
    )
    app = modal.App("baahar-station-support-v1", image=image)
    function = app.function(
        cpu=2,
        memory=2048,
        timeout=1800,
        retries=0,
        max_containers=1,
        volumes={"/artifacts": modal.Volume.from_name("baahar-training")},
    )(audit_remote)
    with app.run(detach=True):
        call = function.spawn(protocol)
        manifest = json.loads(MANIFEST.read_text())
        manifest.update(status="SUBMITTED", call_id=call.object_id, app_id=app.app_id)
        MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps({"call_id": call.object_id, "app_id": app.app_id}))


if __name__ == "__main__":
    main()
