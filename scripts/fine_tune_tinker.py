#!/usr/bin/env python
"""Fine-tune a LoRA on Baahar briefings with Tinker, and measure it honestly.

What changed
------------
An earlier version of this file was written against an invented REST API --
`--submit-url`, `--status-url-template`, a job id polled to completion. Tinker
has no such endpoint. It is a Python SDK: you create a training client, call
`forward_backward`, call `optim_step`, and the heavy work happens on their GPUs
while the loop runs locally.

That earlier file is gone, and with it the reason the project could not claim
the Tinker category. The blocker was never that Tinker was unreachable: the repo
probed `tinker.ai`, which is not the service. The documented host is
`tinker.thinkingmachines.dev`, and its OpenAI-compatible inference endpoint is
`https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1`. See
docs/adr/001-tinker-outcome.md.

What this measures
------------------
A LoRA fine-tune is only interesting if it is compared against the base model on
held-out data. So the run reports, for both the base model and the fine-tuned
model:

* mean token-level cross-entropy on the 21 validation examples (never trained on)
* the same metric on the 198 training examples
* generated briefings for a few validation prompts, so the change is legible

Every figure lands in `eval/raw/tinker_<stamp>.json`. If the fine-tune does not
beat the base model, that is what gets published.

Usage
-----
    uv sync --group tinker
    uv run python scripts/fine_tune_tinker.py --check     # dataset + auth, no credits
    uv run python scripts/fine_tune_tinker.py --submit    # spends credits

`--submit` is the only thing that costs money, and it is opt-in.
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

from baahar.config import DATA_DIR, get_settings  # noqa: E402

TRAIN_PATH = DATA_DIR / "ft" / "train.jsonl"
VAL_PATH = DATA_DIR / "ft" / "val.jsonl"
ALL_PATH = DATA_DIR / "ft" / "baahar_briefings.jsonl"
RAW = ROOT / "eval" / "raw"

#: Documented OpenAI-compatible inference endpoint. Only used for cross-checks;
#: training and sampling go through the SDK.
OPENAI_COMPAT_BASE = "https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1"

DEFAULT_BASE_MODEL = "Qwen/Qwen3-8B"


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _require_sdk():
    try:
        import tinker  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "the tinker SDK is not installed. It is an opt-in group:\n"
            "    uv sync --group tinker\n"
            f"(import failed: {exc})"
        ) from exc


def _as_int_list(out) -> list[int]:
    """Deprecated shim. The implementation lives in scripts/tokenise_common.py.

    It was duplicated here once, which is how the same bug existed in two places
    before anyone noticed. Kept as a name because both fine-tuning scripts
    tokenise and they must not each own a copy.
    """
    from tokenise_common import as_int_list

    return as_int_list(out)


def render(tokenizer, messages: list[dict], *, generation_prompt: bool) -> list[int]:
    """Tokenise a chat conversation.

    Uses the model's own chat template when it has one, so the training text
    matches what inference will render. Falls back to a plain newline join rather
    than inventing a special-token scheme, and says so, because a silent format
    mismatch between train and serve is exactly the bug this repo has been bitten
    by before (RESULTS.md C.14).
    """
    template = getattr(tokenizer, "chat_template", None)
    if template:
        try:
            return _as_int_list(
                tokenizer.apply_chat_template(
                    messages, tokenize=True, add_generation_prompt=generation_prompt
                )
            )
        except Exception:  # noqa: BLE001 - fall through to the plain rendering
            pass
    text = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    if generation_prompt:
        text += "\nassistant:"
    return _as_int_list(tokenizer.encode(text))


def to_datum(types_mod, tokenizer, messages: list[dict]):
    """One Datum, with loss masked to the assistant turn only.

    Tinker's `cross_entropy` requires both `target_tokens` and `weights`.
    `weights` is per-target-token, which is what lets this train on the briefing
    rather than on the conditions prompt too -- otherwise the model spends its
    capacity learning to predict the input it was just given.

    Target index j corresponds to ids[j + 1], so the assistant tokens are those
    with j + 1 >= len(prefix_ids), where prefix_ids is the same conversation
    rendered up to the assistant's turn.
    """
    ids = render(tokenizer, messages, generation_prompt=False)
    prefix_ids = render(tokenizer, messages[:-1], generation_prompt=True)
    if len(ids) < 2 or len(prefix_ids) >= len(ids):
        return None
    weights = [1.0 if (j + 1) >= len(prefix_ids) else 0.0 for j in range(len(ids) - 1)]
    if not any(weights):
        return None
    datum = types_mod.Datum(
        model_input=types_mod.ModelInput.from_ints(ids[:-1]),
        loss_fn_inputs={"target_tokens": ids[1:], "weights": weights},
    )
    # Carried alongside so the summed loss can be divided by the right
    # denominator: the count of unmasked (assistant) target tokens.
    return datum, int(sum(weights))


def _probe_endpoint(api_key: str) -> tuple[bool, str]:
    """Does the documented OpenAI-compatible endpoint answer this key?

    A GET on /models. It allocates nothing and costs nothing; it is the cheapest
    possible proof that the host is right and the key is accepted, which is
    exactly what the project previously got wrong by probing tinker.ai.
    """
    try:
        import httpx

        resp = httpx.get(
            f"{OPENAI_COMPAT_BASE}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=20.0,
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"
    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code}"
    try:
        n = len(resp.json().get("data", []))
    except Exception:  # noqa: BLE001
        n = -1
    return True, f"HTTP 200, {n} checkpoints visible to this key"


def _loss_sum(out) -> float:
    """Pull the summed loss out of a ForwardBackwardOutput, strictly.

    Thin wrapper over scripts/tokenise_common.loss_sum, shared with the local
    fine-tuning script so there is one implementation of "a missing metric must
    raise, not default to 0.0000".
    """
    from tokenise_common import loss_sum

    return loss_sum(out)


def mean_loss(training_client, data: list, batch_size: int) -> float:
    """Mean token-level cross-entropy over `data`, masked to assistant tokens.

    `data` is a list of `(datum, weight_sum)` pairs. Tinker returns the summed
    loss for the batch, so the mean is that sum divided by the number of
    unmasked target tokens -- otherwise the reported figure would silently scale
    with batch size.
    """
    if not data:
        raise ValueError("mean_loss called with no data; refusing to report 0.0000")
    total_loss = 0.0
    total_weight = 0
    for start in range(0, len(data), batch_size):
        batch = data[start : start + batch_size]
        out = training_client.forward_backward(
            data=[d for d, _ in batch], loss_fn="cross_entropy"
        ).result()
        total_loss += _loss_sum(out)
        total_weight += sum(int(w) for _, w in batch)
    return total_loss / max(1, total_weight)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="dataset and auth readiness, no credits")
    ap.add_argument("--submit", action="store_true", help="run the fine-tune; spends credits")
    ap.add_argument("--base-model", default=DEFAULT_BASE_MODEL)
    ap.add_argument("--lora-rank", type=int, default=16)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--learning-rate", type=float, default=1e-4)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--checkpoint-name", default="baahar-brief-v1")
    ap.add_argument("--max-tokens", type=int, default=160)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    train_ex = load_jsonl(TRAIN_PATH)
    val_ex = load_jsonl(VAL_PATH)
    all_ex = load_jsonl(ALL_PATH)

    settings = get_settings()
    print("Tinker fine-tune readiness")
    print(
        f"  dataset            {len(all_ex)} examples ({len(train_ex)} train / {len(val_ex)} val)"
    )
    print(f"  TINKER_API_KEY     {'present' if settings.has_tinker else 'MISSING'}")
    if all_ex:
        from collections import Counter

        counts = Counter(e["meta"]["decision"] for e in all_ex)
        print("  decisions          " + ", ".join(f"{d}={n}" for d, n in sorted(counts.items())))

    if not all_ex:
        print("\nrun `uv run python scripts/build_ft_dataset.py` first", file=sys.stderr)
        return 1
    if not settings.has_tinker:
        print("\nTINKER_API_KEY is not set. See docs/NEEDS_HUMAN.md section 2.", file=sys.stderr)
        return 1

    if args.check:
        # Deliberately stops before the SDK is imported and before any forward
        # pass. `--check` must be free to run: it reports what is on disk and
        # whether the documented endpoint answers, and creates no GPU-side
        # state. The base model's starting loss is measured by `--submit`, which
        # costs credits and says so.
        ok, detail = _probe_endpoint(settings.tinker_api_key)
        print(f"  endpoint           {OPENAI_COMPAT_BASE}")
        print(f"  endpoint reachable {'yes' if ok else 'no'}  ({detail})")
        print("\n--check made no remote training call and spent no credits.")
        return 0

    if not args.submit:
        ap.print_help()
        return 0

    _require_sdk()
    import tinker
    from tinker import types

    os.environ["TINKER_API_KEY"] = settings.tinker_api_key

    t0 = time.perf_counter()
    client = tinker.ServiceClient()
    training_client = client.create_lora_training_client(
        base_model=args.base_model, rank=args.lora_rank
    )
    tokenizer = training_client.get_tokenizer()
    setup_seconds = time.perf_counter() - t0

    train_data = [d for d in (to_datum(types, tokenizer, e["messages"]) for e in train_ex) if d]
    val_data = [d for d in (to_datum(types, tokenizer, e["messages"]) for e in val_ex) if d]
    print(f"  base model         {args.base_model}  rank={args.lora_rank}")
    print(f"  usable examples    {len(train_data)} train / {len(val_data)} val")
    print(f"  tokenizer chat template present: {bool(getattr(tokenizer, 'chat_template', None))}")

    # Refuse to "train" on nothing. The first version of this script tokenised
    # into a BatchEncoding instead of a list, every example failed the length
    # check, and the run completed three epochs of zero batches and wrote an
    # artifact claiming a fine-tune with a loss of 0.0000. A guard is the only
    # thing standing between a tokenizer API change and a fabricated result.
    if not train_data or not val_data:
        raise SystemExit(
            f"refusing to run: {len(train_data)} usable train and {len(val_data)} usable "
            f"validation examples from {len(train_ex)}/{len(val_ex)} records. This is a "
            "tokenisation bug, not an empty dataset, and running anyway would publish "
            "a fine-tune that never happened."
        )

    if args.check:
        # Unreachable: handled above, before the SDK is imported.
        raise AssertionError("check should have returned earlier")

    if not args.submit:
        ap.print_help()
        return 0

    # ---- baseline, before any weight is touched -----------------------------
    base_train = mean_loss(training_client, train_data, args.batch_size)
    base_val = mean_loss(training_client, val_data, args.batch_size)
    print(f"\nbaseline  train {base_train:.4f}  val {base_val:.4f}")

    # ---- train --------------------------------------------------------------
    curve: list[dict] = []
    t_train = time.perf_counter()
    for epoch in range(args.epochs):
        order = list(range(len(train_data)))
        # Deterministic shuffle: seed the RNG from the epoch so a rerun with the
        # same --epochs reproduces the same batches.
        import random

        random.Random(1234 + epoch).shuffle(order)
        epoch_loss, epoch_weight = 0.0, 0
        for start in range(0, len(order), args.batch_size):
            batch = [train_data[i] for i in order[start : start + args.batch_size]]
            fwd = training_client.forward_backward(
                data=[d for d, _ in batch], loss_fn="cross_entropy"
            ).result()
            training_client.optim_step(types.AdamParams(learning_rate=args.learning_rate)).result()
            epoch_loss += _loss_sum(fwd)
            epoch_weight += sum(int(w) for _, w in batch)
        mean_step = epoch_loss / max(1, epoch_weight)
        val_after = mean_loss(training_client, val_data, args.batch_size)
        curve.append(
            {
                "epoch": epoch + 1,
                "mean_train_loss": round(mean_step, 6),
                "val_loss": round(val_after, 6),
            }
        )
        print(f"  epoch {epoch + 1}: train {mean_step:.4f}  val {val_after:.4f}")
    train_seconds = time.perf_counter() - t_train

    # ---- sample, so the change is legible ------------------------------------
    sampler = training_client.save_weights_and_get_sampling_client(name=args.checkpoint_name)
    generated = []
    for ex in val_ex[:3]:
        prompt = ex["messages"][:-1]
        model_input = types.ModelInput.from_ints(render(tokenizer, prompt, generation_prompt=True))
        params = types.SamplingParams(max_tokens=args.max_tokens, temperature=0.0, seed=0)
        resp = sampler.sample(prompt=model_input, num_samples=1, sampling_params=params).result()
        text = tokenizer.decode(resp.sequences[0].tokens)
        generated.append(
            {
                "decision": ex["meta"]["decision"],
                "reference": ex["messages"][-1]["content"],
                "fine_tuned": text,
            }
        )
        print(f"  sample ({ex['meta']['decision']}): {text[:90]}...")

    final_train = mean_loss(training_client, train_data, args.batch_size)
    final_val = mean_loss(training_client, val_data, args.batch_size)

    payload = {
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "task": "LoRA fine-tune of a base model on Baahar briefings, vs the base model",
        "provider": "Tinker (remote GPU); base model served by them, nothing trained locally",
        "sdk_version": getattr(tinker, "__version__", "unknown"),
        "base_model": args.base_model,
        "lora_rank": args.lora_rank,
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "batch_size": args.batch_size,
        "n_train": len(train_data),
        "n_val": len(val_data),
        "checkpoint_name": args.checkpoint_name,
        "loss": "mean token-level cross-entropy",
        "baseline": {"train": round(base_train, 6), "val": round(base_val, 6)},
        "fine_tuned": {"train": round(final_train, 6), "val": round(final_val, 6)},
        "curve": curve,
        "val_delta": round(final_val - base_val, 6),
        "train_delta": round(final_train - base_train, 6),
        "generated": generated,
        "setup_seconds": round(setup_seconds, 1),
        "train_seconds": round(train_seconds, 1),
        "caveats": [
            f"Single seed and a single LoRA configuration ({args.lora_rank=} "
            f"{args.learning_rate=} {args.epochs=}). One point on a hyper-parameter "
            "surface, not a tuned result.",
            f"{len(val_data)} validation examples is a small held-out set; a val-loss "
            "move of a few hundredths should not be read as decisive.",
            "The dataset targets were written by the deterministic local writer, so "
            "this measures how far a base model can be pulled toward that style, not "
            "whether the style is right.",
            "tau_mod-style tuning and the briefing safety checks still apply at "
            "serving time; a fine-tuned model does not bypass them.",
        ],
    }

    RAW.mkdir(parents=True, exist_ok=True)
    if args.out:
        out = Path(args.out)
        if not out.is_absolute():
            out = ROOT / out
    else:
        out = RAW / f"tinker_{time.strftime('%Y%m%dT%H%M%S%z')}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nval loss {base_val:.4f} -> {final_val:.4f} ({payload['val_delta']:+.4f})")
    print(f"train loss {base_train:.4f} -> {final_train:.4f} ({payload['train_delta']:+.4f})")
    print(f"artifact -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
