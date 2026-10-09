"""Cohort integrity and policy provenance checks, all offline."""

import hashlib
import importlib.util
import json
from pathlib import Path

from baahar.briefing_contract import evaluate
from baahar.config import REPO_ROOT

spec = importlib.util.spec_from_file_location(
    "ft_v2_builder", REPO_ROOT / "scripts" / "build_ft_v2_dataset.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def read(split):
    return [
        json.loads(line)
        for line in (REPO_ROOT / "data" / "ft_v2" / f"{split}.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]


def test_recorded_cohorts_have_disjoint_days_and_conditions():
    observed_days, observed_fingerprints, observed_prompts = set(), set(), set()
    previous_end = None
    for split in ("train", "val", "test"):
        real = [c for c in read(split) if c["meta"]["source_kind"] == "recorded_archive"]
        days = {c["meta"]["source_time"][:10] for c in real}
        fingerprints = {builder.near_fingerprint(c["facts"]) for c in real}
        prompts = {c["messages"][1]["content"] for c in real}
        assert not days & observed_days
        assert not fingerprints & observed_fingerprints
        assert not prompts & observed_prompts
        assert len(fingerprints) == len(real)
        if previous_end:
            assert min(days) > previous_end
        previous_end = max(days)
        observed_days |= days
        observed_fingerprints |= fingerprints
        observed_prompts |= prompts


def test_targets_and_holdout_metadata_are_honest():
    training_prompts = {c["messages"][1]["content"] for c in read("train")}
    for split in ("train", "val", "test", "stress"):
        for case in read(split):
            assert case["meta"]["split"] == split
            assert case["meta"]["target_kind"] == "synthetic_deterministic_prose"
            if split == "stress":
                assert case["meta"]["source_time"] is None
                assert case["meta"]["source_kind"] == "synthetic_stress"
            if split != "train":
                assert case["messages"][1]["content"] not in training_prompts
            result = evaluate(case["messages"][-1]["content"], case)
            assert result["accepted"], (case["id"], result)


def test_future_labels_cannot_change_briefing_decision():
    row = json.loads(
        (REPO_ROOT / "data" / "eval" / "gono_rows.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    baseline = builder.facts_for_row(row, "Cubbon Park")
    row.update(target_naqi=500, target_band="hazardous", decision="GO")
    assert builder.facts_for_row(row, "Cubbon Park") == baseline


def test_rebuilding_is_byte_reproducible(tmp_path: Path):
    # Runtime policy wording evolves; a new build must be versioned before use
    # in training. The stored v2 cohort remains immutable experiment evidence.
    first, second = tmp_path / "first", tmp_path / "second"
    source = REPO_ROOT / "data" / "eval" / "gono_rows.jsonl"
    builder.build(source, first)
    builder.build(source, second)
    for filename in ("train.jsonl", "val.jsonl", "test.jsonl", "stress.jsonl", "manifest.json"):
        assert (first / filename).read_bytes() == (second / filename).read_bytes()


def test_frozen_cohort_matches_its_recorded_hashes():
    frozen = REPO_ROOT / "data" / "ft_v2"
    manifest = json.loads((frozen / "manifest.json").read_text(encoding="utf-8"))
    for split in ("train", "val", "test", "stress"):
        actual = hashlib.sha256((frozen / f"{split}.jsonl").read_bytes()).hexdigest()
        assert actual == manifest["cohorts"][split]["sha256"]
