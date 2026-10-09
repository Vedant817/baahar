# V4 fixed target and feature experiment

Consumed modeled archive diagnostics; no calibration, threshold tuning or automatic model adoption.

| Period | Candidate | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ FAR | Severe+ misses/support | Severe+ FAR | MAE | Quantile coverage |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| development | base_classifier | 0.841 | 0.6425 | 15/16 | 0.0010284538909838875 | 0/0 | 0.00017094017094017094 | N/A | N/A |
| development | base_quantile_0.5 | 0.8403 | 0.6178 | 16/16 | 0.00017140898183064793 | 0/0 | 0.0 | 9.879232762672896 | 0.38461538461538464 |
| development | base_quantile_0.9 | 0.7082 | 0.5868 | 6/16 | 0.010284538909838875 | 0/0 | 0.0 | 14.728437653474662 | 0.8049572649572649 |
| development | instant_history_classifier | 0.8409 | 0.6552 | 14/16 | 0.0015426808364758314 | 0/0 | 0.0 | N/A | N/A |
| development | instant_history_quantile_0.5 | 0.8422 | 0.6196 | 16/16 | 0.0005142269454919438 | 0/0 | 0.0 | 9.759855905808955 | 0.3902564102564103 |
| development | instant_history_quantile_0.9 | 0.7152 | 0.5968 | 5/16 | 0.010284538909838875 | 0/0 | 0.0 | 14.436731372267337 | 0.8061538461538461 |
| diagnostic_pollution | base_classifier | 0.7638 | 0.4848 | 144/248 | 0.020722635494155154 | 11/11 | 0.0033034450212364322 | N/A | N/A |
| diagnostic_pollution | base_quantile_0.5 | 0.7615 | 0.4335 | 158/248 | 0.018065887353878853 | 11/11 | 0.0 | 18.2119116150227 | 0.3854460093896714 |
| diagnostic_pollution | base_quantile_0.9 | 0.6638 | 0.4046 | 23/248 | 0.0871413390010627 | 11/11 | 0.001415762151958471 | 22.399022984735378 | 0.7943661971830986 |
| diagnostic_pollution | instant_history_classifier | 0.7638 | 0.4772 | 144/248 | 0.018065887353878853 | 11/11 | 0.004247286455875413 | N/A | N/A |
| diagnostic_pollution | instant_history_quantile_0.5 | 0.7563 | 0.4192 | 160/248 | 0.01700318809776833 | 11/11 | 0.0 | 18.004367378768755 | 0.3892018779342723 |
| diagnostic_pollution | instant_history_quantile_0.9 | 0.6676 | 0.4059 | 25/248 | 0.08607863974495218 | 11/11 | 0.0009438414346389807 | 22.266945740029094 | 0.8014084507042254 |
| diagnostic_other_seasons | base_classifier | 0.8295 | 0.569 | 11/23 | 0.004666483667307164 | 2/2 | 0.0 | N/A | N/A |
| diagnostic_other_seasons | base_quantile_0.5 | 0.8393 | 0.5611 | 15/23 | 0.0016469942355201758 | 2/2 | 0.0 | 9.755253949761896 | 0.32896890343698854 |
| diagnostic_other_seasons | base_quantile_0.9 | 0.7474 | 0.5104 | 2/23 | 0.016195443315948393 | 2/2 | 0.0 | 13.345772880440865 | 0.7446808510638298 |
| diagnostic_other_seasons | instant_history_classifier | 0.8306 | 0.5696 | 10/23 | 0.004666483667307164 | 2/2 | 0.0002729257641921397 | N/A | N/A |
| diagnostic_other_seasons | instant_history_quantile_0.5 | 0.8418 | 0.5506 | 18/23 | 0.0008234971177600879 | 2/2 | 0.0 | 9.54889045645738 | 0.3270594653573377 |
| diagnostic_other_seasons | instant_history_quantile_0.9 | 0.7542 | 0.5089 | 3/23 | 0.017018940433708482 | 2/2 | 0.0 | 13.012775552210847 | 0.7479541734860884 |

Classifier Brier/ECE use uncalibrated probabilities. Quantile heads do not supply risk probabilities; their Brier/ECE are null. Empirical quantile coverage does not establish calibrated safety. Numeric target labels are preserved, including any rounding discrepancies. Raw output includes feature orders, source checks, episodes, onset misses, numeric predictions, RMSE/pinball loss and all risk metrics. Development reporting does not select candidates.


## V4 completed and reviewed by three research agents

Six fixed candidates completed on Modal: weighted multiclass, median quantile and 90th-percentile quantile, each with 28 original versus 35 instantaneous-history columns. Both diagnostic baseline vectors reproduce v3 exactly; all source/row hashes match. Exact t+6 source checks passed on 32,826 rows, with zero rounded numeric-label disagreements in all periods. No archive refresh or weights download occurred.

Data agent: small mixed feature gains. Pollution classifier accuracy remains 0.7638, macro-F1 declines 0.4848 to 0.4772, poor+ misses stay 144/248, false alarms decline 39 to 34; severe false alarms increase 7 to 9. Other-season accuracy improves 0.8295 to 0.8306, poor+ misses improve 11 to 10/23 and false alarms stay 17; severe false alarms increase 0 to 1. Poor-episode any-hit declines 5 to 4/7 in the later window, despite one more caught hour. Hourly improvement is not broader episode coverage.

Architecture agent: quantile heads expose a tradeoff. Base-feature upper-quantile poor+ recall reaches 0.9073 and 0.9130 versus classifier 0.4194 and 0.5217. Accuracy falls from 0.7638 to 0.6638 and 0.8295 to 0.7474; false alarms rise 39 to 164 and 17 to 59. Its empirical coverage is only 0.7944 and 0.7447, below nominal 0.9. Augmented upper-quantile coverage is 0.8014 and 0.7480. None is a calibrated safety bound. Median MAE improves slightly with instantaneous history (18.21 to 18.00; 9.76 to 9.55), but median poor+ recall is lower than classification.

Safety agent: all six candidates miss all 13 severe hours in five episodes, all severe onsets. Development has 16 poor+ hours in seven episodes and zero severe hours; severe recall there is unmeasured. Training contains 27 severe hours in six episodes, with no hazardous examples. More modeling on these consumed windows does not provide independent severe-risk qualification.

Disposition: retain candidates as research evidence, with no automatic model adoption. All results are consumed CAMS/ERA5 modeled archive diagnostics, not station observations, prospective validation, human field evidence or medical safety. Actual billing is unmeasured. Severe modeling needs distinct severe development episodes and evidence beyond repeated diagnostic tuning. The full offline suite, eleven focused forecast tests and Ruff passed. The completed monitor is disabled.
