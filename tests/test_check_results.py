"""
Regression suite for omitted or mistranscribed seed variability.

These guard the honesty gate itself rather than the model: that a mean published
without a spread is rejected, that a published spread matches the artifact, and
that the cells the gate used to skip silently are now checked. A gate that can
be fooled is worse than no gate, so its own failure modes need tests too.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_results  # noqa: E402


@pytest.fixture
def recorded_run():
    md = check_results.RESULTS.read_text(encoding="utf-8")
    citation = check_results.CITED_TABULAR_RE.search(md)
    path = check_results.RAW / f"{citation.group(1)}.json"
    return path, json.loads(path.read_text(encoding="utf-8"))


def table(entry, label="random forest", separator="+/-"):
    cells = []
    for metric in ("accuracy", "macro_f1"):
        cell = str(entry[f"{metric}_mean"])
        if entry.get(f"{metric}_sd") is not None:
            cell += f" {separator} {entry[f'{metric}_sd']}"
        cells.append(cell)
    safety = entry["safety"]
    return (
        "| model | accuracy | macro-F1 | skip_as_go | n(SKIP) |\n"
        "|---|---|---|---|---|\n"
        f"| {label} | {cells[0]} | {cells[1]} | "
        f"{safety['skip_as_go_rate']} | {safety['n_true_skip']} |\n"
    )


def failures(md, path):
    out = check_results.Problem()
    check_results.check_tabular(md, path, out)
    return [line for line in out if line.startswith("!!")]


@pytest.mark.parametrize("separator", ["+/-", "±"])
def test_recorded_means_and_spread_pass(recorded_run, separator):
    path, payload = recorded_run
    assert payload["results"]["rf"]["runs"] == 5
    assert not failures(table(payload["results"]["rf"], separator=separator), path)


@pytest.mark.parametrize("metric", ["accuracy", "macro_f1"])
@pytest.mark.parametrize("change", ["omit_sd", "wrong_sd", "wrong_mean", "missing_mean"])
def test_bad_multiseed_publication_fails(recorded_run, metric, change):
    path, payload = recorded_run
    entry = payload["results"]["rf"]
    md = table(entry)
    if change == "omit_sd":
        md = md.replace(f" +/- {entry[f'{metric}_sd']}", "", 1)
    elif change == "wrong_sd":
        md = md.replace(f"+/- {entry[f'{metric}_sd']}", "+/- 0.9", 1)
    else:
        replacement = "0.01" if change == "wrong_mean" else "SKIPPED"
        md = md.replace(str(entry[f"{metric}_mean"]), replacement, 1)
    assert any(f"rf.{metric}" in line for line in failures(md, path))


@pytest.mark.parametrize("key", ["majority", "persistence"])
def test_deterministic_baselines_need_no_spread(recorded_run, key):
    path, payload = recorded_run
    entry = payload["results"][key]
    md = table(entry, label=key)
    for metric in ("accuracy", "macro_f1"):
        md = md.replace(f" +/- {entry[f'{metric}_sd']}", "", 1)
    assert not failures(md, path)


def test_single_seed_artifact_still_passes():
    path = check_results.RAW / "gono_20261007T142204+0530.json"
    entry = json.loads(path.read_text(encoding="utf-8"))["results"]["rf"]
    assert not failures(table(entry), path)


def test_wrong_skip_count_fails(recorded_run):
    path, payload = recorded_run
    md = table(payload["results"]["rf"]).replace("| 24 |", "| 25 |")
    assert any("n_skip" in line for line in failures(md, path))


def test_comparison_table_also_requires_spread(recorded_run):
    path, payload = recorded_run
    entry = payload["results"]["rf"]
    first = table(entry)
    second = first.replace(f" +/- {entry['accuracy_sd']}", "", 1)
    md = first + f"\nArtifact: [{path.name}](raw/{path.name}).\n\n" + second
    out = check_results.Problem()
    check_results.check_additional_tabular(md, path, out)
    assert any("no standard deviation" in line for line in out)
