# Reopened forecast research agenda after v3

The user authorizes continued hosted research, including longer runs when needed. Three follow-up reviewers completed and supported a distinct v4 residual experiment. See [their reviews](POLLUTANT_SEQUENCE_V4_RESEARCH_REVIEWS.md) and [the frozen v4 protocol](POLLUTANT_SEQUENCE_V4_PROTOCOL.md). Earlier provider outages are historical; they do not describe these completed reviews. The old forecast tuning counters remain preserved.

## Objective and current evidence

Improve detection of polluted future hours without excessive false alarms, loss of common-category accuracy or fabricated safety. V3's fixed ensemble passed the v1 research gate: pollution Poor+ recall 0.5524→0.6452, false alarms 41→56; later recall 0.25→0.625, false alarms 1→3. Its fixed ensemble still missed all eleven eligible Very Poor pollution hours. Only five Very Poor hours in one episode occur in training; official Severe has no support. These are consumed modeled-archive diagnostics, not independent station qualification.

## Stage 1: current-referenced forecast, v4

Keep v3's inputs, architecture, seeds, weights and optimization. Learn future-minus-current pollutant changes with the SAME absolute-target training scales, reconstruct concentrations and compare to the fixed v3 ensemble. This tests an optimization shortcut without changing data or capacity. Report all seeds, pollutant errors, recall/precision/FAR, missed hours and episode detection. Existing gates stay fixed. Longer unchanged training is not indicated by v3's checkpoint plateaus.

## Stage 2: diagnose before choosing another fit

V4 completed and failed its paired fixed-mean episode gate: pollution-window Poor+ episode hits decreased from 41/49 to 40/49 while the count of missed Poor+ hours stayed at 88/248. Its pollution false alarms fell from 56 to 50, but it still missed all 11 eligible Very Poor+ hours. Three reviewers found no integrity defect and recommended saved-output development error attribution plus a support audit before another fit. The completed analysis is `eval/raw/pollutant_sequence_v4_error_analysis.md`; it verifies paired targets and reports event-level transitions. Use actual saved outputs; v1-v3 endpoint predictions cannot support all-horizon claims. Preserve unsuccessful v4 and keep v3 as its comparison. Do not select a seed or tune a cutoff using diagnostic labels.

## Stage 3: longer causal context if evidence supports it

A 48- or 72-hour history could expose prior-day patterns. A read-only Modal audit completed as `eval/raw/pollutant_context_support_v1_manifest.json` (call `fc-01M4FK0MTAX6ZMYG4MJ5S3WEZ4`, app `ap-WvQPIWiaSDVO8kdHtQE8Rf`). It checked phase-local exact finite gas histories, 32,826 canonical t+6 targets, category/episode support, and eligible-origin timestamp hashes. It pins v3/v4 artifacts, source fixtures, rows, and code. The audit shows 48h is feasible and retains observed rare-event counts in train, development and pollution diagnostic, but reviewers found no evidence yet that older lags add predictive value. Therefore the next step is a development-only incremental-lag signal check, not a model fit. If that check supports context, compare 24h and 48h models on the exact same eligible origin intersection and report full-period summaries separately. Keep future weather out of inputs, training-only preprocessing and wholly phase-local histories/targets. A different denominator is not an architecture win. This requires a distinct protocol/call, not an automatic parameter sweep. See [the audit review](POLLUTANT_CONTEXT_SUPPORT_V1_REVIEW.md).

## Stage 4: capacity or attention if a matched question exists

Use a small attention or linear temporal comparator only after identifying a representation/context limitation on development. Hold data, feature order, eligible origins, seeds, optimization budget and the comparison rule fixed where possible. Do not infer that more parameters, pretraining or GPU hours improve Bengaluru accuracy. A relevant pretrained model requires verified compatible input channels, units, sample interval and source coverage; unrelated language-model pretraining does not provide a six-pollutant forecasting contract. The [original linear-versus-transformer forecasting study](https://arxiv.org/abs/2205.13504) supports testing architecture empirically, not a universal claim that either architecture wins here.

## Current follow-up: V5 objective alignment after the lag probe

The fixed matched-origin 24/48h probe has now completed on Modal. Its 48h screen failed: normalized MAE gain 0.509%, category accuracy 75.9745% to 75.1240%, unchanged Poor+ misses64/168, and Very Poor+ false alarms2 to4. Three new reviewers found no pairing/scaling bug and supported endpoint-objective research. V5 retains 24h context and architecture, but trains and checkpoint-selects with half all-horizon error plus half sixth-hour error. This is an explicitly combined objective/selection package, retaining trajectory supervision and freezing all diagnostic gates. See [V5 protocol](POLLUTANT_SEQUENCE_V5_PROTOCOL.md) and [completed new reviews](POLLUTANT_SEQUENCE_V5_RESEARCH_REVIEWS.md). The lag probe does not disprove nonlinear context benefit, and V5 is a testable hypothesis rather than a guaranteed correction.

## Data and probability work in parallel

Establish independent CPCB station source availability, timestamped concentrations/units, coverage/quality and licensing before acquisition claims. Reserve station/time blocks before fitting or model selection. More modeled archive years may improve training event coverage but remain modeled evidence. Do not manufacture extreme labels or treat adjacent hours/grids as independent episodes. No official Severe recall claim is possible with zero positives.

If trustworthy risk probabilities become a product requirement, run a separate probability/calibration study only after an episode-separated calibration interval has adequate positive/negative coverage. Seed disagreement and point forecasts are not calibrated probabilities; current Brier/ECE stay null. Actual future weather is unavailable at serving time and cannot be introduced as a deployment predictor through an oracle diagnostic.

## Execution and stopping decisions

One source-pinned job at a time, one T4, 7200-second call ceiling, retries zero, no local weights/PyTorch. Save every manifest/call/app/result and disclose diagnostic reuse. The monitor fetches each result once, reports it, then reviews exactly one defensible next hypothesis. Do not stop solely because the historical two-no-gain counter was reached, and do not force five or seven runs by inventing hypotheses. If development evidence and verified data cannot justify another study, document that specific gap rather than claim a global maximum. Current billing and remaining credit balance are unmeasured. The user's authorization covers longer jobs when the frozen study and learning evidence require them.
