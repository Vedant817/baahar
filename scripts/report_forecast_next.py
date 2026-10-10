"""Frozen paired gates for finite retrospective rounds; no fetching or fitting."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "eval/raw"
PERIODS = ("diagnostic_pollution", "diagnostic_other_seasons")
EPSILON = 1e-12


def write_new(path, value):
    """Keep prior measured output immutable."""
    if path.exists():
        raise ValueError("Refusing to overwrite " + str(path))
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def episodes(times, labels, minimum):
    groups = []
    previous = None
    for i, (stamp, label) in enumerate(zip(times, labels, strict=True)):
        if label < minimum:
            continue
        if previous is None or stamp - previous > timedelta(hours=6):
            groups.append([])
        groups[-1].append(i)
        previous = stamp
    return groups


def metrics(times, labels, predictions, minimum):
    truth = [label >= minimum for label in labels]
    positives = sum(truth)
    negatives = len(labels) - positives
    tp = sum(t and p >= minimum for t, p in zip(truth, predictions, strict=True))
    fp = sum(not t and p >= minimum for t, p in zip(truth, predictions, strict=True))
    groups = episodes(times, labels, minimum)
    return {
        "positive_support": positives,
        "negative_support": negatives,
        "misses": positives - tp,
        "recall": tp / positives if positives else None,
        "false_alarms": fp,
        "false_alarm_rate": fp / negatives if negatives else None,
        "precision": tp / (tp + fp) if tp + fp else None,
        "episode_count": len(groups),
        "any_hit_count": sum(any(predictions[i] >= minimum for i in g) for g in groups),
        "full_hit_count": sum(all(predictions[i] >= minimum for i in g) for g in groups),
    }


def new_severe_hits(times, labels, reference, challenger):
    missed = [g for g in episodes(times, labels, 4) if all(reference[i] < 4 for i in g)]
    captured = [g for g in missed if any(challenger[i] >= 4 for i in g)]
    return {
        "newly_captured_previously_missed_episodes": len(captured),
        "new_severe_hours_in_previously_missed_episodes": sum(
            challenger[i] >= 4 for g in captured for i in g
        ),
        "newly_detected_times": [
            times[i].isoformat() for g in captured for i in g if challenger[i] >= 4
        ],
    }


def paired_period(period, reference_name, challenger_name):
    labels = period["labels"]
    times = [datetime.fromisoformat(t) for t in period["times"]]
    reference = period["models"][reference_name]["predictions"]
    challenger = period["models"][challenger_name]["predictions"]
    if not labels or len({len(labels), len(times), len(reference), len(challenger)}) != 1:
        raise ValueError("Empty or misaligned paired predictions")
    if len(set(times)) != len(times) or times != sorted(times):
        raise ValueError("Paired timestamps must be unique and chronological")
    if any(not isinstance(v, int) or not 0 <= v <= 5 for v in labels + reference + challenger):
        raise ValueError("Invalid ordinal target or prediction")

    def accuracy(pred):
        return sum(a == b for a, b in zip(labels, pred, strict=True)) / len(labels)

    ref = {
        "accuracy": accuracy(reference),
        "poor": metrics(times, labels, reference, 3),
        "severe": metrics(times, labels, reference, 4),
    }
    cand = {
        "accuracy": accuracy(challenger),
        "poor": metrics(times, labels, challenger, 3),
        "severe": metrics(times, labels, challenger, 4),
    }
    for measured, key in ((ref, reference_name), (cand, challenger_name)):
        raw = period["models"][key]
        measured["reported_metrics"] = {
            field: raw.get(field)
            for field in ("classification", "risk", "severe_or_worse", "severe_onset", "numeric")
        }
    gates = {"accuracy_loss": cand["accuracy"] + EPSILON >= ref["accuracy"] - 0.01}
    for family, increase, maximum in (("poor", 0.01, 0.05), ("severe", 0.0025, 0.01)):
        a, b = ref[family], cand[family]
        gates[family + "_false_alarms"] = (
            b["false_alarm_rate"] is not None
            and a["false_alarm_rate"] is not None
            and b["false_alarm_rate"] <= min(maximum, a["false_alarm_rate"] + increase) + EPSILON
        )
        gates[family + "_episode_any_hits"] = b["any_hit_count"] >= a["any_hit_count"]
    gates["severe_misses"] = cand["severe"]["misses"] <= ref["severe"]["misses"]
    delta = (
        cand["poor"]["recall"] - ref["poor"]["recall"]
        if ref["poor"]["recall"] is not None
        else None
    )
    return {
        "partition": period["partition"],
        "n": len(labels),
        "reference": ref,
        "challenger": cand,
        "gates": gates,
        "utility_gates_passed": all(gates.values()),
        "poor_recall_delta": delta,
        "severe_counterfactual": new_severe_hits(times, labels, reference, challenger),
    }


def evaluate(result, reference_name, challenger_name):
    found = {p["partition"]: p for p in result["results"]}
    compared = [paired_period(found[name], reference_name, challenger_name) for name in PERIODS]
    deltas = [p["poor_recall_delta"] for p in compared]
    no_recall_loss = all(d is not None and d >= -EPSILON for d in deltas)
    recall_gain = no_recall_loss and any(d >= 0.05 - EPSILON for d in deltas)
    new_hours = sum(
        p["severe_counterfactual"]["new_severe_hours_in_previously_missed_episodes"]
        for p in compared
    )
    new_episodes = sum(
        p["severe_counterfactual"]["newly_captured_previously_missed_episodes"] for p in compared
    )
    severe_gain = no_recall_loss and new_hours >= 2 and new_episodes >= 1
    utility = all(p["utility_gates_passed"] for p in compared)
    return {
        "reference_model": reference_name,
        "challenger_model": challenger_name,
        "periods": compared,
        "utility_gates_passed": utility,
        "poor_recall_gain_criterion": recall_gain,
        "severe_gain_criterion": severe_gain,
        "meaningful_gain": utility and (recall_gain or severe_gain),
        "disposition": "RETROSPECTIVE_RESEARCH_ONLY_NO_PROMOTION",
        "limitations": "Consumed modeled archive; adaptive repeated comparisons; correlated hours; "
        "finite plateau does not establish maximum performance or live safety.",
    }


def record_round(summary, source, run_id):
    ledger_path = RAW / "forecast_next_loop_ledger.jsonl"
    state_path = RAW / "forecast_next_loop_state.json"
    rows = (
        [
            json.loads(line)
            for line in ledger_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if ledger_path.exists()
        else []
    )
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    existing = next((r for r in rows if r["run_id"] == run_id), None)
    if existing:
        if existing["raw_result_sha256"] != digest:
            raise ValueError("Recorded run raw result hash changed")
    else:
        if len(rows) >= 7 or trailing_no_gain(rows) >= 2:
            raise ValueError("Finite research loop already stopped")
        row = {
            "iteration": len(rows) + 1,
            "run_id": run_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "result": str(source.relative_to(ROOT)),
            "raw_result_sha256": digest,
            "meaningful_gain": summary["meaningful_gain"],
            "reference_model": summary["reference_model"],
            "challenger_model": summary["challenger_model"],
        }
        with ledger_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
        rows.append(row)
    stopped = len(rows) >= 7 or trailing_no_gain(rows) >= 2
    state = {
        "max_iterations": 7,
        "plateau_patience": 2,
        "completed_iterations": len(rows),
        "consecutive_no_gain": trailing_no_gain(rows),
        "stopped": stopped,
        "stop_reason": "two_consecutive_no_gain"
        if trailing_no_gain(rows) >= 2
        else "seven_round_limit"
        if len(rows) >= 7
        else None,
        "last_run_id": rows[-1]["run_id"],
        "disposition": "FINITE_RETROSPECTIVE_RESEARCH_NO_AUTOMATIC_ADOPTION",
    }
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return state


def trailing_no_gain(rows):
    count = 0
    for row in reversed(rows):
        if row["meaningful_gain"]:
            break
        count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("--reference")
    parser.add_argument("--candidate")
    parser.add_argument("--record-round", action="store_true")
    args = parser.parse_args()
    source = args.result.resolve()
    result = json.loads(source.read_text(encoding="utf-8"))
    manifest = result.get("manifest", {})
    for key, path in (
        ("protocol_sha256", ROOT / "docs/FORECAST_NEXT_ITERATION_PROTOCOL.md"),
        ("gate_reporter_sha256", Path(__file__)),
    ):
        if key in manifest and hashlib.sha256(path.read_bytes()).hexdigest() != manifest[key]:
            raise ValueError("Frozen gate source hash mismatch: " + key)
    comparison = result.get("comparison", result.get("manifest", {}).get("comparison", {}))
    reference = args.reference or comparison.get("reference_model")
    challenger = args.candidate or comparison.get("candidate_model")
    if not reference or not challenger:
        parser.error("Provide --reference/--candidate or a pinned comparison in raw results")
    if comparison and (
        reference != comparison["reference_model"] or challenger != comparison["candidate_model"]
    ):
        parser.error("Model names contradict the pinned raw comparison")
    summary = evaluate(result, reference, challenger)
    summary["raw_result_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    prefix = source.with_name(source.stem.removesuffix("_results") + "_gate_summary")
    output = prefix.with_suffix(".json")
    if output.exists():
        if json.loads(output.read_text(encoding="utf-8")) != summary:
            raise ValueError("Refusing to overwrite a different measured gate summary")
    else:
        write_new(output, summary)
    if args.record_round:
        run_id = result.get("manifest", {}).get("run_name", source.stem)
        summary["loop_state"] = record_round(summary, source, run_id)
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
