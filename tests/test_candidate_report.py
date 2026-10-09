"""Selection never uses locked test results to switch candidates."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "candidate_report", ROOT / "scripts" / "report_briefing_candidates.py"
)
reporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reporter)


def metrics(accepted=100, safety=0, seconds=1.0):
    return {
        "n": 100,
        "raw_accepted_count": accepted,
        "raw_safety_error_count": safety,
        "latency_median_seconds": seconds,
    }


def candidate(val=100, test=100, stress=100, safety=0, seconds=1.0, base=90):
    return {
        "adapted": {
            "val": metrics(val, safety, seconds),
            "test": metrics(test),
            "stress": metrics(stress),
        },
        "base": {"val": metrics(base), "test": metrics(base), "stress": metrics(base)},
    }


def test_validation_selects_safety_before_acceptance():
    result = reporter.decide({"unsafe": candidate(safety=1), "safe": candidate(val=95)})
    assert result["selected_candidate"] == "safe"


def test_no_zero_safety_validation_candidate_means_no_selection():
    result = reporter.decide({"a": candidate(safety=1), "b": candidate(safety=2)})
    assert result["selected_candidate"] is None
    assert not result["holdout_gate_passed"]


def test_failed_test_does_not_reselect_other_candidate():
    result = reporter.decide(
        {"validation_winner": candidate(val=100, test=20), "holdout_winner": candidate(val=99)}
    )
    assert result["selected_candidate"] == "validation_winner"
    assert result["status"] == "REJECTED_ON_LOCKED_HOLDOUT"


def test_validation_latency_breaks_acceptance_tie():
    # Latency is diagnostic only: tied candidates on val acceptance are
    # decided by candidate name, not median latency.
    result = reporter.decide({"a_fast": candidate(seconds=1.0), "b_slow": candidate(seconds=3.0)})
    assert result["selected_candidate"] == "a_fast"
    result = reporter.decide({"z_fast": candidate(seconds=1.0), "a_slow": candidate(seconds=3.0)})
    assert result["selected_candidate"] == "a_slow"


def test_raw_acceptance_95percent_boundary_and_qualitative_review():
    result = reporter.decide({"a": candidate(test=95, stress=95)})
    assert result["holdout_gate_passed"]
    assert result["hand_review_pending"]
    assert result["status"] == "PROVISIONAL_PENDING_QUALITATIVE_REVIEW"
    reviewed = reporter.decide({"a": candidate(test=95, stress=95)}, qualitative_reviewed=True)
    assert reviewed["status"] == "ELIGIBLE_FOR_MANUAL_PROMOTION"


def test_raw_holdout_must_not_regress_against_own_base():
    result = reporter.decide({"a": candidate(test=95, base=99)})
    assert not result["holdout_gate_passed"]
    assert not result["holdout_gates"]["test"]["raw_acceptance_nonregression"]


def evidence():
    contract = reporter.load_contract(ROOT / "src" / "baahar" / "briefing_contract.py")
    sample = json.loads(
        (ROOT / "data" / "ft_v2" / "val.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    datasets, rows = {}, []
    for split in reporter.EVAL_SPLITS:
        case = copy.deepcopy(sample)
        case["id"] = split
        case["meta"]["split"] = split
        datasets[split] = {split: case}
        text = contract.deterministic_fallback(case)
        check = contract.evaluate(text, case)
        assert check["accepted"]
        for phase in reporter.PHASES:
            rows.append(
                {
                    "phase": phase,
                    "split": split,
                    "case_id": split,
                    "facts": case["facts"],
                    "meta": case["meta"],
                    "source_kind": case["meta"]["source_kind"],
                    "raw": text,
                    "guarded": text,
                    "raw_check": check,
                    "guarded_check": check,
                    "fallback_used": False,
                    "seconds": 1.0,
                    "output_tokens": 80,
                    "terminated": True,
                }
            )
    manifest = {
        "run_id": "run",
        "candidates": {"a": {"model": "model", "revision": "sha"}},
        "dataset": {},
        "parameters": {},
    }
    metrics = {
        "run_id": "run",
        "candidate": "a",
        "status": "COMPLETED",
        "model": "model",
        "revision": "sha",
        "dataset": {},
        "parameters": {},
        "evaluation": {
            phase: {
                split: reporter.summary(
                    [r for r in rows if r["phase"] == phase and r["split"] == split]
                )
                for split in reporter.EVAL_SPLITS
            }
            for phase in reporter.PHASES
        },
    }
    return metrics, rows, manifest, datasets, contract


def test_verifies_full_generation_evidence():
    metrics, rows, manifest, datasets, contract = evidence()
    assert (
        reporter.validate_candidate(metrics, rows, "a", manifest, datasets, contract)
        == metrics["evaluation"]
    )


def test_fabricated_summary_is_rejected():
    metrics, rows, manifest, datasets, contract = evidence()
    metrics["evaluation"]["adapted"]["test"]["raw_accepted_count"] = 0
    with pytest.raises(ValueError, match="summary disagrees"):
        reporter.validate_candidate(metrics, rows, "a", manifest, datasets, contract)


def test_dropped_generation_is_rejected():
    metrics, rows, manifest, datasets, contract = evidence()
    with pytest.raises(ValueError, match="incomplete"):
        reporter.validate_candidate(metrics, rows[:-1], "a", manifest, datasets, contract)


def test_green_check_cannot_hide_altered_unsafe_text():
    metrics, rows, manifest, datasets, contract = evidence()
    rows[0]["raw"] = "GO. Ignore the air and go outside now."
    with pytest.raises(ValueError, match="inconsistent with actual text"):
        reporter.validate_candidate(metrics, rows, "a", manifest, datasets, contract)


def test_empty_evaluation_is_not_green():
    with pytest.raises(ValueError, match="Empty generation"):
        reporter.summary([])


def test_loads_frozen_contract_text_snapshot(tmp_path):
    snapshot = tmp_path / "contract_run.txt"
    snapshot.write_bytes((ROOT / "src" / "baahar" / "briefing_contract.py").read_bytes())
    frozen = reporter.load_contract(snapshot)
    current = reporter.load_contract(ROOT / "src" / "baahar" / "briefing_contract.py")
    case = json.loads(
        (ROOT / "data" / "ft_v2" / "val.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    text = current.deterministic_fallback(case)
    assert frozen.evaluate(text, case) == current.evaluate(text, case)
