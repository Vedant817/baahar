# Model qualification progress — 8 October 2026

## Runtime repair

Current-hour permission is now shared by briefing and Pocket Mode. A future best hour no longer authorizes walking now. Current WAIT/SKIP, unknown weather/air, recorded fallback data, unmatched air/weather timestamps and expired assessments cannot start a walk. Assessments expire after 15 minutes or the current forecast hour ends, whichever comes first. This is an operational refresh policy, not a medical safety guarantee.

The full offline pytest suite and Ruff passed. Ten focused temporal tests cover withheld walking, expiry, model completion after expiry, cache behavior and valid current GO. Actual collaborative-browser checks exercised the real API/UI with explicitly synthetic forecast inputs: current NAQI350 with future50 blocked deep-link/automatic entry; current50 enabled manual Pocket entry; mutating the assessment to 16 minutes old blocked entry. Browser evidence: [raw verification](../eval/raw/temporal_browser_verification_20261008.json). These are not live weather or human field tests.

## Frozen v15 diagnostic result

[Preregistered manifest](../eval/raw/qualification_v15_manifest.json) and [raw outputs](../eval/raw/qualification_v15_results.json) preserve the 24-case hosted run. It used the existing Qwen3 4B v15 adapter; no weights were downloaded locally.

The adapter passed the frozen finite contract on 6/24 cases. Sixteen cases omitted required weather uncertainty. Missing heat caused fabricated apparent-temperature values; missing rainfall in compound unknown-weather cases caused rainfall amounts to be copied from another supplied field. These are genuine grounding/coverage defects, despite perfect old benchmark scores. Runtime withholds model prose on these incomplete-input paths.

The frozen qualification rubric also has defects which must remain visible:

- Its three `walk_now_permission` flags match “Postpone the walk for now”, which withholds walking. They do not establish harmful invitations.
- Its refresh anchor misses “A later forecast must be checked”; this explains 20 flags in the deterministic baseline and is not a safety failure.
- The four temporal fallback cases contain scheduled ISO timestamps absent from the frozen numeric allowance. The live contract now formats and grounds scheduled hours, but this diagnostic snapshot remains unchanged.
- Temporal prompts contain both current and future NAQI values with a WAIT label even for current unsafe air. Two `wrong_naqi` flags reflect selecting the supplied current value instead of the expected future value. Treat these as ambiguous prompt/fact-binding diagnostics, not as invention of an unsupplied measurement.

The suite has zero GO positives and cannot establish stylistic benefit over deterministic prose, independent generalization, or promotion readiness. Do not aggregate its flawed anchor checks into a safety-error headline. Preserve it as diagnostic regression evidence after using its findings to guide training.

## Targeted next candidate

One hosted 4B candidate has completed training with 96 unique added coverage prompts for missing weather and combined hazards, holding the v15 optimization parameters fixed. It uses `data/ft_v4/` and [the v16 manifest](../eval/raw/candidate_submission_v16.json) with recomputed hashes; the archived ft_v2 files remain unchanged. The standard offline reporter verified the manifest-pinned data and contract bytes, all generation rows and raw checks using `--data-dir data/ft_v4`.

The reported finite-contract scores are 80/80 validation, 88/88 test and 64/64 stress, all with zero raw safety failures and zero fallback. The 32-case synthetic development set scored 32/32 adapted versus 1/32 base. It shares authored families with the augmented training data and is not an independent holdout. Adapted median GPU generation was 4.993, 5.134, 5.436 and 5.824 seconds on validation, test, stress and development. These timings exclude container startup and end-to-end serving.

Training app: https://modal.com/apps/vedantmahajan271/main/ap-SrdTxVysSsZ33ucN4KWSmh . The single-run compute ceiling estimate is $4.602528, not measured billing.

## Frozen v15 regression comparison

The v16 adapter passed **21/24** cases on the consumed diagnostic suite, versus **6/24** for v15. Per-family accepted counts (v15 → v16): missing heat 0/4 → 4/4; missing rain 0/4 → 4/4; nonfinite weather 0/4 → 4/4; compound unknown air/night/thunderstorm 0/4 → 4/4; instruction paraphrases 4/4 → 4/4; future permission 2/4 → 1/4.

For the 24 v16 outputs, the finite checker flags two `wrong_naqi` and three `ungrounded_number` defects, all on future-permission cases whose prompts contain conflicting current and future NAQI facts. Those outputs explicitly say to hold off and state that the later forecast is not permission to walk now. The v16 outputs removed the v15 missing-heat invented temperatures, missing-weather uncertainty omissions and copied rainfall values: zero `wrong_apparent_c`, `wrong_precip_mm` or `missing_weather_uncertainty` flags remain. All 20 SKIP outputs still trigger the frozen refresh wording anchor, including v15/v16 answers saying “A later forecast must be checked”; that anchor does not recognize the wording and these flags are not safety failures. The three v15 `walk_now_permission` flags were false positives on “Postpone the walk for now” and are absent in v16.

The complete paired outputs, defect counts and limitations are in [v16 completion summary](../eval/raw/v16_completion_summary.json). This is regression evidence on a previously consumed, synthetic suite with no GO-positive cases and no human semantic review. **Disposition: v16 is the best measured provisional adapter for finite contract adherence, but it is not qualified for promotion or deployment.** A new independently authored, semantically reviewed suite with current-GO and withheld-action cases is needed to establish user-facing value and broader safety.

The completion and comparison monitor is no longer needed and is disabled. The old training-loop completion counter remains unchanged; no additional training was started. Existing credits were user-authorized, but remaining credit and actual billed costs have not been measured. No adapter is promoted or publicly deployed.

## Follow-up qualification — submitted 8 October

The user authorized the remaining qualification work and continued service monitoring. The live contract now explicitly scopes measurements to current conditions and rejects mixed `current_`/`future_` measurement prompts. A scheduled hour is only a window to recheck; it cannot authorize walking. The finite checker also rejects an invitation when `walk_allowed=false`, even with a contradictory GO token. Three focused regressions were added; all 29 briefing-contract tests passed before submission.

The frozen V16 adapter is being evaluated on 48 new synthetic cases, including six current-GO positives and seven withheld-action families. These are AI-authored scenarios, not independently human-authored or blind qualification. Families overlap previous training; no independent-generalization claim or automatic promotion is allowed. The deterministic baseline passed every preregistration self-check. Prompts and the updated contract are pinned in [the fresh manifest](../eval/raw/qualification_v16_fresh_manifest.json). Runner: `scripts/qualify_briefing_v16_fresh_modal.py`. Hosted app: https://modal.com/apps/vedantmahajan271/main/ap-13nxXfHtx83WzYuJtVos8L . No additional LLM training was started.

Separately, [rolling forecast diagnostics](../eval/raw/forecast_rolling_manifest.json) compare majority, persistence, LightGBM and the existing ensemble across February, April, June and August 2026. They use training-only imputation and a six-hour label embargo. Target-hour recorded weather is aligned for policy diagnostics; it is oracle weather, not evidence of deployed weather-forecast performance. The archive and model configurations were already consumed, so these are broader temporal diagnostics rather than a pristine holdout. Serving artifacts are never written by this runner. Hosted app: https://modal.com/apps/vedantmahajan271/main/ap-WeWVM1pF4RdqyqPHJxirSG . Runner: `scripts/validate_forecast_modal.py`.

The existing scheduler checked these two manifests every ten minutes, fetched only small result artifacts, and is disabled after this final report. Actual billing and remaining credits are unmeasured.

Rolling forecast results have completed. Ensemble accuracy by month is February 0.7232, April 0.7000, June 0.6403 and August 0.9489. Poor-or-worse hours predicted below poor are respectively 33/33, 87/124, 2/2 and 0/0 (August has no such cases, so its risk recall is unmeasured). April includes seven severe hours; no hazardous hours occur in these four evaluation windows. These are actual target-band misses, not evidence of an unsafe live invitation. The result identifies rare polluted-hour prediction as the next training research target and contradicts treating the earlier 0.8617 aggregate as season-independent performance. No model is replaced. Full model-by-month comparisons are in [follow-up report](../eval/raw/next_qualification_report.md) and [raw rolling outputs](../eval/raw/forecast_rolling_results.json).

The fresh V16 briefing run completed on an L40S. Raw finite contract acceptance is 46/48 for V16 and 48/48 for deterministic fallback; semantic-anchor flags are 0/48 for both. All six current-GO positives pass for both. The other 42 scenarios withhold walking (SKIP for 36; WAIT for six stale assessments); all deterministic fallbacks pass. V16's two raw checker failures are solely `ungrounded_number` on “recheck at 5 PM” and “5:00 PM” for the supplied 17:00 scheduled window. Both answers withhold walking, identify extreme heat, and ask for a recheck. This looks like a checker time-format limitation, while the raw finite flags are preserved and the stated zero-finite-safety-flag gate is not met. No current/future NAQI or band mixing appeared in these 48 outputs. Median generation time by family ranges from 5.014 seconds (current GO) to 5.697 seconds (stale assessment); these timings omit service startup and end-to-end serving. This is an AI-authored synthetic qualification with family overlap, not independent human review or a pristine holdout. See [the full family report](../eval/raw/next_qualification_report.md), [summary](../eval/raw/next_qualification_summary.json), and [raw paired generations](../eval/raw/qualification_v16_fresh_results.json). **Disposition remains provisional; do not promote or deploy.**

The full offline pytest suite and repository Ruff checks passed after the temporal changes. No serving artifact, weight download, commit or deployment was made.

The field-test instructions now require a fresh current GO for outdoor testing and indoor-only testing for WAIT/SKIP. This safety instruction was corrected under the user's authorization to complete remaining work; the blank observation form and NOT YET DONE status were preserved. Human semantic review, an actual walk/photo, end-to-end hosted serving measurement and final publication remain outstanding.

## Rare-air forecast experiment — submitted 8 October

The user authorized implementing [the next approach](NEXT_MODEL_APPROACH.md). The new hosted runner, `scripts/train_forecast_risk_modal.py`, expands the archive to January 2024–October 2025, trains weighted LightGBM and a separate binary poor-or-worse classifier, calibrates its probabilities on a separate January partition, and selects a risk threshold on a later development partition. Locked evaluation uses February–April and May–October 2025. All phase endings have a six-hour label gap. Required source fields and contiguous lag history are screened before evaluation; learned medians come only from training rows.

The ordinary LightGBM, current ensemble configuration and persistence are refitted/evaluated as matched research baselines on the same training and test windows. The remote candidate bundle records feature order and preprocessing. This does not modify existing serving artifacts. Source code is hash-pinned in [the experiment manifest](../eval/raw/forecast_risk_v1_manifest.json); fetched results will pin dataset and recorded source-response hashes. Raw source responses, expanded rows and candidate models stay on the Modal volume. This is CAMS/ERA5 modelled archive research, not station-observed accuracy, prospective independent validation or field evidence.

Hosted app: https://modal.com/apps/vedantmahajan271/main/ap-lFq6HhNUx288elP4t3Kfor . Call `fc-01M4E7EEVJMY8PNNGS0AXBR3FC` is submitted and was still pending at the first short fetch. The scheduler now checks this experiment every ten minutes, writes measured results after completion, and disables itself after the final report. No additional run is automatically submitted. The manifest's CPU compute ceiling estimate is $0.158256; this is not measured billing and excludes storage/network charges. Actual billed cost and remaining credit are unknown.

Four focused offline algorithm tests and the full offline pytest suite passed; repository Ruff passed. The weighted and risk models are research candidates; no accuracy improvement is claimed before results arrive. Promotion and actual outdoor testing remain separate steps.


## Rare-air forecast experiment — terminal failure verified

Direct fetch confirmed that call `fc-01M4E7EEVJMY8PNNGS0AXBR3FC` failed at the class-support gate before model fitting. The former SUBMITTED status was stale and is now FAILED. No live training job remains from this call, and no candidate performance metrics exist.

Reading the recorded Modal-volume rows and source fixtures, with the original quality filters and six-hour label gap, gives training 97/7,308 poor-or-worse hours; development 1/1,458; calibration 0/348; threshold selection 4/378. Locked evaluation labels were not inspected. Zero calibration positives caused the abort; development support is also inadequate for a reliable rare-event selection claim. The failure preserved the data on the volume. See [support diagnostic](../eval/raw/forecast_risk_v1_support_diagnostic.json) and [failure summary](../eval/raw/forecast_risk_v1_completion_summary.json).

The fetch runner now records this known terminal failure and avoids repeated fetches of the failed call. Its source changes do not alter the hash-pinned historical submission. The monitor is disabled after this failure report; no run was resubmitted and no serving artifact changed. Next work is a preregistered support-aware development/calibration protocol using training/development data, keeping locked evaluation labels untouched. Do not claim calibrated risk probabilities or improved accuracy from this failed run.


## Rare-air forecast v2 — submitted after support-gate repair

The user authorized the revised run. The failed v1 manifest and diagnostic are preserved. V2 trains on 2023 and chooses earliest daily development/calibration endings within January 2024–January 2025 using preregistered minimum support (20 poor-or-worse and 200 below-poor usable hours per phase). Threshold selection uses the remaining pre-February period, with the same support gate. Every phase retains the six-hour target embargo; preprocessing uses training data only. The locked February–April and May–October 2025 evaluation dates are unchanged. No locked labels select split boundaries. Adaptive development labels and correlated hourly support limit interpretation; this remains archive research, not prospective station or field proof.

Submitted call `fc-01M4E89CB1TT1N2GGXADVB367G`; [Modal app](https://modal.com/apps/vedantmahajan271/main/ap-TEgQlUlHwlOtS47NVfVpta). The first direct five-second fetch returned pending. This verifies an outstanding call, not successful training or improved performance. Ten-minute monitoring is enabled for this call only, without automatic resubmission or deployment. The runner records known terminal support failures as FAILED. Full offline pytest and repository Ruff checks passed. No heavy local installation or model download occurred. Manifest: [forecast_risk_v2_manifest.json](../eval/raw/forecast_risk_v2_manifest.json). Actual billing remains unmeasured.


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


## Forecast target correction measured

A research agent identified that v2 persisted current effective NAQI against future instantaneous NAQI labels. The matching instantaneous baseline scores 0.4103/0.2208 accuracy/macro-F1 in February–April and 0.4932/0.2816 in May–October, versus 0.3042/0.1506 and 0.3862/0.2353 for conservative persistence. Poor-or-worse misses remain 185/205 and 41/49; false alarms fall from 245 to 185 and 53 to 41. The source replay reproduced every future target label and verified source/row hashes. Original v2 outputs remain preserved. All learned candidates predict all 27 severe evaluation hours below severe; training contains no severe or hazardous hours. These consumed diagnostics motivate class-coverage work, not promotion. The target contract and future rare-air report were corrected; eight focused tests and repository Ruff passed. [Full audit](../eval/raw/forecast_risk_v2_target_audit.md).


## V3 coverage ablation — submitted

The user authorized training and obtaining results. V3 compares fixed LightGBM candidates (ordinary and [1,1,1,4,16,16] class-weighted) using 2023-only versus January 2023–May 2025 training. Expanded ensemble and matching instantaneous persistence provide additional baselines. February–April and May–September 2026 are consumed diagnostic periods, not independent holdouts. V2's consumed 2025 periods now explicitly contribute to training. No target-label selection of configurations or probability calibration occurs. Training support must include at least 20 severe hours; episode counts report correlation.

Source-hashed [manifest](../eval/raw/forecast_risk_v3_manifest.json). Hosted call `fc-01M4EANGW0531QG8A4ZP7EAHQK`, [app](https://modal.com/apps/vedantmahajan271/main/ap-GG9w1wGAh04JTEZ6fb39vJ). The first short fetch returned pending. Ten-minute monitoring checks this call only and stops after its report. All offline tests and Ruff passed. Source fixtures and candidate weights stay on Modal; results are pending and no benefit is claimed yet.


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

Full measured class support, episode counts, precision and probability diagnostics: [completion report](../eval/raw/forecast_risk_v3_completion_summary.md), [raw results](../eval/raw/forecast_risk_v3_results.json). These are consumed modeled archive diagnostics with correlated hours and uncalibrated probabilities. No automatic adoption, human review, field test or measured billing is claimed.


### Measured v3 disposition

Matched weighted models improve from 0.7423 to 0.7638 accuracy and 0.4606 to 0.4848 macro-F1 on February–April 2026; poor-or-worse misses fall from 200/248 to 144/248, with false alarms increasing from 17 to 39. On May–September, accuracy improves from 0.8151 to 0.8295 and macro-F1 from 0.5001 to 0.5690; misses fall from 20/23 to 11/23, with false alarms increasing from 10 to 17. Poor+ Brier/ECE improve against the old weighted model on both windows, but in the later window ordinary expanded LightGBM has lower Brier/ECE than expanded weighted LightGBM. This is a tradeoff, not universal model superiority.

Expanded training contains 469 poor-or-worse hours in 115 episodes, including 27 severe hours in six episodes, using the descriptive six-hour gap rule. All candidates still predict below severe on all 11 severe hours in the pollution window and both severe hours in the later window. Hazardous training/evaluation support is zero; hazardous recall is unmeasured. Expanded weighted training now emits some severe predictions, but its seven pollution-window severe alerts are all false positives. Severe forecasting remains unresolved, so this candidate is research-only and not qualified for adoption. These are consumed modeled archive diagnostics; no human, field, medical or prospective claim follows.

The completed monitor is disabled. Offline pytest, nine focused forecast tests and Ruff passed. No serving artifact or model deployment changed; actual billed costs remain unmeasured.


## V4 completed and reviewed by three research agents

Six fixed candidates completed on Modal: weighted multiclass, median quantile and 90th-percentile quantile, each with 28 original versus 35 instantaneous-history columns. Both diagnostic baseline vectors reproduce v3 exactly; all source/row hashes match. Exact t+6 source checks passed on 32,826 rows, with zero rounded numeric-label disagreements in all periods. No archive refresh or weights download occurred.

Data agent: small mixed feature gains. Pollution classifier accuracy remains 0.7638, macro-F1 declines 0.4848 to 0.4772, poor+ misses stay 144/248, false alarms decline 39 to 34; severe false alarms increase 7 to 9. Other-season accuracy improves 0.8295 to 0.8306, poor+ misses improve 11 to 10/23 and false alarms stay 17; severe false alarms increase 0 to 1. Poor-episode any-hit declines 5 to 4/7 in the later window, despite one more caught hour. Hourly improvement is not broader episode coverage.

Architecture agent: quantile heads expose a tradeoff. Base-feature upper-quantile poor+ recall reaches 0.9073 and 0.9130 versus classifier 0.4194 and 0.5217. Accuracy falls from 0.7638 to 0.6638 and 0.8295 to 0.7474; false alarms rise 39 to 164 and 17 to 59. Its empirical coverage is only 0.7944 and 0.7447, below nominal 0.9. Augmented upper-quantile coverage is 0.8014 and 0.7480. None is a calibrated safety bound. Median MAE improves slightly with instantaneous history (18.21 to 18.00; 9.76 to 9.55), but median poor+ recall is lower than classification.

Safety agent: all six candidates miss all 13 severe hours in five episodes, all severe onsets. Development has 16 poor+ hours in seven episodes and zero severe hours; severe recall there is unmeasured. Training contains 27 severe hours in six episodes, with no hazardous examples. More modeling on these consumed windows does not provide independent severe-risk qualification.

Disposition: retain candidates as research evidence, with no automatic model adoption. All results are consumed CAMS/ERA5 modeled archive diagnostics, not station observations, prospective validation, human field evidence or medical safety. Actual billing is unmeasured. Severe modeling needs distinct severe development episodes and evidence beyond repeated diagnostic tuning. The full offline suite, eleven focused forecast tests and Ruff passed. The completed monitor is disabled.

[All six candidates and metrics](../eval/raw/forecast_risk_v4_completion_summary.md).

## Bounded forecast research follow-up

Consumed CAMS/ERA5 archive diagnostics; repeated research comparisons, not independent station or prospective validation.

| Round | Period | Candidate | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ false alarms | Poor+ recall | Severe+ misses/support | Episode any-hit |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| forecast_risk_v5 | development | incumbent | 0.8409 | 0.6552 | 14/16 | 9 | 0.125 | 0/0 | 2/7 |
| forecast_risk_v5 | development | challenger | 0.8470 | 0.6703 | 14/16 | 3 | 0.125 | 0/0 | 2/7 |
| forecast_risk_v5 | diagnostic_pollution | incumbent | 0.7638 | 0.4772 | 144/248 | 34 | 0.41935483870967744 | 11/11 | 34/49 |
| forecast_risk_v5 | diagnostic_pollution | challenger | 0.7596 | 0.4691 | 136/248 | 46 | 0.45161290322580644 | 11/11 | 33/49 |
| forecast_risk_v5 | diagnostic_other_seasons | incumbent | 0.8306 | 0.5696 | 10/23 | 17 | 0.5652173913043478 | 2/2 | 4/7 |
| forecast_risk_v5 | diagnostic_other_seasons | challenger | 0.8312 | 0.5435 | 12/23 | 21 | 0.4782608695652174 | 2/2 | 5/7 |
| forecast_risk_v6 | development | incumbent | 0.8409 | 0.6552 | 14/16 | 9 | 0.125 | 0/0 | 2/7 |
| forecast_risk_v6 | development | challenger | 0.8337 | 0.6729 | 5/16 | 60 | 0.6875 | 0/0 | 6/7 |
| forecast_risk_v6 | diagnostic_pollution | incumbent | 0.7638 | 0.4772 | 144/248 | 34 | 0.41935483870967744 | 11/11 | 34/49 |
| forecast_risk_v6 | diagnostic_pollution | challenger | 0.7592 | 0.5045 | 24/248 | 162 | 0.9032258064516129 | 11/11 | 49/49 |
| forecast_risk_v6 | diagnostic_other_seasons | incumbent | 0.8306 | 0.5696 | 10/23 | 17 | 0.5652173913043478 | 2/2 | 4/7 |
| forecast_risk_v6 | diagnostic_other_seasons | challenger | 0.8200 | 0.5262 | 3/23 | 63 | 0.8695652173913043 | 2/2 | 6/7 |

Completed rounds: 2; consecutive rounds without gated gain: 2. Stop reason: two_consecutive_no_gain.

V5 fitted paired classifiers on Modal. V6 evaluated the fixed poor-band floor using existing v4 classifier and quantile weights on Modal, with no refitting; this is one training round and one hosted architecture evaluation, not two training rounds. Exact incumbent and quantile prediction hashes reproduce v4. The reused bundle hash was observed at read time, not independently pinned before its original training.

Gas history improved some hourly metrics but degraded others and did not resolve severe misses. The fixed quantile floor trades fewer poor+ misses for more false alarms; it cannot raise a prediction to severe. No candidate is promoted. Development has zero severe support; training has only 27 severe hours across six descriptive episodes. Hazardous recall remains unmeasured. Full raw probabilities/reliability and predictions are preserved in the linked JSON artifacts. No human, field, medical or billed-cost evidence is claimed. This finite stopping rule does not establish maximum attainable performance.

Evidence: `eval/raw/forecast_risk_v5_results.json`, `eval/raw/forecast_risk_v6_results.json`, their `_gate_summary.json` files, and `eval/raw/forecast_next_completion_summary.json`. Three data, architecture and safety reviews are recorded for each round under `docs/FORECAST_V5_*_REVIEW.md` and `docs/FORECAST_V6_*_REVIEW.md`. Offline pytest and Ruff passed; eight focused checks cover causal features, rounded boundaries, episode regressions and the frozen stopping criteria.

Next research prerequisite: obtain distinct severe development episodes and a separately frozen future evaluation source, then test whether pollutant-specific forecasting generalizes. Repeating parameter changes on these same consumed windows cannot establish that. A larger transformer is not supported by the present evidence. Keep deterministic safety handling and current serving behavior.
# Reopened deep pollutant study

The user authorized a new research loop after the finite v5/v6 comparisons.
The implemented [research agenda](DEEP_RESEARCH_AGENDA.md) and
[frozen protocol](DEEP_POLLUTANT_STUDY_PROTOCOL.md) compare a three-seed causal
TCN with matched pollutant LightGBM and persistence baselines. Offline pytest,
seven focused checks and Ruff passed before submission. No local PyTorch or
weights were installed or fetched.

Modal accepted call `fc-01M4FFVSEHZWCJPY63XPC49NNY`, app
`ap-5XMZznjWFQljij21mY21UO`. Training was confirmed from the remote progress
artifact: seed 0 had reached epoch 20 at the first progress check. This is
training progress, not completed evaluation or a measured model improvement.
The monitor is enabled every ten minutes to fetch final metrics, review them
with research agents and continue justified follow-up experiments.

Primary-source category review corrected the terminology: historical `severe`
identifiers represent official Very Poor (301–400), while historical
`hazardous` represents official Severe (401–500). Existing raw artifacts and
stopped ledgers remain unchanged. New results use the official names and the
shared rounded canonical bands. This remains an instantaneous modeled-hour
proxy, not official station AQI.

The pre-fit support audit found 19,663 training origins with five Very Poor
hours in one episode; 1,435 development origins with 22 hours in five episodes;
2,107 pollution-diagnostic origins with eleven hours in four episodes; and
3,643 later-diagnostic origins with zero Very Poor hours. Full phase-local
24-hour histories exclude the two historical May-boundary events. Official
Severe has zero support throughout, so its recall is unmeasured. Both
diagnostics are previously consumed research data. No automatic promotion,
station/prospective validation, medical benefit or measured billing follows.


## Deep pollutant sequence v1 measured completion

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


Full [measured report](../eval/raw/pollutant_sequence_v1_completion_summary.md) and [machine-readable metrics](../eval/raw/pollutant_sequence_v1_completion_summary.json). Research-only consumed modeled archive; no automatic adoption or measured billing.


## Active deep study: v2 loss ablation (9 October 2026)

V1 completed; its fixed ensemble passed the retrospective research utility gate against the matching tree, but missed all eleven eligible Very Poor+ pollution hours. V2 changes only standardized SmoothL1 loss to MSE, retaining the same architecture, seeds, development checkpoint rule and data. The primary comparator is the frozen v1 fixed ensemble. Offline pytest and Ruff passed before submission. Hosted call `fc-01M4FGJG73MFMNR1EZFCNNFNZY`, app `ap-xvJUwXwSUCMSjNpflZe9Xn`. Results are pending; no improvement is yet claimed. [Preregistered protocol](POLLUTANT_SEQUENCE_V2_PROTOCOL.md). Reviewer quota/authentication failures prevented completed secondary v2 reviews; root checked the implementation. No model was promoted.


## Deep pollutant sequence v2 measured completion

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


Full [measured report](../eval/raw/pollutant_sequence_v2_completion_summary.md) and [machine-readable metrics](../eval/raw/pollutant_sequence_v2_completion_summary.json). Research-only consumed modeled archive; no automatic adoption or measured billing.


## V2 disposition and next weighting study

V2 completed in 335.298 seconds of remote run time (not billed cost). Its fixed ensemble failed the paired gate against v1: pollution Poor+ misses 133/248 versus 111/248, false alarms 32 versus 41; later misses 13/16 versus 12/16, false alarms zero versus one. Very Poor+ misses remain 11/11. All four v2 candidates failed the v1 comparison. Keep v1 as research incumbent; no adoption or deployment. V3 is being prepared with only training-origin risk weighting relative to v1 (SmoothL1, multiplier two on canonical Poor+ labels from training only). Completed secondary reviewers remain unavailable through provider quota/authentication/balance; root synthesis is disclosed.


## Active hosted study: v3 risk-weighted SmoothL1

Submitted exactly once as `fc-01M4FH3RPFGP8WW3B4HP033708`, app `ap-DSoWADIe18ypb2ODCLkHhC`. [Protocol](POLLUTANT_SEQUENCE_V3_PROTOCOL.md). Fixed training-only Poor+ origin weighting replaces uniform weighting relative to v1; no new data or evaluation relaxation. Full offline pytest, twelve focused sequence/report checks and Ruff passed. V3 result is PENDING; v1 remains research reference. The persistent monitor checks every ten minutes and preserves old artifacts/ledgers.


## Deep pollutant sequence v3 measured completion

# Deep pollutant sequence study: measured results

All candidates were evaluated on identical phase-local 24-hour-context origins. Both 2026 periods are consumed modeled-archive diagnostics, not fresh holdouts. The primary reference is the frozen v1 three-seed concentration-average ensemble. Matched LightGBM remains a secondary comparator.

Historical raw `severe` means official Very Poor (301â€“400); `hazardous` means official Severe (401+). This is an instantaneous concentration proxy, not averaging-compliant station AQI.

| Period | Model | n | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ recall | Poor+ precision | Poor+ FAR | Very Poor+ misses/support | Very Poor+ recall | Very Poor+ FAR | Severe misses/support |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| development | tcn_seed_0 | 1435 | 0.730314 | 0.560950 | 94/168 | 0.440476 | 0.860465 | 0.009471 | 21/22 | 0.045455 | 0.000000 | 0/0 |
| development | tcn_seed_1 | 1435 | 0.739373 | 0.570759 | 58/168 | 0.654762 | 0.814815 | 0.019732 | 22/22 | 0.000000 | 0.001415 | 0/0 |
| development | tcn_seed_2 | 1435 | 0.735889 | 0.579122 | 61/168 | 0.636905 | 0.842520 | 0.015785 | 21/22 | 0.045455 | 0.002123 | 0/0 |
| development | tcn_fixed_mean | 1435 | 0.745645 | 0.576626 | 62/168 | 0.630952 | 0.876033 | 0.011839 | 22/22 | 0.000000 | 0.000708 | 0/0 |
| development | paired_lightgbm | 1435 | 0.743554 | 0.560935 | 79/168 | 0.529762 | 0.855769 | 0.011839 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | persistence | 1435 | 0.364460 | 0.257717 | 146/168 | 0.130952 | 0.130952 | 0.115233 | 22/22 | 0.000000 | 0.015570 | 0/0 |
| development | v1_fixed_mean | 1435 | 0.738676 | 0.562208 | 75/168 | 0.553571 | 0.885714 | 0.009471 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_0 | 2107 | 0.786901 | 0.480468 | 99/248 | 0.600806 | 0.726829 | 0.030124 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_1 | 2107 | 0.788799 | 0.523214 | 86/248 | 0.653226 | 0.757009 | 0.027972 | 11/11 | 0.000000 | 0.000477 | 0/0 |
| diagnostic_pollution | tcn_seed_2 | 2107 | 0.787375 | 0.516024 | 86/248 | 0.653226 | 0.733032 | 0.031737 | 10/11 | 0.090909 | 0.000477 | 0/0 |
| diagnostic_pollution | tcn_fixed_mean | 2107 | 0.791172 | 0.486293 | 88/248 | 0.645161 | 0.740741 | 0.030124 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | paired_lightgbm | 2107 | 0.794495 | 0.506529 | 129/248 | 0.479839 | 0.815068 | 0.014524 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | persistence | 2107 | 0.385382 | 0.211169 | 231/248 | 0.068548 | 0.068548 | 0.124260 | 11/11 | 0.000000 | 0.005248 | 0/0 |
| diagnostic_pollution | v1_fixed_mean | 2107 | 0.788799 | 0.486780 | 111/248 | 0.552419 | 0.769663 | 0.022055 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_0 | 3643 | 0.838869 | 0.743890 | 7/16 | 0.562500 | 0.529412 | 0.002206 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_1 | 3643 | 0.845183 | 0.721250 | 6/16 | 0.625000 | 0.333333 | 0.005514 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_2 | 3643 | 0.854516 | 0.760749 | 9/16 | 0.437500 | 0.777778 | 0.000551 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_fixed_mean | 3643 | 0.847928 | 0.789472 | 6/16 | 0.625000 | 0.769231 | 0.000827 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | paired_lightgbm | 3643 | 0.839967 | 0.664454 | 13/16 | 0.187500 | 0.333333 | 0.001654 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | persistence | 3643 | 0.451551 | 0.299947 | 16/16 | 0.000000 | 0.000000 | 0.004411 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | v1_fixed_mean | 3643 | 0.854516 | 0.716318 | 12/16 | 0.250000 | 0.800000 | 0.000276 | 0/0 | UNMEASURED | 0.000000 | 0/0 |


Full [measured report](../eval/raw/pollutant_sequence_v3_completion_summary.md) and [machine-readable metrics](../eval/raw/pollutant_sequence_v3_completion_summary.json). Research-only consumed modeled archive; no automatic adoption or measured billing.


## V3 completed: passed finite retrospective gate

V3 passed the preregistered research gate versus the frozen v1 ensemble on both consumed 2026 diagnostics. Pollution Poor+ misses fell 111/248→88/248 while false alarms rose 41→56; later misses fell 12/16→6/16 while false alarms rose 1→3. The fixed ensemble still missed all 11 pollution Very Poor+ hours; later Very Poor+ and official Severe recall remain unmeasured. The 296/19,663 training weighting-support check passed. [Full paired review and next-data requirements](POLLUTANT_SEQUENCE_V3_REVIEW.md).


## Reopened v4 residual experiment and three completed reviews

The user reopened continued research. Three reviewers completed this round and supported a single residual representation ablation; historical provider failures do not describe these reviews. The earlier conclusion that no further experiment was justified is revised: consumed diagnostics restrict external claims, but a distinct adaptive hypothesis remains legitimate. V4 predicts (future-current)/the same absolute training target scale, decodes current+output*scale, and compares the fixed ensemble to frozen v3. Data, model, weights, seeds and gates stay fixed. Full offline pytest and Ruff passed before one submission: `fc-01M4FJ5XZTY70CX9HZ9VFSKZG8`, app `ap-ZCEDn4h4FTeo8QfGVIUbGc`. Results PENDING. [Protocol](POLLUTANT_SEQUENCE_V4_PROTOCOL.md), [three reviews](POLLUTANT_SEQUENCE_V4_RESEARCH_REVIEWS.md), [depth roadmap](REOPENED_RESEARCH_ROADMAP.md). No product promotion or independent station qualification.


## Deep pollutant sequence v4 measured completion

# Deep pollutant sequence study: measured results

All candidates were evaluated on identical phase-local 24-hour-context origins. Both 2026 periods are consumed modeled-archive diagnostics, not fresh holdouts. The primary reference is the frozen v3 three-seed concentration-average ensemble. Matched LightGBM remains a secondary comparator.

Historical raw `severe` means official Very Poor (301â€“400); `hazardous` means official Severe (401+). This is an instantaneous concentration proxy, not averaging-compliant station AQI.

| Period | Model | n | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ recall | Poor+ precision | Poor+ FAR | Very Poor+ misses/support | Very Poor+ recall | Very Poor+ FAR | Severe misses/support |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| development | tcn_seed_0 | 1435 | 0.698955 | 0.510189 | 100/168 | 0.404762 | 0.871795 | 0.007893 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | tcn_seed_1 | 1435 | 0.724739 | 0.629951 | 55/168 | 0.672619 | 0.856061 | 0.014996 | 16/22 | 0.272727 | 0.004246 | 0/0 |
| development | tcn_seed_2 | 1435 | 0.758188 | 0.660446 | 56/168 | 0.666667 | 0.811594 | 0.020521 | 15/22 | 0.318182 | 0.004246 | 0/0 |
| development | tcn_fixed_mean | 1435 | 0.737282 | 0.580140 | 68/168 | 0.595238 | 0.877193 | 0.011050 | 21/22 | 0.045455 | 0.001415 | 0/0 |
| development | paired_lightgbm | 1435 | 0.743554 | 0.560935 | 79/168 | 0.529762 | 0.855769 | 0.011839 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | persistence | 1435 | 0.364460 | 0.257717 | 146/168 | 0.130952 | 0.130952 | 0.115233 | 22/22 | 0.000000 | 0.015570 | 0/0 |
| development | v3_fixed_mean | 1435 | 0.745645 | 0.576626 | 62/168 | 0.630952 | 0.876033 | 0.011839 | 22/22 | 0.000000 | 0.000708 | 0/0 |
| diagnostic_pollution | tcn_seed_0 | 2107 | 0.789274 | 0.548512 | 116/248 | 0.532258 | 0.776471 | 0.020441 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_1 | 2107 | 0.794495 | 0.583828 | 77/248 | 0.689516 | 0.721519 | 0.035503 | 10/11 | 0.090909 | 0.000954 | 0/0 |
| diagnostic_pollution | tcn_seed_2 | 2107 | 0.795918 | 0.534362 | 76/248 | 0.693548 | 0.738197 | 0.032813 | 11/11 | 0.000000 | 0.002385 | 0/0 |
| diagnostic_pollution | tcn_fixed_mean | 2107 | 0.796393 | 0.548551 | 88/248 | 0.645161 | 0.761905 | 0.026896 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | paired_lightgbm | 2107 | 0.794495 | 0.506529 | 129/248 | 0.479839 | 0.815068 | 0.014524 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | persistence | 2107 | 0.385382 | 0.211169 | 231/248 | 0.068548 | 0.068548 | 0.124260 | 11/11 | 0.000000 | 0.005248 | 0/0 |
| diagnostic_pollution | v3_fixed_mean | 2107 | 0.791172 | 0.486293 | 88/248 | 0.645161 | 0.740741 | 0.030124 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_0 | 3643 | 0.850947 | 0.751999 | 10/16 | 0.375000 | 1.000000 | 0.000000 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_1 | 3643 | 0.842438 | 0.774007 | 4/16 | 0.750000 | 0.545455 | 0.002757 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_2 | 3643 | 0.861378 | 0.789140 | 5/16 | 0.687500 | 0.611111 | 0.001930 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_fixed_mean | 3643 | 0.857260 | 0.802230 | 6/16 | 0.625000 | 0.833333 | 0.000551 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | paired_lightgbm | 3643 | 0.839967 | 0.664454 | 13/16 | 0.187500 | 0.333333 | 0.001654 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | persistence | 3643 | 0.451551 | 0.299947 | 16/16 | 0.000000 | 0.000000 | 0.004411 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | v3_fixed_mean | 3643 | 0.847928 | 0.789472 | 6/16 | 0.625000 | 0.769231 | 0.000827 | 0/0 | UNMEASURED | 0.000000 | 0/0 |


Full [measured report](../eval/raw/pollutant_sequence_v4_completion_summary.md) and [machine-readable metrics](../eval/raw/pollutant_sequence_v4_completion_summary.json). Research-only consumed modeled archive; no automatic adoption or measured billing.

## Read-only pollutant context support audit completed

Modal call `fc-01M4FK0MTAX6ZMYG4MJ5S3WEZ4` completed once; its saved result and manifest hashes verified. The audit rechecked 32,826/32,826 canonical six-hour target index/band pairs, with zero missing timestamps and zero incomplete finite six-gas sequences. Phase-local eligible counts at 24/48/72 hours were train 19,663/19,639/19,615; development 1,435/1,411/1,387; pollution diagnostic 2,107/2,083/2,059; other-seasons diagnostic 3,643/3,619/3,595. Poor+ support stayed 296 hours/86 episodes for train, 168/28 for development, and 248/49 for pollution at all lengths. Other-seasons support fell from 16/6 to 13/5 at 48h and stayed 13/5 at 72h. Training Very Poor+ support remained only five hours in one episode; official Severe support was zero in every phase, so Severe recall remains UNMEASURED. The longer histories lose only phase-boundary origins; exact eligible timestamp hashes are saved in the raw result. Three reviewers agreed a matched 48h set is feasible, but one noted the evidence does not show older lags add predictive value. Decision: no model fit yet; first test that incremental-signal hypothesis on development only. Details and review synthesis: [context support report](POLLUTANT_CONTEXT_SUPPORT_V1_REVIEW.md). This is a support audit over consumed CAMS/ERA5 modeled archive, not performance validation or station evidence.

## Fixed older-history probe v1: measured development results

Modal call `fc-01M4FM73AHVNNJFY7F8SGSYD8Q`, app `ap-LOJY41QfJZesEwi80LRam5` completed once. Both fits used the exact same 19,639 train and 1,411 development origins; 21,050 canonical target pairs verified. Median imputation, input scaling and target scales fit only on training. There were 296 Poor+ weighted training origins. No 2026 diagnostic labels entered this study.

| Development period | Context | n | Normalized MAE | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ false alarms | Poor+ episode hits/support | Very Poor+ misses/support |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 24h | 1411 | 0.474160 | 0.759745 | 0.638596 | 64/168 | 23 | 21/28 | 18/22 |
| overall | 48h | 1411 | 0.471746 | 0.751240 | 0.626867 | 64/168 | 22 | 21/28 | 18/22 |
| 2025-04 | 24h | 673 | 0.532290 | 0.760773 | 0.490218 | 48/122 | 7 | 16/21 | 8/8 |
| 2025-04 | 48h | 673 | 0.532371 | 0.760773 | 0.485323 | 48/122 | 7 | 16/21 | 8/8 |
| 2025-05 | 24h | 738 | 0.421149 | 0.758808 | 0.637216 | 16/46 | 16 | 5/7 | 10/14 |
| 2025-05 | 48h | 738 | 0.416461 | 0.742547 | 0.629883 | 16/46 | 15 | 5/7 | 10/14 |

48h relative normalized MAE improvement: 0.509%. Predeclared exploratory context screen passed: **False**.

- overall_normalized_mae_gain_at_least_1pct: False
- neither_month_normalized_mae_worse: False
- poor_misses_not_worse: True
- poor_false_alarms_not_worse: True
- poor_episode_hits_not_worse: True
- very_poor_misses_not_worse: True
- very_poor_false_alarms_not_worse: False

Full raw results include six pollutant MAEs, recalls/precision/FAR, episode counts, monthly scores, negative pre-clipping predictions, train scales, actual and predicted development concentrations, and exact origin hashes. These are consumed CAMS/ERA5 modeled archive diagnostics, not independent station, prospective or medical qualification. Unsupported recall is UNMEASURED. A fixed linear probe cannot disprove nonlinear older-history value. No promotion, deployment or billed cost is claimed.


## V5 endpoint-priority study completed

The hosted run completed after 277.37 seconds with 296/19,663 weighted train origins. All three seeds and the fixed mean failed the frozen V3 gate; the fixed mean had Poor+ misses 94/248 versus 88 in the pollution diagnostic and 10/16 versus 6 in the later diagnostic. The complete measured comparison is in [the raw completion report](../eval/raw/pollutant_sequence_v5_completion_summary.md). Three independent read-only result reviews found no pairing defect and no case for another fit on this consumed archive. Saved development analysis finds all 168 Poor+ hours ozone-controlled, with V5 ozone MAE 22.88 versus V3 21.86 and bias -21.66 versus -20.14. See [event and gas attribution](../eval/raw/pollutant_sequence_v5_error_analysis.md) and [review synthesis](POLLUTANT_SEQUENCE_V5_RESULT_REVIEWS.md). V5 remains rejected as incumbent; the model remains research-only.

## Research reopened after V5

The user authorized continued research on 2026-10-09. A target-contract audit, station-source investigation and distinct-hypothesis review are in progress. See [the execution plan](CONTINUED_RESEARCH_EXECUTION.md). No new performance scores or global maximum are claimed.


# Target-contract audit: measured results

Hosted read-only CPU call fc-01M4FQ5AR38P77DCWRDAZ9N2M3, app ap-EYjomUeIBrjTquMy5bYdOv. All 32,826 historical instantaneous targets verified. Complete-window decomposition identity error was zero in every phase.

| Phase | Paired origins | Hourly Poor+ / VP+ | Trailing Poor+ / VP+ | Conservative Poor+ / VP+ |
|---|---:|---:|---:|---:|
| train | 19663 | 296 / 5 | 74 / 0 | 344 / 5 |
| development | 1435 | 168 / 22 | 94 / 6 | 213 / 27 |
| diagnostic_pollution | 2107 | 248 / 11 | 113 / 0 | 317 / 11 |
| diagnostic_other_seasons | 3643 | 16 / 0 | 0 / 0 | 16 / 0 |

Official Severe support is zero under every target in every phase. Later complete-trailing Poor+ support is also zero: recall is UNMEASURED, not successful detection.

Period averaging changes the task and cannot be reported as an improvement in historical model accuracy. The conservative product approximation retains hourly spikes and additionally includes persistent elevated averages. Training on trailing means alone would remove the five training Very Poor hours and is not justified as a safety improvement.

Causal persistence trailing Poor+ recall/precision: train 0.6216/0.1581; development 0.6489/0.3631; pollution diagnostic 0.6549/0.3020; later recall UNMEASURED with 15 false alarms. These are a baseline on a different target, not neural results.

No station quality, pristine evaluation, prospective, medical, probability calibration or billed-cost claim. Saved neural h6 outputs cannot reconstruct full trajectories; further inference would require the existing hosted checkpoints.

The development-only fixed-linear comparison provides a distinct algorithm hypothesis. Keep its original hourly task and frozen V3 gate for comparability while independently qualifying station sources.


## Linear v1 startup failure and GPU replacement

The CPU call never entered training. App logs recorded ModuleNotFoundError for probe_pollutant_lag_modal at module hydration; repeated pending fetches did not reveal these container initialization failures. The failed call/source hashes and log are preserved; app ap-WKqEXk9UEV8FEfre0BhVkz was stopped. No performance scores exist for this call. A distinct GPU v2 fixes the pre-import helper path and computes weighted Ridge fitting/predictions with CUDA float64 on one T4, with numerical residual and tiny-matrix CPU-reference parity checks. Submission is in progress; no completion/GPU execution claim yet. See POLLUTANT_LINEAR_V2_GPU_PROTOCOL.md.


## Deep pollutant GPU linear v2 measured completion

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


Full [measured report](../eval/raw/pollutant_linear_v2_gpu_completion_summary.md) and [machine-readable metrics](../eval/raw/pollutant_linear_v2_gpu_completion_summary.json). Research-only consumed modeled archive; no automatic adoption or measured billing.
