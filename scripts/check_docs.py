#!/usr/bin/env python
"""Verify the claims in post.md, README.md and docs/DOD.md against reality.

``scripts/check_results.py`` guards ``eval/RESULTS.md``. It does not open the other
published documents, and those have drifted four separate times:

* ``post.md`` credited the briefing rubric judge as ``gemini-2.5-flash``. The raw
  artifact records ``gemini-3.5-flash-lite``; ``gemini-2.5-flash`` appears there
  only as a *rejected candidate*. The one sentence whose entire job is to prove
  Baahar is not graded by its own model family credited the wrong grader.
* ``post.md`` claimed "291 tests pass offline". ``docs/DOD.md`` claimed "173
  passed". Two documents, two numbers, neither of them current.
* ``post.md`` quoted a ``naqi_basis`` literal the code stopped emitting once the
  conservative-NAQI fix landed, so the worked example no longer showed a value any
  user could observe.
* ``post.md`` claimed "All 24 hours, zero disagreements" between TabPFN and the
  heuristic. No artifact records that comparison, so nothing could check it.

Every one of those is a transcription error -- the exact failure
``check_results.py`` exists to catch, in a file that gate never reads. So this
opens those files, and derives truth from the repository and the raw artifacts
rather than from another document.

What it checks
--------------
1. Every "N tests pass" / "N passed" claim matches the suite that actually runs.
2. The judge named in ``post.md`` is the judge the briefing artifact recorded.
3. The ``naqi_basis`` literal in ``post.md`` is a value the code actually emits.
4. Any document quoting a TabPFN accuracy carries the same not-like-for-like
   caveat ``eval/RESULTS.md`` carries, so a reader who only opens the README is
   not told a provisional number as if it were settled.
5. Any "N disagreements" claim is backed by a field in a raw artifact.

What it deliberately does NOT do
--------------------------------
* It does not judge whether prose is *good*. It checks facts that were wrong.
* It does not verify RESULTS.md. That is ``check_results.py``'s job, and the two
  scripts deliberately do not overlap.

Usage
-----
    uv run python scripts/check_docs.py
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "eval" / "raw"

#: The published prose, in the order a judge is likely to read it.
DOCS: tuple[str, ...] = ("post.md", "README.md", "docs/DOD.md")

#: "291 tests pass offline", "173 tests passed", "291 offline tests"
_TESTS_PASS_RE = re.compile(r"\b(\d{2,5})\s+(?:offline\s+)?tests?\b", re.I)
#: "pytest -> 173 passed, no network"
_PASSED_RE = re.compile(r"\b(\d{2,5})\s+passed\b", re.I)
#: A backticked Gemini model name, e.g. `` `gemini-2.5-flash` ``.
_GEMINI_RE = re.compile(r"`([A-Za-z0-9._-]*gemini[A-Za-z0-9._-]*)`", re.I)
#: Any word meaning "this thing judged that thing": judged, judging, judge.
_JUDGE_RE = re.compile(r"\bjudg\w*", re.I)
#: ``naqi_basis = "..."`` as shown to a reader as a worked example.
_BASIS_RE = re.compile(r"naqi_basis\s*=\s*[\"']([^\"']+)[\"']")
#: TabPFN's published accuracy. Quoted in three documents, provisional in all.
_TABPFN_ACC_RE = re.compile(r"0\.8512")
_TABPFN_RE = re.compile(r"tabpfn", re.I)
#: Wording that admits the number is not settled.
_CAVEAT_RE = re.compile(
    r"provisional|not like-for-like|not re-fitted|was skipped|was SKIPPED", re.I
)
#: "zero disagreements", "0 of 24 disagreements"
_DISAGREE_RE = re.compile(r"\b(?:zero|0)\s+disagreements?\b", re.I)
_DISAGREE_FIELD_RE = re.compile(r"disagree", re.I)

#: Wording that marks a named model as *not* the judge that ran. Disclosing a
#: rejected candidate is the honest thing to do, so the gate has to accept it --
#: its own failure message tells the author to write exactly this.
_REJECTED_RE = re.compile(r"tried|rejected|exhausted|429|not the judge", re.I)

#: How far past the word "judge" to look for a model name. Covers the newline in
#: "judged by\n  `gemini-2.5-flash`" without swallowing the rest of the document.
_JUDGE_WINDOW = 160

#: Present-tense claims that TabPFN *currently* runs. If the newest run skipped
#: it, none of these may stand: the licence really was accepted once, but a past
#: run is not a present capability.
_TABPFN_RUNNING_RE = re.compile(
    r"licence accepted,?\s*TabPFN runs|TabPFN, for real|\*\*done\*\*[^\n]*0\.8512",
    re.I,
)

#: How far around a *named* model to look for a rejection marker.
_REJECT_WINDOW_BEFORE = 80
_REJECT_WINDOW_AFTER = 120


class Problem(list):
    """Collects failures, tagged so the printer can separate ok from bad."""

    def add(self, text: str, *, ok: bool = False) -> None:
        self.append(("ok " if ok else "!! ") + text)

    @property
    def failed(self) -> int:
        return sum(1 for row in self if row.startswith("!!"))


def collect_test_counts() -> tuple[int | None, dict[str, int]]:
    """Count what pytest collects: the suite total, and a per-file breakdown.

    Counting files or test functions by hand would be a second source of truth,
    which is the thing this script exists to eliminate.
    """
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    per_file: dict[str, int] = {}
    for line in proc.stdout.splitlines():
        match = re.match(r"^(\S+\.py):\s*(\d+)\s*$", line.strip())
        if match:
            # Only the suite's own files. The warnings summary at the end of a
            # collect prints bare ``.venv\...\something.py:43`` location lines,
            # which match the same shape as ``tests/test_x.py: 12`` and used to
            # be added to the total -- so the count moved with whatever warning
            # the machine happened to emit, and a correct claim failed at random.
            if not match.group(1).replace("\\", "/").startswith("tests/"):
                continue
            per_file[Path(match.group(1)).name] = int(match.group(2))
    if not per_file:
        return None, {}
    return sum(per_file.values()), per_file


def _line_of(text: str, index: int) -> str:
    end = text.find("\n", index)
    return text[text.rfind("\n", 0, index) + 1 : end if end != -1 else len(text)]


def newest_briefing() -> Path | None:
    """The most recent briefing artifact, which is where the judge is recorded."""
    candidates = sorted(RAW.glob("briefing_*.json"))
    return candidates[-1] if candidates else None


def check_test_counts(out: Problem) -> None:
    """Check "N tests" claims against the suite total or the named file.

    Both kinds appear in the docs and they drift independently: a claim about the
    whole suite goes stale every time a test is added, and a claim about one file
    goes stale when that file changes. So both are resolved against pytest rather
    than against each other.
    """
    total, per_file = collect_test_counts()
    if total is None:
        out.add("could not count the collected tests; pytest gave no per-file counts")
        return
    out.add(f"collected {total} tests", ok=True)

    file_ref = re.compile(r"(?:tests/)?(test_[\w]+\.py)")
    for name in DOCS:
        path = ROOT / name
        if not path.exists():
            out.add(f"{name}: missing")
            continue
        text = path.read_text(encoding="utf-8")
        handled: set[int] = set()
        for rx in (_TESTS_PASS_RE, _PASSED_RE):
            for match in rx.finditer(text):
                if match.start() in handled:
                    continue
                handled.add(match.start())
                claimed = int(match.group(1))
                line_no = text[: match.start()].count("\n") + 1
                line = _line_of(text, match.start())
                ref = file_ref.search(line)
                if ref:
                    target = ref.group(1)
                    actual = per_file.get(target)
                    if actual == claimed:
                        out.add(f"{name}:{line_no} {target} really has {claimed} tests", ok=True)
                    else:
                        out.add(
                            f"{name}:{line_no} claims {target} has {claimed} tests; "
                            f"pytest collects {actual}."
                        )
                    continue
                if claimed == total:
                    out.add(f"{name}:{line_no} suite count {total} matches", ok=True)
                else:
                    out.add(
                        f"{name}:{line_no} claims {claimed} tests pass; the suite collects "
                        f"{total}. Copy the real number from `uv run pytest`, or name the "
                        f"test file the count is about."
                    )


def check_judge(out: Problem, artifact: Path | None) -> None:
    if artifact is None:
        out.add("no briefing artifact found; cannot verify the judge claim")
        return
    data = json.loads(artifact.read_text(encoding="utf-8"))
    judge = data.get("judge_model")
    if not judge:
        out.add(f"{artifact.name}: no judge_model recorded; cannot verify the judge claim")
        return

    path = ROOT / "post.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")

    if judge in text:
        out.add(f"post.md names the recorded judge ({judge})", ok=True)
    else:
        out.add(f"post.md never mentions the recorded judge, {judge}")

    for window in _JUDGE_RE.finditer(text):
        tail = text[window.end() : window.end() + _JUDGE_WINDOW]
        for named in _GEMINI_RE.finditer(tail):
            model = named.group(1)
            if model == judge:
                continue
            around = text[
                max(0, window.end() + named.start() - _REJECT_WINDOW_BEFORE) : window.end()
                + named.end()
                + _REJECT_WINDOW_AFTER
            ]
            if _REJECTED_RE.search(around):
                out.add(
                    f"post.md names `{model}` near the judge but marks it as tried and"
                    f" rejected; `{judge}` is the one that actually ran",
                    ok=True,
                )
                continue
            out.add(
                f"post.md attributes the judging role to `{model}`, but "
                f"{artifact.name} records `{judge}`. If `{model}` was tried and "
                f"rejected, say so explicitly instead of crediting it."
            )


def check_basis(out: Problem) -> None:
    """The worked example must be a value a caller can actually observe."""
    try:
        from baahar.naqi import NAQI_BASIS
    except Exception as exc:  # noqa: BLE001
        out.add(f"could not import NAQI_BASIS: {exc}")
        return

    path = ROOT / "post.md"
    if not path.exists():
        return
    for match in _BASIS_RE.finditer(path.read_text(encoding="utf-8")):
        shown = match.group(1)
        if shown == NAQI_BASIS:
            out.add("post.md's naqi_basis example is a value the API emits", ok=True)
        else:
            out.add(
                f'post.md shows naqi_basis = "{shown}", but an hourly result now '
                f'carries "{NAQI_BASIS}". Show the value the product actually returns.'
            )


def check_tabpfn_caveat(out: Problem) -> None:
    """A provisional number must not be quoted as settled outside RESULTS.md."""
    for name in DOCS:
        path = ROOT / name
        if not path.exists() or name == "eval/RESULTS.md":
            continue
        text = path.read_text(encoding="utf-8")
        if not _TABPFN_RE.search(text):
            continue
        if not _TABPFN_ACC_RE.search(text):
            continue
        if _CAVEAT_RE.search(text):
            out.add(f"{name}: carries the TabPFN caveat alongside its numbers", ok=True)
        else:
            out.add(
                f"{name}: quotes TabPFN's 0.8512 without saying it was not re-fitted "
                f"on the current feature column. eval/RESULTS.md says so; this file must too."
            )


def check_disagreements(out: Problem) -> None:
    """A disagreement count is only publishable if some artifact recorded it."""
    for name in DOCS:
        path = ROOT / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if not _DISAGREE_RE.search(text):
            continue
        backed = any(
            _DISAGREE_FIELD_RE.search(k)
            for artifact in RAW.glob("*.json")
            for k in _top_level_keys(artifact)
        )
        if backed:
            out.add(f"{name}: the disagreement claim is backed by an artifact", ok=True)
        else:
            out.add(
                f"{name}: claims a disagreement count, but no raw artifact records one. "
                f"Either emit it from scripts/run_eval.py or drop the claim."
            )


def newest_tabular() -> Path | None:
    """The most recent tabular artifact, which records whether TabPFN ran."""
    candidates = sorted(RAW.glob("gono_*.json"))
    return candidates[-1] if candidates else None


def check_tabpfn_not_claimed_running(out: Problem, tabular: Path | None) -> None:
    """A past TabPFN run must not be written up as a present capability.

    This is the drift that is easiest to miss and most expensive to get wrong: the
    licence genuinely was accepted, so every sentence about it reads as true, and
    the reader concludes the category is live. The artifact settles it.
    """
    if tabular is None:
        return
    try:
        data = json.loads(tabular.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return
    entry = (data.get("results") or {}).get("tabpfn") or {}
    if str(entry.get("status", "")).upper() != "SKIPPED":
        return
    for name in (*DOCS, "docs/NEEDS_HUMAN.md"):
        path = ROOT / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for match in _TABPFN_RUNNING_RE.finditer(text):
            # A disclosure sitting on the same line is the fix this check asks
            # for, not a failure: "ran for real on 2026-10-07 ... (earlier
            # provisional run ... 0.8512)" is a past run written down as one.
            line = text[text.rfind("\n", 0, match.start()) + 1 : text.find("\n", match.start())]
            if _CAVEAT_RE.search(line):
                continue
            line_no = text[: match.start()].count("\n") + 1
            out.add(
                f"{name}:{line_no} presents TabPFN as currently running, but "
                f"{tabular.name} records it SKIPPED. Write it as a past run."
            )


def _top_level_keys(artifact: Path) -> list[str]:
    try:
        data = json.loads(artifact.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    return list(data) if isinstance(data, dict) else []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--briefings",
        default=None,
        help="explicit briefing_*.json to read the judge from (default: newest)",
    )
    args = parser.parse_args(argv)

    artifact = Path(args.briefings) if args.briefings else newest_briefing()
    if artifact is not None and not artifact.is_absolute():
        candidate = RAW / artifact.name
        artifact = candidate if candidate.exists() else artifact

    out = Problem()
    print(f"checking published prose against {artifact.name if artifact else 'no artifact'}")
    print()
    check_test_counts(out)
    check_judge(out, artifact)
    check_basis(out)
    check_tabpfn_caveat(out)
    check_tabpfn_not_claimed_running(out, newest_tabular())
    check_disagreements(out)
    print()
    for row in out:
        print("  " + row)
    print()
    if out.failed:
        print(f"RESULT: FAIL -- {out.failed} published claim(s) do not match reality")
        return 1
    print("RESULT: PASS -- published prose matches the repo and the raw artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
