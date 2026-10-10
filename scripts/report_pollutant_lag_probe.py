"""Report the immutable fixed lag probe without fetching or fitting anything."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest_path = ROOT / "eval/raw/pollutant_lag_probe_v1_manifest.json"
    result_path = ROOT / "eval/raw/pollutant_lag_probe_v1_results.json"
    manifest = json.loads(manifest_path.read_text())
    result = json.loads(result_path.read_text())
    if (
        manifest["status"] != "COMPLETED"
        or hashlib.sha256(result_path.read_bytes()).hexdigest() != manifest["result_sha256"]
    ):
        raise ValueError("Completed raw probe result hash mismatch")
    for relative, sha in manifest["source_sha256"].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != sha:
            raise ValueError("Pinned implementation/reference changed: " + relative)
    title = "## Fixed older-history probe v1: measured development results"
    lines = [
        title,
        "",
        f"Modal call `{manifest['call_id']}`, app `{manifest['app_id']}` completed once. "
        f"Both fits used the exact same 19,639 train and 1,411 development origins; "
        f"{result['canonical_target_checks']:,} canonical target pairs verified. "
        "Median imputation, input scaling and target scales fit only on training. "
        "There were 296 Poor+ weighted training origins. No 2026 diagnostic labels entered this study.",
        "",
        "| Development period | Context | n | Normalized MAE | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ false alarms | Poor+ episode hits/support | Very Poor+ misses/support |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for period in ("overall", "2025-04", "2025-05"):
        for context in ("24", "48"):
            candidate = result["results"][context]
            score = candidate["overall"] if period == "overall" else candidate["monthly"][period]
            poor, very = score["risk"]["poor_or_worse"], score["risk"]["very_poor_or_worse"]
            ep = poor["episodes"]
            lines.append(
                f"| {period} | {context}h | {score['rows']} | {score['normalized_mae']:.6f} | "
                f"{score['accuracy']:.6f} | {score['macro_f1']:.6f} | {poor['misses']}/{poor['support']} | "
                f"{poor['false_alarms']} | {ep['any_hit']}/{ep['episodes']} | {very['misses']}/{very['support']} |"
            )
    lines += [
        "",
        f"48h relative normalized MAE improvement: {100 * result['normalized_mae_relative_gain']:.3f}%. "
        f"Predeclared exploratory context screen passed: **{result['context_followup_supported']}**.",
        "",
    ]
    lines += [f"- {name}: {passed}" for name, passed in result["criteria"].items()]
    lines += [
        "",
        "Full raw results include six pollutant MAEs, recalls/precision/FAR, episode counts, monthly scores, "
        "negative pre-clipping predictions, train scales, actual and predicted development concentrations, "
        "and exact origin hashes. These are consumed CAMS/ERA5 modeled archive diagnostics, "
        "not independent station, prospective or medical qualification. Unsupported recall is UNMEASURED. "
        "A fixed linear probe cannot disprove nonlinear older-history value. No promotion, deployment or billed cost is claimed.",
        "",
    ]
    report = "\n".join(lines)
    report_path = ROOT / "eval/raw/pollutant_lag_probe_v1_summary.md"
    report_path.write_text(report, encoding="utf-8")
    for relative in ("docs/MODEL_QUALIFICATION_PROGRESS.md", "eval/RESULTS.md", "post.md"):
        path = ROOT / relative
        original = path.read_text(encoding="utf-8")
        if title not in original:
            path.write_text(original.rstrip() + "\n\n" + report, encoding="utf-8")
    state_path = ROOT / "eval/raw/deep_research_state.json"
    state = json.loads(state_path.read_text())
    state.update(
        status="LAG_PROBE_COMPLETED",
        current_manifest=str(manifest_path.relative_to(ROOT).as_posix()),
        call_id=manifest["call_id"],
        app_id=manifest["app_id"],
        last_observed_at=datetime.now(UTC).isoformat(),
    )
    state["lag_probe"] = {
        "status": "COMPLETED",
        "result": str(result_path.relative_to(ROOT).as_posix()),
        "summary": str(report_path.relative_to(ROOT).as_posix()),
        "context_followup_supported": result["context_followup_supported"],
        "result_sha256": manifest["result_sha256"],
    }
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
