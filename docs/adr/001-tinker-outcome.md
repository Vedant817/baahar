# ADR 001 — Tinker fine-tuning outcome

- **Status:** Blocked — dataset built, API unverifiable, no endpoint invented
- **Date:** 2026-10-06 IST
- **Relates to:** the "Tinker" prize category in the HF26 Week 1 brief

## Decision

Ship the fine-tuning **dataset** and the **evaluation harness**, do not ship a
fine-tuned model, and do not enter the Tinker prize category.

## What was attempted

1. `scripts/build_ft_dataset.py` runs successfully and produces **219
   balanced examples** (80 GO / 80 WAIT / 59 SKIP), built from the archived
   historical rows so the conditions are real, spanning Indian NAQI 26–302 with
   a mean target length of 50 words. It excludes everything after 2026-09-05 so
   the fine-tuning data cannot contaminate the tabular holdout.
2. `scripts/fine_tune_tinker.py` and `brief.py`'s Tinker writer are implemented
   against a *configurable* endpoint rather than a hard-coded one.
3. `scripts/run_briefing_eval.py --writers gemma,tinker` will produce the
   baseline-vs-fine-tuned table as soon as a trained model is available.

## Why it is blocked

The Tinker API could not be verified from the build environment:

```
https://tinker.ai              -> request timed out
https://tinker.ai/docs         -> request timed out
https://docs.tinker.ai         -> no such host
https://api.tinker.ai/v1/...   -> no such host
```

An earlier version of `brief.py` hard-coded
`https://api.tinker.ai/v1/sampling/generate`. That URL was a **guess**, and
`AGENTS.md` explicitly forbids inventing APIs. Shipping it would have been worse
than shipping nothing:

- it would 404 in front of a judge who tried the Tinker path;
- it would make the repo *look* to have a Tinker integration that was never run;
- and it would contradict the honesty rule that governs every other number here.

So the endpoint is now read from `TINKER_SAMPLE_URL`, empty by default, and
`write_tinker` raises a clear, actionable error until someone reads the vendor
docs and sets it. The response parser still tolerates the several shapes the
vendor documents (plain completion string, sampled token list, OpenAI-style
`choices[0].text`), so it should work once the real path is supplied.

## Why the fallback is acceptable

The Gemma baseline is already evaluated on 36 stratified cases with a blind
rubric, and it scores well on the objective checks. The fine-tune's intended
benefit was stylistic — prose instead of a restated plan, Indian outdoor
vocabulary, a firmer SKIP register — not correctness. Those are real gains, but
they are not worth entering a prize category for code that never ran.

## To unblock

See [`docs/NEEDS_HUMAN.md`](../NEEDS_HUMAN.md) §2:

1. Claim the Tinker promo at <https://hacktoberfest.com/my/promos>.
2. Create an API key at <https://tinker.ai>.
3. Read the docs, set `TINKER_API_KEY` and `TINKER_SAMPLE_URL` in `.env`.
4. `uv run python scripts/fine_tune_tinker.py --submit`
5. `uv run python scripts/run_briefing_eval.py --writers gemma,tinker`
6. Copy the table into `eval/RESULTS.md` and update this ADR to Accepted.

## Consequences

- **Lost:** the Tinker prize category (Featured, $200) unless unblocked.
- **Kept:** the Gemma category, and an honest story about a constraint that was
  discovered rather than papered over.
- **Cost:** roughly an hour of the five-day budget, spent verifying an API
  instead of writing features. That was the right trade given the alternative
  was fabricated integration code.