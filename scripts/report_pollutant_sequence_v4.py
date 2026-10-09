"""Report a completed deep pollutant study without fitting, fetching or promotion."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "eval/raw/pollutant_sequence_v4"
LEGACY = ("good", "satisfactory", "moderate", "poor", "severe", "hazardous")
OFFICIAL = ("Good", "Satisfactory", "Moderately polluted", "Poor", "Very Poor", "Severe")


def ordinal(value):
    """Read historical names explicitly without silently renaming raw artifacts."""
    return LEGACY.index(value) if isinstance(value, str) else int(value)


def paired_new_hits(times, truth, reference, candidate, minimum=4):
    """Count new detections inside episodes completely missed by the reference."""
    positives = sorted(
        (datetime.fromisoformat(t), ordinal(r) >= minimum, ordinal(c) >= minimum)
        for t, y, r, c in zip(times, truth, reference, candidate, strict=True)
        if ordinal(y) >= minimum
    )
    episodes = []
    for point in positives:
        if not episodes or point[0] - episodes[-1][-1][0] > timedelta(hours=6):
            episodes.append([])
        episodes[-1].append(point)
    counts = [sum(c for _, _, c in e) for e in episodes if not any(r for _, r, _ in e)]
    return {"new_hits_in_fully_missed_reference_episodes": sum(counts),
            "maximum_new_hits_in_one_reference_missed_episode": max(counts, default=0),
            "newly_detected_reference_missed_episodes": sum(n > 0 for n in counts)}


def evaluate_gate(periods, candidate_name, reference_name="paired_lightgbm"):
    """Apply preregistered paired constraints; missing support stays unmeasured."""
    details, checks, recall_deltas, new_episode_hit_counts = [], [], [], []
    unsupported = []
    for p in periods:
        ref, cand = p["models"][reference_name], p["models"][candidate_name]
        poor_r, poor_c = ref["risk"]["poor_or_worse"], cand["risk"]["poor_or_worse"]
        very_r, very_c = ref["risk"]["very_poor_or_worse"], cand["risk"]["very_poor_or_worse"]
        criterion = {"accuracy": cand["accuracy"] >= ref["accuracy"] - 0.01 - 1e-12,
                     "poor_false_alarm_rate": poor_c["false_alarm_rate"] is not None
                     and poor_r["false_alarm_rate"] is not None
                     and poor_c["false_alarm_rate"] <= min(0.05, poor_r["false_alarm_rate"] + 0.01) + 1e-12,
                     "very_poor_false_alarm_rate": very_c["false_alarm_rate"] is not None
                     and very_r["false_alarm_rate"] is not None
                     and very_c["false_alarm_rate"] <= min(0.01, very_r["false_alarm_rate"] + 0.0025) + 1e-12,
                     "very_poor_misses_nonincreasing": very_c["misses"] <= very_r["misses"],
                     "poor_episode_any_hits_nondecreasing": poor_c["episodes"]["any_hit"] >= poor_r["episodes"]["any_hit"],
                     "very_poor_episode_any_hits_nondecreasing": very_c["episodes"]["any_hit"] >= very_r["episodes"]["any_hit"]}
        checks.extend(criterion.values())
        delta = None if poor_c["recall"] is None or poor_r["recall"] is None else poor_c["recall"] - poor_r["recall"]
        recall_deltas.append(delta)
        if not very_r["support"]:
            unsupported.append(p["partition"] + ": Very Poor+ recall UNMEASURED")
        if not ref["risk"]["severe"]["support"]:
            unsupported.append(p["partition"] + ": official Severe recall UNMEASURED")
        paired = paired_new_hits(p["times"], p["actual_legacy_bands"],
                                 ref["predicted_legacy_bands"], cand["predicted_legacy_bands"])
        new_episode_hit_counts.append(paired["maximum_new_hits_in_one_reference_missed_episode"])
        details.append({"partition": p["partition"], "checks": criterion,
                        "poor_recall_delta": delta, "paired_very_poor": paired})
    no_poor_loss = all(d is not None and d >= -1e-12 for d in recall_deltas)
    poor_gain = no_poor_loss and any(d is not None and d >= 0.05 - 1e-12 for d in recall_deltas)
    very_gain = no_poor_loss and any(n >= 2 for n in new_episode_hit_counts)
    return {"candidate": candidate_name, "reference": reference_name,
            "research_utility_gate_passed": bool(all(checks) and (poor_gain or very_gain)),
            "guardrails_passed": all(checks), "poor_recall_gain_branch": poor_gain,
            "very_poor_episode_gain_branch": very_gain, "paired_periods": details,
            "unsupported_claims": unsupported,
            "disposition": "RESEARCH_ONLY_NO_AUTOMATIC_PROMOTION"}


def prepare_summary(result, manifest, raw_sha):
    periods = result["results"]
    for p in periods:
        if not p.get("actual_legacy_bands"):
            # Canonical local helper is the same source-pinned contract used remotely.
            from baahar.naqi import band_for_index

            p["actual_legacy_bands"] = [band_for_index(v).value for v in p["actual_naqi"]]
        if len(p["times"]) != p["count"]:
            raise ValueError("Result count/timestamp mismatch")
        for model in p["models"].values():
            if len(model["predicted_legacy_bands"]) != p["count"]:
                raise ValueError("Prediction/timestamp mismatch")
            for risk in model["risk"].values():
                if risk["brier"] is not None or risk["ece"] is not None:
                    raise ValueError("Point-forecast output incorrectly supplied probability calibration")
    diagnostics = [p for p in periods if p["partition"].startswith("diagnostic_")]
    if len(diagnostics) != 2:
        raise ValueError("Both declared diagnostic periods are required")
    candidates = [name for name in diagnostics[0]["models"] if name.startswith("tcn_")]
    small_periods = []
    for p in periods:
        small_periods.append({key: value for key, value in p.items()
                              if key not in ("times", "actual_naqi", "actual_pollutants", "actual_legacy_bands", "models")}
                            | {"models": {name: {key: value for key, value in model.items()
                                                 if key not in ("predicted_naqi", "predicted_pollutants", "predicted_legacy_bands")}
                                          for name, model in p["models"].items()}})
    return {"status": "COMPLETED", "call_id": manifest.get("call_id"),
            "app_id": manifest.get("app_id"), "raw_result_sha256": raw_sha,
            "target_contract": result["target_contract"], "limitations": result["limitations"],
            "training": result["training"], "periods": small_periods,
            "resolved_support": result.get("support", {}),
            "utility_gates": [evaluate_gate(diagnostics, name, reference_name="v3_fixed_mean") for name in candidates],
            "official_category_names": dict(zip(LEGACY, OFFICIAL, strict=True)),
            "elapsed_seconds": result["elapsed_seconds"],
            "billing": "UNMEASURED", "disposition": "RESEARCH_ONLY_NO_AUTOMATIC_PROMOTION"}


def render(summary):
    def value(v):
        return "UNMEASURED" if v is None else f"{v:.6f}"

    lines = ["# Deep pollutant sequence study: measured results", "",
             "All candidates were evaluated on identical phase-local 24-hour-context origins. "
             "Both 2026 periods are consumed modeled-archive diagnostics, not fresh holdouts. "
             "The primary reference is the frozen v3 three-seed concentration-average ensemble. Matched LightGBM remains a secondary comparator.", "",
             "Historical raw `severe` means official Very Poor (301â€“400); `hazardous` means official Severe (401+). "
             "This is an instantaneous concentration proxy, not averaging-compliant station AQI.", "",
             "| Period | Model | n | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ recall | Poor+ precision | Poor+ FAR | Very Poor+ misses/support | Very Poor+ recall | Very Poor+ FAR | Severe misses/support |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for p in summary["periods"]:
        for name, m in p["models"].items():
            a, b, c = (m["risk"][k] for k in ("poor_or_worse", "very_poor_or_worse", "severe"))
            lines.append(f"| {p['partition']} | {name} | {p['count']} | {value(m['accuracy'])} | {value(m['macro_f1'])} | "
                         f"{a['misses']}/{a['support']} | {value(a['recall'])} | {value(a['precision'])} | {value(a['false_alarm_rate'])} | "
                         f"{b['misses']}/{b['support']} | {value(b['recall'])} | {value(b['false_alarm_rate'])} | {c['misses']}/{c['support']} |")
    lines += ["", "## Full metric detail", "", "The machine-readable completion summary retains pollutant MAE/RMSE, "
              "class support, episode counts, ranking average precision, seed histories and all paired gate checks. "
              "Ranking scores are not probabilities; Brier/ECE are unavailable. Missing positive support means recall is unmeasured.", "",
              "```json", json.dumps(summary["utility_gates"], indent=2), "```", "",
              "No candidate was promoted. No prospective station validation, human review, field test, medical benefit "
              "or measured billing is established. A passing retrospective gate supports further qualification only."]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, default=PREFIX)
    args = parser.parse_args()
    raw = Path(str(args.prefix) + "_results.json")
    manifest_path = Path(str(args.prefix) + "_manifest.json")
    output = Path(str(args.prefix) + "_completion_summary.json")
    report = Path(str(args.prefix) + "_completion_summary.md")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["status"] != "COMPLETED":
        raise ValueError("Cannot report unfinished hosted run")
    for relative in ("scripts/report_pollutant_sequence_v4.py", "docs/POLLUTANT_SEQUENCE_V4_PROTOCOL.md"):
        expected = manifest["source_sha256"].get(relative)
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        if expected != actual:
            raise ValueError("Frozen evaluation source SHA mismatch: " + relative)
    raw_sha = hashlib.sha256(raw.read_bytes()).hexdigest()
    if manifest.get("result_sha256") != raw_sha:
        raise ValueError("Saved raw result SHA mismatch")
    if output.exists() or report.exists():
        print("Completion artifact exists; refusing overwrite")
        return
    summary = prepare_summary(json.loads(raw.read_text(encoding="utf-8")), manifest, raw_sha)
    output.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    report.write_text(render(summary), encoding="utf-8")
    heading = "## Deep pollutant sequence v4 measured completion"
    for path, prefix in ((ROOT / "docs/MODEL_QUALIFICATION_PROGRESS.md", "../eval/raw/"),
                         (ROOT / "eval/RESULTS.md", "raw/"), (ROOT / "post.md", "eval/raw/")):
        if heading not in path.read_text(encoding="utf-8"):
            with path.open("a", encoding="utf-8") as stream:
                stream.write("\n\n" + heading + "\n\n" + render(summary).split("## Full metric detail")[0]
                             + f"\nFull [measured report]({prefix}{report.name}) and [machine-readable metrics]({prefix}{output.name}). "
                             "Research-only consumed modeled archive; no automatic adoption or measured billing.\n")
    print("Completed deep-study report and documentation additions: " + str(report))


if __name__ == "__main__":
    main()
