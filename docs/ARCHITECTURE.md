# Architecture

The mental model for Baahar, why the pieces are shaped the way they are, and the
failure modes each piece exists to prevent.

---

## The pipeline

```
                           │
                    ┌──────▼───────┐
                    │  forecast.py │  join on timestamp
                    └──────┬───────┘
            ┌──────────────┴──────────────┐
            ▼              ▼               ▼
     ┌────────────┐  ┌─────────────┐  ┌──────────┐
     │ weather.py │  │   air.py    │  │stations.py│  optional WAQI
     │ Open-Meteo │  │ Open-Meteo  │  └──────────┘
     │ forecast   │  │ + naqi.py   │
     └─────┬──────┘  └─────┬───────┘
           │                │
           │          ┌─────▼──────┐
           │          │  naqi.py   │  CPCB Indian NAQI
           │          │            │  worst-sub-index
           │          └────────────┘
           └────────────┬───────────┘
                        ▼
             ┌─────────────────────┐
             │ features.py         │  28 features (13 base + 15 lags)
             │   · policy labels   │  + documented GO/WAIT/SKIP rule
             │   · time_split()    │  chronological, never shuffled
             └──────────┬──────────┘
                        ▼
             ┌─────────────────────┐
             │ score.py            │  heuristic ──or──▶ Ensemble (shipped) / TabPFN
             │   · safety asymmetry│  a model may be stricter
             └──────────┬──────────┘  than policy, never laxer
                        ▼
             ┌─────────────────────┐        ┌──────────────┐
             │ brief.py            │───────▶│ parks.py     │
             │ template · gemma    │        │ pocket.py    │
             │ · enforce_safety()  │◀───────│ sensory cues │
             └─────────────────────┘        └──────────────┘
                        │
                        ▼
             ┌─────────────────────┐
             │ static/             │  HTML + CSS + JS, zero bundler
             │ · Pocket Mode       │  large type, near-black, phone-down
             └─────────────────────┘
```

---

## Eight decisions that matter

### 1. Indian NAQI, not US AQI

Open-Meteo's default is the US EPA AQI. Baahar ignores it and derives the Indian
National Air Quality Index directly from PM2.5, PM10, NO₂, SO₂, CO and O₃
concentrations using CPCB breakpoints (`naqi.py`).

US AQI and Indian NAQI have different breakpoints and different reference
intervals (e.g. 24h for particulate matter vs US 1h/24h mixes). Running an
Indian park planner on US AQI is an error in jurisdiction.

Every hourly record carries `naqi_basis`, which names the governing pollutant
(e.g. `pm25` or `pm10`). If particulate data is missing entirely, `naqi` is
`None` — Baahar refuses to derive a cheerful NAQI from NO₂ alone on a day when
dust is the hazard.

### 2. The safety rule is code, not a model output

`features.py` owns the policy that turns conditions into GO / WAIT / SKIP, with
every threshold stated in one place and anchored to CPCB's own category edges
(Moderate ≤ 200, Poor 201–300, Severe 301+). Two reasons:

- It is auditable. A judge can read twenty lines and know exactly what Baahar
  will and will not tell a person.
- It means the learned model only has to predict something physical — the future
  NAQI band — rather than approximate a rule we can already write down exactly.

### 3. Safety asymmetry in the scorer

When a learned model (consensus ensemble or TabPFN) is active, a model prediction
that is *less* strict than the policy is discarded in favour of the policy. A model
may talk someone out of a walk; it may never talk them into bad air. This is one
comparison in `score.py` and it is covered by tests with a deliberately adversarial
stub model.

- **The eval and the app share one 28-feature definition.** `FEATURE_NAMES` in
  `features.py` is the single owner of the column order (13 base features + 15 past-hour
  lags, differences, and rolling windows); `scripts/run_eval.py` does
  `FEATURE_COLUMNS = list(TABPFN_FEATURE_ORDER)` rather than declaring its own list.
  They used to diverge (13 archive columns against 15 library features), which meant
  a model fitted by the eval could never be used at request time: it raised inside
  `predict_proba`, `score_slots` caught it, and every hour fell back to the policy
  while the published accuracy table described a pipeline nobody ran. `score_tabpfn`
  now compares `n_features_in_` against `len(FEATURE_NAMES)` (28) and raises a
  `ValueError` naming both counts, rather than reordering columns to fit.
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

**Engine selection:** The consensus ensemble (LightGBM, HistGradientBoosting, Random Forest)
is the default shipped engine (`ensemble_gono.pkl`). While TabPFN achieves the highest raw
accuracy on the 1,626-row holdout (0.8708 vs 0.8617), the ensemble wins on 4-band macro-F1
(0.6349 vs 0.6193), 3-band macro-F1 (0.8249 vs 0.8236), and crucially on moderate recall
(0.6620 vs 0.5845) — the vital under-warning boundary for an air quality assistant — while
fitting in 46 s instead of 358 s. On the offline fixture window, both TabPFN and the heuristic
pick the same best hour.

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
