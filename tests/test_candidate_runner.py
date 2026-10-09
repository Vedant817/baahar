"""Offline guardrails for expensive training submission and honest reporting."""

import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "candidate_runner",
    Path(__file__).resolve().parents[1] / "scripts" / "train_briefing_candidates_modal.py",
)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def corpus(tmp_path):
    for index, split in enumerate(runner.SPLITS):
        row = {
            "id": split,
            "facts": {"decision": "GO"},
            "messages": [
                {"role": "system", "content": "Write brief"},
                {"role": "user", "content": f"Case {split}"},
                {"role": "assistant", "content": "Go now."},
            ],
            "meta": {
                "split": split,
                "source_time": f"2026-01-0{index + 1}T06:00",
                "source_kind": "synthetic_stress" if split == "stress" else "recorded_archive",
            },
        }
        (tmp_path / f"{split}.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    return tmp_path


def alter(directory, split, transform):
    path = directory / f"{split}.jsonl"
    row = json.loads(path.read_text())
    transform(row)
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")


def test_preflight_records_hashes_and_real_synthetic_denominators(tmp_path):
    directory = corpus(tmp_path)
    result = runner.preflight(directory)
    assert result["counts"] == dict.fromkeys(runner.SPLITS, 1)
    assert len(result["sha256"]["test"]) == 64
    assert result["source_kind_counts"]["stress"]["synthetic_stress"] == 1


def test_preflight_blocks_duplicate_prompt_across_holdout(tmp_path):
    directory = corpus(tmp_path)
    alter(directory, "test", lambda row: row["messages"][1].update(content="Case train"))
    with pytest.raises(ValueError, match="Identical prompt"):
        runner.preflight(directory)


def test_preflight_blocks_same_source_day_leak(tmp_path):
    directory = corpus(tmp_path)
    alter(directory, "val", lambda row: row["meta"].update(source_time="2026-01-01T09:00"))
    with pytest.raises(ValueError, match="Source days overlap"):
        runner.preflight(directory)


def test_preflight_blocks_reversed_chronology(tmp_path):
    directory = corpus(tmp_path)
    alter(directory, "train", lambda row: row["meta"].update(source_time="2026-02-01T09:00"))
    with pytest.raises(ValueError, match="Nonchronological"):
        runner.preflight(directory)


def test_empty_data_is_not_a_valid_run(tmp_path):
    directory = corpus(tmp_path)
    (directory / "test.jsonl").write_text("")
    with pytest.raises(ValueError, match="Empty dataset"):
        runner.preflight(directory)


class Tokenizer:
    def __init__(self, full, prefix):
        self.full, self.prefix = full, prefix

    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        return self.prefix if add_generation_prompt else self.full


def test_assistant_loss_mask_excludes_exact_prompt_prefix():
    assert runner.encode_case(Tokenizer([1, 2, 3, 4], [1, 2]), {"id": "a", "messages": []}, 5) == (
        [1, 2, 3, 4],
        [-100, -100, 3, 4],
    )


def test_prefix_mismatch_fails_instead_of_training_prompt_tokens():
    with pytest.raises(ValueError, match="not a token prefix"):
        runner.encode_case(Tokenizer([1, 2, 3], [1, 9]), {"id": "a", "messages": []}, 5)


def test_overflow_returns_exclusion_without_truncation():
    assert runner.encode_case(Tokenizer([1, 2, 3], [1]), {"id": "a", "messages": []}, 2) is None


def test_metrics_expose_raw_failure_even_when_fallback_passes():
    rows = [
        {
            "seconds": 1.0,
            "raw_check": {"accepted": False, "safety_errors": ["unsafe"]},
            "guarded_check": {"accepted": True, "safety_errors": []},
            "fallback_used": True,
        },
        {
            "seconds": 3.0,
            "raw_check": {"accepted": True, "safety_errors": []},
            "guarded_check": {"accepted": True, "safety_errors": []},
            "fallback_used": False,
        },
    ]
    result = runner.summarize(rows)
    assert result["raw_safety_error_count"] == 1
    assert result["raw_accepted_count"] == 1
    assert result["guarded_accepted_count"] == 2
    assert result["rejection_rate"] == 0.5
    assert result["latency_median_seconds"] == 2.0
    assert result["latency_p95_seconds"] == 3.0


def test_empty_evaluation_cannot_report_green():
    with pytest.raises(ValueError, match="zero generation"):
        runner.summarize([])


def test_submission_requires_explicit_detached_action():
    with pytest.raises(SystemExit):
        runner.main(["--submit"])


def test_cost_ceiling_is_compute_estimate_below_ten_dollars():
    assert 9 < runner.MAX_PAIR_COMPUTE_USD < 10
