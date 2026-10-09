# V3 research review and V4 protocol

The user requested a deeper multi-agent review and implementation followed by hosted execution. Three read-only research agents reviewed v3 source, artifacts, target semantics and failure metrics.

## Data review

The 28-feature v3 matrix already includes causal effective-NAQI, PM and wind history (`src/baahar/features.py`, `scripts/run_eval.py`). Generic additional lag features would duplicate existing information. Recorded instantaneous NAQI is excluded from that matrix while the target is future instantaneous NAQI. Recommended comparison: original 28 columns versus seven instantaneous columns (current, lag1/3/6 and corresponding differences). Use exact timestamp lookups, preserve missing hours, and fit medians only on training. The builder uses positional target indexing; v4 therefore checks each archived label and numeric target against raw measurements at exactly t+6 before fitting. No historical targets are silently changed.

## Architecture review

A class-only target discards within-band NAQI magnitude. With only six severe training episodes, a larger network or calibrated severe head has inadequate support. Recommended comparison: LightGBM quantile regression at fixed alpha0.5 and0.9 against the categorical model, preserving numeric targets already recorded. Report numeric MAE/RMSE/pinball/coverage separately from class scores. A quantile is not a risk probability; do not manufacture Brier/ECE for it or call it a calibrated safety guarantee.

## Safety and evaluation review

All 13 severe targets in v3 occur while current instantaneous air is below poor (11 satisfactory, two moderate). They are severe onsets, so a current-severe floor cannot repair these cases. Expanded weighted v3 predicts nine as poor and four as moderate, with seven other severe predictions all false positives. Six severe training episodes and five evaluation episodes remain a limitation. Recommended per-case onset counts and episode any-hit/full-hit summaries. A broader 24-hour history comparison is deferred to keep the current experiment on the same eligible rows.

## Implemented synthesis: fixed 2 x 3 experiment

Compare classifier, median quantile regression and90th-percentile quantile regression, each with original28 versus augmented35 columns. Each within-head feature comparison and each within-feature target comparison changes one factor. All six candidates are preregistered; diagnostic results do not choose a head, quantile, feature set or threshold. Classifier retains v3 weights [1,1,1,4,16,16]. Quantile heads are unweighted, retaining quantile interpretation. Model parameters, training dates and diagnostic dates match expanded v3. Development (June2025–January2026) is reported without candidate selection. No automatic adoption.

Replay exact v3 rows and recorded source bytes from the Modal volume, pinning their hashes. No archive refetch, local weights, synthetic pollution training, or rewriting prior raw outputs. Strictly verify current/target quality, contiguous six-hour history and t+6 source reconstruction. Preserve original band labels; report rounded numeric-to-band disagreements instead of rewriting them. Return feature orders, numeric predictions, categorical outputs, all hourly risk metrics, quantile quality and descriptive episode/onset metrics. Reproduce the v3 base classifier predictions on both diagnostic windows and report whether they match.

Training: 2023-01-01 to2025-06-01 with six-hour target embargo. Diagnostic pollution:2026-02-01 to2026-05-01. Other seasons:2026-05-01 to2026-10-01. These are already consumed modelled CAMS/ERA5 archive diagnostics. Human review, station validation, prospective evidence and measured billing are absent. There is no policy-weather or medical safety claim.

```powershell
uv run --group modal python scripts/train_forecast_risk_modal.py --submit --version v4
uv run --group modal python scripts/train_forecast_risk_modal.py --fetch --version v4
```


## V4 completed and reviewed by three research agents

Six fixed candidates completed on Modal: weighted multiclass, median quantile and 90th-percentile quantile, each with 28 original versus 35 instantaneous-history columns. Both diagnostic baseline vectors reproduce v3 exactly; all source/row hashes match. Exact t+6 source checks passed on 32,826 rows, with zero rounded numeric-label disagreements in all periods. No archive refresh or weights download occurred.

Data agent: small mixed feature gains. Pollution classifier accuracy remains 0.7638, macro-F1 declines 0.4848 to 0.4772, poor+ misses stay 144/248, false alarms decline 39 to 34; severe false alarms increase 7 to 9. Other-season accuracy improves 0.8295 to 0.8306, poor+ misses improve 11 to 10/23 and false alarms stay 17; severe false alarms increase 0 to 1. Poor-episode any-hit declines 5 to 4/7 in the later window, despite one more caught hour. Hourly improvement is not broader episode coverage.

Architecture agent: quantile heads expose a tradeoff. Base-feature upper-quantile poor+ recall reaches 0.9073 and 0.9130 versus classifier 0.4194 and 0.5217. Accuracy falls from 0.7638 to 0.6638 and 0.8295 to 0.7474; false alarms rise 39 to 164 and 17 to 59. Its empirical coverage is only 0.7944 and 0.7447, below nominal 0.9. Augmented upper-quantile coverage is 0.8014 and 0.7480. None is a calibrated safety bound. Median MAE improves slightly with instantaneous history (18.21 to 18.00; 9.76 to 9.55), but median poor+ recall is lower than classification.

Safety agent: all six candidates miss all 13 severe hours in five episodes, all severe onsets. Development has 16 poor+ hours in seven episodes and zero severe hours; severe recall there is unmeasured. Training contains 27 severe hours in six episodes, with no hazardous examples. More modeling on these consumed windows does not provide independent severe-risk qualification.

Disposition: retain candidates as research evidence, with no automatic model adoption. All results are consumed CAMS/ERA5 modeled archive diagnostics, not station observations, prospective validation, human field evidence or medical safety. Actual billing is unmeasured. Severe modeling needs distinct severe development episodes and evidence beyond repeated diagnostic tuning. The full offline suite, eleven focused forecast tests and Ruff passed. The completed monitor is disabled.
