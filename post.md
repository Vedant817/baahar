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
                ├─→ forecast.py ─→ features.py ─→ score.py ─→ brief.py ─→ Pocket Mode
   air.py ──────┘   (join on        (tabular      (TabPFN or   (Gemma /      (near-black,
   naqi.py            timestamp)      features +    heuristic)    template)     timer, one
   (CPCB NAQI)                       documented                   + safety     instruction)
                                     policy)                       repair)
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

Features are hour-*t* only. The split is **chronological**, never shuffled,
because air quality is strongly autocorrelated and a shuffle leaks neighbouring
hours across the boundary and inflates everything.

Data: **8,130 hourly rows**, Bengaluru, 2025-11-01 → 2026-10-05, from Open-Meteo's
CAMS air-quality and ERA5 weather archives. Both keyless. Both free.

I extended the window into winter deliberately. A June–October window gave only
**33 SKIP hours**, which makes the safety metric meaningless. Winter adds the
genuinely bad-air days.

### Go / no-go, predicting band +6h

Holdout: last 20% chronologically — 1,626 rows, 2026-07-30 → 2026-10-05.

| model | accuracy | macro-F1 | skip_as_go | n(SKIP) | fit time |
|---|---|---|---|---|---|
| majority class | 0.4047 | 0.1441 | 0.0 | 24 | <0.1 s |
| persistence (band at *t*) | 0.3647 | 0.2492 | 0.0 | 24 | <0.1 s |
| logistic regression | 0.7294 | 0.4850 | 0.0 | 24 | 1.9 s |
| random forest | 0.8296 | 0.5642 | 0.0 | 24 | 1.8 s |
| gradient boosting | 0.8383 | 0.5874 | 0.0 | 24 | 5.7 s |
| lightgbm | 0.8432 | 0.5825 | 0.0 | 24 | 2.5 s |
| **consensus ensemble** | **0.8487** | **0.6089** | **0.0** | **24** | **6.6 s** |
| TabPFN 9.1.0 (cpu)* | 0.8512 | 0.6040 | 0.0 | 24 | 339 s |

**TabPFN wins. By an amount I do not think means anything.** +0.012 accuracy and
+0.014 macro-F1 over gradient boosting is about 20 rows out of 1,626, from a single
seed with no variance recorded. If I ran that comparison ten times the order would
probably flip. And it is not like-for-like with the rows above it: TabPFN was
SKIPPED in the current run, and its number comes from an earlier run fitted on
instantaneous-only NAQI, before the conservative-NAQI fix. That row is provisional.
So: TabPFN is the top line because it has the highest number, and I am not going to
dress that up as "prior-learning transformers beat gradient boosting on Indian air
quality".

Two things I find more interesting than the ranking:

**Where the gain actually came from.** One place: `moderate` recall, 0.5845 vs
0.5563. Same error class, slightly fewer of them. The hard bands — `poor` on three
examples, `severe` and `hazardous` on zero — are untested for TabPFN exactly as
they are for everything else in the table.

**It is 37x slower to fit, and on the live window it appears to pick the same
hour as the heuristic.** I compared the two by hand on 6 October and did **not**
record that per-hour comparison as an artifact, so read it as an anecdote rather
than a measurement - nothing in `eval/raw/` supports it, and I would rather say
that than publish a precise-sounding "all 24 hours" that no run reproduces. So for
*this product*, TabPFN may be paying 339 seconds for something I cannot prove. I am
shipping the claim because it genuinely ran and won the table, not because I think
it is the right engine
yet. The honest version of this row is "it works, it is the best number I have,
and I cannot yet show it is worth it".

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
| length ≤ 120 words | 1.000 | 1.000 |
| hallucinated park | 0.000 | 0.000 |
| safety caveat present | 1.000 | 1.000 |
| cites the NAQI figure | 1.000 | 1.000 |
| names the given park (GO cases) | **1.000** | 0.833 |
| blind rubric, mean /10 | **9.83** | 9.53 |
| latency p50 | **3 ms** | 51,730 ms |
| latency p95 | **6 ms** | 115,187 ms |

**The deterministic writer won.** Better rubric score, more consistent about
naming the park it was given, and roughly 17,000× faster. That is why Baahar
ships the local writer as the default and treats the model as an optional
upgrade — **the eval changed the product.**

Both writers scored **zero** hallucinated parks and **zero** forbidden terms
across 72 briefings, and every safety requirement passed on every case. That is
the post-generation safety pass earning its keep, not the model complying.

Two caveats, so this is not over-read. The rubric is **saturated** — scores run
8.92–10.00, so it separates a broken briefing from a good one and does almost
nothing to rank good ones against each other. And the p95 is the real cost:
Open-Meteo answers in 3 ms and the open model takes two minutes, so the fast
default is not a cop-out, it is the product.

Full tables, per-decision breakdown, and the raw JSON:
[`eval/RESULTS.md`](eval/RESULTS.md).

---

## What I got wrong (the useful part)

**A model shipped its own instructions as the briefing.** Gemma 4 returns a
reasoning part marked `"thought": true` *before* the answer. I read `parts[0]`.
So the first version of the product greeted users with a verbatim restatement of
my system prompt. Found it because I read the output. Fixed by skipping thought
parts; pinned by a test.

**The safety caveat deleted itself.** `enforce_safety` stripped medical hedging
and then appended a disclaimer containing the phrase *"not medical advice"*. Same
run: added, then deleted. Reordered the passes.

**My eval was silently measuring nothing.** The blind judge was handed a rubric
whose JSON example used a placeholder `id` on the line immediately above a
paragraph starting with the word `BANNED`. It copied the id from the wrong line
and returned a confident **0** for every dimension. A benchmark that scores zero
looks like a result. I only noticed because the local writer — which passes
every machine check — was scoring 0.

**Then I fixed that, and the rubric was still measuring nothing.** The next full
run reported 3.43/10 for a writer that scores 10/10 on every GO case, because my
rubric prompt said *"score 0 if conditions are BAD"* and the judge applied that
to any non-GO decision — including briefings that correctly said "stay in". Every
GO case scored exactly 10. Every non-GO case scored exactly 0.

That one was worse, because the aggregate number looked like a plausible
finding about both writers. The tell was in the confusion: a perfect step
function from the decision label. The fix was to tell the judge to grade the
*writing*, and that a briefing saying "stay in" is well written. Re-judging the
same 72 briefings took the local writer from **3.43 to 9.83** and introduced
real variation within each decision.

I also added a check that fails the harness when every decision receives a single
identical score, because that is the exact signature of this bug.

Three times the eval caught itself rather than the product. Two of them looked
like findings.

**A park name duplicated itself.** Grounding "Lalbagh" in a briefing for
*"Lalbagh Botanical Garden"* produced *"Lalbagh Botanical Garden Botanical
Garden"*.

**The loading spinner never went away.** An author `display: grid` rule outranks
the browser's `[hidden] { display: none }`, so the spinner stayed painted
underneath the finished brief. Found by screenshotting the UI rather than
trusting that it worked.

**I invented an API.** I could not reach Tinker's documentation, and
`brief.py` contained a plausible-looking endpoint I had guessed. I deleted it.
Shipping a fabricated integration would have 404'd in front of a judge, made the
repo *look* like it had a Tinker integration that had never run, and contradicted
the honesty rule governing every other number here. It is now an empty
configuration value that refuses loudly. See
[`docs/adr/001-tinker-outcome.md`](docs/adr/001-tinker-outcome.md).

That last one cost me the Tinker prize category. I would rather lose a category
than win it with code I know is fake.

### Things I did not finish, plainly

- **No field test.** The walk has not happened. `docs/FIELD_TEST.md` says NOT YET
  DONE and that banner is accurate. Everything above is measured against my own
  harness by me, and the single strongest claim in the project — that the screen
  is the shortest part of the walk — is untested by a human. I left the blank form
  in the repo rather than writing a plausible paragraph.
- **TabPFN took a licence and a CPU override to run.** Two separate gates, and
  they behave completely differently:

  - The *licence* is a real gate. `tabpfn==9.1.0` will not fetch weights until a
    Prior Labs acceptance is recorded, even though `Prior-Labs/TabPFN-v2-clf` is
    public and reports `gated=False`. I did not route around that — a human
    accepted it and put the key in `.env`.
  - The *CPU size guard* is not. TabPFN refuses >5,000 rows on CPU by default and
    hands you the switch: `TABPFN_ALLOW_CPU_LARGE_DATASET=1`, or a GPU, or the
    hosted API. I measured it first — 6,504 rows fit in 1.6 s, 1,626 predictions
    take 312 s — and took the switch. Five and a half minutes is a reasonable
    price to actually measure the model I was claiming to use.

  The thing that cost me an hour: **you have to set that variable before importing
  `tabpfn`.** The guard reads a pydantic settings object that snapshots at import
  time, so setting it afterwards does nothing, and the symptom is *identical* to
  the guard not existing — same `SKIPPED` line, same non-zero feeling. Twice I
  "fixed" it and got the same output. If you hit that, it is not your code.
- **TabPFN's fitted model is 840 MB, so it is not in the repo.** `eval/artifacts/`
  is gitignored and `scripts/run_eval.py` recreates it. Committing an 840 MB pickle
  to a public repo would have been a hostile thing to do to every judge who clones
  it, and the brief says no multi-GB downloads — this one stayed out.
- **Gemma is slow.** Measured **40–95 seconds** per briefing, because the Gemma 4
  reasoning trace cannot be disabled on these models — the API returns
  *"Thinking budget is not supported for this model."* That is why Baahar ships a
  deterministic template writer as the default fast path (**3 ms**) and caches
  model output. I would rather have a fast boring answer than a good slow one.
- **Not deployed.** Local run plus a recorded walk, which the brief accepts.

---

## The field test

<!-- FILL (optional, only after the walk): replace the paragraph below with the
     block from `uv run baahar journal --markdown`. If the walk has not happened,
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
| **Best Use of TabPFN** | ✅ | `tabpfn==9.1.0` ran on a real 1,626-row chronological holdout: 0.8512 acc / 0.6040 macro-F1, best in my table. Licence accepted by a human; CPU override documented. |
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
- **505 tests pass offline.** `uv run pytest`
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
3. **Make TabPFN earn its 339 seconds.** It is the best number in my table and it
   changes none of my answers. Either it starts beating the heuristic where it
   matters — the bands the holdout cannot currently test — or it goes back to being
   an optional extra, which is where it honestly belongs right now.
4. **Finish the Tinker fine-tune** — the 219-example dataset exists; the reason is
   that `tinker.ai` does not resolve from my environment, not a missing idea. The
   fine-tune's target is stylistic: prose instead of a restated plan, Indian outdoor
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
