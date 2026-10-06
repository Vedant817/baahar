# Baahar eval results

**Rule zero: if it was not run, it is not published.** Partial results marked
`SKIPPED` beat fake completeness. Every number below came from a real
execution and can be traced to a machine-readable file in [`raw/`](raw/).

---

## Run metadata

| | |
|---|---|
| Dataset built | 2026-10-06 IST, 8,130 hourly rows |
| Tabular run | 2026-10-06 03:53 IST → refreshed 04:34 with the SKIP-cause breakdown → **12:56 IST with TabPFN included** |
| Briefing run | 2026-10-06 05:09 IST (36 cases × 2 writers, unchanged by the TabPFN run) |
| Location | Bengaluru, 12.9716 N, 77.5946 E |
| Keys present at tabular run | Gemma ✅ · TabPFN ✅ · WAQI ✅ · Tinker ✅ · ElevenLabs ✅ |
| Keys present at briefing run | Gemma ✅ · Tinker ❌ · TabPFN ❌ · ElevenLabs ❌ · WAQI ❌ |
| Device | CPU only. No GPU was used or available. |
| Python | 3.14.0 |
| numpy / scikit-learn / tabpfn / torch | 2.5.3 / 1.9.1 / 9.1.0 / 2.14.1 |
| Raw artifacts | [`raw/gono_*.json`](raw/) · [`raw/briefing_*.json`](raw/) |

The two runs above have different key sets on purpose and the numbers are not
mixed: **§ B is from the 05:09 briefing run**, § A is from the **12:56 tabular
run**. Each raw artifact records its own `keys_present` and `versions` block, and
`scripts/check_results.py` reads the newest artifact of each kind rather than
assuming they came from the same invocation.

### Reproduce

```bash
uv run python scripts/build_dataset.py --start 2025-11-01 --end 2026-10-05
uv run python scripts/run_eval.py
uv run python scripts/build_briefing_cases.py
uv run python scripts/run_briefing_eval.py --writers template,gemma --no-cache
```

---

# A · Go / no-go

## The task, and why it is not circular

The obvious version of this experiment is meaningless: define labels with a
rule, train a model to reproduce that rule, and report the accuracy as though
the model had discovered something. Baahar does not do that.

The task is a genuine **next-step prediction**:

> Given what was known at hour *t* — current air quality, current weather, hour
> of day, month — predict the **CPCB NAQI band six hours ahead**, where the
> target is computed from an independent reading of that future hour.

Three properties make it a real test:

1. **Features are hour-*t* only.** Nothing downstream of the split can see hour
   *t+6*. `scripts/build_dataset.py` asserts the invariant structurally.
2. **The split is chronological.** Last 20% held out. Air quality is strongly
   autocorrelated, so a random shuffle would put neighbouring hours on both
   sides of the boundary and inflate every metric.
3. **GO/WAIT/SKIP is a policy, not the label.** The model predicts a physical
   quantity (an air-quality band). `apply_band_policy` then maps the predicted
   band to a decision, which keeps the safety rule as readable, reviewed code
   instead of something a model has to approximate.

## Data

| | |
|---|---|
| Rows | 8,130 hourly |
| Window | 2025-11-01 → 2026-10-05 |
| Air quality | Open-Meteo CAMS archive (keyless) — `pm2_5`, `pm10`, NO2, O3, SO2, CO |
| Weather | Open-Meteo ERA5 archive (keyless) — temp, apparent temp, precipitation, precipitation probability, humidity, wind, UV |
| NAQI | CPCB 2014 sub-index breakpoints; overall = worst sub-index |
| Features (13) | `naqi`, `pm25`, `pm10`, `temp_c`, `apparent_c`, `precip_mm`, `precip_prob`, `humidity`, `wind_kmh`, `uv_index`, `is_day`, `hour`, `month` |
| Classes | 6 CPCB bands: good, satisfactory, moderate, poor, severe, hazardous |

**The window deliberately includes winter.** A June–October window produced only
**33 SKIP hours**, which makes the safety metric meaningless. Winter adds the
genuinely bad-air days.

### Class distribution, and an uncomfortable asymmetry

| Band | Train (6,504) | Holdout (1,626) |
|---|---|---|
| good | 1,052 | 829 |
| satisfactory | 3,218 | 652 |
| moderate | 1,950 | 142 |
| poor | 271 | **3** |
| severe | 13 | **0** |
| hazardous | 0 | **0** |

The last three rows are the important ones. **The holdout contains no Severe or
Hazardous hours at all, and only 3 Poor hours.** So:

- macro-F1 is averaged over the four classes with support, not six. The harness
  reports the zero-support classes explicitly (`absent_from_holdout`) rather
  than quietly dividing by fewer.
- **Bands `severe` and `hazardous` are not validated by this run at all.** Any
  claim about them would be fiction.

## Results

Holdout: **1,626 rows**, 2026-07-30T00:00 → 2026-10-05T17:00.

| model | accuracy | macro-F1 | skip_as_go | n(SKIP) | decision acc | fit time |
|---|---|---|---|---|---|---|
| majority class | 0.4047 | 0.1441 | 0.0 | 24 | 0.9982 | <0.1 s |
| persistence (band at *t*) | 0.4760 | 0.3106 | 0.0 | 24 | 0.9982 | <0.1 s |
| logistic regression | 0.7306 | 0.4845 | 0.0 | 24 | 0.9969 | 3.4 s |
| random forest (300) | 0.8272 | 0.5685 | 0.0 | 24 | 0.9982 | 2.4 s |
| gradient boosting | 0.8395 | 0.5897 | 0.0 | 24 | 0.9975 | 9.2 s |
| **TabPFN 9.1.0 (cpu)** | **0.8512** | **0.6040** | **0.0** | **24** | **0.9982** | 339.0 s |

Standard deviation across seeds is reported per run in `raw/`; at `--repeat 1`
it is `null`, which is honest rather than a fabricated ±0.

### Reading that table honestly

**TabPFN wins, by a small margin.** 0.8512 against 0.8395 for gradient boosting,
and 0.6040 against 0.5897 macro-F1 — about +0.012 and +0.014. On 1,626 holdout
rows that is roughly 20 rows different. With `--repeat 1` and no seed variance
recorded, **this gap is not statistically meaningful and is not claimed to be.**
TabPFN is reported as the best model in this table because it has the highest
number, not because the evidence establishes that it is a better model than
gradient boosting on this data.

It is also 37× slower to fit (339 s against 9.2 s). The prize category asks
whether TabPFN was used, and it was — genuinely, on a real holdout, with the
real weights. Whether that is the right *engineering* choice for a product that
answers one question in under two seconds is a different question, and the honest
answer is that gradient boosting is very likely the better choice here.

### TabPFN: how it actually ran

Two gates had to be lifted, and neither is a licence or correctness condition:

1. **The licence.** `TABPFN_TOKEN` is set. Without it `tabpfn>=2.x` refuses to
   download weights even though `Prior-Labs/TabPFN-v2-clf` is public and reports
   `gated=False`. That is a licence acceptance tied to a Prior Labs account, and
   Baahar does not route around it — the human accepted it. See
   `docs/NEEDS_HUMAN.md` § 1.
2. **The CPU size guard.** TabPFN refuses to fit more than ~5,000 rows on CPU by
   default, and offers `TABPFN_ALLOW_CPU_LARGE_DATASET=1`, a GPU, or the hosted
   API as the alternatives. Measured here: 6,504 rows fit in 1.6 s and 1,626
   predictions take 312 s, so the whole eval is about five and a half minutes.

The second gate cost an hour of confusion worth recording: setting the environment
variable *after* importing `tabpfn` does nothing, because the guard reads a
pydantic settings object that snapshots its values at import time. The failure mode
is indistinguishable from the guard not existing — the same `SKIPPED` message, the
same exit. `score.py` and `scripts/run_eval.py` now set it before the import, with
a comment saying why, because the next person to hit this will otherwise assume
the feature is unavailable.

**`skip_as_go_rate = 0.0` is a much weaker result than it looks**, and the
harness now says so explicitly. Breaking down *why* each of the 24 true-SKIP
hours was a SKIP:

| cause | hours |
|---|---|
| rain | 22 |
| heat | 2 |
| **air (Severe or worse)** | **0** |

So this metric is measuring **rain and heat handling**, not air-quality safety.
Not one of the 24 SKIPs was caused by pollution. A model could achieve 0.0 here
while being completely unable to recognise a polluted day — and with zero
Severe hours in the holdout, **that possibility is not excluded by this
evaluation at all.**

This is the single most important limitation in this document.

### Why `skip_as_go` is 0.0 even for the majority baseline

Because the decision rule is *hard*. `apply_band_policy` returns SKIP only when
the band is Severe-or-worse, or apparent temperature ≥ 35 °C, or precipitation
≥ 2.5 mm/h, or rain probability ≥ 70%. If none of those hold, the answer is GO or
WAIT regardless of which band was predicted. So the majority-class model — which
predicts a single band for every hour — still gets every SKIP decision right.

That is not a modelling triumph. It means **the band classification is where the
real difficulty is**, and the accuracy and macro-F1 columns are the numbers that
actually separate the models.

### Confusion matrix — gradient boosting

Rows are the true band, columns the predicted band.

| true \ predicted | good | satisfactory | moderate | poor | severe | hazardous |
|---|---|---|---|---|---|---|
| **good** | 750 | 69 | 4 | 0 | 0 | 0 |
| **satisfactory** | 110 | 536 | 12 | 0 | 0 | 0 |
| **moderate** | 2 | 60 | 79 | 0 | 1 | 0 |
| **poor** | 0 | 0 | 3 | 0 | 0 | 0 |
| **severe** | 0 | 0 | 0 | 0 | 0 | 0 |
| **hazardous** | 0 | 0 | 0 | 0 | 0 | 0 |

Two things worth naming:

- **`poor` F1 = 0.0 on n=3.** The model never predicts `poor`. With three
  examples, that is not a finding about the model; it is a statement about the
  holdout window.
- **`moderate` recall 0.556** is where the errors live. 60 of 142 moderate hours
  were called `satisfactory`. That direction is *lenient*: it under-warns. It is
  the error class worth watching, and it is not caught by `skip_as_go_rate` at all.

### Baseline framing

`persistence` is not a strawman. Air quality is persistent, so predicting the
current band six hours out is a real meteorological baseline, and it beats the
majority class by 7 points of accuracy. Any claim that a model "understands air
quality" should be measured against persistence, not against chance.

---

## Per-class, gradient boosting

| band | precision | recall | F1 | support |
|---|---|---|---|---|
| good | 0.8701 | 0.9113 | 0.8902 | 823 |
| satisfactory | 0.8060 | 0.8146 | 0.8103 | 658 |
| moderate | 0.8061 | 0.5563 | 0.6583 | 142 |
| poor | 0.0 | 0.0 | 0.0 | **3** |
| severe | — | — | — | **0** |
| hazardous | — | — | — | **0** |

Two things worth naming:

- **`poor` F1 = 0.0 on n=3.** The model never predicts `poor`. With three
  examples, that is not a finding about the model; it is a statement about the
  holdout window.
- **`moderate` recall 0.556** is where the errors live. 60 of 142 moderate hours
  were called `satisfactory`. That direction is *lenient*: it under-warns. It is
  the error class worth watching, and it is not caught by `skip_as_go_rate` at all.

## Per-class, TabPFN 9.1.0 (cpu)

| band | precision | recall | F1 | support |
|---|---|---|---|---|
| good | 0.8909 | 0.9028 | 0.8968 | 823 |
| satisfactory | 0.8029 | 0.8480 | 0.8248 | 658 |
| moderate | 0.8557 | 0.5845 | 0.6946 | 142 |
| poor | 0.0 | 0.0 | 0.0 | **3** |
| severe | — | — | — | **0** |
| hazardous | — | — | — | **0** |

Compared with gradient boosting, TabPFN's gain comes from exactly one place:
`moderate` recall, 0.5845 against 0.5563. That is the same error class, mildly
reduced. It does not fix `poor`, and it cannot touch `severe` or `hazardous`
because there are no such rows in the holdout to be right or wrong about.

It also produces a decision confusion matrix identical to the majority baseline's
(`[[1367,0,0],[3,232,0],[0,0,24]]`, decision accuracy 0.9982). Gradient boosting
made one GO-into-SKIP mistake; TabPFN made none. On 24 SKIP hours that difference
is one row, and it is not worth reading as a safety property.

The honest summary: **TabPFN is the highest number in this table by a margin too
small to defend, on a holdout that cannot test the bands that matter most, at
37× the fit cost.** It is reported because it ran, not because it should be
shipped.

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

### 13. The seasonal cue shipped as four lines of statistics

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
| Whether TabPFN beats gradient boosting | One seed, no variance recorded. The +0.012 accuracy gap is ~20 rows on 1,626 and is not claimed to be significant. |
| TabPFN's behaviour on the bands that matter | `severe` / `hazardous` / `poor` are unvalidated for TabPFN too, for the same reason as every other model here. |
| Fine-tuned vs baseline briefings | Tinker API unverifiable; endpoint deliberately not invented. |
| Field test | Not performed. No human has walked with Baahar. Not fabricated. |
| Multi-seed variance | Tabular runs used `--repeat 1`; per-run values are in `raw/`, sd is `null`. |
| Rubric discrimination | Scores run 8.92–10.00 across 72 briefings. The rubric catches a broken briefing and does almost nothing to rank good ones. |
| Voice output quality | ElevenLabs implemented, never called. No audio was generated or assessed. |
| Whether a seasonal cue led to a sighting | The cue wording and its provenance are tested; whether it changed what anyone looked at is not measured, because no human has walked with the app. Same answer as the field test: unknown, and not guessed at. |
| Seasonal cue accuracy | No metric. There is no ground truth for "did this person see it", and inventing one (a self-reported sighting rate from n=0 walks) would be a number with no denominator. The tested properties are wording, radius anchoring, and suppression under unsafe conditions. |
| A deployed end-to-end latency figure | `/api/brief` with the Gemma writer is 51.7 s p50 / 115.2 s p95 (measured, 36 calls); the template writer is 3 ms / 6 ms. A *hosted* p95 is **SKIPPED** — nothing is deployed. |
| Whether any of this changed behaviour | Only a human can say whether a briefing got someone outside. That is the field test, and it has not happened. |