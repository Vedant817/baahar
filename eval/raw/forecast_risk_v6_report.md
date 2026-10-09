# Bounded forecast research v6

Consumed CAMS/ERA5 modeled archive; adaptive research choice informed by previous diagnostics. No adoption.

| Period | Model | Accuracy | Macro-F1 | Poor+ misses | Poor+ FAR | Severe+ misses | Severe+ FAR |
|---|---|---:|---:|---:|---:|---:|---:|
| development | incumbent | 0.8409 | 0.6552 | 14/16 | 0.0015426808364758314 | 0/0 | 0.0 |
| development | challenger | 0.8337 | 0.6729 | 5/16 | 0.010284538909838875 | 0/0 | 0.0 |
| diagnostic_pollution | incumbent | 0.7638 | 0.4772 | 144/248 | 0.018065887353878853 | 11/11 | 0.004247286455875413 |
| diagnostic_pollution | challenger | 0.7592 | 0.5045 | 24/248 | 0.08607863974495218 | 11/11 | 0.004247286455875413 |
| diagnostic_other_seasons | incumbent | 0.8306 | 0.5696 | 10/23 | 0.004666483667307164 | 2/2 | 0.0002729257641921397 |
| diagnostic_other_seasons | challenger | 0.82 | 0.5262 | 3/23 | 0.017293439472961844 | 2/2 | 0.0002729257641921397 |

Class probabilities are uncalibrated; hybrid quantile floor has no risk probability. Support is correlated hourly archive data. No prospective, station, field, medical or billing claim.
