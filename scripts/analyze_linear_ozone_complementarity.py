"""Compare immutable linear/TCN development predictions on identical origins."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

from baahar.naqi import band_for_index, compute_naqi

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "eval/raw"
GASES = ("pm2_5", "pm10", "nitrogen_dioxide", "ozone", "sulphur_dioxide", "carbon_monoxide")
KEYS = ("pm25", "pm10", "no2", "o3", "so2", "co")
BANDS = ("good", "satisfactory", "moderate", "poor", "severe", "hazardous")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(values):
    reading = compute_naqi(dict(zip(KEYS, values, strict=True)))
    return reading.index, BANDS.index(band_for_index(reading.index))


def score(times, actual, predicted, scales):
    truth = [canonical(row)[1] for row in actual]
    guesses = [canonical(row)[1] for row in predicted]
    matrix = [
        [sum(a == i and p == j for a, p in zip(truth, guesses, strict=True)) for j in range(6)]
        for i in range(6)
    ]
    union = sorted(set(truth) | set(guesses))
    f1 = []
    for label in union:
        tp = matrix[label][label]
        denominator = sum(matrix[label]) + sum(row[label] for row in matrix)
        f1.append(2 * tp / denominator if denominator else 0)
    risk = {}
    for threshold, name in (
        (3, "poor_or_worse"),
        (4, "very_poor_or_worse"),
        (5, "official_severe"),
    ):
        positives = [i for i, value in enumerate(truth) if value >= threshold]
        alarms = [i for i, value in enumerate(guesses) if value >= threshold]
        tp = len(set(positives) & set(alarms))
        fp = len(set(alarms) - set(positives))
        episodes = []
        for i in positives:
            if not episodes or datetime.fromisoformat(times[i]) - datetime.fromisoformat(
                times[episodes[-1][-1]]
            ) > timedelta(hours=6):
                episodes.append([])
            episodes[-1].append(i)
        risk[name] = {
            "support": len(positives),
            "misses": len(positives) - tp,
            "false_alarms": fp,
            "recall": tp / len(positives) if positives else None,
            "precision": tp / len(alarms) if alarms else None,
            "false_alarm_rate": fp / (len(times) - len(positives))
            if len(times) > len(positives)
            else None,
            "episodes": {
                "support": len(episodes),
                "any_hit": sum(any(guesses[i] >= threshold for i in e) for e in episodes),
                "onset_hit": sum(guesses[e[0]] >= threshold for e in episodes),
                "full_hit": sum(all(guesses[i] >= threshold for i in e) for e in episodes),
            },
        }
    gas = {}
    for j, name in enumerate(GASES):
        errors = [p[j] - a[j] for a, p in zip(actual, predicted, strict=True)]
        tail = [error for error, label in zip(errors, truth, strict=True) if label >= 3]
        gas[name] = {
            "mae": sum(map(abs, errors)) / len(errors),
            "rmse": math.sqrt(sum(e * e for e in errors) / len(errors)),
            "bias": sum(errors) / len(errors),
            "poor_plus_mae": sum(map(abs, tail)) / len(tail) if tail else None,
            "poor_plus_bias": sum(tail) / len(tail) if tail else None,
        }
    return {
        "rows": len(times),
        "accuracy": sum(a == p for a, p in zip(truth, guesses, strict=True)) / len(times),
        "macro_f1_actual_predicted_union": sum(f1) / len(f1),
        "confusion_matrix": matrix,
        "normalized_mae_using_probe_train_scales": sum(
            gas[g]["mae"] / s for g, s in zip(GASES, scales, strict=True)
        )
        / 6,
        "pollutant_errors": gas,
        "risk": risk,
    }


def main():
    output, report = (
        RAW / "linear_ozone_complementarity_v1.json",
        RAW / "linear_ozone_complementarity_v1.md",
    )
    if output.exists() or report.exists():
        raise FileExistsError("Saved analysis exists; never overwrite evidence")
    sources = {}
    loaded = {}
    for label, stem in (("v3", "pollutant_sequence_v3"), ("ridge", "pollutant_lag_probe_v1")):
        path = RAW / f"{stem}_results.json"
        manifest = json.loads((RAW / f"{stem}_manifest.json").read_text())
        if manifest["status"] != "COMPLETED" or manifest["result_sha256"] != digest(path):
            raise ValueError("Completed source result hash mismatch")
        sources[label] = {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": digest(path),
            "call_id": manifest["call_id"],
        }
        loaded[label] = json.loads(path.read_text())
    dev = next(p for p in loaded["v3"]["results"] if p["partition"] == "development")
    probe = loaded["ridge"]
    times = probe["development_times"]
    if len(set(times)) != len(times) or times != sorted(times):
        raise ValueError("Probe origins must be unique and chronological")
    position = {t: i for i, t in enumerate(dev["times"])}
    indexes = [position[t] for t in times]
    actual = probe["actual_pollutants"]
    for j, i in enumerate(indexes):
        index, label = canonical(actual[j])
        if actual[j] != dev["actual_pollutants"][i] or round(index, 2) != round(
            dev["actual_naqi"][i], 2
        ):
            raise ValueError("Exact paired pollutant/rounded target mismatch")
        if label != probe["actual_ordinals"][j] or BANDS[label] != dev["actual_legacy_bands"][i]:
            raise ValueError("Canonical rounded band mismatch")
    predictions = {
        "v3_fixed_mean": [
            dev["models"]["tcn_fixed_mean"]["predicted_pollutants"][i] for i in indexes
        ],
        "ridge_24h": probe["results"]["24"]["predicted_pollutants"],
    }
    predictions["fixed_ozone_hybrid"] = [
        a[:3] + [b[3]] + a[4:]
        for a, b in zip(predictions["v3_fixed_mean"], predictions["ridge_24h"], strict=True)
    ]
    for name in ("paired_lightgbm", "persistence"):
        predictions[name] = [dev["models"][name]["predicted_pollutants"][i] for i in indexes]
    metrics = {
        name: score(times, actual, pred, probe["target_scale_training_only"])
        for name, pred in predictions.items()
    }
    result = {
        "status": "COMPLETED",
        "sources": sources,
        "analysis_source_sha256": digest(Path(__file__)),
        "partition": "development",
        "rows": len(times),
        "excluded_v3_boundary_origins": dev["count"] - len(times),
        "exact_target_checks": len(times),
        "origin_times_sha256": hashlib.sha256("\n".join(times).encode()).hexdigest(),
        "actual_class_support": {
            name: sum(canonical(a)[1] == i for a in actual) for i, name in enumerate(BANDS)
        },
        "metrics": metrics,
        "times": times,
        "actual_pollutants": actual,
        "predicted_pollutants": predictions,
        "limitations": [
            "Adaptive descriptive development screen; no fit or diagnostic/test selection",
            "Probe training excludes24 boundary origins compared with V3; algorithms were not trained on identical origin sets",
            "Common macroF1 uses actual/predicted union, unlike original neural reporter",
            "Consumed CAMS/ERA5 modeled archive; no station/pristine/prospective/medical claim",
            "Legacy severe means official Very Poor; hazardous means official Severe; zero support recall UNMEASURED",
            "Point predictions have no probability calibration; Brier/ECE null",
        ],
    }
    lines = [
        "# Matched development linear ozone complementarity",
        "",
        f"Exact shared origins/targets: {len(times)}; V3 boundary origins excluded: {dev['count'] - len(times)}.",
        "",
        "Fixed hybrid substitutes Ridge ozone only, retaining V3's other five pollutants. No averaging weight or threshold sweep. Both trained forecasts are frozen; training origin sets differ by24 boundary origins.",
        "",
        "| Model | Accuracy | Common macroF1 | Poor+ misses / false alarms | Poor+ episodes / onset hits | VeryPoor+ misses / false alarms | Ozone Poor+ MAE / bias |",
        "|---|---:|---:|---|---|---|---|",
    ]
    for name, m in metrics.items():
        p, v, o = (
            m["risk"]["poor_or_worse"],
            m["risk"]["very_poor_or_worse"],
            m["pollutant_errors"]["ozone"],
        )
        lines.append(
            f"| {name} | {m['accuracy']:.6f} | {m['macro_f1_actual_predicted_union']:.6f} | {p['misses']}/{p['support']} / {p['false_alarms']} | {p['episodes']['any_hit']}/{p['episodes']['support']} / {p['episodes']['onset_hit']} | {v['misses']}/{v['support']} / {v['false_alarms']} | {o['poor_plus_mae']:.3f} / {o['poor_plus_bias']:.3f} |"
        )
    lines += [
        "",
        *result["limitations"],
        "",
        "Input/result hashes, canonical checks, exact arrays, all six gas errors and risk precision/recall/FAR/episodes are in the JSON. This screen does not establish generalization or deployment readiness.",
    ]
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
