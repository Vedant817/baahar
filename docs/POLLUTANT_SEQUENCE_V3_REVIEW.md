# V3 measured review and qualification decision

The source-pinned v3 run completed under Modal call `fc-01M4FH3RPFGP8WW3B4HP033708`, app `ap-DSoWADIe18ypb2ODCLkHhC`. Its saved result hash matches the manifest and completion summary. Remote training/evaluation elapsed 209.000 seconds; billed cost is UNMEASURED. The training-only weight check observed exactly 296 weighted Poor+ origins among 19,663 training origins. The fixed ensemble is the preregistered three-seed mean; no seed was selected on diagnostic outcomes.

## Paired fixed-ensemble results

| Metric | Pollution diagnostic, support n=2,107 | Other-season diagnostic, support n=3,643 |
|---|---:|---:|
| Poor+ target hours | 248 | 16 |
| Poor+ misses, v1 → v3 | 111/248 → 88/248 | 12/16 → 6/16 |
| Poor+ recall, v1 → v3 | 0.5524 → 0.6452 | 0.2500 → 0.6250 |
| Poor+ precision, v1 → v3 | 0.7697 → 0.7407 | 0.8000 → 0.7692 |
| Poor+ false alarms, v1 → v3 | 41 → 56 | 1 → 3 |
| Poor+ false-alarm rate, v1 → v3 | 0.022055 → 0.030124 | 0.000276 → 0.000827 |
| Positive episodes detected, v1 → v3 | 37/49 → 41/49 | 2/6 → 4/6 |
| Accuracy, v1 → v3 | 0.788799 → 0.791172 | 0.854516 → 0.847928 |
| Macro-F1, v1 → v3 | 0.486780 → 0.486293 | 0.716318 → 0.789472 |
| Very Poor+ misses, v1 → v3 | 11/11 → 11/11 | UNMEASURED (0 positives) |

All six preregistered period guardrails passed for the fixed mean. The Poor-recall-gain branch passed in both periods. The Very Poor episode-gain branch did not: the fixed mean found no new hit in a v1 fully missed episode. Seed 2 alone hit one of four pollution Very Poor episodes, but the three-seed ensemble did not. Do not substitute that diagnostic-selected seed for the preregistered ensemble. Official Severe (401+) support is zero in every phase.

V3 also lowered pollution-period ozone MAE from 11.930 to 11.735 µg/m³ and lowered PM2.5, PM10 and NO2 MAE slightly. SO2 MAE was essentially unchanged (2.407 to 2.408) and CO MAE rose from 81.738 to 82.177. In the later window, most pollutant MAEs changed slightly upward while CO MAE fell from 93.723 to 92.953. The risk-recall gain is therefore accompanied by more false alarms, some loss in common-category accuracy, and mixed pollutant errors.

## Seed variability and limits

Pollution Poor+ misses for seeds 0/1/2 were 99/86/86, with 56/52/59 false alarms; later-window misses were 7/6/9, with 8/20/2 false alarms. This spread reinforces using the preregistered ensemble and reporting seed behavior, not choosing a favored seed from consumed diagnostics. The best development-MAE checkpoint epochs were 20/19/20; stopping epochs were 28/27/28.

These are hourly CPCB-breakpoint proxy predictions over consumed CAMS/ERA5 modeled archive, not station AQI, independent episodes, a fresh prospective holdout, or medical evidence. Positive hours are correlated. Both 2026 diagnostics were used to shape the v1/v2/v3 research sequence. Current reports are adequate to say v3 passed this finite research gate; they do not establish dependable severe-air warnings. Later Very Poor+ and all official Severe recall remain unmeasured, while pollution-period Very Poor+ recall is zero for the fixed mean.

The requested follow-up reviewers did not produce completed reviews: native provider usage was exhausted, Claude could not authenticate, and Grok returned a 402 usage-balance error. Root checked the pinned report, raw SHA, paired gate, per-seed metrics, training support and pollutant errors; this is not presented as multi-agent consensus.

## Next evidence needed

Do not fit another multiplier, loss or architecture against the same consumed 2026 labels. The next justified work is data acquisition and preregistration for a genuinely reserved evaluation: independent CPCB reference-station pollutant measurements with timestamps, quality/coverage metadata and enough Poor+/Very Poor episodes; aligned weather observations; documented access, licensing and source provenance. Keep a contiguous station/time block out of fitting, model selection and thresholds. If that coverage cannot be obtained, retain v1 as the comparator and describe v3 as a research candidate that passed one adaptive retrospective gate. No deployment, automatic promotion, human field evidence, cost claim or global-best-model claim follows.
