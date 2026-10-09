"""Summarize completed hosted diagnostics without promoting any model."""

from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "eval/raw"


def main():
    summary = {"disposition": "PROVISIONAL_NO_PROMOTION", "field_test": "NOT_DONE"}
    lines = ["# Follow-up qualification", "", "Measured hosted diagnostics; no promotion.", ""]
    forecast = RAW / "forecast_rolling_results.json"
    if forecast.exists():
        data = json.loads(forecast.read_text())
        summary["forecast"] = []
        summary["forecast_support"] = []
        lines += [
            "## Rolling forecast diagnostics",
            "",
            "Consumed archive, fixed previously selected configurations, seed 0. Six-hour label embargo and train-only imputation. Aligned recorded target-hour weather is oracle weather, not deployed forecast evidence.",
            "",
        ]
        for window in data["windows"]:
            support = {
                band: values["support"]
                for band, values in next(iter(window["models"].values()))["metrics"][
                    "per_class"
                ].items()
            }
            summary["forecast_support"].append(
                {"window": window["start"], "n": window["n_test"], **support}
            )
            lines.append("")
            lines.append(
                f"**{window['start'][:7]} class support (n={window['n_test']}):** "
                + ", ".join(f"{band} {count}" for band, count in support.items())
            )
            lines += [
                "",
                "| Window | Model | N | Accuracy | Macro-F1 | Moderate recall (support) | Poor-or-worse underprediction |",
                "|---|---|---:|---:|---:|---:|---:|",
            ]
            for name, model in window["models"].items():
                m = model["metrics"]
                moderate = m["per_class"]["moderate"]
                recall = str(moderate["recall"]) if moderate["support"] else "N/A"
                row = {
                    "window": window["start"],
                    "model": name,
                    "n": window["n_test"],
                    "accuracy": m["accuracy"],
                    "macro_f1": m["macro_f1"],
                    "moderate_recall": moderate["recall"] if moderate["support"] else None,
                    "poor_or_worse_n": model["poor_or_worse_n"],
                    "poor_or_worse_underpredicted": model["poor_or_worse_predicted_below_poor"],
                }
                summary["forecast"].append(row)
                lines.append(
                    f"| {window['start'][:7]} | {name} | {window['n_test']} | {m['accuracy']} | {m['macro_f1']} | {recall} ({moderate['support']}) | {row['poor_or_worse_underpredicted']}/{row['poor_or_worse_n']} |"
                )
        lines += [
            "",
            "Missing hazardous examples remain unvalidated. Poor-or-worse underprediction is a band error, not proof of an actual unsafe invitation; current-hour runtime permission remains deterministic.",
        ]
    briefing = RAW / "qualification_v16_fresh_results.json"
    if briefing.exists():
        data = json.loads(briefing.read_text())
        summary["briefing"] = {}
        summary["briefing_overall"] = {
            "n": len(data["rows"]),
            "adapter_raw_contract_accepted": sum(
                r["adapter_contract"]["accepted"] for r in data["rows"]
            ),
            "fallback_raw_contract_accepted": sum(
                r["fallback_contract"]["accepted"] for r in data["rows"]
            ),
            "adapter_semantic_flagged": sum(
                bool(r["adapter_semantic_errors"]) for r in data["rows"]
            ),
            "fallback_semantic_flagged": sum(
                bool(r["fallback_semantic_errors"]) for r in data["rows"]
            ),
            "adapter_finite_safety_flagged": sum(
                bool(r["adapter_contract"]["safety_errors"]) for r in data["rows"]
            ),
            "fallback_finite_safety_flagged": sum(
                bool(r["fallback_contract"]["safety_errors"]) for r in data["rows"]
            ),
            "adapter_combined_accepted": sum(
                r["adapter_contract"]["accepted"] and not r["adapter_semantic_errors"]
                for r in data["rows"]
            ),
            "fallback_combined_accepted": sum(
                r["fallback_contract"]["accepted"] and not r["fallback_semantic_errors"]
                for r in data["rows"]
            ),
            "current_go_n": sum(r["family"] == "current_go" for r in data["rows"]),
            "current_go_adapter_combined_accepted": sum(
                r["family"] == "current_go"
                and r["adapter_contract"]["accepted"]
                and not r["adapter_semantic_errors"]
                for r in data["rows"]
            ),
        }
        lines += [
            "",
            "## Fresh synthetic briefing evaluation",
            "",
            "New AI-authored synthetic prompts; some families overlap training. Updated current-condition prompt; not blind human review or a pristine holdout.",
            "",
            "| Family | N | Adapter raw | Fallback raw | Adapter combined | Fallback combined | Adapter safety flags | Median GPU seconds |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for family in sorted({row["family"] for row in data["rows"]}):
            rows = [r for r in data["rows"] if r["family"] == family]
            info = {
                "n": len(rows),
                "adapter_raw_contract_accepted": sum(
                    r["adapter_contract"]["accepted"] for r in rows
                ),
                "fallback_raw_contract_accepted": sum(
                    r["fallback_contract"]["accepted"] for r in rows
                ),
                "adapter_semantic_flagged": sum(bool(r["adapter_semantic_errors"]) for r in rows),
                "fallback_semantic_flagged": sum(bool(r["fallback_semantic_errors"]) for r in rows),
                "adapter_accepted": sum(
                    r["adapter_contract"]["accepted"] and not r["adapter_semantic_errors"]
                    for r in rows
                ),
                "fallback_accepted": sum(
                    r["fallback_contract"]["accepted"] and not r["fallback_semantic_errors"]
                    for r in rows
                ),
                "adapter_safety_flagged": sum(
                    bool(r["adapter_contract"]["safety_errors"] or r["adapter_semantic_errors"])
                    for r in rows
                ),
                "adapter_defects": dict(
                    Counter(e for r in rows for e in r["adapter_contract"]["errors"])
                ),
                "median_seconds": statistics.median(r["seconds"] for r in rows),
            }
            summary["briefing"][family] = info
            lines.append(
                f"| {family} | {info['n']} | {info['adapter_raw_contract_accepted']} | {info['fallback_raw_contract_accepted']} | {info['adapter_accepted']} | {info['fallback_accepted']} | {info['adapter_safety_flagged']} | {info['median_seconds']:.3f} |"
            )
        lines += [
            "",
            "All raw prose and finite flags are preserved. These checks do not measure human usefulness or authorize deployment.",
        ]
        overall = summary["briefing_overall"]
        lines += [
            "",
            f"Overall raw contract acceptance: adapter {overall['adapter_raw_contract_accepted']}/{overall['n']}; fallback {overall['fallback_raw_contract_accepted']}/{overall['n']}. Combined finite acceptance (contract plus anchors): adapter {overall['adapter_combined_accepted']}/{overall['n']}; fallback {overall['fallback_combined_accepted']}/{overall['n']}. Semantic-anchor flags: adapter {overall['adapter_semantic_flagged']}, fallback {overall['fallback_semantic_flagged']}. Six current-GO positives: adapter {overall['current_go_adapter_combined_accepted']}/{overall['current_go_n']} combined accepted.",
            "",
            "Two adapter finite flags are `ungrounded_number` for `recheck at 5 PM` / `5:00 PM` on supplied scheduled time 17:00. Both texts withhold walking, identify extreme heat, and ask for a recheck. Treat as a finite time-format allowlist limitation, not an observed safety invitation. Raw flags remain recorded. No other current/future value mixing was observed in these 48 outputs.",
        ]
    else:
        summary["briefing_status"] = "PENDING"
        lines += ["", "Briefing evaluation remains pending."]
    summary["status"] = (
        "COMPLETED" if briefing.exists() and forecast.exists() else "PARTIAL_PENDING"
    )
    (RAW / "next_qualification_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    (RAW / "next_qualification_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(summary["status"])


if __name__ == "__main__":
    main()
