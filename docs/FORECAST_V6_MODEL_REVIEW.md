# Model review after v6 and finite stopping decision

V6 completed its hosted inference-only evaluation. It does not pass the frozen
utility gates, despite a substantial poor+ recall improvement. The series has
two completed research rounds and two consecutive no-gain decisions; the
frozen stopping rule is reached. No further submission follows from this
review. This is a finite research plateau, not proof of the best attainable
forecast architecture.

## Verified implementation and provenance

The result records `inference_only: true` and `no_refitting: true`. Both heads
were loaded from `/artifacts/forecast_risk_v4/target_feature_candidates.joblib`.
The observed bundle SHA256 is
`62b3ad8d2820112e30e766abe822f31fc5b28de6efba1b4589bc985a3a09b875`.
That hash was observed at read time; no prior recorded bundle hash existed.
The runner verifies the stored source/configuration contract, feature order,
model parameters and quantile alpha. Incumbent categorical predictions and
q90 numeric prediction hashes match v4 in development and both diagnostics.
The archived source and target timestamp checks remain part of the raw result.

The challenger preserves the 35-column classifier and raises its band to poor
when the unchanged q90 numerical head maps to poor or worse through the shared
rounded band function. It does not lower a classifier prediction or create a
severe floor. Its risk probability, Brier and ECE remain null: a quantile head
is not a calibrated binary risk probability.

## Measured architecture tradeoff

In February–April, poor+ recall rises from 41.94% to 90.32%, with misses falling
from 144/248 to 24/248. Accuracy changes from 76.38% to 75.92%, while macro-F1
rises from 0.4772 to 0.5045. Poor+ episode any-hits rise from 34/49 to 49/49.
However, false alarms increase from 34 to 162 and the false-alarm rate rises
from 1.81% to 8.61%. That exceeds both the absolute 5% cap and the permitted
one-percentage-point increase. Episode any-hit coverage does not imply that
all positive hours within each episode are detected.

In May–September, recall rises from 56.52% to 86.96%, with misses falling from
10/23 to 3/23 and episode any-hits increasing from 4/7 to 6/7. Accuracy falls
from 83.06% to 82.00%; the exact loss exceeds the frozen one-percentage-point
limit. False alarms increase from 17 to 63, raising their rate from 0.47% to
1.73%, also exceeding the allowed increase. Macro-F1 falls from 0.5696 to
0.5262. The small support of 23 positive hours does not establish a stable
season-wide recall estimate.

All thirteen severe hours remain missed. Since this architecture adds only a
poor-band floor and preserves the classifier's severe decisions, it cannot
repair the incumbent's severe detection failure. The gain criterion for poor
recall passes, but the utility gates fail; neither improved recall nor improved
pollution-period macro-F1 overrides those frozen gates.

## Concrete prerequisite before another model search

The next prerequisite is a new evaluation and data plan, rather than a larger
transformer trained on the same six severe training episodes. Establish whether
the target is operationally meaningful: the current instantaneous NAQI labels
are derived from a modeled CAMS archive, with severe events determined by
ozone subindices; this is not proof that a six-hour model can predict those
events or that the archive label is a station-based safety assessment.

A separately authorized future study should obtain sufficiently many distinct
pollution episodes, include severe support in a development period, freeze a
prospective or separately reserved temporal assessment before tuning, and
evaluate the actual deployment inputs available at issuance time. If station
data are used, establish their units, coverage and target aggregation contract
before combining them with CAMS features. Define acceptable missed-event and
false-alarm costs with explicit support denominators. Only then compare a
larger sequence model against the existing tabular and persistence baselines.
Additional correlated hourly rows alone do not satisfy that prerequisite.

Raw evidence: `eval/raw/forecast_risk_v6_results.json`,
`eval/raw/forecast_risk_v6_gate_summary.json`, and
`eval/raw/forecast_next_loop_state.json`. Preserve both completed rounds and
their frozen protocol. No serving artifact or historical ledger is changed.
