# V5 safety and finite diagnostic review

This review reads the saved v5 raw predictions, frozen gate summary, v4
comparison and hosted runner. It makes no parameter changes or submissions.
Evidence: [v5 raw results](../eval/raw/forecast_risk_v5_results.json),
[v5 gate summary](../eval/raw/forecast_risk_v5_gate_summary.json),
[v4 raw results](../eval/raw/forecast_risk_v4_results.json), and
[frozen protocol](FORECAST_NEXT_ITERATION_PROTOCOL.md).

## Measured paired result

The incumbent's prediction replay matches v4 on both diagnostic periods. The
challenger adds current and causal 1/3/6-hour history/differences for all four
predeclared gases; no gas subset is chosen from severe evaluation labels. Source
fixtures and derived targets are pinned and checked, timestamp lookups avoid
adjacency shifts, and imputation is fitted only on the training partition.

| Period | Measure | Incumbent | Gas-history challenger |
|---|---|---:|---:|
| February–April 2026 | Accuracy | 76.38498% | 75.96244% |
| | Macro-F1 | 0.4772 | 0.4691 |
| | Poor+ misses/support | 144/248 | 136/248 |
| | Poor+ recall | 41.93548% | 45.16129% |
| | Poor+ false alarms | 34 | 46 |
| | Poor+ false-alarm rate | 1.80659% | 2.44421% |
| | Poor+ precision | 75.36232% | 70.88608% |
| | Poor+ episode any-hit/full-hit | 34/49; 4/49 | 33/49; 5/49 |
| | Severe+ misses/support | 11/11 | 11/11 |
| | Severe+ false alarms | 9 | 4 |
| May–September 2026 | Accuracy | 83.06056% | 83.11511% |
| | Macro-F1 | 0.5696 | 0.5435 |
| | Poor+ misses/support | 10/23 | 12/23 |
| | Poor+ recall | 56.52174% | 47.82609% |
| | Poor+ false alarms | 17 | 21 |
| | Poor+ false-alarm rate | 0.46665% | 0.57645% |
| | Poor+ precision | 43.33333% | 34.37500% |
| | Poor+ episode any-hit/full-hit | 4/7; 1/7 | 5/7; 2/7 |
| | Severe+ misses/support | 2/2 | 2/2 |
| | Severe+ false alarms | 1 | 0 |

The frozen no-gain classification is correct. Pollution-period hourly recall
improves only 3.22581 percentage points, below the five-point gain requirement,
and episode any-hit falls from 34 to 33, failing a utility gate. Other-season
recall falls 8.69565 points. More fully hit episodes do not erase the explicit
any-hit regression or the poorer other-season hourly recall.

All thirteen severe targets remain onset misses from current instantaneous air
below poor. Challenger outputs are twelve poor and one moderate, versus ten poor
and three moderate for the incumbent. This improves some broad poor+ warning
coverage, but is zero severe+ recall and captures none of the five severe
episodes as severe. Fewer severe false alarms are useful but do not satisfy the
new-severe-hit criterion. Development contains zero severe targets and cannot
establish severe threshold/calibration performance. Training's 27 severe hours
represent only six descriptive episodes; there is no hazardous support.

Class probabilities are uncalibrated. Pollution poor+ Brier improves from
0.0644832 to 0.0635220 while ECE worsens from 0.0517556 to 0.0527007. Other-season
poor+ Brier worsens from 0.00538356 to 0.00646851 and ECE from 0.00348083 to
0.00559659. These mixed probability metrics do not override the frozen decision
and episode gates, and low severe probability error with rare support is not
severe-event detection success.

## Predeclared v6 objection and bounded verification

The fixed 0.9-quantile poor-band floor is already named in the frozen protocol.
It is an evaluation of an alternative decision architecture, so the same paired
gates apply whether its existing hosted fitted heads are reused or refitted. A
hosted replay must verify the saved heads/source contract, identical rows and
incumbent predictions; if it reuses the v4 bundle, document evaluation only and
do not claim new training. It must preserve the existing raw outputs and must
not change the protocol to make this candidate pass.

There is a strong pre-existing objection: the v4 instantaneous-history 0.9 head
already has poor+ false-alarm rates 8.60786% in pollution and 1.70189% in other
seasons. A floor taking the union of these alarms and incumbent alarms cannot
reduce those rates on the same predictions. Pollution therefore necessarily
exceeds both its incumbent-relative 2.80659% gate and the absolute 5% gate;
other seasons exceed their incumbent-relative 1.46665% gate. Furthermore,
`max(incumbent_band, 3)` never creates a new severe prediction. Its severe
misses cannot improve by construction. This is not a promising gate-passing
candidate, and repeated refitting solely to remeasure that bound is unnecessary.

One authorized hosted replay can still verify the exact union, full episode
coverage, accuracy and null hybrid probability metrics. Brier/ECE/reliability
must remain null for this hybrid because it has no coherent risk probability.
If the replay confirms no gain, it is the second consecutive no-gain round and
the finite loop stops. Do not replace it with an unapproved tuned threshold or
additional round to avoid stopping. Seven rounds are a maximum, not a quota.

## Disposition

Keep the 35-column research incumbent. V5 does not justify promotion. The
evidence is repeated adaptive comparison on consumed CAMS/ERA5 modeled archive
hours, with correlated positive support; it is not independent/prospective
station, human, deployment-weather or medical validation. A two-round finite
plateau would describe this bounded protocol's outcome, not maximum attainable
performance. Severe onset forecasting remains unresolved.
