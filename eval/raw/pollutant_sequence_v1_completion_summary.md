# Deep pollutant sequence study: measured results

All candidates were evaluated on identical phase-local 24-hour-context origins. Both 2026 periods are consumed modeled-archive diagnostics, not fresh holdouts. The reference is the new matched LightGBM model; old v4-v6 counts are not an identical subset.

Historical raw `severe` means official Very Poor (301–400); `hazardous` means official Severe (401+). This is an instantaneous concentration proxy, not averaging-compliant station AQI.

| Period | Model | n | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ recall | Poor+ precision | Poor+ FAR | Very Poor+ misses/support | Very Poor+ recall | Very Poor+ FAR | Severe misses/support |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| development | tcn_seed_0 | 1435 | 0.720557 | 0.527710 | 105/168 | 0.375000 | 0.887324 | 0.006314 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | tcn_seed_1 | 1435 | 0.726829 | 0.547261 | 79/168 | 0.529762 | 0.839623 | 0.013418 | 22/22 | 0.000000 | 0.002123 | 0/0 |
| development | tcn_seed_2 | 1435 | 0.739373 | 0.569031 | 65/168 | 0.613095 | 0.844262 | 0.014996 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | tcn_fixed_mean | 1435 | 0.738676 | 0.562208 | 75/168 | 0.553571 | 0.885714 | 0.009471 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | paired_lightgbm | 1435 | 0.743554 | 0.560935 | 79/168 | 0.529762 | 0.855769 | 0.011839 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | persistence | 1435 | 0.364460 | 0.257717 | 146/168 | 0.130952 | 0.130952 | 0.115233 | 22/22 | 0.000000 | 0.015570 | 0/0 |
| diagnostic_pollution | tcn_seed_0 | 2107 | 0.783579 | 0.462954 | 112/248 | 0.548387 | 0.719577 | 0.028510 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_1 | 2107 | 0.789274 | 0.518402 | 125/248 | 0.495968 | 0.793548 | 0.017214 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_2 | 2107 | 0.785002 | 0.480535 | 101/248 | 0.592742 | 0.765625 | 0.024207 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_fixed_mean | 2107 | 0.788799 | 0.486780 | 111/248 | 0.552419 | 0.769663 | 0.022055 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | paired_lightgbm | 2107 | 0.794495 | 0.506529 | 129/248 | 0.479839 | 0.815068 | 0.014524 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | persistence | 2107 | 0.385382 | 0.211169 | 231/248 | 0.068548 | 0.068548 | 0.124260 | 11/11 | 0.000000 | 0.005248 | 0/0 |
| diagnostic_other_seasons | tcn_seed_0 | 3643 | 0.851496 | 0.713231 | 12/16 | 0.250000 | 0.800000 | 0.000276 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_1 | 3643 | 0.846555 | 0.720355 | 9/16 | 0.437500 | 0.411765 | 0.002757 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_2 | 3643 | 0.849300 | 0.725629 | 11/16 | 0.312500 | 0.714286 | 0.000551 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_fixed_mean | 3643 | 0.854516 | 0.716318 | 12/16 | 0.250000 | 0.800000 | 0.000276 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | paired_lightgbm | 3643 | 0.839967 | 0.664454 | 13/16 | 0.187500 | 0.333333 | 0.001654 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | persistence | 3643 | 0.451551 | 0.299947 | 16/16 | 0.000000 | 0.000000 | 0.004411 | 0/0 | UNMEASURED | 0.000000 | 0/0 |

## Full metric detail

The machine-readable completion summary retains pollutant MAE/RMSE, class support, episode counts, ranking average precision, seed histories and all paired gate checks. Ranking scores are not probabilities; Brier/ECE are unavailable. Missing positive support means recall is unmeasured.

```json
[
  {
    "candidate": "tcn_seed_0",
    "reference": "paired_lightgbm",
    "research_utility_gate_passed": false,
    "guardrails_passed": false,
    "poor_recall_gain_branch": true,
    "very_poor_episode_gain_branch": false,
    "paired_periods": [
      {
        "partition": "diagnostic_pollution",
        "checks": {
          "accuracy": false,
          "poor_false_alarm_rate": false,
          "very_poor_false_alarm_rate": true,
          "very_poor_misses_nonincreasing": true,
          "poor_episode_any_hits_nondecreasing": true,
          "very_poor_episode_any_hits_nondecreasing": true
        },
        "poor_recall_delta": 0.06854838709677413,
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
    "reference": "paired_lightgbm",
    "research_utility_gate_passed": true,
    "guardrails_passed": true,
    "poor_recall_gain_branch": true,
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
        "poor_recall_delta": 0.016129032258064502,
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
          "poor_episode_any_hits_nondecreasing": true,
          "very_poor_episode_any_hits_nondecreasing": true
        },
        "poor_recall_delta": 0.25,
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
    "reference": "paired_lightgbm",
    "research_utility_gate_passed": true,
    "guardrails_passed": true,
    "poor_recall_gain_branch": true,
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
        "poor_recall_delta": 0.11290322580645162,
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
          "poor_episode_any_hits_nondecreasing": true,
          "very_poor_episode_any_hits_nondecreasing": true
        },
        "poor_recall_delta": 0.125,
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
    "reference": "paired_lightgbm",
    "research_utility_gate_passed": true,
    "guardrails_passed": true,
    "poor_recall_gain_branch": true,
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
        "poor_recall_delta": 0.07258064516129026,
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
  }
]
```

No candidate was promoted. No prospective station validation, human review, field test, medical benefit or measured billing is established. A passing retrospective gate supports further qualification only.
