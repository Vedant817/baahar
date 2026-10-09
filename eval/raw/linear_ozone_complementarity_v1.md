# Matched development linear ozone complementarity

Exact shared origins/targets: 1411; V3 boundary origins excluded: 24.

Fixed hybrid substitutes Ridge ozone only, retaining V3's other five pollutants. No averaging weight or threshold sweep. Both trained forecasts are frozen; training origin sets differ by24 boundary origins.

| Model | Accuracy | Common macroF1 | Poor+ misses / false alarms | Poor+ episodes / onset hits | VeryPoor+ misses / false alarms | Ozone Poor+ MAE / bias |
|---|---:|---:|---|---|---|---|
| v3_fixed_mean | 0.742027 | 0.574439 | 62/168 / 15 | 21/28 / 5 | 22/22 / 1 | 21.861 / -20.135 |
| ridge_24h | 0.759745 | 0.638596 | 64/168 / 23 | 21/28 / 13 | 18/22 / 2 | 19.056 / -16.251 |
| fixed_ozone_hybrid | 0.748405 | 0.629178 | 64/168 / 23 | 21/28 / 13 | 18/22 / 2 | 19.056 / -16.251 |
| paired_lightgbm | 0.739192 | 0.558465 | 79/168 / 15 | 21/28 / 11 | 22/22 / 0 | 25.198 / -24.865 |
| persistence | 0.364989 | 0.257825 | 146/168 / 146 | 13/28 / 0 | 22/22 / 22 | 91.988 / -88.607 |

Adaptive descriptive development screen; no fit or diagnostic/test selection
Probe training excludes24 boundary origins compared with V3; algorithms were not trained on identical origin sets
Common macroF1 uses actual/predicted union, unlike original neural reporter
Consumed CAMS/ERA5 modeled archive; no station/pristine/prospective/medical claim
Legacy severe means official Very Poor; hazardous means official Severe; zero support recall UNMEASURED
Point predictions have no probability calibration; Brier/ECE null

Input/result hashes, canonical checks, exact arrays, all six gas errors and risk precision/recall/FAR/episodes are in the JSON. This screen does not establish generalization or deployment readiness.
