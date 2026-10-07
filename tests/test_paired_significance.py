"""The paired significance test must stay honest, and must stay published.

Failure modes this guards against, each of which has actually happened in this repo:

1. The script re-declares the models' hyper-parameters. The first draft did exactly
   that, copied the standalone-LightGBM settings instead of the ensemble's, and
   produced an ensemble accuracy 0.015 below the published mean while looking
   entirely plausible. The script now imports `run_eval.fit_predict`, and the test
   enforces the import rather than comparing token strings.
2. A model that fails to fit is quietly omitted. TabPFN costs ~358 s, so it is
   opt-in; if it is requested and fails, or not requested, the artifact must say so.
3. The disclosure is deleted. The seed-spread column understates sampling
   uncertainty by roughly 18x, so the paired test is the only thing standing between
   a reader and a false claim of significance.
4. The document drifts from the artifact it cites.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "paired_significance.py"
RESULTS = ROOT / "eval" / "RESULTS.md"
RAW = ROOT / "eval" / "raw"

CITED = re.compile(r"`(significance_[0-9A-Za-z_+\-]+\.json)`")
CITED_TABULAR = re.compile(r"`(gono_[0-9A-Za-z_+\-]+\.json)`")


def _artifact() -> dict:
    match = CITED.search(RESULTS.read_text(encoding="utf-8"))
    assert match, "RESULTS.md no longer cites a paired-significance artifact"
    path = RAW / match.group(1)
    assert path.exists(), f"RESULTS.md cites {match.group(1)}, which is absent"
    return json.loads(path.read_text(encoding="utf-8"))


def _text() -> str:
    return RESULTS.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# the script must not own a second copy of the models
# --------------------------------------------------------------------------


def test_script_reuses_run_eval_instead_of_copying_hyperparameters() -> None:
    """Every model must come from `run_eval.fit_predict`.

    A hard-coded hyper-parameter in this script is a second copy of a contract that
    can drift silently, and one already did.
    """
    src = SCRIPT.read_text(encoding="utf-8")
    assert "run_eval.fit_predict" in src, "the script must fit via run_eval.fit_predict"

    for token in (
        "n_estimators=",
        "learning_rate=",
        "num_leaves=",
        "max_depth=",
        "reg_alpha=",
        "reg_lambda=",
        "max_leaf_nodes=",
        "l2_regularization=",
        "min_child_samples=",
        "min_samples_leaf=",
        "LGBMClassifier(",
        "HistGradientBoostingClassifier(",
        "RandomForestClassifier(",
    ):
        assert token not in src, (
            f"paired_significance.py re-declares {token!r}; it must import the fitter "
            "from run_eval.py instead of keeping a second copy of the configuration"
        )


def test_script_loads_run_eval_from_disk_not_a_vendored_copy() -> None:
    """It must import the real module, so edits to run_eval.py take effect."""
    src = SCRIPT.read_text(encoding="utf-8")
    assert "spec_from_file_location" in src
    assert "run_eval.py" in src


# --------------------------------------------------------------------------
# the artifact must describe what it actually did
# --------------------------------------------------------------------------


def test_artifact_records_the_ensemble_modelled_at_seed_zero() -> None:
    """The single-seed caveat must be present and honest."""
    a = _artifact()
    assert a["seed"] == 0
    assert "run_eval" in a.get("fitted_by", ""), (
        "artifact must record that run_eval fitted the models"
    )


def test_ensemble_accuracy_lands_inside_the_published_seed_band() -> None:
    """A refit far from the published mean means the wrong model was fitted.

    This is the check that would have caught the wrong-hyper-parameters bug at
    publication time rather than after the numbers were written down.
    """
    a = _artifact()
    refit = a["holdout_accuracy"]["consensus_ensemble"]
    tabular = json.loads((RAW / CITED_TABULAR.search(_text()).group(1)).read_text(encoding="utf-8"))
    mean = tabular["results"]["ensemble"]["accuracy_mean"]
    sd = tabular["results"]["ensemble"]["accuracy_sd"]
    # Generous band: 6 sd of seed noise, floored at a half-point so an sd of 0
    # (a deterministic model) still gets a usable tolerance.
    tolerance = max(6 * sd, 0.005)
    assert abs(refit - mean) <= tolerance, (
        f"the seed-0 refit scored {refit:.4f} but the published five-seed mean is "
        f"{mean:.4f} +/- {sd:.4f}; outside {tolerance:.4f} the script is fitting a "
        "different model from the one the results document describes"
    )


@pytest.mark.parametrize("field", ["n_train", "n_test", "n_features"])
def test_artifact_matches_the_adopted_run(field: str) -> None:
    """The significance run must describe the same split as the published table."""
    a = _artifact()
    tabular = json.loads((RAW / CITED_TABULAR.search(_text()).group(1)).read_text(encoding="utf-8"))
    expected = {
        "n_train": tabular["dataset"]["n_train"],
        "n_test": tabular["dataset"]["n_test"],
        "n_features": len(tabular["dataset"]["feature_columns"]),
    }[field]
    assert a[field] == expected, (
        f"paired test {field}={a[field]} disagrees with the adopted tabular run "
        f"({expected}); the two are describing different pipelines"
    )


def test_artifact_records_its_own_caveats() -> None:
    a = _artifact()
    caveats = " ".join(a["caveats"]).lower()
    assert "tau_mod" in caveats, "the tau_mod selection caveat is missing"
    assert "single seed" in caveats or "five-seed mean" in caveats


def test_artifact_says_something_about_tabpfn_either_way() -> None:
    """Measured or explicitly untested -- never silently absent."""
    a = _artifact()
    assert "tabpfn" in a["comparisons"] or a.get("not_tested", {}).get("tabpfn"), (
        "TabPFN must either be measured or recorded as untested"
    )


# --------------------------------------------------------------------------
# the document must match the artifact
# --------------------------------------------------------------------------


def test_results_quotes_every_mcnemar_p_value() -> None:
    a = _artifact()
    text = _text()
    for name, comp in a["comparisons"].items():
        p = comp["mcnemar"]["p_value_exact_two_sided"]
        assert f"{p:.4f}" in text, f"RESULTS.md does not quote the McNemar p-value for {name} ({p})"


def test_results_quotes_every_moderate_recall() -> None:
    """The safety band is the deciding metric; its numbers must be traceable."""
    a = _artifact()
    text = _text()
    for name, comp in a["comparisons"].items():
        r = comp["moderate_recall"]
        assert f"{r:.4f}" in text, f"RESULTS.md does not quote moderate recall for {name} ({r})"


def test_every_challenger_has_a_paired_test_on_the_safety_band() -> None:
    """The deciding metric needs its own interval, not the accuracy one.

    Accuracy is dominated by two easy bands. Quoting a recall with no uncertainty
    while attaching a binomial-SE argument to accuracy elsewhere in the same
    document would be inconsistent about which number we trust.
    """
    a = _artifact()
    for name, comp in a["comparisons"].items():
        mb = comp.get("moderate_band")
        assert mb, f"{name} has no paired test restricted to the moderate band"
        assert mb["n_moderate_rows"] > 0
        assert "mcnemar" in mb and "paired_bootstrap" in mb
        assert "ci95_low" in mb["paired_bootstrap"]


def test_the_artifact_admits_it_did_not_correct_for_multiplicity() -> None:
    """Eight comparisons without a correction must say so.

    Asserted on the substance -- a named correction that is explicitly *not*
    applied -- rather than on any single keyword, so rewording the caveat cannot
    quietly drop the disclosure.
    """
    a = _artifact()
    joined = " ".join(a["caveats"]).lower()
    assert a.get("n_comparisons", 0) >= 2
    assert a.get("n_challengers", 0) >= 1
    named = [k for k in ("bonferroni", "fdr", "benjamini", "holm", "tukey") if k in joined]
    assert named, (
        "the artifact must name a multiplicity correction and state that it is not applied"
    )
    assert "no " in joined and "correction" in joined, (
        "the artifact must say that no correction was applied, not merely name the methods"
    )
    assert str(a["n_comparisons"]) in joined or "comparisons" in joined, (
        "the artifact must state how many comparisons it makes"
    )


def test_results_reports_the_safety_band_counts() -> None:
    """The raw caught counts, in the paired form, so the claim is checkable by hand.

    Checking for the bare digits would pass on coincidence -- "71" occurs inside
    plenty of unrelated decimals in this document. The published form is
    "<challenger> vs <ensemble>", so that is what is asserted.
    """
    a = _artifact()
    text = _text()
    for name, comp in a["comparisons"].items():
        mb = comp["moderate_band"]
        pair = f"{mb['challenger_caught']} vs {mb['ensemble_caught']}"
        assert pair in text, (
            f"RESULTS.md does not report the moderate-band caught counts for {name} as {pair!r}"
        )


def test_the_withdrawn_contradictory_verdicts_are_gone() -> None:
    """The earlier, un-artifacted seed-4 numbers must not survive anywhere.

    They reported the ensemble and lightgbm as statistically indistinguishable at
    p=0.8919 on a comparison the corrected refit puts at p=0.6835 -- and were
    produced by a script measuring a differently-configured model. A results file
    that carries both verdicts is worse than one that carries either.
    """
    text = _text()
    for withdrawn in ("0.8919", "0.2543", "86.16%", "seed 4 serving models"):
        assert withdrawn not in text, (
            f"RESULTS.md still contains the withdrawn figure {withdrawn!r}; it came "
            "from a mis-configured refit and contradicts the published comparison"
        )


def test_significance_disclosure_is_not_removable_silently() -> None:
    text = _text().lower()
    assert "mcnemar" in text, "the paired-significance disclosure has been removed"
    assert "binomial standard error" in text, (
        "the reason the seed spreads are not significance has been removed"
    )


def test_tabpfn_caveat_is_stated_next_to_the_comparison() -> None:
    text = _text().lower()
    i = text.find("paired significance")
    j = text.find("### reproduce", i)
    window = text[i : j if j > i else i + 6000]
    assert "tabpfn" in window, (
        "the paired section must mention TabPFN; an unmeasured comparison must not "
        "read as a measured one"
    )
