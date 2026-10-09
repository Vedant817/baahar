# Model review after v5

V5 does not qualify as useful improvement under the protocol frozen before its
submission. Preserve the 35-column incumbent. The raw result and paired gate
summary are the evidence:

- `eval/raw/forecast_risk_v5_results.json`
- `eval/raw/forecast_risk_v5_gate_summary.json`
- `docs/FORECAST_NEXT_ITERATION_PROTOCOL.md`

The gas-history challenger improves pollution-period poor+ recall from
104/248 (41.94%) to 112/248 (45.16%), while accuracy decreases from 76.38% to
75.96% and poor+ false-alarm rate increases from 1.81% to 2.44%. However, poor+
episode any-hits decrease from 34/49 to 33/49. This fails the explicit episode
utility gate; additional hourly detections are not evidence of covering more
pollution episodes.

In the other-season period, poor+ recall decreases from 13/23 (56.52%) to
11/23 (47.83%). Accuracy changes from 83.06% to 83.12%, while macro-F1 falls
from 0.5696 to 0.5435. Poor+ episode any-hits increase from 4/7 to 5/7, but that
does not cancel the decline in hourly recall. There is no severe gain: all 11
and 2 severe target hours remain missed. These are correlated modeled archive
hours, not independent station or prospective observations.

The implementation preserves the training period, preprocessing discipline,
weights and model parameters, adds all four preregistered gases, and verifies
the fixed incumbent predictions against v4 hashes. The result therefore tests
the proposed gas-history feature addition. Retrospective O3 dominance explains
which pollutant determines the target index; it does not prove that current O3
features can predict six-hour peaks. V5 provides no such proof.

## Objection to a redundant v6 fitting run

The predeclared v6 is a fixed alpha=0.9 quantile poor-band floor over the same
35-column incumbent. Its head has already been fitted and evaluated with the
same data and parameters as `instant_history_quantile_0.9` in v4. In the
pollution period, that head has poor+ false-alarm rate **8.61%**
(0.08607863974495218).

The proposed floor warns poor+ whenever either the incumbent warns poor+ or
the q90 numeric prediction maps to poor+ through the shared band function.
Consequently, its poor+ false-positive set contains the q90 false-positive set.
The hybrid cannot have a false-alarm rate below 8.61% on this exact replay,
already above the protocol's **5% absolute cap**. Preserving existing severe
predictions does not change this poor+ set relation.

This is a structural objection using existing consumed results, not a newly
run v6 result or a threshold selected after evaluation. A new unchanged fitting
call would not create a new scientific comparison. If reproducibility differs,
investigate the replay before interpreting metrics. Do not alter alpha, gas
subset, threshold, or the gate to rescue this candidate.

Recommendation: retain the incumbent and record v5 as the first completed
no-gain round. To fulfill the authorized hosted evaluation workflow, v6 may
evaluate the predeclared floor on Modal using the existing frozen v4 model
bundle. This is an inference-only architecture evaluation, not another model
training run. It can count as the second completed research evaluation round
under the finite protocol; report its actual metrics before recording the
plateau. Verify both the incumbent predictions and q90 numeric predictions
against v4 digests. Record the actual bundle SHA256 at read time and disclose
that no prior bundle hash was recorded. A different challenger requires a new
preregistered rationale; the seven-round budget does not require spending all
seven rounds.
