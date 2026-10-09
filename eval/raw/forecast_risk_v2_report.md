# Rare-air forecast experiment

Research-only, no automatic promotion. New modelled archive periods; not station-accuracy or medical-safety evidence.

| Period | Model | N | Accuracy | Macro-F1 | Poor+ misses/support | Recall | False-alarm rate | Precision | Brier | ECE |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| locked_pollution | persistence | 2130 | 0.3042 | 0.1506 | 185/205 | 0.0975609756097561 | 0.12727272727272726 | 0.07547169811320754 | 0.20188 | 0.20188 |
| locked_pollution | lightgbm_baseline | 2130 | 0.7469 | 0.4031 | 164/205 | 0.2 | 0.005714285714285714 | 0.7884615384615384 | 0.07244 | 0.06485 |
| locked_pollution | ensemble_baseline | 2130 | 0.7188 | 0.4276 | 156/205 | 0.23902439024390243 | 0.006753246753246753 | 0.7903225806451613 | 0.07934 | 0.07934 |
| locked_pollution | weighted_lightgbm | 2130 | 0.7493 | 0.4346 | 152/205 | 0.25853658536585367 | 0.011428571428571429 | 0.7066666666666667 | 0.07020 | 0.06077 |
| locked_pollution | weighted_plus_risk | 2130 | 0.7418 | 0.4526 | 109/205 | 0.4682926829268293 | 0.04051948051948052 | 0.5517241379310345 | 0.07602 | 0.06654 |
| locked_other_seasons | persistence | 4410 | 0.3862 | 0.2353 | 41/49 | 0.16326530612244897 | 0.01215317587709241 | 0.13114754098360656 | 0.02132 | 0.02132 |
| locked_other_seasons | lightgbm_baseline | 4410 | 0.8211 | 0.4598 | 45/49 | 0.08163265306122448 | 0.000687915615684476 | 0.5714285714285714 | 0.00988 | 0.00961 |
| locked_other_seasons | ensemble_baseline | 4410 | 0.8061 | 0.4484 | 44/49 | 0.10204081632653061 | 0.0016051364365971107 | 0.4166666666666667 | 0.01156 | 0.01156 |
| locked_other_seasons | weighted_lightgbm | 4410 | 0.8188 | 0.4622 | 41/49 | 0.16326530612244897 | 0.001375831231368952 | 0.5714285714285714 | 0.00975 | 0.00931 |
| locked_other_seasons | weighted_plus_risk | 4410 | 0.8181 | 0.4786 | 35/49 | 0.2857142857142857 | 0.002751662462737904 | 0.5384615384615384 | 0.00954 | 0.00452 |

Brier/ECE for persistence and ensemble use binary band decisions, not calibrated probabilities. Target-hour policy weather is oracle recorded data. Calibration and threshold selection precede both locked periods.

## Selection and support

```json
{
  "selection": {
    "band_weight": 4,
    "binary_weight": 4,
    "threshold": 0.1,
    "risk_floor_enabled": true
  },
  "partition_support": {
    "train": {
      "n": 8748,
      "bands": {
        "moderate": 1836,
        "satisfactory": 4373,
        "good": 2423,
        "poor": 116
      },
      "first_time": "2023-01-01T06:00",
      "last_time": "2023-12-31T17:00"
    },
    "locked_pollution": {
      "n": 2130,
      "bands": {
        "satisfactory": 1070,
        "moderate": 788,
        "good": 67,
        "poor": 192,
        "severe": 13
      },
      "first_time": "2025-02-01T00:00",
      "last_time": "2025-04-30T17:00"
    },
    "locked_other_seasons": {
      "n": 4410,
      "bands": {
        "satisfactory": 1700,
        "moderate": 294,
        "poor": 35,
        "severe": 14,
        "good": 2367
      },
      "first_time": "2025-05-01T00:00",
      "last_time": "2025-10-31T17:00"
    },
    "development": {
      "n": 1620,
      "bands": {
        "moderate": 480,
        "satisfactory": 1073,
        "good": 47,
        "poor": 20
      },
      "first_time": "2024-01-01T06:00",
      "last_time": "2024-03-08T17:00"
    },
    "calibration": {
      "n": 1050,
      "bands": {
        "satisfactory": 578,
        "moderate": 397,
        "poor": 21,
        "good": 54
      },
      "first_time": "2024-03-09T00:00",
      "last_time": "2024-04-21T17:00"
    },
    "threshold_selection": {
      "n": 6822,
      "bands": {
        "satisfactory": 3072,
        "moderate": 1119,
        "good": 2570,
        "poor": 61
      },
      "first_time": "2024-04-22T00:00",
      "last_time": "2025-01-31T17:00"
    }
  }
}
```
