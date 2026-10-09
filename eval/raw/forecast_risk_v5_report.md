# Bounded forecast research v5

Consumed CAMS/ERA5 modeled archive; adaptive research choice informed by previous diagnostics. No adoption.

| Period | Model | Accuracy | Macro-F1 | Poor+ misses | Poor+ FAR | Severe+ misses | Severe+ FAR |
|---|---|---:|---:|---:|---:|---:|---:|
| development | incumbent | 0.8409 | 0.6552 | 14/16 | 0.0015426808364758314 | 0/0 | 0.0 |
| development | challenger | 0.847 | 0.6703 | 14/16 | 0.0005142269454919438 | 0/0 | 0.0 |
| diagnostic_pollution | incumbent | 0.7638 | 0.4772 | 144/248 | 0.018065887353878853 | 11/11 | 0.004247286455875413 |
| diagnostic_pollution | challenger | 0.7596 | 0.4691 | 136/248 | 0.024442082890541977 | 11/11 | 0.0018876828692779614 |
| diagnostic_other_seasons | incumbent | 0.8306 | 0.5696 | 10/23 | 0.004666483667307164 | 2/2 | 0.0002729257641921397 |
| diagnostic_other_seasons | challenger | 0.8312 | 0.5435 | 12/23 | 0.005764479824320615 | 2/2 | 0.0 |

Class probabilities are uncalibrated; hybrid quantile floor has no risk probability. Support is correlated hourly archive data. No prospective, station, field, medical or billing claim.
