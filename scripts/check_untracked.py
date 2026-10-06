#!/usr/bin/env python
"""Fail if a file that must never be published is tracked in git.

Why this exists as its own script
--------------------------------
The existing CI secret gate greps tracked files for credential *shapes*. That
would not have caught the incident that actually happened here: `data/journal.jsonl`
was committed, and it contains no key. It is a person's unfinished field notes,
which is worse in a different way -- it publishes observations that were never
reviewed and that `docs/FIELD_TEST.md` deliberately keeps human-only. It had to
be force-pushed out of history.

So the rule here is not "no secrets" but "these paths are never tracked",
whatever their contents. `.gitignore` already says so; a file can be tracked
anyway via `git add -f`, a merge, or an editor that stages what it sees.

Usage
    uv run python scripts/check_untracked.py

Exits 0 when clean, 1 with a list of offenders otherwise.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Tracked paths that must never appear. Each entry is a comment about what
#: actually goes wrong, because "don't commit this" is not a reason.
#:
#: * `.env` / `.env.*` -- real API keys. `.env.example` is the committed
#:   template and is explicitly allowed, or the repo cannot document its config.
#: * `data/journal.jsonl` -- the human's own walk observations. Committed once,
#:   force-pushed out. Publishing unreviewed field notes next to a hand-written
#:   `docs/FIELD_TEST.md` produces two contradictory versions of the truth.
#: * `eval/artifacts/**` -- fitted TabPFN classifiers, 840 MB each.
#: * `*.pkl` -- same weights under a different directory.
#: * `data/cache/**` -- recorded upstream responses and generated briefing cache.
#:   The committed fixtures live in `data/samples/`; the cache is machine-local.
DENY_EXACT: frozenset[str] = frozenset({".env", "data/journal.jsonl"})
DENY_PREFIX: tuple[str, ...] = ("eval/artifacts/", "data/cache/")
DENY_SUFFIX: tuple[str, ...] = (".pkl",)

#: The one `.env*` path that is supposed to be tracked.
ALLOW_EXACT: frozenset[str] = frozenset({".env.example"})


def is_denied(path: str) -> bool:
    """Whether a repo-relative path is on the denylist.

    Pure and filesystem-free so the rule itself is unit-testable, not just the
    git plumbing around it.
    """
    # Compare on forward slashes: git always reports `/` even on Windows, and a
    # rule that only holds on the machine that wrote it is not a rule.
    normalised = path.strip().replace("\\", "/")
    # Only a leading `./` is noise. `lstrip("./")` would eat the dot of `.env`
    # and turn the single most important entry into a miss.
    while normalised.startswith("./"):
        normalised = normalised[2:]
    if normalised in ALLOW_EXACT:
        return False
    if normalised in DENY_EXACT or normalised.startswith(".env."):
        return True
    if any(normalised.startswith(prefix) for prefix in DENY_PREFIX):
        return True
    return normalised.endswith(DENY_SUFFIX)


def tracked_files(root: Path = ROOT) -> list[str]:
    """`git ls-files` for `root`, or a loud failure if git is unavailable."""
    try:
        out = subprocess.run(
            ["git", "ls-files"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"could not list tracked files: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    return [line for line in out.splitlines() if line.strip()]


def main() -> int:
    offenders = [path for path in tracked_files() if is_denied(path)]
    if offenders:
        print("::error::these paths must never be tracked in this repo:", file=sys.stderr)
        for path in offenders:
            print(f"  {path}", file=sys.stderr)
        print(
            "  If one of these is genuinely needed, fix .gitignore and this list "
            "in the same commit, and say why in the message.",
            file=sys.stderr,
        )
        return 1
    print("no denied paths are tracked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
