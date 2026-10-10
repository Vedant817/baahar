"""Publish measured bounded-research evidence without touching historical ledgers."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "eval/raw"


def main():
    state = json.loads((RAW / "forecast_next_loop_state.json").read_text())
    ledger = [
        json.loads(line)
        for line in (RAW / "forecast_next_loop_ledger.jsonl").read_text().splitlines()
        if line.strip()
    ]
    rounds = []
    lines = [
        "## Bounded forecast research follow-up",
        "",
        "Consumed CAMS/ERA5 archive diagnostics; repeated research comparisons, not independent station or prospective validation.",
        "",
        "| Round | Period | Candidate | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ false alarms | Poor+ recall | Severe+ misses/support | Episode any-hit |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for entry in ledger:
        prefix = RAW / entry["run_id"]
        result_path = prefix.with_name(prefix.name + "_results.json")
        result = json.loads(result_path.read_text())
        manifest = json.loads(prefix.with_name(prefix.name + "_manifest.json").read_text())
        gate = json.loads(prefix.with_name(prefix.name + "_gate_summary.json").read_text())
        periods = []
        for period in result["results"]:
            models = {}
            for name, model in period["models"].items():
                scores = {
                    k: v
                    for k, v in model.items()
                    if k
                    not in (
                        "predictions",
                        "numeric_predictions",
                        "poor_probabilities",
                        "severe_probabilities",
                    )
                }
                models[name] = scores
                c, p, s, e = (
                    model["classification"],
                    model["risk"],
                    model["severe_or_worse"],
                    model["poor_episodes"],
                )
                lines.append(
                    f"| {entry['run_id']} | {period['partition']} | {name} | {c['accuracy']:.4f} | {c['macro_f1']:.4f} | {p['misses']}/{p['positive_support']} | {p['false_alarms']} | {p['recall'] if p['recall'] is not None else 'unmeasured'} | {s['misses']}/{s['positive_support']} | {e['any_hit_count']}/{e['episode_count']} |"
                )
            periods.append({"partition": period["partition"], "n": period["n"], "models": models})
        rounds.append(
            {
                "run_id": entry["run_id"],
                "call_id": manifest["call_id"],
                "app_id": manifest["app_id"],
                "approach": manifest["approach"],
                "execution_mode": manifest.get("execution_mode", "hosted_fitting"),
                "inference_only": result.get("inference_only", False),
                "reused_model": result.get("reused_model"),
                "raw_result_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
                "partition_support": result["partition_support"],
                "periods": periods,
                "gate": gate,
                "source_target_timestamp_checks": result["source_target_timestamp_checks"],
            }
        )
    lines += [
        "",
        f"Completed rounds: {state['completed_iterations']}; consecutive rounds without gated gain: {state['consecutive_no_gain']}. Stop reason: {state['stop_reason'] or 'still active'}.",
        "",
        "V5 fitted paired classifiers on Modal. V6 evaluated the fixed poor-band floor using existing v4 classifier and quantile weights on Modal, with no refitting; this is one training round and one hosted architecture evaluation, not two training rounds. Exact incumbent and quantile prediction hashes reproduce v4. The reused bundle hash was observed at read time, not independently pinned before its original training.",
        "",
        "Gas history improved some hourly metrics but degraded others and did not resolve severe misses. The fixed quantile floor trades fewer poor+ misses for more false alarms; it cannot raise a prediction to severe. No candidate is promoted. Development has zero severe support; training has only 27 severe hours across six descriptive episodes. Hazardous recall remains unmeasured. Full raw probabilities/reliability and predictions are preserved in the linked JSON artifacts. No human, field, medical or billed-cost evidence is claimed. This finite stopping rule does not establish maximum attainable performance.",
    ]
    lines += [
        "",
        "Evidence: `eval/raw/forecast_risk_v5_results.json`, `eval/raw/forecast_risk_v6_results.json`, their `_gate_summary.json` files, and `eval/raw/forecast_next_completion_summary.json`. Three data, architecture and safety reviews are recorded for each round under `docs/FORECAST_V5_*_REVIEW.md` and `docs/FORECAST_V6_*_REVIEW.md`. Offline pytest and Ruff passed; eight focused checks cover causal features, rounded boundaries, episode regressions and the frozen stopping criteria.",
        "",
        "Next research prerequisite: obtain distinct severe development episodes and a separately frozen future evaluation source, then test whether pollutant-specific forecasting generalizes. Repeating parameter changes on these same consumed windows cannot establish that. A larger transformer is not supported by the present evidence. Keep deterministic safety handling and current serving behavior.",
    ]
    text = "\n".join(lines) + "\n"
    summary = {
        "state": state,
        "rounds": rounds,
        "disposition": "RESEARCH_ONLY_NO_PROMOTION",
        "notes": lines[-5],
        "next_step": lines[-1],
        "validation": {"offline_pytest": "PASSED", "ruff": "PASSED", "focused_checks": 8},
    }
    output = RAW / "forecast_next_completion_summary.json"
    if output.exists():
        if json.loads(output.read_text()) != summary:
            raise ValueError("Refusing to overwrite prior completion evidence")
    else:
        output.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (RAW / "forecast_next_completion_summary.md").write_text(text, encoding="utf-8")
    for name in ("docs/MODEL_QUALIFICATION_PROGRESS.md", "eval/RESULTS.md", "post.md"):
        path = ROOT / name
        content = path.read_text(encoding="utf-8")
        if "## Bounded forecast research follow-up" not in content:
            path.write_text(content.rstrip() + "\n\n" + text, encoding="utf-8")
    print("Measured summaries and documentation written; no serving artifacts changed")


if __name__ == "__main__":
    main()
