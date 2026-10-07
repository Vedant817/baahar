#!/usr/bin/env python
"""Verify that eval/RESULTS.md matches the raw run artifacts.

The point of this project is that no number is published unless it came from a
real run. That rule is only as good as the transcription step, and transcription
is exactly where a careful person makes a careful-looking mistake: a digit
transposed, a row copied from the wrong model, a stale run left in place.

So RESULTS.md is checked against the JSON files it claims to summarise.

What it checks
--------------
1. Dataset sizes and the holdout window quoted in the prose.
2. Accuracy/macro-F1 means and published sample standard deviations, plus
   SKIP rates and counts, in every go/no-go comparison table. Repeated fitted
   models must publish spread; deterministic baselines need not.
3. That classes absent from the holdout are *named* in RESULTS.md.
4. That the SKIP-cause breakdown in RESULTS.md matches the artifact, including
   the disclosure that no SKIP hour was caused by air quality.

What it deliberately does NOT do
--------------------------------
* It cannot judge whether the raw run was itself honest. No script can.
* It does not check prose. Numbers yes, sentences no.

Usage
    uv run python scripts/check_results.py
    uv run python scripts/check_results.py --tabular raw/gono_20261006T045056+0530.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval" / "RESULTS.md"
RAW = ROOT / "eval" / "raw"

#: RESULTS.md uses human-readable model names; the artifact uses short keys.
#: Keeping this map explicit means a rename on either side is a hard failure
#: rather than a silently skipped row.
ALIASES: dict[str, str] = {
    "majority class": "majority",
    "majority": "majority",
    "persistence": "persistence",
    "logistic regression": "logreg",
    "random forest": "rf",
    "gradient boosting": "histgb",
    "lightgbm": "lgbm",
    "tabpfn": "tabpfn",
    # `norm()` strips the trailing "(cpu)", so the row arrives here as
    # "tabpfn 9.1.0". RESULTS.md names the version and device because "TabPFN"
    # alone does not say which model produced the number.
    "tabpfn 9.1.0": "tabpfn",
    "consensus ensemble": "ensemble",
    "ensemble": "ensemble",
}


class Problem(list):
    """Collects failures, tagged so the printer can separate ok from bad."""

    def add(self, text: str, *, ok: bool = False) -> None:
        self.append(("ok " if ok else "!! ") + text)


def newest(pattern: str) -> Path | None:
    candidates = sorted(RAW.glob(pattern), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def newest_excluding(pattern: str, skip_fragments: set[str]) -> Path | None:
    """Newest match, ignoring runs that were known not to be publishable.

    A `--no-judge` run produces an artifact with the right texts but no rubric
    scores. It is the newest file on disk but it is not the run being published,
    so picking it blindly would make the briefing check pass vacuously.
    """
    candidates = [
        p
        for p in sorted(RAW.glob(pattern), key=lambda p: p.stat().st_mtime)
        if not any(frag in p.name for frag in skip_fragments)
    ]
    return candidates[-1] if candidates else None


#: RESULTS.md cites the artifact each section was written from, e.g.
#: "Tabular artifact: [`gono_20261006T125637+0530.json`](raw/...)". Extracting the
#: name lets the checker verify a document against the run that produced it rather
#: than against whichever run happened to finish most recently.
CITED_TABULAR_RE = re.compile(r"`(gono_[0-9A-Za-z_+\-]+)\.json`")


def parse_tables(text: str) -> list[list[list[str]]]:
    """Every markdown table in the document, as lists of cell lists."""
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):  # separator row
                continue
            current.append(cells)
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


def num(text: str) -> float | None:
    """Parse a cell as a number, or None if it is prose / SKIPPED."""
    text = text.strip().strip("*").replace("`", "")
    if not text or text.upper().startswith("SKIP"):
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    if not cleaned or cleaned in {"-", "."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def norm(name: str) -> str:
    """Strip markdown emphasis and anything after the model name."""
    name = name.strip().strip("*").strip()
    name = re.sub(r"\s*\(.*?\)\s*$", "", name)  # "random forest (300)"
    return name.strip().lower()


def check_dataset(md: str, raw_path: Path, out: Problem) -> None:
    payload = json.loads(raw_path.read_text(encoding="utf-8"))
    ds = payload["dataset"]

    # Anchored patterns. An earlier version searched for a bare "N rows" and
    # matched the *holdout* size, reporting 1626 against 8130 -- a false
    # accusation caused by an ambiguous regex.
    checks = [
        ("total rows", r"(\d[\d,]*)\s*hourly rows", ds["n_rows"]),
        ("train rows", r"[Tt]rain\s*\((\d[\d,]*)\)", ds["n_train"]),
        ("holdout rows", r"[Hh]oldout\s*\((\d[\d,]*)\)", ds["n_test"]),
    ]
    for label, pattern, expected in checks:
        match = re.search(pattern, md)
        if not match:
            out.add(f"dataset: could not find {label} in RESULTS.md (pattern {pattern!r})")
            continue
        got = int(match.group(1).replace(",", ""))
        if got != expected:
            out.add(f"dataset {label}: RESULTS.md says {got}, artifact says {expected}")
        else:
            out.add(f"dataset {label}: verified {got}", ok=True)

    absent = ds.get("absent_from_holdout") or []
    for band in absent:
        if band not in md:
            out.add(f"dataset: class {band!r} has zero holdout rows but RESULTS.md never says so")
    if absent:
        out.add(f"dataset: verified the zero-support disclosure for {', '.join(absent)}", ok=True)


def check_tabular(md: str, raw_path: Path, out: Problem) -> None:
    payload = json.loads(raw_path.read_text(encoding="utf-8"))
    results = payload["results"]

    table = None
    for candidate in parse_tables(md):
        header = {norm(c) for c in candidate[0]}
        if {"model", "accuracy"} <= header:
            table = candidate
            break
    if table is None:
        out.add("tabular: could not find the go/no-go comparison table")
        return

    # Parentheses in column names are meaningful: norm() is for model names
    # and would erase "(SKIP)", silently leaving that safety count unchecked.
    header = [c.strip().strip("*").lower() for c in table[0]]

    def column(*names: str) -> int | None:
        for name in names:
            if name in header:
                return header.index(name)
        return None

    col_acc = column("accuracy")
    col_f1 = column("macro-f1", "macro f1")
    col_skip = column("skip_as_go", "skip-as-go")
    col_nskip = column("n(skip)", "n skip")

    checked = 0
    for row in table[1:]:
        label = norm(row[0])
        key = ALIASES.get(label)
        if key is None:
            out.add(
                f"tabular: row {row[0]!r} is not in ALIASES, so it cannot be verified "
                "against the artifact. Add it or fix the name."
            )
            continue
        if key not in results:
            out.add(f"tabular: {key} is in RESULTS.md but not in {raw_path.name}")
            continue

        entry = results[key]
        if entry.get("status") != "OK":
            joined = " ".join(row).lower()
            if "skip" not in joined:
                out.add(
                    f"tabular {key}: artifact says {entry.get('status')} but RESULTS.md "
                    f"publishes numbers for it"
                )
            else:
                out.add(f"tabular {key}: correctly marked SKIPPED", ok=True)
            continue

        for name, col, expected in (
            ("accuracy", col_acc, entry.get("accuracy_mean", entry.get("accuracy"))),
            ("macro_f1", col_f1, entry.get("macro_f1_mean", entry.get("macro_f1"))),
            ("skip_as_go", col_skip, entry["safety"]["skip_as_go_rate"]),
            ("n_skip", col_nskip, entry["safety"]["n_true_skip"]),
        ):
            if col is None:
                out.add(f"tabular {key}.{name}: missing column in RESULTS.md")
                continue
            cell = row[col].replace("±", "+/-")
            parts = cell.split("+/-")
            got = num(parts[0])
            if got is None or expected is None:
                out.add(f"tabular {key}.{name}: missing or invalid published/artifact number")
                continue
            tolerance = 0.00005 if name in {"accuracy", "macro_f1"} else 0.0005
            if abs(got - float(expected)) > tolerance:
                out.add(f"tabular {key}.{name}: RESULTS.md says {got}, artifact says {expected}")
            else:
                checked += 1

            if name not in {"accuracy", "macro_f1"}:
                continue
            # These two baselines do not fit stochastic models. Repeating their
            # predictions is not a measurement of seed variability.
            needs_spread = entry.get("runs", 1) > 1 and key not in {"majority", "persistence"}
            if len(parts) == 1:
                if needs_spread:
                    out.add(f"tabular {key}.{name}: runs > 1 but no standard deviation published")
                continue
            sd = num(parts[1]) if len(parts) == 2 else None
            expected_sd = entry.get(f"{name}_sd")
            if sd is None or expected_sd is None:
                out.add(f"tabular {key}.{name}_sd: missing or invalid standard deviation")
            elif abs(sd - float(expected_sd)) > 0.00005:
                out.add(
                    f"tabular {key}.{name}_sd: RESULTS.md says {sd}, artifact says {expected_sd}"
                )
            else:
                checked += 1

    if checked:
        out.add(f"tabular: verified {checked} numbers against {raw_path.name}", ok=True)


def check_per_class(md: str, raw_path: Path, out: Problem) -> None:
    """Verify every "Per-class, <model>" table against the artifact.

    RESULTS.md publishes per-class precision/recall/F1 tables, which are a dozen
    numbers each. They were previously unchecked, which meant a stale or
    hand-edited per-class table would pass CI silently while the summary table
    beside it was verified -- the exact gap that let the old "TabPFN: SKIPPED"
    section sit in the document beside a table claiming it was the best model.
    """
    payload = json.loads(raw_path.read_text(encoding="utf-8"))
    results = payload.get("results") or {}
    if not results:
        return

    checked = 0
    # Matches "## Per-class, gradient boosting" and
    # "## Per-class, TabPFN 9.1.0 (cpu)". The model name may contain commas, so the
    # capture is greedy up to the end of the line and normalised afterwards.
    for match in re.finditer(r"^#+\s*Per-class,\s*(.+?)\s*$", md, re.MULTILINE | re.IGNORECASE):
        heading = match.group(1).strip().rstrip(":").strip()
        key = ALIASES.get(norm(heading))
        if key is None:
            # "TabPFN 9.1.0 (cpu)" -> try the leading words before the version.
            key = ALIASES.get(norm(re.split(r"\d+\.\d+", heading)[0]))
        if key is None or key not in results:
            out.add(
                f"per-class: section {heading!r} does not map to a model in "
                f"{raw_path.name}, so its numbers cannot be verified"
            )
            continue

        entry = results[key]
        if entry.get("status") != "OK" or not entry.get("per_class"):
            out.add(
                f"per-class: {heading} has a table in RESULTS.md but no per-class "
                f"data in {raw_path.name}"
            )
            continue

        per_class = entry["per_class"]
        # The table body starts after the heading and runs to the next heading.
        tail = md[match.end() :]
        nxt = re.search(r"^#+\s", tail, re.MULTILINE)
        body = tail[: nxt.start()] if nxt else tail

        for band, stats in per_class.items():
            row = re.search(rf"^\|\s*{re.escape(band)}\s*\|(.+)\|\s*$", body, re.MULTILINE)
            if row is None:
                if int(stats.get("support") or 0) == 0:
                    # Zero-support bands are legitimately absent or dashed.
                    continue
                out.add(
                    f"per-class {key}: band {band!r} has support "
                    f"{stats['support']} in the artifact but no row in RESULTS.md"
                )
                continue

            cells = [c.strip().replace("*", "") for c in row.group(1).split("|")]
            cells = [c for c in cells if c]
            if len(cells) < 4:
                out.add(f"per-class {key}.{band}: expected precision/recall/F1/support")
                continue

            for label, idx in (("precision", 0), ("recall", 1), ("f1", 2)):
                got = num(cells[idx])
                expected = stats.get(label)
                if got is None or expected is None:
                    continue
                if abs(got - float(expected)) > 0.0005:
                    out.add(
                        f"per-class {key}.{band}.{label}: RESULTS.md says {got}, "
                        f"artifact says {expected}"
                    )
                else:
                    checked += 1

            got_support = num(cells[3].replace("**", ""))
            if got_support is not None and abs(got_support - int(stats["support"])) > 0:
                out.add(
                    f"per-class {key}.{band}.support: RESULTS.md says {got_support}, "
                    f"artifact says {stats['support']}"
                )
            elif got_support is not None:
                checked += 1

    if checked:
        out.add(f"per-class: verified {checked} numbers against {raw_path.name}", ok=True)


def check_additional_tabular(md: str, raw_path: Path, out: Problem) -> None:
    """Comparison tables need the same checks as the adopted headline table."""
    headers = list(re.finditer(r"^\|\s*model\s*\|\s*accuracy\s*\|", md, re.MULTILINE))
    for header in headers[1:]:
        citations = list(re.finditer(r"gono_[0-9A-Za-z_+\-]+\.json", md[: header.start()]))
        if not citations:
            out.add("tabular comparison: no cited artifact before table")
            continue
        path = RAW / citations[-1].group()
        if not path.exists():
            out.add(f"tabular comparison: cited artifact {path.name} does not exist")
            continue
        check_tabular(md[header.start() :], path, out)


def check_skip_causes(md: str, raw_path: Path, out: Problem) -> None:
    payload = json.loads(raw_path.read_text(encoding="utf-8"))
    entry = next((v for v in payload["results"].values() if v.get("status") == "OK"), None)
    if not entry:
        return
    causes = entry["safety"].get("skip_cause_breakdown") or {}
    if not causes:
        return

    total = sum(causes.values())
    for cause, count in causes.items():
        label = cause.split("+")[0]
        pattern = rf"\|\s*{re.escape(label)}\s*\|\s*\**{count}\**\s*\|"
        if not re.search(pattern, md, re.IGNORECASE):
            out.add(
                f"skip causes: {count} {label} hours is not in RESULTS.md's breakdown "
                f"table (total {total})"
            )

    air = sum(v for k, v in causes.items() if "air" in k)
    if air == 0:
        if re.search(r"ZERO|zero", md) and re.search(r"air", md, re.IGNORECASE):
            out.add(
                "skip causes: verified that RESULTS.md discloses zero air-quality SKIPs",
                ok=True,
            )
        else:
            out.add(
                "skip causes: NO skip hour was caused by air quality, and RESULTS.md "
                "does not say so. That is the most important limitation in the eval."
            )


def check_metrics_honesty(md: str, raw_path: Path, out: Problem) -> None:
    """Verify that RESULTS.md discloses non-discrimination of safety metrics.

    Neither skip_as_go_rate nor decision_accuracy discriminates good air-quality
    models from catastrophic ones:
    - skip_as_go_rate is 0.0 for every model (including always-good and always-hazardous)
      because all true SKIPs are weather-caused and identical weather is fed to
      the policy.
    - decision_accuracy cannot discriminate always-good (0.9982) from real models
      (ensemble 0.9975) because 99.82% of holdout rows have target bands in
      {good, satisfactory, moderate}, which all map to the same decision.
    """
    if not re.search(
        r"skip_as_go.*(?:cannot discriminate|does not discriminate|unreachable)",
        md,
        re.IGNORECASE,
    ):
        out.add(
            "metrics honesty: RESULTS.md must disclose that skip_as_go cannot discriminate "
            "a good model from a catastrophic one (0.0 for all models, non-zero unreachable)"
        )
    elif not re.search(
        r"decision\s+acc.*(?:cannot discriminate|does not discriminate)", md, re.IGNORECASE
    ):
        out.add(
            "metrics honesty: RESULTS.md must disclose that decision acc cannot discriminate "
            "genuine models from catastrophic always-good"
        )
    elif not (
        re.search(r"always[- ]good.*0\.9982", md, re.IGNORECASE)
        and re.search(r"always[- ]hazardous.*0\.0148", md, re.IGNORECASE)
    ):
        out.add(
            "metrics honesty: RESULTS.md must report catastrophic baseline figures "
            "(always-good: 0.9982, always-hazardous: 0.0148)"
        )
    else:
        out.add(
            "metrics honesty: verified disclosures on metric non-discrimination and catastrophic baselines",
            ok=True,
        )


def check_briefings(md: str, raw_path: Path | None, out: Problem) -> None:
    """Cross-check the briefing tables against the briefing artifact."""
    if raw_path is None:
        return
    payload = json.loads(raw_path.read_text(encoding="utf-8"))
    summary = payload.get("summary")
    if not summary:
        out.add("briefings: artifact has no summary block")
        return

    # RESULTS.md compares "template" against "gemma".
    wanted = [w for w in ("template", "gemma") if w in summary]
    if not wanted:
        out.add("briefings: artifact has neither a template nor a gemma summary")
        return

    checked = 0
    for writer in wanted:
        stats = summary[writer]

        # The briefing figures are quoted as bare numbers in both documents, so
        # this check is "does this exact figure appear in RESULTS.md" rather than
        # a cell-by-cell table comparison. That is deliberately weaker than the
        # tabular check: it catches transcription slips, not missing rows.
        p50 = stats.get("latency_ms_p50")
        p95 = stats.get("latency_ms_p95")
        if p50 is not None:
            token = f"{p50:,}"
            if token in md:
                checked += 1
            else:
                out.add(f"briefings {writer}: latency p50 {token} does not appear in RESULTS.md")
        if p95 is not None:
            token = f"{p95:,}"
            if token in md:
                checked += 1
            else:
                out.add(f"briefings {writer}: latency p95 {token} does not appear in RESULTS.md")

        rubric = stats.get("rubric_mean_all")
        if rubric is not None:
            token = f"{rubric:.2f}"
            if token in md:
                checked += 1
            else:
                out.add(f"briefings {writer}: rubric mean {token} does not appear in RESULTS.md")

        if stats.get("hallucinated_park_rate") not in (0.0, None):
            out.add(
                f"briefings {writer}: hallucinated_park_rate is "
                f"{stats['hallucinated_park_rate']}, which RESULTS.md must not call zero"
            )

    health = payload.get("rubric_health") or {}
    for writer, h in health.items():
        if h.get("verdict", "ok").startswith("SUSPECT"):
            out.add(f"briefings {writer}: rubric_health says {h['verdict']}")
    if health:
        out.add("briefings: rubric_health reports no degenerate rubric", ok=True)

    if checked:
        out.add(f"briefings: verified {checked} figures against {raw_path.name}", ok=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tabular", default=None, help="explicit gono_*.json file name")
    ap.add_argument("--briefings", default=None, help="explicit briefing_*.json file name")
    ap.add_argument("--md", default=str(RESULTS))
    args = ap.parse_args(argv)

    md_path = Path(args.md)
    if not md_path.is_absolute():
        md_path = ROOT / md_path
    md = md_path.read_text(encoding="utf-8")

    if args.tabular:
        raw_path = RAW / Path(args.tabular).name
    else:
        # RESULTS.md names the artifact it was written from. Prefer that file
        # rather than the newest on disk.
        #
        # Why this matters: CI re-runs `run_eval.py` with no keys, which writes a
        # *new* artifact in which TabPFN is SKIPPED. Verifying the published
        # TabPFN numbers against that file would fail -- correctly, but for the
        # wrong reason. The published numbers came from the run that had the
        # licence, and that run's raw output is committed precisely so it can be
        # checked. A document that cites its own source is the invariant worth
        # enforcing; "newest file wins" silently verifies a document against
        # whatever happened to run last.
        cited = CITED_TABULAR_RE.search(md)
        candidate = RAW / f"{cited.group(1)}.json" if cited else None
        if candidate is not None and candidate.exists():
            raw_path = candidate
        else:
            if cited:
                print(
                    f"  !! RESULTS.md cites {cited.group(1)}.json, which is not in "
                    f"eval/raw/. Falling back to the newest artifact."
                )
            raw_path = newest("gono_*.json")

    brief_path = (
        RAW / Path(args.briefings).name
        if args.briefings
        else newest_excluding("briefing_*.json", {"050410"})
    )
    out = Problem()
    if raw_path is None:
        out.add("no eval/raw/gono_*.json artifact found; run scripts/run_eval.py")
        print(out[0])
        return 1

    for check in (
        check_dataset,
        check_tabular,
        check_additional_tabular,
        check_per_class,
        check_skip_causes,
        check_metrics_honesty,
    ):
        check(md, raw_path, out)
    try:
        check_briefings(md, brief_path, out)
    except Exception as exc:  # noqa: BLE001
        out.add(f"check_briefings raised {type(exc).__name__}: {exc}")

    for _ in ():
        try:
            check(md, raw_path, out)
        except Exception as exc:  # noqa: BLE001
            out.add(f"{check.__name__} raised {type(exc).__name__}: {exc}")

    print(f"checking {md_path.name} against {raw_path.name}\n")
    for line in out:
        print(f"  {line}")
    print()

    bad = [line for line in out if line.startswith("!! ")]
    if bad:
        print(f"RESULT: FAIL -- {len(bad)} problem(s)")
        print("\nEvery number in eval/RESULTS.md must be traceable to eval/raw/.")
        return 1
    print("RESULT: PASS -- published numbers match the raw artifacts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
