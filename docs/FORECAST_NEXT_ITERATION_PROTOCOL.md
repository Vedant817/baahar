# Finite forecast research rounds

This protocol is frozen before v5. The user authorized at most seven further
review, implementation and hosted evaluation rounds. Stop early after two
consecutive completed rounds without a meaningful gated gain. A terminal failed
run counts as a no-gain round; preserve its failure rather than fabricate scores.

The initial incumbent is v4 `instant_history_classifier` (35 columns). Its
pollution-period poor+ misses are 144/248, episode any-hits 34/49 and full-hits
4/49; other-season misses are 10/23, episode any-hits 4/7 and full-hits 1/7.
All 13 severe target hours, across five episodes, are missed. This starting
choice is explicit despite mixed v4 results: instantaneous history matches the
target basis and is the fixed starting architecture for the new feature round;
it is not a claim that v4 established its superiority. The historical 28-column
baseline remains a reported diagnostic.

## Paired comparison and selection

Every round names exactly one challenger and one incumbent before submission.
Refit/reproduce both on the same recorded source bytes, training window, target
definition and eligible evaluation rows. Pin source hashes and feature orders;
fit preprocessing only on training data. Additional history requirements apply
to both sides. Abort reporting if timestamps, labels or prediction lengths do
not align. Never alter historical raw outputs or previous ledgers.

Both 2026 diagnostic periods must pass all utility gates:

- Accuracy loss at most 0.01 absolute.
- Poor+ false-alarm rate at most incumbent +0.01 and at most 0.05.
- Severe+ false-alarm rate at most incumbent +0.0025 and at most 0.01.
- No additional severe+ hourly misses.
- No decrease in poor+ or severe+ episode any-hit counts.

A meaningful gain additionally requires either:

1. Poor+ hourly recall improves by at least 0.05 in one diagnostic period, with
   no decrease in the other; or
2. At least two newly detected severe+ target hours lie in one or more target
   episodes wholly missed by the incumbent, with at least one newly captured
   episode and no decrease in poor+ recall in either period.

The severe gate uses the actual paired predictions: merely redistributing hits
inside an episode the incumbent already detected does not qualify. Target
episodes group positive target hours separated by at most six hours. Their
any-hit and full-hit counts are descriptive; an any-hit is not protection for
all hours in that episode. Report full-hit changes, per-case onset misses,
precision, false alarms, support, accuracy, macro-F1 and probability reliability
even when the gate passes. A missing support denominator is unmeasured, not zero
error or a positive result. Utility gates are research choices, not a medical
safety standard.

A passing challenger becomes the next research incumbent. A failing challenger
does not replace it. v5 adds gas history to the 35-column incumbent. If v5 fails,
v6 may compare one fixed 0.9-quantile poor-band floor against that same incumbent;
its exact configuration must be pinned before submission, and probability
calibration must not be claimed for a quantile prediction.

The gas set is declared in full: O3, NO2, SO2 and CO. Dominant-pollutant
retrospective counts explain diagnostic failures; they do not select a gas
subset using the thirteen severe evaluation labels. Brier/ECE are reported for
classifiers only. A quantile-floor hybrid supplies no coherent risk probability,
so its Brier/ECE remain null rather than inheriting the classifier's scores.

## Limits and durable bookkeeping

Configurations and research decisions have already used these modeled archive
periods. Selecting an incumbent through this protocol makes the diagnostics
further consumed. This is adaptive retrospective research, not pristine,
prospective, independent, human-reviewed, station-observation or medical
validation. CAMS/ERA5 modeled archive output is not deployment forecast weather.
Development has zero severe support in v4; it cannot select or calibrate a
severe-specific threshold. Hourly positive support is correlated; episode counts
do not establish independence. No automatic serving change or promotion follows.

New state uses `eval/raw/forecast_next_loop_state.json` and a new append-only
`eval/raw/forecast_next_loop_ledger.jsonl`. Record a completed run once by its
run identity and raw-result hash. Do not update the historical training-loop
counter, continuous tuning ledger or serving artifacts. After two no-gain rounds
or seven total recorded rounds, record a finite plateau and stop further
submissions. No claim of maximum attainable performance follows from stopping.
