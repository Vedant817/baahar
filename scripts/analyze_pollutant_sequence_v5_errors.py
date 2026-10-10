"""Attribute saved V3/V5 endpoint errors by event phase and controlling gas."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from baahar.naqi import compute_naqi

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "eval/raw"
OUTPUT = RAW / "pollutant_sequence_v5_error_analysis.json"
REPORT = RAW / "pollutant_sequence_v5_error_analysis.md"
GASES = ("pm2_5", "pm10", "nitrogen_dioxide", "ozone", "sulphur_dioxide", "carbon_monoxide")
KEYS = ("pm25", "pm10", "no2", "o3", "so2", "co")
ORDINALS = ("good", "satisfactory", "moderate", "poor", "severe", "hazardous")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ordinal(value: str) -> int:
    return ORDINALS.index(value)


def gas_errors(period: dict, name: str, mask: list[bool]) -> dict:
    output = {}
    for index, gas in enumerate(GASES):
        errors = [
            pred[index] - actual[index]
            for pred, actual, keep in zip(
                period["models"][name]["predicted_pollutants"],
                period["actual_pollutants"],
                mask,
                strict=True,
            )
            if keep
        ]
        output[gas] = {
            "count": len(errors),
            "mae": sum(abs(value) for value in errors) / len(errors) if errors else None,
            "bias_prediction_minus_actual": sum(errors) / len(errors) if errors else None,
        }
    return output


def analyze(period: dict) -> dict:
    n = period["count"]
    fields = ("times", "actual_naqi", "actual_legacy_bands", "actual_pollutants")
    if not all(len(period[key]) == n for key in fields):
        raise ValueError("Actual endpoint arrays do not align")
    labels = period["actual_legacy_bands"]
    dominant = [
        compute_naqi(dict(zip(KEYS, values, strict=True))).dominant_pollutant
        for values in period["actual_pollutants"]
    ]
    poor = [ordinal(label) >= 3 for label in labels]
    episodes: list[list[int]] = []
    for index, stamp in enumerate(period["times"]):
        if not poor[index]:
            continue
        moment = datetime.fromisoformat(stamp)
        if not episodes or moment - datetime.fromisoformat(
            period["times"][episodes[-1][-1]]
        ) > timedelta(hours=6):
            episodes.append([])
        episodes[-1].append(index)
    phase_by_index = {}
    episode_rows = []
    for number, indexes in enumerate(episodes, start=1):
        peak = max(indexes, key=lambda i: period["actual_naqi"][i])
        for index in indexes:
            phase_by_index[index] = (
                "onset"
                if index == indexes[0]
                else "peak"
                if index == peak
                else "rising"
                if index < peak
                else "falling"
            )
        row = {
            "episode": number,
            "start": period["times"][indexes[0]],
            "end": period["times"][indexes[-1]],
            "positive_hours": len(indexes),
            "peak_time": period["times"][peak],
            "peak_actual_naqi": period["actual_naqi"][peak],
            "dominant_at_peak": dominant[peak],
        }
        for name, label in (("v3_fixed_mean", "v3"), ("tcn_fixed_mean", "v5")):
            hits = [
                i
                for i in indexes
                if ordinal(period["models"][name]["predicted_legacy_bands"][i]) >= 3
            ]
            row[label] = {
                "hit_hours": len(hits),
                "any_hit": bool(hits),
                "onset_hit": bool(hits and hits[0] == indexes[0]),
                "full_hit": len(hits) == len(indexes),
            }
        episode_rows.append(row)
    by_phase, by_gas = {}, {}
    for name, short in (("v3_fixed_mean", "v3"), ("tcn_fixed_mean", "v5")):
        predictions = period["models"][name]["predicted_legacy_bands"]
        phase_counts, gas_counts = Counter(), Counter()
        for i in (j for j, value in enumerate(poor) if value):
            missed = ordinal(predictions[i]) < 3
            phase_counts[(phase_by_index[i], "miss" if missed else "hit")] += 1
            if missed:
                gas_counts[dominant[i] or "unknown"] += 1
        by_phase[short] = {
            f"{phase}_{outcome}": count for (phase, outcome), count in sorted(phase_counts.items())
        }
        by_gas[short] = dict(sorted(gas_counts.items()))
    return {
        "partition": period["partition"],
        "rows": n,
        "poor_plus_hours": sum(poor),
        "actual_controlling_gas_on_poor_plus": dict(
            Counter(dominant[i] for i, ok in enumerate(poor) if ok)
        ),
        "missed_hours_by_episode_phase": by_phase,
        "missed_hours_by_actual_controlling_gas": by_gas,
        "episodes": episode_rows,
        "gas_errors_on_poor_plus": {
            "v3": gas_errors(period, "v3_fixed_mean", poor),
            "v5": gas_errors(period, "tcn_fixed_mean", poor),
        },
    }


def main() -> None:
    sources, periods = {}, {}
    for version in ("v3", "v5"):
        stem = RAW / f"pollutant_sequence_{version}"
        manifest = json.loads(Path(str(stem) + "_manifest.json").read_text(encoding="utf-8"))
        result_path = Path(str(stem) + "_results.json")
        if manifest["status"] != "COMPLETED" or digest(result_path) != manifest["result_sha256"]:
            raise ValueError(f"{version} completion/hash mismatch")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        sources[version] = {
            "call_id": manifest["call_id"],
            "result_sha256": manifest["result_sha256"],
        }
        periods[version] = {item["partition"]: item for item in result["results"]}
    measured = []
    names = [
        name for name in periods["v3"] if name == "development" or name.startswith("diagnostic_")
    ]
    for name in names:
        reference, candidate = periods["v3"][name], periods["v5"][name]
        if reference["count"] != candidate["count"] or any(
            reference[key] != candidate[key]
            for key in ("times", "actual_naqi", "actual_legacy_bands", "actual_pollutants")
        ):
            raise ValueError("V3/V5 paired origins or actual targets differ: " + name)
        paired = {
            **reference,
            "models": {
                "v3_fixed_mean": reference["models"]["tcn_fixed_mean"],
                "tcn_fixed_mean": candidate["models"]["tcn_fixed_mean"],
            },
        }
        measured.append(analyze(paired))
    if OUTPUT.exists() or REPORT.exists():
        raise FileExistsError("Preserving existing V5 error analysis")
    payload = {
        "status": "COMPLETED_SAVED_OUTPUT_ANALYSIS",
        "sources": sources,
        "periods": measured,
        "limitations": [
            "Only saved sixth-horizon outputs; no refitting or other-horizon claims",
            "Development and diagnostics are consumed/adaptive CAMS/ERA5 modeled archive",
            "Controlling-gas attribution is an hourly CPCB instantaneous proxy, not station-grade cause",
        ],
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    lines = [
        "# V3/V5 saved-output error attribution",
        "",
        "This reads saved final-sixth-hour predictions only and verifies exact paired target arrays. "
        "Development is the descriptive lead section; diagnostic summaries were consumed and were not used "
        "to select another fit.",
        "",
    ]
    for item in measured:
        lines += [
            f"## {item['partition']} (n={item['rows']}, Poor+ hours={item['poor_plus_hours']})",
            "",
            f"Controlling pollutants on actual Poor+ hours: {json.dumps(item['actual_controlling_gas_on_poor_plus'])}",
            "",
            f"Misses by phase: {json.dumps(item['missed_hours_by_episode_phase'])}",
            "",
            f"Misses by controlling gas: {json.dumps(item['missed_hours_by_actual_controlling_gas'])}",
            "",
            "| Episode | Positive hours | Peak NAQI / controlling pollutant | V3 hit hours | V5 hit hours | V3 onset | V5 onset |",
            "|---|---:|---|---:|---:|---|---|",
        ]
        for episode in item["episodes"]:
            lines.append(
                f"| {episode['start']} to {episode['end']} | {episode['positive_hours']} | "
                f"{episode['peak_actual_naqi']:.2f} / {episode['dominant_at_peak']} | "
                f"{episode['v3']['hit_hours']} | {episode['v5']['hit_hours']} | "
                f"{episode['v3']['onset_hit']} | {episode['v5']['onset_hit']} |"
            )
        lines += ["", "| Pollutant | V3 MAE / bias | V5 MAE / bias |", "|---|---:|---:|"]
        for gas in GASES:
            a, b = (
                item["gas_errors_on_poor_plus"]["v3"][gas],
                item["gas_errors_on_poor_plus"]["v5"][gas],
            )
            lines.append(
                f"| {gas} (n={a['count']}) | {a['mae']} / {a['bias_prediction_minus_actual']} | "
                f"{b['mae']} / {b['bias_prediction_minus_actual']} |"
            )
        lines.append("")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote saved-output-only V5 error analysis: {REPORT}")


if __name__ == "__main__":
    main()
