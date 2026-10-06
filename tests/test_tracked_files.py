"""The tracked-file denylist must match what `.gitignore` actually protects.

These are small tests about small rules, and the reason they exist is that the
previous CI gate was not enough. It grepped tracked files for credential shapes,
which cannot see `data/journal.jsonl` -- the file that was really committed here,
and which had to be force-pushed out of history. It holds a human's unreviewed
walk notes, not a key.

So the rule is now "these paths are never tracked", and these tests keep the rule
and the ignore file from drifting apart.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT / "scripts"))

from check_untracked import is_denied  # noqa: E402


class TestDenylist:
    @pytest.mark.parametrize(
        "path",
        [
            ".env",
            ".env.local",
            ".env.production",
            ".env.staging",
            "data/journal.jsonl",
            "eval/artifacts/tabpfn_gono.pkl",
            "eval/artifacts/nested/deep.pkl",
            "eval/artifacts/notes.txt",
            "data/cache/briefings/abc123.json",
            "data/cache/audio/brief_1.mp3",
            "some/other/place/model.pkl",
            "models\\tabpfn_gono.pkl",
        ],
    )
    def test_denied_paths(self, path: str) -> None:
        assert is_denied(path) is True, path

    @pytest.mark.parametrize(
        "path",
        [
            ".env.example",
            "README.md",
            "AGENTS.md",
            ".gitignore",
            "data/parks_blr.json",
            "data/samples/open_meteo_forecast.json",
            "eval/RESULTS.md",
            "eval/raw/gono_20261006T045056+0530.json",
            "scripts/check_untracked.py",
            "src/baahar/brief.py",
            "docs/FIELD_TEST.md",
        ],
    )
    def test_allowed_paths(self, path: str) -> None:
        """The gate must not be so broad that it fails on the repo itself."""
        assert is_denied(path) is False, path

    def test_it_ignores_a_leading_dot_slash(self) -> None:
        """.gitignore patterns and `git ls-files` output disagree about `./`."""
        assert is_denied("./.env") is True
        assert is_denied("./data/journal.jsonl") is True


class TestDenylistMatchesGitignore:
    """If `.gitignore` stops covering something, this test fails.

    That is the drift that matters: a denylist entry that no ignore rule backs is
    a rule that depends on everyone remembering to run the checker.

    Asked of `git check-ignore` rather than a re-implementation of gitignore
    matching. The rules here are simple, but "simple" is how hand-rolled glob
    code ends up disagreeing with git on the one path nobody tested -- and the
    first version of this test did exactly that, reporting `.env` as allowed
    because it stripped the dot off the front.
    """

    #: Every denied shape, with the reason it must stay untracked.
    CASES = {
        ".env": "secrets",
        ".env.local": "secrets",
        "data/journal.jsonl": "the human's unreviewed walk notes",
        "eval/artifacts/tabpfn_gono.pkl": "840 MB of fitted weights",
        "data/cache/briefings/abc.json": "machine-local cache",
    }

    @staticmethod
    def _ignored(path: str) -> bool:
        return (
            subprocess.run(
                ["git", "check-ignore", "--no-index", "--quiet", "--", path],
                cwd=ROOT,
                capture_output=True,
            ).returncode
            == 0
        )

    def test_gitignore_still_covers_the_denylist(self) -> None:
        for path, why in self.CASES.items():
            assert self._ignored(path), f".gitignore no longer covers {path} ({why})"

    def test_paths_that_must_stay_trackable_are_not_ignored(self) -> None:
        """The inverse. A `.gitignore` too broad would quietly unpublish the repo.

        `.env.example` is the committed configuration template: a judge cannot
        run `uv sync` correctly without it, so it has to stay tracked.
        """
        for path in (
            ".env.example",
            "README.md",
            "data/parks_blr.json",
            "eval/RESULTS.md",
            "eval/raw/gono_20261006T045056+0530.json",
            "scripts/check_untracked.py",
        ):
            assert not self._ignored(path), f".gitignore now blocks {path}, which must be tracked"


class TestScriptRunsHere:
    def test_the_script_passes_on_this_checkout(self) -> None:
        """The gate itself has to be green, or it gets ignored and then removed."""
        result = subprocess.run(
            [sys.executable, "scripts/check_untracked.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_the_script_fails_when_a_denied_path_is_tracked(self, tmp_path: Path) -> None:
        """Prove the gate can fail. A check never seen red is not known to work."""
        repo = tmp_path / "repo"
        (repo / "data").mkdir(parents=True)
        (repo / "scripts").mkdir()
        (repo / "scripts" / "check_untracked.py").write_text(
            (ROOT / "scripts" / "check_untracked.py").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
        (repo / "data" / "journal.jsonl").write_text('{"note": "a walk"}\n', encoding="utf-8")
        subprocess.run(["git", "add", "-f", "data/journal.jsonl"], cwd=repo, check=True)

        result = subprocess.run(
            [sys.executable, "scripts/check_untracked.py"],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, result.stdout + result.stderr
        assert "data/journal.jsonl" in result.stdout + result.stderr
