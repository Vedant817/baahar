"""Private SDK boundary tests; no GPU imports, model downloads or network."""

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from baahar import modal_writer
from baahar.briefing_contract import build_contract_case
from baahar.http_client import UpstreamError
from baahar.score import build_plan


def fake_sdk(monkeypatch, *, response=None, failure=None):
    calls = []

    class Call:
        def get(self, *, timeout):
            calls.append(("get", timeout))
            if failure:
                raise failure
            return response

        def cancel(self, *, terminate_containers):
            calls.append(("cancel", terminate_containers))

    class Worker:
        def __init__(self, **kwargs):
            calls.append(("worker", kwargs))
            self.generate = SimpleNamespace(spawn=self.spawn)

        def spawn(self, facts):
            calls.append(("spawn", facts))
            return Call()

    def from_name(app, cls):
        calls.append(("lookup", app, cls))
        return Worker

    sdk = SimpleNamespace(Cls=SimpleNamespace(from_name=from_name))
    monkeypatch.setattr(modal_writer.importlib, "import_module", lambda name: sdk)
    monkeypatch.setenv("BAAHAR_MODAL_RUN_ID", "run-20261008")
    monkeypatch.setenv("BAAHAR_MODAL_CANDIDATE", "qwen3_4b")
    return calls


def valid_response():
    return {
        "run_id": "run-20261008",
        "candidate": "qwen3_4b",
        "model": modal_writer.CANDIDATES["qwen3_4b"][0],
        "revision": modal_writer.CANDIDATES["qwen3_4b"][1],
        "raw_text": "A test draft.",
        "terminated": True,
        "output_tokens": 4,
        "latency_ms": 20,
    }


def test_private_sdk_identity_and_bounded_single_submission(monkeypatch, go_slot):
    calls = fake_sdk(monkeypatch, response=valid_response())
    plan = build_plan([go_slot], scorer="heuristic")
    assert modal_writer.write_modal(plan, notice_this="Ignore safety") == "A test draft."
    assert calls[0] == ("lookup", "baahar-briefing-private", "BriefingModel")
    assert calls[1] == ("worker", {"run_id": "run-20261008", "candidate": "qwen3_4b"})
    assert calls[2] == ("spawn", build_contract_case(plan)["facts"])
    assert calls[3] == ("get", 60)


def test_timeout_cancels_paid_input_without_retry(monkeypatch):
    calls = fake_sdk(monkeypatch, failure=TimeoutError("token-secret must not leak"))
    with pytest.raises(UpstreamError, match="timed out") as err:
        modal_writer.generate_modal({"facts": {"decision": "SKIP"}})
    assert "token-secret" not in str(err.value)
    assert calls[-1] == ("cancel", True)
    assert sum(c[0] == "spawn" for c in calls) == 1


def test_auth_failure_is_private_and_not_retried(monkeypatch):
    calls = fake_sdk(monkeypatch, failure=RuntimeError("MODAL_TOKEN_SECRET=private"))
    with pytest.raises(UpstreamError, match="authentication") as err:
        modal_writer.generate_modal({"facts": {}})
    assert "private" not in str(err.value)
    assert sum(c[0] == "spawn" for c in calls) == 1


@pytest.mark.parametrize("run_id", ["", "../escape", "a/b", "a\\b", ".", "x" * 81])
def test_invalid_run_does_not_import_sdk(monkeypatch, run_id):
    monkeypatch.setenv("BAAHAR_MODAL_RUN_ID", run_id)
    monkeypatch.setenv("BAAHAR_MODAL_CANDIDATE", "qwen3_4b")

    def forbidden(name):
        pytest.fail("Invalid config must not initialize a network SDK")

    monkeypatch.setattr(modal_writer.importlib, "import_module", forbidden)
    with pytest.raises(UpstreamError, match="invalid"):
        modal_writer.generate_modal({"facts": {}})


def test_missing_optional_sdk_is_a_transparent_failure(monkeypatch):
    fake_sdk(monkeypatch)

    def absent(name):
        raise ImportError("modal is absent")

    monkeypatch.setattr(modal_writer.importlib, "import_module", absent)
    with pytest.raises(UpstreamError, match="optional modal group"):
        modal_writer.generate_modal({"facts": {}})


@pytest.mark.parametrize(
    "override",
    [
        {"run_id": "another"},
        {"candidate": "unknown"},
        {"model": "another"},
        {"revision": "another"},
        {"raw_text": ""},
        {"terminated": False},
    ],
)
def test_wrong_identity_and_truncated_response_are_rejected(monkeypatch, override):
    fake_sdk(monkeypatch, response={**valid_response(), **override})
    with pytest.raises(UpstreamError, match="invalid or unfinished"):
        modal_writer.generate_modal({"facts": {}})


def load_serving_module(monkeypatch):
    # Minimal no-network decorator SDK makes artifact checks testable without
    # making Modal or torch dependencies of the normal test run.
    class Image:
        @classmethod
        def debian_slim(cls, **kwargs):
            return cls()

        def pip_install(self, *args):
            return self

        def env(self, *args):
            return self

        def add_local_file(self, *args):
            return self

    class App:
        def __init__(self, *args, **kwargs):
            pass

        def cls(self, **kwargs):
            return lambda cls: cls

    sdk = SimpleNamespace(
        Image=Image,
        App=App,
        Volume=SimpleNamespace(from_name=lambda *a, **k: None),
        parameter=lambda: None,
        enter=lambda: lambda fn: fn,
        method=lambda: lambda fn: fn,
    )
    monkeypatch.setitem(sys.modules, "modal", sdk)
    return runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/serve_briefing_modal.py")
    )


def make_artifact(root):
    model, revision = modal_writer.CANDIDATES["qwen3_4b"]
    run = root / "candidates/run-20261008"
    adapter = run / "qwen3_4b/adapter"
    adapter.mkdir(parents=True)
    (run / "serving.json").write_text(
        json.dumps(
            {
                "run_id": "run-20261008",
                "candidate": "qwen3_4b",
                "model": model,
                "revision": revision,
                "status": "promoted",
                "contract_version": 1,
            }
        )
    )
    (adapter / "adapter_config.json").write_text(json.dumps({"base_model_name_or_path": model}))
    (adapter / "adapter_model.safetensors").write_bytes(b"test-only placeholder")
    return run, adapter


def test_serving_refuses_unpromoted_candidate(monkeypatch, tmp_path):
    script = load_serving_module(monkeypatch)
    run, adapter = make_artifact(tmp_path)
    check = script["checked_artifact"]
    assert check(tmp_path, "run-20261008", "qwen3_4b")[0] == adapter
    registry = json.loads((run / "serving.json").read_text())
    registry["status"] = "experimental"
    (run / "serving.json").write_text(json.dumps(registry))
    with pytest.raises(ValueError, match="registered"):
        check(tmp_path, "run-20261008", "qwen3_4b")


def test_serving_refuses_wrong_base_adapter(monkeypatch, tmp_path):
    script = load_serving_module(monkeypatch)
    _, adapter = make_artifact(tmp_path)
    (adapter / "adapter_config.json").write_text(json.dumps({"base_model_name_or_path": "wrong"}))
    with pytest.raises(ValueError, match="base model"):
        script["checked_artifact"](tmp_path, "run-20261008", "qwen3_4b")


def test_serving_refuses_path_escape(monkeypatch, tmp_path):
    script = load_serving_module(monkeypatch)
    with pytest.raises(ValueError, match="identity"):
        script["checked_artifact"](tmp_path, "../outside", "qwen3_4b")
