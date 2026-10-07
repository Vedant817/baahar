#!/usr/bin/env python
"""Run the Baahar briefing fine-tune on Modal, on a GPU.

Why this exists
---------------
The first attempt at this experiment ran locally on CPU: over 40 minutes of wall
clock, and the laptop was visibly struggling. Modal runs the same training loop
on a rented GPU in a few minutes. The measurement is identical to
`fine_tune_local.py` -- mean token-level cross-entropy over assistant tokens,
base vs fine-tuned, same held-out split -- so the two are directly comparable.

This is not a Tinker run and does not claim the Tinker prize category; see
`docs/adr/001-tinker-outcome.md`.

What it costs
-------------
Modal bills GPU seconds against your credit balance. The dataset is 220 short
examples and the model is 1.5B, so a full run is a few minutes on one GPU. Set
`BAAHAR_MODAL_GPU` to change the card (`T4` is the cheap default, `A10G` and
`L4` are faster). Nothing else bills.

Auth
----
Needs a Modal token, which is per-account:

    uv run modal token new

then export it:

    MODAL_TOKEN_ID=ak-...   MODAL_TOKEN_SECRET=sk-...

Usage
-----
    uv run python scripts/fine_tune_modal.py --dry-run   # prints the plan, costs nothing
    uv run python scripts/fine_tune_modal.py             # trains, needs auth
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

GPU = os.getenv("BAAHAR_MODAL_GPU", "T4")
BASE_MODEL = os.getenv("BAAHAR_BASE_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
TRAIN_REMOTE = "/data/train.jsonl"
VAL_REMOTE = "/data/val.jsonl"
COMMON_REMOTE = "/opt/tokenise_common.py"

# Modal requires the decorated function to live in global scope, so the app and
# the function are built here rather than inside a factory. Constructing the
# image does not build it -- that only happens when the function runs -- so
# importing this module, and `--dry-run`, stay free.
import modal  # noqa: E402

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "torch==2.9.*",
        "transformers>=4.44",
        "peft>=0.13",
        "accelerate>=0.34",
        "safetensors",
        "sentencepiece",
    )
    .add_local_file(str(ROOT / "data" / "ft" / "train.jsonl"), TRAIN_REMOTE)
    .add_local_file(str(ROOT / "data" / "ft" / "val.jsonl"), VAL_REMOTE)
    # The shared tokeniser helper has to travel into the container too, or the
    # remote run would silently have no as_int_list and tokenise nothing.
    .add_local_file(str(ROOT / "scripts" / "tokenise_common.py"), COMMON_REMOTE)
)

app = modal.App("baahar-finetune", image=image)


@app.function(gpu=GPU, timeout=60 * 60, retries=0)
def train(lora_rank: int, epochs: int, learning_rate: float, batch_size: int, max_len: int):
    """Fine-tune, and return the measurement. Nothing is written to disk here.

    The artifact is written on the caller's machine from the returned dict, so
    eval/raw/ stays under local version control and the remote run cannot quietly
    replace a committed result.
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
        model.train()
        return total / max(1, ntok)

    t_setup = time.perf_counter()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.manual_seed(0)
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL, dtype=torch.bfloat16 if device == "cuda" else torch.float32
    ).to(device)
    setup_seconds = time.perf_counter() - t_setup

    train_ex, val_ex = load(TRAIN_REMOTE), load(VAL_REMOTE)
    enc_train = [e for e in (encode(tokenizer, x["messages"]) for x in train_ex) if e]
    enc_val = [e for e in (encode(tokenizer, x["messages"]) for x in val_ex) if e]
    if not enc_train or not enc_val:
        raise ValueError(
            f"refusing to run: {len(enc_train)}/{len(enc_val)} usable examples. "
            "Training on zero examples and reporting a loss would be fabricated."
        )

    base_train = mean_loss(model, enc_train)
    base_val = mean_loss(model, enc_val)

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
        mean_step = running / max(1, ntok)
        val_after = mean_loss(model, enc_val)
        curve.append(
            {
                "epoch": epoch + 1,
                "mean_train_loss": round(mean_step, 6),
                "val_loss": round(val_after, 6),
            }
        )
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

    return {
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "task": "LoRA fine-tune of an open model on Baahar briefings, on a Modal GPU",
        "why_modal": (
            "The CPU run took over 40 minutes of wall clock and was making the laptop "
            "unusable. Modal runs the identical loop on a rented GPU in a few minutes. "
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
            "This held-out set is 22 briefing examples, not the 1,626-row tabular "
            "holdout. The two are not comparable.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lora-rank", type=int, default=16)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--learning-rate", type=float, default=2e-4)
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--max-len", type=int, default=768)
    ap.add_argument("--dry-run", action="store_true", help="print the plan and exit")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    print(f"Modal fine-tune plan  gpu={GPU}  base={BASE_MODEL}")
    print(
        f"  epochs={args.epochs} rank={args.lora_rank} lr={args.learning_rate} "
        f"batch={args.batch_size}"
    )
    print("  dataset: 198 train / 22 val (from data/ft, uploaded into the image)")
    print("  billed:  GPU seconds on your Modal credit balance")
    if args.dry_run:
        return 0

    if not (os.getenv("MODAL_TOKEN_ID") and os.getenv("MODAL_TOKEN_SECRET")):
        print(
            "\nNo Modal credentials. Authenticate once with:\n"
            "    uv run modal token new\n"
            "then export MODAL_TOKEN_ID and MODAL_TOKEN_SECRET.",
            file=sys.stderr,
        )
        return 2

    payload = train.remote(
        lora_rank=args.lora_rank,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
        max_len=args.max_len,
    )

    raw = ROOT / "eval" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    out = (
        Path(args.out)
        if args.out
        else raw / f"tinker_modal_{time.strftime('%Y%m%dT%H%M%S%z')}.json"
    )
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
