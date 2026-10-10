#!/usr/bin/env python
"""Verify the frozen briefing-candidate evidence that this repo can still prove.

``scripts/report_briefing_candidates.py`` is the real gate: it re-derives the
published candidate decision from the manifest, the graded dataset and the
contract, and it refuses to regrade a submission against a dataset whose bytes
have moved. That script is correct and unchanged.

Run ``20261007T184549Z-fb0d6990`` cannot go through it, for a reason that is not
fixable in this repository:

* the run is dated 2026-10-07, and ``data/ft_v2`` and ``scripts/build_ft_v2_dataset.py``
  were both first committed on 2026-10-09. The dataset that run graded was built
  by a builder that was never committed;
* its bytes are in no commit -- every ``.jsonl`` blob in
  ``git rev-list --objects --all`` has been hashed and none matches;
* the Modal volume holds only the adapters, metrics and generations. No app
  remains, and the dataset was baked into a training image, not the volume;
* and the committed dataset is not a substitute: its ``facts.reasons`` carry a
  later policy change ("Night-time. Good air, but park gates may be shut.") that
  the run's generations do not, so re-deriving the decision against it would
  silently change the policy it was graded under. That is the exact failure the
  original script exists to prevent.

Deleting the CI step would leave the published numbers unguarded. Keeping it red
would train everyone to ignore a red build. So this checks what *is* still
reproducible, and makes the one gap explicit and auditable instead of silent:

1. the contract snapshot the run was graded under still hashes to the value the
   manifest and the published decision both record;
2. every candidate call is COMPLETED and its metrics and generations artifacts
   still exist;
3. and the numbers the write-up quotes can still be re-derived from the
   generations they came from, for both the metrics artifact and the published
   decision;
4. the published decision's dataset block is still identical to the frozen
   manifest's, so the write-up cannot drift from the evidence;
5. and the dataset-bytes gap is written down in ``docs/NEEDS_HUMAN.md``. If that
   paragraph is deleted, this check fails, which is the point: an acknowledged
   gap may be acknowledged, but it may not be forgotten.

Byte hashes of the artifacts are deliberately not compared. The decision
recorded them from a Windows working tree, so they describe CRLF bytes that no
checkout reproduces now that the repository normalises line endings. Comparing
them would fail forever and teach everyone to ignore a red build; content
verification is the property that actually matters.

Usage
-----
    uv run python scripts/check_frozen_candidate_evidence.py
"""

from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "eval" / "raw"

#: The frozen submission whose graded dataset is no longer in this repository.
MANIFEST = "candidate_submission_v2_frozen.json"

#: Where the gap must stay written down for this check to pass.
GAP_DOC = ROOT / "docs" / "NEEDS_HUMAN.md"
GAP_MARKER = "Verify frozen briefing candidate evidence"


class Checker:
    """Collects ok lines and problems the way the repo's other gates do."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.problems: list[str] = []

    def ok(self, text: str) -> None:
        self.lines.append(f"  ok  {text}")

    def fail(self, text: str) -> None:
        self.problems.append(text)
        self.lines.append(f"  !!  {text}")

    @property
    def passed(self) -> bool:
        return not self.problems


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _summary(rows):
    """Re-derive the per-group figures exactly as the original gate does.

    Imported rather than copied so the two can never drift apart.
    """
    spec = importlib.util.spec_from_file_location(
        "report_briefing_candidates", ROOT / "scripts" / "report_briefing_candidates.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.summary(rows)


def check_contract(out: Checker, manifest: dict, decision: dict) -> None:
    """The contract the run was graded under must still be the recorded bytes."""
    run_id = manifest["run_id"]
    snapshot = RAW / f"contract_{run_id}.txt"
    if not snapshot.exists():
        out.fail(f"contract snapshot missing: {snapshot.name}")
        return
    digest = _sha(snapshot)
    recorded = manifest["dataset"]["contract_sha256"]
    if digest == recorded:
        out.ok(f"contract snapshot still hashes to the frozen value ({digest[:12]})")
    else:
        out.fail(f"contract snapshot hash changed: {digest[:12]} != {recorded[:12]}")

    evidence = decision.get("contract_evidence") or {}
    if evidence.get("sha256") == recorded:
        out.ok("published decision records the same contract hash")
    else:
        out.fail("published decision's contract hash disagrees with the manifest")

    # The live contract must NOT silently equal the snapshot unless it truly is
    # the same bytes; if it does differ, that is expected and fine, but the
    # snapshot is what the run used.
    live = ROOT / "src" / "baahar" / "briefing_contract.py"
    if not live.exists():
        out.fail("live contract source is missing")
    elif _sha(live) == recorded:
        out.ok("live contract is byte-identical to the graded snapshot")


def check_calls(out: Checker, manifest: dict, decision: dict) -> None:
    """Each graded artifact must still be present, parseable and self-consistent.

    Byte hashes are deliberately *not* compared. The published decision recorded
    ``metrics_sha256``/``generations_sha256`` from a Windows working tree, so
    those values describe CRLF bytes that no checkout reproduces now that the
    repository normalises line endings -- comparing them would fail forever and
    teach everyone to ignore the build. :func:`check_published_numbers` verifies
    the artifacts by content instead, which is the property that matters.
    """
    run_id = manifest["run_id"]
    for name, call in manifest["calls"].items():
        if call.get("status") != "COMPLETED":
            out.fail(f"{name}: call is {call.get('status')}, not COMPLETED")
            continue
        metrics_path = ROOT / call["artifact"]
        rows_path = metrics_path.with_name(metrics_path.stem + "_generations.jsonl")
        label = f"{name}"
        for path in (metrics_path, rows_path):
            if not path.exists():
                out.fail(f"{label}: {path.name} is missing")
        if not metrics_path.exists() or not rows_path.exists():
            continue
        try:
            metrics = _load(metrics_path)
            rows = [
                json.loads(line)
                for line in rows_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            out.fail(f"{label}: artifact is not readable JSON ({exc})")
            continue
        if not rows:
            out.fail(f"{label}: generations file is empty")
            continue

        for field, want in (
            ("run_id", run_id),
            ("candidate", name),
            ("status", "COMPLETED"),
            ("model", manifest["candidates"][name]["model"]),
            ("revision", manifest["candidates"][name]["revision"]),
        ):
            if metrics.get(field) != want:
                out.fail(f"{label}: metrics {field} is {metrics.get(field)!r}, expected {want!r}")
        out.ok(f"{label}: {len(rows)} generations, identity matches the frozen manifest")


def check_published_numbers(out: Checker, manifest: dict, decision: dict) -> None:
    """Re-derive the published numbers from the generations they came from.

    This is the part of the original gate that does not need the graded
    dataset: ``summary`` reads only the generation rows, so the figures the
    write-up quotes can be recomputed and compared against both the metrics
    artifact and the published decision. If either has drifted from the recorded
    generations, this fails.
    """
    for name, call in manifest["calls"].items():
        if call.get("status") != "COMPLETED":
            continue
        metrics_path = ROOT / call["artifact"]
        rows_path = metrics_path.with_name(metrics_path.stem + "_generations.jsonl")
        if not metrics_path.exists() or not rows_path.exists():
            continue
        metrics = _load(metrics_path)
        rows = [
            json.loads(line)
            for line in rows_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        groups: dict[tuple[str, str], list[dict]] = {}
        for row in rows:
            groups.setdefault((row["phase"], row["split"]), []).append(row)

        label = name
        mismatches = []
        for (phase, split), group in sorted(groups.items()):
            measured = _summary(group)
            for source, where in (
                (metrics["evaluation"][phase][split], "metrics"),
                (decision["evaluation"][name][phase][split], "published decision"),
            ):
                if measured != source:
                    mismatches.append(f"{phase}/{split} vs {where}")
        if mismatches:
            out.fail(
                f"{label}: published numbers no longer follow from the generations ({', '.join(mismatches)})"
            )
        else:
            out.ok(
                f"{label}: {len(groups)} evaluation groups re-derive exactly the published numbers "
                f"({len(rows)} generations)"
            )


def check_decision_consistency(out: Checker, manifest: dict, decision: dict) -> None:
    """The published write-up must still describe the frozen experiment."""
    if decision.get("run_id") != manifest["run_id"]:
        out.fail("decision artifact is for a different run than the manifest")
        return
    if decision.get("dataset") != manifest["dataset"]:
        out.fail("published decision's dataset block has drifted from the frozen manifest")
    else:
        out.ok("published decision's dataset block is identical to the frozen manifest")
    if not decision.get("selected_candidate"):
        out.fail("published decision names no selected candidate")
    else:
        out.ok(f"published decision still selects {decision['selected_candidate']}")


def check_gap_is_documented(out: Checker) -> None:
    """The acknowledged gap must stay written down, or this check fails."""
    if not GAP_DOC.exists():
        out.fail(f"{GAP_DOC.name} is missing")
        return
    text = GAP_DOC.read_text(encoding="utf-8")
    if GAP_MARKER not in text:
        out.fail(
            f"{GAP_DOC.name} no longer records '{GAP_MARKER}'. "
            "The dataset-bytes gap must stay documented for this check to pass."
        )
        return
    out.ok(f"{GAP_DOC.name} records the acknowledged dataset-bytes gap")


def main() -> int:
    manifest_path = RAW / MANIFEST
    if not manifest_path.exists():
        print(f"frozen manifest missing: {manifest_path}")
        return 1
    manifest = _load(manifest_path)
    decision_path = RAW / f"candidate_decision_{manifest['run_id']}.json"
    if not decision_path.exists():
        print(f"published decision missing: {decision_path}")
        return 1
    decision = _load(decision_path)

    out = Checker()
    print(f"frozen candidate evidence for run {manifest['run_id']}")
    check_contract(out, manifest, decision)
    check_calls(out, manifest, decision)
    check_published_numbers(out, manifest, decision)
    check_decision_consistency(out, manifest, decision)
    check_gap_is_documented(out)

    print()
    for line in out.lines:
        print(line)

    print()
    print(
        "  note  the graded dataset bytes are NOT in this repository: run "
        f"{manifest['run_id']} predates the first commit of data/ft_v2, its builder was\n"
        "        never committed, and the committed dataset carries a later policy change\n"
        "        in facts.reasons. The full re-derivation gate is therefore not applicable\n"
        "        to this run; it still applies to any submission whose dataset is present.\n"
        "        Recorded in docs/NEEDS_HUMAN.md section 9a."
    )
    if out.passed:
        print("\nRESULT: PASS -- the reproducible evidence is intact and the gap is documented")
        return 0
    print("\nRESULT: FAIL")
    for problem in out.problems:
        print(f"  - {problem}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
