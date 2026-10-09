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
