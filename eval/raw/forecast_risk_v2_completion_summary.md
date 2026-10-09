## Rare-air forecast v2 — completed

Modal call `fc-01M4E89CB1TT1N2GGXADVB367G` completed. The source and row hashes, resolved boundaries, full predictions and per-model outputs are in [the raw result](../eval/raw/forecast_risk_v2_results.json); the metric table is in [the experiment report](../eval/raw/forecast_risk_v2_report.md).

| Locked period | Model | N | Accuracy | Macro-F1 | Poor+ misses / support | Recall | False-alarm rate | Precision | Brier | ECE |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| locked_pollution | persistence | 2130 | 0.3042 | 0.1506 | 185/205 | 0.0976 | 0.1273 | 0.0755 | 0.20188 | 0.20188 |
| locked_pollution | lightgbm_baseline | 2130 | 0.7469 | 0.4031 | 164/205 | 0.2000 | 0.0057 | 0.7885 | 0.07244 | 0.06485 |
| locked_pollution | ensemble_baseline | 2130 | 0.7188 | 0.4276 | 156/205 | 0.2390 | 0.0068 | 0.7903 | 0.07934 | 0.07934 |
| locked_pollution | weighted_lightgbm | 2130 | 0.7493 | 0.4346 | 152/205 | 0.2585 | 0.0114 | 0.7067 | 0.07020 | 0.06077 |
| locked_pollution | weighted_plus_risk | 2130 | 0.7418 | 0.4526 | 109/205 | 0.4683 | 0.0405 | 0.5517 | 0.07602 | 0.06654 |
| locked_other_seasons | persistence | 4410 | 0.3862 | 0.2353 | 41/49 | 0.1633 | 0.0122 | 0.1311 | 0.02132 | 0.02132 |
| locked_other_seasons | lightgbm_baseline | 4410 | 0.8211 | 0.4598 | 45/49 | 0.0816 | 0.0007 | 0.5714 | 0.00988 | 0.00961 |
| locked_other_seasons | ensemble_baseline | 4410 | 0.8061 | 0.4484 | 44/49 | 0.1020 | 0.0016 | 0.4167 | 0.01156 | 0.01156 |
| locked_other_seasons | weighted_lightgbm | 4410 | 0.8188 | 0.4622 | 41/49 | 0.1633 | 0.0014 | 0.5714 | 0.00975 | 0.00931 |
| locked_other_seasons | weighted_plus_risk | 4410 | 0.8181 | 0.4786 | 35/49 | 0.2857 | 0.0028 | 0.5385 | 0.00954 | 0.00452 |

Selection: band weight 4, binary weight 4, risk threshold 0.1; risk floor enabled: True.

Development support was 20 poor-or-worse / 1,620 rows; calibration support was 21 / 1,050; threshold-selection support was 61 / 6,822. Resolved periods: development 2024-01-01 to 2024-03-09; calibration 2024-03-09 to 2024-04-22; threshold selection 2024-04-22 to 2025-02-01. Minimum support counts hourly observations, which are correlated, not independent events.

On February–April, the hybrid reduced poor-or-worse misses from 152/205 for weighted LightGBM to 109/205, while accuracy fell from 0.7493 to 0.7418 and false-alarm rate rose from 0.0114 to 0.0405. On May–October, it reduced misses from 41/49 to 35/49, with accuracy 0.8188 to 0.8181 and false-alarm rate 0.0014 to 0.0028. This is a useful archive tradeoff for rare-air research, not proof of a general performance or safety improvement. The later period has only 49 poor-or-worse hours.

Brier/ECE are comparable as probability metrics for the calibrated hybrid and class-probability models; persistence and ensemble use binary decisions and their Brier/ECE are not calibrated-probability assessments. Forecasts use CAMS archive output and ERA5 reanalysis, not station measurements. Target-hour weather used in policy diagnostics is oracle recorded weather. The split protocol was informed by prior consumed archive diagnostics and adapts development boundaries to label support. Locked periods remain untouched for selection. No human review, field validation, measured billing, deployment, or promotion is claimed. See [completion summary](forecast_risk_v2_completion_summary.json).
