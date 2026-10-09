"""Offline orchestration checks; no GPU, auth request, or image build."""

import builtins
import importlib.util
import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

modal = pytest.importorskip("modal", reason="optional Modal client not installed")
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("modal_runner", ROOT / "scripts/fine_tune_modal.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_dry_run_never_starts_app(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("dry-run tried to start a remote app")

    monkeypatch.setattr(runner.app, "run", forbidden)
    assert runner.main(["--dry-run"]) == 0


def test_invalid_parameters_rejected():
    with pytest.raises(SystemExit) as exc:
        runner.main(["--epochs", "0", "--dry-run"])
    assert exc.value.code == 2


def test_remote_error_is_readable_without_vendor_packages(monkeypatch):
    class VendorError(Exception):
        pass

    def fail(*args):
        raise VendorError("GPU memory exhausted")

    monkeypatch.setattr(runner, "_train", fail)
    with pytest.raises(RuntimeError, match="VendorError: GPU memory exhausted"):
        runner.train.local(16, 3, 0.0002, 2, 768, "offline-error-test")


def test_remote_module_import_does_not_require_dotenv(monkeypatch):
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "dotenv":
            pytest.fail("remote container attempted to import local dotenv")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(modal, "is_local", lambda: False)
    monkeypatch.setattr(builtins, "__import__", guarded_import)
    remote_spec = importlib.util.spec_from_file_location(
        "remote_modal_runner", ROOT / "scripts/fine_tune_modal.py"
    )
    remote_module = importlib.util.module_from_spec(remote_spec)
    remote_spec.loader.exec_module(remote_module)


def test_detached_submission_records_call_without_waiting(monkeypatch, tmp_path):
    from modal.config import config

    (tmp_path / "data/ft").mkdir(parents=True)
    for name in ("train.jsonl", "val.jsonl"):
        (tmp_path / "data/ft" / name).write_bytes((ROOT / "data/ft" / name).read_bytes())
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(config, "get", lambda key: "test-auth")
    monkeypatch.setattr(modal, "enable_output", nullcontext)
    contexts = []

    def run(*, detach):
        contexts.append(detach)
        return nullcontext()

    submissions = []

    def spawn(**kwargs):
        submissions.append(kwargs)
        return SimpleNamespace(object_id="fc-offline-test")

    monkeypatch.setattr(runner.app, "run", run)
    monkeypatch.setattr(runner, "train", SimpleNamespace(spawn=spawn))
    assert runner.main(["--detach"]) == 0
    manifests = list((tmp_path / "eval/raw").glob("modal_submission_*.json"))
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text())
    assert manifest["call_id"] == "fc-offline-test"
    assert manifest["status"] == "SUBMITTED"
    assert manifest["parameters"] == submissions[0]
    assert contexts == [True]
