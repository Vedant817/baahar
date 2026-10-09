# Reopened forecast research agenda

The user authorized continued research, implementation and hosted training,
including runs lasting hours. The earlier v5/v6 series remains a completed,
stopped experiment. This new study does not reset its ledger or reinterpret
its failed comparisons as successes.

## What needs to improve

The objective is fewer missed polluted outdoor hours without replacing those
misses with excessive false alarms or degrading common-band predictions.
Report accuracy, macro-F1, pollutant error, threshold-specific recall/precision,
false alarms and episode coverage together. A high headline accuracy alone
does not answer that objective.

Primary-source review corrected the category terminology: 301–400 is officially
Very Poor, and 401–500 is Severe. Historical `severe` and `hazardous` identifiers
are preserved in existing artifacts. The previous thirteen missed high-index
hours were Very Poor proxy hours, not official Severe observations. See the
[government breakpoint table](https://ies.gov.in/arthapedia/concept/national-air-quality-index).
All new metrics use the shared rounded band mapping, not a conflicting raw
floating-point threshold. The calculation remains a modeled-hourly concentration
proxy rather than official station AQI.

## First deeper experiment: pollutant trajectories

Use the preceding 24 hours of six pollutant concentrations and five weather
variables, with cyclic calendar inputs and missingness indicators. Predict
all six pollutants at each of the next six hours. Calculate the final-hour
index from the six predicted concentrations. Actual future pollutants and
weather never enter the prediction.

Compare a small causal temporal convolutional network, trained under three
fixed seeds, against six LightGBM regressors using the same flattened history
and against pollutant persistence. This isolates architecture benefit from
the benefit of longer history. A TCN is a reasonable starting sequence model
based on the [original architectural study](https://arxiv.org/abs/1803.01271);
that study does not establish performance on Bengaluru ozone.

Select checkpoints using development continuous pollutant error, with
normalization fitted only on training data. The preregistered maximum is
60 epochs per seed with eight-epoch patience, one hosted T4 and a two-hour
per-call ceiling. PyTorch, checkpoints and source archives stay on Modal.
The precise architecture, inputs and implementation hashes are frozen in
the [study protocol](DEEP_POLLUTANT_STUDY_PROTOCOL.md) and submitted manifest.

The fixed support audit found one Very Poor training episode (five hours),
five development episodes (22 hours), four pollution diagnostic episodes
(11 hours), and none in the later diagnostic period. Official Severe has
zero support throughout. Full phase-local context excludes the two previously
evaluated May-boundary cases. These limitations remain explicit; zero support
cannot become a successful recall result. Both diagnostic windows are consumed
research data, so no fresh-holdout or prospective claim follows.

## Evidence-driven follow-ups

After the completed run, research agents review actual predictions, learning
curves and event errors before one next experiment is implemented:

- If continuous pollutant error improves but rare-event misses persist, test
  one preregistered residual or event-aware learning change. Keep point-error
  and false-alarm tradeoffs visible. Do not manufacture rare examples or tune
  a threshold using the diagnostic labels.
- If the temporal model underfits and development learning curves support
  additional temporal capacity, compare a longer-context or small attention
  model on matching eligible rows. A larger transformer is a hypothesis,
  not an assumed accuracy improvement.
- If a forecasting score ranks events usefully, a separate probability study
  may add calibration with positive and negative support in an episode-separated
  calibration phase. Point estimates, seed disagreement and quantile coverage
  are not calibrated event probabilities.
- If event coverage remains the limiting factor, audit additional source
  coverage and reserve new evaluation episodes before acquiring their labels.
  Station access, historical coverage and licensing must be established rather
  than assumed. Additional modeled grids or years remain modeled evidence,
  and adjacent correlated hours/grids do not become independent events.

Each changed approach gets a separate source-pinned manifest, one submission,
immutable raw results and a review. Repeating an unchanged fit is not another
research hypothesis. Longer training is used when the learning evidence calls
for it; elapsed hours alone are not progress. Actual billed costs and current
credit balance remain unmeasured.

The research loop can continue under the user's reopened authorization.
Its monitor must recover pending calls without duplicating submissions or
overwriting completed artifacts. There is no automatic model promotion:
deployment inputs, independently reserved evaluation and product safety
boundaries require separate qualification. Preserve the deterministic safety
behavior while the forecast research is in progress.
