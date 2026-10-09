# Deep pollutant sequence study: preregistered initial experiment

The user reopened hosted research after the v5/v6 comparisons failed the earlier improvement rule. This is a new study; the old two-no-gain state and ledgers remain unchanged. Longer computation is authorized, but duration alone is not evidence of improvement. No candidate is automatically promoted or deployed.

## Question and target

Can forecasting six pollutant concentrations from a causal 24-hour sequence recover rare pollution onsets better than a matched tree model? Predict PM2.5, PM10, NO2, O3, CO and SO2 at each of the next six hours. Derive the final-sixth-hour maximum sub-index exclusively from the six predicted concentrations. Never combine a predicted pollutant with another pollutant's actual future concentration. Clip negative concentration predictions at zero and report the clipping rule. The target is the same calculation on modeled actual sixth-hour concentrations.

This is a CPCB-breakpoint instantaneous concentration proxy, not official station AQI. Standard AQI uses pollutant-specific averaging and additional coverage requirements; the archive is CAMS/ERA5 modeled data, not station observations. NH3 and Pb are unavailable. Actual future weather must not enter predictors.

## Frozen temporal protocol

- Training origins and their complete context/targets: 2023-01-01 inclusive to 2025-04-01 exclusive.
- Development origins and their complete context/targets: 2025-04-01 inclusive to 2025-06-01 exclusive.
- Pollution diagnostic: 2026-02-01 inclusive to 2026-05-01 exclusive.
- Other-season diagnostic: 2026-05-01 inclusive to 2026-10-01 exclusive.

Each eligible origin requires all 24 timestamp-matched context hours and all six timestamp-matched future hours to lie wholly within its phase, with finite required continuous measurements. Missing timestamps must never become positional offsets. All models use the identical eligible origins. Record exclusions, resolved bounds, source fixture and row hashes, class support and six-hour-separated episode counts before fitting. There is no new untouched evaluation period here: both 2026 windows have already informed research. Development was chosen after prior results and is also not pristine.

Fit normalization only on training inputs and training targets. Keep development and diagnostics out of fitted normalization. If development has zero Very Poor-or-worse target support, disclose that fact: no severity calibration or severity-driven checkpoint selection is possible. Do not borrow diagnostic labels to fill this gap or silently impose/relax the previous classifier's twenty-positive-hour gate on this continuous regression experiment.

## Fixed initial models

1. Persistence: repeat the current six concentrations through the six-hour horizon.
2. Matched LightGBM: six concentration regressors for the final-sixth-hour target, using the same causal context/origins. Fixed v4 parameters: 450 estimators, learning rate 0.04, 28 leaves, subsample/column fraction 0.85, alpha regularization 0.5, lambda regularization 1, random seed 0, two threads.
3. Causal residual TCN: width 32; four blocks with dilation 1, 2, 4, 8; kernel 3; dropout 0.1. Predict all six future hours and six pollutants. Three training seeds, 0/1/2. SmoothL1 training loss on standardized targets, AdamW learning rate 0.001 and weight decay 0.0001, batch 256, maximum 60 epochs, patience 8. Choose each seed's checkpoint using development standardized MAE only. Report every seed and the concentration-average three-seed ensemble; do not choose a seed using the diagnostic metrics.

The concrete runner's hashed manifest pins feature names and ordering, channel normalization, architecture and all parameters. Any later change requires a new preregistered manifest and distinct call. One T4 container, timeout two hours, no automatic retries. Weights stay on the hosted volume; fetch only small results and metadata.

## Paired utility gate

The reference is the new matched LightGBM baseline, not v4: requiring 24 hours of full context changes eligible origins. In **both** diagnostic periods, a proposed candidate must have:

- band accuracy loss no greater than 0.01;
- Poor-or-worse false alarm rate no greater than reference + 0.01 and no greater than 0.05;
- Very Poor-or-worse false alarm rate no greater than reference + 0.0025 and no greater than 0.01;
- no increase in Very Poor-or-worse missed hours and no decline in positive-episode any-hit counts.

It must additionally gain Poor-or-worse recall by at least 0.05 in one period with no recall decline in the other; **or** detect at least two additional Very Poor-or-worse hours within an episode fully missed by the reference, with no Poor-or-worse recall decline in either period. Exact paired new-hit counts come from per-origin predictions. Passing this finite retrospective gate licenses more qualification work, not deployment or an air-safety claim.

Risk categories use the source-pinned `band_for_index` rounding and ordinal mapping, not raw floating-point comparisons against 201/301/401. Those integer ranges below are category descriptions; a rounded 200.51 proxy is Poor while 200.5 uses the existing canonical rounding behavior.

## Measured eligibility audit before fitting

The hosted support audit resolved training to 19,663 origins, including only **5 Very Poor-or-worse hours in one descriptive episode**; development to 1,435 origins with 22 such hours in five episodes; pollution diagnostics to 2,107 origins with 11 such hours in four episodes; other-season diagnostics to 3,643 origins with **zero** such hours. The old two May 1 positive hours are excluded by this study's whole-phase 24-hour context rule. There are zero official Severe (401+) proxy targets in all four phases. These counts trace to `eval/raw/pollutant_sequence_support_results.json`, not to a trained model result. Later-season Very Poor recall and all official Severe recalls are unmeasured. A pollution-period research gain does not establish all-season Very Poor detection, and this study cannot qualify official Severe detection. Sparse training support remains a serious limitation despite nonzero development support.

## Official naming correction

CPCB categories are Good, Satisfactory, Moderately polluted, Poor, **Very Poor (301–400)** and **Severe (401–500)**. Repository historical raw ordinal labels `severe` (301–400) and `hazardous` (401+) do not use those official names. Preserve old raw files; this study reports ordinal >=4 as Very Poor-or-worse and ordinal >=5 as Severe. Earlier statements that all thirteen `severe` hours were missed refer to Very Poor-or-worse proxy hours, not thirteen official Severe observations.

The [Government of India published breakpoint table](https://www.pib.gov.in/newsite/printrelease.aspx?lang=2&reg=48&relid=110654) lists the ozone Poor upper endpoint 208 and Very Poor lower endpoint 209, with a one-hour mathematical-calculation footnote on the high ozone bands. The existing implementation uses continuous intervals starting above 208; preserve this numeric implementation in the paired study and disclose it. That convention is not proof of valid official averaging. See also the [CPCB final technical report](https://www.cpcb.gov.in/displaypdf.php?id=bmF0aW9uYWwtYWlyLXF1YWxpdHktaW5kZXgvRklOQUwtUkVQT1JUX0FRSV8ucGRm).

## Completion and subsequent research

Preserve raw predictions, checkpoints on Modal, source hashes, training histories and actual call/app IDs. Report all results, including regressions and unsupported classes. A failed support/data audit ends this call with a truthful failure artifact; do not weaken the gate or resubmit the same manifest. The user has reopened continued research, so the old two-no-gain rule does not stop this new study. Each next approach still needs evidence, a recorded protocol and a distinct idempotent submission; no endlessly repeated identical jobs.
