# A deeper forecast study after the finite v5–v6 series

The user separately authorized reopening research. Preserve the stopped old
series and its two no-gain decisions. A new source-hashed study needs a separate
manifest and selection record. No implementation or launch is performed by
this research review.

## What the actual failures imply

The v4 numeric NAQI q90 heads achieved only about 74–80% empirical coverage,
not nominal 90%. V6 used its output as a poor-band floor: poor recall improved
to 90.32%/86.96%, but pollution-period false-alarm rate reached 8.61%, and the
other-season accuracy loss exceeded one percentage point. All thirteen severe
hours remained missed. V5 gas history also failed, including a loss of one
pollution episode any-hit and lower other-season poor recall. Increasing
features or changing a threshold has not established useful improvement.

The severe training support is only 27 correlated hours in six episodes.
The canonical modeled-archive severe evaluation targets are concentrated near
NAQI 301.2–301.9 and O3 drives all thirteen. This justifies an audit of raw O3
precision, source interpolation, canonical breakpoint mapping and label
sensitivity. It does not justify fitting a special 301 threshold, treating
model output as observed station exposure, or concluding that current O3 can
predict a peak six hours later.

## Primary research and applicability

The original [TCN study](https://arxiv.org/abs/1803.01271) evaluates residual,
causal, dilated convolutions against recurrent sequence models. It provides a
reasonable architectural starting point for short temporal histories; it does
not prove ozone forecasting performance. The
[authors' implementation](https://github.com/locuslab/TCN) is an architectural
reference rather than a dependency to copy wholesale into the runtime.

[PatchTST](https://arxiv.org/abs/2211.14730) uses channel-independent patch
representations and demonstrates long-term forecasting and representation
learning benefits. Its results do not establish superiority for a 24-hour
context, six-hour horizon, six rare training episodes or this archive.
A small TCN offers a simpler first test of full temporal history; an attention
model can follow only if that test and matched baselines identify remaining
sequence-model benefit.

[Revisiting Deep Learning Models for Tabular Data](https://arxiv.org/abs/2106.11959)
finds no universally superior choice between strong neural models and boosted
trees. A neural study must therefore retain an equally specified tree baseline,
not compare a full-history network only against the old 35-feature model.

[CORAL](https://arxiv.org/abs/1901.07884) expresses ordered labels as rank tasks
with consistent logits; [CORN](https://arxiv.org/abs/2111.08851) uses conditional
rank tasks. Either can avoid contradictory ordinal probabilities, but neither
creates severe-event information absent from the training episodes. CORN's
conditional high-rank training pools can become particularly small here.
An ordinal-only severe detector is not the first recommendation.

[Guo et al.](https://proceedings.mlr.press/v70/guo17a.html) show neural
confidence can be poorly calibrated and study temperature scaling. Their
classification evidence does not confer calibrated risk on a quantile forecast
or establish that one severe calibration episode is sufficient.

## First deep candidate: pollutant-trajectory TCN

Test one small multi-output temporal convolutional model, with a fixed 24-hour
causal input window t-23 through t. Predict all six source pollutant
concentrations at each horizon t+1 through t+6. Apply the existing canonical
`compute_naqi` to the six predicted t+6 concentrations and map the result using
the existing shared band function. This preserves a physical target and uses
common-hour pollutant trajectories to train the shared representation.

Forecasting only O3 and combining it with actual future PM/NO2/SO2/CO would
leak target-time information. O3-only predictions may be a named pollutant
diagnostic, but cannot be advertised as the full six-hour NAQI forecast.
Reusing current other pollutants instead is a different persistence hybrid,
which must be explicitly labeled if ever studied.

Proposed fixed settings, to be frozen in the new manifest:

- Source channels: the six existing raw pollutant variables, current recorded
  temperature, apparent temperature, rainfall, humidity, wind and UV, plus
  hour/month sine and cosine encodings. Use only observed-at-or-before-t
  archive values. Do not include target weather, future archive values or a
  target-time dominant-pollutant ID. Pin units and source keys from recorded
  fixtures; source CO handling must match canonical conversion.
- Require 24 consecutive hourly timestamps for both neural and tree arms.
  Impute missing inputs using training-only medians and add missingness masks;
  scale each input and each pollutant target using training-only statistics.
  Do not treat missing source measurements as zero pollution.
- Three residual TCN blocks, two left-padded causal convolutions per block,
  width 32, kernel 3 and dilations 1/2/4; dropout 0.1, ReLU, last-time-step
  readout and a linear 36-output head. Its receptive field covers the 24-hour
  window. Clip negative inverse-transformed concentration predictions to zero
  and report the clipping count.
- Mean squared error averaged equally over the six standardized pollutant
  channels and six horizons. This is a continuous-target experiment, not a
  promise of severe sensitivity. Do not initially add target-event resampling,
  focal loss, synthetic severe examples or multiple tuned loss coefficients.
- AdamW, learning rate 0.001, weight decay 0.0001, batch size 256, maximum 100
  epochs, development-loss patience 10. Three fixed seeds 0/1/2, report each
  seed and their fixed mean concentration forecast. Pick checkpoints by
  development pollutant loss, not consumed 2026 severe recall.
- Paired baselines: pollutant persistence, unchanged incumbent on identical
  eligible rows, and six CPU LightGBM regressors for t+6 pollutants using the
  same flattened 24-hour input/mask matrix. Fix tree settings before results;
  the [official LightGBM parameter reference](https://github.com/lightgbm-org/LightGBM/blob/main/docs/Parameters.rst)
  documents continuous regression objectives. The tree arm is needed to
  distinguish temporal information from neural architecture benefit.

These are proposed choices, not externally validated hyperparameters. A small
single hosted GPU is justified for reproducible batched TCN training over three
seeds; CPU is sufficient for the tree arm. An L40S is not required by this
model size. Set a finite per-call timeout and stop at the frozen epoch bound,
not after spending available credits. Install PyTorch only in the Modal image;
keep weights, expanded rows and optimizer checkpoints on the remote volume.
Return only small source/support/metric/prediction artifacts locally. No billed
cost estimate or training time is claimed before a run.

## Episode-separated development and truthful uncertainty

Before fitting, inspect only pre-evaluation data for distinct severe episodes.
Freeze chronological train/development/calibration intervals and the target
contract before examining the new final assessment. Episodes spanning a phase
boundary must be wholly assigned or excluded. For a 24-hour context and six
future targets, exclude windows whose input/target support overlaps a neighboring
phase; a bare six-hour gap does not eliminate shared histories. Record the
exact minimum/maximum support timestamps, not just feature-row timestamps.

Development must contain actual severe target episodes. If the existing pool
forces one or two episodes per development phase, disclose that support and
do not treat hourly counts as independent trials. Expand source coverage or
use a preregistered blocked episode study; never shuffle neighboring windows
to manufacture severe support in every split. Splits adapted using development
labels remain adaptive research. Keep all old 2026 periods named as consumed
diagnostics; they cannot become pristine by changing their manifest name.

The first regression TCN supplies no severe probability. Report raw severe
PR curves and average precision using continuous predicted NAQI as a ranking
score, plus fixed-canonical-band severe recall, precision and false alarms.
These scores are not probability calibration, so severe Brier/ECE must remain
null. Report numeric pollutant and NAQI errors, distance to the severe boundary,
episode any/full/onset hit counts, poor metrics and paired seed variability.
Do not retune the severe threshold from those PR curves.

If calibrated severe probabilities are required later, define a separate
probabilistic/ordinal head or a development-fitted score calibrator, and reserve
an episode-separated calibration interval with actual positive and negative
support. Evaluate Brier, log loss and reliability bins there and on a reserved
assessment. With only six source episodes, effective calibration sample size
may be inadequate; mark calibration unsupported rather than claim it from
temperature scaling or a q90 label. A model can have useful ranking while
still supplying unreliable probabilities.

Retain the explicit missed-event/false-alarm/accuracy/episode utility gates in
the new study, preregistered before results. Even a passing retrospective
candidate requires a separate deployment-input and prospective assessment
before serving changes. The first question is whether full pollutant history
improves a physically defined forecast under these constraints, not whether
a larger model can fit the thirteen already inspected severe diagnostic hours.
