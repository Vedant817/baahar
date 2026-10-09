# Deep pollutant sequence study: measured results

All candidates were evaluated on identical phase-local 24-hour-context origins. Both 2026 periods are consumed modeled-archive diagnostics, not fresh holdouts. The primary reference is the frozen v3 three-seed concentration-average ensemble. Matched LightGBM remains a secondary comparator.

Historical raw `severe` means official Very Poor (301-400); `hazardous` means official Severe (401+). This is an instantaneous concentration proxy, not averaging-compliant station AQI.

| Period | Model | n | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ recall | Poor+ precision | Poor+ FAR | Very Poor+ misses/support | Very Poor+ recall | Very Poor+ FAR | Severe misses/support |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| development | tcn_seed_0 | 1435 | 0.728223 | 0.558271 | 75/168 | 0.553571 | 0.894231 | 0.008682 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | tcn_seed_1 | 1435 | 0.753310 | 0.579183 | 63/168 | 0.625000 | 0.833333 | 0.016575 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | tcn_seed_2 | 1435 | 0.738676 | 0.563584 | 82/168 | 0.511905 | 0.924731 | 0.005525 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | tcn_fixed_mean | 1435 | 0.747038 | 0.573598 | 70/168 | 0.583333 | 0.899083 | 0.008682 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | paired_lightgbm | 1435 | 0.743554 | 0.560935 | 79/168 | 0.529762 | 0.855769 | 0.011839 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | persistence | 1435 | 0.364460 | 0.257717 | 146/168 | 0.130952 | 0.130952 | 0.115233 | 22/22 | 0.000000 | 0.015570 | 0/0 |
| development | v3_fixed_mean | 1435 | 0.745645 | 0.576626 | 62/168 | 0.630952 | 0.876033 | 0.011839 | 22/22 | 0.000000 | 0.000708 | 0/0 |
| diagnostic_pollution | tcn_seed_0 | 2107 | 0.795444 | 0.529715 | 90/248 | 0.637097 | 0.755981 | 0.027434 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_1 | 2107 | 0.789748 | 0.509684 | 86/248 | 0.653226 | 0.746544 | 0.029586 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_2 | 2107 | 0.789274 | 0.489791 | 102/248 | 0.588710 | 0.772487 | 0.023131 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_fixed_mean | 2107 | 0.790698 | 0.482729 | 94/248 | 0.620968 | 0.766169 | 0.025282 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | paired_lightgbm | 2107 | 0.794495 | 0.506529 | 129/248 | 0.479839 | 0.815068 | 0.014524 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | persistence | 2107 | 0.385382 | 0.211169 | 231/248 | 0.068548 | 0.068548 | 0.124260 | 11/11 | 0.000000 | 0.005248 | 0/0 |
| diagnostic_pollution | v3_fixed_mean | 2107 | 0.791172 | 0.486293 | 88/248 | 0.645161 | 0.740741 | 0.030124 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_0 | 3643 | 0.852045 | 0.746901 | 9/16 | 0.437500 | 0.636364 | 0.001103 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_1 | 3643 | 0.845732 | 0.723817 | 9/16 | 0.437500 | 0.437500 | 0.002481 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_2 | 3643 | 0.850398 | 0.706675 | 12/16 | 0.250000 | 0.800000 | 0.000276 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_fixed_mean | 3643 | 0.851222 | 0.741100 | 10/16 | 0.375000 | 0.750000 | 0.000551 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | paired_lightgbm | 3643 | 0.839967 | 0.664454 | 13/16 | 0.187500 | 0.333333 | 0.001654 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | persistence | 3643 | 0.451551 | 0.299947 | 16/16 | 0.000000 | 0.000000 | 0.004411 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | v3_fixed_mean | 3643 | 0.847928 | 0.789472 | 6/16 | 0.625000 | 0.769231 | 0.000827 | 0/0 | UNMEASURED | 0.000000 | 0/0 |

## Full metric detail

The machine-readable completion summary retains pollutant MAE/RMSE, class support, episode counts, ranking average precision, seed histories and all paired gate checks. Ranking scores are not probabilities; Brier/ECE are unavailable. Missing positive support means recall is unmeasured.

```json
[
  {
    "candidate": "tcn_seed_0",
    "reference": "v3_fixed_mean",
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
        "poor_recall_delta": -0.008064516129032251,
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
        "poor_recall_delta": -0.1875,
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
    "reference": "v3_fixed_mean",
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
        "poor_recall_delta": 0.008064516129032251,
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
        "poor_recall_delta": -0.1875,
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
    "reference": "v3_fixed_mean",
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
        "poor_recall_delta": -0.056451612903225756,
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
        "poor_recall_delta": -0.375,
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
    "reference": "v3_fixed_mean",
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
        "poor_recall_delta": -0.024193548387096753,
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
  }
]
```

No candidate was promoted. No prospective station validation, human review, field test, medical benefit or measured billing is established. A passing retrospective gate supports further qualification only.
