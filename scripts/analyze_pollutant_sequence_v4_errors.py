"""Compare saved v3/v4 endpoint errors without reading or fitting archive data."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "eval/raw"
OUTPUT = RAW / "pollutant_sequence_v4_error_analysis.json"
REPORT = RAW / "pollutant_sequence_v4_error_analysis.md"
GASES = ("pm2_5", "pm10", "nitrogen_dioxide", "ozone", "sulphur_dioxide", "carbon_monoxide")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ordinal(label: str) -> int:
    return ("good", "satisfactory", "moderate", "poor", "severe", "hazardous").index(label)


def episodes(period: dict) -> list[dict]:
    positives = [
        (i, datetime.fromisoformat(t))
        for i, (t, b) in enumerate(zip(period["times"], period["actual_legacy_bands"], strict=True))
        if ordinal(b) >= 3
    ]
    groups: list[list[tuple[int, datetime]]] = []
    for point in positives:
        if not groups or point[1] - groups[-1][-1][1] > timedelta(hours=6):
            groups.append([])
        groups[-1].append(point)
    output = []
    for group in groups:
        indexes = [i for i, _ in group]
        result = {
            "start": group[0][1].isoformat(),
            "end": group[-1][1].isoformat(),
            "positive_hours": len(group),
            "peak_actual_naqi": max(period["actual_naqi"][i] for i in indexes),
        }
        for name in ("v3_fixed_mean", "v4_fixed_mean"):
            hits = [
                i
                for i in indexes
                if ordinal(period["models"][name]["predicted_legacy_bands"][i]) >= 3
            ]
            result[name] = {
                "hit_hours": len(hits),
                "hit": bool(hits),
                "onset_hit": bool(hits and hits[0] == indexes[0]),
                "full_hit": len(hits) == len(indexes),
            }
        output.append(result)
    return output


def gas_errors(period: dict, mask: list[bool]) -> dict:
    result = {}
    for name in ("v3_fixed_mean", "v4_fixed_mean"):
        result[name] = {}
        for g, gas in enumerate(GASES):
            pairs = [
                (truth[g], pred[g])
                for truth, pred, keep in zip(
                    period["actual_pollutants"],
                    period["models"][name]["predicted_pollutants"],
                    mask,
                    strict=True,
                )
                if keep
            ]
            errors = [pred - truth for truth, pred in pairs]
            result[name][gas] = {
                "count": len(errors),
                "mae": None if not errors else sum(abs(e) for e in errors) / len(errors),
                "bias_prediction_minus_actual": None if not errors else sum(errors) / len(errors),
            }
    return result


def analyze_period(p3: dict, p4: dict) -> dict:
    if p3["partition"] != p4["partition"]:
        raise ValueError("Paired period names differ")
    for key in ("times", "actual_naqi", "actual_legacy_bands", "actual_pollutants"):
        if p3[key] != p4[key]:
            raise ValueError("Paired source targets differ: " + key)
    if p3["count"] != p4["count"] or p3["count"] != len(p3["times"]):
        raise ValueError("Paired row counts differ")
    paired = {
        **p3,
        "models": {
            "v3_fixed_mean": p3["models"]["tcn_fixed_mean"],
            "v4_fixed_mean": p4["models"]["tcn_fixed_mean"],
        },
    }
    poor = [ordinal(b) >= 3 for b in p3["actual_legacy_bands"]]
    ordinary = [not x for x in poor]
    transitions = {"both_hit": 0, "v3_only": 0, "v4_only": 0, "both_miss": 0}
    for i, actual in enumerate(poor):
        if not actual:
            continue
        a = ordinal(paired["models"]["v3_fixed_mean"]["predicted_legacy_bands"][i]) >= 3
        b = ordinal(paired["models"]["v4_fixed_mean"]["predicted_legacy_bands"][i]) >= 3
        transitions[
            "both_hit" if a and b else "v3_only" if a else "v4_only" if b else "both_miss"
        ] += 1
    false_alarm = {}
    for name in ("v3_fixed_mean", "v4_fixed_mean"):
        false_alarm[name] = sum(
            ordinal(paired["models"][name]["predicted_legacy_bands"][i]) >= 3 and ordinary[i]
            for i in range(len(ordinary))
        )
    return {
        "partition": p3["partition"],
        "n": p3["count"],
        "poor_or_worse_support": sum(poor),
        "hour_transitions_on_actual_poor_plus": transitions,
        "poor_false_alarms": false_alarm,
        "episodes": episodes(paired),
        "gas_errors_on_poor_plus": gas_errors(paired, poor),
        "gas_errors_on_below_poor": gas_errors(paired, ordinary),
    }


def main() -> None:
    manifests, results = {}, {}
    for version in ("v3", "v4"):
        stem = RAW / f"pollutant_sequence_{version}"
        manifest = json.loads(Path(str(stem) + "_manifest.json").read_text(encoding="utf-8"))
        raw = Path(str(stem) + "_results.json")
        if manifest["status"] != "COMPLETED" or digest(raw) != manifest["result_sha256"]:
            raise ValueError(f"{version} artifact status/hash mismatch")
        manifests[version] = {
            "manifest": str(stem.relative_to(ROOT).as_posix()) + "_manifest.json",
            "result_sha256": manifest["result_sha256"],
        }
        results[version] = json.loads(raw.read_text(encoding="utf-8"))["results"]
    v3 = {p["partition"]: p for p in results["v3"]}
    v4 = {p["partition"]: p for p in results["v4"]}
    periods = [
        analyze_period(v3[name], v4[name])
        for name in v3
        if name.startswith(("development", "diagnostic"))
    ]
    output = {
        "status": "COMPLETED_READ_ONLY_ERROR_ANALYSIS",
        "manifests": manifests,
        "periods": periods,
        "limitations": [
            "Uses only already-saved sixth-horizon endpoint predictions; no other horizon claims",
            "Development and 2026 diagnostics have been adaptively consumed",
            "CAMS/ERA5 modeled archive, not independent station or prospective evidence",
        ],
    }
    if OUTPUT.exists() or REPORT.exists():
        raise FileExistsError("Preserving existing error-analysis artifact")
    OUTPUT.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    lines = [
        "# Paired v3/v4 saved-prediction error analysis",
        "",
        "Uses only saved final-sixth-hour arrays, verifies identical actual rows/targets, and does not refit.",
        "The development set and both 2026 diagnostics are adaptively consumed modeled archive.",
        "",
    ]
    for p in periods:
        lines += [
            f"## {p['partition']} (n={p['n']}, Poor+ support={p['poor_or_worse_support']})",
            "",
            f"Hour transitions: `{json.dumps(p['hour_transitions_on_actual_poor_plus'])}`",
            f"Poor+ false alarms: `{json.dumps(p['poor_false_alarms'])}`",
            "",
            "| Episode | Hours | Peak actual proxy | v3 hit hours | v4 hit hours | v3 onset | v4 onset |",
            "|---|---:|---:|---:|---:|---|---|",
        ]
        for e in p["episodes"]:
            lines.append(
                f"| {e['start']} to {e['end']} | {e['positive_hours']} | {e['peak_actual_naqi']:.2f} | "
                f"{e['v3_fixed_mean']['hit_hours']} | {e['v4_fixed_mean']['hit_hours']} | "
                f"{e['v3_fixed_mean']['onset_hit']} | {e['v4_fixed_mean']['onset_hit']} |"
            )
        for section in ("gas_errors_on_poor_plus", "gas_errors_on_below_poor"):
            lines += [
                "",
                f"### {section.replace('_', ' ')}",
                "",
                "| Gas | v3 MAE / bias | v4 MAE / bias |",
                "|---|---:|---:|",
            ]
            for gas in GASES:
                a, b = p[section]["v3_fixed_mean"][gas], p[section]["v4_fixed_mean"][gas]
                lines.append(
                    f"| {gas} (n={a['count']}) | {a['mae']} / {a['bias_prediction_minus_actual']} | "
                    f"{b['mae']} / {b['bias_prediction_minus_actual']} |"
                )
        lines.append("")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote saved-output-only analysis: {REPORT}")


if __name__ == "__main__":
    main()
