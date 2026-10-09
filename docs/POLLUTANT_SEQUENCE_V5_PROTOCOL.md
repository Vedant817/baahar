# V5: endpoint-priority objective with retained trajectory supervision

The matched 24/48h Ridge probe completed and failed its predeclared context screen. Overall normalized MAE improved only 0.509%; category accuracy decreased 75.9745% to 75.1240%, Poor+ misses remained 64/168, and Very Poor+ false alarms increased from two to four. The probe cannot rule out nonlinear older-history information, but it gives no affirmative case for increasing context or capacity now. Its macro-F1 uses the actual/predicted class union, unlike the neural reporter's observed-actual label set; do not directly compare those F1 values across studies.

Three new read-only reviewers identified a concrete objective mismatch: V3 averages training loss and development checkpoint score over all six horizons, but evaluates risk at only the sixth hour. This does not prove negative transfer or a bug. The following bounded study tests one coordinated objective-and-selection hypothesis; improvement cannot be attributed separately to loss weighting or checkpoint choice.

Relative to frozen V3, use:

`origin_loss = 0.5 * mean(all six horizons and gases) + 0.5 * mean(sixth-hour gases)`

Apply this to elementwise SmoothL1 on the same absolute, train-standardized targets, then retain V3's existing 2x Poor+ training-origin weighting and weighted-batch normalization. Horizon weights are exactly `(1/12, 1/12, 1/12, 1/12, 1/12, 7/12)`. Use identical horizon weights on absolute standardized development error to select checkpoints. Record the selection score, ordinary all-horizon MAE, and sixth-hour MAE each epoch. Retain supervision for earlier horizons; no zero-supervision heads and no horizon-weight sweep.

Everything else stays frozen: full phase-local 24h origin sets; train19,663/development1,435/pollution2,107/other-seasons3,643; 296/19,663 Poor+ training weights; all-horizon absolute-target scales; train-only imputation/scaling; input channels; six-horizon architecture; 3 seeds [0,1,2]; batch256; AdamW lr0.001/weight_decay0.0001; clipping; 60 epochs/patience8; fixed concentration-average ensemble; source fixtures and row hash. No future weather input, dataset extension, target relabeling or threshold change.

Compare primary fixed ensemble to SHA-pinned V3 fixed mean on identical ordered timestamps, actual pollutant arrays, canonical indices/categories and partitions. The secondary tree/persistence baselines must reproduce their existing predictions exactly. Preserve the V4 reporter's V3 gate verbatim: no Poor+ recall decrease in either consumed diagnostic; either >=0.05 Poor+ recall gain in at least one period or the existing paired Very Poor episode-hit branch; unchanged accuracy, false-alarm, misses and episode guardrails. Report every seed and ensemble, pollutant MAE/RMSE, risk support/recall/precision/FAR, episode hits and training curves. Unsupported recall remains UNMEASURED; Brier/ECE remain null for concentration forecasts.

Only five Very Poor training hours occur in one episode. Pollution has 11 Very Poor+ hours in four episodes; later has zero. Official Severe is absent everywhere. These are adaptively reused CAMS/ERA5 modeled-archive diagnostics, not station observations, pristine holdouts, prospective tests or medical qualification. No promotion, serving changes or claimed billing. One source-pinned T4 call with timeout7200/retries0; no local torch/weights. Existing manifest or active submission prevents another call. Preserve all V1-V4 and lag-probe sources/results.

Primary mechanism reference: [PyTorch SmoothL1 elementwise reduction](https://docs.pytorch.org/docs/2.6/generated/torch.nn.SmoothL1Loss.html). Horizon prioritization is the study hypothesis, not a claimed external performance guarantee.
