# ADR 000 — Stack choice

- **Status:** Accepted
- **Date:** 2026-10-06 IST
- **Context:** HF26 Week 1 (Touch Grass), 5-day build, beginner-friendly repo
  required, no credit card, limited disk.

## Decision

**Python 3.12+ (developed on 3.14) backend, FastAPI + a build-step-free web UI,
Typer CLI, SQLite/JSONL storage. TabPFN lives in an optional `ml` extra.
Hosted fine-tuning via Tinker. No Node build toolchain in the shipped product.**

## Why

### Python, not Node/TypeScript

- The whole point of the TabPFN category is Python: `priorlabs/TabPFN` is a
  Python library, and the TabPFN *API* client is Python-first. Shipping Node
  would mean the flagship tabular model is second-class.
- The challenge's partner stack (Gemma via Gemini API, Tinker, TabPFN) is
  Python-shaped end to end.
- `numpy` / `pandas` / `scikit-learn` are needed for the honest baseline
  comparison in `eval/RESULTS.md` anyway.

### Python 3.14 specifically

The machine ships 3.14.3. The blocker for a new Python release is usually
wheels for the ML stack. Verified before committing:

```
torch 2.14.1 → cp310 cp311 cp312 cp313 cp314 (win_amd64) ✅
```

so TabPFN is installable on the native interpreter with no extra Python
download. `requires-python = ">=3.12"` in `pyproject.toml` keeps 3.12/3.13
working for contributors on older LTS-ish interpreters.

### Zero-build-step web UI (plain HTML + CSS + a little vanilla JS)

The single most important constraint on this repo is *"a judge must be able to
clone it and see the product in under five minutes."* A Vite/React SPA adds a
Node toolchain, `node_modules`, and a build step to an otherwise
`pip`-only project. Baahar ships one `static/index.html`, one stylesheet, and
one script file, served by the same FastAPI process that serves `/api/brief`.
Pocket Mode is a fullscreen state transition — it does not need a component
framework, and shipping without one keeps the diff readable for a newcomer.

Served as plain static assets: no CDN dependency, works fully offline after
install, and no supply-chain surface for a security-minded judge.

### TabPFN as an *optional* extra

`tabpfn` pulls PyTorch, which is roughly 2.5 GB on Windows. Making it a base
dependency would blow the 5-minute quickstart and the "limited disk" constraint
for every judge who only wants to read the briefing. So:

```bash
uv sync --extra dev            # fast: product + CLI + UI, no PyTorch
uv sync --extra dev --extra ml # adds TabPFN for the tabular go/no-go model
```

Baahar's scorer has a **documented heuristic fallback**, so the product is fully
functional either way. This is a design decision, not an accident — see
`src/baahar/score.py`.

### Hosted fine-tuning only

Tinker trains the LoRA remotely and we sample from its API. This is what makes
"fine-tune an open model on Indian outdoor-briefing style" compatible with a
laptop that must not download 55 GB of weights.

### SQLite / JSONL over MongoDB Atlas

Atlas commonly walls on a card. SQLite via the standard library `sqlite3`
module has zero install cost and zero signup. Baahar's persistence needs are
tiny (a short walk journal + cached fixtures), so anything heavier is
over-engineering.

## Consequences

- **Good:** `uv sync` is fast; `pytest` runs offline; a judge needs one
  language toolchain; the TabPFN category stays reachable.
- **Good:** Pocket Mode's near-black UI is achievable with plain CSS and is
  actually *more* reliable on a phone than a SPA shell.
- **Bad:** no component reuse story if the UI grows a lot. Accepted — the UI is
  three screens and is deliberately not growing.
- **Bad:** TabPFN results are only reproducible with `--extra ml`. Mitigated by
  recording every eval run's package versions in `eval/raw/*.json` and marking
  heuristic-only runs explicitly in `RESULTS.md`.