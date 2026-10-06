# Architecture

Baahar is a small Python package plus a static front end. There is no framework
in the middle and no build step anywhere, which is a deliberate response to the
constraint that a judge should be able to clone the repo and be running inside
five minutes.

```
   ┌──────────────────────────────────────────────────────────┐
   │  baahar serve  →  FastAPI                                │
   │                    /                 /api/brief           │
   │              index.html          (plan + brief + pocket)  │
   │              style.css                                   │
   │              app.js          3 screens, 1 request         │
   └───────────────────────┬──────────────────────────────────┘
                           │
   ┌───────────────────────▼──────────────────────────────────┐
   │  cli.py            brief · score · parks · check · serve │
   └───────────────────────┬──────────────────────────────────┘
                           │
                    ┌──────▼───────┐
                    │  forecast.py │  join on timestamp
                    └──────┬───────┘
            ┌──────────────┼───────────────┐
            ▼              ▼               ▼
     ┌────────────┐  ┌─────────────┐  ┌──────────┐
     │ weather.py │  │   air.py    │  │stations.py│  optional WAQI
     │ Open-Meteo │  │ Open-Meteo  │  └──────────┘
     │ forecast   │  │ + naqi.py   │
     └─────┬──────┘  └──────┬──────┘
           │                │
           │          ┌─────▼──────┐
           │          │  naqi.py   │  CPCB Indian NAQI
           │          │            │  worst-sub-index
           │          └────────────┘
           └────────────┬───────────┘
                        ▼
             ┌─────────────────────┐
             │ features.py         │  tabular rows + the documented
             │   · policy labels   │  GO/WAIT/SKIP rule
             │   · time_split()    │  chronological, never shuffled
             └──────────┬──────────┘
                        ▼
             ┌─────────────────────┐
             │ score.py            │  heuristic  ──or──▶  TabPFN
             │   · safety asymmetry│  a model may be stricter
             └──────────┬──────────┘  than policy, never laxer
                        ▼
             ┌─────────────────────┐        ┌──────────────┐
             │ brief.py            │───────▶│ parks.py     │
             │ template · gemma    │        │ pocket.py    │
             │ · enforce_safety()  │◀───────│ sensory cues │
             └─────────────────────┘        └──────────────┘
```

## The seven decisions worth explaining

### 1. Indian NAQI, computed rather than borrowed

Open-Meteo returns `us_aqi`, the US EPA scale. India has its own index with
different breakpoints, different averaging periods and different band names.
`naqi.py` recomputes the CPCB Indian NAQI from raw concentrations — per-pollutant
sub-index from the 2014 CPCB breakpoints, overall index = the worst sub-index.

The CPCB breakpoints are defined on **24-hour means**; Open-Meteo publishes
**hourly** values. So the number Baahar shows is an approximation of official
NAQI, not official NAQI. Every result carries that provenance in a
`naqi_basis` field and the UI labels it. A clearly-labelled approximation is
honest; a mislabelled number is not.

### 2. The safety rule is code, not a model output

`features.py` owns the policy that turns conditions into GO / WAIT / SKIP, with
every threshold stated in one place and anchored to CPCB's own category edges
(Moderate ≤ 200, Poor 201–300, Severe 301+). Two reasons:

- It is auditable. A judge can read twenty lines and know exactly what Baahar
  will and will not tell a person.
- It means the learned model only has to predict something physical — the future
  NAQI band — rather than approximate a rule we can already write down exactly.

### 3. Safety asymmetry in the scorer

When TabPFN is active, a model prediction that is *less* strict than the policy
is discarded in favour of the policy. A model may talk someone out of a walk; it
may never talk them into bad air. This is one comparison in `score.py` and it
is covered by tests with a deliberately adversarial stub model.

- **The eval and the app share one feature definition.** `FEATURE_NAMES` in
  `features.py` is the single owner of the column order; `scripts/run_eval.py`
  does `FEATURE_COLUMNS = list(TABPFN_FEATURE_ORDER)` rather than declaring its
  own list. They used to diverge (13 archive columns against 15 library features),
  which meant a model fitted by the eval could never be used at request time: it
  raised inside `predict_proba`, `score_slots` caught it, and every hour fell back
  to the policy while the published accuracy table described a pipeline nobody ran.
  `score_tabpfn` now compares `n_features_in_` against `len(FEATURE_NAMES)` and
  raises a `ValueError` naming both counts, rather than reordering columns to fit.
  `eval/RESULTS.md` § C.14 has the full account.

Two further practical notes, all three learned by hitting them:

- **TabPFN's CPU size guard must be lifted before the import.** The guard reads a
  pydantic settings object that snapshots at import time, so
  `os.environ["TABPFN_ALLOW_CPU_LARGE_DATASET"] = "1"` set after `import tabpfn`
  does nothing and produces output identical to the guard not existing. It is a
  documented performance default (the alternatives are a GPU or the hosted API),
  not a licence condition, so `score.py` sets it — and the ordering is commented,
  because the symptom looks like a missing feature rather than a sequencing bug.
- **The fitted classifier is 840 MB.** `save_tabpfn_model` writes it to
  `eval/artifacts/`, which is gitignored along with `*.pkl`. The weights stay out
  of the repository and `scripts/run_eval.py` recreates them. This is the disk
  constraint from `AGENTS.md` enforced at the file level rather than by
  discipline.

- **The fitted model lives at `DEFAULT_TABPFN_ARTIFACT`** and both
  `save_tabpfn_model` and `load_tabpfn_model` name that constant. They used to
  disagree: the writer saved to `eval/artifacts/tabpfn_gono.pkl` while the reader
  only looked at `$TABPFN_MODEL_PATH`, so an 840 MB fitted model sat on disk being
  invisible to the scorer. Writer and reader must agree on the path; that is a test.

Measured on the offline fixture window: TabPFN and the heuristic pick the same best
hour and disagree on 0 of 24 hours. The model is in the product because the
challenge asked for it and because it is genuinely the highest-scoring model on the
holdout — not because it currently changes an answer. That is recorded rather than
smoothed over.

### 4. Safety is enforced after generation, not requested in a prompt

The Gemma prompt *asks* for a caveat. A prompt is a suggestion. `enforce_safety`
runs on whatever comes back and repairs what is actually missing:

- a missing NAQI acknowledgement gets a factual one appended;
- medical hedging ("guaranteed safe") is stripped;
- and if the plan says SKIP but the text sounds encouraging, the text is thrown
  away and rewritten. That case is a hard fail, not a warning.

Ordering matters here and is a bug that shipped once: hedging is stripped
*before* the caveat is appended, because the disclaimer we add contains the
phrase "not medical advice" and the hedging filter would otherwise delete the
caveat it had just inserted.

### 5. Weather and air quality are joined on timestamp

They come from two Open-Meteo endpoints. Joining them positionally is the
obvious implementation and it is wrong: if one series starts an hour later, a
positional zip pairs 06:00 weather with 07:00 air. Everything downstream looks
plausible and is incorrect. `forecast.py` joins on the timestamp, and an hour
with no air reading is kept with `naqi = None` so the scorer treats it as
unusable instead of dropping it and shifting the timeline.

### 6. Every network call has a recorded-fixture fallback

`http_client.py` guarantees three properties for all outbound traffic: a hard
timeout, bounded retries, and a fallback to a *verbatim recorded* response under
`data/samples/`. Fixtures carry provenance (recorded timestamp, source URL) and
are never hand-edited — they are evidence, which is why the offline test suite
is worth anything.

The failure mode this prevents is the expensive one: a brief that quietly says
"looks fine" because the air-quality call returned nothing.

### 7. No build step in the front end

`static/` is one HTML file, one stylesheet and one script, served by the same
FastAPI process as the API. No CDN, no web fonts, no bundler. A judge can read
the whole front end in one sitting, it works with the network unplugged, and
there is no supply-chain surface to worry about.

Pocket Mode is a fullscreen state transition with a near-black background and
large type. It does not need a component framework, and shipping without one
keeps the repo approachable for someone new to software engineering.

### 8. Seasonal cues: recorded, anchored, and worded so they cannot overclaim

Pocket Mode's shuffle button cycles past the hand-written sensory cues to species
that people have actually logged nearby this month. Three choices make this
survivable.

**A recorded snapshot, not a live call.** `seasonal.py` reads
`data/seasonal/blr_<year>_<month>.json`, produced by
`scripts/refresh_seasonal.py`. The briefing is supposed to be ready before it is
asked for, and a committed file means every claim is traceable.

**City-anchored, and the signature enforces it.** The snapshot is a radius around
the configured city centre, so `cues_for()` accepts no `lat`/`lon`. Accepting the
caller's park coordinates would have invited the reader to believe the radius was
measured from that park. It was not, and omitting the parameters makes the honest
reading the only one available. The requested radius is also clamped to the
snapshot's, so asking for 50 km yields a 5 km claim rather than 5 km of evidence
supporting a 50 km promise.

**The instruction and the evidence are separate fields.** `SeasonalCue.text` is one
short line — "Look for a Chocolate Pansy." — because the screen's rule is one
instruction in large type, and an earlier draft put the record count and radius
into the same string. It rendered four lines tall with a footnote in the middle,
which is a readout, not an instruction. `SeasonalCue.evidence` carries the count,
the radius, the source, and the disclaimer, and is rendered small underneath.
`tests/test_seasonal.py` asserts the instruction stays under 45 characters and
contains no statistics.

Two boundaries keep the honesty from being merely intended:

* `briefing_cue()` never hands a seasonal cue to the briefing writer. An LLM told
  to include a species line will restate it more confidently than the record
  supports, so the species never enters the prompt. This also keeps the 36-case
  briefing evaluation describing the prompt that actually ships.
* Seasonal cues are withheld entirely when the plan is not a GO, and whenever an
  air or heat safety cue is showing. "Find the coolest patch of shade within fifty
  metres" is doing real work at 34 °C, and a butterfly suggestion three taps away
  from it would be a distraction from the one instruction that matters.

The cue carries `taxon_id`, `scientific_name` and `source_url`, because common
names are ambiguous and the binomial is what a reader can check. The app is not
an identification tool and makes no identification claims.

## Module map

| Module | Responsibility | Knows nothing about |
|---|---|---|
| `config.py` | settings from `.env` + env, cached | anything domain-specific |
| `http_client.py` | timeouts, retries, recorded fixtures | weather, air, models |
| `naqi.py` | CPCB breakpoints, worst-sub-index | the network, the product |
| `weather.py` | Open-Meteo forecast | air quality |
| `air.py` | Open-Meteo AQ → Indian NAQI | scoring |
| `stations.py` | optional WAQI cross-check | scoring, briefing |
| `forecast.py` | timestamp join | policy |
| `features.py` | feature rows, policy labels, time split | models |
| `score.py` | TabPFN + heuristic, safety asymmetry | language |
| `parks.py` | curated parks, nearest + shade | scoring |
| `brief.py` | writers, safety repair, caching, voice | UI |
| `pocket.py` | Pocket Mode payload and cue ordering | the writer |
| `seasonal.py` | recorded species cues, wording, evidence | the network, scoring |
| `app.py` | HTTP surface | HTML |
| `cli.py` | terminal surface | HTTP |

Dependencies point in one direction only. `naqi.py` is the leaf: it knows the
CPCB table and nothing else, which is why its tests are fast, offline, and
exhaustive.

## Testing strategy

- **Default run is offline.** No test touches the network. `pytest` passes with
  the cable unplugged, because the product must too.
- **Exhaustive where it matters.** Every CPCB breakpoint boundary is pinned in
  `test_naqi.py`, including the exact value where a band changes.
- **Adversarial where it matters.** `test_score.py` feeds a stub model that
  always says GO and asserts the policy overrules it.
- **Regression tests for real bugs.** Each bug found while building has a test
  named after it — the Gemma reasoning part, mid-word truncation, the
  self-deleting safety caveat, the duplicated park name, the `hidden`-attribute
  override. They are in `tests/` with comments saying what happened.
- **The UI is checked headlessly.** `scripts/ui_check.mjs` drives Chrome over
  CDP using Node's built-in WebSocket — no npm install — and fails on console
  errors, horizontal overflow, or a screen that should have been dismissed. It
  also asserts the provenance line is *absent* under a hand-written cue and
  *present* under a data-backed one, since a source credit on the wrong line is
  the kind of bug a screenshot review would not catch.
- **Honesty rules are tests, not prose.** `tests/test_seasonal.py` fails the
  build if a cue ever promises a sighting, if the instruction grows past a
  glanceable line, or if a species claim reaches the briefing prompt.

## Deliberate omissions

- **No background job scheduler.** Baahar answers one question at one moment.
- **No user accounts, no database.** A JSONL journal and SQLite-free state; see
  ADR 000.
- **No continuous location.** City-level coordinates only. There is no GPS
  history because a tool whose purpose is to get you away from the screen should
  not be building a record of where you went.
- **No metrics endpoint.** Nothing about Baahar needs telemetry, and shipping
  any would undercut the privacy claim in the README.