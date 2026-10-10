"""Summarize fetched v3 coverage diagnostics without fetching or fitting."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "eval/raw"


def main():
    source = RAW / "forecast_risk_v3_results.json"
    output = RAW / "forecast_risk_v3_completion_summary.json"
    if output.exists():
        print("Coverage summary already exists; not overwriting")
        return
    result = json.loads(source.read_text(encoding="utf-8"))
    manifest = json.loads((RAW / "forecast_risk_v3_manifest.json").read_text(encoding="utf-8"))
    if manifest["status"] != "COMPLETED":
        raise ValueError("Cannot summarize an incomplete manifest")
    periods = []
    for period in result["results"]:
        periods.append(
            {
                "partition": period["partition"],
                "n": period["n"],
                "models": {
                    name: {
                        key: model[key]
                        for key in (
                            "classification",
                            "risk",
                            "severe_or_worse",
                            "training_partition",
                            "training_unsupported_classes",
                            "probability_note",
                        )
                    }
                    for name, model in period["models"].items()
                },
            }
        )
    summary = {
        "status": "COMPLETED",
        "call_id": manifest["call_id"],
        "app_id": manifest["app_id"],
        "raw_result_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "dataset": result["dataset"],
        "resolved_partitions": result["resolved_partitions"],
        "partition_support": result["partition_support"],
        "periods": periods,
        "limitations": manifest["limitations"],
        "disposition": "RESEARCH_ONLY_NO_PROMOTION",
    }
    output.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    lines = [
        "## V3 coverage ablation completed",
        "",
        "Fixed configurations compare 2023-only training against January 2023–May 2025 training. "
        "The latter includes previously evaluated 2025 examples. The 2026 periods have informed "
        "prior research and are consumed temporal diagnostics, not independent holdouts.",
        "",
        "| Period | Model | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ recall | Poor+ FAR | Severe+ misses/support | Severe+ recall | Severe+ FAR |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for p in periods:
        for name, model in p["models"].items():
            c, r, s = model["classification"], model["risk"], model["severe_or_worse"]
            lines.append(
                f"| {p['partition']} | {name} | {c['accuracy']} | {c['macro_f1']} | "
                f"{r['misses']}/{r['positive_support']} | {r['recall']} | {r['false_alarm_rate']} | "
                f"{s['misses']}/{s['positive_support']} | {s['recall']} | {s['false_alarm_rate']} |"
            )
    lines += [
        "",
        "### Coverage and episodes",
        "",
        "```json",
        json.dumps(result["partition_support"], indent=2),
        "```",
        "",
        "Adjacent polluted hours are correlated; episode counts use a six-hour separation rule "
        "and are descriptive, not independent-event validation. Absent positive support means "
        "recall is unmeasured. Models with no training support cannot establish that class's performance.",
        "",
        "All LightGBM probabilities are uncalibrated; ensemble and persistence probability-style "
        "metrics use binary decisions. Full precision, Brier, ECE and reliability bins are retained "
        "in the raw result and completion summary. No weather-policy accuracy is assessed. "
        "CAMS/ERA5 archives are modeled data, not station observations. Human review, field evidence "
        "and actual billing are unmeasured. No model was promoted or deployed.",
    ]
    report = RAW / "forecast_risk_v3_completion_summary.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    links = {
        ROOT / "docs/MODEL_QUALIFICATION_PROGRESS.md": "../eval/raw/",
        ROOT / "eval/RESULTS.md": "raw/",
        ROOT / "post.md": "eval/raw/",
    }
    for path, prefix in links.items():
        if "## V3 coverage ablation completed" in path.read_text(encoding="utf-8"):
            continue
        with path.open("a", encoding="utf-8") as f:
            f.write(
                "\n\n"
                + "\n".join(lines[:6])
                + "\n"
                + "\n".join(lines[6 : 6 + sum(len(p["models"]) for p in periods)])
                + f"\n\nFull measured class support, episode counts, precision and probability diagnostics: "
                f"[completion report]({prefix}forecast_risk_v3_completion_summary.md), "
                f"[raw results]({prefix}forecast_risk_v3_results.json). "
                "These are consumed modeled archive diagnostics with correlated hours and uncalibrated "
                "probabilities. No automatic adoption, human review, field test or measured billing is claimed.\n"
            )
    print("Wrote v3 completion summary/report and updated qualification, results, and post draft")


if __name__ == "__main__":
    main()
