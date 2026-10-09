# Deep pollutant sequence study: measured results

All candidates were evaluated on identical phase-local 24-hour-context origins. Both 2026 periods are consumed modeled-archive diagnostics, not fresh holdouts. The primary reference is the frozen v1 three-seed concentration-average ensemble. Matched LightGBM remains a secondary comparator.

Historical raw `severe` means official Very Poor (301â€“400); `hazardous` means official Severe (401+). This is an instantaneous concentration proxy, not averaging-compliant station AQI.

| Period | Model | n | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ recall | Poor+ precision | Poor+ FAR | Very Poor+ misses/support | Very Poor+ recall | Very Poor+ FAR | Severe misses/support |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| development | tcn_seed_0 | 1435 | 0.703136 | 0.509053 | 109/168 | 0.351190 | 0.867647 | 0.007103 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | tcn_seed_1 | 1435 | 0.733101 | 0.549333 | 84/168 | 0.500000 | 0.857143 | 0.011050 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | tcn_seed_2 | 1435 | 0.723345 | 0.537784 | 92/168 | 0.452381 | 0.844444 | 0.011050 | 22/22 | 0.000000 | 0.002123 | 0/0 |
| development | tcn_fixed_mean | 1435 | 0.730314 | 0.539391 | 97/168 | 0.422619 | 0.922078 | 0.004736 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | paired_lightgbm | 1435 | 0.743554 | 0.560935 | 79/168 | 0.529762 | 0.855769 | 0.011839 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | persistence | 1435 | 0.364460 | 0.257717 | 146/168 | 0.130952 | 0.130952 | 0.115233 | 22/22 | 0.000000 | 0.015570 | 0/0 |
| development | v1_fixed_mean | 1435 | 0.738676 | 0.562208 | 75/168 | 0.553571 | 0.885714 | 0.009471 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_0 | 2107 | 0.780731 | 0.429600 | 135/248 | 0.455645 | 0.753333 | 0.019903 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_1 | 2107 | 0.789274 | 0.465070 | 119/248 | 0.520161 | 0.796296 | 0.017751 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_2 | 2107 | 0.778358 | 0.488864 | 132/248 | 0.467742 | 0.743590 | 0.021517 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_fixed_mean | 2107 | 0.783579 | 0.464440 | 133/248 | 0.463710 | 0.782313 | 0.017214 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | paired_lightgbm | 2107 | 0.794495 | 0.506529 | 129/248 | 0.479839 | 0.815068 | 0.014524 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | persistence | 2107 | 0.385382 | 0.211169 | 231/248 | 0.068548 | 0.068548 | 0.124260 | 11/11 | 0.000000 | 0.005248 | 0/0 |
| diagnostic_pollution | v1_fixed_mean | 2107 | 0.788799 | 0.486780 | 111/248 | 0.552419 | 0.769663 | 0.022055 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_0 | 3643 | 0.841340 | 0.717388 | 11/16 | 0.312500 | 0.714286 | 0.000551 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_1 | 3643 | 0.844085 | 0.697320 | 12/16 | 0.250000 | 0.571429 | 0.000827 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_2 | 3643 | 0.850673 | 0.617154 | 16/16 | 0.000000 | UNMEASURED | 0.000000 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_fixed_mean | 3643 | 0.849575 | 0.695079 | 13/16 | 0.187500 | 1.000000 | 0.000000 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | paired_lightgbm | 3643 | 0.839967 | 0.664454 | 13/16 | 0.187500 | 0.333333 | 0.001654 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | persistence | 3643 | 0.451551 | 0.299947 | 16/16 | 0.000000 | 0.000000 | 0.004411 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | v1_fixed_mean | 3643 | 0.854516 | 0.716318 | 12/16 | 0.250000 | 0.800000 | 0.000276 | 0/0 | UNMEASURED | 0.000000 | 0/0 |

## Full metric detail

The machine-readable completion summary retains pollutant MAE/RMSE, class support, episode counts, ranking average precision, seed histories and all paired gate checks. Ranking scores are not probabilities; Brier/ECE are unavailable. Missing positive support means recall is unmeasured.

```json
[
  {
    "candidate": "tcn_seed_0",
    "reference": "v1_fixed_mean",
    "research_utility_gate_passed": false,
    "guardrails_passed": false,
    "poor_recall_gain_branch": false,
    "very_poor_episode_gain_branch": false,
    "paired_periods": [
      {
        "partition": "diagnostic_pollution",
        "checks": {
          "accuracy": true,
          "poor_false_alarm_rate": true,
          "very_poor_false_alarm_rate": true,
          "very_poor_misses_nonincreasing": true,
          "poor_episode_any_hits_nondecreasing": true,
          "very_poor_episode_any_hits_nondecreasing": true
        },
        "poor_recall_delta": -0.09677419354838707,
        "paired_very_poor": {
          "new_hits_in_fully_missed_reference_episodes": 0,
          "maximum_new_hits_in_one_reference_missed_episode": 0,
          "newly_detected_reference_missed_episodes": 0
        }
      },
      {
        "partition": "diagnostic_other_seasons",
        "checks": {
          "accuracy": false,
          "poor_false_alarm_rate": true,
          "very_poor_false_alarm_rate": true,
          "very_poor_misses_nonincreasing": true,
          "poor_episode_any_hits_nondecreasing": true,
          "very_poor_episode_any_hits_nondecreasing": true
        },
        "poor_recall_delta": 0.0625,
        "paired_very_poor": {
          "new_hits_in_fully_missed_reference_episodes": 0,
          "maximum_new_hits_in_one_reference_missed_episode": 0,
          "newly_detected_reference_missed_episodes": 0
        }
      }
    ],
    "unsupported_claims": [
      "diagnostic_pollution: official Severe recall UNMEASURED",
      "diagnostic_other_seasons: Very Poor+ recall UNMEASURED",
      "diagnostic_other_seasons: official Severe recall UNMEASURED"
    ],
    "disposition": "RESEARCH_ONLY_NO_AUTOMATIC_PROMOTION"
  },
  {
    "candidate": "tcn_seed_1",
    "reference": "v1_fixed_mean",
    "research_utility_gate_passed": false,
    "guardrails_passed": false,
    "poor_recall_gain_branch": false,
    "very_poor_episode_gain_branch": false,
    "paired_periods": [
      {
        "partition": "diagnostic_pollution",
        "checks": {
          "accuracy": true,
          "poor_false_alarm_rate": true,
          "very_poor_false_alarm_rate": true,
          "very_poor_misses_nonincreasing": true,
          "poor_episode_any_hits_nondecreasing": false,
          "very_poor_episode_any_hits_nondecreasing": true
        },
        "poor_recall_delta": -0.032258064516129004,
        "paired_very_poor": {
          "new_hits_in_fully_missed_reference_episodes": 0,
          "maximum_new_hits_in_one_reference_missed_episode": 0,
          "newly_detected_reference_missed_episodes": 0
        }
      },
      {
        "partition": "diagnostic_other_seasons",
        "checks": {
          "accuracy": false,
          "poor_false_alarm_rate": true,
          "very_poor_false_alarm_rate": true,
          "very_poor_misses_nonincreasing": true,
          "poor_episode_any_hits_nondecreasing": true,
          "very_poor_episode_any_hits_nondecreasing": true
        },
        "poor_recall_delta": 0.0,
        "paired_very_poor": {
          "new_hits_in_fully_missed_reference_episodes": 0,
          "maximum_new_hits_in_one_reference_missed_episode": 0,
          "newly_detected_reference_missed_episodes": 0
        }
      }
    ],
    "unsupported_claims": [
      "diagnostic_pollution: official Severe recall UNMEASURED",
      "diagnostic_other_seasons: Very Poor+ recall UNMEASURED",
      "diagnostic_other_seasons: official Severe recall UNMEASURED"
    ],
    "disposition": "RESEARCH_ONLY_NO_AUTOMATIC_PROMOTION"
  },
  {
    "candidate": "tcn_seed_2",
    "reference": "v1_fixed_mean",
    "research_utility_gate_passed": false,
    "guardrails_passed": false,
    "poor_recall_gain_branch": false,
    "very_poor_episode_gain_branch": false,
    "paired_periods": [
      {
        "partition": "diagnostic_pollution",
        "checks": {
          "accuracy": false,
          "poor_false_alarm_rate": true,
          "very_poor_false_alarm_rate": true,
          "very_poor_misses_nonincreasing": true,
          "poor_episode_any_hits_nondecreasing": false,
          "very_poor_episode_any_hits_nondecreasing": true
        },
        "poor_recall_delta": -0.08467741935483869,
        "paired_very_poor": {
          "new_hits_in_fully_missed_reference_episodes": 0,
          "maximum_new_hits_in_one_reference_missed_episode": 0,
          "newly_detected_reference_missed_episodes": 0
        }
      },
      {
        "partition": "diagnostic_other_seasons",
        "checks": {
          "accuracy": true,
          "poor_false_alarm_rate": true,
          "very_poor_false_alarm_rate": true,
          "very_poor_misses_nonincreasing": true,
          "poor_episode_any_hits_nondecreasing": false,
          "very_poor_episode_any_hits_nondecreasing": true
        },
        "poor_recall_delta": -0.25,
        "paired_very_poor": {
          "new_hits_in_fully_missed_reference_episodes": 0,
          "maximum_new_hits_in_one_reference_missed_episode": 0,
          "newly_detected_reference_missed_episodes": 0
        }
      }
    ],
    "unsupported_claims": [
      "diagnostic_pollution: official Severe recall UNMEASURED",
      "diagnostic_other_seasons: Very Poor+ recall UNMEASURED",
      "diagnostic_other_seasons: official Severe recall UNMEASURED"
    ],
    "disposition": "RESEARCH_ONLY_NO_AUTOMATIC_PROMOTION"
  },
  {
    "candidate": "tcn_fixed_mean",
    "reference": "v1_fixed_mean",
    "research_utility_gate_passed": false,
    "guardrails_passed": false,
    "poor_recall_gain_branch": false,
    "very_poor_episode_gain_branch": false,
    "paired_periods": [
      {
        "partition": "diagnostic_pollution",
        "checks": {
          "accuracy": true,
          "poor_false_alarm_rate": true,
          "very_poor_false_alarm_rate": true,
          "very_poor_misses_nonincreasing": true,
          "poor_episode_any_hits_nondecreasing": false,
          "very_poor_episode_any_hits_nondecreasing": true
        },
        "poor_recall_delta": -0.08870967741935482,
        "paired_very_poor": {
          "new_hits_in_fully_missed_reference_episodes": 0,
          "maximum_new_hits_in_one_reference_missed_episode": 0,
          "newly_detected_reference_missed_episodes": 0
        }
      },
      {
        "partition": "diagnostic_other_seasons",
        "checks": {
          "accuracy": true,
          "poor_false_alarm_rate": true,
          "very_poor_false_alarm_rate": true,
          "very_poor_misses_nonincreasing": true,
          "poor_episode_any_hits_nondecreasing": false,
          "very_poor_episode_any_hits_nondecreasing": true
        },
        "poor_recall_delta": -0.0625,
        "paired_very_poor": {
          "new_hits_in_fully_missed_reference_episodes": 0,
          "maximum_new_hits_in_one_reference_missed_episode": 0,
          "newly_detected_reference_missed_episodes": 0
        }
      }
    ],
    "unsupported_claims": [
      "diagnostic_pollution: official Severe recall UNMEASURED",
      "diagnostic_other_seasons: Very Poor+ recall UNMEASURED",
      "diagnostic_other_seasons: official Severe recall UNMEASURED"
    ],
    "disposition": "RESEARCH_ONLY_NO_AUTOMATIC_PROMOTION"
  }
]
```

No candidate was promoted. No prospective station validation, human review, field test, medical benefit or measured billing is established. A passing retrospective gate supports further qualification only.
