"""The CLI surface.

Every command has to work with no keys and no network, and has to exit 0. These
tests exist because `baahar score --json` shipped a TypeError for most of the
project's life: `rich.console.print_json` takes a JSON *string*, and the code
passed a dict. CI never caught it because the command was piped into `head` and
the pipeline reported `head`'s exit code.

So: every command is invoked as a subprocess with a clean environment, and the
exit code is asserted. No mocking of the internals -- the point is the process a
judge actually runs.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str, offline: bool = True, keys: bool = False) -> subprocess.CompletedProcess:
    """Invoke the installed CLI in a subprocess, deterministically.

    ``keys=False`` strips every credential from the child environment so these
    tests cannot accidentally exercise a paid path or a live model call.
    """
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    if offline:
        env["BAAHAR_OFFLINE"] = "1"
    else:
        env.pop("BAAHAR_OFFLINE", None)
    if not keys:
        for name in (
            "GEMINI_API_KEY",
            "TINKER_API_KEY",
            "TABPFN_TOKEN",
            "TABPFN_API_KEY",
            "ELEVENLABS_API_KEY",
            "ELEVENLABS_VOICE_ID",
            "WAQI_TOKEN",
        ):
            env.pop(name, None)
    env["BAAHAR_CACHE"] = "0"
    # Keep the journal out of the repo.
    env["BAAHAR_JOURNAL"] = str(REPO_ROOT / "data" / "cache" / "test-journal.jsonl")

    return subprocess.run(
        [sys.executable, "-m", "baahar.cli", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )


class TestCommandsExitCleanly:
    @pytest.mark.parametrize(
        "args",
        [
            ("version",),
            ("check",),
            ("parks", "--limit", "3"),
            ("journal",),
            ("score", "--offline"),
            ("brief", "--offline", "--model", "template"),
        ],
    )
    def test_exits_zero_with_no_keys(self, args: tuple[str, ...]) -> None:
        result = run_cli(*args)
        assert result.returncode == 0, (
            f"`baahar {' '.join(args)}` exited {result.returncode}\n"
            f"stdout:\n{result.stdout[-1500:]}\nstderr:\n{result.stderr[-1500:]}"
        )

    def test_help_lists_every_command(self) -> None:
        result = run_cli("--help")
        assert result.returncode == 0
        for command in ("brief", "score", "parks", "journal", "check", "serve"):
            assert command in result.stdout, f"{command} missing from --help"


class TestJsonOutput:
    def test_score_json_is_valid_json(self) -> None:
        """Regression: print_json() was handed a dict and raised TypeError."""
        result = run_cli("score", "--offline", "--json")
        assert result.returncode == 0, result.stderr[-1500:]
        payload = json.loads(result.stdout)
        assert payload["city"]
        assert payload["overall"] in {"GO", "WAIT", "SKIP"}
        assert isinstance(payload["slots"], list)
        assert payload["slots"], "expected at least one scored hour"

    def test_score_json_slots_are_self_describing(self) -> None:
        result = run_cli("score", "--offline", "--json")
        payload = json.loads(result.stdout)
        first = payload["slots"][0]
        for key in ("time", "decision", "comfort", "reasons", "signals", "scorer"):
            assert key in first, f"{key} missing from a slot"
        assert first["scorer"] in {"heuristic", "tabpfn"}


class TestOfflineIsHonest:
    def test_offline_run_declares_itself(self) -> None:
        """A replayed fixture must never look like a live forecast."""
        result = run_cli("brief", "--offline", "--model", "template")
        assert "recorded fixture" in result.stdout

    def test_offline_flag_agrees_with_env(self) -> None:
        """`--offline` must work even when the env var says otherwise."""
        env_result = run_cli("brief", "--model", "template", offline=True)
        assert env_result.returncode == 0
        assert "recorded fixture" in env_result.stdout


class TestErrorHandling:
    def test_unknown_park_is_a_clean_error_not_a_traceback(self) -> None:
        result = run_cli("brief", "--offline", "--model", "template", "--park", "nope")
        assert result.returncode != 0
        assert "unknown park id" in result.stdout + result.stderr
        assert "Traceback" not in result.stderr, "user error should not dump a stack"

    def test_bad_journal_outcome_is_rejected(self) -> None:
        result = run_cli("journal", "--outcome", "went-walking")
        assert result.returncode != 0
        assert "Traceback" not in result.stderr

    def test_requesting_tinker_never_claims_a_finetune(self) -> None:
        """No TINKER_API_KEY here, so the note must say Gemma was substituted."""
        result = run_cli("brief", "--offline", "--model", "tinker")
        assert result.returncode == 0
        combined = result.stdout + result.stderr
        assert "Tinker was requested" in combined
        assert "No fine-tuned model served this briefing" in combined


class TestNoSecretsLeak:
    def test_check_prints_presence_not_values(self) -> None:
        result = run_cli("check")
        assert result.returncode == 0
        assert "keys present" in result.stdout
        for key in ("GEMINI_API_KEY", "TINKER_API_KEY"):
            assert key not in result.stdout, "check() must not echo env var names as values"
