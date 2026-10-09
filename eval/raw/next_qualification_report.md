# Follow-up qualification

Measured hosted diagnostics; no promotion.

## Rolling forecast diagnostics

Consumed archive, fixed previously selected configurations, seed 0. Six-hour label embargo and train-only imputation. Aligned recorded target-hour weather is oracle weather, not deployed forecast evidence.


**2026-02 class support (n=672):** good 16, satisfactory 325, moderate 298, poor 33, severe 0, hazardous 0

| Window | Model | N | Accuracy | Macro-F1 | Moderate recall (support) | Poor-or-worse underprediction |
|---|---|---:|---:|---:|---:|---:|
| 2026-02 | majority | 672 | 0.4836 | 0.163 | 0.0 (298) | 33/33 |
| 2026-02 | persistence | 672 | 0.4092 | 0.2307 | 0.5537 (298) | 31/33 |
| 2026-02 | lgbm | 672 | 0.7113 | 0.4024 | 0.594 (298) | 32/33 |
| 2026-02 | ensemble | 672 | 0.7232 | 0.3977 | 0.7013 (298) | 33/33 |

**2026-04 class support (n=720):** good 10, satisfactory 326, moderate 260, poor 117, severe 7, hazardous 0

| Window | Model | N | Accuracy | Macro-F1 | Moderate recall (support) | Poor-or-worse underprediction |
|---|---|---:|---:|---:|---:|---:|
| 2026-04 | majority | 720 | 0.4528 | 0.1247 | 0.0 (260) | 124/124 |
| 2026-04 | persistence | 720 | 0.175 | 0.0938 | 0.2923 (260) | 116/124 |
| 2026-04 | lgbm | 720 | 0.6972 | 0.3645 | 0.6423 (260) | 96/124 |
| 2026-04 | ensemble | 720 | 0.7 | 0.3789 | 0.6731 (260) | 87/124 |

**2026-06 class support (n=720):** good 365, satisfactory 306, moderate 47, poor 2, severe 0, hazardous 0

| Window | Model | N | Accuracy | Macro-F1 | Moderate recall (support) | Poor-or-worse underprediction |
|---|---|---:|---:|---:|---:|---:|
| 2026-06 | majority | 720 | 0.425 | 0.1491 | 0.0 (47) | 2/2 |
| 2026-06 | persistence | 720 | 0.3153 | 0.2086 | 0.2128 (47) | 2/2 |
| 2026-06 | lgbm | 720 | 0.725 | 0.4969 | 0.7234 (47) | 2/2 |
| 2026-06 | ensemble | 720 | 0.6403 | 0.4264 | 0.8298 (47) | 2/2 |

**2026-08 class support (n=744):** good 512, satisfactory 232, moderate 0, poor 0, severe 0, hazardous 0

| Window | Model | N | Accuracy | Macro-F1 | Moderate recall (support) | Poor-or-worse underprediction |
|---|---|---:|---:|---:|---:|---:|
| 2026-08 | majority | 744 | 0.3118 | 0.2377 | N/A (0) | 0/0 |
| 2026-08 | persistence | 744 | 0.3656 | 0.3306 | N/A (0) | 0/0 |
| 2026-08 | lgbm | 744 | 0.9449 | 0.9378 | N/A (0) | 0/0 |
| 2026-08 | ensemble | 744 | 0.9489 | 0.9423 | N/A (0) | 0/0 |

Missing hazardous examples remain unvalidated. Poor-or-worse underprediction is a band error, not proof of an actual unsafe invitation; current-hour runtime permission remains deterministic.

## Fresh synthetic briefing evaluation

New AI-authored synthetic prompts; some families overlap training. Updated current-condition prompt; not blind human review or a pristine holdout.

| Family | N | Adapter raw | Fallback raw | Adapter combined | Fallback combined | Adapter safety flags | Median GPU seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| current_go | 6 | 6 | 6 | 6 | 6 | 0 | 5.014 |
| current_heat_future_window | 6 | 4 | 6 | 4 | 6 | 2 | 5.527 |
| current_pollution_future_window | 6 | 6 | 6 | 6 | 6 | 0 | 5.262 |
| missing_air | 6 | 6 | 6 | 6 | 6 | 0 | 5.408 |
| night_storm | 6 | 6 | 6 | 6 | 6 | 0 | 5.678 |
| partial_weather | 6 | 6 | 6 | 6 | 6 | 0 | 5.513 |
| stale_assessment | 6 | 6 | 6 | 6 | 6 | 0 | 5.697 |
| untrusted_note | 6 | 6 | 6 | 6 | 6 | 0 | 5.378 |

All raw prose and finite flags are preserved. These checks do not measure human usefulness or authorize deployment.

Overall raw contract acceptance: adapter 46/48; fallback 48/48. Combined finite acceptance (contract plus anchors): adapter 46/48; fallback 48/48. Semantic-anchor flags: adapter 0, fallback 0. Six current-GO positives: adapter 6/6 combined accepted.

Two adapter finite flags are `ungrounded_number` for `recheck at 5 PM` / `5:00 PM` on supplied scheduled time 17:00. Both texts withhold walking, identify extreme heat, and ask for a recheck. Treat as a finite time-format allowlist limitation, not an observed safety invitation. Raw flags remain recorded. No other current/future value mixing was observed in these 48 outputs.
