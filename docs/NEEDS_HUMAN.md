# NEEDS_HUMAN.md

Everything in this file is something **a human must do**. Agents cannot claim a
promo code, accept a licence on someone's behalf, hold a phone during a walk, or
publish a DEV post. Nothing here blocks the rest of the build: Baahar runs
fully with zero keys, and the code paths for everything below are implemented,
tested and documented.

Ordered by what unblocks the most.

---

## 1. TabPFN — unblocks the **TabPFN** prize category (Featured, $200)

**Status: code complete, evaluation blocked on one licence acceptance.**

`uv run python scripts/run_eval.py` currently reports:

```
tabpfn  SKIPPED -- tabpfn refuses to download weights until a Prior Labs
        licence acceptance is recorded in TABPFN_TOKEN, even though the
        weights are public on Hugging Face. We do not bypass a licence gate.
```

Background, verified 2026-10-06: `tabpfn==9.1.0` calls
`ensure_license_accepted()` before it will fetch weights. The weights themselves
are public — `Prior-Labs/TabPFN-v2-clf` reports `gated=False` — so the block is
a **licence acceptance, not a technical or access limit**. Baahar deliberately
does not patch around it. Everything else about the TabPFN path is done: the
adapter, the feature matrix, the eval harness, and the safety asymmetry that
prevents the model from being more permissive than the safety policy.

> **UPDATE 2026-10-06: licence accepted, TabPFN runs.** `TABPFN_TOKEN` is now in
> `.env` and `TabPFNClassifier(device="cpu").fit(...)` completed against
> `tabpfn_3_5` weights. The results below are the ones to follow.

### Steps (about 3 minutes)

1. Register at <https://ux.priorlabs.ai>.
2. Sign in, open the **Licenses** tab, accept the TabPFN licence.
3. Copy the API key from <https://ux.priorlabs.ai/account>.
4. Put it in `.env`:
   ```
   TABPFN_TOKEN=your-key-here
   ```
   Note the variable name is `TABPFN_TOKEN`, not `TABPFN_API_KEY`. That is what
   the upstream package reads.
5. Re-run:
   ```bash
   uv sync --group dev --group ml
   uv run python scripts/run_eval.py
   ```
6. Copy the numbers from `eval/raw/gono_*.json` into `eval/RESULTS.md`.

If you would rather not deal with the licence, **skip it and say so in the post.**
The honest version of the write-up is "TabPFN is implemented but gated behind a
licence acceptance I did not have time to complete", and the conventional
baselines in `RESULTS.md` are strong enough to carry the argument on their own.
Do not claim the TabPFN category for code that never ran.

---

## 2. Tinker — unblocks the **Tinker** prize category (Featured, $200)

**Status: dataset and training script written, not yet run.**

Fine-tuning has to be hosted (a LoRA in the multi-GB range will not fit this
project's disk budget, which is a hard constraint in `AGENTS.md`).

### Steps

1. Claim the Tinker promo at <https://hacktoberfest.com/my/promos> while logged
   in. Credits, not a card.
2. Create a Tinker API key at <https://tinker.ai>.
3. Put it in `.env`:
   ```
   TINKER_API_KEY=...
   TINKER_TRAINING_LOOP_NAME=...   # optional, to reuse a loop from a previous job
   ```
4. Build the fine-tuning dataset:
   ```bash
   uv run python scripts/build_ft_dataset.py
   ```
5. Launch and monitor the run:
   ```bash
   uv run python scripts/fine_tune_tinker.py --submit
   uv run python scripts/fine_tune_tinker.py --sample --n 36
   ```
6. A/B the fine-tune against the Gemma baseline:
   ```bash
   uv run python scripts/run_briefing_eval.py --writers gemma,tinker
   ```
7. Copy the table into `eval/RESULTS.md`.

If the run fails or credits do not arrive, the fallback is already written up:
**ship Gemma-only and say so.** `docs/adr/001-tinker-outcome.md` records the
decision either way.

---

## 3. Google AI Studio — Gemma (already done, but keep the key)

**Status: working.** A `GEMINI_API_KEY` was present in the environment, so the
Gemma path has been evaluated for real. To reproduce on another machine:

1. Get a free key at <https://aistudio.google.com/apikey>. No credit card.
2. Put it in `.env` as `GEMINI_API_KEY`.
3. Verify:
   ```bash
   uv run baahar check          # prints key presence only, never a key
   uv run baahar brief --model gemma
   ```

Two operational notes worth knowing:

- **Open-weight Gemma on the free tier is slow.** Measured 40–95 s per briefing,
  because the Gemma 4 series emits a long reasoning trace that
  `thinkingConfig.thinkingBudget` cannot disable on these models (the API
  returns "Thinking budget is not supported for this model"). Baahar ships a
  deterministic template writer as the default fast path and caches model
  output. This is documented in `eval/RESULTS.md` rather than hidden.
- **Per-model quotas.** Free-tier limits are enforced per model, so
  `gemini-2.5-flash` can return HTTP 429 while `gemini-2.5-flash-lite` works
  fine. The eval harness probes a candidate list.

---

## 4. ElevenLabs — unblocks the **ElevenLabs** prize category (Partner, $100)

**Status: client implemented and tested against fixtures, never called live.**

Baahar already generates the briefing; voice is a few lines on top.

1. Claim the ElevenLabs promo at <https://hacktoberfest.com/my/promos>.
2. Create an API key at <https://elevenlabs.io>.
3. Pick a voice and copy its ID.
4. Put both in `.env`:
   ```
   ELEVENLABS_API_KEY=...
   ELEVENLABS_VOICE_ID=...
   ```
5. Verify:
   ```bash
   uv run baahar brief --model template --voice
   uv run baahar serve      # then hit "speak" in the UI
   ```

Voice is the highest-leverage stretch feature for this particular challenge,
because Pocket Mode's whole argument is that you should not be looking at a
screen. If time is short, this is the one to do.

---

## 4b. Seasonal snapshots — optional, and needs no key at all

**Status: shipping.** Pocket Mode's species cues read
`data/seasonal/blr_<year>_<month>.json`, a recorded iNaturalist snapshot that is
committed to the repo. No key, no network, nothing to do.

It is listed here only because a snapshot goes stale. The one in the repo covers
**October 2026**; next month the app falls back to the hand-written sensory cues,
which is a supported outcome and not a broken state.

To refresh — about 20 seconds, no key, no signup:

```bash
uv run python scripts/refresh_seasonal.py              # current month
uv run python scripts/refresh_seasonal.py --all-months # one snapshot, no month filter
```

Commit the file it writes. Worth doing once a month if you keep using this
repo; not worth doing at all if the field test is the priority.

---

## 5. WAQI — optional live station cross-check

Not a prize category. Improves the honesty of the number by showing what a real
monitoring station says versus the forecast.

1. Free token at <https://aqicn.org/data-platform/token/>.
2. `WAQI_TOKEN=...` in `.env`.

Baahar labels WAQI readings as **US EPA AQI** and only ever uses them as a
directional cross-check, never as the number shown to the user. That is because
converting an EPA index back to a concentration to derive Indian NAQI would be
a lossy round trip through a different standard.

---

## 6. Render — optional hosted demo

Not required. A recorded screen capture plus the local quickstart is enough for a
judge, and the challenge explicitly accepts "clear local run + recorded demo".

1. Claim the Render promo at <https://hacktoberfest.com/my/promos>.
2. `render.yaml` is included; Render picks it up automatically.
3. **Abort cleanly if you hit a credit-card wall** and record that in
   `eval/RESULTS.md`. Do not enter a card.

---

## 7. The outdoor walk — the field test

**This is the only part of Baahar that cannot be automated, and the only part
that makes it real.** No agent will fabricate it.

Checklist: [`docs/FIELD_TEST.md`](FIELD_TEST.md).

Short version: check `uv run baahar brief`, read or hear it once, tap
**Pocket the phone**, walk 15–25 minutes in a Bengaluru park, and write down
what matched and what did not. Five bullets and up to three photos is enough.

When it is done, fill in the "Results" section of `FIELD_TEST.md` and move the
notes into `post.md`. Until then both documents say the walk has not happened.

---

## 8. Publishing

1. `post.md` is a complete draft. Edit it in your own voice — it is written to be
   rewritten, not defended.
2. Post to DEV using the challenge template.
3. Tags: `#devchallenge` `#hf26challenge`
4. **Prize categories: list only what actually ran.** Current honest list is in
   `post.md` under "Prize categories". If TabPFN was never licensed, do not list
   TabPFN. If the Tinker run failed, do not list Tinker.
5. Deadline: **Oct 11, 2026 23:59 PDT = Oct 12, 2026 12:29 PM IST.** Write-up
   lock target is Oct 12 10:00 AM IST.

---

## Summary

| # | Item | Unblocks | Effort | Agent blocked? |
|---|---|---|---|---|
| 1 | TabPFN licence | TabPFN category | 3 min | yes |
| 2 | Tinker key + FT run | Tinker category | 20 min + job | partly |
| 3 | Gemini key | Gemma category | done | no |
| 4 | ElevenLabs key | ElevenLabs category | 5 min | yes |
| 5 | WAQI token | nothing | 2 min | no |
| 6 | Render promo | nothing | 10 min | yes |
| 7 | The walk | credibility | 30 min | **yes, always** |
| 8 | Publish | everything | 30 min | yes |
| 4b | Monthly seasonal refresh | nothing (goes stale) | 20 s | no |

---

## What is already done, so you can skip ahead

- Everything that needs no key: the whole product, the web UI, Pocket Mode, the
  journal, the CLI, the seasonal species cues, and 267 offline tests.
- **Gemma.** A key was present in the build environment, so the Gemma path was
  evaluated for real: 36 cases, machine checks plus a blind rubric.
  [`eval/RESULTS.md`](../eval/RESULTS.md) § B.
- **The tabular eval.** 8,130 rows from keyless archives, five models, full
  confusion matrix. `eval/RESULTS.md` § A.
- **A verification tool for my own numbers.**
  `uv run python scripts/check_results.py` fails if RESULTS.md stops matching the
  raw artifacts. It runs in CI.

So the *only* things standing between this repo and a complete submission are
the five human items above, and three of them are under five minutes each.