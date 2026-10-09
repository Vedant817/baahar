## Bounded forecast research follow-up

Consumed CAMS/ERA5 archive diagnostics; repeated research comparisons, not independent station or prospective validation.

| Round | Period | Candidate | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ false alarms | Poor+ recall | Severe+ misses/support | Episode any-hit |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| forecast_risk_v5 | development | incumbent | 0.8409 | 0.6552 | 14/16 | 9 | 0.125 | 0/0 | 2/7 |
| forecast_risk_v5 | development | challenger | 0.8470 | 0.6703 | 14/16 | 3 | 0.125 | 0/0 | 2/7 |
| forecast_risk_v5 | diagnostic_pollution | incumbent | 0.7638 | 0.4772 | 144/248 | 34 | 0.41935483870967744 | 11/11 | 34/49 |
| forecast_risk_v5 | diagnostic_pollution | challenger | 0.7596 | 0.4691 | 136/248 | 46 | 0.45161290322580644 | 11/11 | 33/49 |
| forecast_risk_v5 | diagnostic_other_seasons | incumbent | 0.8306 | 0.5696 | 10/23 | 17 | 0.5652173913043478 | 2/2 | 4/7 |
| forecast_risk_v5 | diagnostic_other_seasons | challenger | 0.8312 | 0.5435 | 12/23 | 21 | 0.4782608695652174 | 2/2 | 5/7 |
| forecast_risk_v6 | development | incumbent | 0.8409 | 0.6552 | 14/16 | 9 | 0.125 | 0/0 | 2/7 |
| forecast_risk_v6 | development | challenger | 0.8337 | 0.6729 | 5/16 | 60 | 0.6875 | 0/0 | 6/7 |
| forecast_risk_v6 | diagnostic_pollution | incumbent | 0.7638 | 0.4772 | 144/248 | 34 | 0.41935483870967744 | 11/11 | 34/49 |
| forecast_risk_v6 | diagnostic_pollution | challenger | 0.7592 | 0.5045 | 24/248 | 162 | 0.9032258064516129 | 11/11 | 49/49 |
| forecast_risk_v6 | diagnostic_other_seasons | incumbent | 0.8306 | 0.5696 | 10/23 | 17 | 0.5652173913043478 | 2/2 | 4/7 |
| forecast_risk_v6 | diagnostic_other_seasons | challenger | 0.8200 | 0.5262 | 3/23 | 63 | 0.8695652173913043 | 2/2 | 6/7 |

Completed rounds: 2; consecutive rounds without gated gain: 2. Stop reason: two_consecutive_no_gain.

V5 fitted paired classifiers on Modal. V6 evaluated the fixed poor-band floor using existing v4 classifier and quantile weights on Modal, with no refitting; this is one training round and one hosted architecture evaluation, not two training rounds. Exact incumbent and quantile prediction hashes reproduce v4. The reused bundle hash was observed at read time, not independently pinned before its original training.

Gas history improved some hourly metrics but degraded others and did not resolve severe misses. The fixed quantile floor trades fewer poor+ misses for more false alarms; it cannot raise a prediction to severe. No candidate is promoted. Development has zero severe support; training has only 27 severe hours across six descriptive episodes. Hazardous recall remains unmeasured. Full raw probabilities/reliability and predictions are preserved in the linked JSON artifacts. No human, field, medical or billed-cost evidence is claimed. This finite stopping rule does not establish maximum attainable performance.

Evidence: `eval/raw/forecast_risk_v5_results.json`, `eval/raw/forecast_risk_v6_results.json`, their `_gate_summary.json` files, and `eval/raw/forecast_next_completion_summary.json`. Three data, architecture and safety reviews are recorded for each round under `docs/FORECAST_V5_*_REVIEW.md` and `docs/FORECAST_V6_*_REVIEW.md`. Offline pytest and Ruff passed; eight focused checks cover causal features, rounded boundaries, episode regressions and the frozen stopping criteria.

Next research prerequisite: obtain distinct severe development episodes and a separately frozen future evaluation source, then test whether pollutant-specific forecasting generalizes. Repeating parameter changes on these same consumed windows cannot establish that. A larger transformer is not supported by the present evidence. Keep deterministic safety handling and current serving behavior.
