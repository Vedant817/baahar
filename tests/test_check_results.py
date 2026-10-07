"""
Regression suite for omitted or mistranscribed seed variability.

These guard the honesty gate itself rather than the model: that a mean published
without a spread is rejected, that a published spread matches the artifact, and
that the cells the gate used to skip silently are now checked. A gate that can
be fooled is worse than no gate, so its own failure modes need tests too.
"""

from __future__ import annotations

import json
import re
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


def test_metrics_honesty_passes_on_current_results(recorded_run):
    path, _ = recorded_run
    md = check_results.RESULTS.read_text(encoding="utf-8")
    out = check_results.Problem()
    check_results.check_metrics_honesty(md, path, out)
    assert not [line for line in out if line.startswith("!!")]


@pytest.mark.parametrize(
    "omission",
    ["skip_as_go", "decision_acc", "always_good", "always_hazardous"],
)
def test_metrics_honesty_fails_if_disclosure_missing(recorded_run, omission):
    path, _ = recorded_run
    md = check_results.RESULTS.read_text(encoding="utf-8")
    if omission == "skip_as_go":
        md = md.replace("skip_as_go", "skip_metric")
    elif omission == "decision_acc":
        md = md.replace("decision acc", "decision_metric")
    elif omission == "always_good":
        md = md.replace("0.9982", "0.9900")
    elif omission == "always_hazardous":
        md = md.replace("0.0148", "0.0100")
    out = check_results.Problem()
    check_results.check_metrics_honesty(md, path, out)
    assert any(line.startswith("!!") for line in out)


def test_significance_passes_on_current_results():
    md = check_results.RESULTS.read_text(encoding="utf-8")
    citation = check_results.CITED_SIGNIFICANCE_RE.search(md)
    assert citation, "RESULTS.md does not cite a significance artifact"
    sig_path = check_results.RAW / f"{citation.group(1)}.json"
    assert sig_path.exists()
    out = check_results.Problem()
    check_results.check_significance(md, sig_path, out)
    assert not [line for line in out if line.startswith("!!")]


def test_significance_gate_fails_if_claim_removed_while_artifact_remains():
    """Gate must notice a dropped disclosure if section is removed while artifact remains."""
    md = check_results.RESULTS.read_text(encoding="utf-8")
    citation = check_results.CITED_SIGNIFICANCE_RE.search(md)
    assert citation
    sig_path = check_results.RAW / f"{citation.group(1)}.json"
    stripped_md = re.sub(
        r"### Paired significance on the holdout.*?(?=\n### |\Z)",
        "",
        md,
        flags=re.DOTALL,
    )
    out = check_results.Problem()
    check_results.check_significance(stripped_md, sig_path, out)
    assert any(
        "significance: RESULTS.md has no 'Paired significance' section" in line for line in out
    )


@pytest.mark.parametrize(
    "omission,expected_error",
    [
        ("drop_tabpfn", "TabPFN"),
        ("drop_mcnemar", "McNemar"),
        ("drop_binomial_se", "binomial standard error"),
        ("drop_seed_0", "single-seed"),
        ("drop_tau_mod", "tau_mod"),
        ("wrong_p_value", "McNemar p-value"),
        ("wrong_accuracy", "holdout accuracy"),
        ("wrong_moderate_recall", "moderate recall"),
    ],
)
def test_significance_gate_notices_dropped_disclosure_or_wrong_number(omission, expected_error):
    md = check_results.RESULTS.read_text(encoding="utf-8")
    citation = check_results.CITED_SIGNIFICANCE_RE.search(md)
    sig_path = check_results.RAW / f"{citation.group(1)}.json"
    if omission == "drop_tabpfn":
        match = re.search(r"^#+\s*Paired significance[^\n]*", md, re.MULTILINE | re.IGNORECASE)
        tail = md[match.end() :]
        nxt = re.search(r"^#+\s", tail, re.MULTILINE)
        section = tail[: nxt.start()] if nxt else tail
        rest = tail[nxt.start() :] if nxt else ""
        replaced_section = re.sub(r"(?i)tabpfn", "OtherModel", section)
        md = md[: match.end()] + replaced_section + rest
    elif omission == "drop_mcnemar":
        md = md.replace("McNemar", "ChiSquared").replace("mcnemar", "chisquared")
    elif omission == "drop_binomial_se":
        md = md.replace("binomial standard error", "standard error")
    elif omission == "drop_seed_0":
        md = re.sub(r"(?i)seed[- ]?0", "run 1", md)
    elif omission == "drop_tau_mod":
        md = md.replace("tau_mod", "threshold")
    elif omission == "wrong_p_value":
        md = md.replace("0.6835", "0.0100")
    elif omission == "wrong_accuracy":
        md = md.replace("0.8622", "0.8999")
    elif omission == "wrong_moderate_recall":
        md = md.replace("0.6620", "0.7500")

    out = check_results.Problem()
    check_results.check_significance(md, sig_path, out)
    assert any(line.startswith("!!") and expected_error in line for line in out)
