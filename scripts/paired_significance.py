"""Paired significance test on the chronological holdout, written to an artifact.

Why this exists
---------------
`run_eval.py` reports a sample standard deviation across seeds, which measures
whether a fit is reproducible. It says nothing about whether two models differ on
the rows they were both scored against. At n=1,626 the binomial standard error on
accuracy is roughly 0.009 -- about eighteen times the consensus ensemble's seed sd
of 0.0005 -- so the seed column on its own would let anyone read a 0.008 gap as
decisive when it is not.

The models are fitted by calling `run_eval.fit_predict` directly. That is the whole
point: the first draft of this script re-declared the hyper-parameters, used the
standalone-LightGBM settings by mistake instead of the ensemble's, and produced an
ensemble accuracy 0.015 below the published mean. A second copy of a hyper-parameter
block is a second copy of a contract, and it drifted silently. Importing the real
function makes that class of bug impossible here.

What it deliberately does not do
--------------------------------
* TabPFN is opt-in via `--with-tabpfn`, because a fit costs ~358 s. Without the flag
  the artifact records TabPFN as untested rather than silently omitting it.
* It runs at a single seed. The published table is a five-seed mean; this is one
  fitted model per candidate, and the artifact records that so the two are not
  confused.
* It does not re-tune `tau_mod`, which was chosen against this same holdout. Treat
  the p-values as descriptive.

Usage
-----
    uv run python scripts/paired_significance.py
    uv run python scripts/paired_significance.py --seed 4
    uv run python scripts/paired_significance.py --with-tabpfn --out eval/raw/sig_t.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from math import comb
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def _load_run_eval():
    """Import scripts/run_eval.py as a module so we reuse its real fitters."""
    spec = importlib.util.spec_from_file_location(
        "_baahar_run_eval", ROOT / "scripts" / "run_eval.py"
    )
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError("could not load scripts/run_eval.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def mcnemar_exact(reference_ok: np.ndarray, challenger_ok: np.ndarray) -> dict:
    """Exact two-sided binomial McNemar on the discordant pairs.

    `reference_ok` is the model in the "left" column, `challenger_ok` the right one.
    """
    only_challenger = int((~reference_ok & challenger_ok).sum())
    only_reference = int((reference_ok & ~challenger_ok).sum())
    n = only_challenger + only_reference
    if n == 0:
        p = 1.0
    else:
        k = min(only_reference, only_challenger)
        p = min(1.0, 2.0 * sum(comb(n, i) for i in range(k + 1)) / (2**n))
    return {
        "only_challenger_right": only_challenger,
        "only_reference_right": only_reference,
        "n_discordant": n,
        "p_value_exact_two_sided": round(p, 6),
    }


def paired_bootstrap(
    reference_ok: np.ndarray, challenger_ok: np.ndarray, n_boot: int = 4000, seed: int = 12345
) -> dict:
    """Bootstrap the accuracy difference (challenger - reference) over rows."""
    rng = np.random.default_rng(seed)
    delta = challenger_ok.astype(float) - reference_ok.astype(float)
    idx = rng.integers(0, len(delta), size=(n_boot, len(delta)))
    samples = delta[idx].mean(axis=1)
    return {
        "delta_accuracy": round(float(delta.mean()), 6),
        "ci95_low": round(float(np.percentile(samples, 2.5)), 6),
        "ci95_high": round(float(np.percentile(samples, 97.5)), 6),
        "n_boot": n_boot,
        "bootstrap_seed": seed,
    }


def binomial_se(n: int, p: float = 0.85) -> float:
    return float(np.sqrt(p * (1 - p) / n))


def moderate_band_test(
    reference_pred: np.ndarray, challenger_pred: np.ndarray, yte: np.ndarray
) -> dict:
    """Paired test on the `moderate` band only, which is what decides the engine.

    Accuracy is dominated by `good` and `satisfactory`, which are easy and nearly
    balanced. The number that actually matters for an air-safety product is how
    many of the genuinely moderate hours get called moderate, so it gets its own
    interval rather than inheriting the accuracy one.

    Restricted to rows whose true band is `moderate`: on those rows "correct"
    means "predicted moderate". McNemar then compares the two models on that
    subset, and the bootstrap resamples *within* the subset so the interval is on
    the recall difference rather than on accuracy.
    """
    subset = yte == 2
    n = int(subset.sum())
    if n == 0:
        return {"n_moderate_rows": 0, "note": "the holdout has no moderate rows"}

    ref = reference_pred[subset] == 2
    chal = challenger_pred[subset] == 2
    boot = paired_bootstrap(ref, chal)
    return {
        "n_moderate_rows": n,
        "ensemble_recall": round(float(ref.mean()), 6),
        "challenger_recall": round(float(chal.mean()), 6),
        "ensemble_caught": int(ref.sum()),
        "challenger_caught": int(chal.sum()),
        "mcnemar": mcnemar_exact(ref, chal),
        "paired_bootstrap": boot,
        "binomial_se_ensemble": round(binomial_se(n, float(ref.mean())), 6),
        "binomial_se_challenger": round(binomial_se(n, float(chal.mean())), 6),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rows", default="data/eval/gono_rows.jsonl")
    ap.add_argument("--holdout", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument(
        "--with-tabpfn",
        action="store_true",
        help="also fit TabPFN (~358 s) so its gap is measured rather than untested",
    )
    ap.add_argument(
        "--out", default=None, help="artifact path (default: eval/raw/significance_<stamp>.json)"
    )
    args = ap.parse_args(argv)

    run_eval = _load_run_eval()
    from baahar.features import FEATURE_NAMES

    rows = run_eval.load_rows(ROOT / args.rows)
    rows.sort(key=lambda r: r["time"])
    cut = int(len(rows) * (1.0 - args.holdout))
    train, test = rows[:cut], rows[cut:]

    # to_matrix derives the lag columns itself and returns y alongside x; using it
    # keeps this script on the same feature construction the published run used.
    xtr, ytr = run_eval.to_matrix(train, FEATURE_NAMES)
    xte, yte = run_eval.to_matrix(test, FEATURE_NAMES)
    xtr, medians = run_eval.impute(xtr)
    xte, _ = run_eval.impute(xte, medians)

    if (ytr < 0).any() or (yte < 0).any():
        raise SystemExit("a row carries an unknown target band; refusing to publish a comparison")

    t0 = time.perf_counter()
    predictions: dict[str, np.ndarray] = {}
    notes: dict[str, str] = {}
    skipped: dict[str, str] = {}

    wanted = ["ensemble", "lgbm", "histgb", "rf"]
    if args.with_tabpfn:
        wanted.append("tabpfn")

    for name in wanted:
        try:
            preds, _secs, note = run_eval.fit_predict(
                name, xtr, ytr, xte, medians, seed=args.seed, feature_columns=FEATURE_NAMES
            )
        except Exception as exc:  # noqa: BLE001 - a missing model must be recorded, not faked
            skipped[name] = f"{type(exc).__name__}: {exc}"
            continue
        predictions[name] = np.asarray(preds, dtype=int)
        notes[name] = note

    if "ensemble" not in predictions:
        raise SystemExit("the reference model failed to fit; refusing to publish a comparison")

    ens_ok = predictions["ensemble"] == yte
    n_challengers = len(predictions) - 1
    payload = {
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "task": "paired significance test on the chronological holdout",
        "seed": args.seed,
        "n_train": len(train),
        "n_test": len(test),
        "n_features": len(FEATURE_NAMES),
        "fitted_by": "scripts/run_eval.py::fit_predict (imported, not re-declared)",
        "holdout_accuracy": {"consensus_ensemble": round(float(ens_ok.mean()), 6)},
        "binomial_se_at_p_0_85": round(binomial_se(len(yte)), 6),
        "comparisons": {},
        "notes": notes,
        "skipped": skipped,
        "not_tested": {},
        "caveats": [
            f"Single seed ({args.seed}). The published table is a five-seed mean; this is "
            "one fitted model per candidate.",
            "tau_mod was tuned against this same holdout, so treat the p-values as "
            "descriptive rather than as independent validation.",
            "McNemar counts discordant rows only; the bootstrap resamples rows and so "
            "assumes those rows are exchangeable.",
            f"This run makes {n_challengers} accuracy comparisons and {n_challengers} "
            "moderate-band ones, and applies no Bonferroni or FDR correction. Treat the "
            "individual p-values as descriptive and the consistency of direction across "
            "challengers as the finding, not any single threshold crossing.",
            "Moderate recall is measured only on the rows whose true band is moderate, so "
            "its interval is wider than the accuracy one. A holdout that size cannot "
            "resolve small differences in that band either.",
        ],
        "n_comparisons": 2 * n_challengers,
        "n_challengers": n_challengers,
    }

    for name, pred in predictions.items():
        if name == "ensemble":
            continue
        ok = pred == yte
        payload["comparisons"][name] = {
            "holdout_accuracy": round(float(ok.mean()), 6),
            "mcnemar": mcnemar_exact(ens_ok, ok),
            "paired_bootstrap": paired_bootstrap(ens_ok, ok),
            "moderate_recall": round(
                float(((pred == 2) & (yte == 2)).sum() / max(1, (yte == 2).sum())), 6
            ),
            # The deciding metric gets its own paired test and its own interval.
            "moderate_band": moderate_band_test(predictions["ensemble"], pred, yte),
        }

    payload["holdout_accuracy"]["_moderate_recall_ensemble"] = round(
        float(((predictions["ensemble"] == 2) & (yte == 2)).sum() / max(1, (yte == 2).sum())), 6
    )

    if "tabpfn" in skipped and "tabpfn" in payload["comparisons"] or "tabpfn" in skipped:
        payload["not_tested"]["tabpfn"] = (
            f"TabPFN was requested but did not fit: {skipped['tabpfn']}. "
            "Its gap is left unmeasured rather than asserted in either direction."
        )
    elif "tabpfn" not in predictions:
        payload["not_tested"]["tabpfn"] = (
            "TabPFN was not fitted because --with-tabpfn was not passed. A fit costs "
            "~358 s. Its gap is unmeasured here rather than asserted in either direction."
        )

    payload["elapsed_seconds"] = round(time.perf_counter() - t0, 1)

    if args.out:
        out = Path(args.out)
        if not out.is_absolute():
            out = ROOT / out
    else:
        stamp = time.strftime("%Y%m%dT%H%M%S%z")
        out = ROOT / "eval" / "raw" / f"significance_{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"paired significance -> {out}")
    print(
        f"seed {args.seed}  ensemble holdout accuracy {payload['holdout_accuracy']['consensus_ensemble']:.4f}"
    )
    print(f"binomial SE at n={len(yte)}: {payload['binomial_se_at_p_0_85']:.4f}")
    for name, comp in payload["comparisons"].items():
        print(
            f"  vs {name:12s} acc {comp['holdout_accuracy']:.4f}  "
            f"McNemar p={comp['mcnemar']['p_value_exact_two_sided']:.4f}  "
            f"dAcc {comp['paired_bootstrap']['delta_accuracy']:+.4f} "
            f"[{comp['paired_bootstrap']['ci95_low']:+.4f}, {comp['paired_bootstrap']['ci95_high']:+.4f}]  "
            f"modR {comp['moderate_recall']:.4f}"
        )
        mb = comp.get("moderate_band", {})
        if mb.get("n_moderate_rows"):
            print(
                f"     {'':12s} moderate band (n={mb['n_moderate_rows']}): "
                f"ensemble {mb['ensemble_caught']} vs {mb['challenger_caught']} caught, "
                f"McNemar p={mb['mcnemar']['p_value_exact_two_sided']:.4f}, "
                f"dRecall {mb['paired_bootstrap']['delta_accuracy']:+.4f} "
                f"[{mb['paired_bootstrap']['ci95_low']:+.4f}, "
                f"{mb['paired_bootstrap']['ci95_high']:+.4f}]"
            )
    for name, why in skipped.items():
        print(f"  skipped {name}: {why}")
    print(f"elapsed {payload['elapsed_seconds']} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
