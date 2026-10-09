# V5 data and paired-output review

Read-only review of `forecast_risk_v5_results.json`, its gate summary,
`scripts/forecast_next_modal.py`, the frozen next-iteration protocol, and the
recorded pollutant-driver audit. No fitting, submission or parameter change
was performed by this review.

## Integrity and coverage

V5's derived row SHA-256 and all source fixture records exactly match v4.
The 35-column incumbent reproduces v4 instantaneous-history classifier
predictions in development and both diagnostic periods. Exact source/target
checks cover 32,826 rows. Training support and diagnostic denominators are
unchanged.

All 28 added gas columns are finite in every partition: current O3/NO2/SO2/CO,
their lag1/3/6 and their difference1/3/6 values. Missing added gas coverage does
not explain the candidate's failure. The shared `precip_prob` and `uv_index`
columns are entirely missing in both candidates and all partitions; these
existing uninformative columns do not uniquely disadvantage the gas candidate.
Gas histories use exact timestamps at or before the feature time, and imputation
is fitted on training data only.

## Measured paired tradeoffs

| Metric | February–April: incumbent → gas | May–September: incumbent → gas |
|---|---:|---:|
| Accuracy | 0.7638498 → 0.7596244 | 0.8306056 → 0.8311511 |
| Macro-F1 | 0.4772 → 0.4691 | 0.5696 → 0.5435 |
| Poor+ misses | 144/248 → 136/248 | 10/23 → 12/23 |
| Poor+ recall | 0.419355 → 0.451613 | 0.565217 → 0.478261 |
| Poor+ false alarms | 34 → 46 | 17 → 21 |
| Poor+ precision | 0.753623 → 0.708861 | 0.433333 → 0.343750 |
| Poor episode any-hit | 34/49 → 33/49 | 4/7 → 5/7 |
| Poor episode full-hit | 4/49 → 5/49 | 1/7 → 2/7 |
| Poor probability Brier | 0.0644832 → 0.0635220 | 0.00538356 → 0.00646851 |
| Poor probability ECE | 0.0517556 → 0.0527007 | 0.00348083 → 0.00559659 |
| Severe misses | 11/11 → 11/11 | 2/2 → 2/2 |
| Severe false alarms | 9 → 4 | 1 → 0 |

Development accuracy improves 0.8409 to 0.8470 with poor false alarms falling
from nine to three, but poor misses remain 14/16. Development has no severe
examples and cannot establish a severe benefit.

Across the 13 severe evaluation hours, poor-band-or-worse warnings increase
from ten to twelve, while severe detection remains zero. These are distinct
outcomes. The candidate raises two March/April onset cases and the later May
case from moderate to poor, but lowers `2026-04-10T06:00` from poor to moderate.
It does not uniformly improve each severe case.

The gate summary correctly rejects replacement: pollution episode any-hit
falls, the pollution recall gain is below the required 0.05, and later poor
recall falls by 0.0869565. Fewer severe false alarms alone is not improved
severe detection. Retain the incumbent.

## Predeclared V6 floor: rationale and objection

A fixed 0.9-quantile poor floor can increase poor warnings while preserving
incumbent severe predictions. It structurally cannot newly detect severe
hours because its maximum newly imposed floor is band three.

The saved v4 predictions already permit a deterministic retrospective check
of exactly that floor, without fitting or changing parameters. This is not a
new completed V6 result:

- Pollution accuracy becomes 0.7591549; poor misses become 24/248, any-hit
  becomes 49/49, and full-hit becomes 35/49. False alarms become 162/1882
  (0.0860786), exceeding both the absolute 0.05 cap and incumbent-plus-0.01 cap.
- Later accuracy becomes 0.8199673 versus incumbent 0.8306056: loss 0.0106383,
  exceeding the 0.01 cap. Poor misses become 3/23, false alarms become 63,
  any-hit becomes 6/7, and full-hit becomes 5/7.

The fixed V6 experiment is explainable as a poor-recall tradeoff test, but the
existing paired replay provides a strong objection to expecting a gated gain.
Do not adjust its quantile or gates using these outcomes. Report actual V6
results separately if the frozen hosted cycle is executed; maintain the
authorized two-consecutive-no-gain stopping rule. Hybrid probability
Brier/ECE must remain null because this floor is not a coherent risk
probability model.

All comparisons use consumed CAMS/ERA5 modeled archives and correlated hourly
support. They do not establish prospective station, human, field or medical
performance. No model promotion follows this review.
