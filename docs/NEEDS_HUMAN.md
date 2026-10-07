# NEEDS_HUMAN.md

Everything in this file is something **a human must do**. Agents cannot claim a
promo code, accept a licence on someone's behalf, hold a phone during a walk, or
publish a DEV post. Nothing here blocks the rest of the build: Baahar runs
fully with zero keys, and the code paths for everything below are implemented,
tested and documented.

Ordered by what unblocks the most.

---

## 1. TabPFN — unblocks the **TabPFN** prize category (Featured, $200)

**Status: COMPLETED. Evaluated across 5 seeds on current features.**

`TABPFN_TOKEN` is configured and TabPFN 9.1.0 ran on the 1,626-row chronological
holdout on 28 features (13 base + 15 past-hour lags) across 5 seeds (0–4). The earlier
`SKIPPED` status and provisional single-seed numbers have been retired.

Artifact: [`eval/raw/gono_20261007T173452+0530.json`](../eval/raw/gono_20261007T173452+0530.json).

Results:
- **Accuracy**: 0.8708 +/- 0.0023 (highest in the evaluation, +0.0091 over the consensus ensemble 0.8617 +/- 0.0005).
- **Macro-F1**: 0.6193 +/- 0.0020 (averaged over the 4 supported bands; loses to consensus ensemble 0.6349 +/- 0.0368; on 3 bands with real support, ensemble 0.8249 vs TabPFN 0.8236).
- **Moderate recall**: 0.5845 (seed 0 is 0.5845, 5-seed mean is 0.5845 +/- 0.0000) vs ensemble 0.6620 (7.75 percentage points worse on the critical under-warning boundary).
- **Fit time**: 358.1 s per fit (~6 minutes on CPU) vs ensemble 46.43 s (~7.7× slower).

> **Prize category status**: **Genuinely claimable.** TabPFN was evaluated for real
> on the current 28-feature pipeline without mocks or shortcuts. The post claims the category
> honestly, while explicitly reporting the product trade-off: TabPFN is the accuracy leader
> on raw accuracy (0.8708), but the consensus ensemble remains the superior engine
> for this product because it wins macro-F1 (0.6349 vs 0.6193) and substantially outperforms TabPFN on
> moderate recall (0.6620 vs 0.5845).
>
> The `+/-` figures are seed spreads (sample standard deviations over 5 seeds 0–4), not confidence
> intervals: ensemble seed sd is 0.0005, whereas the binomial SE at n=1,626 is ~0.009 (~18× larger).
>
> *(Historical note: The earlier 13-feature run scored 0.8542 / 0.6031. An older single-seed run scored
> 0.8512 acc / 0.6040 macro-F1 on instantaneous-only NAQI before the conservative-NAQI fix; in a subsequent
> run it was SKIPPED when the token was temporarily unset. Both were superseded by the 28-feature 5-seed run).*

### Reproduction steps (if reproducing on a clean environment)

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
   uv run python scripts/run_eval.py --repeat 5
   ```
6. The outputs match `eval/raw/gono_20261007T173452+0530.json` and [`eval/RESULTS.md`](../eval/RESULTS.md).

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

## 4. ElevenLabs - unblocks the **ElevenLabs** prize category (Partner, $100)

**Status: BLOCKED AT THE VENDOR'S PAID PLAN. Tested live 2026-10-07.**

Baahar already generates the briefing; voice is a few lines on top, and the
client is implemented and tested against fixtures.

### What the live call returned

With a real `ELEVENLABS_API_KEY` and a real `ELEVENLABS_VOICE_ID` in `.env`, the
text-to-speech call returns:

```
POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}   -> HTTP 402

{"detail":{"type":"payment_required",
           "code":"paid_plan_required",
           "message":"Free users cannot use library voices via the API.
                       Please upgrade your subscription to use this voice.",
           "status":"payment_required"}}
```

This is not a missing key, a wrong voice ID, or a bad request. The credentials
are valid and the endpoint answers; **the free plan is not permitted to call
library voices over the API at all.** No amount of configuration on our side
changes that.

### Why we stop here rather than upgrade

`AGENTS.md` forbids adding a service that requires a card signup, and says to
abort cleanly and ship the fallback when a partner promo walls on a card. That is
exactly this. Upgrading would also mean the ElevenLabs number in
`eval/RESULTS.md` depended on a paid account, which is a different claim from the
one this repo makes about everything else.

The product already degrades correctly: `brief --voice` without a working voice
falls back to the text briefing and says so. Nothing breaks; one optional feature
is absent.

### To unblock

Only a paid ElevenLabs plan does it. If you have one:

1. Claim the ElevenLabs promo at <https://hacktoberfest.com/my/promos>.
2. Put the key and a voice ID in `.env`:
   ```
   ELEVENLABS_API_KEY=...
   ELEVENLABS_VOICE_ID=...
   ```
3. Verify:
   ```bash
   uv run baahar brief --model template --voice
   uv run baahar serve      # then hit "speak" in the UI
   ```
4. Re-run the briefing eval and update `eval/RESULTS.md` § B.

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
4. **Read this before you expose it publicly.** `render.yaml` binds `0.0.0.0`,
   so the app is reachable by anyone who finds the URL, and `/api/brief` has no
   authentication and no rate limit. `POST /api/cache/clear` is now restricted to
   loopback callers, but that only removes the cheap way to force a cache miss -
   varying `park` or `hours` misses the cache anyway, so an anonymous caller can
   still spend your Gemini and ElevenLabs quota on ~45 s calls. If you deploy this
   for the challenge, treat it as a demo with an open door: either accept the
   quota risk, or put it behind whatever auth your host offers. Nothing in the
   codebase papers over this.
---

## 6b. Git history - a removed file is still readable (security, human only)

**Verified 2026-10-07: still true.** An earlier commit included
`data/journal.jsonl` - the field-test journal. It was removed from `main` and the
history was rewritten to drop it, but the blob is still served by GitHub to anyone
who asks for it by SHA, with no authentication:

```
GET https://api.github.com/repos/Vedant817/baahar/git/blobs/09c74ab9b7289bec1dd34e00b475a92282b12219
-> 200 OK
```

No credential was ever in that file - it holds walk notes, and the CI gate confirmed
`.env` was never committed - so this is a privacy item, not a key exposure. It is
still worth closing, because "we deleted it" is not the same claim as "nobody can
read it". Only a human can do this; an agent cannot delete objects from someone
else's GitHub account.

Options, cheapest first:

1. Leave it and say so. The file holds nothing sensitive, and an honest note in the
   README is defensible.
2. Contact [GitHub Support](https://support.github.com/contact) and ask them to
   garbage-collect the dangling object. This normally works within a few days.
3. Delete and re-create the repository, then re-push. Guaranteed, but it breaks the
   star/fork history and any existing links.

The guard against a repeat is already in place: `scripts/check_untracked.py` runs in
CI and fails if `data/journal.jsonl`, `.env`, `eval/artifacts/*.pkl` or `.env.*` is
ever tracked again, so this cannot silently come back.

---

## 7. The outdoor walk — the field test

**This is the only part of Baahar that cannot be automated, and the only part
that makes it real.** No agent will fabricate it.

Checklist: [`docs/FIELD_TEST.md`](FIELD_TEST.md).

Short version: check `uv run baahar brief`, read or hear it once, tap
**Pocket the phone**, walk 15–25 minutes in a Bengaluru park, and write down
what matched and what did not. Five bullets and up to three photos is enough.

Two things to do during the walk that are easy to forget:

1. **Tap "another thing to notice" three or four times** until a species cue
   appears. That is what unlocks the journal's "did you see it?" question.
2. **Count the phone reaches honestly.** That number is the design claim's only
   test.

Then:

```bash
uv run baahar journal --outcome went --phone 3 \
  --species "a Chocolate Pansy" --saw no \
  --note "kept reaching for the phone around minute six"

uv run baahar journal --markdown --all   # paste into post.md section 7
```

Repeat that at least three times if you can — the species sighting rate only
appears at n=3, and one walk is an anecdote rather than a measurement.

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

| # | Item | Unblocks | Effort | Agent blocked? | Status |
|---|---|---|---|---|---|
| 1 | TabPFN licence | TabPFN category | 3 min | no (token set) | **done** — ran 2026-10-07 on current 28 features over 5 seeds (0.8708 acc / 0.6193 macro-F1); category claimable |
| 2 | Tinker key + FT run | Tinker category | 20 min + job | partly | blocked: `tinker.ai` does not resolve |
| 3 | Gemini key | Gemma category | done | no | **done** — 36 cases judged |
| 4 | ElevenLabs paid plan | ElevenLabs category | a paid plan | yes | **blocked at the vendor**: free accounts cannot call library voices over the API (HTTP 402) |
| 5 | WAQI token | nothing | 2 min | no | **done** — found a 1,727 km bug |
| 6 | Render promo | nothing | 10 min | yes | optional |
| 7 | **The walk** | credibility + the species rate | 30 min × 3 | **yes, always** | **not done** |
| 8 | Publish | everything | 30 min | yes | ready, one optional marker |
| 4b | Monthly seasonal refresh | nothing (goes stale) | 20 s | no | October snapshot committed |
| 6b | Purge the dangling journal blob | nothing (privacy) | 10 min + waiting | yes | **open** - blob still served, HTTP 200, verified 2026-10-07 |

---

## What is already done, so you can skip ahead

- Everything that needs no key: the whole product, the web UI, Pocket Mode, the
  journal (including the species sighting question), the CLI, the seasonal species
  cues, and 529 offline tests.
- **TabPFN ran for real across 5 seeds.** With `TABPFN_TOKEN` configured, TabPFN 9.1.0
  was evaluated on the 1,626-row chronological holdout on 28 features (13 base + 15 past-hour lags):
  **0.8708 +/- 0.0023 acc / 0.6193 +/- 0.0020 macro-F1** (4 supported bands).
  It leads raw accuracy, but loses macro-F1 and moderate recall (0.5845 vs 0.6620) to the consensus ensemble,
  which is the shipped engine. The earlier 13-feature numbers (0.8542 / 0.6031), the provisional 0.8512 / 0.6040
  single-seed numbers, and the SKIPPED status have all been retired as superseded history.
  [`eval/RESULTS.md`](../eval/RESULTS.md) § A.
- **Gemma.** A key was present in the build environment, so the Gemma path was
  evaluated for real: 36 cases, machine checks plus a blind rubric.
  [`eval/RESULTS.md`](../eval/RESULTS.md) § B.
- **The tabular eval.** 8,130 rows from keyless archives, five models, full
  confusion matrix. `eval/RESULTS.md` § A.
- **A verification tool for my own numbers.**
  `uv run python scripts/check_results.py` fails if RESULTS.md stops matching the
  raw artifacts. It runs in CI.

So the *only* things standing between this repo and a complete submission are
the human items above, and most of them are under five minutes each. One of
them - the walk - is the only one no amount of engineering can substitute for,
and one (§6b) is cleanup rather than a feature.
