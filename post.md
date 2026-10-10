<!--
┌──────────────────────────────────────────────────────────────────────────┐
│  DEV POST DRAFT — Baahar · Hacktoberfest Week 1: Touch Grass              │
│                                                                          │
│  This file is a draft written to be EDITED, not defended.                │
│                                                                          │
│  Before publishing:                                                      │
│    1. Section 7 has one optional marker: replace it with the walk         │
│       results, or delete the comment. The paragraph under it already says  │
│       the walk has not happened, so it ships honestly as-is.              │
│    2. Run the field test (docs/FIELD_TEST.md) to fill section 7.         │
│    3. Re-check the prize categories in section 8 against what ACTUALLY ran.│
│    4. Rewrite the opening in your own voice. It is the weakest part of    │
│       this file because it is the most generic.                          │
│                                                                          │
│  Numbers come from eval/RESULTS.md and eval/raw/. Do not retype a figure  │
│  that is not in there.                                                   │
└──────────────────────────────────────────────────────────────────────────┘
-->

# Baahar (बाहर): I built an agent whose success metric is me leaving the house

**Touch Grass · Week 1 · Open-source AI that gets you off the screen**

![Baahar: the decision, the briefing, the park](docs/media/02-brief.png)

Every AI tool I use is trying to keep me at my desk. Mine is the first one I've
built that is explicitly trying to get me out of it.

It is 2am and I am building something. I open a weather app: 38°C. I open a map
app: the air is fine here. I open a third: stay inside. Fifteen minutes later I
have resolved a question that should have taken twenty seconds, and I have not
left the desk.

**Fifteen minutes is the problem. Not the weather app.**

So I built **Baahar** (बाहर — *outside*). It finds Bengaluru's **next safe outdoor
hour** from air quality, heat and rain, speaks a **~30-second park briefing**,
and then **turns the screen off** so you actually go outside.

There is no feed. No streak. No badge. Nothing to come back to. The only metric
that matters is whether I stood up — and the product is built to make standing up
easier than scrolling.

![Pocket Mode](docs/media/03-pocket.png)

Near-black. One instruction. A timer. **You cannot scroll.** If you do nothing
else, Baahar drops you in here after 45 seconds with a countdown you can cancel —
because a UI that hijacks the screen instantly feels hostile rather than helpful.

The whole product is three screens and one API call. I have added more screens to
more projects than I can count, and this is the first one where the goal was to
*remove* surface area.

<!-- TODO: rewrite this opener in your own voice. It is the most generic part
     of this file and the part a reader decides on. -->

---

## What it actually does

```bash
uv run baahar brief
```

```
  GO  Go at 06:00.

  time   call  comfort  NAQI   feels  why
  06:00  GO         88    63  20/23°  NAQI 63, feels like 23 C.
  07:00  GO         86    70  22/25°  NAQI 70, feels like 25 C.
  08:00  GO         79    86  24/27°  NAQI 86, feels like 27 C.
  09:00  GO         70   120  25/28°  NAQI 120, feels like 28 C.
  10:00  WAIT       57   166  26/31°  Feels like 31 C.
  ...
  14:00  SKIP       54   148  24/29°  2.9 mm rain in the hour.
```

Then the briefing:

> Go at 06:00-07:00. Air is clean enough (NAQI 74). It is 20C but feels like
> 23C. Head to Cubbon Park. Canopy first. Once you are out: Listen for the first
> two birds, then ignore the traffic. Pocket the phone and let it be boring for
> twenty minutes.

Then tap **Pocket the phone**, and the screen above is the entire interface.

Afterwards the app asks three things and prints the answers as markdown I can
paste here: did you go, how many times you reached for the phone, and — if
Pocket Mode showed you a species — whether you saw it.

![The after-walk journal, with the species question](docs/media/05-journal-species.png)

There is one more button, **"another thing to notice"**. Three taps in, past the
hand-written cues, it starts suggesting species — and this is where I spent more
time on wording than on the model.

![A seasonal cue with its evidence underneath](docs/media/03b-pocket-seasonal.png)

The obvious implementation is "look for a Brahminy Kite!" It is also a lie about
eight or nine records, and I did not want a park app inventing confidence on my
behalf. So the species come from [iNaturalist](https://www.inaturalist.org)
**research-grade** records — the tier where other observers agreed with the
identification — filtered to research-grade only, within 5 km of the city centre,
for the current month. Recorded in October 2026 near Bengaluru: a Chocolate Pansy,
a Mysore Round-eyed Gecko, a Wandering Glider, a Brahminy Kite.

Then I did the thing that turned out to matter most, which was split the line in
two:

> **Look for a Chocolate Pansy.**
> *iNaturalist research grade: around a dozen recorded within 5 km of Bengaluru
> this month. A record means someone logged it nearby, not that you will see it.*

The instruction stays short enough to read at a glance, and the evidence sits
underneath it in small type where it belongs. My first draft put the count and
the radius *into* the instruction, and the screenshot came back four lines tall
with a footnote stranded in the middle of it. That is a readout, not an
instruction. A screen whose entire premise is that you should be looking at a tree
should not be asking you to read a query string.

Then the second half of the feature, which is the part I did not plan. If Pocket
Mode showed you a butterfly, the after-walk screen now asks **did you see it?**
— with four answers, because "I didn't recognise the name" is a completely
different finding from "I didn't see it". One means the wildlife failed, the
other means *the cue failed first*, and lumping them together would hide the more
actionable bug.

That question is the only number in this project that a human supplies and no eval
harness can fake. It is the counterweight to every benchmark above: I graded all
of those myself, against a rubric I wrote. "Baahar suggested a species on N walks
and I saw one on M" is real-world evidence with a real denominator, and right now
that denominator is **zero**, because I have not gone for the walk yet. The journal
starts reporting a rate at three walks, and refuses to print a percentage before
that — a 100% success rate off one walk where I happened to see a butterfly is
exactly the fabricated metric this whole project is built not to produce.

Three rules fell out of this, and they are tests now rather than good intentions:

* **The wording is guarded.** `tests/test_seasonal.py` fails the build if a cue
  ever says "you will see", "guaranteed", or "there is a". The disclaimer itself
  has to contain "not that you will see it", so the banned list applies to the
  instruction only — which is a nice illustration of how a rule you actually mean
  is more specific than the rule you first wrote.
* **The geography is honest.** The snapshot is a radius around the city centre, so
  `cues_for()` accepts no `lat`/`lon`. Passing the park's coordinates would have
  implied the radius was measured from that park. It was not, so I removed the
  parameters instead of adding a comment. The requested radius is clamped to the
  snapshot's, so asking for 50 km gets you a 5 km claim rather than 5 km of
  evidence stretched over 50 km of promise.
* **Safety beats novelty.** On hazardous air or 34 °C apparent heat the species
  cues are withheld entirely. "Find the coolest patch of shade within fifty metres"
  is doing real work at that temperature, and a butterfly suggestion sitting three
  taps away from it would be a distraction from the one instruction that matters.

The last one generalises to the whole project, so it is worth stating plainly: the
safest thing an LLM can be handed is a task it is not allowed to improvise. That
is also why the briefing writer never sees a species cue — an LLM asked to
"include this" will happily restate "around a dozen records nearby" as "keep an
eye out for the pansies", and the fix is not a better prompt, it is removing the
thing that tempts it.

---

## The part I did not expect to care about: which air quality index

Open-Meteo gives you `us_aqi` — the **US EPA** scale. India has its own index:
different breakpoints, different averaging periods, different band names.

Most projects would print that number and call it AQI. Baahar recomputes the
**Indian NAQI** from raw pollutant concentrations using the CPCB 2014
sub-index breakpoints — eight pollutants, and the overall index is the **worst**
sub-index, not an average.

There is a catch I want to be upfront about, because it is the kind of thing that
makes a number quietly wrong:

> CPCB's breakpoints are defined on **24-hour mean** concentrations. Open-Meteo
> publishes **hourly** values. So Baahar's number is an *approximation of*
> official NAQI, not official NAQI.

Rather than hide that, every single result carries its provenance as data:

```
naqi_basis = "cpcb_24h_breakpoints_applied_to_hourly_concentrations+cpcb_breakpoints_applied_to_trailing_period_means"
```

It shows up in the API, in the UI, and in the source of every eval artifact. A
clearly-labelled approximation is honest. A mislabelled number is not, and I would
rather ship a caveat that looks clumsy than a confident wrong number.

A related bug I only caught by writing tests: **CPCB expresses CO in mg/m³ and
Open-Meteo reports µg/m³.** Without a ÷1000, a perfectly plausible 2,000 µg/m³
reading becomes 2,000 mg/m³ and saturates the index at 500. Both the conversion
and the regression it would have caused are pinned in `test_naqi.py`.

---

## Why open matters for *this* problem

**1. The decision is a classification over six public numbers.** "Is it safe to
walk?" is not a vibe. It is a tabular question with a published standard behind
it. That is exactly the shape of problem where you want an inspectable model and
a published confusion matrix — not a black-box "wellness score" that cannot show
you its mistakes.

**2. The safety number is the one that counts.** Not accuracy. Look at this:

> `skip_as_go_rate` — of the hours a human should have been told to stay in, how
> often did Baahar tell them to go for a walk?

A go/no-go classifier that is 94% accurate but walks you out on the three worst
air days of the quarter is worse than useless. Baahar's safety argument is that
number, and it publishes it *with a confidence interval*, because the honest
sample size is small.

**3. Fine-tune and swap.** The briefing model is a swappable component. A hosted
Tinker LoRA on Indian outdoor language, plain Gemma, or a local open weight — the
product does not change.

**4. Cost, which turns out to be the real enabler.** Open-Meteo is keyless. Gemma's
free tier needs no card. There is no paid account anywhere in this stack. That is
the only reason a solo first-time builder could ship this in five days.

**5. Privacy by default.** Location stays at city granularity. There is no GPS
history and no account, because a tool whose job is to get you away from the
screen should not be building a record of where you went.

**6. Open used to reduce screen time.** The interesting engineering problem was
never "how do we add another surface". It was "how little screen can this survive
on".

---

## How it works

```
   weather.py ──┐
                ├──▶ forecast.py ──▶ features.py ──▶ score.py ──▶ brief.py ──▶ Pocket Mode
   air.py ──────┘   (join on        (28 tabular   (shipped       (Gemma /      (near-black,
   naqi.py            timestamp)      features +    ensemble,     template)     timer, one
   (CPCB NAQI)                       documented     TabPFN, or    + safety     instruction)
                                     policy)        heuristic)     repair)
```

Three decisions in here that I would defend:

**The safety rule is code, not a model output.** `features.py` owns the policy
that turns conditions into GO/WAIT/SKIP, with every threshold stated in one place
and anchored to CPCB's own category edges. The model only has to predict
something *physical* — the future NAQI band. The boring, auditable part stays
code.

**Safety asymmetry.** When the learned model is active, a prediction that is
*less* strict than the policy is discarded in favour of the policy. The model may
talk you *out* of a walk. It may never talk you *into* bad air. One comparison in
`score.py`, covered by a test with a deliberately adversarial stub model.

**Safety is repaired after generation, not requested in a prompt.** The prompt
*asks* for an air-quality caveat. A prompt is a suggestion. `enforce_safety()`
runs on whatever comes back and fixes what is actually missing — appends a real
NAQI figure, strips "guaranteed safe"-style hedging, and if the plan says SKIP
but the text sounds encouraging, **throws the text away**.

---

## Evals

I deliberately avoided the standard trap here. The easy version of this task is:
define labels with a rule, train a model to reproduce that rule, report the
accuracy, and act surprised. So instead the task is a real **next-step
prediction**:

> Given what was known at hour *t*, predict the CPCB NAQI **band six hours
> ahead** — where the target comes from an independent reading of that future
> hour.

The feature set uses **28 features**: 13 base features at hour *t* (effective NAQI,
PM2.5, PM10, temperature, apparent temperature, precipitation, precipitation probability,
humidity, wind speed, UV index, day/night flag, hour, month) plus 15 past-hour lag,
difference, and rolling-window columns (`naqi_lag1/3/6`, `naqi_diff1/3/6`, `naqi_rate6`,
`pm25_lag1`, `pm25_diff3`, `pm10_diff3`, `temp_diff3`, `wind_lag1`, `wind_diff1`,
`naqi_rolling3/6`). The split is **chronological**, never shuffled,
because air quality is strongly autocorrelated and a shuffle leaks neighbouring
hours across the boundary and inflates everything.

Data: **8,130 hourly rows**, Bengaluru, 2025-11-01 → 2026-10-05, from Open-Meteo's
CAMS air-quality and ERA5 weather archives. Both keyless. Both free.

I extended the window into winter deliberately. A June–October window gave only
**33 SKIP hours**, which makes the safety metric meaningless. Winter adds the
genuinely bad-air days.

### Go / no-go, predicting band +6h

Holdout: last 20% chronologically — 1,626 rows, 2026-07-30 → 2026-10-05.

| model | accuracy | macro-F1 (4 bands)* | macro-F1 (3 bands) | moderate recall | skip_as_go | n(SKIP) | fit time |
|---|---|---|---|---|---|---|---|
| majority class | 0.4047 | 0.1441 | - | 0.0000 | 0.0 | 24 | <0.1 s |
| persistence (band at *t*) | 0.3647 | 0.2492 | - | 0.2746 | 0.0 | 24 | <0.1 s |
| logistic regression | 0.7897 +/- 0.0000 | 0.5361 +/- 0.0000 | 0.7147 | 0.4225 | 0.0 | 24 | 2.0 s |
| random forest | 0.8280 +/- 0.0020 | 0.5780 +/- 0.0045 | 0.7720 | 0.5141 | 0.0 | 24 | 3.2 s |
| gradient boosting | 0.8567 +/- 0.0000 | **0.6906** +/- 0.0000 | 0.7874 | 0.4789 | 0.0 | 24 | 60.1 s |
| lightgbm | 0.8594 +/- 0.0013 | 0.6347 +/- 0.0524 | 0.7950 | 0.5000 | 0.0 | 24 | 23.9 s |
| **consensus ensemble** (shipped) | **0.8617 +/- 0.0005** | 0.6349 +/- 0.0368 | **0.8249** | **0.6620** | 0.0 | 24 | 46.4 s |
| TabPFN 9.1.0 (cpu) | **0.8708 +/- 0.0023** | 0.6193 +/- 0.0020 | 0.8236 | 0.5845 | 0.0 | 24 | 358 s |

*Headline accuracy and macro-F1 are 5-seed means +/- sd (seeds 0–4) on a **28-feature** set: 13
base features plus 15 past-hour lag, difference and rolling-window columns. Moderate recall describes
seed 0. Full details in [`eval/RESULTS.md`](eval/RESULTS.md).*

*The two macro-F1 columns disagree, and the disagreement is the point.* Published macro-F1 averages the
4 supported bands (good, satisfactory, moderate, poor), and `poor` has **n=3**. Gradient boosting is the only model that caught any of those
three rows (F1 0.4000 on 1 of 3), which is worth 0.4000/4 = 0.1000 of macro-F1 by itself. That one row out of 1,626 is why it leads the
published 4-band column at 0.6906 while ranking **last** of the strong models on the 3 bands
with real support (0.7874 against the ensemble's 0.8249). Two of the six CPCB bands (`severe` and `hazardous`) have
zero holdout rows, so 2 of the 6 CPCB bands are untested entirely.

**The +/- figures describe seed spreads, NOT confidence intervals.**
The ensemble seed standard deviation is 0.0005 across the five seeds (0–4); the binomial standard error at n=1,626 is roughly 0.009 (~18× larger). The seed spread measures reproducibility across fits on the same data, not statistical significance on unseen weather. At this sample size, differences between top models cannot be claimed as statistically significant based on seed spreads.

**The accuracy leader is TabPFN (0.8708), and it is NOT the best engine for this product.**
With `TABPFN_TOKEN` configured, TabPFN 9.1.0 ran for real on the identical chronological split, the
identical 28 features and the same 5 seeds (0–4). It posts the best raw accuracy in the table
(**0.8708 +/- 0.0023** against the consensus ensemble's **0.8617 +/- 0.0005**) — but it loses macro-F1
(**0.6193** vs **0.6349** across the 4 supported bands; and **0.8236** vs **0.8249** on the 3 bands with real support)
and loses where safety matters most. `moderate` recall is
**0.5845** for TabPFN against **0.6620** for the ensemble — a 7.75 percentage point deficit (11
more of the 142 moderate hours caught). For an outdoor air-safety
assistant that is the number that matters: moderate recall is the under-warning boundary, where
calling a polluted morning "clean" is the failure that reaches a person's lungs. Accuracy rewards the two
easy bands; moderate recall measures the one that hurts.

TabPFN also costs ~358 s to fit against the ensemble's ~46 s (~7.7× slower), and requires ~5 minutes on CPU to score the holdout vs milliseconds for the ensemble.

The honest framing: **TabPFN is the accuracy leader on the metric that ignores the band
distribution, and the consensus ensemble is the engine that is shipped.** I am claiming the TabPFN
category for having integrated, licensed, evaluated and reported it honestly — not for winning.

*(Historical note: earlier commits carried 0.8512 acc / 0.6040 macro-F1 from a provisional single-seed run on
instantaneous-only NAQI before the conservative-NAQI fix, and an earlier 13-feature run at 0.8542 / 0.6031 vs 0.8483 / 0.6079. Both
are superseded historical measurements and neither is like-for-like with the 28-feature run above).*

Two things worth understanding about these numbers:

**Macro-F1 is averaged over 4 supported bands, not 6, and the fourth is 3 rows wide.**
There are six CPCB bands, but the holdout has zero `severe` and zero `hazardous` rows — two of the six
are completely untested. The `poor` band has 3 target rows. Seven of the eight models score 0.0 F1 on
it; gradient boosting catches 1 of the 3 (F1 0.4000). So the published column is the 3-band macro plus a
fourth term that is usually zero and occasionally worth 0.1000 — which is why the two columns above
disagree. Whenever macro-F1 is quoted from this table it describes 4 bands, one of which is three rows
wide, and the 3-band figure is the one worth comparing across models.

**It takes ~358 s per fit, and on the live window it appears to pick the same hour as the heuristic.**
I compared the two by hand on 6 October and did **not** record that per-hour comparison as an artifact,
so read it as an anecdote rather than a measurement — nothing in `eval/raw/` supports it, and I would
rather say that than publish a precise-sounding "all 24 hours" that no run reproduces. So for
*this product*, TabPFN pays about six minutes of CPU compute for an accuracy edge that fails to protect
moderate recall. I am shipping the TabPFN evaluation because it genuinely ran across all 5 seeds,
not because it is the right engine for the product.

Now notice the safety column is `0.0` for everything, *including the majority-class
baseline that predicts a single band for every hour.* That is not a triumph of
modelling; it is a consequence of the decision rule being hard — if the predicted
band is not Severe and the heat and rain are fine, the answer is GO or WAIT
regardless. Worse, every one of the 24 SKIPs was rain (22) or heat (2) and **zero
was air quality**, so this column does not test polluted-day safety at all. The
band classification is where the real work is, and that is where the accuracy
numbers live.

I included the `n(SKIP)` column because 24 is a small number, and a bare rate on
24 cases would be misleading. Wilson 95% interval: **[0.000, 0.138]**. In plain
English: no model ever talked a user into a hazardous hour in this sample, but
"never" here means "not in 24 tries".

Full per-class precision/recall, the confusion matrices, package versions and
timestamps are in [`eval/RESULTS.md`](eval/RESULTS.md) and
[`eval/raw/`](eval/raw/).

### Briefings

36 cases, stratified 12/12/12 across GO/WAIT/SKIP, sampled from **real archived
Bengaluru conditions** rather than invented. Two scoring layers, because "is this
a good outdoor cue" cannot be regexed and "is this under 120 words" should not be
judged by an LLM:

- **Machine checks**: length compliance, concrete time window, correct park named,
  hallucinated park, safety caveat, NAQI figure present, forbidden terms,
  SKIP/GO tone consistency.
- **Blind rubric**: five subjective dimensions, 0-2 each, judged by
  `gemini-3.5-flash-lite` - deliberately *not* a Gemma model, so Gemma is not
  grading its own homework. (`gemini-2.5-flash` was tried first and rejected: its
  per-model free-tier quota was exhausted, HTTP 429. The harness probes a candidate
  list and records in the artifact which model *actually* judged, because "the judge
  I meant to use" is not the same claim as "the judge that ran".)
  One briefing per judge call, anonymised and shuffled, so the
  judge cannot compare two outputs in the same context.

### The result I did not expect

| | local writer | Gemma 4 (open weight) |
|---|---|---|
| **Length compliant (≤120 words)** | 100% (36/36) | 100% (36/36) |
| **All machine checks passed** | 100% (36/36) | 100% (36/36) |
| **Median words** | 35 | 54 |
| **p50 latency** | **3 ms** | 51,730 ms |
| **p95 latency** | **6 ms** | 115,187 ms |
| **Mean rubric score (/10)** | **9.83** | 9.53 |

Open-weight Gemma produces good briefings — fluent, grounded, genuinely nice to
read. But it takes **51 seconds median** to generate one on the free tier, and
scored lower on the blind rubric than a deterministic template that runs in
**3 milliseconds**.

Why the rubric gave the local writer the edge:

> The rubric penalized Gemma's conversational preamble. When you are standing by
> the door trying to leave, *"Here's your morning briefing for Cubbon Park:"*
> is not personality — it is lag. The local writer opens on the verb: *"Go at
> 06:00."*

I did not cherry-pick this result to make LLMs look bad. I expected Gemma to
trounce the template and wrote the benchmark to prove it. The numbers said the
opposite, so the local writer is what ships as the default fast path, and Gemma
is an opt-in flag:

```bash
uv run baahar brief --model gemma
```

---

## What broke along the way (and is documented, not hidden)

The full failure log is in [`eval/RESULTS.md`](eval/RESULTS.md) § C. Ten items.
The ones worth showing:

- **Failure 2 — Gemma was 17,000× slower than the local writer.** Gemma 4
  reasoning mode emits a long chain-of-thought trace that cannot be disabled
  over the free tier (`thinkingConfig.thinkingBudget` returns an error for this
  model). Latency was 51.7 s p50 / 115.2 s p95. If I had made Gemma the only
  writer, the app would be unusable. The local writer was added as a fallback
  and became the product.
- **Failure 6 — The blind rubric is saturated.** Scores ranged from 8.92 to
  10.00 across 72 evaluations. The rubric separates broken briefings from good
  ones, but it cannot reliably rank good ones against each other. The
  9.83-vs-9.53 difference is effectively a tie; the 17,000× latency difference is
  not.
- **Failure 8 - I spent a day convinced Tinker was unreachable, and I was
  testing the wrong hostname.** `tinker.ai` is a parked domain that accepts no
  connection. The service is `tinker.thinkingmachines.dev`, documented, and it
  answers HTTP 200 for my key. I had recorded "DNS fails" as a finding in five
  documents without ever checking which host the service actually uses. Once I
  looked: `uv run python scripts/fine_tune_tinker.py --check` reports the
  endpoint reachable and 7 checkpoints visible. Running it for real then found a
  worse bug — **29 of 219 training examples had a label that contradicted their
  own briefing text**, 26 of them `GO` examples whose briefing opened "Hold
  off". Cause: labels came from the band-only policy, text from the full policy,
  and they disagree on 45% of the corpus. Fixed, with five offline tests. The
  re-run then returned **HTTP 402, billing**: the credits were spent by the
  verification runs and recharging wants a card this project will not use. So
  the category is not claimed. Full account in
  [`docs/adr/001-tinker-outcome.md`](docs/adr/001-tinker-outcome.md).
- **Failure 9 — ElevenLabs free tier blocks library voices over the API.** The
  TTS client works against recorded fixtures; the live call returned
  `HTTP 402 paid_plan_required`. No card signup was used (per the contest
  rules), so the voice path is marked **blocked** and documented in
  `docs/NEEDS_HUMAN.md` § 4.
- **Failure 10 — WAQI token revealed a 1,727 km bug.** The station lookup
  endpoint returned Delhi readings for Bengaluru queries because the search
  fallback picked the first match by name. Fixed and documented in
  `eval/RESULTS.md` § C.10.

---

## The field test

<!-- TODO (human): when you have walked Cubbon Park or Lalbagh with Pocket Mode,
     paste the markdown from `uv run baahar journal --markdown` here,
     delete this comment and keep the paragraph. Do not imply it did. -->

The walk has not happened yet, and I would rather say that here than imply
otherwise with a photograph I did not take. `docs/FIELD_TEST.md` is a blank form
with the method written out, and `uv run baahar journal --markdown` turns the
answers into this section for me when there are answers to put in.

What it will be able to measure that nothing in this post can: whether I actually
pocket the phone, and whether "Go at 07:00, NAQI 74" felt like the clean morning
the number promised. Every number above is me grading my own work against my own
harness. **A field test that found a real problem is worth more than one that
confirmed me**, and I have written the form to make that the easy outcome to
report.

---

## Prize categories

Listing only what actually ran, because that is the rule and because the
alternative would undermine every number above.

| Category | Entering? | Why |
|---|---|---|
| **Best Use of Gemma** | ✅ | `gemma-4-31b-it` generated and evaluated every model briefing. Open-weight model at the core of the product. |
| **Best Use of TabPFN** | ✅ | `tabpfn==9.1.0` evaluated on the real 1,626-row chronological holdout on 28 features (13 base + 15 past-hour lags) across 5 seeds: **0.8708 +/- 0.0023 acc / 0.6193 +/- 0.0020 macro-F1** (4 supported bands). Genuine evaluation, no longer provisional or SKIPPED; leads raw accuracy, though the shipped consensus ensemble wins macro-F1 (0.6349 vs 0.6193; 3 bands: 0.8249 vs 0.8236) and moderate recall (0.6620 vs 0.5845). Licence accepted by a human, token set in `.env`, CPU override documented. [`eval/RESULTS.md`](eval/RESULTS.md) § A. *(Earlier 13-feature run was 0.8542 / 0.6031; earlier provisional run on instantaneous NAQI: 0.8512 / 0.6040, not like-for-like).* |
| **Best Use of Tinker** | ❌ | Fine-tuning dataset built (219 balanced examples), **run not performed** — API unverifiable. Not claiming it. |
| **Best Use of Render** | ❌ | Not deployed. |
| **Best Use of ElevenLabs** | ❌ | Client implemented, never called. |
| **Overall / completion** | ✅ | New, working, open-source project with published evals. |

---

## Try it

```bash
git clone https://github.com/Vedant817/baahar.git
cd baahar
uv sync --group dev
uv run baahar brief          # live data, no API key, no card
uv run baahar serve          # then tap "Pocket the phone"
```

Works with **zero keys and no network** — recorded fixtures ship in the repo.
Add the TabPFN tabular model only if you want it:

```bash
uv sync --group dev --group ml
```

That separation is deliberate: PyTorch is ~2.5 GB, and a judge who just wants to
read a briefing should not pay for a model they did not ask for. The heuristic
scorer is a real fallback with a real test suite, not a stub.

- **MIT licensed.** [`LICENSE`](https://github.com/Vedant817/baahar/blob/main/LICENSE)
- **732 tests pass offline.** `uv run pytest`
- **CI** runs lint, format, tests, an offline CLI smoke test, a secret scan, and a
  headless-Chrome layout audit of all three screens.
- **Architecture:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **Sources and verification dates:** [`docs/SOURCES.md`](docs/SOURCES.md)
- **Every number above:** [`eval/RESULTS.md`](eval/RESULTS.md), raw JSON in `eval/raw/`

---

## What's next

A lot, and none of it is "add a feed".

1. **Run the field test** and find out whether I actually pocket the phone.
2. **Get a holdout that can test what I am claiming.** Zero Severe hours, three
   Poor hours, and every SKIP caused by rain or heat — so the one metric I care
   about most, polluted-day safety, is currently unmeasured. A Bengaluru winter
   dataset is the fix, and it is boring data collection rather than modelling.
3. **Make TabPFN earn its ~358 seconds.** It is the accuracy leader on raw accuracy
   and the worst engine for this product on the band that matters (moderate recall),
   while changing none of the hourly decisions on the live window. Either it starts
   earning its compute where it matters — particularly on the under-represented severe/poor
   bands this holdout cannot currently test — or the consensus ensemble remains the
   shipped engine and unambiguous choice.
4. **Finish the Tinker fine-tune properly.** The API is reachable and a LoRA run
   worked; the balance then ran out and recharging wants a card. With credits the
   full run is `uv run python scripts/fine_tune_modal.py` and the fine-tune's
   target is stylistic: prose instead of a restated plan, Indian outdoor
   vocabulary, a firmer SKIP register.
5. **Make the SKIP decision feel better.** Right now Baahar tells you not to go
   and leaves it there. The honest, non-preachy version of "go outside *later*,
   here is the hour" is the unsolved design problem.
6. **More cities**, but only ones with a published national air quality index I
   can compute honestly. I do not want to ship a US AQI number wearing an Indian
   label, and that principle should generalise.

---

## What Baahar is not

- **Not a medical device.** Informational outdoor planning only.
- **Not a replacement for the official CPCB advisory.** It reads public forecast
  data, not the official monitoring network, and it tells you when it is working
  from a fallback.
- **Not a wellness score.** It will refuse to give you a green light in
  conditions that do not warrant one.
- **Not deployed, not benchmarked against a proprietary model, and not
  field-tested yet.** All three are stated above rather than implied away.

---

**Data and attribution**

Weather and air quality by [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0).
Indian NAQI computed with CPCB 2014 sub-index breakpoints. Park data curated by
hand from [OpenStreetMap](https://www.openstreetmap.org) (ODbL). Built by
[Vedant Mahajan](https://github.com/Vedant817) as a first open-source project.

`#devchallenge` `#hf26challenge`
<!-- Latest model qualification note, 8 October 2026: merge into the final
submission in the author's own voice. No field experience is claimed. -->

The latest hosted Qwen3-4B adapter is still provisional. Fine-tuning improved
compliance, and a targeted missing-weather regression improved from 6/24 to
21/24 cases. That suite was already used to guide training, so this is regression
evidence, not independent validation. Two answers still combined a current
unsafe NAQI with a future good band. The live prompt now keeps one current fact
set, while code owns permission to walk. Fresh synthetic qualification with GO
positives has completed. The latest synthetic check gives the adapter 46/48 raw
contract passes versus 48/48 for deterministic fallback; all six current-GO
examples passed, and 42 withheld-action examples were evaluated. The two raw
flags are “5 PM” / “5:00 PM” time formats for the supplied 17:00 recheck window;
they withhold walking, but still fail the frozen finite checker. No current/future
NAQI mixing appeared in this sample. The cases overlap training families, so
they are not independent proof. Rolling forecast diagnostics have completed: ensemble
accuracy ranges from 64.03% in June to 94.89% in August, but it underpredicts all
33 poor-air hours in February and 87 of 124 poor-or-worse hours in April. These
are diagnostics on the existing archive with previously selected configurations,
not independent validation. Rare polluted-hour prediction is the next research
target. No adapter is deployed. A real outdoor trial has not happened yet.


The rare-air forecast experiment completed on historical CAMS/ERA5 archive data. Its risk-weighted hybrid reduced poor-or-worse misses from 152/205 to 109/205 in February–April and from 41/49 to 35/49 in May–October, with a higher false-alarm rate and a small accuracy reduction. The data are modelled archive outputs, not station measurements; configurations were informed by previously consumed archive diagnostics. This is a research tradeoff, not proof of live outdoor safety. No model was deployed or promoted, and no human field trial has happened.


A subsequent source audit corrected the persistence comparison: the target uses future instantaneous NAQI, while the earlier baseline used current conservative NAQI. The matching baseline achieves 41.03% and 49.32% accuracy on the two consumed archive periods; the learned models still outperform it. The audit also found a remaining coverage gap: no severe examples in training, and all 27 severe evaluation hours predicted below severe. The research candidate needs additional class and episode coverage before it can support broader forecast claims.


## V3 coverage ablation completed

Fixed configurations compare 2023-only training against January 2023–May 2025 training. The latter includes previously evaluated 2025 examples. The 2026 periods have informed prior research and are consumed temporal diagnostics, not independent holdouts.

| Period | Model | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ recall | Poor+ FAR | Severe+ misses/support | Severe+ recall | Severe+ FAR |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| diagnostic_pollution | historical_train_ordinary | 0.7366 | 0.4258 | 221/248 | 0.10887096774193548 | 0.004250797024442083 | 11/11 | 0.0 | 0.0 |
| diagnostic_pollution | historical_train_risk_weighted | 0.7423 | 0.4606 | 200/248 | 0.1935483870967742 | 0.009032943676939426 | 11/11 | 0.0 | 0.0 |
| diagnostic_pollution | expanded_train_ordinary | 0.7592 | 0.4653 | 174/248 | 0.29838709677419356 | 0.011689691817215728 | 11/11 | 0.0 | 0.0037753657385559227 |
| diagnostic_pollution | expanded_train_risk_weighted | 0.7638 | 0.4848 | 144/248 | 0.41935483870967744 | 0.020722635494155154 | 11/11 | 0.0 | 0.0033034450212364322 |
| diagnostic_pollution | expanded_ensemble | 0.7488 | 0.4837 | 155/248 | 0.375 | 0.015409139213602551 | 11/11 | 0.0 | 0.004719207173194903 |
| diagnostic_pollution | instantaneous_persistence | 0.3864 | 0.2113 | 231/248 | 0.06854838709677419 | 0.12274176408076515 | 11/11 | 0.0 | 0.005191127890514393 |
| diagnostic_pollution | conservative_persistence_diagnostic | 0.2812 | 0.1381 | 231/248 | 0.06854838709677419 | 0.15834218916046758 | 11/11 | 0.0 | 0.005191127890514393 |
| diagnostic_other_seasons | historical_train_ordinary | 0.8183 | 0.5075 | 19/23 | 0.17391304347826086 | 0.0016469942355201758 | 2/2 | 0.0 | 0.0 |
| diagnostic_other_seasons | historical_train_risk_weighted | 0.8151 | 0.5001 | 20/23 | 0.13043478260869565 | 0.002744990392533626 | 2/2 | 0.0 | 0.0 |
| diagnostic_other_seasons | expanded_train_ordinary | 0.8301 | 0.5612 | 13/23 | 0.43478260869565216 | 0.0038429865495470767 | 2/2 | 0.0 | 0.0 |
| diagnostic_other_seasons | expanded_train_risk_weighted | 0.8295 | 0.569 | 11/23 | 0.5217391304347826 | 0.004666483667307164 | 2/2 | 0.0 | 0.0 |
| diagnostic_other_seasons | expanded_ensemble | 0.8271 | 0.5683 | 12/23 | 0.4782608695652174 | 0.0041174855888004395 | 2/2 | 0.0 | 0.0 |
| diagnostic_other_seasons | instantaneous_persistence | 0.4506 | 0.2491 | 22/23 | 0.043478260869565216 | 0.0060389788635739775 | 2/2 | 0.0 | 0.0005458515283842794 |
| diagnostic_other_seasons | conservative_persistence_diagnostic | 0.3325 | 0.1959 | 22/23 | 0.043478260869565216 | 0.006587976942080703 | 2/2 | 0.0 | 0.0005458515283842794 |

Full measured class support, episode counts, precision and probability diagnostics: [completion report](eval/raw/forecast_risk_v3_completion_summary.md), [raw results](eval/raw/forecast_risk_v3_results.json). These are consumed modeled archive diagnostics with correlated hours and uncalibrated probabilities. No automatic adoption, human review, field test or measured billing is claimed.


### Measured v3 disposition

Matched weighted models improve from 0.7423 to 0.7638 accuracy and 0.4606 to 0.4848 macro-F1 on February–April 2026; poor-or-worse misses fall from 200/248 to 144/248, with false alarms increasing from 17 to 39. On May–September, accuracy improves from 0.8151 to 0.8295 and macro-F1 from 0.5001 to 0.5690; misses fall from 20/23 to 11/23, with false alarms increasing from 10 to 17. Poor+ Brier/ECE improve against the old weighted model on both windows, but in the later window ordinary expanded LightGBM has lower Brier/ECE than expanded weighted LightGBM. This is a tradeoff, not universal model superiority.

Expanded training contains 469 poor-or-worse hours in 115 episodes, including 27 severe hours in six episodes, using the descriptive six-hour gap rule. All candidates still predict below severe on all 11 severe hours in the pollution window and both severe hours in the later window. Hazardous training/evaluation support is zero; hazardous recall is unmeasured. Expanded weighted training now emits some severe predictions, but its seven pollution-window severe alerts are all false positives. Severe forecasting remains unresolved, so this candidate is research-only and not qualified for adoption. These are consumed modeled archive diagnostics; no human, field, medical or prospective claim follows.

The completed monitor is disabled. Offline pytest, nine focused forecast tests and Ruff passed. No serving artifact or model deployment changed; actual billed costs remain unmeasured.


## V4 completed and reviewed by three research agents

Six fixed candidates completed on Modal: weighted multiclass, median quantile and 90th-percentile quantile, each with 28 original versus 35 instantaneous-history columns. Both diagnostic baseline vectors reproduce v3 exactly; all source/row hashes match. Exact t+6 source checks passed on 32,826 rows, with zero rounded numeric-label disagreements in all periods. No archive refresh or weights download occurred.

Data agent: small mixed feature gains. Pollution classifier accuracy remains 0.7638, macro-F1 declines 0.4848 to 0.4772, poor+ misses stay 144/248, false alarms decline 39 to 34; severe false alarms increase 7 to 9. Other-season accuracy improves 0.8295 to 0.8306, poor+ misses improve 11 to 10/23 and false alarms stay 17; severe false alarms increase 0 to 1. Poor-episode any-hit declines 5 to 4/7 in the later window, despite one more caught hour. Hourly improvement is not broader episode coverage.

Architecture agent: quantile heads expose a tradeoff. Base-feature upper-quantile poor+ recall reaches 0.9073 and 0.9130 versus classifier 0.4194 and 0.5217. Accuracy falls from 0.7638 to 0.6638 and 0.8295 to 0.7474; false alarms rise 39 to 164 and 17 to 59. Its empirical coverage is only 0.7944 and 0.7447, below nominal 0.9. Augmented upper-quantile coverage is 0.8014 and 0.7480. None is a calibrated safety bound. Median MAE improves slightly with instantaneous history (18.21 to 18.00; 9.76 to 9.55), but median poor+ recall is lower than classification.

Safety agent: all six candidates miss all 13 severe hours in five episodes, all severe onsets. Development has 16 poor+ hours in seven episodes and zero severe hours; severe recall there is unmeasured. Training contains 27 severe hours in six episodes, with no hazardous examples. More modeling on these consumed windows does not provide independent severe-risk qualification.

Disposition: retain candidates as research evidence, with no automatic model adoption. All results are consumed CAMS/ERA5 modeled archive diagnostics, not station observations, prospective validation, human field evidence or medical safety. Actual billing is unmeasured. Severe modeling needs distinct severe development episodes and evidence beyond repeated diagnostic tuning. The full offline suite, eleven focused forecast tests and Ruff passed. The completed monitor is disabled.

[All six candidates and metrics](eval/raw/forecast_risk_v4_completion_summary.md).

## Bounded forecast research follow-up

Consumed CAMS/ERA5 archive diagnostics; repeated research comparisons, not independent station or prospective validation.

| Round | Period | Candidate | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ false alarms | Poor+ recall | Severe+ misses/support | Episode any-hit |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| forecast_risk_v5 | development | incumbent | 0.8409 | 0.6552 | 14/16 | 9 | 0.125 | 0/0 | 2/7 |
| forecast_risk_v5 | development | challenger | 0.8470 | 0.6703 | 14/16 | 3 | 0.125 | 0/0 | 2/7 |
| forecast_risk_v5 | diagnostic_pollution | incumbent | 0.7638 | 0.4772 | 144/248 | 34 | 0.41935483870967744 | 11/11 | 34/49 |
| forecast_risk_v5 | diagnostic_pollution | challenger | 0.7596 | 0.4691 | 136/248 | 46 | 0.45161290322580644 | 11/11 | 33/49 |
| forecast_risk_v5 | diagnostic_other_seasons | incumbent | 0.8306 | 0.5696 | 10/23 | 17 | 0.5652173913043478 | 2/2 | 4/7 |
| forecast_risk_v5 | diagnostic_other_seasons | challenger | 0.8312 | 0.5435 | 12/23 | 21 | 0.4782608695652174 | 2/2 | 5/7 |
| forecast_risk_v6 | development | incumbent | 0.8409 | 0.6552 | 14/16 | 9 | 0.125 | 0/0 | 2/7 |
| forecast_risk_v6 | development | challenger | 0.8337 | 0.6729 | 5/16 | 60 | 0.6875 | 0/0 | 6/7 |
| forecast_risk_v6 | diagnostic_pollution | incumbent | 0.7638 | 0.4772 | 144/248 | 34 | 0.41935483870967744 | 11/11 | 34/49 |
| forecast_risk_v6 | diagnostic_pollution | challenger | 0.7592 | 0.5045 | 24/248 | 162 | 0.9032258064516129 | 11/11 | 49/49 |
| forecast_risk_v6 | diagnostic_other_seasons | incumbent | 0.8306 | 0.5696 | 10/23 | 17 | 0.5652173913043478 | 2/2 | 4/7 |
| forecast_risk_v6 | diagnostic_other_seasons | challenger | 0.8200 | 0.5262 | 3/23 | 63 | 0.8695652173913043 | 2/2 | 6/7 |

Completed rounds: 2; consecutive rounds without gated gain: 2. Stop reason: two_consecutive_no_gain.

V5 fitted paired classifiers on Modal. V6 evaluated the fixed poor-band floor using existing v4 classifier and quantile weights on Modal, with no refitting; this is one training round and one hosted architecture evaluation, not two training rounds. Exact incumbent and quantile prediction hashes reproduce v4. The reused bundle hash was observed at read time, not independently pinned before its original training.

Gas history improved some hourly metrics but degraded others and did not resolve severe misses. The fixed quantile floor trades fewer poor+ misses for more false alarms; it cannot raise a prediction to severe. No candidate is promoted. Development has zero severe support; training has only 27 severe hours across six descriptive episodes. Hazardous recall remains unmeasured. Full raw probabilities/reliability and predictions are preserved in the linked JSON artifacts. No human, field, medical or billed-cost evidence is claimed. This finite stopping rule does not establish maximum attainable performance.

Evidence: `eval/raw/forecast_risk_v5_results.json`, `eval/raw/forecast_risk_v6_results.json`, their `_gate_summary.json` files, and `eval/raw/forecast_next_completion_summary.json`. Three data, architecture and safety reviews are recorded for each round under `docs/FORECAST_V5_*_REVIEW.md` and `docs/FORECAST_V6_*_REVIEW.md`. Offline pytest and Ruff passed; eight focused checks cover causal features, rounded boundaries, episode regressions and the frozen stopping criteria.

Next research prerequisite: obtain distinct severe development episodes and a separately frozen future evaluation source, then test whether pollutant-specific forecasting generalizes. Repeating parameter changes on these same consumed windows cannot establish that. A larger transformer is not supported by the present evidence. Keep deterministic safety handling and current serving behavior.


## Deep pollutant sequence v1 measured completion

# Deep pollutant sequence study: measured results

All candidates were evaluated on identical phase-local 24-hour-context origins. Both 2026 periods are consumed modeled-archive diagnostics, not fresh holdouts. The reference is the new matched LightGBM model; old v4-v6 counts are not an identical subset.

Historical raw `severe` means official Very Poor (301–400); `hazardous` means official Severe (401+). This is an instantaneous concentration proxy, not averaging-compliant station AQI.

| Period | Model | n | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ recall | Poor+ precision | Poor+ FAR | Very Poor+ misses/support | Very Poor+ recall | Very Poor+ FAR | Severe misses/support |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| development | tcn_seed_0 | 1435 | 0.720557 | 0.527710 | 105/168 | 0.375000 | 0.887324 | 0.006314 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | tcn_seed_1 | 1435 | 0.726829 | 0.547261 | 79/168 | 0.529762 | 0.839623 | 0.013418 | 22/22 | 0.000000 | 0.002123 | 0/0 |
| development | tcn_seed_2 | 1435 | 0.739373 | 0.569031 | 65/168 | 0.613095 | 0.844262 | 0.014996 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | tcn_fixed_mean | 1435 | 0.738676 | 0.562208 | 75/168 | 0.553571 | 0.885714 | 0.009471 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | paired_lightgbm | 1435 | 0.743554 | 0.560935 | 79/168 | 0.529762 | 0.855769 | 0.011839 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | persistence | 1435 | 0.364460 | 0.257717 | 146/168 | 0.130952 | 0.130952 | 0.115233 | 22/22 | 0.000000 | 0.015570 | 0/0 |
| diagnostic_pollution | tcn_seed_0 | 2107 | 0.783579 | 0.462954 | 112/248 | 0.548387 | 0.719577 | 0.028510 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_1 | 2107 | 0.789274 | 0.518402 | 125/248 | 0.495968 | 0.793548 | 0.017214 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_2 | 2107 | 0.785002 | 0.480535 | 101/248 | 0.592742 | 0.765625 | 0.024207 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_fixed_mean | 2107 | 0.788799 | 0.486780 | 111/248 | 0.552419 | 0.769663 | 0.022055 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | paired_lightgbm | 2107 | 0.794495 | 0.506529 | 129/248 | 0.479839 | 0.815068 | 0.014524 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | persistence | 2107 | 0.385382 | 0.211169 | 231/248 | 0.068548 | 0.068548 | 0.124260 | 11/11 | 0.000000 | 0.005248 | 0/0 |
| diagnostic_other_seasons | tcn_seed_0 | 3643 | 0.851496 | 0.713231 | 12/16 | 0.250000 | 0.800000 | 0.000276 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_1 | 3643 | 0.846555 | 0.720355 | 9/16 | 0.437500 | 0.411765 | 0.002757 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_2 | 3643 | 0.849300 | 0.725629 | 11/16 | 0.312500 | 0.714286 | 0.000551 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_fixed_mean | 3643 | 0.854516 | 0.716318 | 12/16 | 0.250000 | 0.800000 | 0.000276 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | paired_lightgbm | 3643 | 0.839967 | 0.664454 | 13/16 | 0.187500 | 0.333333 | 0.001654 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | persistence | 3643 | 0.451551 | 0.299947 | 16/16 | 0.000000 | 0.000000 | 0.004411 | 0/0 | UNMEASURED | 0.000000 | 0/0 |


Full [measured report](eval/raw/pollutant_sequence_v1_completion_summary.md) and [machine-readable metrics](eval/raw/pollutant_sequence_v1_completion_summary.json). Research-only consumed modeled archive; no automatic adoption or measured billing.


## Deep pollutant sequence v2 measured completion

# Deep pollutant sequence study: measured results

All candidates were evaluated on identical phase-local 24-hour-context origins. Both 2026 periods are consumed modeled-archive diagnostics, not fresh holdouts. The primary reference is the frozen v1 three-seed concentration-average ensemble. Matched LightGBM remains a secondary comparator.

Historical raw `severe` means official Very Poor (301â€“400); `hazardous` means official Severe (401+). This is an instantaneous concentration proxy, not averaging-compliant station AQI.

| Period | Model | n | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ recall | Poor+ precision | Poor+ FAR | Very Poor+ misses/support | Very Poor+ recall | Very Poor+ FAR | Severe misses/support |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| development | tcn_seed_0 | 1435 | 0.703136 | 0.509053 | 109/168 | 0.351190 | 0.867647 | 0.007103 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | tcn_seed_1 | 1435 | 0.733101 | 0.549333 | 84/168 | 0.500000 | 0.857143 | 0.011050 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | tcn_seed_2 | 1435 | 0.723345 | 0.537784 | 92/168 | 0.452381 | 0.844444 | 0.011050 | 22/22 | 0.000000 | 0.002123 | 0/0 |
| development | tcn_fixed_mean | 1435 | 0.730314 | 0.539391 | 97/168 | 0.422619 | 0.922078 | 0.004736 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | paired_lightgbm | 1435 | 0.743554 | 0.560935 | 79/168 | 0.529762 | 0.855769 | 0.011839 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | persistence | 1435 | 0.364460 | 0.257717 | 146/168 | 0.130952 | 0.130952 | 0.115233 | 22/22 | 0.000000 | 0.015570 | 0/0 |
| development | v1_fixed_mean | 1435 | 0.738676 | 0.562208 | 75/168 | 0.553571 | 0.885714 | 0.009471 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_0 | 2107 | 0.780731 | 0.429600 | 135/248 | 0.455645 | 0.753333 | 0.019903 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_1 | 2107 | 0.789274 | 0.465070 | 119/248 | 0.520161 | 0.796296 | 0.017751 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_2 | 2107 | 0.778358 | 0.488864 | 132/248 | 0.467742 | 0.743590 | 0.021517 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_fixed_mean | 2107 | 0.783579 | 0.464440 | 133/248 | 0.463710 | 0.782313 | 0.017214 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | paired_lightgbm | 2107 | 0.794495 | 0.506529 | 129/248 | 0.479839 | 0.815068 | 0.014524 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | persistence | 2107 | 0.385382 | 0.211169 | 231/248 | 0.068548 | 0.068548 | 0.124260 | 11/11 | 0.000000 | 0.005248 | 0/0 |
| diagnostic_pollution | v1_fixed_mean | 2107 | 0.788799 | 0.486780 | 111/248 | 0.552419 | 0.769663 | 0.022055 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_0 | 3643 | 0.841340 | 0.717388 | 11/16 | 0.312500 | 0.714286 | 0.000551 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_1 | 3643 | 0.844085 | 0.697320 | 12/16 | 0.250000 | 0.571429 | 0.000827 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_2 | 3643 | 0.850673 | 0.617154 | 16/16 | 0.000000 | UNMEASURED | 0.000000 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_fixed_mean | 3643 | 0.849575 | 0.695079 | 13/16 | 0.187500 | 1.000000 | 0.000000 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | paired_lightgbm | 3643 | 0.839967 | 0.664454 | 13/16 | 0.187500 | 0.333333 | 0.001654 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | persistence | 3643 | 0.451551 | 0.299947 | 16/16 | 0.000000 | 0.000000 | 0.004411 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | v1_fixed_mean | 3643 | 0.854516 | 0.716318 | 12/16 | 0.250000 | 0.800000 | 0.000276 | 0/0 | UNMEASURED | 0.000000 | 0/0 |


Full [measured report](eval/raw/pollutant_sequence_v2_completion_summary.md) and [machine-readable metrics](eval/raw/pollutant_sequence_v2_completion_summary.json). Research-only consumed modeled archive; no automatic adoption or measured billing.


## V2 disposition and next weighting study

V2 completed in 335.298 seconds of remote run time (not billed cost). Its fixed ensemble failed the paired gate against v1: pollution Poor+ misses 133/248 versus 111/248, false alarms 32 versus 41; later misses 13/16 versus 12/16, false alarms zero versus one. Very Poor+ misses remain 11/11. All four v2 candidates failed the v1 comparison. Keep v1 as research incumbent; no adoption or deployment. V3 is being prepared with only training-origin risk weighting relative to v1 (SmoothL1, multiplier two on canonical Poor+ labels from training only). Completed secondary reviewers remain unavailable through provider quota/authentication/balance; root synthesis is disclosed.


## Deep pollutant sequence v3 measured completion

# Deep pollutant sequence study: measured results

All candidates were evaluated on identical phase-local 24-hour-context origins. Both 2026 periods are consumed modeled-archive diagnostics, not fresh holdouts. The primary reference is the frozen v1 three-seed concentration-average ensemble. Matched LightGBM remains a secondary comparator.

Historical raw `severe` means official Very Poor (301â€“400); `hazardous` means official Severe (401+). This is an instantaneous concentration proxy, not averaging-compliant station AQI.

| Period | Model | n | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ recall | Poor+ precision | Poor+ FAR | Very Poor+ misses/support | Very Poor+ recall | Very Poor+ FAR | Severe misses/support |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| development | tcn_seed_0 | 1435 | 0.730314 | 0.560950 | 94/168 | 0.440476 | 0.860465 | 0.009471 | 21/22 | 0.045455 | 0.000000 | 0/0 |
| development | tcn_seed_1 | 1435 | 0.739373 | 0.570759 | 58/168 | 0.654762 | 0.814815 | 0.019732 | 22/22 | 0.000000 | 0.001415 | 0/0 |
| development | tcn_seed_2 | 1435 | 0.735889 | 0.579122 | 61/168 | 0.636905 | 0.842520 | 0.015785 | 21/22 | 0.045455 | 0.002123 | 0/0 |
| development | tcn_fixed_mean | 1435 | 0.745645 | 0.576626 | 62/168 | 0.630952 | 0.876033 | 0.011839 | 22/22 | 0.000000 | 0.000708 | 0/0 |
| development | paired_lightgbm | 1435 | 0.743554 | 0.560935 | 79/168 | 0.529762 | 0.855769 | 0.011839 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | persistence | 1435 | 0.364460 | 0.257717 | 146/168 | 0.130952 | 0.130952 | 0.115233 | 22/22 | 0.000000 | 0.015570 | 0/0 |
| development | v1_fixed_mean | 1435 | 0.738676 | 0.562208 | 75/168 | 0.553571 | 0.885714 | 0.009471 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_0 | 2107 | 0.786901 | 0.480468 | 99/248 | 0.600806 | 0.726829 | 0.030124 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_1 | 2107 | 0.788799 | 0.523214 | 86/248 | 0.653226 | 0.757009 | 0.027972 | 11/11 | 0.000000 | 0.000477 | 0/0 |
| diagnostic_pollution | tcn_seed_2 | 2107 | 0.787375 | 0.516024 | 86/248 | 0.653226 | 0.733032 | 0.031737 | 10/11 | 0.090909 | 0.000477 | 0/0 |
| diagnostic_pollution | tcn_fixed_mean | 2107 | 0.791172 | 0.486293 | 88/248 | 0.645161 | 0.740741 | 0.030124 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | paired_lightgbm | 2107 | 0.794495 | 0.506529 | 129/248 | 0.479839 | 0.815068 | 0.014524 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | persistence | 2107 | 0.385382 | 0.211169 | 231/248 | 0.068548 | 0.068548 | 0.124260 | 11/11 | 0.000000 | 0.005248 | 0/0 |
| diagnostic_pollution | v1_fixed_mean | 2107 | 0.788799 | 0.486780 | 111/248 | 0.552419 | 0.769663 | 0.022055 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_0 | 3643 | 0.838869 | 0.743890 | 7/16 | 0.562500 | 0.529412 | 0.002206 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_1 | 3643 | 0.845183 | 0.721250 | 6/16 | 0.625000 | 0.333333 | 0.005514 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_2 | 3643 | 0.854516 | 0.760749 | 9/16 | 0.437500 | 0.777778 | 0.000551 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_fixed_mean | 3643 | 0.847928 | 0.789472 | 6/16 | 0.625000 | 0.769231 | 0.000827 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | paired_lightgbm | 3643 | 0.839967 | 0.664454 | 13/16 | 0.187500 | 0.333333 | 0.001654 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | persistence | 3643 | 0.451551 | 0.299947 | 16/16 | 0.000000 | 0.000000 | 0.004411 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | v1_fixed_mean | 3643 | 0.854516 | 0.716318 | 12/16 | 0.250000 | 0.800000 | 0.000276 | 0/0 | UNMEASURED | 0.000000 | 0/0 |


Full [measured report](eval/raw/pollutant_sequence_v3_completion_summary.md) and [machine-readable metrics](eval/raw/pollutant_sequence_v3_completion_summary.json). Research-only consumed modeled archive; no automatic adoption or measured billing.


## V3 completed: passed finite retrospective gate

V3 passed the preregistered research gate versus the frozen v1 ensemble on both consumed 2026 diagnostics. Pollution Poor+ misses fell 111/248→88/248 while false alarms rose 41→56; later misses fell 12/16→6/16 while false alarms rose 1→3. The fixed ensemble still missed all 11 pollution Very Poor+ hours; later Very Poor+ and official Severe recall remain unmeasured. The 296/19,663 training weighting-support check passed. [Full paired review and next-data requirements](POLLUTANT_SEQUENCE_V3_REVIEW.md).


## Deep pollutant sequence v4 measured completion

# Deep pollutant sequence study: measured results

All candidates were evaluated on identical phase-local 24-hour-context origins. Both 2026 periods are consumed modeled-archive diagnostics, not fresh holdouts. The primary reference is the frozen v3 three-seed concentration-average ensemble. Matched LightGBM remains a secondary comparator.

Historical raw `severe` means official Very Poor (301â€“400); `hazardous` means official Severe (401+). This is an instantaneous concentration proxy, not averaging-compliant station AQI.

| Period | Model | n | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ recall | Poor+ precision | Poor+ FAR | Very Poor+ misses/support | Very Poor+ recall | Very Poor+ FAR | Severe misses/support |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| development | tcn_seed_0 | 1435 | 0.698955 | 0.510189 | 100/168 | 0.404762 | 0.871795 | 0.007893 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | tcn_seed_1 | 1435 | 0.724739 | 0.629951 | 55/168 | 0.672619 | 0.856061 | 0.014996 | 16/22 | 0.272727 | 0.004246 | 0/0 |
| development | tcn_seed_2 | 1435 | 0.758188 | 0.660446 | 56/168 | 0.666667 | 0.811594 | 0.020521 | 15/22 | 0.318182 | 0.004246 | 0/0 |
| development | tcn_fixed_mean | 1435 | 0.737282 | 0.580140 | 68/168 | 0.595238 | 0.877193 | 0.011050 | 21/22 | 0.045455 | 0.001415 | 0/0 |
| development | paired_lightgbm | 1435 | 0.743554 | 0.560935 | 79/168 | 0.529762 | 0.855769 | 0.011839 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | persistence | 1435 | 0.364460 | 0.257717 | 146/168 | 0.130952 | 0.130952 | 0.115233 | 22/22 | 0.000000 | 0.015570 | 0/0 |
| development | v3_fixed_mean | 1435 | 0.745645 | 0.576626 | 62/168 | 0.630952 | 0.876033 | 0.011839 | 22/22 | 0.000000 | 0.000708 | 0/0 |
| diagnostic_pollution | tcn_seed_0 | 2107 | 0.789274 | 0.548512 | 116/248 | 0.532258 | 0.776471 | 0.020441 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_1 | 2107 | 0.794495 | 0.583828 | 77/248 | 0.689516 | 0.721519 | 0.035503 | 10/11 | 0.090909 | 0.000954 | 0/0 |
| diagnostic_pollution | tcn_seed_2 | 2107 | 0.795918 | 0.534362 | 76/248 | 0.693548 | 0.738197 | 0.032813 | 11/11 | 0.000000 | 0.002385 | 0/0 |
| diagnostic_pollution | tcn_fixed_mean | 2107 | 0.796393 | 0.548551 | 88/248 | 0.645161 | 0.761905 | 0.026896 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | paired_lightgbm | 2107 | 0.794495 | 0.506529 | 129/248 | 0.479839 | 0.815068 | 0.014524 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | persistence | 2107 | 0.385382 | 0.211169 | 231/248 | 0.068548 | 0.068548 | 0.124260 | 11/11 | 0.000000 | 0.005248 | 0/0 |
| diagnostic_pollution | v3_fixed_mean | 2107 | 0.791172 | 0.486293 | 88/248 | 0.645161 | 0.740741 | 0.030124 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_0 | 3643 | 0.850947 | 0.751999 | 10/16 | 0.375000 | 1.000000 | 0.000000 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_1 | 3643 | 0.842438 | 0.774007 | 4/16 | 0.750000 | 0.545455 | 0.002757 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_2 | 3643 | 0.861378 | 0.789140 | 5/16 | 0.687500 | 0.611111 | 0.001930 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_fixed_mean | 3643 | 0.857260 | 0.802230 | 6/16 | 0.625000 | 0.833333 | 0.000551 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | paired_lightgbm | 3643 | 0.839967 | 0.664454 | 13/16 | 0.187500 | 0.333333 | 0.001654 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | persistence | 3643 | 0.451551 | 0.299947 | 16/16 | 0.000000 | 0.000000 | 0.004411 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | v3_fixed_mean | 3643 | 0.847928 | 0.789472 | 6/16 | 0.625000 | 0.769231 | 0.000827 | 0/0 | UNMEASURED | 0.000000 | 0/0 |


Full [measured report](eval/raw/pollutant_sequence_v4_completion_summary.md) and [machine-readable metrics](eval/raw/pollutant_sequence_v4_completion_summary.json). Research-only consumed modeled archive; no automatic adoption or measured billing.

### A support check before another model fit

A read-only Modal audit checked whether 48- or 72-hour histories could be built without changing the target rows. It verified all 32,826 canonical six-hour targets and found no missing hourly source values. Training retained 296 Poor+ hours and five Very Poor+ hours in one episode at all three context lengths. At 48 hours, each phase loses only 24 boundary rows; at 72 hours it loses 48. The pollution diagnostic retains its 248 Poor+ hours and 11 Very Poor+ hours across lengths, while the low-support other-seasons diagnostic drops from 16 Poor+ hours in six episodes at 24h to 13 hours in five episodes at 48h.

Three reviewers agreed 48 hours is feasible, but the audit cannot say whether older history improves a forecast. We therefore did not start another fit: the next evidence needed is a development-only test of whether lags 24–48 add signal beyond recent history. These remain consumed CAMS/ERA5 modeled archive data, not station or prospective validation; official Severe recall is unmeasured. See the [support result and review](docs/POLLUTANT_CONTEXT_SUPPORT_V1_REVIEW.md).

## Fixed older-history probe v1: measured development results

Modal call `fc-01M4FM73AHVNNJFY7F8SGSYD8Q`, app `ap-LOJY41QfJZesEwi80LRam5` completed once. Both fits used the exact same 19,639 train and 1,411 development origins; 21,050 canonical target pairs verified. Median imputation, input scaling and target scales fit only on training. There were 296 Poor+ weighted training origins. No 2026 diagnostic labels entered this study.

| Development period | Context | n | Normalized MAE | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ false alarms | Poor+ episode hits/support | Very Poor+ misses/support |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 24h | 1411 | 0.474160 | 0.759745 | 0.638596 | 64/168 | 23 | 21/28 | 18/22 |
| overall | 48h | 1411 | 0.471746 | 0.751240 | 0.626867 | 64/168 | 22 | 21/28 | 18/22 |
| 2025-04 | 24h | 673 | 0.532290 | 0.760773 | 0.490218 | 48/122 | 7 | 16/21 | 8/8 |
| 2025-04 | 48h | 673 | 0.532371 | 0.760773 | 0.485323 | 48/122 | 7 | 16/21 | 8/8 |
| 2025-05 | 24h | 738 | 0.421149 | 0.758808 | 0.637216 | 16/46 | 16 | 5/7 | 10/14 |
| 2025-05 | 48h | 738 | 0.416461 | 0.742547 | 0.629883 | 16/46 | 15 | 5/7 | 10/14 |

48h relative normalized MAE improvement: 0.509%. Predeclared exploratory context screen passed: **False**.

- overall_normalized_mae_gain_at_least_1pct: False
- neither_month_normalized_mae_worse: False
- poor_misses_not_worse: True
- poor_false_alarms_not_worse: True
- poor_episode_hits_not_worse: True
- very_poor_misses_not_worse: True
- very_poor_false_alarms_not_worse: False

Full raw results include six pollutant MAEs, recalls/precision/FAR, episode counts, monthly scores, negative pre-clipping predictions, train scales, actual and predicted development concentrations, and exact origin hashes. These are consumed CAMS/ERA5 modeled archive diagnostics, not independent station, prospective or medical qualification. Unsupported recall is UNMEASURED. A fixed linear probe cannot disprove nonlinear older-history value. No promotion, deployment or billed cost is claimed.


## Deep pollutant sequence v5 measured completion

# Deep pollutant sequence study: measured results

All candidates were evaluated on identical phase-local 24-hour-context origins. Both 2026 periods are consumed modeled-archive diagnostics, not fresh holdouts. The primary reference is the frozen v3 three-seed concentration-average ensemble. Matched LightGBM remains a secondary comparator.

Historical raw `severe` means official Very Poor (301-400); `hazardous` means official Severe (401+). This is an instantaneous concentration proxy, not averaging-compliant station AQI.

| Period | Model | n | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ recall | Poor+ precision | Poor+ FAR | Very Poor+ misses/support | Very Poor+ recall | Very Poor+ FAR | Severe misses/support |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| development | tcn_seed_0 | 1435 | 0.728223 | 0.558271 | 75/168 | 0.553571 | 0.894231 | 0.008682 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | tcn_seed_1 | 1435 | 0.753310 | 0.579183 | 63/168 | 0.625000 | 0.833333 | 0.016575 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | tcn_seed_2 | 1435 | 0.738676 | 0.563584 | 82/168 | 0.511905 | 0.924731 | 0.005525 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | tcn_fixed_mean | 1435 | 0.747038 | 0.573598 | 70/168 | 0.583333 | 0.899083 | 0.008682 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | paired_lightgbm | 1435 | 0.743554 | 0.560935 | 79/168 | 0.529762 | 0.855769 | 0.011839 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | persistence | 1435 | 0.364460 | 0.257717 | 146/168 | 0.130952 | 0.130952 | 0.115233 | 22/22 | 0.000000 | 0.015570 | 0/0 |
| development | v3_fixed_mean | 1435 | 0.745645 | 0.576626 | 62/168 | 0.630952 | 0.876033 | 0.011839 | 22/22 | 0.000000 | 0.000708 | 0/0 |
| diagnostic_pollution | tcn_seed_0 | 2107 | 0.795444 | 0.529715 | 90/248 | 0.637097 | 0.755981 | 0.027434 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_1 | 2107 | 0.789748 | 0.509684 | 86/248 | 0.653226 | 0.746544 | 0.029586 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_2 | 2107 | 0.789274 | 0.489791 | 102/248 | 0.588710 | 0.772487 | 0.023131 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_fixed_mean | 2107 | 0.790698 | 0.482729 | 94/248 | 0.620968 | 0.766169 | 0.025282 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | paired_lightgbm | 2107 | 0.794495 | 0.506529 | 129/248 | 0.479839 | 0.815068 | 0.014524 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | persistence | 2107 | 0.385382 | 0.211169 | 231/248 | 0.068548 | 0.068548 | 0.124260 | 11/11 | 0.000000 | 0.005248 | 0/0 |
| diagnostic_pollution | v3_fixed_mean | 2107 | 0.791172 | 0.486293 | 88/248 | 0.645161 | 0.740741 | 0.030124 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_0 | 3643 | 0.852045 | 0.746901 | 9/16 | 0.437500 | 0.636364 | 0.001103 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_1 | 3643 | 0.845732 | 0.723817 | 9/16 | 0.437500 | 0.437500 | 0.002481 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_2 | 3643 | 0.850398 | 0.706675 | 12/16 | 0.250000 | 0.800000 | 0.000276 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_fixed_mean | 3643 | 0.851222 | 0.741100 | 10/16 | 0.375000 | 0.750000 | 0.000551 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | paired_lightgbm | 3643 | 0.839967 | 0.664454 | 13/16 | 0.187500 | 0.333333 | 0.001654 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | persistence | 3643 | 0.451551 | 0.299947 | 16/16 | 0.000000 | 0.000000 | 0.004411 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | v3_fixed_mean | 3643 | 0.847928 | 0.789472 | 6/16 | 0.625000 | 0.769231 | 0.000827 | 0/0 | UNMEASURED | 0.000000 | 0/0 |


Full [measured report](eval/raw/pollutant_sequence_v5_completion_summary.md) and [machine-readable metrics](eval/raw/pollutant_sequence_v5_completion_summary.json). Research-only consumed modeled archive; no automatic adoption or measured billing.

Three read-only reviewers found that V5's gate failure is real and recommended against another fit on these reused modeled rows. The saved development analysis shows ozone controls all 168 Poor+ hours; V5's ozone error and Poor+ misses both rose from V3. The [episode analysis](eval/raw/pollutant_sequence_v5_error_analysis.md) and [review synthesis](docs/POLLUTANT_SEQUENCE_V5_RESULT_REVIEWS.md) are recorded. The next valuable data is additional quality-controlled, station-aligned pollution episodes with timestamps and units, especially Very Poor and official Severe cases. Severe recall remains unmeasured.


# Target-contract audit: measured results

Hosted read-only CPU call fc-01M4FQ5AR38P77DCWRDAZ9N2M3, app ap-EYjomUeIBrjTquMy5bYdOv. All 32,826 historical instantaneous targets verified. Complete-window decomposition identity error was zero in every phase.

| Phase | Paired origins | Hourly Poor+ / VP+ | Trailing Poor+ / VP+ | Conservative Poor+ / VP+ |
|---|---:|---:|---:|---:|
| train | 19663 | 296 / 5 | 74 / 0 | 344 / 5 |
| development | 1435 | 168 / 22 | 94 / 6 | 213 / 27 |
| diagnostic_pollution | 2107 | 248 / 11 | 113 / 0 | 317 / 11 |
| diagnostic_other_seasons | 3643 | 16 / 0 | 0 / 0 | 16 / 0 |

Official Severe support is zero under every target in every phase. Later complete-trailing Poor+ support is also zero: recall is UNMEASURED, not successful detection.

Period averaging changes the task and cannot be reported as an improvement in historical model accuracy. The conservative product approximation retains hourly spikes and additionally includes persistent elevated averages. Training on trailing means alone would remove the five training Very Poor hours and is not justified as a safety improvement.

Causal persistence trailing Poor+ recall/precision: train 0.6216/0.1581; development 0.6489/0.3631; pollution diagnostic 0.6549/0.3020; later recall UNMEASURED with 15 false alarms. These are a baseline on a different target, not neural results.

No station quality, pristine evaluation, prospective, medical, probability calibration or billed-cost claim. Saved neural h6 outputs cannot reconstruct full trajectories; further inference would require the existing hosted checkpoints.

The development-only fixed-linear comparison provides a distinct algorithm hypothesis. Keep its original hourly task and frozen V3 gate for comparability while independently qualifying station sources.


## Deep pollutant GPU linear v2 measured completion

# Fixed pollutant linear study: measured results

All candidates were evaluated on identical phase-local 24-hour-context origins. Both 2026 periods are consumed modeled-archive diagnostics, not fresh holdouts. The primary reference is the frozen v3 three-seed concentration-average ensemble. Matched LightGBM remains a secondary comparator.

Historical raw `severe` means official Very Poor (301-400); `hazardous` means official Severe (401+). This is an instantaneous concentration proxy, not averaging-compliant station AQI.

| Period | Model | n | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ recall | Poor+ precision | Poor+ FAR | Very Poor+ misses/support | Very Poor+ recall | Very Poor+ FAR | Severe misses/support |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| development | ridge_fixed | 1435 | 0.763066 | 0.639753 | 64/168 | 0.619048 | 0.806202 | 0.019732 | 18/22 | 0.181818 | 0.001415 | 0/0 |
| development | v3_fixed_mean | 1435 | 0.745645 | 0.576626 | 62/168 | 0.630952 | 0.876033 | 0.011839 | 22/22 | 0.000000 | 0.000708 | 0/0 |
| development | paired_lightgbm | 1435 | 0.743554 | 0.560935 | 79/168 | 0.529762 | 0.855769 | 0.011839 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | persistence | 1435 | 0.364460 | 0.257717 | 146/168 | 0.130952 | 0.130952 | 0.115233 | 22/22 | 0.000000 | 0.015570 | 0/0 |
| diagnostic_pollution | ridge_fixed | 2107 | 0.799241 | 0.498535 | 106/248 | 0.572581 | 0.820809 | 0.016676 | 11/11 | 0.000000 | 0.000477 | 0/0 |
| diagnostic_pollution | v3_fixed_mean | 2107 | 0.791172 | 0.486293 | 88/248 | 0.645161 | 0.740741 | 0.030124 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | paired_lightgbm | 2107 | 0.794495 | 0.506529 | 129/248 | 0.479839 | 0.815068 | 0.014524 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | persistence | 2107 | 0.385382 | 0.211169 | 231/248 | 0.068548 | 0.068548 | 0.124260 | 11/11 | 0.000000 | 0.005248 | 0/0 |
| diagnostic_other_seasons | ridge_fixed | 3643 | 0.845732 | 0.707854 | 12/16 | 0.250000 | 0.800000 | 0.000276 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | v3_fixed_mean | 3643 | 0.847928 | 0.789472 | 6/16 | 0.625000 | 0.769231 | 0.000827 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | paired_lightgbm | 3643 | 0.839967 | 0.664454 | 13/16 | 0.187500 | 0.333333 | 0.001654 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | persistence | 3643 | 0.451551 | 0.299947 | 16/16 | 0.000000 | 0.000000 | 0.004411 | 0/0 | UNMEASURED | 0.000000 | 0/0 |


Full [measured report](eval/raw/pollutant_linear_v2_gpu_completion_summary.md) and [machine-readable metrics](eval/raw/pollutant_linear_v2_gpu_completion_summary.json). Research-only consumed modeled archive; no automatic adoption or measured billing.
