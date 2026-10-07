"""Tokeniser-output normalisation, shared by the fine-tuning scripts.

One function, one copy, because this exact bug has already bitten twice in this
repo.

`tokenizer.apply_chat_template(..., tokenize=True)` returns a `BatchEncoding` in
transformers 5.x, not a list of ints. Taking that at face value means `len(x)` is
the number of *keys* (2), not the number of tokens, and `x[:]` is a list of two
dicts. A training script written against that silently builds zero usable
examples and then either refuses to run -- correctly -- or reports a loss of
0.0000 before and after training, which looks like a result and is pure silence.

The safe version raises instead of defaulting. A missing metric must never
quietly become a number.
"""

from __future__ import annotations

from typing import Any


def as_int_list(out: Any) -> list[int]:
    """Normalise a tokeniser return value to a plain list of ints.

    Handles the shapes we actually see: a list of ints (older transformers), a
    `BatchEncoding` carrying `input_ids` (transformers 5.x), a nested list for
    batched input, and a tensor with `.tolist()`.
    """
    # `BatchEncoding` is a UserDict, not a dict subclass, so `isinstance(x, dict)`
    # is False for it -- and iterating it yields keys, not tokens. Duck-type on
    # `input_ids` instead, which is what actually identifies the shape.
    if hasattr(out, "keys") and "input_ids" in out:
        out = out["input_ids"]
    elif hasattr(out, "input_ids"):
        out = out.input_ids
    if hasattr(out, "tolist"):
        out = out.tolist()
    if out is None:
        return []
    flat: list[int] = []
    for item in out:
        if isinstance(item, (list, tuple)):
            flat.extend(int(x) for x in item)
        else:
            flat.append(int(item))
    return flat


def loss_sum(out: Any) -> float:
    """Pull the summed cross-entropy out of a training response, strictly.

    The hosted SDK returns it as `metrics['loss:sum']`. There is no `.loss`
    attribute; reading one with a default produced 0.0000 for every batch. A
    missing metric raises here rather than becoming a plausible-looking figure.
    """
    metrics = getattr(out, "metrics", None)
    if not isinstance(metrics, dict) or "loss:sum" not in metrics:
        raise ValueError(f"no loss in the response; got metrics={metrics!r}")
    return float(metrics["loss:sum"])
