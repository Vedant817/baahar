"""The fine-tuning dataset must agree with itself.

Found by running the fine-tune for real. 29 of 219 examples carried a
`meta.decision` that contradicted their own target text -- 26 labelled GO whose
briefing opened "Hold off", and 3 labelled WAIT whose briefing read like a GO.
The model reproduced those targets faithfully, which is the point: a fine-tune on
contradictory supervision learns to contradict its own label, and in the
direction that matters, writing encouraging copy for an hour the policy held off
for.

The cause was two different policy functions. The bucket key and the label came
from `apply_band_policy` (band, rain, heat); the briefing text is rendered from
the full policy in `score_heuristic`, which also applies park-gate hours. They
disagree on 45% of the corpus, almost all night hours where the band policy says
GO and the gates say WAIT.

These tests run offline against the committed dataset, so a regression is caught
without spending a credit.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "ft" / "baahar_briefings.jsonl"


def load() -> list[dict]:
    if not DATASET.exists():
        pytest.skip("fine-tuning dataset not built; run scripts/build_ft_dataset.py")
    return [
        json.loads(line)
        for line in DATASET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def register(text: str) -> str:
    """Which decision the briefing's own wording commits to.

    Deliberately keyed on the opening clause only. The dataset's register is
    carried by the first few words -- "Go at", "Hold off until", "Skip" -- so
    anything later is prose, not a decision.
    """
    t = text.strip().lower()
    if t.startswith("go at"):
        return "GO"
    if t.startswith("hold off"):
        return "WAIT"
    if t.startswith("skip") or "stay in" in t[:60] or "stay home" in t[:60]:
        return "SKIP"
    return "OTHER"


def test_every_label_matches_its_own_target_text() -> None:
    rows = load()
    bad = [
        (r["meta"]["decision"], register(r["messages"][-1]["content"]))
        for r in rows
        if r["meta"]["decision"] != register(r["messages"][-1]["content"])
    ]
    assert not bad, (
        f"{len(bad)} of {len(rows)} examples have a meta.decision that contradicts "
        f"their own briefing text: {Counter(bad)}. A model trained on this learns to "
        "contradict its label, and to do it in the encouraging direction."
    )


def test_no_example_commits_to_an_unrecognised_register() -> None:
    """Catches a template change that would silently fall through the check above."""
    rows = load()
    unknown = [r for r in rows if register(r["messages"][-1]["content"]) == "OTHER"]
    assert not unknown, (
        f"{len(unknown)} briefings open in a way register() cannot classify, so the "
        "consistency check above is not actually checking them"
    )


def test_all_three_decisions_are_present() -> None:
    """A fine-tune that never sees one register cannot learn it."""
    counts = Counter(r["meta"]["decision"] for r in load())
    for decision in ("GO", "WAIT", "SKIP"):
        assert counts[decision] > 0, f"no {decision} examples in the dataset"


def test_the_dataset_does_not_leak_into_the_tabular_holdout() -> None:
    """The eval holdout starts 2026-07-30; FT data must stop before it."""
    cutoff = max(r["meta"]["source_time"] for r in load())
    assert cutoff[:10] <= "2026-09-05", (
        f"fine-tuning data reaches {cutoff}, past the 2026-09-05 cutoff that protects "
        "the tabular holdout"
    )


def test_build_script_does_not_label_from_the_band_policy() -> None:
    """The bug, pinned at the source rather than only in the output.

    `apply_band_policy` is still imported for the initial bucketing, which is
    harmless now that the label is recomputed. What must not come back is using
    the bucket key as the meta label, so the assignment that defines `decision`
    has to be the one taken from the plan, and it has to happen after that plan
    is built.
    """
    src = (ROOT / "scripts" / "build_ft_dataset.py").read_text(encoding="utf-8")
    from_plan = re.search(r"decision\s*=\s*plan\.overall\.value", src)
    assert from_plan, (
        "build_ft_dataset.py must take the example's label from the plan that "
        "generated its text, not from the band-only policy bucket"
    )
    built = src.rindex("plan_for_row(")
    assert from_plan.start() > built, (
        "the label must be taken after plan_for_row() has run; taken before it, "
        "the label is the bucket key again and the contradiction returns"
    )
    # And the bucket loop must not be the thing that sets the emitted label.
    emitted = re.search(r'"decision":\s*(\w+)', src)
    assert emitted is not None
    tail = src[src.rindex("examples.append(") :]
    assert re.search(rf'"decision":\s*{emitted.group(1)}', tail), (
        "the emitted meta label must be the local recomputed decision"
    )
