# Baahar eval results

**Rule zero: if it was not run, it is not published.** Partial results marked
`SKIPPED` beat fake completeness. Every number below came from a real
execution and can be traced to a machine-readable file in [`raw/`](raw/).

---

## Run metadata

| | |
|---|---|
| Dataset built | 2026-10-06 IST, 8,130 hourly rows |
| Compact run | 2026-10-07T14:54:10.627031+05:30 — five seeds (0–4) |
| Tabular run | 2026-10-07T14:51:38.957575+05:30 — base features, five seeds (0–4) |
| Briefing run | 2026-10-06 05:09 IST (36 cases × 2 writers, unchanged by the TabPFN run) |
| Location | Bengaluru, 12.9716 N, 77.5946 E |
| Keys present at tabular run | Gemma ✅ · TabPFN ❌ · WAQI ❌ · Tinker ❌ · ElevenLabs ❌ |
| Keys present at briefing run | Gemma ✅ · Tinker ❌ · TabPFN ❌ · ElevenLabs ❌ · WAQI ❌ |
| Device | CPU only. No GPU was used or available. |
| Python | 3.14.0 |
| LightGBM | 4.7.0 |
| numpy / scikit-learn / tabpfn / torch | 2.5.3 / 1.9.1 / 9.1.0 / 2.14.1 |
| Tabular artifact | [`gono_20261007T145138+0530.json`](raw/gono_20261007T145138+0530.json) — adopted run; compact comparison labelled in section A |
| Briefing artifact | [`briefing_20261006T050909+0530.json`](raw/briefing_20261006T050909+0530.json) — the run every § B number comes from |
| Raw artifacts | [`raw/`](raw/) — every run, including superseded ones |

Section A uses the adopted tabular artifact and labels its compact comparison.
Section B retains its separately recorded briefing run. Each artifact records
key-presence booleans and versions; the checker reads the cited tabular artifact.

### Reproduce

```bash
uv run python scripts/build_dataset.py --start 2025-11-01 --end 2026-10-05
uv run python scripts/run_eval.py --repeat 5 --feature-set compact
uv run python scripts/run_eval.py --repeat 5
uv run pytest scripts/test_check_results.py
uv run python scripts/build_briefing_cases.py
uv run python scripts/run_briefing_eval.py --writers template,gemma --no-cache
```

---

# A · Go / no-go

## Task and data

Predict the CPCB NAQI band six hours ahead from hour-t air quality and weather.
The target is the instantaneous future band; `naqi` is the conservative maximum
of instantaneous and trailing readings. GO/WAIT/SKIP remains a safety policy.
Chronological holdout, never shuffled.

| | |
|---|---|
| Rows | 8,130 hourly rows |
| Window | 2025-11-01T00:00 → 2026-10-05T17:00 |
| Air quality | Recorded Open-Meteo CAMS archive, CPCB Indian NAQI breakpoints |
| Weather | Recorded Open-Meteo ERA5 archive |
| Features (13) | `naqi`, `pm25`, `pm10`, `temp_c`, `apparent_c`, `precip_mm`, `precip_prob`, `humidity`, `wind_kmh`, `uv_index`, `is_day`, `hour`, `month` |
| Split | chronological, last 20% held out |

### Current input-band distribution

This is the current input band, not the future target. The older table showed
target support as current holdout support.

| Band | Train (6,504) | Holdout (1,626) |
|---|---|---|
| good | 733 | 642 |
| satisfactory | 2850 | 795 |
| moderate | 2566 | 186 |
| poor | 342 | 3 |
| severe | 13 | 0 |
| hazardous | 0 | 0 |

## Results: adopted base features (13)

Artifact: [gono_20261007T145138+0530.json](raw/gono_20261007T145138+0530.json).
Holdout: **1,626 rows**, 2026-07-30T00:00 → 2026-10-05T17:00.

| model | accuracy | macro-F1 | moderate recall | skip_as_go | n(SKIP) | decision acc | fit time |
|---|---|---|---|---|---|---|---|
| majority class | 0.4047 | 0.1441 | 0.0000 | 0.0 | 24 | 0.9982 | 0.0002 s |
| persistence | 0.3647 | 0.2492 | 0.2746 | 0.0 | 24 | 0.9982 | 0.0 s |
| logistic regression | 0.7294 +/- 0.0000 | 0.4850 +/- 0.0000 | 0.3662 | 0.0 | 24 | 0.9969 | 1.0026 s |
| random forest | 0.8325 +/- 0.0040 | 0.5695 +/- 0.0073 | 0.4296 | 0.0 | 24 | 0.9982 | 2.08 s |
| gradient boosting | 0.8383 +/- 0.0000 | 0.5874 +/- 0.0000 | 0.5493 | 0.0 | 24 | 0.9982 | 8.8106 s |
| lightgbm | 0.8437 +/- 0.0019 | 0.5837 +/- 0.0019 | 0.4930 | 0.0 | 24 | 0.9975 | 3.971 s |
| consensus ensemble | 0.8483 +/- 0.0005 | 0.6079 +/- 0.0006 | 0.6831 | 0.0 | 24 | 0.9975 | 11.8966 s |
| TabPFN | SKIPPED | SKIPPED | SKIPPED | SKIPPED | SKIPPED | SKIPPED | — |

Headline accuracy and macro-F1 are means +/- sample standard deviations over
five fits, seeds 0–4, on the same chronological holdout. Majority class and
persistence use deterministic predictions, so they are shown without spread.
Logistic regression and gradient boosting also returned identical headline
metrics across these seeds; their measured sd is zero, not an assumed value.
These spreads describe seed variability, not confidence intervals or variability
across future weather periods.

The moderate-recall and decision/safety columns, confusion matrix, and per-class
tables below describe **seed 0 only**, because the runner retains `runs[0]` for
these diagnostics. We retain that diagnostic rather than averaging confusion
counts: it describes one actual fitted model, and remains directly auditable
against the artifact. Fit time is a five-seed mean.

The fitted base-feature serving artifacts `lgbm_gono.pkl` and
`ensemble_gono.pkl` are **seed 4**, the last seed saved by the loop, rather than
an average of five fitted models. The base seed 4 files were preserved before
the compact comparison and restored afterward. `auto` prefers the fitted
ensemble when available; a keyless clone without these ignored local files
still falls back to the heuristic. The headline mean is not a measurement of
the single serving model. The reproduction commands run compact first and adopted base last, so the
base seed 4 files serve requests after reproduction.

The ensemble has the highest mean accuracy and macro-F1. Its mean +/- sd
intervals do not overlap any other model's on either metric. No fitted base
model pair overlaps on either metric. LightGBM ranks above gradient boosting on accuracy, while gradient
boosting ranks above LightGBM on macro-F1.
This is a descriptive comparison, not a significance test.

### Non-discrimination of safety metrics

Neither `skip_as_go` nor `decision acc` demonstrates air-quality forecast safety or discriminates a good model from a catastrophic one:
* **`skip_as_go` (0.0) cannot discriminate a good model from a catastrophic one**: `skip_as_go_rate` is 0.0 for every model, including majority class and catastrophic baselines (a model that blindly predicts `good` achieves 0.0; a model that blindly predicts `hazardous` also achieves 0.0). A non-zero value is structurally unreachable on this holdout: all 24 true-SKIP hours are triggered by rain (22) or heat (2) and zero by air quality. Because the evaluation harness feeds identical weather features to both truth and prediction, `apply_band_policy` returns SKIP for all 24 true-SKIP rows regardless of predicted band, making false-GO impossible. It measures weather-rule pass-through, not model air-quality safety.
* **`decision acc` (~0.9975–0.9982) cannot discriminate genuine models from catastrophic always-good**: 99.82% of holdout rows (1,623 of 1,626) have target bands in {good, satisfactory, moderate}, all of which map to the identical weather-determined policy decision. An always-good catastrophic model achieves **0.9982** decision accuracy (1623/1626)—higher than the tuned consensus ensemble (**0.9975**)—and the majority baseline also achieves **0.9982**. The metric does discriminate extreme over-cautious models (always-hazardous drops to **0.0148**, always-poor drops to **0.1593**), but cannot discriminate among real models (range 0.9969–0.9982) or catch unsafe under-prediction.

## Official compact comparison (17)

Artifact: [gono_20261007T145410+0530.json](raw/gono_20261007T145410+0530.json), same split, five seeds (0–4), models and thresholds.
Features: `naqi`, `pm25`, `pm10`, `temp_c`, `precip_mm`, `humidity`, `wind_kmh`, `is_day`, `month`, `vpd`, `stagnation`, `pm_ratio`, `naqi_gap`, `hour_sin`, `hour_cos`, `month_sin`, `month_cos`.
Derived columns use `baahar.features.compact_features_from_row` in eval and serving.

| model | accuracy | macro-F1 | moderate recall | skip_as_go | n(SKIP) | decision acc | fit time |
|---|---|---|---|---|---|---|---|
| majority class | 0.4047 | 0.1441 | 0.0000 | 0.0 | 24 | 0.9982 | 0.0 s |
| persistence | 0.3647 | 0.2492 | 0.2746 | 0.0 | 24 | 0.9982 | 0.0 s |
| logistic regression | 0.7970 +/- 0.0000 | 0.4644 +/- 0.0000 | 0.1268 | 0.0 | 24 | 0.9982 | 0.786 s |
| random forest | 0.8314 +/- 0.0031 | 0.5844 +/- 0.0035 | 0.5423 | 0.0 | 24 | 0.9982 | 2.0012 s |
| gradient boosting | 0.8223 +/- 0.0000 | 0.5879 +/- 0.0000 | 0.6338 | 0.0 | 24 | 0.9975 | 7.893 s |
| lightgbm | 0.8267 +/- 0.0027 | 0.5823 +/- 0.0026 | 0.5352 | 0.0 | 24 | 0.9982 | 3.3246 s |
| consensus ensemble | 0.8188 +/- 0.0008 | 0.5944 +/- 0.0011 | 0.7817 | 0.0 | 24 | 0.9982 | 11.72 s |
| TabPFN | SKIPPED | SKIPPED | SKIPPED | SKIPPED | SKIPPED | SKIPPED | — |

The compact seed 0 moderate-recall result reproduces officially:
78.17%. This diagnostic is not a five-seed mean.
We retain 13 features: ensemble accuracy 0.8483 +/- 0.0005 versus
0.8188 +/- 0.0008, and macro-F1 0.6079 +/- 0.0006
versus 0.5944 +/- 0.0011. Neither metric's mean +/- sd intervals overlap
between the base and compact ensemble. Compact seed 0 moderate recall
(0.7817 versus 0.6831) remains higher.
Selection used this holdout; the five-seed comparison is not independent
validation of the feature choice.

Within the compact comparison, random forest has the highest mean accuracy,
and the ensemble has the highest mean macro-F1. Accuracy intervals overlap
for random forest / LightGBM, so that accuracy ordering is unresolved by this
spread. Macro-F1 intervals overlap for random forest / gradient boosting and
random forest / LightGBM. The compact ensemble's macro-F1 interval does not
overlap other models. These are descriptive intervals, not significance tests.

TabPFN is **SKIPPED** in both five-seed runs: no `TABPFN_TOKEN`; no licence bypass.
Earlier TabPFN runs used different NAQI semantics and do not establish current
performance. The old single-seed TabPFN-versus-classical margin **still has no
spread**: classical seed variability cannot supply missing TabPFN variability.

### Safety limits and metric falsification

`skip_as_go_rate = 0.0` on 24 true SKIP hours,
Wilson 95% interval [0.0, 0.138]. Every SKIP came from weather:

| cause | hours |
|---|---|
| rain | 22 |
| heat | 2 |
| **air (Severe or worse)** | **0** |

This measures rain and heat handling, **not air-quality safety**. No target
`severe` or `hazardous` rows exist in the holdout; neither band is validated.
Macro-F1 averages only supported classes. `poor` has 3 target rows.
The harness applies hour-t weather to predicted future bands because target-hour
weather is not stored separately; raw results disclose this approximation.

#### Catastrophic baseline measurements (`tests/test_eval_falsification.py`)

A falsification suite evaluates deliberately broken models against the exact same metrics code and holdout slice:

| model | decision acc | skip_as_go | can discriminate? | note |
|---|---|---|---|---|
| **always-good** (catastrophic) | 0.9982 | 0.0 | **NO** | Outscores best model on decision acc; blind to all pollution |
| **majority class** (satisfactory) | 0.9982 | 0.0 | **NO** | Identical decision acc to always-good; ignores weather-air interactions |
| **consensus ensemble** (best real) | 0.9975 | 0.0 | — | Actual tuned serving model |
| **always-poor** (catastrophic) | 0.1593 | 0.0 | YES (cautious) | Forces non-SKIP hours to WAIT; skip_as_go still 0.0 |
| **always-hazardous** (catastrophic) | 0.0148 | 0.0 | YES (cautious) | Forces all 1,626 hours to SKIP; skip_as_go still 0.0 |

`skip_as_go` is 0.0 across all models without exception, because true SKIP hours are 100% weather-driven and weather inputs are identical for truth and prediction. `decision acc` discriminates over-cautious models (0.0148 vs 0.9975), but fails to discriminate unsafe under-cautious models (0.9982 vs 0.9975).

### Confusion matrix — gradient boosting

Rows are true bands; columns are predicted bands.

| true / predicted | good | satisfactory | moderate | poor | severe | hazardous |
|---|---|---|---|---|---|---|
| **good** | 754 | 68 | 1 | 0 | 0 | 0 |
| **satisfactory** | 112 | 531 | 15 | 0 | 0 | 0 |
| **moderate** | 1 | 63 | 78 | 0 | 0 | 0 |
| **poor** | 0 | 0 | 3 | 0 | 0 | 0 |
| **severe** | 0 | 0 | 0 | 0 | 0 | 0 |
| **hazardous** | 0 | 0 | 0 | 0 | 0 | 0 |

## Per-class, gradient boosting

| band | precision | recall | F1 | support |
|---|---|---|---|---|
| good | 0.8697 | 0.9162 | 0.8923 | 823 |
| satisfactory | 0.8021 | 0.8070 | 0.8045 | 658 |
| moderate | 0.8041 | 0.5493 | 0.6527 | 142 |
| poor | 0.0000 | 0.0000 | 0.0000 | 3 |
| severe | — | — | — | 0 |
| hazardous | — | — | — | 0 |

## Per-class, consensus ensemble

| band | precision | recall | F1 | support |
|---|---|---|---|---|
| good | 0.8778 | 0.9162 | 0.8966 | 823 |
| satisfactory | 0.8266 | 0.8040 | 0.8151 | 658 |
| moderate | 0.7698 | 0.6831 | 0.7239 | 142 |
| poor | 0.0000 | 0.0000 | 0.0000 | 3 |
| severe | — | — | — | 0 |
| hazardous | — | — | — | 0 |

## Per-class, lightgbm

| band | precision | recall | F1 | support |
|---|---|---|---|---|
| good | 0.8819 | 0.9162 | 0.8987 | 823 |
| satisfactory | 0.7985 | 0.8313 | 0.8146 | 658 |
| moderate | 0.8235 | 0.4930 | 0.6167 | 142 |
| poor | 0.0000 | 0.0000 | 0.0000 | 3 |
| severe | — | — | — | 0 |
| hazardous | — | — | — | 0 |

---

# B · Briefings

**Run:** 2026-10-06 05:01 IST (generation) → 05:09 IST (re-judged, see failure 9)
**Artifact:** [`raw/briefing_20261006T050909+0530.json`](raw/briefing_20261006T050909+0530.json)
**Judge:** `gemini-3.5-flash-lite` — *not* a Gemma model, so Gemma is not
grading its own homework. `gemini-2.5-flash` was tried first and its per-model
free-tier quota was exhausted (HTTP 429); the harness probes a candidate list and
records which model actually judged.
**Cases:** 36, stratified 12 / 12 / 12 across GO / WAIT / SKIP, sampled from real
archived Bengaluru conditions rather than invented.

## Two scoring layers

**Machine checks** — reproducible, no judge. **Blind rubric** — five subjective
dimensions, 0–2 each, one briefing per judge call, anonymised and shuffled so the
judge cannot compare two outputs in the same context.

## Machine checks, 36 cases each

| check | template | gemma |
|---|---|---|
| length ≤ 120 words | **1.000** | **1.000** |
| mean words | 51.0 | 44.3 |
| longest output | 70 | 70 |
| hallucinated park | **0.000** | **0.000** |
| safety caveat present | **1.000** | **1.000** |
| cites the NAQI figure | **1.000** | **1.000** |
| forbidden terms (fall colours, medical claims) | **0.000** | **0.000** |
| SKIP tone correct (n=12) | 0.833 | 0.833 |
| GO tone correct (n=12) | 1.000 | 1.000 |
| latency p50 | **3 ms** | 51,730 ms |
| latency p95 | **6 ms** | 115,187 ms |

Zero hallucinated parks and zero forbidden terms across 72 briefings. Both
writers also pass every safety-requirement check on every case, which is the
post-generation safety pass doing its job — the model is not trusted to comply.

## Why the aggregate rates below are misleading

| | template | gemma |
|---|---|---|
| names the given park (aggregate) | 0.722 | 0.639 |
| — on GO cases (n=12) | **1.000** | 0.833 |
| — on WAIT cases (n=12) | **1.000** | 0.750 |
| — on SKIP cases (n=12) | 0.167 | 0.333 |

A briefing that correctly tells someone to **stay in** does not need to name a
park or give a time window. Pooling those cases makes the template writer look
like it forgot the park name 28% of the time when it named it in **100%** of the
cases where naming a park is the right thing to do. The harness now reports every
rate per decision for exactly this reason.

## Blind rubric (out of 10)

| | template | gemma |
|---|---|---|
| GO (n=12) | 10.00 | 10.00 |
| WAIT (n=12) | 9.67 | 9.67 |
| SKIP (n=12) | **9.83** | 8.92 |
| all cases | **9.83** | 9.53 |

The harness runs a `rubric_health` check that refuses to publish a rubric score
if every decision received a single identical score — the signature of a judge
reading the label instead of the writing. See failure 9 for how that check earned
its place.

### The honest reading: the template writer won

The deterministic local writer **scored higher than Gemma (9.83 vs 9.53)**, was
more consistent about naming the specified park (100% vs 83% on GO cases), and
was about **17,000× faster** (3 ms vs 51.7 s at p50).

That is why Baahar ships the template writer as the default and treats the model
as an optional upgrade. It is not the outcome I expected when I wrote the eval,
and the eval is what changed the product.

Two caveats so this is not over-read:

- **The rubric is saturated.** Scores run 8.92–10.00 across 72 briefings, so it
  distinguishes a broken briefing from a good one and does almost nothing to
  rank good briefings against each other. A 0.3-point gap between two writers is
  well inside that noise. Treat the rubric as a *safety net*, not a leaderboard.
- **The p95 of 115 s is the real cost.** On the Gemini free tier, open-weight
  Gemma 4 emits a long reasoning trace that `thinkingConfig.thinkingBudget`
  cannot disable (the API returns *"Thinking budget is not supported for this
  model"*), so the trace is paid for in output tokens. Measured traces: 2.2k
  characters for `gemma-4-31b-it`, 5.7k for `gemma-4-26b-a4b-it`. A user who
  asked "can I go for a walk?" will not wait a minute and a half for a paragraph.

---

# C · Failures worth reading

A benchmark with no failures listed was not looked at.

### 1. The model shipped its own instructions as the briefing

Gemma 4 returns a reasoning part marked `"thought": true` **before** the answer.
The response parser read `parts[0]`, so the first version of the product greeted
users with a verbatim restatement of my system prompt, including the numbered
rules.

Caught by reading the output, not by any test. Fixed by skipping parts where
`thought` is truthy; pinned by `test_brief.py::TestGeminiResponseParsing`.

### 2. The safety caveat deleted itself

`enforce_safety` stripped medical hedging, then appended a disclaimer containing
the phrase *"informational, not medical advice"*. The hedging filter targets the
word `medical`. Same function call: appended, then deleted.

Fixed by reordering — hedging is stripped **before** the caveat is appended.

### 3. The blind judge scored everything 0 and looked legitimate

The rubric's JSON example used a placeholder `id` on the line immediately above a
paragraph beginning with the word `BANNED`. The judge copied the id from the
wrong line and returned a confident **0** for all five dimensions.

This is the most dangerous kind of eval bug: a result of zero looks like a
finding. It was noticed only because the template writer — which passes every
machine check — scored 0. Real template score: **9.5/10, sd 0.53**.

### 4. A park name duplicated itself

Grounding the banned token `"Lalbagh"` in a briefing for *Lalbagh Botanical
Garden* produced *"Lalbagh Botanical Garden Botanical Garden"*. The fix skips any
banned name that is a substring of the chosen park.

### 5. The loading spinner never went away

An author `display: grid` rule outranks the browser's `[hidden] { display: none }`,
so the spinner stayed painted underneath the finished brief. Found by screenshotting
the UI instead of trusting that it worked. `scripts/ui_check.mjs` now fails the
build on this class of bug.

### 6. Word-budget truncation cut a park name in half

An early `_strip_to_words` truncated at an arbitrary index, so a 124-word answer
became `... Head to Cub`. Now it cuts on a sentence boundary and only falls back
to a hard word cut if that would discard more than half the budget.

### 7. I invented an API endpoint

Tinker's documentation was unreachable from the build environment, and
`brief.py` contained `https://api.tinker.ai/v1/sampling/generate` — a URL I had
guessed and never called.

Shipping it would have been worse than shipping nothing: it would 404 in front of
a judge, make the repo *look* as though it had a Tinker integration that had
never run, and contradict the honesty rule governing every other number in this
document. It is now an empty configuration value that refuses loudly.

**This cost the Tinker prize category, and it was the right trade.** See
[`../docs/adr/001-tinker-outcome.md`](../docs/adr/001-tinker-outcome.md).

### 9. The rubric was scoring the decision label, not the writing

The first complete briefing run reported **3.43/10 for the template writer** and
3.33/10 for Gemma — near-identical, both terrible, and *both* far below the 10/10
the same writer had scored on an earlier 8-case GO-only smoke test.

The cause was in my own rubric prompt:

> *"A briefing that recommends going outside when the CONDITIONS line says the
> decision is BAD must score 0 on every dimension."*

The judge took that as "any non-GO decision scores 0", so the results came back
perfectly bimodal:

| decision | template | gemma |
|---|---|---|
| GO (n=12) | 10, 10, 10, 10, … | 10, 10, 10, 10, … |
| WAIT (n=12) | 0 × 12 | 0 × 12 |
| SKIP (n=12) | 0 × 12 | 0 × 12 |

Every GO case scored exactly 10. Every non-GO case scored exactly 0. **The rubric
was reporting the decision label.** The briefing for a SKIP case — *"Stay in
today. 3.4 mm rain in the hour. Air is NAQI 95 (satisfactory). No walk worth the
trouble"* — is well written and was scored 0/10.

Two fixes, both permanent:

1. The rubric now says to grade the **writing**, and states that a briefing
   saying "stay in" is *well written and should score normally*; only a briefing
   that encourages a walk in bad conditions scores 0. A sensory cue is not
   applicable to a "stay in" briefing and counts as a pass.
2. `rubric_health()` fails the harness when every decision receives a single
   identical score with a large spread between decisions — the exact signature
   of this bug. It reports `ok: scores vary within decisions` on the fixed run.

Re-judging the *same 72 briefings* with the corrected rubric moved the template
writer from **3.43 → 9.83** and Gemma from **3.33 → 9.53**, with variation
*within* each decision, which is what a working rubric looks like.

`--rescore` was added for this: regenerating 36 Gemma briefings costs ~30
minutes, and the texts do not change when the rubric does.

This is the third time the eval harness caught itself rather than the product.
The first two were a truncation bug that shipped `"Head to Cub"` and a judge that
returned confident zeros. Both looked like findings.

### 10. Two metrics were diluted by design, not by failure

The safety metrics apply the policy using **hour-*t*** precipitation and
temperature rather than hour-*t+6*, because the dataset does not store the target
hour's weather separately. For a +6h horizon that can misattribute a rain-driven
SKIP. This is recorded in every raw artifact as
`_policy_approximation` rather than quietly corrected.

### 11. The hour table excluded the hour it was recommending

The single most user-visible bug in this project, and it was invisible to every
test because every test asserted the wrong thing.

`build_plan` populated the plan with `scores[:window_hours]` — the first 12 hours
from now. At 13:00 with a 24-hour window those run 13:00 → midnight, while the
best hour was **07:00 the next morning**. So the briefing said *"Go at 07:00"* and
every row of the table beside it read `WAIT` or `SKIP`. The table appeared to
contradict the advice it was meant to justify.

Nothing was wrong with the data, the scorer, or the headline. The bug was purely
one of slicing: "show the next N hours" and "show the hour we are recommending"
are not the same request, and the first was implemented where the second was
meant.

`display_window()` now anchors on the recommendation. If the best hour is already
inside the window, behaviour is unchanged; otherwise the window shifts to end just
after it, keeping lead-in context so the reader can see the hour is better rather
than take it on faith. `tests/test_score.py::TestDisplayWindow` asserts the
property for every position 0–23, that the cap holds, that no invented hours
appear, and — end to end through `build_plan` — that a plan never omits its own
recommendation.

### 12. A station reading 1,727 km away looked entirely plausible

With a WAQI token configured, a query for Bengaluru (`geo:12.9716;77.5946/`)
returned *Dr. Karni Singh Shooting Range, Delhi* at `28.499727, 77.267095` with a
perfectly reasonable AQI of 89 and a well-formed payload. Nothing about it looked
broken — no error field, no nulls, no missing coordinates. It would have put a
Delhi air-quality number on a Bengaluru screen, labelled as a local cross-check,
next to a park name.

`stations.py` now computes the haversine distance and discards anything beyond
`MAX_STATION_KM = 60`. The reading is also deleted rather than shown with a
caveat, because 60 km of "nearby" that turns out to be 1,727 km is not a caveat
anyone reads. The distance is included in the payload for the readings that
survive, so a judge can check the claim rather than take it.

60 km is deliberately generous: it covers the whole city plus a wide margin, so a
Bengaluru park with no station of its own still gets its cross-check. The guard
exists to catch a different city, not to demand a sensor in the park. Absent
coordinates are not a rejection — no distance check is possible, so the reading
stands.

`tests/test_stations.py` covers this with the real response shape, plus the
payload-shape bug found alongside it: WAQI returns `city` as an object for the
geo feed and as a list for some other feeds, and the original code only read the
object form, so the station name silently vanished on one of them.

### 14. The published model could not be the one the product used

The most consequential bug in this project, and it was invisible from the eval's
own side. The accuracy table was always internally consistent — the numbers were
real, measured on a real holdout. What was false was the claim that they
described the shipped pipeline.

**The eval and the app used different feature sets.** `scripts/run_eval.py`
declared its own 13 columns from the archive row shape:

```
naqi, pm25, pm10, temp_c, apparent_c, precip_mm, precip_prob,
humidity, wind_kmh, uv_index, is_day, hour, month
```

`baahar/features.py` independently defined 15 for the live path, substituting
derived encodings:

```
naqi, pm25, pm10, naqi_band_ordinal, temp_c, apparent_c, heat_index_flag,
precip_mm, precip_prob, humidity, wind_kmh, uv_index, is_day, hour_sin, hour_cos
```

So `run_eval.py` fitted a 13-column model, saved it to
`eval/artifacts/tabpfn_gono.pkl`, and `score_tabpfn` then handed it a 15-column
matrix. It raised `X has 13 features, but TabPFNClassifier is expecting 15`
*inside* `predict_proba`, `score_slots` caught it, and every hour silently fell
back to the heuristic. Meanwhile `baahar brief` printed a reassuring note about
the heuristic and nothing else. The 840 MB artifact sat in `eval/artifacts/`
looking authoritative.

Three separate things had to be true for this to be invisible, and each was
individually reasonable:

1. **The feature failure was silent.** It degraded to the documented policy,
   which is the correct behaviour for a missing model — and indistinguishable
   from a fitted one that failed. `score_tabpfn` now compares `n_features_in_`
   against `len(FEATURE_NAMES)` and raises a `ValueError` naming both counts and
   refusing to reorder. A mismatch is a contract violation, not something to pad
   around: the values would silently mean something else.
2. **`load_tabpfn_model()` only looked where `.env` pointed.** With
   `TABPFN_MODEL_PATH` unset it returned `None`, so `choose_scorer("auto")` never
   saw the artifact that `save_tabpfn_model` had written to
   `eval/artifacts/`. Both sides now name `DEFAULT_TABPFN_ARTIFACT`. "Writer and
   reader must agree on the path" is now a test.
3. **The eval redeclared the column list.** `FEATURE_COLUMNS` in `run_eval.py`
   was a second copy of a contract, which is how the two drifted. It now does
   `list(TABPFN_FEATURE_ORDER)` and a test asserts that line is still there.

**The eval was re-run after the fix** — the cited artifact is
`gono_20261006T151017+0530.json`, and every number in § A is unchanged
(0.8512 / 0.6040). The features were already equivalent in what they expressed;
`hour` + `month` and `hour_sin` + `hour_cos` carry the same information. So no
accuracy moved, which is the reassuring outcome — but it was a coincidence, not a
guarantee, and I could not have known that without re-running.

**Verified after the fix:** `baahar brief` reports `scorer=tabpfn`, every hour
carries the `tabpfn` tag, `degraded` is empty, and a NAQI-488 hour still returns
SKIP with the policy's reasons intact. The safety asymmetry is now exercised
against the real fitted model rather than a stub.

The lesson is narrow and worth stating: *an eval that measures a pipeline the
product does not run is a benchmark, not a result.* The numbers were never wrong.
The sentence "the app scores with the exact model this table reports" was.

A related fix fell out of it. `build_plan` defaults to `scorer="auto"`, so once a
fitted artifact existed the offline test suite started behaving differently on a
machine that had run the eval than in CI — same code, different decisions, and two
test failures that meant nothing. `tests/conftest.py` now pins
`TABPFN_MODEL_PATH` to a path that cannot exist, so the suite is deterministic
regardless of local state. The TabPFN tests ask for it explicitly.

### 15. The seasonal cue shipped as four lines of statistics

Not an eval bug, but it belongs here because it is the failure mode the whole
project is built against, caught by looking at a screenshot.

The first version of the species cue put the record count, the radius and the
source into the instruction itself:

> look for a Chocolate Pansy near Bengaluru — researchers have logged around a
> dozen within 5 km this month

The unit tests passed. Every honesty rule was satisfied: it did not promise a
sighting, it named the evidence, it stated the radius. But
`docs/media/03b-pocket-seasonal.png` showed it rendering **four lines tall** with a
footnote in the middle of a screen whose entire purpose is that you should be
looking at a tree. The information was honest and the screen was still wrong.

Fixing it meant splitting `SeasonalCue` into two fields — `text` for the
instruction, `evidence` for the provenance — and then encoding the design rule as
a test: the instruction must stay under 45 characters and must not contain a
digit or the string "km". A reviewer reading only the tests can now see the
constraint that a reviewer looking at a screenshot would otherwise have to notice.

Two more bugs in the same feature, both found by the tests rather than by reading
the code:

* The seasonal cues were **unreachable**. `alternate_cues()` truncated to the first
  two cues, and the pool put three hand-written cues first, so the shuffle button
  could never land on a species. The API now returns the whole remainder, and
  `scripts/ui_check.mjs` clicks the button until the seasonal cue is on screen and
  asserts it got there.
* The provenance line was **one global sentence**, so the number it showed did not
  necessarily belong to the species above it. It is now a per-cue mapping, keyed by
  cue text, because "around a dozen" is a different claim from "several".

The headless UI check now asserts the credit line is **absent** under a hand-written
cue and **present** under a data-backed one. Attributing a data source to a line
the author wrote by hand is the same error as overclaiming a sighting, just quieter.

---

# D · What was not measured

Stated so the gaps are visible rather than inferred.

| Not measured | Why |
|---|---|
| `severe` / `hazardous` band accuracy | Zero such hours in the holdout. Not testable with this split. This is the gap that matters most. |
| `poor` band accuracy | 3 examples. F1 = 0.0 is not a meaningful signal. |
| Air-quality-driven SKIP safety | Every SKIP in the holdout was rain or heat. `skip_as_go_rate` does not test polluted-day safety. |
| Whether TabPFN beats gradient boosting | TabPFN was SKIPPED in the five-seed runs. Its old single-seed margin has no spread and used different NAQI semantics; it is not variance-backed or a current comparison. |
| TabPFN's behaviour on the bands that matter | `severe` / `hazardous` / `poor` are unvalidated for TabPFN too, for the same reason as every other model here. |
| Fine-tuned vs baseline briefings | Tinker API unverifiable; endpoint deliberately not invented. |
| Field test | Not performed. No human has walked with Baahar. Not fabricated. |
| Independent temporal validation | Five-seed variability on one holdout is now measured; variation across independent holdout periods is not. Feature selection used this same holdout. |
| Rubric discrimination | Scores run 8.92–10.00 across 72 briefings. The rubric catches a broken briefing and does almost nothing to rank good ones. |
| Voice output quality | **Not assessed.** The client is implemented and tested against fixtures. A live call with real credentials returns HTTP 402 `paid_plan_required`: free ElevenLabs accounts cannot call library voices over the API at all. The credentials are valid and the endpoint answers - the free plan is simply not permitted to. No audio was generated or assessed, and no plan was upgraded, because `AGENTS.md` forbids a card wall. See `docs/NEEDS_HUMAN.md` §4. |
| Whether a seasonal cue led to a sighting | The cue wording and its provenance are tested; whether it changed what anyone looked at is not measured, because no human has walked with the app. Same answer as the field test: unknown, and not guessed at. |
| Seasonal cue accuracy | No metric yet. There is no ground truth for "did this person see it", and inventing one from n=0 walks would be a number with no denominator. The tested properties are wording, radius anchoring, and suppression under unsafe conditions. The journal now records the sighting answer (`Entry.species_seen`) and reports a rate at three walks, with a small-denominator caveat. **n=0 so far** — the field test has not happened. |
| A deployed end-to-end latency figure | `/api/brief` with the Gemma writer is 51.7 s p50 / 115.2 s p95 (measured, 36 calls); the template writer is 3 ms / 6 ms. A *hosted* p95 is **SKIPPED** — nothing is deployed. |
| Whether any of this changed behaviour | Only a human can say whether a briefing got someone outside. That is the field test, and it has not happened. |
