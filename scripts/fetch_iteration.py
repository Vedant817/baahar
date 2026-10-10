#!/usr/bin/env python3
"""Reliable candidate fetcher and reporter for autonomous loop.

Polls Modal function calls, saves metrics and generation artifacts,
and generates the decision report without PowerShell escaping issues.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

try:
    import modal
except ImportError:
    modal = None


def fetch_and_report(manifest_path: Path, max_attempts: int = 18, sleep_sec: int = 30) -> bool:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw = ROOT / "eval" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    run_id = manifest["run_id"]

    print(f"Monitoring manifest {manifest_path.name} (run_id: {run_id})...", flush=True)

    # 1. Wait for candidate function calls to be ready
    completed = {}
    for attempt in range(max_attempts):
        all_ready = True
        for candidate, entry in manifest.get("calls", {}).items():
            if candidate in completed:
                continue
            if entry.get("status") == "COMPLETED" and entry.get("artifact"):
                # Already saved previously
                completed[candidate] = None
                continue
            call_id = entry.get("call_id")
            if not call_id:
                continue
            try:
                fc = modal.FunctionCall.from_id(call_id)
                res = fc.get(timeout=2)
                completed[candidate] = res
                print(f"Candidate {candidate} ({call_id}) is READY!", flush=True)

                # Immediately save candidate artifact
                stem = f"candidate_{run_id}_{candidate}"
                f_json = raw / f"{stem}.json"
                f_jsonl = raw / f"{stem}_generations.jsonl"
                f_json.write_text(json.dumps(res["metrics"], indent=2), encoding="utf-8")
                f_jsonl.write_text(
                    "".join(
                        json.dumps(row, ensure_ascii=False) + "\n" for row in res["generations"]
                    ),
                    encoding="utf-8",
                )
                manifest["calls"][candidate]["status"] = "COMPLETED"
                manifest["calls"][candidate]["artifact"] = f"eval/raw/{stem}.json"
                manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
                print(f"Saved {f_json.name}", flush=True)
            except TimeoutError:
                all_ready = False
            except Exception as e:
                print(f"Candidate {candidate} check error: {e}", flush=True)
                all_ready = False

        if all_ready and len(completed) == len(manifest.get("calls", {})):
            print("All candidates are ready!", flush=True)
            break

        ready_names = list(completed.keys())
        pending_names = [c for c in manifest.get("calls", {}) if c not in completed]
        print(
            f"Attempt {attempt + 1}/{max_attempts} ({(attempt + 1) * sleep_sec}s): ready={ready_names}, pending={pending_names}",
            flush=True,
        )
        time.sleep(sleep_sec)

    if len(completed) < len(manifest.get("calls", {})):
        print("Still waiting for some candidates to finish.", flush=True)
        return False

    manifest["status"] = "COMPLETED"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Updated {manifest_path.name} with COMPLETED statuses.", flush=True)

    # 2. Generate decision report
    print("Generating decision report...", flush=True)
    out_md = (
        raw / f"candidate_decision_{manifest_path.stem.replace('candidate_submission_', '')}.md"
    )
    subprocess.run(
        [
            "uv",
            "run",
            "python",
            "scripts/report_briefing_candidates.py",
            str(manifest_path),
            "--markdown",
            str(out_md),
        ],
        check=True,
        cwd=str(ROOT),
    )
    print(f"Report generated at {out_md.name}!", flush=True)
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--attempts", type=int, default=18)
    parser.add_argument("--sleep", type=int, default=30)
    args = parser.parse_args()

    success = fetch_and_report(args.manifest, max_attempts=args.attempts, sleep_sec=args.sleep)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
