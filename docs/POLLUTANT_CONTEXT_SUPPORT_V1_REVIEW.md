# Pollutant context support audit: result and review

The read-only Modal audit completed once under call `fc-01M4FK0MTAX6ZMYG4MJ5S3WEZ4` (app `ap-WvQPIWiaSDVO8kdHtQE8Rf`). The raw manifest and result are `eval/raw/pollutant_context_support_v1_manifest.json` and `eval/raw/pollutant_context_support_v1_results.json`. The result SHA and all six pinned local source/code/reference SHA-256 values were verified after fetch. The remote audit rechecked all 32,826 canonical t+6 target index/band pairs. It found zero absent source timestamps and zero incomplete finite six-gas sequences. The context windows were confined to each phase.

| Phase | Eligible rows, 24/48/72h | Poor+ hours / episodes, 24/48/72h | Very Poor+ hours / episodes, 24/48/72h | Official Severe |
|---|---:|---:|---:|---:|
| Train | 19,663 / 19,639 / 19,615 | 296 / 86 in all three | 5 / 1 in all three | 0 |
| Development | 1,435 / 1,411 / 1,387 | 168 / 28 in all three | 22 / 5 in all three | 0 |
| Pollution diagnostic | 2,107 / 2,083 / 2,059 | 248 / 49 in all three | 11 / 4 in all three | 0 |
| Other-seasons diagnostic | 3,643 / 3,619 / 3,595 | 16 / 6, then 13 / 5, then 13 / 5 | 0 in all three | 0 |

There are 24 fewer eligible origins per phase at 48h and 48 fewer at 72h; losses are phase-boundary exclusions. Longer-context origin sets are subsets of the 24h sets. Per-phase, per-context eligible-origin timestamp SHA-256 values are in the raw result, along with exact support and episode details. The timestamp digests plus source row/fixture digests make the intended comparison reproducible; the audit did not emit sequence-tensor hashes.

Three read-only reviewers assessed the result, runner, v4 paired report/reviews, and saved-output error analysis. All found the support audit credible for eligibility and agreed that 48h is feasible while 72h adds no rare-event support. Two considered a single matched 48h exploratory test reasonable. The evaluation reviewer objected that feasibility does not establish that older history contains incremental predictive signal. The v4 development transition analysis shows mixed row-level changes, but does not isolate the value of lags 24–48.

Decision: do not start a 48h model fit yet. First establish, on development only and without using diagnostic labels for selection, whether the older 24–48h portion adds a defensible signal beyond the recent 24h. If that check supports a temporal-context hypothesis, preregister exactly one 48h study with a 24h comparator retrained on the identical hashed 48h-eligible origins. Freeze architecture, seeds, target, loss, training weights, train-only preprocessing, optimizer, checkpoint rule and V3 gates; change only context length. Report all seeds, ensemble, episode errors and pollutant regression error. Preserve a separate full-period summary, and do not claim independent qualification.

The train split contains only five Very Poor+ hours in one episode and no official Severe examples. Severe recall is UNMEASURED. Development and both 2026 diagnostic windows are already consumed; the diagnostics are correlated CAMS/ERA5 modeled archive outputs, not independent station observations, prospective tests, pristine holdouts or medical qualification. The small other-seasons support is especially weak.
