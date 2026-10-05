# Definition of Done

The checklist from the HF26 Week 1 brief, with an honest status for each item.
Last updated **2026-10-06 IST**.

Legend: **DONE** · **PARTIAL** (implemented, one thing outstanding) ·
**BLOCKED** (needs a human) · **NOT DONE**

---

## Repository

| | Item | Evidence |
|---|---|---|
| **DONE** | New public GitHub repo, started inside the challenge window | [github.com/Vedant817/baahar](https://github.com/Vedant817/baahar), first commit 2026-10-06 |
| **DONE** | MIT licence | [`LICENSE`](../LICENSE) |
| **DONE** | Green README: quickstart, architecture, why-open, field test | [`README.md`](../README.md) |
| **DONE** | No secrets in git | `.env` gitignored; `.env.example` complete and empty |
| **DONE** | Tests pass offline | `uv run pytest` → 158 passed, no network |
| **DONE** | Lint clean | `uv run ruff check .` |
| **DONE** | Conventional commits with real explanations | `git log` |

## Product

| | Item | Evidence |
|---|---|---|
| **DONE** | Weather + air-quality fetch (keyless) | `weather.py`, `air.py`, recorded fixtures in `data/samples/` |
| **DONE** | Indian NAQI, not US AQI | `naqi.py`; CPCB breakpoints; `naqi_basis` provenance on every result |
| **DONE** | GO / WAIT / SKIP scorer with documented policy | `features.py`, `score.py` |
| **DONE** | Heuristic fallback always available | `score_heuristic`, exercised by 12 tests |
| **PARTIAL** | TabPFN path implemented + evaluated | Code complete and tested; **eval blocked** on a Prior Labs licence acceptance → `NEEDS_HUMAN.md` §1 |
| **DONE** | Gemma briefing path works | `brief.py`; `gemma-4-31b-it` via AI Studio free tier |
| **DONE** | ≤120-word safety-aware briefing | `MAX_WORDS`, `enforce_safety` |
| **DONE** | Pocket Mode | `pocket.py` + `static/`, verified headless |
| **DONE** | CLI | `baahar brief · score · parks · check · serve` |
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
| **DONE** | Latency p50/p95 measured | `eval/RESULTS.md` |
| **DONE** | At least one documented failure | [`eval/RESULTS.md`](../eval/RESULTS.md) § Failures |
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
| **DONE** | `post.md` complete DEV draft | [`post.md`](../post.md) |
| **NOT DONE** | Field test performed | [`FIELD_TEST.md`](FIELD_TEST.md) — **not yet done**, and marked as such |
| **NOT DONE** | Photos / video | Awaiting the walk |
| **DONE** | Human-only steps documented | [`NEEDS_HUMAN.md`](NEEDS_HUMAN.md) |
| **NOT DONE** | DEV post published | Human step, deadline Oct 11 23:59 PDT |

## Prize categories — honest list

Only categories for tech that **actually ran**, per the challenge rule.

| Category | Claim? | Why |
|---|---|---|
| **Gemma** | **Yes** | `gemma-4-31b-it` generated and evaluated briefings. Open-weight model at the core of the product. |
| **TabPFN** | **No** | Code complete, never executed — blocked by a licence acceptance. Do not claim. |
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
   the most important outstanding item.
2. **No TabPFN or Tinker numbers.** Both are one human step away. Both are
   documented rather than faked.
3. **`skip_as_go_rate` is 0.0 on n=24.** That is a real result but a weak one.
   Skip hours are genuinely rare in Bengaluru's year; the confidence interval is
   reported so it is not read as a guarantee.
4. **The tabular eval is trained on reanalysis, served on forecasts.** The
   mismatch is documented in `RESULTS.md`. It is small — Open-Meteo's AQ forecast
   and archive come from the same CAMS model — but it is not zero.
5. **Gemma latency is 40–95 s.** Real, measured, and mitigated with a template
   fast path and a cache. It is also the main thing a user feels.
6. **Not deployed.** A local run plus a recorded walk is acceptable to the
   challenge; a hosted demo would be better.