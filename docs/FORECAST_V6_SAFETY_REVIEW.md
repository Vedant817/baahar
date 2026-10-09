# V6 completed safety review and finite stop

Evidence: [v6 raw results](../eval/raw/forecast_risk_v6_results.json),
[v6 gate summary](../eval/raw/forecast_risk_v6_gate_summary.json),
[new loop ledger](../eval/raw/forecast_next_loop_ledger.jsonl),
[loop state](../eval/raw/forecast_next_loop_state.json), and
[frozen protocol](FORECAST_NEXT_ITERATION_PROTOCOL.md).

V6 is an inference-only hosted evaluation reusing the fitted v4 heads. It is
not new training. The challenger retains the incumbent prediction and raises
it to at least poor when the fixed 0.9 quantile forecast crosses the poor
threshold. It creates no new severe prediction.

| Period | Measure | Incumbent | Quantile poor-floor |
|---|---|---:|---:|
| February–April 2026 | Accuracy | 76.38498% | 75.91549% |
| | Macro-F1 | 0.4772 | 0.5045 |
| | Poor+ misses/support | 144/248 | 24/248 |
| | Poor+ recall | 41.93548% | 90.32258% |
| | Poor+ false alarms | 34 | 162 |
| | Poor+ false-alarm rate | 1.80659% | 8.60786% |
| | Poor+ precision | 75.36232% | 58.03109% |
| | Poor+ episode any-hit/full-hit | 34/49; 4/49 | 49/49; 35/49 |
| | Severe+ misses/support | 11/11 | 11/11 |
| May–September 2026 | Accuracy | 83.06056% | 81.99673% |
| | Macro-F1 | 0.5696 | 0.5262 |
| | Poor+ misses/support | 10/23 | 3/23 |
| | Poor+ recall | 56.52174% | 86.95652% |
| | Poor+ false alarms | 17 | 63 |
| | Poor+ false-alarm rate | 0.46665% | 1.72934% |
| | Poor+ precision | 43.33333% | 24.09639% |
| | Poor+ episode any-hit/full-hit | 4/7; 1/7 | 6/7; 5/7 |
| | Severe+ misses/support | 2/2 | 2/2 |

The substantial poor+ hourly and episode gains are real on these consumed
diagnostics. They do not pass the frozen utility gates. Pollution false alarms
exceed both the incumbent-relative 2.80659% limit and absolute 5% ceiling.
Other-season false alarms exceed the incumbent-relative 1.46665% limit, and
accuracy falls 1.06383 percentage points, exceeding the one-point allowed loss.
The pollution accuracy gate itself passes: its loss is 0.46948 points.

All thirteen severe target hours, across five episodes, remain severe onset
misses. Severe false alarms are unchanged at nine pollution hours and one
other-season hour. Zero newly detected severe hours in previously wholly missed
episodes means the severe gain criterion fails. Development still has zero
severe support; its zero misses cannot be represented as successful severe
performance. Hazardous performance is unmeasured.

The raw hybrid's poor+ and severe+ Brier, ECE and reliability bins are all null,
as required: this decision union has no coherent calibrated risk probability.
The underlying classifier probabilities remain uncalibrated and describe that
classifier, not the hybrid. Neither a high quantile nor fewer broad poor+
misses establishes a calibrated air-safety bound.

## Finite disposition

The new ledger contains two completed research rounds, v5 and v6, both without
a meaningful gated gain. State records `completed_iterations=2`,
`consecutive_no_gain=2`, `stopped=true` and
`stop_reason=two_consecutive_no_gain`. This exactly meets the frozen early-stop
rule; seven was the maximum, not a required number of rounds. The 35-column
research incumbent remains the reference. No promotion follows.

This is a finite plateau under the declared gates and retrospective candidates,
not a global maximum or evidence that further modeling cannot improve. Repeated
adaptive comparisons on consumed CAMS/ERA5 archive periods and correlated hourly
positives cannot establish independent, prospective, station-observation,
human, deployment-weather or medical validation.

## Prerequisite for a separately authorized next study

Before another severe-model experiment, acquire and freeze a chronological
development/evaluation design with severe onsets across distinct episodes on
both sides. Record source provenance and missingness; retain the model-archive
label if observations remain modeled. Separate episode support from hourly
counts, require both event/non-event support for any severe threshold or
calibration stage, and refuse fitting/selection when that prerequisite fails.
Keep evaluation episodes unused until final assessment. For deployment claims,
evaluate features and weather forecasts actually available at issuance time and
compare against documented station observations where available.

An architectural upgrade alone does not supply those missing denominators.
Preregister one next hypothesis and its utility gates before assessing fresh
labels, rather than weakening this study's gates or continuing beyond its stop.
