## V3 coverage ablation completed

Fixed configurations compare 2023-only training against January 2023–May 2025 training. The latter includes previously evaluated 2025 examples. The 2026 periods have informed prior research and are consumed temporal diagnostics, not independent holdouts.

| Period | Model | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ recall | Poor+ FAR | Severe+ misses/support | Severe+ recall | Severe+ FAR |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| diagnostic_pollution | historical_train_ordinary | 0.7366 | 0.4258 | 221/248 | 0.10887096774193548 | 0.004250797024442083 | 11/11 | 0.0 | 0.0 |
| diagnostic_pollution | historical_train_risk_weighted | 0.7423 | 0.4606 | 200/248 | 0.1935483870967742 | 0.009032943676939426 | 11/11 | 0.0 | 0.0 |
| diagnostic_pollution | expanded_train_ordinary | 0.7592 | 0.4653 | 174/248 | 0.29838709677419356 | 0.011689691817215728 | 11/11 | 0.0 | 0.0037753657385559227 |
| diagnostic_pollution | expanded_train_risk_weighted | 0.7638 | 0.4848 | 144/248 | 0.41935483870967744 | 0.020722635494155154 | 11/11 | 0.0 | 0.0033034450212364322 |
| diagnostic_pollution | expanded_ensemble | 0.7488 | 0.4837 | 155/248 | 0.375 | 0.015409139213602551 | 11/11 | 0.0 | 0.004719207173194903 |
| diagnostic_pollution | instantaneous_persistence | 0.3864 | 0.2113 | 231/248 | 0.06854838709677419 | 0.12274176408076515 | 11/11 | 0.0 | 0.005191127890514393 |
| diagnostic_pollution | conservative_persistence_diagnostic | 0.2812 | 0.1381 | 231/248 | 0.06854838709677419 | 0.15834218916046758 | 11/11 | 0.0 | 0.005191127890514393 |
| diagnostic_other_seasons | historical_train_ordinary | 0.8183 | 0.5075 | 19/23 | 0.17391304347826086 | 0.0016469942355201758 | 2/2 | 0.0 | 0.0 |
| diagnostic_other_seasons | historical_train_risk_weighted | 0.8151 | 0.5001 | 20/23 | 0.13043478260869565 | 0.002744990392533626 | 2/2 | 0.0 | 0.0 |
| diagnostic_other_seasons | expanded_train_ordinary | 0.8301 | 0.5612 | 13/23 | 0.43478260869565216 | 0.0038429865495470767 | 2/2 | 0.0 | 0.0 |
| diagnostic_other_seasons | expanded_train_risk_weighted | 0.8295 | 0.569 | 11/23 | 0.5217391304347826 | 0.004666483667307164 | 2/2 | 0.0 | 0.0 |
| diagnostic_other_seasons | expanded_ensemble | 0.8271 | 0.5683 | 12/23 | 0.4782608695652174 | 0.0041174855888004395 | 2/2 | 0.0 | 0.0 |
| diagnostic_other_seasons | instantaneous_persistence | 0.4506 | 0.2491 | 22/23 | 0.043478260869565216 | 0.0060389788635739775 | 2/2 | 0.0 | 0.0005458515283842794 |
| diagnostic_other_seasons | conservative_persistence_diagnostic | 0.3325 | 0.1959 | 22/23 | 0.043478260869565216 | 0.006587976942080703 | 2/2 | 0.0 | 0.0005458515283842794 |

### Coverage and episodes

```json
{
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
}
```

Adjacent polluted hours are correlated; episode counts use a six-hour separation rule and are descriptive, not independent-event validation. Absent positive support means recall is unmeasured. Models with no training support cannot establish that class's performance.

All LightGBM probabilities are uncalibrated; ensemble and persistence probability-style metrics use binary decisions. Full precision, Brier, ECE and reliability bins are retained in the raw result and completion summary. No weather-policy accuracy is assessed. CAMS/ERA5 archives are modeled data, not station observations. Human review, field evidence and actual billing are unmeasured. No model was promoted or deployed.


### Measured v3 disposition

Matched weighted models improve from 0.7423 to 0.7638 accuracy and 0.4606 to 0.4848 macro-F1 on February–April 2026; poor-or-worse misses fall from 200/248 to 144/248, with false alarms increasing from 17 to 39. On May–September, accuracy improves from 0.8151 to 0.8295 and macro-F1 from 0.5001 to 0.5690; misses fall from 20/23 to 11/23, with false alarms increasing from 10 to 17. Poor+ Brier/ECE improve against the old weighted model on both windows, but in the later window ordinary expanded LightGBM has lower Brier/ECE than expanded weighted LightGBM. This is a tradeoff, not universal model superiority.

Expanded training contains 469 poor-or-worse hours in 115 episodes, including 27 severe hours in six episodes, using the descriptive six-hour gap rule. All candidates still predict below severe on all 11 severe hours in the pollution window and both severe hours in the later window. Hazardous training/evaluation support is zero; hazardous recall is unmeasured. Expanded weighted training now emits some severe predictions, but its seven pollution-window severe alerts are all false positives. Severe forecasting remains unresolved, so this candidate is research-only and not qualified for adoption. These are consumed modeled archive diagnostics; no human, field, medical or prospective claim follows.

The completed monitor is disabled. Offline pytest, nine focused forecast tests and Ruff passed. No serving artifact or model deployment changed; actual billed costs remain unmeasured.
