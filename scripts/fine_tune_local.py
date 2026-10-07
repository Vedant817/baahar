#!/usr/bin/env python
"""LoRA fine-tune a small open model on Baahar briefings, locally, on CPU.

Why this exists
---------------
The Tinker prize category needs a Tinker-hosted fine-tune. Tinker's balance was
spent by the two verification runs, and topping it up requires a credit card,
which `AGENTS.md` forbids outright. Rather than publish a blocked item or a
number nobody can reproduce, this runs the same experiment on the same dataset
locally, so the "fine-tune vs baseline" question gets a real answer.

It does **not** claim the Tinker category. Tinker's API is verified reachable and
the run there did happen -- see docs/adr/001-tinker-outcome.md -- but it was run
against a dataset that has since been fixed, so its numbers are superseded and
are not published.

What it measures
----------------
Identical protocol to `fine_tune_tinker.py`, so the two are comparable: mean
token-level cross-entropy on assistant tokens only, reported for the base model
and the fine-tuned model on the same held-out split, plus generated briefings.

Honest limits, recorded in the artifact:

* A 0.5B model is not a substitute for an 8B one. It is here to be trainable on
  a CPU with no card and no credits, not because it is the better model.
* The targets were written by the deterministic local writer, so a low loss
  means the model learned that writer's template. It is a style-transfer result,
  not evidence that the prose is good.
* Single seed, single rank, single learning rate.

Usage
-----
    uv sync --group tinker        # brings transformers/peft
    uv run python scripts/fine_tune_local.py --check
    uv run python scripts/fine_tune_local.py --submit
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

from tokenise_common import as_int_list  # noqa: E402

from baahar.config import DATA_DIR  # noqa: E402

TRAIN_PATH = DATA_DIR / "ft" / "train.jsonl"
VAL_PATH = DATA_DIR / "ft" / "val.jsonl"
RAW = ROOT / "eval" / "raw"

DEFAULT_BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def encode_example(tokenizer, messages: list[dict], max_len: int = 768):
    """Token ids plus a loss mask over the assistant turn.

    Returns `(ids, weights)` where weights is 1 on assistant tokens and 0
    elsewhere, so the model is trained to write the briefing rather than to
    echo the conditions it was handed.
    """
    full = as_int_list(
        tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=False)
    )
    prefix = as_int_list(
        tokenizer.apply_chat_template(messages[:-1], tokenize=True, add_generation_prompt=True)
    )
    if len(full) > max_len:
        return None
    ids = full[:]
    weights = [0.0] * (len(ids) - 1)
    start = min(len(prefix), len(ids) - 1)
    for j in range(start, len(ids) - 1):
        weights[j] = 1.0
    if not any(weights):
        return None
    return ids, weights


def mean_loss(model, batches) -> float:
    """Mean cross-entropy per unmasked token, without touching gradients."""
    import torch

    was_training = model.training
    model.eval()
    total, ntok = 0.0, 0
    with torch.no_grad():
        for ids, weights in batches:
            input_ids = torch.tensor([ids[:-1]], dtype=torch.long)
            target = torch.tensor([ids[1:]], dtype=torch.long)
            w = torch.tensor([weights], dtype=torch.float32)
            logits = model(input_ids=input_ids).logits
            loss = torch.nn.functional.cross_entropy(
                logits.reshape(-1, logits.size(-1)),
                target.reshape(-1),
                reduction="none",
            )
            total += float((loss * w.reshape(-1)).sum())
            ntok += int(w.sum())
    if was_training:
        model.train()
    return total / max(1, ntok)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="dataset readiness, downloads nothing")
    ap.add_argument("--submit", action="store_true", help="train; costs no money, only time")
    ap.add_argument("--base-model", default=DEFAULT_BASE_MODEL)
    ap.add_argument("--lora-rank", type=int, default=8)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--learning-rate", type=float, default=2e-4)
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--max-len", type=int, default=768)
    ap.add_argument(
        "--threads",
        type=int,
        default=2,
        help="cap torch CPU threads; the default keeps a laptop usable during a run",
    )
    ap.add_argument(
        "--limit-train",
        type=int,
        default=0,
        help="train on at most N examples (0 = all). Used for a smoke-scale run.",
    )
    ap.add_argument(
        "--limit-eval",
        type=int,
        default=0,
        help="evaluate on at most N examples (0 = all)",
    )
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    train_ex = load_jsonl(TRAIN_PATH)
    val_ex = load_jsonl(VAL_PATH)

    print("Local LoRA fine-tune readiness")
    print(f"  train / val        {len(train_ex)} / {len(val_ex)}")
    print(f"  base model         {args.base_model}")
    print("  credits spent      none (runs on this CPU)")
    print("  model download     ~1 GB, cached in the HF hub directory, not in the repo")

    if not train_ex or not val_ex:
        print("\nrun `uv run python scripts/build_ft_dataset.py` first", file=sys.stderr)
        return 1

    if args.check:
        print("\n--check downloaded nothing and trained nothing.")
        return 0

    if not args.submit:
        ap.print_help()
        return 0

    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    torch.manual_seed(0)
    torch.set_num_threads(max(1, args.threads))
    print(f"  torch threads       {args.threads} (capped so the machine stays usable)")

    t_setup = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    model = AutoModelForCausalLM.from_pretrained(args.base_model, dtype=torch.float32)
    setup_seconds = time.perf_counter() - t_setup

    encoded_train = [
        e for e in (encode_example(tokenizer, x["messages"], args.max_len) for x in train_ex) if e
    ]
    encoded_val = [
        e for e in (encode_example(tokenizer, x["messages"], args.max_len) for x in val_ex) if e
    ]
    scoped = bool(args.limit_train or args.limit_eval)
    if args.limit_train:
        encoded_train = encoded_train[: args.limit_train]
    if args.limit_eval:
        encoded_val = encoded_val[: args.limit_eval]
        val_ex = val_ex[: args.limit_eval]
    print(f"  usable examples    {len(encoded_train)} train / {len(encoded_val)} val")
    if scoped:
        print(
            f"  SCOPE LIMIT        train<={args.limit_train or 'all'} "
            f"eval<={args.limit_eval or 'all'} -- this is a smoke-scale run, not the "
            "full experiment"
        )
    if not encoded_train or not encoded_val:
        raise SystemExit(
            f"refusing to run: {len(encoded_train)}/{len(encoded_val)} usable examples. "
            "Training on zero examples and reporting a loss would be a fabricated result."
        )

    base_train = mean_loss(model, encoded_train)
    base_val = mean_loss(model, encoded_val)
    print(f"\nbaseline  train {base_train:.4f}  val {base_val:.4f}")

    config = LoraConfig(
        r=args.lora_rank,
        lora_alpha=2 * args.lora_rank,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    )
    model = get_peft_model(model, config)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    print(
        f"  LoRA parameters    {trainable:,} of {total_params:,} "
        f"({100 * trainable / total_params:.3f}%)"
    )
    model.train()

    import random

    optim = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad], lr=args.learning_rate
    )

    curve: list[dict] = []
    t_train = time.perf_counter()
    for epoch in range(args.epochs):
        order = list(range(len(encoded_train)))
        random.Random(1234 + epoch).shuffle(order)
        running, ntok = 0.0, 0
        pad_id = tokenizer.pad_token_id
        if pad_id is None:
            pad_id = tokenizer.eos_token_id
        for start in range(0, len(order), args.batch_size):
            idx = order[start : start + args.batch_size]
            batch = [encoded_train[i] for i in idx]

            # Left-pad to a common length. Truncating to the longest example --
            # which is what this did first -- leaves the shorter sequences short
            # and torch refuses the stack outright. Padding goes on the left so
            # the real tokens keep their positions measured from the end.
            maxlen = max(len(ids) - 1 for ids, _ in batch)
            inp_rows, tgt_rows, w_rows, attn_rows = [], [], [], []
            for ids, weights in batch:
                length = len(ids) - 1
                pad = maxlen - length
                inp_rows.append([pad_id] * pad + ids[:-1])
                tgt_rows.append([-100] * pad + ids[1:])
                w_rows.append([0.0] * pad + list(weights))
                attn_rows.append([0] * pad + [1] * length)

            input_ids = torch.tensor(inp_rows, dtype=torch.long)
            target = torch.tensor(tgt_rows, dtype=torch.long)
            weights_t = torch.tensor(w_rows, dtype=torch.float32)
            attn = torch.tensor(attn_rows, dtype=torch.long)
            # Explicit positions, or the left padding shifts every real token's
            # RoPE position and the model trains against shifted text.
            position_ids = (attn.cumsum(dim=1) - 1).clamp(min=0)

            logits = model(
                input_ids=input_ids, attention_mask=attn, position_ids=position_ids
            ).logits
            # logits[i] predicts ids[i + 1], i.e. target[i]. Pairing
            # logits[:, :-1] with target[:, 1:] instead would predict two tokens
            # ahead -- a one-token shift against the eval function, so the
            # training loss and the reported loss would not measure the same thing.
            loss_vec = torch.nn.functional.cross_entropy(
                logits.reshape(-1, logits.size(-1)),
                target.reshape(-1),
                reduction="none",
                ignore_index=-100,
            )
            w = weights_t.reshape(-1)
            loss = (loss_vec * w).sum() / w.sum().clamp(min=1)
            loss.backward()
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
            optim.step()
            optim.zero_grad(set_to_none=True)
            running += float(loss) * int(w.sum())
            ntok += int(w.sum())

        mean_step = running / max(1, ntok)
        val_after = mean_loss(model, encoded_val)
        curve.append(
            {
                "epoch": epoch + 1,
                "mean_train_loss": round(mean_step, 6),
                "val_loss": round(val_after, 6),
            }
        )
        print(f"  epoch {epoch + 1}: train {mean_step:.4f}  val {val_after:.4f}", flush=True)
    train_seconds = time.perf_counter() - t_train

    generated = []
    for ex in val_ex[:3]:
        prompt = as_int_list(
            tokenizer.apply_chat_template(
                ex["messages"][:-1], tokenize=True, add_generation_prompt=True
            )
        )
        ids = torch.tensor([prompt], dtype=torch.long)
        with torch.no_grad():
            out = model.generate(
                input_ids=ids,
                attention_mask=torch.ones_like(ids),
                max_new_tokens=140,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        text = tokenizer.decode(out[0][ids.shape[1] :], skip_special_tokens=True)
        generated.append(
            {
                "decision": ex["meta"]["decision"],
                "reference": ex["messages"][-1]["content"],
                "fine_tuned": text.strip(),
            }
        )
        print(f"  sample ({ex['meta']['decision']}): {text.strip()[:90]}...")

    final_train = mean_loss(model, encoded_train)
    final_val = mean_loss(model, encoded_val)

    payload = {
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "task": "local CPU LoRA fine-tune on Baahar briefings, vs its own base model",
        "why_local": (
            "Tinker's balance was spent by two verification runs and topping it up "
            "requires a credit card, which AGENTS.md forbids. This runs the same "
            "experiment on the same dataset locally so the fine-tune-vs-baseline "
            "question has a real, reproducible answer."
        ),
        "not_a_tinker_run": (
            "This does not claim the Tinker prize category. The Tinker API is verified "
            "reachable and a run there did happen, but against a dataset that has "
            "since been fixed, so those numbers are superseded and unpublished."
        ),
        "base_model": args.base_model,
        "lora_rank": args.lora_rank,
        "lora_target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
        "trainable_parameters": trainable,
        "total_parameters": total_params,
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "batch_size": args.batch_size,
        "n_train": len(encoded_train),
        "n_val": len(encoded_val),
        "scope_limits": {
            "limit_train": args.limit_train or None,
            "limit_eval": args.limit_eval or None,
            "max_len": args.max_len,
            "torch_threads": args.threads,
            "smoke_scale": scoped,
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
            "A 0.5B model is not a substitute for an 8B one. It is used because it "
            "trains on a CPU with no card and no credits.",
            "The targets were written by the deterministic local writer, so a low loss "
            "means the model learned that writer's template. This is style transfer, "
            "not evidence that the prose is good.",
            f"Single seed, single configuration ({args.lora_rank=}, {args.learning_rate=}, "
            f"{args.epochs=}). One point on a hyper-parameter surface, not a tuned result.",
            f"{len(encoded_val)} validation examples is a small held-out set; a "
            "few-hundredths move should not be read as decisive.",
            "The holdout here is the 22 briefing examples, a different and much smaller "
            "set than the 1,626-row tabular holdout.",
            *(
                [
                    "SMOKE-SCALE RUN: this was deliberately limited to "
                    f"{len(encoded_train)} training and {len(encoded_val)} evaluation "
                    "examples so a full CPU run would not make the machine unusable. "
                    "The delta below is a real measurement on that subset, not the "
                    "full-dataset result, and must not be quoted as one. "
                    "scripts/fine_tune_modal.py runs the full experiment on a GPU."
                ]
                if scoped
                else []
            ),
        ],
    }

    RAW.mkdir(parents=True, exist_ok=True)
    if args.out:
        out = Path(args.out)
        if not out.is_absolute():
            out = ROOT / out
    else:
        out = RAW / f"tinker_local_{time.strftime('%Y%m%dT%H%M%S%z')}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nval loss {base_val:.4f} -> {final_val:.4f} ({payload['val_delta']:+.4f})")
    print(f"train loss {base_train:.4f} -> {final_train:.4f} ({payload['train_delta']:+.4f})")
    print(f"train time {train_seconds / 60:.1f} min")
    print(f"artifact -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
