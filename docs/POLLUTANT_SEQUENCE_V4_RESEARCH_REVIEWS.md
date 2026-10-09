# Three completed reviews for the reopened v4 study

These reviews completed in this session after earlier provider outages. They assess actual v3 results, the current runner and the proposed residual representation. They are research reviews, not external human/station validation.

## Objective review: `/root/v4_objective_review`

The reviewer supports one bounded optimization-bias ablation, with target `(future-current)/absolute_train_ystd`, no absolute mean subtraction, and decoded forecast `current+output*ystd`. Keep architecture and initialization, weights, seeds and the development rule fixed. Zero-initializing the head would be an extra change. Development residual MAE is algebraically equivalent to decoded absolute MAE divided by the same scale; assert that equivalence. Decode before averaging and clip afterward. Pin v3 as primary paired reference.

The reviewer objects that persistence is a weak measured baseline: ozone MAE 47.444 versus v3 11.735 in pollution and 28.775 versus 8.557 later. The shortcut may help optimization but does not establish forecasting superiority. Five Very Poor training hours in one episode cannot supply new rare-event information. A passing adaptive result still requires independent measured evaluation for stronger claims.

## Integrity review: `/root/v4_integrity_review`

Construct origin concentrations from raw `air[t]` in fixed six-gas order, preferably float64. Never use standardized inputs or future targets for reconstruction. Keep absolute-target standard deviations; no residual-scale refitting or target clipping. Check zero-residual persistence across all horizons, finite `(N,6,6)` reconstruction, round-trip within float32 tolerance and origin-fixture alignment. Training weighting support remains 296/19,663.

The v3 raw hash matches its manifest. Pin it as `v3_fixed_mean` and verify exact origins/actual targets, dataset/partitions and secondary baseline reproduction. Replace all hardcoded v1 references in the new runner/reporter; passing against v1 alone is insufficient. Later Very Poor and every official Severe recall remain unmeasured.

## Direction review: `/root/v4_direction_review`

The reviewer supports the residual experiment as one isolated test under reopened authorization. A learned current-value correction could improve peak transitions or could lag rapid peaks; the paired result must resolve this. Preserve the absolute error scales to avoid changing pollutant loss weights. Select checkpoints on decoded absolute normalized MAE.

Stage further work conditionally: investigate 48/72-hour context only when development errors suggest missing temporal information, auditing changed support first and comparing identical origin intersections. Investigate a small attention model only when a matched capacity question exists. Acquire independent station measurements with verified timestamps, units, quality, coverage, access and licensing in parallel, reserving evaluation before fitting. Additional modeled years remain modeled evidence. Longer training alone has little support from v3's best epochs 20/19/20. If v4 fails, avoid diagnostic multiplier sweeps and use development errors/source coverage to choose the next hypothesis.

## Root synthesis

Proceed with exactly the residual representation change, retain v3 as frozen incumbent and preserve all historical evidence. The prior statement that no further run was justified is revised: diagnostic reuse constrains generalization claims but does not prohibit a clearly labeled, new adaptive research hypothesis. It remains inappropriate to call repeated diagnostics a pristine holdout or a passing candidate deployment ready.
