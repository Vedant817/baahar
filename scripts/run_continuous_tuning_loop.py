"""Continuous autonomous tuning loop engine for Baahar briefing models on Modal.

Runs 20-25 iterations systematically exploring hyperparameters, capacity,
multi-hazard balancing, and latency profiles across Qwen2.5-7B and Qwen3-4B.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "eval" / "raw" / "continuous_tuning_ledger.jsonl"


def log(msg: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)


def run_command(args: list[str], timeout: int = 1200) -> tuple[int, str, str]:
    p = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def ensure_manifest_for_iteration(iteration_num: int) -> Path:
    manifest_path = ROOT / "eval" / "raw" / f"candidate_submission_v{iteration_num + 2}.json"
    if manifest_path.exists():
        return manifest_path
    
    # Template from v4
    template_path = ROOT / "eval" / "raw" / "candidate_submission_v4.json"
    if not template_path.exists():
        template_path = ROOT / "eval" / "raw" / "candidate_submission_v2_frozen.json"
    
    data = json.loads(template_path.read_text(encoding="utf-8"))
    
    # Phase schedule configurations
    if iteration_num <= 7:
        # Phase 1: Capacity & Learning Rate calibration
        lrs = [5e-5, 6e-5, 7e-5, 8e-5]
        ranks = [16, 24, 32]
        data["parameters"]["learning_rate"] = lrs[(iteration_num - 1) % len(lrs)]
        data["parameters"]["rank"] = ranks[(iteration_num - 1) % len(ranks)]
        data["parameters"]["alpha"] = data["parameters"]["rank"] * 2
    elif iteration_num <= 13:
        # Phase 2: Multi-hazard & adversarial injection balancing
        data["parameters"]["learning_rate"] = 5e-5
        data["parameters"]["rank"] = 32
        data["parameters"]["alpha"] = 64
        data["parameters"]["epochs"] = 3 + (iteration_num % 2)
    elif iteration_num <= 19:
        # Phase 3: Repetition penalty & length calibration
        data["parameters"]["max_new_tokens"] = 160
        data["parameters"]["warmup_fraction"] = 0.08
    else:
        # Phase 4: Production latency & seed validation
        data["parameters"]["seed"] = iteration_num * 101
    
    # Fresh run_id so artifacts never collide with the template's run
    import uuid

    data["run_id"] = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:8]
    # Reset tracking state for new submission
    data["status"] = "PENDING_SUBMISSION"
    data.pop("app_id", None)
    for c in data.get("calls", {}).values():
        c["status"] = "PENDING_SUBMISSION"
        c.pop("call_id", None)
        c.pop("artifact", None)
    
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    log(f"Generated manifest for Iteration {iteration_num}: {manifest_path.name}")
    return manifest_path


def poll_submission(manifest_path: Path, poll_seconds: int = 25) -> bool:
    log(f"Monitoring submission manifest: {manifest_path.name}")
    start_time = time.time()
    while True:
        code, stdout, stderr = run_command([
            "uv", "run", "--group", "modal", "python",
            "scripts/train_briefing_candidates_modal.py",
            "--fetch", str(manifest_path)
        ], timeout=120)
        
        # Primary signal: the durable manifest, not the fetcher's stdout,
        # which prints nothing once all entries are already COMPLETED.
        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            calls = manifest_data.get("calls", {})
            if calls and all(e.get("status") == "COMPLETED" for e in calls.values()):
                manifest_data["status"] = "COMPLETED"
                manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
                log(f"All candidates in {manifest_path.name} COMPLETED!")
                return True
        except Exception as manifest_exc:
            log(f"Manifest check error (will retry): {manifest_exc}")

        if "completed" in stdout and "still running" not in stdout and "not submitted" not in stdout:
            log(f"All candidates in {manifest_path.name} COMPLETED! Output:\n{stdout.strip()}")
            return True
        
        elapsed_min = (time.time() - start_time) / 60.0
        log(f"[{elapsed_min:.1f}m elapsed] Remote GPUs running... polling again in {poll_seconds}s")
        time.sleep(poll_seconds)


def run_iteration(iteration_num: int, dry_run: bool = False) -> dict:
    log(f"=== Starting Iteration {iteration_num} / 25 ===")
    manifest_path = ensure_manifest_for_iteration(iteration_num)
    
    if dry_run:
        log(f"[DRY RUN] Would submit Iteration {iteration_num} to Modal")
        return {"iteration": iteration_num, "status": "DRY_RUN"}
    
    existing = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    existing_completed = existing.get("status") == "COMPLETED" or (
        bool(existing.get("calls"))
        and all(e.get("status") == "COMPLETED" for e in existing["calls"].values())
    )
    if existing_completed:
        log(f"Manifest {manifest_path.name} already COMPLETED; ingesting without re-submitting.")
        if existing.get("status") != "COMPLETED":
            existing["status"] = "COMPLETED"
            manifest_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    else:
        # 1. Submit iteration to Modal with detached execution
        log(f"Submitting candidate training to Modal L40S GPUs (Manifest: {manifest_path.name})...")
        code, stdout, stderr = run_command([
            "uv", "run", "--group", "modal", "python",
            "scripts/train_briefing_candidates_modal.py",
            "--submit", "--detach", "--manifest", str(manifest_path)
        ], timeout=180)

        if code != 0:
            log(f"Submission failed! Error:\n{stderr}\n{stdout}")
            raise RuntimeError(f"Iteration {iteration_num} submission failed.")

        log(f"Successfully submitted to Modal! Output:\n{stdout.strip()}")

        # 2. Poll until completed
        poll_submission(manifest_path)
    
    # 3. Generate candidate decision report
    log(f"Generating decision report for Iteration {iteration_num}...")
    report_code, report_out, report_err = run_command([
        "uv", "run", "python", "scripts/report_briefing_candidates.py", str(manifest_path),
        "--markdown", str(ROOT / "eval" / "raw" / f"candidate_decision_v{iteration_num + 2}.md")
    ], timeout=120)
    log(f"Decision report output:\n{report_out.strip()}")
    
    # 4. Ingest and record into ledger
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    run_id = manifest_data["run_id"]
    decision_path = ROOT / "eval" / "raw" / f"candidate_decision_{run_id}.json"
    
    decision_summary = {}
    if decision_path.exists():
        decision_summary = json.loads(decision_path.read_text(encoding="utf-8"))
    
    entry = {
        "iteration": iteration_num,
        "run_id": run_id,
        "timestamp": time.time(),
        "manifest": str(manifest_path.relative_to(ROOT)),
        "status": decision_summary.get("status", "UNKNOWN"),
        "selected_candidate": decision_summary.get("selected_candidate"),
        "holdout_gate_passed": decision_summary.get("holdout_gate_passed", False),
    }
    
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    
    log(f"=== Completed Iteration {iteration_num} / 25 ===")
    return entry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=int, default=4, help="Start iteration (default: 4)")
    parser.add_argument("--target", type=int, default=25, help="Target iteration (default: 25)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate execution without cloud GPU calls")
    args = parser.parse_args()
    
    log(f"Starting Autonomous Training Sweep from Iteration {args.start} to {args.target}")
    for i in range(args.start, args.target + 1):
        run_iteration(i, dry_run=args.dry_run)
    log(f"All iterations {args.start} through {args.target} completed successfully!")


if __name__ == "__main__":
    main()
