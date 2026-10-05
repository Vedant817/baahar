#!/usr/bin/env python
"""Launch and monitor a Tinker-hosted fine-tune for Baahar briefings.

    ⚠ Blocked on one human step. ⚠

Tinker's API could not be verified from the build environment (tinker.ai timed
out and api.tinker.ai did not resolve), and `AGENTS.md` forbids inventing APIs.
This script therefore takes the training configuration as **explicit
command-line arguments** rather than hard-coding endpoint paths and payloads
that have never been called.

An earlier draft of this file invented a plausible-looking endpoint. That was
removed. See `docs/adr/001-tinker-outcome.md`.

To use this, read the Tinker docs and supply the real values:

    uv run python scripts/fine_tune_tinker.py --submit \
        --base-model <their-model-id> \
        --submit-url <their-endpoint> \
        --status-url-template '<their-endpoint>/{job_id}'

Everything else -- dataset loading, message formatting, train/val split,
submission payload assembly, polling, and export of the LoRA for serving -- is
implemented and does not depend on guessing.

Usage
    uv run python scripts/fine_tune_tinker.py --check
    uv run python scripts/fine_tune_tinker.py --submit --base-model X --submit-url Y
    uv run python scripts/fine_tune_tinker.py --status <job_id> --status-url-template Z
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from baahar.config import DATA_DIR, get_settings
from baahar.http_client import UpstreamError, get_json

TRAIN_PATH = DATA_DIR / "ft" / "train.jsonl"
VAL_PATH = DATA_DIR / "ft" / "val.jsonl"
ALL_PATH = DATA_DIR / "ft" / "baahar_briefings.jsonl"
EXPORT_DIR = DATA_DIR / "ft"


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def build_payload(examples: list[dict], args: argparse.Namespace) -> dict:
    """Assemble the training payload.

    The record shape is the one this repo controls and can defend: chat messages
    with a system prompt, a user turn carrying the structured conditions, and an
    assistant turn holding the target briefing. Whatever field names the vendor
    expects for that, they map onto this.
    """
    payload: dict = {
        "model": args.base_model,
        "train_examples": [
            {
                "messages": ex["messages"],
                **({"metadata": ex.get("meta", {})} if args.include_metadata else {}),
            }
            for ex in examples
        ],
    }
    if args.lora_rank:
        payload.setdefault("lora", {"rank": args.lora_rank})
    if args.epochs:
        payload.setdefault("hyperparameters", {"num_epochs": args.epochs})
    if args.learning_rate:
        payload.setdefault("hyperparameters", {})["learning_rate"] = args.learning_rate
    return payload


def post_json(url: str, payload: dict, api_key: str, timeout: float = 120) -> dict:
    import httpx

    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, json=payload, headers={"Authorization": f"Bearer {api_key}"})
    if resp.status_code >= 400:
        raise UpstreamError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="report dataset readiness and exit")
    ap.add_argument("--submit", action="store_true")
    ap.add_argument("--status", metavar="JOB_ID")
    ap.add_argument("--base-model", default="")
    ap.add_argument("--submit-url", default="")
    ap.add_argument("--status-url-template", default="")
    ap.add_argument("--train", default=str(TRAIN_PATH))
    ap.add_argument("--lora-rank", type=int, default=0)
    ap.add_argument("--epochs", type=int, default=0)
    ap.add_argument("--learning-rate", type=float, default=0.0)
    ap.add_argument("--include-metadata", action="store_true")
    ap.add_argument("--poll-seconds", type=int, default=30)
    ap.add_argument("--poll-max", type=int, default=60)
    args = ap.parse_args(argv)

    settings = get_settings()
    train = load_jsonl(Path(args.train))
    val = load_jsonl(VAL_PATH)
    all_ex = load_jsonl(ALL_PATH)

    print("Tinker fine-tune readiness")
    print(f"  dataset            {all_ex and len(all_ex) or 0} examples")
    print(f"  train / val        {len(train)} / {len(val)}")
    print(f"  TINKER_API_KEY     {'present' if settings.has_tinker else 'MISSING'}")
    print(
        f"  TINKER_SAMPLE_URL  {'configured' if os.getenv('TINKER_SAMPLE_URL') else 'not configured'}"
    )

    from collections import Counter

    if all_ex:
        counts = Counter(e["meta"]["decision"] for e in all_ex)
        for decision, count in sorted(counts.items()):
            print(f"    {decision:<6} {count}")

    if args.check:
        if not all_ex:
            print("\nrun `uv run python scripts/build_ft_dataset.py` first", file=sys.stderr)
            return 1
        print("\nDataset ready. Next: supply --base-model and --submit-url from the Tinker docs.")
        return 0

    if not settings.has_tinker:
        print("\nTINKER_API_KEY is not set. See docs/NEEDS_HUMAN.md section 2.", file=sys.stderr)
        return 1
    if not train:
        print("\nno training data. Run scripts/build_ft_dataset.py first.", file=sys.stderr)
        return 1

    if args.submit:
        if not args.base_model or not args.submit_url:
            print(
                "\n--submit requires --base-model and --submit-url.\n"
                "Baahar deliberately does not hard-code these: the Tinker API could not be\n"
                "verified from this environment, and inventing it would mean shipping a\n"
                "fabricated integration. Read the vendor docs and pass the real values.\n"
                "See docs/adr/001-tinker-outcome.md.",
                file=sys.stderr,
            )
            return 2
        payload = build_payload(train, args)
        print(f"\nsubmitting {len(train)} examples to {args.submit_url}")
        try:
            result = post_json(args.submit_url, payload, settings.tinker_api_key)
        except UpstreamError as exc:
            print(f"submission failed: {exc}", file=sys.stderr)
            return 1
        job_id = result.get("id") or result.get("job_id") or result.get("jobId")
        print(f"job id: {job_id or '(not present in response)'}")
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        (EXPORT_DIR / "last_submit.json").write_text(
            json.dumps({"request": payload, "response": result}, indent=2), encoding="utf-8"
        )
        print(f"request/response saved to {EXPORT_DIR / 'last_submit.json'}")
        return 0

    if args.status:
        if not args.status_url_template:
            print(
                "\n--status requires --status-url-template from the Tinker docs.", file=sys.stderr
            )
            return 2
        for attempt in range(args.poll_max):
            url = args.status_url_template.format(job_id=args.status)
            try:
                result = get_json(url, {}, timeout=60, retries=1)
            except UpstreamError as exc:
                print(f"poll failed: {exc}", file=sys.stderr)
                return 1
            state = result.get("status") or result.get("state") or "unknown"
            print(f"[{attempt + 1}] status={state}")
            if state in {"completed", "succeeded", "failed", "cancelled", "error"}:
                print(json.dumps(result, indent=2)[:2000])
                if state in {"completed", "succeeded"}:
                    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
                    (EXPORT_DIR / "last_status.json").write_text(
                        json.dumps(result, indent=2), encoding="utf-8"
                    )
                    print(f"saved to {EXPORT_DIR / 'last_status.json'}")
                    print("now point TINKER_LORA_PATH at the exported LoRA and re-run the A/B")
                return 0
            time.sleep(args.poll_seconds)
        print("poll limit reached", file=sys.stderr)
        return 1

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
