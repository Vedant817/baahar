# Baahar eval results

**Rule zero: if it was not run, it is not published.** Partial results marked
`SKIPPED` beat fake completeness. Every number below came from a real
execution and can be traced to a machine-readable file in [`raw/`](raw/).

---

## Run metadata

| | |
|---|---|
| Dataset built | 2026-10-06 IST, 8,130 hourly rows |
| Tabular run | 2026-10-06 03:53 IST → refreshed 04:34 IST with the SKIP-cause breakdown |
| Location | Bengaluru, 12.9716 N, 77.5946 E |
| Keys present at run time | Gemma ✅ · Tinker ❌ · TabPFN ❌ · ElevenLabs ❌ · WAQI ❌ |
| Python | 3.14.0 |
| numpy / scikit-learn / tabpfn / torch | 2.5.3 / 1.9.1 / 9.1.0 / 2.14.1 |
| Raw artifacts | [`raw/gono_*.json`](raw/) · [`raw/briefing_*.json`](raw/) |

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
| **gradient boosting** | **0.8395** | **0.5897** | **0.0** | **24** | 0.9975 | 12.3 s |
| TabPFN | **SKIPPED** — see below | | | | | |

Standard deviation across seeds is reported per run in `raw/`; at `--repeat 1`
it is `null`, which is honest rather than a fabricated ±0.

### Reading that table honestly

**Gradient boosting wins.** TabPFN did not run, so there is no number for it and
none is invented.

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

Per-class, gradient boosting:

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

### Baseline framing

`persistence` is not a strawman. Air quality is persistent, so predicting the
current band six hours out is a real meteorological baseline, and it beats the
majority class by 7 points of accuracy. Any claim that a model "understands air
quality" should be measured against persistence, not against chance.

---

## TabPFN: `SKIPPED`

```
tabpfn  SKIPPED -- tabpfn refuses to download weights until a Prior Labs licence
        acceptance is recorded in TABPFN_TOKEN, even though the weights are
        public on Hugging Face. We do not bypass a licence gate.
        See docs/NEEDS_HUMAN.md for the 3 steps.
```

Verified on 2026-10-06: `Prior-Labs/TabPFN-v2-clf` reports `gated=False` via the
Hugging Face API and is downloadable anonymously. `tabpfn==9.1.0` nevertheless
calls `ensure_license_accepted()` before fetching weights and requires
`TABPFN_TOKEN` from a Prior Labs account. That is a licence gate, not a
technical or access limit, so it was not patched around.

The code path is implemented and tested; it degrades to the documented policy with
a reason rather than a traceback. To produce the number:
<https://github.com/Vedant817/baahar/blob/main/docs/NEEDS_HUMAN.md>

---

# B · Briefings

<!-- BRIEFING-EVAL -->

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

### 8. `apply_band_policy` was fed the wrong hour's weather

The safety metrics apply the policy using **hour-*t*** precipitation and
temperature rather than hour-*t+6*, because the dataset does not store the target
hour's weather separately. For a +6h horizon that can misattribute a rain-driven
SKIP. This is recorded in every raw artifact as
`_policy_approximation` rather than quietly corrected.

---

# D · What was not measured

Stated so the gaps are visible rather than inferred.

| Not measured | Why |
|---|---|
| `severe` / `hazardous` band accuracy | Zero such hours in the holdout. Not testable with this split. |
| `poor` band accuracy | 3 examples. F1 = 0.0 is not a meaningful signal. |
| Air-quality-driven SKIP safety | Every SKIP in the holdout was rain or heat. `skip_as_go_rate` does not test polluted-day safety. |
| TabPFN | Licence gate. See above. |
| Fine-tuned vs baseline briefings | Tinker API unverifiable; endpoint deliberately not invented. |
| Field test | Not performed. No human has walked with Baahar. Not fabricated. |
| Multi-seed variance | Runs used `--repeat 1`; per-run values are in `raw/`, sd is `null`. |
| A deployed end-to-end latency figure | `/api/brief` with the Gemma writer is 40–95 s (measured); the template writer is 3 ms. A hosted p95 is **SKIPPED** — nothing is deployed. |