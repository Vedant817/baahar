#!/usr/bin/env python
"""Run the Baahar briefing fine-tune on Modal, on a GPU.

Why this exists
---------------
The first attempt at this experiment ran locally on CPU: over 40 minutes of wall
clock, and the laptop was visibly struggling. Modal runs the same training loop
on a remote GPU. The measurement uses the same definition as
`fine_tune_local.py` -- mean token-level cross-entropy over assistant tokens,
base vs fine-tuned, same held-out split. Different base models across runs
are not directly comparable.

This is not a Tinker run and does not claim the Tinker prize category; see
`docs/adr/001-tinker-outcome.md`.

What it costs
-------------
Modal bills compute and persistent storage against your credit balance. Set
`BAAHAR_MODAL_GPU` to change the card (`L4` is the default after a T4 memory
failure). Runtime and cost must be measured on a real run.

Auth
----
Needs a Modal token, which is per-account:

    uv run --group modal modal token new

or configure private environment variables:

    MODAL_TOKEN_ID=ak-...   MODAL_TOKEN_SECRET=sk-...

Usage
-----
    uv run --group modal python scripts/fine_tune_modal.py --dry-run
    uv run --group modal python scripts/fine_tune_modal.py --detach
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

TRAIN_REMOTE = "/data/train.jsonl"
VAL_REMOTE = "/data/val.jsonl"
COMMON_REMOTE = "/opt/tokenise_common.py"

# Modal requires the decorated function to live in global scope, so the app and
# the function are built here rather than inside a factory. Constructing the
# image does not build it -- that only happens when the function runs -- so
# importing this module, and `--dry-run`, stay free.
import modal  # noqa: E402

if modal.is_local():
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
GPU = os.getenv("BAAHAR_MODAL_GPU") or "L4"
BASE_MODEL = os.getenv("BAAHAR_BASE_MODEL") or "Qwen/Qwen2.5-1.5B-Instruct"
VOLUME_NAME = "baahar-training"
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "torch==2.9.*",
        "transformers>=4.57,<5",
        "peft>=0.17,<0.19",
        "accelerate>=0.34",
        "safetensors",
        "sentencepiece",
    )
    .env(
        {
            "BAAHAR_BASE_MODEL": BASE_MODEL,
            "BAAHAR_MODAL_GPU": GPU,
            "HF_HOME": "/artifacts/hf-cache",
            "HF_HUB_DOWNLOAD_TIMEOUT": "120",
            "HF_HUB_ETAG_TIMEOUT": "30",
        }
    )
    .add_local_file(str(ROOT / "data" / "ft" / "train.jsonl"), TRAIN_REMOTE)
    .add_local_file(str(ROOT / "data" / "ft" / "val.jsonl"), VAL_REMOTE)
    # The shared tokeniser helper has to travel into the container too, or the
    # remote run would silently have no as_int_list and tokenise nothing.
    .add_local_file(str(ROOT / "scripts" / "tokenise_common.py"), COMMON_REMOTE)
)

app = modal.App("baahar-finetune", image=image)


@app.function(gpu=GPU, timeout=60 * 60, retries=0, volumes={"/artifacts": volume})
def train(
    lora_rank: int, epochs: int, learning_rate: float, batch_size: int, max_len: int, run_id: str
):
    # Vendor exceptions such as torch.OutOfMemoryError cannot be unpickled by
    # the lightweight laptop client. Return a built-in exception with the cause.
    try:
        return _train(lora_rank, epochs, learning_rate, batch_size, max_len, run_id)
    except Exception as exc:
        raise RuntimeError(f"Remote training failed: {type(exc).__name__}: {exc}") from None


def _train(lora_rank, epochs, learning_rate, batch_size, max_len, run_id):
    """Fine-tune, persist the adapter and results remotely, and return metrics.

    Only a small metrics JSON is copied back to the caller; weights stay on Modal.
    """
    sys.path.insert(0, "/opt")

    import torch
    from peft import LoraConfig, get_peft_model
    from tokenise_common import as_int_list
    from transformers import AutoModelForCausalLM, AutoTokenizer

    def load(path):
        with open(path, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh.read().splitlines() if line.strip()]

    def encode(tokenizer, messages):
        full = as_int_list(
            tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=False)
        )
        prefix = as_int_list(
            tokenizer.apply_chat_template(messages[:-1], tokenize=True, add_generation_prompt=True)
        )
        if len(full) > max_len or len(prefix) >= len(full):
            return None
        weights = [0.0] * (len(full) - 1)
        for j in range(len(prefix) - 1, len(full) - 1):
            weights[j] = 1.0
        if not any(weights):
            return None
        return full, weights

    def mean_loss(model, encoded):
        model.eval()
        total, ntok = 0.0, 0
        with torch.no_grad():
            for ids, weights in encoded:
                inp = torch.tensor([ids[:-1]], device=model.device)
                tgt = torch.tensor([ids[1:]], device=model.device)
                w = torch.tensor([weights], device=model.device, dtype=torch.float32)
                logits = model(input_ids=inp).logits
                vec = torch.nn.functional.cross_entropy(
                    logits.reshape(-1, logits.size(-1)), tgt.reshape(-1), reduction="none"
                )
                total += float((vec * w.reshape(-1)).sum())
                ntok += int(w.sum())
                del logits, vec
        model.train()
        return total / max(1, ntok)

    t_setup = time.perf_counter()
    if not torch.cuda.is_available():
        raise RuntimeError("Modal did not provide a CUDA GPU; refusing CPU training")
    device = "cuda"
    print(f"GPU: {torch.cuda.get_device_name(0)}; loading {BASE_MODEL}", flush=True)
    torch.manual_seed(0)
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL, dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float32
    ).to(device)
    setup_seconds = time.perf_counter() - t_setup
    print(f"Model loaded in {setup_seconds:.1f}s", flush=True)

    train_ex, val_ex = load(TRAIN_REMOTE), load(VAL_REMOTE)
    enc_train = [e for e in (encode(tokenizer, x["messages"]) for x in train_ex) if e]
    enc_val = [e for e in (encode(tokenizer, x["messages"]) for x in val_ex) if e]
    if not enc_train or not enc_val:
        raise ValueError(
            f"refusing to run: {len(enc_train)}/{len(enc_val)} usable examples. "
            "Training on zero examples and reporting a loss would be fabricated."
        )

    print(f"Usable examples: train={len(enc_train)}, validation={len(enc_val)}", flush=True)
    base_train = mean_loss(model, enc_train)
    base_val = mean_loss(model, enc_val)
    print(f"Baseline: train={base_train:.6f}, val={base_val:.6f}", flush=True)

    model = get_peft_model(
        model,
        LoraConfig(
            r=lora_rank,
            lora_alpha=2 * lora_rank,
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        ),
    )
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    model.train()

    import random

    optim = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=learning_rate)
    pad_id = tokenizer.pad_token_id or tokenizer.eos_token_id

    curve = []
    t_train = time.perf_counter()
    for epoch in range(epochs):
        order = list(range(len(enc_train)))
        random.Random(1234 + epoch).shuffle(order)
        running, ntok = 0.0, 0
        for start in range(0, len(order), batch_size):
            batch = [enc_train[i] for i in order[start : start + batch_size]]
            maxlen = max(len(ids) - 1 for ids, _ in batch)
            inp_rows, tgt_rows, w_rows, attn_rows = [], [], [], []
            for ids, weights in batch:
                length = len(ids) - 1
                pad = maxlen - length
                inp_rows.append([pad_id] * pad + ids[:-1])
                tgt_rows.append([-100] * pad + ids[1:])
                w_rows.append([0.0] * pad + list(weights))
                attn_rows.append([0] * pad + [1] * length)
            inp = torch.tensor(inp_rows, device=device)
            tgt = torch.tensor(tgt_rows, device=device)
            wt = torch.tensor(w_rows, device=device, dtype=torch.float32)
            attn = torch.tensor(attn_rows, device=device)
            pos = (attn.cumsum(dim=1) - 1).clamp(min=0)
            logits = model(input_ids=inp, attention_mask=attn, position_ids=pos).logits
            vec = torch.nn.functional.cross_entropy(
                logits.reshape(-1, logits.size(-1)),
                tgt.reshape(-1),
                reduction="none",
                ignore_index=-100,
            )
            w = wt.reshape(-1)
            loss = (vec * w).sum() / w.sum().clamp(min=1)
            loss.backward()
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
            optim.step()
            optim.zero_grad(set_to_none=True)
            running += float(loss.detach()) * int(w.sum())
            ntok += int(w.sum())
            del logits, vec, loss
        mean_step = running / max(1, ntok)
        val_after = mean_loss(model, enc_val)
        curve.append(
            {
                "epoch": epoch + 1,
                "mean_train_loss": round(mean_step, 6),
                "val_loss": round(val_after, 6),
            }
        )
        print(f"Epoch {epoch + 1}/{epochs}: train={mean_step:.6f}, val={val_after:.6f}", flush=True)
    train_seconds = time.perf_counter() - t_train

    generated = []
    for ex in val_ex[:3]:
        prompt = as_int_list(
            tokenizer.apply_chat_template(
                ex["messages"][:-1], tokenize=True, add_generation_prompt=True
            )
        )
        ids = torch.tensor([prompt], device=device)
        with torch.no_grad():
            out = model.generate(
                input_ids=ids,
                attention_mask=torch.ones_like(ids),
                max_new_tokens=140,
                do_sample=False,
                pad_token_id=pad_id,
            )
        generated.append(
            {
                "decision": ex["meta"]["decision"],
                "reference": ex["messages"][-1]["content"],
                "fine_tuned": tokenizer.decode(
                    out[0][ids.shape[1] :], skip_special_tokens=True
                ).strip(),
            }
        )

    final_train = mean_loss(model, enc_train)
    final_val = mean_loss(model, enc_val)

    run_dir = Path("/artifacts/runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    model.save_pretrained(run_dir / "adapter")
    tokenizer.save_pretrained(run_dir / "adapter")

    payload = {
        "run_id": run_id,
        "volume": VOLUME_NAME,
        "adapter_path": f"runs/{run_id}/adapter",
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "task": "LoRA fine-tune of an open model on Baahar briefings, on a Modal GPU",
        "why_modal": (
            "The CPU run took over 40 minutes of wall clock and was making the laptop "
            "unusable. Modal runs the training loop on a remote GPU. "
            "Same measurement as fine_tune_local.py."
        ),
        "not_a_tinker_run": (
            "This does not claim the Tinker prize category. Tinker's API is verified "
            "reachable but its balance is exhausted and recharging requires a card. "
            "See docs/adr/001-tinker-outcome.md."
        ),
        "provider": "Modal",
        "gpu": GPU,
        "device": device,
        "base_model": BASE_MODEL,
        "lora_rank": lora_rank,
        "lora_target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
        "trainable_parameters": trainable,
        "total_parameters": total_params,
        "epochs": epochs,
        "learning_rate": learning_rate,
        "batch_size": batch_size,
        "n_train": len(enc_train),
        "n_val": len(enc_val),
        "discarded_train": len(train_ex) - len(enc_train),
        "discarded_val": len(val_ex) - len(enc_val),
        "dataset_sha256": {
            "train": hashlib.sha256(Path(TRAIN_REMOTE).read_bytes()).hexdigest(),
            "val": hashlib.sha256(Path(VAL_REMOTE).read_bytes()).hexdigest(),
        },
        "loss": "mean token-level cross-entropy, assistant tokens only",
        "baseline": {"train": round(base_train, 6), "val": round(base_val, 6)},
        "fine_tuned": {"train": round(final_train, 6), "val": round(final_val, 6)},
        "curve": curve,
        "val_delta": round(final_val - base_val, 6),
        "train_delta": round(final_train - base_train, 6),
        "generated": generated,
        "setup_seconds": round(setup_seconds, 1),
        "train_seconds": round(train_seconds, 1),
        "caveats": [
            "The targets were written by the deterministic local writer, so a low loss "
            "means the model learned that writer's template. This is style transfer, "
            "not evidence that the prose is good; the briefing rubric in "
            "eval/RESULTS.md remains the only measurement of readability.",
            f"Single seed, single configuration ({lora_rank=}, {learning_rate=}, "
            f"{epochs=}). One point on a hyper-parameter surface, not a tuned result.",
            f"{len(enc_val)} validation examples is a small held-out set; a "
            "few-hundredths move should not be read as decisive.",
            f"This held-out set is {len(enc_val)} briefing examples, not the tabular "
            "holdout. The two are not comparable.",
        ],
    }
    (run_dir / "results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    volume.commit()
    print(f"Adapter and results committed: {run_dir}", flush=True)
    return payload


def main(argv: list[str] | None = None) -> int:
    # Modal's progress output contains Unicode checkmarks; Windows pipes may
    # otherwise use cp1252 and fail before submitting a function.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lora-rank", type=int, default=16)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--learning-rate", type=float, default=2e-4)
    ap.add_argument("--batch-size", type=int, default=2)
    ap.add_argument("--max-len", type=int, default=768)
    ap.add_argument("--dry-run", action="store_true", help="print the plan and exit")
    ap.add_argument("--detach", action="store_true", help="submit and exit; training stays remote")
    ap.add_argument("--fetch-call", help="retrieve a completed detached call's results")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    if min(args.lora_rank, args.epochs, args.batch_size, args.max_len) <= 0:
        ap.error("rank, epochs, batch size and max length must be positive")
    if not 0 < args.learning_rate < 1:
        ap.error("learning rate must be between 0 and 1")

    print(f"Modal fine-tune plan  gpu={GPU}  base={BASE_MODEL}")
    print(
        f"  epochs={args.epochs} rank={args.lora_rank} lr={args.learning_rate} "
        f"batch={args.batch_size}"
    )
    counts = [
        sum(
            bool(line.strip())
            for line in (ROOT / "data" / "ft" / name).read_text(encoding="utf-8").splitlines()
        )
        for name in ("train.jsonl", "val.jsonl")
    ]
    print(f"  dataset: {counts[0]} train / {counts[1]} val (uploaded into the image)")
    print("  billed: remote compute and storage; no local model download")
    if args.dry_run:
        return 0

    from modal.config import config

    if not (config.get("token_id") and config.get("token_secret")):
        print(
            "\nNo Modal credentials. Authenticate once with:\n"
            "    uv run --group modal modal token new\n"
            "or set MODAL_TOKEN_ID and MODAL_TOKEN_SECRET privately in .env.",
            file=sys.stderr,
        )
        return 2

    if args.fetch_call:
        try:
            payload = modal.FunctionCall.from_id(args.fetch_call).get(timeout=5)
        except TimeoutError:
            print("Training is still running; check the Modal dashboard and fetch later.")
            return 3
    else:
        run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:8]
        kwargs = {
            "lora_rank": args.lora_rank,
            "epochs": args.epochs,
            "learning_rate": args.learning_rate,
            "batch_size": args.batch_size,
            "max_len": args.max_len,
            "run_id": run_id,
        }
        with modal.enable_output(), app.run(detach=args.detach):
            if args.detach:
                call = train.spawn(**kwargs)
                manifest = ROOT / "eval" / "raw" / f"modal_submission_{run_id}.json"
                manifest.parent.mkdir(parents=True, exist_ok=True)
                manifest.write_text(
                    json.dumps(
                        {
                            "status": "SUBMITTED",
                            "run_id": run_id,
                            "call_id": call.object_id,
                            "parameters": kwargs,
                            "volume": VOLUME_NAME,
                            "gpu": GPU,
                            "base_model": BASE_MODEL,
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                print(f"Submitted; training continues on Modal. Manifest: {manifest}")
                print(
                    f"Fetch: uv run --group modal python scripts/fine_tune_modal.py --fetch-call {call.object_id}"
                )
                return 0
            payload = train.remote(**kwargs)

    raw = ROOT / "eval" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else raw / f"modal_{payload['run_id']}.json"
    if not out.is_absolute():
        out = ROOT / out
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"\nbase       {payload['baseline']}")
    print(f"fine-tuned {payload['fine_tuned']}")
    print(f"val delta {payload['val_delta']:+.4f}   train delta {payload['train_delta']:+.4f}")
    for g in payload["generated"]:
        print(f"  [{g['decision']}] {g['fine_tuned'][:100]}")
    print(f"artifact -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
