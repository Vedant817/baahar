# Fixed pollutant linear study: measured results

All candidates were evaluated on identical phase-local 24-hour-context origins. Both 2026 periods are consumed modeled-archive diagnostics, not fresh holdouts. The primary reference is the frozen v3 three-seed concentration-average ensemble. Matched LightGBM remains a secondary comparator.

Historical raw `severe` means official Very Poor (301-400); `hazardous` means official Severe (401+). This is an instantaneous concentration proxy, not averaging-compliant station AQI.

| Period | Model | n | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ recall | Poor+ precision | Poor+ FAR | Very Poor+ misses/support | Very Poor+ recall | Very Poor+ FAR | Severe misses/support |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| development | ridge_fixed | 1435 | 0.763066 | 0.639753 | 64/168 | 0.619048 | 0.806202 | 0.019732 | 18/22 | 0.181818 | 0.001415 | 0/0 |
| development | v3_fixed_mean | 1435 | 0.745645 | 0.576626 | 62/168 | 0.630952 | 0.876033 | 0.011839 | 22/22 | 0.000000 | 0.000708 | 0/0 |
| development | paired_lightgbm | 1435 | 0.743554 | 0.560935 | 79/168 | 0.529762 | 0.855769 | 0.011839 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | persistence | 1435 | 0.364460 | 0.257717 | 146/168 | 0.130952 | 0.130952 | 0.115233 | 22/22 | 0.000000 | 0.015570 | 0/0 |
| diagnostic_pollution | ridge_fixed | 2107 | 0.799241 | 0.498535 | 106/248 | 0.572581 | 0.820809 | 0.016676 | 11/11 | 0.000000 | 0.000477 | 0/0 |
| diagnostic_pollution | v3_fixed_mean | 2107 | 0.791172 | 0.486293 | 88/248 | 0.645161 | 0.740741 | 0.030124 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | paired_lightgbm | 2107 | 0.794495 | 0.506529 | 129/248 | 0.479839 | 0.815068 | 0.014524 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | persistence | 2107 | 0.385382 | 0.211169 | 231/248 | 0.068548 | 0.068548 | 0.124260 | 11/11 | 0.000000 | 0.005248 | 0/0 |
| diagnostic_other_seasons | ridge_fixed | 3643 | 0.845732 | 0.707854 | 12/16 | 0.250000 | 0.800000 | 0.000276 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | v3_fixed_mean | 3643 | 0.847928 | 0.789472 | 6/16 | 0.625000 | 0.769231 | 0.000827 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | paired_lightgbm | 3643 | 0.839967 | 0.664454 | 13/16 | 0.187500 | 0.333333 | 0.001654 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | persistence | 3643 | 0.451551 | 0.299947 | 16/16 | 0.000000 | 0.000000 | 0.004411 | 0/0 | UNMEASURED | 0.000000 | 0/0 |

## Full metric detail

The machine-readable completion summary retains pollutant MAE/RMSE, class support, episode counts, ranking average precision, fixed linear fit metadata and all paired gate checks. Ranking scores are not probabilities; Brier/ECE are unavailable. Missing positive support means recall is unmeasured.

```json
[
  {
    "candidate": "ridge_fixed",
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
        "poor_recall_delta": -0.07258064516129026,
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
  }
]
```

No candidate was promoted. No prospective station validation, human review, field test, medical benefit or measured billing is established. A passing retrospective gate supports further qualification only.
