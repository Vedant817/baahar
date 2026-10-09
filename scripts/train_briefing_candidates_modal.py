#!/usr/bin/env python
"""Train two pinned briefing adapters remotely; keep weights off the laptop.

Dry-run validates data offline. Submission requires explicit --submit --detach.
Fetch uses the durable manifest and waits at most five seconds per call.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "ft_v2"
SPLITS = ("train", "val", "test", "stress")
CANDIDATES = {
    "qwen3_4b": {
        "model": "Qwen/Qwen3-4B-Instruct-2507",
        "revision": "cdbee75f17c01a7cc42f958dc650907174af0554",
    },
    "qwen25_7b": {
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "revision": "a09a35458c702b33eeacc393d103063234e8bc28",
    },
}
PARAMETERS = {
    "max_len": 1024,
    "microbatch": 1,
    "gradient_accumulation": 16,
    "epochs": 3,
    "learning_rate": 5e-5,
    "rank": 16,
    "alpha": 32,
    "dropout": 0.05,
    "warmup_fraction": 0.05,
    "seed": 0,
    "max_new_tokens": 160,
    "early_stopping_patience": 1,
}
VOLUME_NAME = "baahar-training"
TIMEOUT_SECONDS = 7200
# Estimate, not an invoice. CPU cores and requested RAM are included.
MAX_PAIR_COMPUTE_USD = 2 * TIMEOUT_SECONDS * (0.000542 + 2 * 0.0000131 + 32 * 0.00000222)


def read_cases(path: Path) -> list[dict]:
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if not rows:
        raise ValueError(f"Empty dataset: {path.name}")
    return rows


def preflight(directory: Path) -> dict:
    """Fail closed before compute if dates, IDs or prompts leak across splits."""
    datasets = {split: read_cases(directory / f"{split}.jsonl") for split in SPLITS}
    all_ids: set[str] = set()
    prompts: dict[str, str] = {}
    days: dict[str, set[str]] = {}
    for split, rows in datasets.items():
        days[split] = set()
        for row in rows:
            case_id = row["id"]
            if case_id in all_ids:
                raise ValueError(f"Duplicate case ID: {case_id}")
            all_ids.add(case_id)
            messages = row["messages"]
            if [m["role"] for m in messages] != ["system", "user", "assistant"]:
                raise ValueError(f"Invalid messages: {case_id}")
            if not row["facts"] or any(not m["content"].strip() for m in messages):
                raise ValueError(f"Missing facts or content: {case_id}")
            meta = row["meta"]
            if meta["split"] != split:
                raise ValueError(f"Wrong split: {case_id}")
            kind = meta["source_kind"]
            if kind not in {"recorded_archive", "synthetic_stress"}:
                raise ValueError(f"Unknown provenance: {case_id}")
            if kind == "recorded_archive":
                day = meta["source_time"][:10]
                if len(day) != 10:
                    raise ValueError(f"Missing recorded date: {case_id}")
                days[split].add(day)
            prompt = json.dumps(messages[:-1], sort_keys=True, ensure_ascii=False)
            if prompt in prompts and prompts[prompt] != split:
                raise ValueError(f"Identical prompt across splits: {case_id}")
            prompts[prompt] = split
    for left, right in (("train", "val"), ("val", "test"), ("train", "test")):
        if days[left] & days[right]:
            raise ValueError(f"Source days overlap: {left}/{right}")
        if days[left] and days[right] and max(days[left]) >= min(days[right]):
            raise ValueError(f"Nonchronological partitions: {left}/{right}")
    result = {
        "counts": {s: len(rows) for s, rows in datasets.items()},
        "sha256": {
            s: hashlib.sha256((directory / f"{s}.jsonl").read_bytes()).hexdigest() for s in SPLITS
        },
        "contract_sha256": hashlib.sha256(
            (ROOT / "src" / "baahar" / "briefing_contract.py").read_bytes()
        ).hexdigest(),
        "recorded_day_ranges": {
            s: [min(values), max(values)] if values else [] for s, values in days.items()
        },
        "source_kind_counts": {
            s: {
                kind: sum(r["meta"]["source_kind"] == kind for r in rows)
                for kind in ("recorded_archive", "synthetic_stress")
            }
            for s, rows in datasets.items()
        },
    }
    development = directory / "development.jsonl"
    if development.exists():
        rows = read_cases(development)
        for row in rows:
            if row["id"] in all_ids:
                raise ValueError(f"Development ID overlap: {row['id']}")
            all_ids.add(row["id"])
            prompt = json.dumps(row["messages"][:-1], sort_keys=True, ensure_ascii=False)
            if prompt in prompts:
                raise ValueError(f"Development prompt overlap: {row['id']}")
            prompts[prompt] = "development"
        result["development"] = {
            "count": len(rows),
            "sha256": hashlib.sha256(development.read_bytes()).hexdigest(),
            "independent_holdout": False,
        }
    return result


def encode_case(tokenizer, case: dict, max_len: int):
    full = list(
        tokenizer.apply_chat_template(case["messages"], tokenize=True, add_generation_prompt=False)
    )
    prefix = list(
        tokenizer.apply_chat_template(
            case["messages"][:-1], tokenize=True, add_generation_prompt=True
        )
    )
    if full[: len(prefix)] != prefix or len(prefix) >= len(full):
        raise ValueError(f"Chat response mask is not a token prefix: {case['id']}")
    if len(full) > max_len:
        return None
    return full, [-100] * len(prefix) + full[len(prefix) :]


def summarize(rows: list[dict]) -> dict:
    if not rows:
        raise ValueError("Cannot summarize zero generation cases")
    latencies = sorted(row["seconds"] for row in rows)
    count = len(rows)
    defect_codes = sorted({code for row in rows for code in row["raw_check"].get("errors", [])})
    return {
        "n": count,
        "raw_accepted_count": sum(bool(r["raw_check"]["accepted"]) for r in rows),
        "raw_safety_error_count": sum(bool(r["raw_check"]["safety_errors"]) for r in rows),
        "raw_harmful_encouragement_count": sum(
            "unsafe_invitation" in r["raw_check"].get("errors", []) for r in rows
        ),
        "raw_defect_counts": {
            code: sum(code in row["raw_check"]["errors"] for row in rows) for code in defect_codes
        },
        "guarded_accepted_count": sum(bool(r["guarded_check"]["accepted"]) for r in rows),
        "guarded_safety_error_count": sum(bool(r["guarded_check"]["safety_errors"]) for r in rows),
        "fallback_count": sum(r["fallback_used"] for r in rows),
        "rejection_rate": sum(r["fallback_used"] for r in rows) / count,
        "latency_median_seconds": (latencies[(count - 1) // 2] + latencies[count // 2]) / 2,
        "latency_p95_seconds": latencies[math.ceil(count * 0.95) - 1],
    }


def _train(candidate: str, run_id: str, expected_data: dict, parameters: dict):
    """Executed inside Modal only; heavy imports never run on the client."""
    import importlib.metadata
    import random

    import torch
    from peft import (
        LoraConfig,
        get_peft_model,
        get_peft_model_state_dict,
        set_peft_model_state_dict,
    )
    from transformers import AutoModelForCausalLM, AutoTokenizer

    sys.path.insert(0, "/opt")
    from briefing_contract import deterministic_fallback, evaluate

    begin = time.perf_counter()
    datasets = {s: read_cases(Path("/data") / f"{s}.jsonl") for s in SPLITS}
    actual_hashes = {
        s: hashlib.sha256((Path("/data") / f"{s}.jsonl").read_bytes()).hexdigest() for s in SPLITS
    }
    if actual_hashes != expected_data["sha256"]:
        raise ValueError("Uploaded dataset differs from preflight hashes")
    evaluation_splits = ("val", "test", "stress")
    if "development" in expected_data:
        path = Path("/data/development.jsonl")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_data["development"]["sha256"]:
            raise ValueError("Uploaded development corpus differs from preflight hash")
        datasets["development"] = read_cases(path)
        evaluation_splits += ("development",)
    actual_contract_hash = hashlib.sha256(
        Path("/opt/briefing_contract.py").read_bytes()
    ).hexdigest()
    if actual_contract_hash != expected_data["contract_sha256"]:
        raise ValueError("Uploaded contract differs from preflight hash")
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("BF16 CUDA GPU required; refusing CPU/FP32 fallback")
    torch.manual_seed(parameters["seed"])
    random.seed(parameters["seed"])
    config = CANDIDATES[candidate]
    tokenizer = AutoTokenizer.from_pretrained(config["model"], revision=config["revision"])
    model = AutoModelForCausalLM.from_pretrained(
        config["model"],
        revision=config["revision"],
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    ).to("cuda")
    model.config.use_cache = False
    encoded, excluded = {}, {}
    for split in ("train", "val"):
        encoded[split], excluded[split] = [], []
        for case in datasets[split]:
            entry = encode_case(tokenizer, case, parameters["max_len"])
            if entry is None:
                excluded[split].append(case["id"])
            else:
                encoded[split].append(entry)
        if not encoded[split]:
            raise ValueError(f"No usable {split} cases")

    def tensors(entry):
        ids, labels = entry
        return (torch.tensor([ids], device="cuda"), torch.tensor([labels], device="cuda"))

    def val_loss():
        model.eval()
        total, tokens = 0.0, 0
        with torch.no_grad():
            for entry in encoded["val"]:
                ids, labels = tensors(entry)
                n = int((labels[:, 1:] != -100).sum())
                result = model(input_ids=ids, labels=labels)
                total += float(result.loss) * n
                tokens += n
                del result
        return total / tokens

    def generate(phase):
        model.eval()
        rows = []
        with torch.no_grad():
            for split in evaluation_splits:
                for case in datasets[split]:
                    inputs = tokenizer.apply_chat_template(
                        case["messages"][:-1],
                        tokenize=True,
                        add_generation_prompt=True,
                        return_tensors="pt",
                    ).to("cuda")
                    if inputs.shape[1] > parameters["max_len"]:
                        raise ValueError(f"Evaluation prompt overflow: {case['id']}")
                    torch.cuda.synchronize()
                    started = time.perf_counter()
                    result = model.generate(
                        inputs,
                        attention_mask=torch.ones_like(inputs),
                        do_sample=False,
                        max_new_tokens=parameters["max_new_tokens"],
                        use_cache=True,
                        pad_token_id=tokenizer.eos_token_id,
                    )
                    torch.cuda.synchronize()
                    seconds = time.perf_counter() - started
                    text = tokenizer.decode(
                        result[0, inputs.shape[1] :], skip_special_tokens=True
                    ).strip()
                    output_ids = result[0, inputs.shape[1] :].tolist()
                    terminated = bool(output_ids and output_ids[-1] == tokenizer.eos_token_id)
                    raw_check = evaluate(text, case)
                    fallback = not raw_check["accepted"]
                    guarded = deterministic_fallback(case) if fallback else text
                    rows.append(
                        {
                            "case_id": case["id"],
                            "split": split,
                            "phase": phase,
                            "source_kind": case["meta"]["source_kind"],
                            "facts": case["facts"],
                            "meta": case["meta"],
                            "raw": text,
                            "raw_check": raw_check,
                            "guarded": guarded,
                            "guarded_check": evaluate(guarded, case),
                            "fallback_used": fallback,
                            "seconds": seconds,
                            "output_tokens": len(output_ids),
                            "terminated": terminated,
                            "token_limit_reached": len(output_ids) >= parameters["max_new_tokens"]
                            and not terminated,
                        }
                    )
                    if len(rows) % 25 == 0:
                        print(f"{candidate}: {phase} generation {len(rows)} cases", flush=True)
        return rows

    base_val = val_loss()
    base_rows = generate("base")
    setup_seconds = time.perf_counter() - begin
    model = get_peft_model(
        model,
        LoraConfig(
            r=parameters["rank"],
            lora_alpha=parameters["alpha"],
            lora_dropout=parameters["dropout"],
            target_modules="all-linear",
            bias="none",
            task_type="CAUSAL_LM",
        ),
    )
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    trainable = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(trainable, lr=parameters["learning_rate"])
    accumulation = parameters["gradient_accumulation"]
    steps_per_epoch = math.ceil(len(encoded["train"]) / accumulation)
    total_steps = steps_per_epoch * parameters["epochs"]
    warmup = max(1, math.ceil(total_steps * parameters["warmup_fraction"]))
    best_loss, best_state, best_epoch = float("inf"), None, None
    curve, step, stale = [], 0, 0
    started = time.perf_counter()
    for epoch in range(parameters["epochs"]):
        model.train()
        order = list(range(len(encoded["train"])))
        random.Random(parameters["seed"] + epoch).shuffle(order)
        total, ntokens = 0.0, 0
        for start in range(0, len(order), accumulation):
            group = [encoded["train"][i] for i in order[start : start + accumulation]]
            group_tokens = sum(sum(x != -100 for x in labels[1:]) for _, labels in group)
            optimizer.zero_grad(set_to_none=True)
            for entry in group:
                ids, labels = tensors(entry)
                n = int((labels[:, 1:] != -100).sum())
                result = model(input_ids=ids, labels=labels)
                loss = result.loss
                total += float(loss.detach()) * n
                ntokens += n
                (loss * (n / group_tokens)).backward()
                del result, loss
            step += 1
            scale = (
                step / warmup
                if step <= warmup
                else max(0.0, (total_steps - step) / max(1, total_steps - warmup))
            )
            for parameter_group in optimizer.param_groups:
                parameter_group["lr"] = parameters["learning_rate"] * scale
            torch.nn.utils.clip_grad_norm_(trainable, 1.0)
            optimizer.step()
            if step % 20 == 0:
                print(f"{candidate}: optimizer step {step}/{total_steps}", flush=True)
        current = val_loss()
        curve.append({"epoch": epoch + 1, "train_loss": total / ntokens, "val_loss": current})
        print(f"{candidate}: epoch={epoch + 1} val_loss={current:.6f}", flush=True)
        if current < best_loss:
            best_loss, best_epoch, stale = current, epoch + 1, 0
            best_state = {
                k: v.detach().cpu().clone() for k, v in get_peft_model_state_dict(model).items()
            }
        else:
            stale += 1
            if stale >= parameters["early_stopping_patience"]:
                break
    train_seconds = time.perf_counter() - started
    set_peft_model_state_dict(model, best_state)
    adapted_rows = generate("adapted")
    rows = base_rows + adapted_rows
    run_dir = Path("/artifacts/candidates") / run_id / candidate
    run_dir.mkdir(parents=True, exist_ok=False)
    model.save_pretrained(run_dir / "adapter")
    tokenizer.save_pretrained(run_dir / "adapter")
    payload = {
        "status": "COMPLETED",
        "run_id": run_id,
        "candidate": candidate,
        **config,
        "parameters": parameters,
        "dataset": expected_data,
        "excluded_case_ids": excluded,
        "usable_counts": {s: len(v) for s, v in encoded.items()},
        "base_val_loss": base_val,
        "adapted_val_loss": val_loss(),
        "best_epoch": best_epoch,
        "selection": "minimum validation loss only; test untouched",
        "curve": curve,
        "setup_and_baseline_eval_seconds": setup_seconds,
        "train_seconds": train_seconds,
        "total_seconds": time.perf_counter() - begin,
        "hardware": {
            "gpu": torch.cuda.get_device_name(),
            "gpu_total_bytes": torch.cuda.get_device_properties(0).total_memory,
            "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
            "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
        },
        "versions": {
            package: importlib.metadata.version(package)
            for package in ("torch", "transformers", "peft", "accelerate")
        },
        "adapter_path": f"candidates/{run_id}/{candidate}/adapter",
        "trainable_parameters": sum(p.numel() for p in trainable),
        "evaluation": {
            phase: {
                split: summarize([r for r in rows if r["phase"] == phase and r["split"] == split])
                for split in evaluation_splits
            }
            for phase in ("base", "adapted")
        },
        "limitations": [
            "One seed; deterministic targets do not establish prose quality.",
            "Synthetic stress cases are not recorded field observations.",
            "Guarded success includes fallback; inspect raw rejection rate.",
            "Compute estimate is not measured billed cost; no live deployment.",
        ],
    }
    (run_dir / "metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (run_dir / "generations.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    volume.commit()
    return {"metrics": payload, "generations": rows}


def remote_train(candidate: str, run_id: str, expected_data: dict, parameters: dict):
    try:
        return _train(candidate, run_id, expected_data, parameters)
    except Exception as exc:
        raise RuntimeError(f"Remote candidate failed: {type(exc).__name__}: {exc}") from None


try:
    import modal
except ImportError:
    modal = None


def configure_remote(directory: Path):
    """Bind the uploaded corpus explicitly; historical default stays ft_v2."""
    image = (
        modal.Image.debian_slim(python_version="3.12")
        .pip_install(
            "torch==2.9.1",
            "transformers==4.57.6",
            "peft==0.18.1",
            "accelerate==1.15.0",
            "safetensors",
            "sentencepiece",
        )
        .env(
            {
                "HF_HOME": "/artifacts/hf-cache",
                "HF_HUB_DOWNLOAD_TIMEOUT": "120",
                "HF_HUB_ETAG_TIMEOUT": "30",
            }
        )
    )
    if directory.exists():
        image = image.add_local_dir(str(directory), "/data")
    contract = ROOT / "src" / "baahar" / "briefing_contract.py"
    if contract.exists():
        image = image.add_local_file(str(contract), "/opt/briefing_contract.py")
    app = modal.App("baahar-briefing-candidates", image=image)
    train = app.function(
        gpu="L40S",
        timeout=TIMEOUT_SECONDS,
        retries=0,
        cpu=2,
        memory=32768,
        scaledown_window=10,
        max_containers=2,
        volumes={"/artifacts": volume},
    )(remote_train)
    return app, train


if modal is not None:
    volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
    app, train = configure_remote(DATA)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--detach", action="store_true")
    parser.add_argument("--fetch", type=Path, metavar="MANIFEST")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--data-dir", type=Path, default=DATA)
    args = parser.parse_args(argv)
    directory = args.data_dir.resolve()
    if sum((args.dry_run, args.submit, bool(args.fetch))) != 1:
        parser.error("Choose exactly one of --dry-run, --submit, --fetch MANIFEST")
    if args.submit and not args.detach:
        parser.error("Submission requires --detach; laptop must not remain a training client")
    if args.dry_run:
        print(
            json.dumps(
                {
                    "candidates": CANDIDATES,
                    "parameters": PARAMETERS,
                    "dataset": preflight(directory),
                    "max_pair_compute_estimate_usd": MAX_PAIR_COMPUTE_USD,
                },
                indent=2,
            )
        )
        return 0
    if modal is None:
        parser.error("Install lightweight Modal group: uv sync --group dev --group modal")
    from modal.config import config

    if not (config.get("token_id") and config.get("token_secret")):
        print("Authenticate privately using modal token new", file=sys.stderr)
        return 2
    if args.fetch:
        manifest = json.loads(args.fetch.read_text(encoding="utf-8"))
        pending = False
        for candidate, entry in manifest["calls"].items():
            if entry.get("status") == "COMPLETED":
                continue
            if not entry.get("call_id"):
                print(f"{candidate}: not submitted; inspect manifest")
                pending = True
                continue
            try:
                result = modal.FunctionCall.from_id(entry["call_id"]).get(timeout=5)
            except TimeoutError:
                print(f"{candidate}: still running")
                pending = True
                continue
            except Exception as exc:
                entry.update(status="FAILED", error=f"{type(exc).__name__}: {exc}")
                pending = True
                continue
            raw = ROOT / "eval" / "raw"
            raw.mkdir(parents=True, exist_ok=True)
            stem = f"candidate_{manifest['run_id']}_{candidate}"
            (raw / f"{stem}.json").write_text(
                json.dumps(result["metrics"], indent=2), encoding="utf-8"
            )
            (raw / f"{stem}_generations.jsonl").write_text(
                "".join(
                    json.dumps(row, ensure_ascii=False) + "\n" for row in result["generations"]
                ),
                encoding="utf-8",
            )
            entry.update(status="COMPLETED", artifact=f"eval/raw/{stem}.json")
            print(f"{candidate}: completed; {stem}.json")
        args.fetch.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return 3 if pending else 0
    dataset = preflight(directory)
    if args.manifest and args.manifest.exists():
        # A prepared manifest pins the run_id, candidate set, and parameters
        # (e.g. from the continuous tuning loop). Refuse re-submission.
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        already = manifest.get("status") not in (None, "PREPARED", "PENDING_SUBMISSION") or any(
            entry.get("call_id") for entry in manifest.get("calls", {}).values()
        )
        if already:
            print("Manifest already submitted or completed; refusing to re-submit", file=sys.stderr)
            return 2
        run_id = manifest["run_id"]
        path = args.manifest
        parameters = manifest["parameters"]
        candidates = manifest["candidates"]
        if (
            manifest["dataset"]["sha256"] != dataset["sha256"]
            or (manifest["dataset"]["contract_sha256"] != dataset["contract_sha256"])
            or manifest["dataset"].get("development") != dataset.get("development")
        ):
            raise ValueError("Prepared manifest dataset/contract differs from uploaded files")
        manifest["status"] = "PREPARED"
    else:
        run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:8]
        path = args.manifest or ROOT / "eval" / "raw" / f"candidate_submission_{run_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        parameters = PARAMETERS
        candidates = CANDIDATES
        manifest = {
            "run_id": run_id,
            "status": "PREPARED",
            "candidates": candidates,
            "parameters": parameters,
            "dataset": dataset,
            "volume": VOLUME_NAME,
            "max_pair_compute_estimate_usd": MAX_PAIR_COMPUTE_USD,
            "calls": {name: {"status": "NOT_SUBMITTED"} for name in candidates},
        }
        # Exclusive creation before the first remote action prevents accidental retries.
        with path.open("x", encoding="utf-8") as stream:
            json.dump(manifest, stream, indent=2)
    submission_app, submission_train = (
        configure_remote(directory) if directory != DATA.resolve() else (app, train)
    )
    manifest["dataset_directory"] = str(directory.relative_to(ROOT))
    manifest["max_compute_estimate_usd"] = MAX_PAIR_COMPUTE_USD * len(candidates) / 2
    manifest["max_pair_compute_estimate_usd"] = MAX_PAIR_COMPUTE_USD * len(candidates) / 2
    with modal.enable_output(), submission_app.run(detach=True):
        manifest["app_id"] = submission_app.app_id
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        for candidate in candidates:
            call = submission_train.spawn(candidate, run_id, dataset, parameters)
            manifest["calls"][candidate] = {"call_id": call.object_id, "status": "SUBMITTED"}
            path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["status"] = "SUBMITTED"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Submitted {len(candidates)} remote candidate(s). Manifest: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
