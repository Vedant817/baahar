"""check_docs must count the published suite, not local lab files."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_docs import collect_test_counts, tracked_test_files  # noqa: E402


def test_tracked_test_files_are_published_modules() -> None:
    files = {path.replace("\\", "/") for path in tracked_test_files()}
    assert files, "git ls-files tests returned nothing"
    assert all(path.startswith("tests/test_") for path in files)
    assert "tests/conftest.py" not in files
    assert "tests/test_modal_runner.py" not in files
    assert "tests/test_score.py" in files


def test_untracked_test_file_does_not_move_the_published_count() -> None:
    extra = ROOT / "tests" / "_tmp_untracked_count_probe.py"
    extra.write_text("def test_probe():\n    assert True\n", encoding="utf-8")
    try:
        _total, per_file = collect_test_counts()
        assert extra.name not in per_file
    finally:
        extra.unlink(missing_ok=True)
