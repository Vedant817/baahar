"""Add missing-weather coverage without altering historical ft_v2 files.

All prose is synthetic. Historical cohorts are reused development benchmarks;
the additional development cases are not an independent generalization test.
Run: uv run python scripts/build_ft_v4_dataset.py
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import time
import uuid
from collections import Counter
from pathlib import Path

from baahar.briefing_contract import deterministic_fallback, evaluate, render_messages
from baahar.naqi import band_for_index

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "ft_v2"
DEST = ROOT / "data" / "ft_v4"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def target_for(row, variant=0):
    target = deterministic_fallback(row, variant)
    # Probability is optional in the prose; omit its redundant clause when a
    # combined-hazard warning otherwise exceeds the paragraph length contract.
    if len(target.split()) > 80 and row["facts"].get("precip_prob") is not None:
        target = target.replace(f" The chance of rain is {row['facts']['precip_prob']:g}%.", "")
    check = evaluate(target, row)
    if not check["accepted"]:
        raise ValueError(f"Rejected target {row['id']}: {check['errors']}")
    row["messages"] = render_messages(row["facts"], target)
    return row


def synthetic_case(family, index, split):
    # Development variants use different facts, never copies of train prompts.
    offset = 7 if split == "development" else 0
    naqi = (62, 147, 266, 371)[index % 4] + offset
    temporal = family == "temporal_missing"
    missing_heat = family in ("missing_heat", "missing_both", "temporal_missing")
    missing_rain = family in ("missing_rain", "missing_both")
    heat = None if missing_heat else (24 + index % 5 if index % 4 else 37)
    rain = None if missing_rain else (0.3 + index % 3 if index % 4 else 3.6)
    storm = index % 6 == 0
    night = index % 6 == 1
    air_missing = index % 6 == 2
    reasons = []
    if missing_heat:
        reasons.append("Apparent temperature unavailable")
    if missing_rain:
        reasons.append("Hourly rainfall unavailable")
    if storm:
        reasons.append("Thunderstorm forecast")
    if night:
        reasons.append("Night; park gates may be closed")
    if air_missing:
        reasons.append("Indian NAQI unavailable")
    if not air_missing and naqi >= 301:
        reasons.append(f"Indian NAQI {naqi} is very poor")
    facts = {
        "decision": "SKIP",
        "park": ("Cubbon Park", "Ulsoor Lake", "Bugle Rock Park")[index % 3],
        "naqi": None if air_missing else naqi,
        "band": None if air_missing else band_for_index(naqi).value,
        "apparent_c": heat,
        "precip_mm": rain,
        "precip_prob": 22 + index + offset,
        "is_day": not night,
        "time": f"{20 if night else 9 + index % 5:02d}:{(index * 7 + offset) % 60:02d}",
        "air_available": not air_missing,
        "weather_available": False,
        "weather_code": 95 if storm else 1,
        "reasons": reasons,
        "allowed_park_names": ["Cubbon Park", "Ulsoor Lake", "Bugle Rock Park"],
    }
    if temporal:
        facts.update(
            walk_allowed=False,
            scheduled_time=f"{15 + index % 3:02d}:{(index * 11 + offset) % 60:02d}",
            permission_reason="Current weather is incomplete; refresh before walking.",
        )
        reasons.append(facts["permission_reason"])
    case_id = f"v4-{split}-{family}-{index:02d}"
    return target_for(
        {
            "id": case_id,
            "facts": facts,
            "meta": {
                "case_id": case_id,
                "split": split,
                "source_kind": "synthetic_stress",
                "source_time": None,
                "source_sha256": "not_applicable_synthetic",
                "target_kind": "synthetic_deterministic_prose",
                "family": family,
            },
        },
        index % 3,
    )


def write_rows(path, rows):
    # Pinned to LF for the same reason as build_ft_v2_dataset.py: a CRLF build
    # on Windows would hash differently from the identical build on Linux, and
    # every manifest downstream of these bytes would be platform-specific.
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def main():
    manifest_path = ROOT / "eval" / "raw" / "candidate_submission_v16.json"
    prepared = None
    if manifest_path.exists():
        prepared = json.loads(manifest_path.read_text(encoding="utf-8"))
        if prepared["status"] != "PENDING_SUBMISSION" or any(
            entry.get("call_id") for entry in prepared["calls"].values()
        ):
            raise FileExistsError("v16 exists; do not mutate a submitted corpus")
    original_hashes = {s: digest(SOURCE / f"{s}.jsonl") for s in ("train", "val", "test", "stress")}
    DEST.mkdir(parents=True, exist_ok=True)
    datasets = {}
    for split in original_hashes:
        original = [
            json.loads(line)
            for line in (SOURCE / f"{split}.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        datasets[split] = [target_for(copy.deepcopy(row), i % 3) for i, row in enumerate(original)]
    families = ("missing_heat", "missing_rain", "missing_both", "temporal_missing")
    additions = [synthetic_case(f, i, "train") for f in families for i in range(24)]
    development = [synthetic_case(f, i, "development") for f in families for i in range(8)]
    datasets["train"].extend(additions)
    # Consumed qualification remains a regression test, never training data.
    diagnostic = json.loads(
        (ROOT / "eval/raw/qualification_v15_suite.json").read_text(encoding="utf-8")
    )

    def prompt_key(row):
        return json.dumps(row["messages"][:2], sort_keys=True, ensure_ascii=False)

    diagnostic_prompts = {prompt_key(row) for row in diagnostic}
    train_prompts = {prompt_key(row) for row in datasets["train"]}
    development_prompts = {prompt_key(row) for row in development}
    if diagnostic_prompts & train_prompts or development_prompts & train_prompts:
        raise ValueError("Diagnostic/development prompt overlap with training")
    if len({prompt_key(row) for row in additions}) != 96:
        raise ValueError("Training augmentation duplicates prompts")
    for split, rows in datasets.items():
        write_rows(DEST / f"{split}.jsonl", rows)
    write_rows(DEST / "development.jsonl", development)
    spec = importlib.util.spec_from_file_location(
        "candidate_runner_v4", ROOT / "scripts/train_briefing_candidates_modal.py"
    )
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    dataset = runner.preflight(DEST)
    for split in original_hashes:
        if digest(SOURCE / f"{split}.jsonl") != original_hashes[split]:
            raise ValueError("Historical data unexpectedly changed")
    metadata = {
        "intervention": "missing-weather and normalized temporal coverage only",
        "historical_source_sha256": original_hashes,
        "training_added": 96,
        "training_families": dict(Counter(row["meta"]["family"] for row in additions)),
        "development_count": len(development),
        "development_sha256": digest(DEST / "development.jsonl"),
        "unique_augmented_prompts": 96,
        "consumed_diagnostic_prompt_overlap": 0,
        "train_development_prompt_overlap": 0,
        "all_targets_accepted": True,
        "limitations": [
            "Historical val/test/stress reused for tuning; not independent holdouts.",
            "Development missing-data cases share authored families with training.",
            "Current contract rerenders synthetic targets; scores not directly comparable to old contract.",
            "Qualification v15 consumed; retain as regression only.",
        ],
        "dataset": dataset,
    }
    (DEST / "manifest.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8", newline="\n"
    )
    baseline = json.loads(
        (ROOT / "eval/raw/candidate_submission_v15.json").read_text(encoding="utf-8")
    )
    run_id = (
        prepared["run_id"]
        if prepared
        else time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:8]
    )
    manifest = {
        "run_id": run_id,
        "status": "PENDING_SUBMISSION",
        "candidates": {"qwen3_4b": baseline["candidates"]["qwen3_4b"]},
        "parameters": baseline["parameters"],
        "dataset": dataset,
        "dataset_directory": "data/ft_v4",
        "volume": runner.VOLUME_NAME,
        "max_compute_estimate_usd": runner.MAX_PAIR_COMPUTE_USD / 2,
        "max_pair_compute_estimate_usd": runner.MAX_PAIR_COMPUTE_USD / 2,
        "calls": {"qwen3_4b": {"status": "NOT_SUBMITTED"}},
        "parent_manifest": "eval/raw/candidate_submission_v15.json",
        "intervention": metadata["intervention"],
        "development_suite": "data/ft_v4/development.jsonl",
        "development_sha256": metadata["development_sha256"],
        "limitations": metadata["limitations"],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
