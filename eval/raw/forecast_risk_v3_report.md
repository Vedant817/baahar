# Rare-air forecast experiment

Research-only coverage ablation on consumed archive diagnostics; no station, prospective or medical-safety claim.

| Period | Model | N | Accuracy | Macro-F1 | Poor+ misses/support | Recall | False-alarm rate | Precision | Brier | ECE |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| diagnostic_pollution | historical_train_ordinary | 2130 | 0.7366 | 0.4258 | 221/248 | 0.10887096774193548 | 0.004250797024442083 | 0.7714285714285715 | 0.09236 | 0.09293 |
| diagnostic_pollution | historical_train_risk_weighted | 2130 | 0.7423 | 0.4606 | 200/248 | 0.1935483870967742 | 0.009032943676939426 | 0.7384615384615385 | 0.08826 | 0.08688 |
| diagnostic_pollution | expanded_train_ordinary | 2130 | 0.7592 | 0.4653 | 174/248 | 0.29838709677419356 | 0.011689691817215728 | 0.7708333333333334 | 0.07135 | 0.06518 |
| diagnostic_pollution | expanded_train_risk_weighted | 2130 | 0.7638 | 0.4848 | 144/248 | 0.41935483870967744 | 0.020722635494155154 | 0.7272727272727273 | 0.06473 | 0.04866 |
| diagnostic_pollution | expanded_ensemble | 2130 | 0.7488 | 0.4837 | 155/248 | 0.375 | 0.015409139213602551 | 0.7622950819672131 | 0.08638 | 0.08638 |
| diagnostic_pollution | instantaneous_persistence | 2130 | 0.3864 | 0.2113 | 231/248 | 0.06854838709677419 | 0.12274176408076515 | 0.06854838709677419 | 0.21690 | 0.21690 |
| diagnostic_pollution | conservative_persistence_diagnostic | 2130 | 0.2812 | 0.1381 | 231/248 | 0.06854838709677419 | 0.15834218916046758 | 0.05396825396825397 | 0.24836 | 0.24836 |
| diagnostic_other_seasons | historical_train_ordinary | 3666 | 0.8183 | 0.5075 | 19/23 | 0.17391304347826086 | 0.0016469942355201758 | 0.4 | 0.00589 | 0.00586 |
| diagnostic_other_seasons | historical_train_risk_weighted | 3666 | 0.8151 | 0.5001 | 20/23 | 0.13043478260869565 | 0.002744990392533626 | 0.23076923076923078 | 0.00641 | 0.00636 |
| diagnostic_other_seasons | expanded_train_ordinary | 3666 | 0.8301 | 0.5612 | 13/23 | 0.43478260869565216 | 0.0038429865495470767 | 0.4166666666666667 | 0.00479 | 0.00330 |
| diagnostic_other_seasons | expanded_train_risk_weighted | 3666 | 0.8295 | 0.569 | 11/23 | 0.5217391304347826 | 0.004666483667307164 | 0.41379310344827586 | 0.00555 | 0.00460 |
| diagnostic_other_seasons | expanded_ensemble | 3666 | 0.8271 | 0.5683 | 12/23 | 0.4782608695652174 | 0.0041174855888004395 | 0.4230769230769231 | 0.00736 | 0.00736 |
| diagnostic_other_seasons | instantaneous_persistence | 3666 | 0.4506 | 0.2491 | 22/23 | 0.043478260869565216 | 0.0060389788635739775 | 0.043478260869565216 | 0.01200 | 0.01200 |
| diagnostic_other_seasons | conservative_persistence_diagnostic | 3666 | 0.3325 | 0.1959 | 22/23 | 0.043478260869565216 | 0.006587976942080703 | 0.04 | 0.01255 | 0.01255 |

## Severe-or-worse diagnostics

| Period | Model | Misses/support | Recall | False-alarm rate | Precision | Brier | ECE |
|---|---|---:|---:|---:|---:|---:|---:|
| diagnostic_pollution | historical_train_ordinary | 11/11 | 0.0 | 0.0 | None | 0.00516 | 0.00516 |
| diagnostic_pollution | historical_train_risk_weighted | 11/11 | 0.0 | 0.0 | None | 0.00516 | 0.00516 |
| diagnostic_pollution | expanded_train_ordinary | 11/11 | 0.0 | 0.0037753657385559227 | 0.0 | 0.00721 | 0.00868 |
| diagnostic_pollution | expanded_train_risk_weighted | 11/11 | 0.0 | 0.0033034450212364322 | 0.0 | 0.00739 | 0.00787 |
| diagnostic_pollution | expanded_ensemble | 11/11 | 0.0 | 0.004719207173194903 | 0.0 | 0.00986 | 0.00986 |
| diagnostic_pollution | instantaneous_persistence | 11/11 | 0.0 | 0.005191127890514393 | 0.0 | 0.01033 | 0.01033 |
| diagnostic_pollution | conservative_persistence_diagnostic | 11/11 | 0.0 | 0.005191127890514393 | 0.0 | 0.01033 | 0.01033 |
| diagnostic_other_seasons | historical_train_ordinary | 2/2 | 0.0 | 0.0 | None | 0.00055 | 0.00055 |
| diagnostic_other_seasons | historical_train_risk_weighted | 2/2 | 0.0 | 0.0 | None | 0.00055 | 0.00055 |
| diagnostic_other_seasons | expanded_train_ordinary | 2/2 | 0.0 | 0.0 | None | 0.00056 | 0.00052 |
| diagnostic_other_seasons | expanded_train_risk_weighted | 2/2 | 0.0 | 0.0 | None | 0.00063 | 0.00070 |
| diagnostic_other_seasons | expanded_ensemble | 2/2 | 0.0 | 0.0 | None | 0.00055 | 0.00055 |
| diagnostic_other_seasons | instantaneous_persistence | 2/2 | 0.0 | 0.0005458515283842794 | 0.0 | 0.00109 | 0.00109 |
| diagnostic_other_seasons | conservative_persistence_diagnostic | 2/2 | 0.0 | 0.0005458515283842794 | 0.0 | 0.00109 | 0.00109 |

Coverage ablation uses fixed configurations without calibration or threshold selection. Persistence/ensemble Brier and ECE use binary decisions; LightGBM uses uncalibrated class probabilities. Periods are consumed diagnostics; no policy or deployment weather accuracy is assessed.

## Selection and support

```json
{
  "selection": {
    "band_weight": "fixed [1,1,1,4,16,16]",
    "binary_weight": null,
    "threshold": null,
    "risk_floor_enabled": false
  },
  "partition_support": {
    "historical_train": {
      "n": 8748,
      "bands": {
        "moderate": 1836,
        "satisfactory": 4373,
        "good": 2423,
        "poor": 116
      },
      "first_time": "2023-01-01T06:00",
      "last_time": "2023-12-31T17:00",
      "poor_or_worse_episodes": {
        "positive_hours": 116,
        "episode_count": 35,
        "episode_sizes": [
          3,
          3,
          3,
          1,
          5,
          1,
          5,
          5,
          7,
          4,
          2,
          4,
          4,
          4,
          2,
          7,
          1,
          5,
          3,
          3,
          2,
          4,
          3,
          2,
          4,
          5,
          1,
          3,
          3,
          1,
          2,
          3,
          4,
          4,
          3
        ],
        "largest_episode_fraction": 0.0603448275862069,
        "separation_hours": 6
      },
      "severe_or_worse_episodes": {
        "positive_hours": 0,
        "episode_count": 0,
        "episode_sizes": [],
        "largest_episode_fraction": null,
        "separation_hours": 6
      }
    },
    "expanded_train": {
      "n": 21132,
      "bands": {
        "moderate": 4810,
        "satisfactory": 10504,
        "good": 5349,
        "poor": 442,
        "severe": 27
      },
      "first_time": "2023-01-01T06:00",
      "last_time": "2025-05-31T17:00",
      "poor_or_worse_episodes": {
        "positive_hours": 469,
        "episode_count": 115,
        "episode_sizes": [
          3,
          3,
          3,
          1,
          5,
          1,
          5,
          5,
          7,
          4,
          2,
          4,
          4,
          4,
          2,
          7,
          1,
          5,
          3,
          3,
          2,
          4,
          3,
          2,
          4,
          5,
          1,
          3,
          3,
          1,
          2,
          3,
          4,
          4,
          3,
          3,
          1,
          2,
          3,
          3,
          5,
          2,
          1,
          2,
          4,
          2,
          3,
          2,
          3,
          3,
          2,
          2,
          5,
          5,
          3,
          5,
          5,
          5,
          5,
          2,
          3,
          2,
          2,
          4,
          5,
          3,
          1,
          1,
          3,
          1,
          1,
          3,
          1,
          6,
          8,
          8,
          7,
          1,
          5,
          2,
          4,
          6,
          6,
          6,
          7,
          6,
          5,
          2,
          3,
          6,
          5,
          6,
          5,
          8,
          8,
          7,
          9,
          8,
          7,
          7,
          3,
          6,
          7,
          5,
          6,
          4,
          3,
          7,
          9,
          8,
          8,
          5,
          5,
          4,
          7
        ],
        "largest_episode_fraction": 0.019189765458422176,
        "separation_hours": 6
      },
      "severe_or_worse_episodes": {
        "positive_hours": 27,
        "episode_count": 6,
        "episode_sizes": [
          5,
          6,
          2,
          6,
          5,
          3
        ],
        "largest_episode_fraction": 0.2222222222222222,
        "separation_hours": 6
      }
    },
    "diagnostic_pollution": {
      "n": 2130,
      "bands": {
        "satisfactory": 996,
        "moderate": 854,
        "poor": 237,
        "good": 32,
        "severe": 11
      },
      "first_time": "2026-02-01T00:00",
      "last_time": "2026-04-30T17:00",
      "poor_or_worse_episodes": {
        "positive_hours": 248,
        "episode_count": 49,
        "episode_sizes": [
          7,
          1,
          3,
          5,
          3,
          5,
          2,
          7,
          7,
          4,
          6,
          7,
          7,
          6,
          1,
          1,
          5,
          7,
          5,
          6,
          7,
          7,
          2,
          7,
          3,
          3,
          7,
          6,
          6,
          7,
          6,
          2,
          5,
          5,
          6,
          5,
          5,
          3,
          6,
          8,
          3,
          3,
          3,
          4,
          6,
          8,
          7,
          7,
          6
        ],
        "largest_episode_fraction": 0.03225806451612903,
        "separation_hours": 6
      },
      "severe_or_worse_episodes": {
        "positive_hours": 11,
        "episode_count": 4,
        "episode_sizes": [
          4,
          3,
          2,
          2
        ],
        "largest_episode_fraction": 0.36363636363636365,
        "separation_hours": 6
      }
    },
    "diagnostic_other_seasons": {
      "n": 3666,
      "bands": {
        "satisfactory": 1506,
        "moderate": 383,
        "poor": 21,
        "severe": 2,
        "good": 1754
      },
      "first_time": "2026-05-01T00:00",
      "last_time": "2026-09-30T17:00",
      "poor_or_worse_episodes": {
        "positive_hours": 23,
        "episode_count": 7,
        "episode_sizes": [
          7,
          3,
          5,
          1,
          4,
          1,
          2
        ],
        "largest_episode_fraction": 0.30434782608695654,
        "separation_hours": 6
      },
      "severe_or_worse_episodes": {
        "positive_hours": 2,
        "episode_count": 1,
        "episode_sizes": [
          2
        ],
        "largest_episode_fraction": 1.0,
        "separation_hours": 6
      }
    }
  },
  "forecast_target_contract": {
    "target_basis": "instantaneous_naqi",
    "horizon_hours": 6,
    "target_column": "target_band",
    "current_effective_naqi": "conservative feature and policy diagnostic; not matching persistence"
  },
  "training_unsupported_classes": {
    "diagnostic_pollution": {},
    "diagnostic_other_seasons": {}
  }
}
```
