"""Freeze the consumed v15 diagnostic unchanged for a v16 regression comparison."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "eval/raw"


def main():
    training = json.loads((RAW / "candidate_submission_v16.json").read_text())
    target = RAW / "qualification_v16_regression_manifest.json"
    if target.exists():
        print(target)
        return
    previous = json.loads((RAW / "qualification_v15_manifest.json").read_text())
    runner = (RAW / "qualification_v15_preregistered_runner.py").read_text(encoding="utf-8")
    runner = runner.replace(
        'PREFIX = RAW / "qualification_v15"', 'PREFIX = RAW / "qualification_v16_regression"'
    )
    runner = runner.replace("20261008T112810Z-6067171e", training["run_id"])
    runner = runner.replace(
        "except modal.exception.TimeoutError:",
        "except (TimeoutError, modal.exception.TimeoutError):",
    )
    script = ROOT / "scripts/qualify_briefing_v16_regression_modal.py"
    script.write_text(runner, encoding="utf-8")
    suite = RAW / "qualification_v16_regression_suite.json"
    contract = RAW / "qualification_v16_regression_contract.py"
    suite.write_bytes((RAW / "qualification_v15_suite.json").read_bytes())
    contract.write_bytes((RAW / "qualification_v15_contract.py").read_bytes())
    for key in ("call_id", "app_id", "results"):
        previous.pop(key, None)
    previous.update(
        status="PREREGISTERED",
        suite=str(suite.relative_to(ROOT)),
        rubric_script_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
        adapter_path=f"/artifacts/candidates/{training['run_id']}/qwen3_4b/adapter",
        comparison="Consumed diagnostic regression only; identical suite and checker snapshot to v15, including known rubric defects.",
    )
    assert hashlib.sha256(suite.read_bytes()).hexdigest() == previous["suite_sha256"]
    assert hashlib.sha256(contract.read_bytes()).hexdigest() == previous["contract_sha256"]
    target.write_text(json.dumps(previous, indent=2), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
