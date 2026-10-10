"""Tests for the frozen-candidate evidence gate.

The gate's whole job is to refuse to let an acknowledged gap become a silent
one, so its own failure modes matter more than its happy path: a tampered
generation must change the re-derived numbers, and deleting the documented gap
must fail the check rather than quietly pass.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_frozen_candidate_evidence as gate  # noqa: E402


@pytest.fixture
def fixtures():
    manifest = json.loads((gate.RAW / gate.MANIFEST).read_text(encoding="utf-8"))
    decision_path = gate.RAW / f"candidate_decision_{manifest['run_id']}.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    return manifest, decision


def test_the_real_evidence_passes(fixtures):
    manifest, decision = fixtures
    out = gate.Checker()
    gate.check_contract(out, manifest, decision)
    gate.check_calls(out, manifest, decision)
    gate.check_published_numbers(out, manifest, decision)
    gate.check_decision_consistency(out, manifest, decision)
    assert out.passed, list(out.problems)


def test_published_numbers_are_re_derived_from_the_generations(fixtures, tmp_path: Path):
    """The check must actually recompute, not just compare two stored blobs."""
    manifest, decision = fixtures
    call = manifest["calls"]["qwen3_4b"]
    metrics = json.loads((gate.ROOT / call["artifact"]).read_text(encoding="utf-8"))
    rows_path = (gate.ROOT / call["artifact"]).with_name(
        Path(call["artifact"]).stem + "_generations.jsonl"
    )
    rows = [
        json.loads(line)
        for line in rows_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        groups.setdefault((row["phase"], row["split"]), []).append(row)
    assert groups, "the fixture has evaluation groups"
    for (phase, split), group in groups.items():
        assert gate._summary(group) == metrics["evaluation"][phase][split]


def test_a_tampered_generation_changes_the_re_derived_numbers(
    fixtures, tmp_path: Path, monkeypatch
):
    manifest, _ = fixtures
    call = manifest["calls"]["qwen3_4b"]
    metrics_path = gate.ROOT / call["artifact"]
    original = metrics_path.read_text(encoding="utf-8")

    altered = json.loads(original)
    first = next(iter(altered["evaluation"]["base"].values()))
    first["raw_accepted_count"] = first.get("raw_accepted_count", 0) + 1
    metrics_path.write_text(json.dumps(altered), encoding="utf-8")
    try:
        out = gate.Checker()
        gate.check_published_numbers(out, manifest, _decision_for(manifest))
        assert not out.passed
        assert any("no longer follow" in p for p in out.problems)
    finally:
        metrics_path.write_text(original, encoding="utf-8")
    assert json.loads(metrics_path.read_text(encoding="utf-8")) == json.loads(original)


def _decision_for(manifest):
    return json.loads(
        (gate.RAW / f"candidate_decision_{manifest['run_id']}.json").read_text(encoding="utf-8")
    )


def test_deleting_the_documented_gap_fails_the_check(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(gate, "GAP_DOC", tmp_path / "NEEDS_HUMAN.md")
    (tmp_path / "NEEDS_HUMAN.md").write_text("nothing about frozen evidence\n", encoding="utf-8")
    out = gate.Checker()
    gate.check_gap_is_documented(out)
    assert not out.passed
    assert any("still records" in p or "no longer records" in p for p in out.problems)


def test_a_changed_contract_snapshot_fails_the_check(fixtures):
    manifest, decision = fixtures
    snapshot = gate.RAW / f"contract_{manifest['run_id']}.txt"
    saved = snapshot.read_bytes()
    snapshot.write_bytes(b"tampered\n")
    try:
        out = gate.Checker()
        gate.check_contract(out, manifest, decision)
        assert not out.passed
        assert any("contract snapshot" in p for p in out.problems)
    finally:
        snapshot.write_bytes(saved)
    assert snapshot.read_bytes() == saved
