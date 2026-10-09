# Pollutant target contract audit v1

This is a read-only CPU audit of the consumed CAMS modeled archive on the existing baahar-training volume. It fits no model, changes no historical labels or gates, and downloads only small metadata/results. Root decides whether and when to submit the source-pinned runner. An existing manifest prevents duplicate submission.

## Why this comes before another fit

V3–V5 predict six concentration horizons but score only instantaneous t+6 concentrations through CPCB breakpoints. V5 worsened development ozone bias and Poor+ misses. The production policy also computes period means and chooses the higher of instantaneous and trailing index. Training/evaluation targets and runtime policy therefore differ. Changing to period means may reduce or increase positive support; that is a different target, not an accuracy improvement in the historical task.

The [CPCB primary AQI report](https://airquality.cpcb.gov.in/ccr_docs/FINAL-REPORT_AQI_.pdf) specifies 24-hour pollutant averages, 8-hour CO/O3 averages, at least three pollutants including PM2.5 or PM10, and a minimum 16-hour data criterion. This audit uses stricter complete 24/8-hour windows for six gases and does not interpret the 16-hour statement as a permission to label partial 8-hour windows official. It does not reproduce station measurement quality assurance, every pollutant, all bulletin conventions or every breakpoint detail. Its output is a period-correct modeled approximation, not official station AQI.

## Exact causal reconstruction

At origin t, 24 historical hourly entries end at t. Forecast entries cover t+1 through t+6. The t+6 inclusive 24-hour window is t−17 through t+6: 18 known entries plus six forecasts. The 8-hour window is t−1 through t+6: two known entries plus six forecasts. Each concentration mean is reconstructed first; then each pollutant's subindex is computed and the maximum is rounded for its canonical band. Averaging subindices instead would be wrong.

Ground truth uses actual future concentrations only for target construction. A causal persistence diagnostic repeats the origin concentration over all six future entries; it never reads future values as inputs. An oracle reconstruction identity verifies this decomposition against compute_naqi_trailing on complete histories, but is not a forecast score.

## Eligibility and outputs

Use the frozen train/development/two diagnostic phase bounds and pinned source fixtures/rows. Eligible origins require every timestamp t−23 through t+6 within the phase, one-hour continuity, and all six gases finite and nonnegative. No imputation, sorting away source defects, relaxed coverage or cross-phase history. Validate every historical row's exact instantaneous t+6 label before comparing targets. Record boundary/missing/invalid exclusions and eligible timestamp hashes.

On the same eligible origins, report instantaneous, complete trailing, and conservative max target band support, Poor+/Very Poor+/Severe hours and six-hour-gap episode support, instantaneous-to-trailing transition counts, trailing controlling gases and index differences. Report causal persistence trailing NAQI MAE, confusion counts, recall and precision. Zero-support recall remains null/UNMEASURED; Brier/ECE cannot be computed from point forecasts. These diagnostic windows and families were consumed previously; they are not pristine or prospective holdouts.

## Existing implementation limitations

compute_naqi_trailing accepts three usable samples per pollutant, checks timestamp order but not hourly spacing, and accepts fewer than three pollutants without requiring particulate matter. It skips invalid values and transparently records counts, so its partial result must remain labeled an approximation. This audit requires complete windows and does not silently alter runtime code. The legacy severe band string denotes official Very Poor (301–400); hazardous denotes official Severe (401+).

Historical neural raw results save only sixth-hour pollutant forecasts. Full six-horizon forecasts are necessary for exact period reconstruction; repeating a learned h6 prediction across earlier hours would invent model outputs. This audit therefore cannot honestly produce V3/V5 trailing-target model accuracy from saved point outputs. Before a later hosted inference study, verify a source-pinned checkpoint and export all horizons without training again, or preregister a distinct target study if such checkpoints are unavailable. Any new target gate must be explicit and cannot claim a pass of the historical instantaneous gate.

## Reproducibility and boundaries

Runner: scripts/audit_pollutant_target_contract_modal.py. One CPU-only call, 600-second timeout, retries zero, one container. Submission pins runner, this protocol, naqi.py, package initializer, source fixtures and rows. Fetch uses a five-second timeout and refuses to overwrite saved raw output. Source hashes, phase support and result identity precede interpretation. No serving/promotion/deployment, model weights, local PyTorch, billing claims or edits to previous study chains.
