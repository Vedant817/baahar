# Ensemble artifact contract repair report

The reproduced root cause was the dictionary bundle: `getattr(bundle, "n_features_in_")`
returned no width, so inference built 17 columns for a model fitted on 13.
The pre-fix CLI warned and scored every hour with the heuristic.

Changes:
- `src/baahar/score.py:221`: Recorded order is authoritative; legacy component width resolves only known library contracts; missing/unknown contracts raise an actionable error.
- `src/baahar/score.py:249`: Validate every component before prediction; errors name expected and actual widths, artifact path, component, and refit command.
- `src/baahar/score.py:352`: Persist the fitted feature order alongside weights and threshold.
- `scripts/run_eval.py:491`: Pass the exact training columns to the ensemble writer.
- `src/baahar/features.py:180`: Share hour-t derived features between official evaluation and serving.
- `src/baahar/cli.py:146`: Display the model scorer in brief output.
- `tests/test_seasonal.py:479`: Pin the API contract tests to the start of the recorded day; eliminate reproduced wall-clock failures without changing assertions.

The bare LightGBM save/load path remains bare and is tested. Dictionary LightGBM
scoring uses its lgb component with the same contract checks. Safety asymmetry is
unchanged. Runtime exceptions still reach the existing warning and policy fallback.

Adopted **13 features**, correcting the LightGBM docstring. Compact improves
moderate recall but regresses ensemble accuracy and macro-F1. This decision
prioritizes overall accuracy and macro-F1, not maximum moderate recall.
The choice was made on this holdout; it is not independently validated.

Official comparison, every model (accuracy / macro-F1 / moderate recall / skip_as_go):

| Model | Before fix: official 13 | After fix: official 13 | Official 17 |
|---|---|---|---|
| majority | 0.4047 / 0.1441 / 0.0000 / 0.0 | 0.4047 / 0.1441 / 0.0000 / 0.0 | 0.4047 / 0.1441 / 0.0000 / 0.0 |
| persistence | 0.3647 / 0.2492 / 0.2746 / 0.0 | 0.3647 / 0.2492 / 0.2746 / 0.0 | 0.3647 / 0.2492 / 0.2746 / 0.0 |
| logreg | 0.7294 / 0.4850 / 0.3662 / 0.0 | 0.7294 / 0.4850 / 0.3662 / 0.0 | 0.7970 / 0.4644 / 0.1268 / 0.0 |
| rf | 0.8296 / 0.5642 / 0.4296 / 0.0 | 0.8296 / 0.5642 / 0.4296 / 0.0 | 0.8303 / 0.5871 / 0.5423 / 0.0 |
| histgb | 0.8383 / 0.5874 / 0.5493 / 0.0 | 0.8383 / 0.5874 / 0.5493 / 0.0 | 0.8223 / 0.5879 / 0.6338 / 0.0 |
| lgbm | 0.8432 / 0.5825 / 0.4930 / 0.0 | 0.8432 / 0.5825 / 0.4930 / 0.0 | 0.8266 / 0.5813 / 0.5352 / 0.0 |
| ensemble | 0.8487 / 0.6089 / 0.6831 / 0.0 | 0.8487 / 0.6089 / 0.6831 / 0.0 | 0.8192 / 0.5948 / 0.7817 / 0.0 |
| tabpfn | SKIPPED: licence gate | 0.8542 / 0.6031 / 0.5775 / 0.0* | SKIPPED: unsupported in compact |

Before: `eval/raw/gono_20261007T141923+0530.json`.
After/adopted: `eval/raw/gono_20261007T142204+0530.json`.
Compact: `eval/raw/gono_20261007T142032+0530.json`.
There was no official pre-fix compact run; none is fabricated.
The official 13-feature metrics are unchanged by the runtime contract repair.

**YES: 78.17% moderate recall reproduces in the official 17-feature harness.**
This does not imply an overall win: ensemble accuracy is 0.8192 versus 0.8487,
and macro-F1 is 0.5948 versus 0.6089. Moderate recall improves from 0.6831 to 0.7817.

Commands run:

```powershell
uv run python scripts/run_eval.py
uv run python scripts/run_eval.py --feature-set compact
uv run python scripts/run_eval.py
uv run python scripts/check_results.py
```

Section A and all its per-class tables were generated from raw JSON values.
The checker passed unchanged. The initial contract fix runs (141923 and 142204) reported TabPFN SKIPPED on its licence gate; with the token subsequently set, the adopted 5-seed evaluation (gono_20261007T155628+0530.json) ran TabPFN for real on the 13 base features (0.8542 acc / 0.6031 macro-F1 / 0.5775 moderate recall / 0.0 skip_as_go), while compact remained SKIPPED.

*TabPFN was SKIPPED in the initial contract-fix run (142204) on the licence gate, but subsequently evaluated on the adopted 13-feature baseline across 5 seeds in gono_20261007T155628+0530.json.

Saved-model identity: reloaded ensemble and LightGBM reproduce the adopted
holdout confusion matrices on all 1,626 target rows. Hashes and feature order
are recorded in `eval/raw/ensemble_contract_identity.json`.

Acceptance commands below ran with all service keys blank in the subprocess
environment, cache disabled, and no changes to `.env`. Stdout is pasted verbatim;
stderr is empty and every exit code is zero.

The brief initially run with the configured Gemma key attempted a network call
despite `--offline`; it emitted an HTTP 500 warning and fell back to template.
This is separate from ensemble scoring. It is not claimed to be fixed here.

**Acceptance contradiction:** `degraded` cannot be empty on the offline CLI
while preserving the existing fixture provenance contract. The JSON command
shows the two truthful fixture notices. There is no model fallback notice.
All nine returned hours carry `ensemble`; LightGBM tags are checked separately.
Therefore the model bug is repaired, but the literal empty-degraded condition
is not met. It was not coded around.

```powershell
uv run baahar score --offline --scorer ensemble
```

```text

                  Baahar score · Bengaluru · scorer=ensemble                   
 time   call  comfort  NAQI  band          why                                 
 15:00  WAIT       70   103  moderate      Feels like 30 C.                    
 16:00  WAIT       72   105  moderate      41% chance of rain.                 
 17:00  WAIT       73   101  moderate      47% chance of rain.                 
 18:00  WAIT       76    94  satisfactory  45% chance of rain.                 
 19:00  WAIT       80    85  satisfactory  Night-time. Good air, but park      
                                           gates may be shut.                  
 20:00  WAIT       84    74  satisfactory  Night-time. Good air, but park      
                                           gates may be shut.                  
 21:00  WAIT       87    64  satisfactory  Night-time. Good air, but park      
                                           gates may be shut.                  
 22:00  WAIT       90    56  satisfactory  Night-time. Good air, but park      
                                           gates may be shut.                  
 23:00  WAIT       89    59  satisfactory  Night-time. Good air, but park      
                                           gates may be shut.                  

  WAIT: Wait for 22:00.
  Consensus ensemble requested and model artifact loaded.
```

```powershell
uv run baahar score --offline --scorer lgbm
```

```text

                    Baahar score · Bengaluru · scorer=lgbm                     
 time   call  comfort  NAQI  band          why                                 
 15:00  WAIT       70   103  moderate      Feels like 30 C.                    
 16:00  WAIT       72   105  moderate      41% chance of rain.                 
 17:00  WAIT       73   101  moderate      47% chance of rain.                 
 18:00  WAIT       76    94  satisfactory  45% chance of rain.                 
 19:00  WAIT       80    85  satisfactory  Night-time. Good air, but park      
                                           gates may be shut.                  
 20:00  WAIT       84    74  satisfactory  Night-time. Good air, but park      
                                           gates may be shut.                  
 21:00  WAIT       87    64  satisfactory  Night-time. Good air, but park      
                                           gates may be shut.                  
 22:00  WAIT       90    56  satisfactory  Night-time. Good air, but park      
                                           gates may be shut.                  
 23:00  WAIT       89    59  satisfactory  Night-time. Good air, but park      
                                           gates may be shut.                  

  WAIT: Wait for 22:00.
  LightGBM requested and model artifact loaded.
```

```powershell
uv run baahar brief --offline
```

```text

───────────────────────────── Baahar · Bengaluru ──────────────────────────────

  WAIT  Wait for 22:00.

  ! weather from recorded fixture, not a live forecast
  ! air quality from recorded fixture, not a live forecast
  scorer=ensemble
time   call  comfort  NAQI   feels  why                                        
15:00  WAIT       70   103  28/30°  Feels like 30 C.                           
16:00  WAIT       72   105  27/29°  41% chance of rain.                        
17:00  WAIT       73   101  26/29°  47% chance of rain.                        
18:00  WAIT       76    94  25/28°  45% chance of rain.                        
19:00  WAIT       80    85  24/26°  Night-time. Good air, but park gates may be
                                    shut.                                      
20:00  WAIT       84    74  24/25°  Night-time. Good air, but park gates may be
                                    shut.                                      
21:00  WAIT       87    64  22/24°  Night-time. Good air, but park gates may be
                                    shut.                                      
22:00  WAIT       90    56  22/24°  Night-time. Good air, but park gates may be
                                    shut.                                      
23:00  WAIT       89    59  21/24°  Night-time. Good air, but park gates may be
                                    shut.                                      

  Park: Cubbon Park (central)
        Canopy first. Old rain trees, a lot of shade, and the walking crowd 
that makes 6am feel safe. High early morning and Sunday evening; quietest 
weekdays 07:00-09:00.
        Multiple gates; several close around sunset. Check locally before a 
late walk.

  Briefing
  Hold off until 22:00-23:00. Air is clean enough (NAQI 56). It is 22C but
  feels like 24C. 31% chance of rain, so take a light layer. Head to Cubbon
  Park. Canopy first. Once you are out: Count how many different smells the
  rain left behind. Pocket the phone and let it be boring for twenty
  minutes.

  writer=template model=template words=56 latency=8ms

  Pocket Mode
    Not yet.
    No clean hour left in this window.
    notice this: Count how many different smells the rain left behind.
    walk: 20 min
    Nothing unusual. Go enjoy it.

  Informational outdoor planning only. Not medical advice, and not a 
replacement for the official CPCB advisory.

  after the walk: uv run baahar journal --outcome went --note "..."
```

```powershell
uv run baahar score --offline --scorer ensemble --json
```

```text
{
  "city": "Bengaluru",
  "generated_at": "2026-10-07T08:55:52.929997Z",
  "window_hours": 12,
  "overall": "WAIT",
  "best_slot": {
    "time": "2026-10-07T22:00:00",
    "weather": {
      "time": "2026-10-07T22:00:00",
      "temp_c": 21.8,
      "apparent_c": 24.0,
      "precip_mm": 0.0,
      "precip_prob": 31.0,
      "humidity": 90.0,
      "wind_kmh": 11.5,
      "uv_index": 0.0,
      "weather_code": 2,
      "is_day": 0
    },
    "air": {
      "time": "2026-10-07T22:00:00",
      "pm25": 15.8,
      "pm10": 16.2,
      "no2": 32.4,
      "o3": 48.0,
      "co": 546.0,
      "so2": 8.9,
      "nh3": null,
      "pb": null,
      "naqi": 48.0,
      "naqi_trailing": 56.4,
      "naqi_trailing_hours": 8,
      "naqi_band": "satisfactory",
      "naqi_band_label": "Satisfactory",
      "naqi_health_impact": "Minor breathing discomfort to sensitive people.",
      "dominant_pollutant": "o3",
      "dominant_label": "O3",
      "naqi_basis": "cpcb_24h_breakpoints_applied_to_hourly_concentrations+cpcb_breakpoints_applied_to_trailing_period_means",
      "us_aqi_reference": 69.0,
      "naqi_effective": 56.4,
      "naqi_effective_band": "satisfactory",
      "naqi_uses_trailing_mean": true
    },
    "weather_source": "live",
    "air_source": "live"
  },
  "best_time": "2026-10-07T22:00:00",
  "headline": "Wait for 22:00.",
  "slots": [
    {
      "time": "2026-10-07T15:00:00",
      "decision": "WAIT",
      "comfort": 69.7,
      "reasons": [
        "Feels like 30 C."
      ],
      "signals": {
        "naqi": 103.4,
        "naqi_band": "moderate",
        "naqi_instant": 100.0,
        "naqi_trailing": 103.4,
        "naqi_trailing_hours": 8,
        "dominant_pollutant": "O3",
        "pm25": 11.1,
        "pm10": 12.0,
        "temp_c": 28.1,
        "apparent_c": 30.3,
        "precip_mm": 0.0,
        "precip_prob": 32.0,
        "humidity": 56.0,
        "wind_kmh": 9.4,
        "uv_index": 5.5
      },
      "scorer": "ensemble"
    },
    {
      "time": "2026-10-07T16:00:00",
      "decision": "WAIT",
      "comfort": 72.0,
      "reasons": [
        "41% chance of rain."
      ],
      "signals": {
        "naqi": 104.8,
        "naqi_band": "moderate",
        "naqi_instant": 83.3,
        "naqi_trailing": 104.8,
        "naqi_trailing_hours": 8,
        "dominant_pollutant": "O3",
        "pm25": 11.0,
        "pm10": 11.7,
        "temp_c": 27.4,
        "apparent_c": 28.9,
        "precip_mm": 0.0,
        "precip_prob": 41.0,
        "humidity": 57.0,
        "wind_kmh": 9.9,
        "uv_index": 1.2
      },
      "scorer": "ensemble"
    },
    {
      "time": "2026-10-07T17:00:00",
      "decision": "WAIT",
      "comfort": 73.1,
      "reasons": [
        "47% chance of rain."
      ],
      "signals": {
        "naqi": 101.4,
        "naqi_band": "moderate",
        "naqi_instant": 66.7,
        "naqi_trailing": 101.4,
        "naqi_trailing_hours": 8,
        "dominant_pollutant": "O3",
        "pm25": 14.1,
        "pm10": 14.8,
        "temp_c": 26.3,
        "apparent_c": 28.6,
        "precip_mm": 0.0,
        "precip_prob": 47.0,
        "humidity": 64.0,
        "wind_kmh": 6.8,
        "uv_index": 0.35
      },
      "scorer": "ensemble"
    },
    {
      "time": "2026-10-07T18:00:00",
      "decision": "WAIT",
      "comfort": 76.3,
      "reasons": [
        "45% chance of rain."
      ],
      "signals": {
        "naqi": 94.1,
        "naqi_band": "satisfactory",
        "naqi_instant": 54.1,
        "naqi_trailing": 94.1,
        "naqi_trailing_hours": 8,
        "dominant_pollutant": "O3",
        "pm25": 21.5,
        "pm10": 22.1,
        "temp_c": 24.9,
        "apparent_c": 27.6,
        "precip_mm": 0.0,
        "precip_prob": 45.0,
        "humidity": 72.0,
        "wind_kmh": 5.9,
        "uv_index": 0.05
      },
      "scorer": "ensemble"
    },
    {
      "time": "2026-10-07T19:00:00",
      "decision": "WAIT",
      "comfort": 80.1,
      "reasons": [
        "Night-time. Good air, but park gates may be shut."
      ],
      "signals": {
        "naqi": 84.9,
        "naqi_band": "satisfactory",
        "naqi_instant": 61.7,
        "naqi_trailing": 84.9,
        "naqi_trailing_hours": 8,
        "dominant_pollutant": "O3",
        "pm25": 25.0,
        "pm10": 25.6,
        "temp_c": 24.2,
        "apparent_c": 26.4,
        "precip_mm": 0.0,
        "precip_prob": 38.0,
        "humidity": 74.0,
        "wind_kmh": 9.0,
        "uv_index": 0.0
      },
      "scorer": "ensemble"
    },
    {
      "time": "2026-10-07T20:00:00",
      "decision": "WAIT",
      "comfort": 83.9,
      "reasons": [
        "Night-time. Good air, but park gates may be shut."
      ],
      "signals": {
        "naqi": 74.3,
        "naqi_band": "satisfactory",
        "naqi_instant": 66.8,
        "naqi_trailing": 74.3,
        "naqi_trailing_hours": 8,
        "dominant_pollutant": "O3",
        "pm25": 22.5,
        "pm10": 23.0,
        "temp_c": 23.5,
        "apparent_c": 25.4,
        "precip_mm": 0.0,
        "precip_prob": 33.0,
        "humidity": 77.0,
        "wind_kmh": 11.2,
        "uv_index": 0.0
      },
      "scorer": "ensemble"
    },
    {
      "time": "2026-10-07T21:00:00",
      "decision": "WAIT",
      "comfort": 87.3,
      "reasons": [
        "Night-time. Good air, but park gates may be shut."
      ],
      "signals": {
        "naqi": 64.2,
        "naqi_band": "satisfactory",
        "naqi_instant": 58.1,
        "naqi_trailing": 64.2,
        "naqi_trailing_hours": 8,
        "dominant_pollutant": "O3",
        "pm25": 18.4,
        "pm10": 18.9,
        "temp_c": 22.4,
        "apparent_c": 24.5,
        "precip_mm": 0.0,
        "precip_prob": 31.0,
        "humidity": 84.0,
        "wind_kmh": 10.6,
        "uv_index": 0.0
      },
      "scorer": "ensemble"
    },
    {
      "time": "2026-10-07T22:00:00",
      "decision": "WAIT",
      "comfort": 89.7,
      "reasons": [
        "Night-time. Good air, but park gates may be shut."
      ],
      "signals": {
        "naqi": 56.4,
        "naqi_band": "satisfactory",
        "naqi_instant": 48.0,
        "naqi_trailing": 56.4,
        "naqi_trailing_hours": 8,
        "dominant_pollutant": "O3",
        "pm25": 15.8,
        "pm10": 16.2,
        "temp_c": 21.8,
        "apparent_c": 24.0,
        "precip_mm": 0.0,
        "precip_prob": 31.0,
        "humidity": 90.0,
        "wind_kmh": 11.5,
        "uv_index": 0.0
      },
      "scorer": "ensemble"
    },
    {
      "time": "2026-10-07T23:00:00",
      "decision": "WAIT",
      "comfort": 89.2,
      "reasons": [
        "Night-time. Good air, but park gates may be shut."
      ],
      "signals": {
        "naqi": 58.8,
        "naqi_band": "satisfactory",
        "naqi_instant": 58.8,
        "naqi_trailing": 51.2,
        "naqi_trailing_hours": 8,
        "dominant_pollutant": "O3",
        "pm25": 14.6,
        "pm10": 15.1,
        "temp_c": 21.3,
        "apparent_c": 23.9,
        "precip_mm": 0.0,
        "precip_prob": 29.0,
        "humidity": 94.0,
        "wind_kmh": 9.8,
        "uv_index": 0.0
      },
      "scorer": "ensemble"
    }
  ],
  "park": null,
  "scorer": "ensemble",
  "scorer_note": "Consensus ensemble requested and model artifact loaded.",
  "degraded": [
    "weather from recorded fixture, not a live forecast",
    "air quality from recorded fixture, not a live forecast"
  ],
  "weather_source": "fixture",
  "air_source": "fixture"
}
```

Regression reversion proof (original code restored after each mutation):

- Ignore recorded order: two tests fail.
- Remove width validation: six tests fail before any prediction runs.
- Drop serialized feature_order: round-trip test fails with KeyError.

Full mutation outputs: `eval/raw/ensemble_contract_mutations.json`.

Other contradictions and limits:

- Four seasonal API tests failed on the original scorer/features at the current
  clock time; baseline proof is in `eval/raw/ensemble_contract_baseline_failures.json`.
  Their fixture is now anchored to the recorded start, with all assertions kept.
- The current input-band holdout distribution differs from the old publication;
  section A now separates input-band counts from future target support.
- The SKIP metric still has no air-quality-driven SKIP examples: only rain and
  heat. Neither severe nor hazardous is validated by this holdout.
- The existing official harness median-imputes before splitting. This repair
  retains that protocol for a comparable run; it is not new independent validation.
- Concurrent docs work changed README.md, post.md, docs/DOD.md and
  docs/NEEDS_HUMAN.md; those changes are excluded from this implementation commit.
- `scripts/check_docs.py` appeared concurrently with F541 and formatting failures.
  Only ruff mechanical fixes were applied to allow global gates; that new docs
  checker is left outside this implementation commit.

Final validation results are recorded in `eval/raw/ensemble_contract_tests.json`.

Final gates: **465 passed in 46.17s**, with all keys blank and external sockets/DNS
blocked (loopback allowed for Windows asyncio). `uv run ruff check .` passes;
`uv run ruff format --check .` reports all files formatted.
`uv run python scripts/check_results.py` passes. Both model scorers have matching
tags on all nine hours; see `eval/raw/ensemble_contract_hour_tags.json`.
