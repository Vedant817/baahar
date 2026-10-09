# V4 preregistered current-referenced pollutant forecasts

User authorization reopens continued hosted research. Three completed reviewers assessed the v3 results and current implementation. Their agreed next test is one representation change relative to v3: forecast future pollutant concentration minus the observed concentration at the origin, then add that observed concentration back. This is an optimization hypothesis, not new information or a claim that persistence is superior.

## Exact change and fixed controls

For every eligible origin, read `current` from its timestamp-t raw air fixture in the fixed six-gas order, float64. The six future-horizon targets become `(future-current)/ystd`, where `ystd` is still the standard deviation of ABSOLUTE training targets used by v3. Do not subtract the absolute target mean or refit delta standard deviations. Decode every predicted horizon as `current+output*ystd`; average reconstructed, unclipped concentrations across seeds, then preserve the existing clipping and rounded canonical band rules.

Keep causal 24-hour inputs, all phase eligibility rules, imputation/input normalization, six horizons, v3 TCN architecture and initialization, seeds 0/1/2, SmoothL1, training-only Poor+ origin weights two, optimizer, batch size, 60 maximum epochs and eight-epoch patience. Do not zero-initialize the head: that would be another change. Select checkpoints by decoded, unclipped absolute development error divided by the same ystd. Assert its numerical equivalence to residual-target MAE. No actual future pollutant or weather enters inputs or reconstruction.

Before fitting, verify encode/decode round-trip and zero-residual persistence behavior, finite shape `(N,6,6)`, fixture-origin current values and unchanged training weighting support 296/19,663. Pin source bytes and the completed v3 raw result SHA. Require exact matching origins, actual pollutant/category/index targets, dataset and partitions. Reproduce unchanged tree and persistence predictions. Primary comparison is **v3_fixed_mean**; v1 remains historical context, never a substitute for this stronger comparison.

Apply the existing paired utility gate against v3 in BOTH consumed diagnostic periods, with the same accuracy/FAR/episode/miss restrictions and gain branches. Report every seed but use the preregistered fixed mean for the next-approach decision. A diagnostic-selected seed or pass against v1 alone is insufficient.

## Evidence and objections

V3 passed the finite v1 gate through Poor+ recall gains, while its ensemble still missed all eleven eligible Very Poor+ pollution hours. Training has only five Very Poor+ hours in one episode, and official Severe support is zero in every phase. Persistence ozone MAE is 47.444 versus v3's 11.735 in pollution diagnostics, and 28.775 versus 8.557 later. A current-value shortcut may help optimization or may bias forecasts toward a poor baseline; the measured v3 comparison resolves that question.

The representation choice responds to consumed development/diagnostic results. Both 2026 windows remain adaptive modeled CAMS/ERA5 archive diagnostics. No pristine, station, prospective, human or medical qualification follows. Later Very Poor+ and all official Severe recall remain UNMEASURED. Point forecasts have no Brier/ECE calibration. Independent station data is still necessary for external qualification; it is not a prerequisite for labeling this bounded ablation as exploratory research.

A [primary forecasting study](https://arxiv.org/abs/2205.13504) illustrates why forecasting architecture should be compared empirically with simple alternatives. V4 is a residual TCN ablation, not an implementation of that paper's NLinear model or proof of its results on Bengaluru.

One T4 call, 7200-second timeout, retries zero; checkpoints and source archives stay on Modal. Fetch small result artifacts only. Preserve every prior source/result/ledger and product serving state. No automatic promotion/deployment or billing/credit claim.
