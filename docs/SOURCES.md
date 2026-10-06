# Sources

Every external claim Baahar makes traces to something below. Where a fact was
verified live during the build, the date is recorded — APIs move, and a citation
without a date is a rumour.

---

## Challenge

| What | Where |
|---|---|
| Hub, rules, judging, deadlines | <https://dev.to/challenges/hacktoberfest-week1-2026-10-05> |
| Launch post, prize structure | <https://dev.to/devteam/join-the-hacktoberfest-open-source-ai-challenge-week-1-touch-grass-2450-in-prizes-across-17-4pom |
| HF26 hub | <https://dev.to/challenges/hf26> |
| Partner promos (Tinker, Render, Backboard, ElevenLabs) | <https://hacktoberfest.com/my/promos> |

Deadline arithmetic, recomputed rather than copied: Oct 11 2026 23:59 PDT is
UTC−7, so Oct 12 06:59 UTC, which is Oct 12 **12:29 IST** (UTC+5:30).

---

## Indian NAQI — the most load-bearing citation

Baahar's headline number is the Indian National Air Quality Index, so its
breakpoints need a real source rather than a plausible-looking table.

| What | Where | Status |
|---|---|---|
| CPCB NAQI, official | <https://cpcb.nic.in/National-Air-Quality-Index/> | primary reference |
| CPCB real-time dashboard | <https://airquality.cpcb.gov.in/AQI_India/> | live values, for comparison |
| CPCB real-time data portal | <http://www.cpcb.gov.in/real-time-air-quality-data/> | live values |

**What was used to write the table.** The eight-pollutant CPCB table (PM10,
PM2.5, NO2, O3, CO, SO2, NH3, Pb), its six categories (Good, Satisfactory,
Moderate, Poor, Severe, Hazardous), the per-pollutant health-breakpoint ranges,
and the rule that *the worst sub-index reflects overall NAQI*.

The breakpoints were cross-checked against the **India** section of the
Wikipedia "Air quality index" article, which reproduces the CPCB table verbatim
including the per-pollutant ranges:

<https://en.wikipedia.org/wiki/Air_quality_index#India>

Retrieved 2026-10-06. Wikipedia is used here as a transcription of the CPCB
table, not as an authority in its own right; `naqi.py` cites CPCB as the source
and the tests pin every boundary value.

### The caveat that travels with every number

CPCB's breakpoints are defined on **24-hour mean** concentrations (8-hour for O3
and CO). Open-Meteo publishes **hourly** values. Baahar applies the 24-hour
breakpoints to hourly readings, which is an approximation. Every result carries

```
naqi_basis = "cpcb_24h_breakpoints_applied_to_hourly_concentrations"
```

and the UI says so. This is stated in the README, in `naqi.py`'s module
docstring, and in the attribution line at the bottom of the web app.

**Unit conversion worth recording.** CPCB expresses CO in mg/m³; Open-Meteo
reports µg/m³. A factor of 1/1000 is applied (`PollutantSpec.scale`). Without
it a plausible 2 000 µg/m³ reading would be read as 2 000 mg/m³ and saturate the
index at 500. `test_naqi.py` pins both the conversion and the regression.

---

## Weather and air quality

| What | Where | Notes |
|---|---|---|
| Open-Meteo forecast API | <https://api.open-meteo.com/v1/forecast> | keyless |
| Open-Meteo air quality API | <https://air-quality-api.open-meteo.com/v1/air-quality> | keyless, CAMS |
| Open-Meteo ERA5 archive | <https://archive-api.open-meteo.com/v1/archive> | historical weather |
| Open-Meteo historical forecast | <https://historical-forecast-api.open-meteo.com/v1/forecast> | past model runs |
| Documentation | <https://open-meteo.com/en/docs>, <https://open-meteo.com/en/docs/air-quality-api> | |
| Pricing / terms | <https://open-meteo.com/en/pricing> | free non-commercial |
| Source code | <https://github.com/open-meteo/open-meteo> | |

Attribution required by the licence: **Weather data by Open-Meteo.com, CC BY
4.0.** Reproduced in the README table and in the web app footer.

### Endpoints verified on 2026-10-06

Everything below was called successfully during the build rather than assumed:

```
api.open-meteo.com/v1/forecast                          200
air-quality-api.open-meteo.com/v1/air-quality           200
archive-api.open-meteo.com/v1/archive                   200  (ERA5 weather)
air-quality-api.open-meteo.com/v1/air-quality + dates   200  (historical AQ)
historical-forecast-api.open-meteo.com/v1/forecast      200
archive-api.open-meteo.com/v1/forecast                  404  ← does not exist
```

The 404 is recorded because it cost real time: the obvious guess for "the
weather archive" is the wrong path, and `scripts/build_dataset.py` carries a
comment saying so.

**Historical air quality.** The AQ endpoint accepts `start_date`/`end_date` for
past hours, which is what makes the non-circular tabular eval possible without
any key. Range used: 2025-11-01 → 2026-10-05, 8130 hourly rows.

### Sources deliberately *not* used

| Source | Why not |
|---|---|
| `api.data.gov.in` CPCB resource `3b01bcb8-…` | The HF26 pack flags it as possibly stale. Claiming live data from an unverified-freshness feed would be exactly the kind of claim this repo refuses to make. Not used at all. |
| [OpenCity Bengaluru AQI CSVs](https://data.opencity.in/dataset/bengaluru-hourly-air-quality-reports) | The planned source. Not needed: the Open-Meteo archive gave 8130 keyless rows including all six CPCB pollutant species, so pulling station CSVs would have added a scrape step and licensing questions for no gain. Recorded as a deliberate substitution. |
| WAQI | US EPA AQI only. Used, optionally, as a labelled cross-check — never as the number shown. Converting an EPA index back to a concentration to derive Indian NAQI would be a lossy round trip through a different standard. |

---

## Models and partner tech

| What | Where | Status |
|---|---|---|
| Google AI Studio keys | <https://ai.google.dev/gemini-api/docs/api-key> | used; free, no card |
| Billing / free-tier notes | <https://ai.google.dev/gemini-api/docs/billing> | |
| TabPFN / Prior Labs | <https://priorlabs.ai>, <https://docs.priorlabs.ai/quickstart> | licence-gated, see ADR 001 |
| Tinker | <https://tinker.ai> | **unverifiable**, see ADR 001 |
| ElevenLabs | <https://elevenlabs.io> | optional voice |
| WAQI token | <https://aqicn.org/data-platform/token/>, <https://aqicn.org/api/> | optional |

### Gemma model IDs — verified live, and they had moved

A live `GET /v1beta/models` listing on **2026-10-06** returned 61 models. The only
open-weight Gemma entries were:

```
models/gemma-4-26b-a4b-it
models/gemma-4-31b-it
```

The pin in `.env.example` started as `gemma-2.5-9b-it`, which now returns
**404**. Anyone reproducing this should re-run that listing rather than trusting
the pin. Defaults are now `gemma-4-31b-it` with `gemma-4-26b-a4b-it` as fallback.

Two verified behaviours that shaped the implementation:

1. **Gemma 4 emits a reasoning part.** The response contains a part with
   `"thought": true` *before* the answer. Reading `parts[0]` shipped the model's
   internal notes as the user-facing briefing, including a verbatim restatement
   of Baahar's instructions. `brief._extract_gemini_text` skips thought parts;
   `test_brief.py` pins the behaviour.
2. **Thinking cannot be disabled on these models.**
   `generationConfig.thinkingConfig.thinkingBudget` returns
   `"Thinking budget is not supported for this model."` So the reasoning trace
   must be paid for in output tokens. Measured traces: 2.2k characters
   (`gemma-4-31b-it`) to 5.7k (`gemma-4-26b-a4b-it`).
3. **Free-tier quotas are per model.** `gemini-2.5-flash` returned
   `429 quota exceeded` while `gemini-2.5-flash-lite`, `gemini-3.5-flash-lite`
   and `gemini-flash-latest` all answered. The eval harness probes a candidate
   list and records which model actually judged.

### TabPFN: licence gate vs CPU guard — two different kinds of "no"

Both were hit on 2026-10-06 and they are worth keeping apart, because treating
them the same way is how you either break a licence or waste an afternoon.

**Licence gate — real, and not routed around.** `Prior-Labs/TabPFN-v2-clf` reports
`gated=False` via the Hugging Face API and is downloadable anonymously.
Nevertheless `tabpfn==9.1.0` calls `ensure_license_accepted()` before fetching
weights and requires `TABPFN_TOKEN` from a Prior Labs account. A human accepted the
licence and put the key in `.env`. See `NEEDS_HUMAN.md` §1.

**CPU size guard — a performance default, not a restriction.** TabPFN refuses to
fit more than ~5,000 rows on CPU and offers three documented ways out:
`TABPFN_ALLOW_CPU_LARGE_DATASET=1`, a GPU, or the hosted `tabpfn-client` API.
Measured here before taking it: 6,504 rows fit in 1.6 s, 1,626 predictions take
312 s.

The trap: **`TABPFN_ALLOW_CPU_LARGE_DATASET` must be set before `tabpfn` is
imported.** `tabpfn/validation.py` reads `settings.tabpfn.allow_cpu_large_dataset`,
a pydantic settings object that snapshots at import time. Setting the variable
afterwards is silently ignored and produces byte-identical output to the guard not
existing — the same `SKIPPED` line. `score.py` and `scripts/run_eval.py` set it
before the import, with a comment, because the failure looks like a missing
feature rather than an ordering bug.

---

## Map data

| What | Where | Licence |
|---|---|---|
| OpenStreetMap | <https://www.openstreetmap.org> | ODbL 1.0 |

Park extents and footpaths in `data/parks_blr.json` were curated by hand using
OSM as a reference, with `osm_ref` recorded per entry. The vibe, crowding and
gate notes are original prose, not OSM data.

Gate hours are deliberately stated as *nudges to check locally*, not as claims.
An app that tells you Cubbon's gates are open at a time when they are shut is
worse than one that says "check locally".

---

## Seasonal species cues

| What | Where | Licence |
|---|---|---|
| iNaturalist API v1 | <https://api.inaturalist.org/v1/> | free, no key |
| iNaturalist observations | <https://www.inaturalist.org/observations> | CC0 / CC-BY, per record |

Pocket Mode's "another thing to notice" button cycles to species suggestions drawn
from research-grade iNaturalist records near the city centre. The rules that keep
this from becoming a bird-identification confidence machine:

* **Research grade only.** That is iNaturalist's community-verified tier: other
  observers agreed with the identification. `tally()` additionally drops any
  record with zero agreeing identifications.
* **The cue never promises a sighting.** The instruction is "Look for a
  Chocolate Pansy." The provenance line underneath says what the record count
  does and does not mean: *"A record means someone logged it nearby, not that you
  will see it."* `tests/test_seasonal.py` fails the build if a banned phrase like
  "you will see" or "guaranteed" appears in an instruction.
* **City-anchored, not park-anchored.** The snapshot is a radius around the
  configured city centre, so `cues_for()` takes no `lat`/`lon`. Accepting the
  caller's park coordinates would have implied the radius was measured from that
  park, which it was not.
* **The radius is clamped to the snapshot.** Asking for 50 km yields a 5 km claim,
  because that is how much the recorded evidence covers.
* **Evidence stays out of the instruction.** The count and radius live in a small
  provenance line, not in the large type. The screen's rule is one short
  instruction; a four-line cue with a footnote in it is a readout.
* **The briefing writer never sees a species cue.** `briefing_cue()` hands it a
  hand-written instruction only, because an LLM asked to include a species line
  will restate it more confidently than the evidence supports.
* **Safety outranks novelty.** On hazardous air or 33 °C apparent heat the
  seasonal cues are withheld entirely, so a butterfly cannot displace "find the
  coolest patch of shade".

Recorded snapshots live in `data/seasonal/blr_<year>_<month>.json` and are
committed. Re-record one with:

```bash
uv run python scripts/refresh_seasonal.py          # current month
uv run python scripts/refresh_seasonal.py --all-months
```

Baahar does **not** call iNaturalist at request time. The briefing is meant to be
ready before it is asked for, and a committed snapshot means every claim in the
write-up is traceable to a file.

Species names are iNaturalist taxonomy, used here as pointer labels only -- the
app is not an identification tool and makes no identification claims.

---

## Reproducing the evals

```bash
# 1. dataset (keyless, cached)
uv run python scripts/build_dataset.py --start 2025-11-01 --end 2026-10-05

# 2. tabular go/no-go
uv run python scripts/run_eval.py

# 3. briefings (needs GEMINI_API_KEY)
uv run python scripts/build_briefing_cases.py
uv run python scripts/run_briefing_eval.py --writers template,gemma --no-cache

# 4. offline fixtures (commits the recorded responses)
uv run python scripts/record_samples.py

# 5. UI screenshots + layout audit (needs Chrome or Edge, no npm install)
uv run baahar serve &
node scripts/ui_check.mjs
```

Raw machine-readable output for every run lands in `eval/raw/`. Every number in
`eval/RESULTS.md` and in `post.md` comes from one of those files.