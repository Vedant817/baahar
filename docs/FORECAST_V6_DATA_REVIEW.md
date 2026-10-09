# V6 final data review and stopped research sequence

V6 completed hosted inference using the already fitted v4 35-column classifier
and 0.9-quantile regressor. It applied the predeclared poor-band floor without
refitting. This review reads the saved results, gate summary and loop state;
it performs no additional submission, training or protocol change.

## Integrity and measured tradeoff

The row SHA-256 and all ten recorded source fixture records match v4. The
incumbent prediction vectors reproduce v4 exactly in development and both
diagnostic periods. The reused remote bundle's observed hash is
`62b3ad8d2820112e30e766abe822f31fc5b28de6efba1b4589bc985a3a09b875`;
the result records verified model contracts and no refitting. This hash was
observed at read time, rather than independently pinned before the original
v4 fitting. The exact source/target checks cover 32,826 rows. Both candidates
use the same 35 columns and eligible rows.

| Metric | February–April: incumbent → floor | May–September: incumbent → floor |
|---|---:|---:|
| Accuracy | 0.7638498 → 0.7591549 | 0.8306056 → 0.8199673 |
| Macro-F1 | 0.4772 → 0.5045 | 0.5696 → 0.5262 |
| Poor+ misses | 144/248 → 24/248 | 10/23 → 3/23 |
| Poor+ recall | 0.419355 → 0.903226 | 0.565217 → 0.869565 |
| Poor+ false alarms | 34 → 162 | 17 → 63 |
| Poor+ false-alarm rate | 0.0180659 → 0.0860786 | 0.00466648 → 0.0172934 |
| Poor+ precision | 0.753623 → 0.580311 | 0.433333 → 0.240964 |
| Poor episode any-hit | 34/49 → 49/49 | 4/7 → 6/7 |
| Poor episode full-hit | 4/49 → 35/49 | 1/7 → 5/7 |
| Severe misses | 11/11 → 11/11 | 2/2 → 2/2 |
| Severe false alarms | 9 → 9 | 1 → 1 |

Development poor misses fall from 14/16 to 5/16; false alarms increase nine to
60, and accuracy decreases 0.8409 to 0.8337. Development still contains zero
severe hours. The poor floor cannot create severe detections, and severe
outcomes are consequently unchanged.

The floor's quantile-regression diagnostic has MAE 22.2669, RMSE 28.4847,
pinball loss 4.89259 and empirical coverage 0.801408 in the pollution period.
The corresponding later values are 13.0128, 19.5849, 2.76822 and 0.747954.
Coverage is below the nominal 0.9 in both periods; the forecast is not a
calibrated safety bound. Hybrid Brier/ECE are correctly null because a
band floor is not a coherent probability model. Incumbent poor probability
Brier/ECE remain 0.0644832/0.0517556 and 0.00538356/0.00348083; these
uncalibrated classifier scores do not transfer to the hybrid.

## Gate and stopping disposition

V6 does not pass the frozen utility gates. Pollution false alarms exceed the
absolute 0.05 cap and incumbent-plus-0.01 cap. Later false alarms also exceed
incumbent-plus-0.01; later accuracy loss is 0.0106383, above the allowed 0.01.
The large poor-recall gain does not override these failures.

The durable state correctly records two completed rounds, two consecutive
no-gain outcomes, `stopped: true`, and reason `two_consecutive_no_gain`. Retain
the research incumbent and stop submissions under this protocol. This finite
plateau does not establish the maximum achievable forecast quality.

## Concrete prerequisite for any later improvement program

The next task is a data-feasibility audit, before another model family or
parameter sweep. Training has 27 severe hours in six episodes; development
has zero severe hours; the five consumed evaluation severe episodes are all
ozone-driven and narrowly cross the repository's severe boundary. Repeated
fitting on the same thirteen hours cannot provide an independent severe test.

First establish what source can actually be obtained, with documented access,
license, recording period, geography, timestamp/timezone semantics, missingness,
gas coverage and sampling frequency. Station observations would enable a
different validation tier if accessible, but no station API, historical coverage
or free access has been verified here. Do not promise those inputs. If only
modeled archives are available, document that limitation and evaluate newly
recorded temporal episodes as modeled-archive evidence.

A future frozen dataset design needs distinct severe ozone episodes in
training, development and evaluation, separated at the episode level with
causal history and target embargoes. Establish feasibility and denominators
before fitting; severe recall in an empty development stratum remains
unmeasured. Choose support requirements and the target basis before inspecting
future evaluation outcomes. Preserve the existing instantaneous research target
when reproducing this sequence; official averaged station NAQI would require
a separately versioned target and appropriate pollutant averaging histories.

Actual station/prospective/human/field/medical evidence and billed cost remain
absent. Current deterministic permission boundaries and serving artifacts are
not qualified by this research review.

Sources: [v6 raw results](../eval/raw/forecast_risk_v6_results.json),
[gate summary](../eval/raw/forecast_risk_v6_gate_summary.json),
[loop state](../eval/raw/forecast_next_loop_state.json),
[v5 data review](FORECAST_V5_DATA_REVIEW.md), and
[pollutant diagnostic](FORECAST_POLLUTANT_DIAGNOSTIC.md).
