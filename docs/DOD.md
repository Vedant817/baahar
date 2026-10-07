# Definition of Done

The checklist from the HF26 Week 1 brief, with an honest status for each item.
Last updated **2026-10-07 IST**.

Legend: **DONE** · **PARTIAL** (implemented, one thing outstanding) ·
**BLOCKED** (needs a human) · **NOT DONE**

---

## Repository

| | Item | Evidence |
|---|---|---|
| **DONE** | New public GitHub repo, started inside the challenge window | [github.com/Vedant817/baahar](https://github.com/Vedant817/baahar), first commit 2026-10-06 |
| **DONE** | MIT licence | [`LICENSE`](../LICENSE) |
| **DONE** | Green README: quickstart, architecture, why-open, field test | [`README.md`](../README.md) |
| **DONE** | CLI exercised as a subprocess, exit codes asserted | `tests/test_cli.py`, 17 tests |
| **DONE** | CI green on all three jobs | lint · format · tests · offline smoke · secret scan · honest-numbers · headless-Chrome UI audit |
| **DONE** | No secrets in git | `.env` gitignored; `.env.example` complete and empty |
| **DONE** | Tests pass offline | `uv run pytest` 529 passed, no network |
| **DONE** | Lint clean | `uv run ruff check .` |
| **DONE** | Conventional commits with real explanations | `git log` |

## Product

| | Item | Evidence |
|---|---|---|
| **DONE** | Weather + air-quality fetch (keyless) | `weather.py`, `air.py`, recorded fixtures in `data/samples/` |
| **DONE** | Indian NAQI, not US AQI | `naqi.py`; CPCB breakpoints; `naqi_basis` provenance on every result |
| **DONE** | GO / WAIT / SKIP scorer with documented policy | `features.py`, `score.py` |
| **DONE** | Heuristic fallback always available | `score_heuristic`, called directly in `tests/test_score.py` and `tests/test_pocket.py`, and used as the fallback whenever a model is absent |
| **DONE** | TabPFN path implemented + evaluated | `tabpfn==9.1.0` on cpu ran for real on 2026-10-07 on 28 features (13 base + 15 past-hour lags) across 5 seeds (0–4): **0.8708 +/- 0.0023 acc / 0.6193 +/- 0.0020 macro-F1** (averaged over 4 supported bands). Leads raw accuracy, but loses macro-F1 to the shipped consensus ensemble (0.6349 +/- 0.0368; 3 bands: 0.8249 vs 0.8236) and falls behind on moderate recall (0.5845 vs 0.6620 on seed 0). Fit time ~358 s vs ensemble ~46 s. [`eval/RESULTS.md`](../eval/RESULTS.md) § A. *(Historical superseded runs: 13-feature run was 0.8542 / 0.6031; earlier provisional run on instantaneous NAQI, not like-for-like: 0.8512 / 0.6040).* The request-time path is exercised by test after the feature-alignment fix (C.14) and only runs when a token and the artifact are both present. |
| **DONE** | Gemma briefing path works | `brief.py`; `gemma-4-31b-it` via AI Studio free tier |
| **DONE** | ≤120-word safety-aware briefing | `MAX_WORDS`, `enforce_safety` |
| **DONE** | Pocket Mode | `pocket.py` + `static/`, verified headless |
| **DONE** | Seasonal species cues, evidence-backed | `seasonal.py`; research-grade iNaturalist snapshot in `data/seasonal/`; hedged wording + radius clamping + safety suppression tested |
| **DONE** | After-walk journal | `journal.py`, `baahar journal --markdown`; produces the field-test block |
| **DONE** | CLI | `baahar brief · score · parks · journal · check · serve` |
| **DONE** | Offline / fixture mode | `BAAHAR_OFFLINE=1`, `data/samples/` |
| **DONE** | Failure modes never return a cheerful empty answer | `tests/test_offline.py`; `UpstreamError` reaches the client as HTTP 503 |

## Evaluation

| | Item | Evidence |
|---|---|---|
| **DONE** | Non-circular dataset | `scripts/build_dataset.py` → 8130 rows; target is the band +6h, measured independently |
| **DONE** | Chronological split, no shuffle | `time_split`; `run_eval.py` |
| **DONE** | Real tabular numbers with baselines | [`eval/RESULTS.md`](../eval/RESULTS.md), raw in `eval/raw/` |
| **DONE** | `skip_as_go_rate` with a Wilson interval | headline safety metric; n(SKIP) reported because it is small |
| **DONE** | Briefing eval: machine checks | `scripts/run_briefing_eval.py`, 36 stratified cases |
| **DONE** | Briefing eval: blind LLM rubric | same script; judge model recorded per run |
| **DONE** | Rubric validity check | `rubric_health()` fails the harness if the judge scores by decision label |
| **DONE** | Published numbers verified against raw artifacts | `scripts/check_results.py`, wired into CI, negative-tested |
| **DONE** | Latency p50/p95 measured | 3 ms / 6 ms local · 51,730 ms / 115,187 ms Gemma |
| **DONE** | At least one documented failure | 10 failures in [`eval/RESULTS.md`](../eval/RESULTS.md) § C |
| **DONE** | Package versions + timestamps in raw output | `eval/raw/*.json` |
| **NOT DONE** | Fine-tune vs baseline table | Tinker API unverifiable → [`adr/001-tinker-outcome.md`](adr/001-tinker-outcome.md) |

## Constraints

| | Item | Evidence |
|---|---|---|
| **DONE** | No credit card used | No paid signup anywhere in the stack |
| **DONE** | No multi-GB model downloads | TabPFN in an opt-in group; no weights committed |
| **DONE** | Beginner-approachable repo | one-command quickstart, offline tests, plain-Python front end |
| **DONE** | India-first | Bengaluru, CPCB NAQI, monsoon-exit October, dust |
| **DONE** | Prize categories reflect real usage | see below |

## Writing and field test

| | Item | Evidence |
|---|---|---|
| **DONE** | DEV post draft complete | [`post.md`](../post.md) |
| **NOT DONE** | Field test performed | [`FIELD_TEST.md`](FIELD_TEST.md) — **not yet done**, and marked as such |
| **NOT DONE** | Photos / video | Awaiting the walk |
| **DONE** | Human-only steps documented | [`NEEDS_HUMAN.md`](NEEDS_HUMAN.md) |
| **NOT DONE** | DEV post published | Human step, deadline Oct 11 23:59 PDT |

## Prize categories — honest list

Only categories for tech that **actually ran**, per the challenge rule.

| Category | Claim? | Why |
|---|---|---|
| **Gemma** | **Yes** | `gemma-4-31b-it` generated and evaluated briefings. Open-weight model at the core of the product. |
| **TabPFN** | **Yes** | `tabpfn==9.1.0` ran on the real chronological holdout (1,626 rows) on 28 features (13 base + 15 past-hour lags) across 5 seeds: **0.8708 +/- 0.0023 acc / 0.6193 +/- 0.0020 macro-F1** (4 supported bands). Genuine evaluation, no longer provisional or SKIPPED; leads raw accuracy, though the shipped consensus ensemble wins macro-F1 (0.6349 vs 0.6193; 3 bands: 0.8249 vs 0.8236) and moderate recall (0.6620 vs 0.5845). Licence accepted by the human, token set in `.env`. [`eval/RESULTS.md`](../eval/RESULTS.md) § A. *(Earlier 13-feature run was 0.8542 / 0.6031; earlier provisional run on instantaneous NAQI was 0.8512 / 0.6040, not like-for-like).* |
| **Tinker** | **No** | Dataset built (219 examples), run not performed. Do not claim. |
| **Render** | **No** | Not deployed. |
| **ElevenLabs** | **No** | Client implemented, never called. Do not claim. |
| **Overall / completion** | Yes | The submission is a new, working, open-source project. |

If the human completes `NEEDS_HUMAN.md` §1, §2 or §4 and re-runs the evals,
this table should be updated to match. The rule is simple: **the post may only
name what a reader can reproduce.**

## Known gaps, stated plainly

1. **No field test.** The strongest claim in the project — that the screen is
   the shortest part of the walk — is currently unverified by a human. This is
   the most important outstanding item. `baahar journal` now makes it a three-tap
   job rather than a blank form.
2. **No Tinker numbers.** `tinker.ai` is unreachable from this environment
   (DNS fails), so the API shape stays unverified and the endpoint stays empty.
   The 219-example fine-tune dataset is built and committed; the run has not
   happened. Documented in `adr/001`, not faked.
3. **The tabular holdout contains no Severe or Hazardous hours**, and every SKIP
   in it was rain (22) or heat (2) — zero air quality. So `skip_as_go_rate = 0.0`
   measures rain and heat handling, **not** air-quality safety, and this
   evaluation does not rule out a model that would fail on a polluted day. The
   harness reports the SKIP-cause breakdown for exactly this reason.
4. **The blind rubric is saturated** (8.92–10.00 across 72 briefings). It
   separates a broken briefing from a good one and barely ranks good ones against
   each other. The 9.83-vs-9.53 gap should be read as "a tie, with the local
   writer also being 17,000× faster".
5. **The tabular eval is trained on reanalysis, served on forecasts.** The
   mismatch is documented in `RESULTS.md`. It is small — Open-Meteo's AQ forecast
   and archive come from the same CAMS model — but it is not zero.
6. **Gemma latency is 51.7 s p50 / 115.2 s p95.** Real, measured, and the reason
   the deterministic writer is the default.
7. **TabPFN leads accuracy (0.8708), and is NOT the best engine for the product.**
   It achieves the highest raw accuracy (0.8708 +/- 0.0023 vs ensemble 0.8617 +/- 0.0005),
   but loses macro-F1 to the consensus ensemble (0.6193 +/- 0.0020 vs 0.6349 +/- 0.0368 averaged
   across the 4 supported bands; on the 3 bands with real support, ensemble 0.8249 vs TabPFN 0.8236)
   and falls behind on moderate recall (0.5845 vs 0.6620 on seed 0) — the critical under-warning direction
   for outdoor air safety. It is also ~7.7× slower to fit (~358 s vs ~46 s for the ensemble). The +/- figures
   are seed spreads over 5 seeds (sd 0.0005 for ensemble; binomial SE at n=1,626 is ~0.009, ~18× larger,
   so seed spreads do not imply statistical significance). The consensus ensemble is the shipped engine.
   *(Old 13-feature run was 0.8542 / 0.6031 vs 0.8483 / 0.6079; earlier provisional single-seed run on instantaneous NAQI was 0.8512 / 0.6040, not like-for-like).*
8. **The fitted TabPFN classifier is 840 MB** and is deliberately not committed
   (`eval/artifacts/` is gitignored). `scripts/run_eval.py` recreates it. This is
   the disk constraint doing its job: the weights stay out of the repo.
9. **The eval measured a pipeline the app did not run**, until the feature lists
   were unified. 13 archive columns against 15 library features meant a fitted
   model raised inside `predict_proba` and every hour fell back to the heuristic
   while the accuracy table was published as a result. Fixed and re-run — no
   number moved — but the claim "the app scores with this exact model" was false
   until then. `RESULTS.md` § C.14.
10. **Not deployed.** A local run plus a recorded walk is acceptable to the
    challenge; `render.yaml` is ready if a promo is claimed.
