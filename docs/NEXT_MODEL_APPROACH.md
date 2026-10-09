# Next model approach

The priority is rare polluted-hour forecasting. The frozen V16 briefing adapter
remains provisional; deterministic current-hour permission continues to control
walking. The user authorized implementing this experiment; its hosted runner
trains research candidates without changing serving artifacts.

## Measured improvements and costs

- V16 improved the consumed missing-weather diagnostic from 6/24 to 21/24
  accepted cases. In the new synthetic evaluation it passed 46/48 finite checks,
  versus 48/48 for deterministic fallback. Its two flags are 12-hour renditions
  of the supplied 17:00 recheck window. All six current-GO cases passed. These
  sets differ; their percentages are not a before/after generalization result.
- Fine-tuning improves compliance at a latency cost: on the same V16 test
  prompts the base median GPU generation time is 2.712 seconds and the adapted
  median is 5.134 seconds. These exclude startup, voice, and end-to-end serving.
- In June's matched rolling evaluation, the ensemble improves moderate recall
  over LightGBM from 0.7234 to 0.8298, while accuracy falls from 0.7250 to 0.6403
  and macro-F1 falls from 0.4969 to 0.4264. This is a measured tradeoff, not proof
  that V16 caused a forecast regression; the briefing and forecast are different
  models.
- The ensemble predicts below poor on 33/33 poor-or-worse February hours,
  87/124 April hours, and 2/2 June hours. August contains no such examples.
  Current-hour deterministic permission is separate from these band forecasts.

Evidence: [briefing training metrics](../eval/raw/candidate_20261008T133038Z-eb8923e8_qwen3_4b.json),
[paired synthetic outputs](../eval/raw/qualification_v16_fresh_results.json),
[rolling raw outputs](../eval/raw/forecast_rolling_results.json), and
[full follow-up report](../eval/raw/next_qualification_report.md).

## Next controlled experiment

1. Expand recorded Bengaluru historical coverage across seasons and pollution
   episodes. Report the source and whether it is modelled archive data or station
   observations; do not silently treat one as the other. Preserve missing values
   and quality exclusions. Keep constructed hazards as stress tests, separate
   from natural-data accuracy.
2. Preregister a weighted LightGBM baseline and a separate poor-or-worse risk
   classifier. Select weights and probability thresholds only on chronological
   development windows, with a six-hour label gap and training-only imputation.
   The risk classifier is an experiment, not permission to walk.
3. Freeze configurations before assessing a genuinely unused period. Report
   class support, poor-or-worse underprediction, precision/false alarms, macro-F1,
   calibration, and accuracy together. The consumed rolling windows remain
   diagnostics and must not be renamed independent holdouts. Compare against
   the existing ensemble and persistence.
4. Adopt a candidate only if it reduces rare-air misses without unacceptable
   false alarms or loss of ordinary-hour usefulness. A larger transformer is
   worth comparing only after this controlled baseline has established the gap.

For briefing qualification, handle 12-hour/24-hour time equivalence in a future
checker version with contradiction tests; leave the frozen raw flags intact.
Compare useful current-GO prose and total latency against deterministic prose
with human review. More briefing training is not yet justified by the two time
format flags. Human outdoor observations remain NOT DONE.

## Repository cleanup

Removed four unreferenced helpers with obsolete hard-coded calls/manifests:
`scripts/autonomous_trainer.py`, `scripts/check_both_candidates.py`,
`scripts/save_iter6_7b.py`, and `scripts/run_continuous_worker.py`. Current
manifest-driven training, qualification and reporting runners remain available.

Raw evaluations, frozen checker snapshots, ledgers, curated datasets and serving
model artifacts are retained. `.gitignore` covers reproducible caches, temporary
backups, local logs, Modal state and optional downloaded/fitted artifacts.
Automatic approval review blocked shell deletion of cache/log paths, so those
ignored files remain locally. They are not removed by `.gitignore`.

## Implemented experiment

`scripts/train_forecast_risk_modal.py` records expanded real upstream responses
and derived rows in the Modal volume, pins their hashes in the returned result,
and compares ordinary LightGBM, the existing ensemble, persistence, weighted
LightGBM and a calibrated binary risk floor. No synthetic pollution rows are
included in these natural-data metrics. The saved remote bundle records feature
order, training medians, calibrated risk model, selected threshold and provenance.
Only result JSON and Markdown are fetched locally.

The preregistered dates are training January–October 2024, weight/model
development November–December 2024, probability calibration January 1–15 2025,
threshold selection January 16–31 2025, and locked evaluation February–April
plus May–October 2025. Every partition excludes features whose six-hour target
crosses its ending boundary. Weights 1/2/4/8 and thresholds 0.1–0.9 are frozen
before submission. Development selections require at most 10% false alarms on
non-poor hours and at most three percentage points of accuracy loss; these are
experiment criteria, not an asserted medical safety standard. No valid hybrid
threshold means the risk floor stays disabled and that limitation is reported.

Parameter choices were inspired by later consumed archive diagnostics. The new
historical periods were not previously evaluated here, but they are not
prospective station evidence. Source archive failures, missing risk support or
missing calibration classes abort rather than produce invented scores. Required
current/target pollutant and weather fields are screened against raw responses
before the builder's defaults can enter evaluation, and gap-crossing lag rows are
excluded. Brier score and reliability bins report probability quality separately
from the risk decisions. Model adoption requires inspecting actual final-period
tradeoffs; it is never automatic.

Reproduce using the Modal dependency group:

```powershell
uv run --group modal python scripts/train_forecast_risk_modal.py --submit
uv run --group modal python scripts/train_forecast_risk_modal.py --fetch
```

Submission refuses an existing manifest. Fetch uses a five-second timeout,
returns a pending status without blocking, and refuses to overwrite raw results.
Manifests and results live under `eval/raw/forecast_risk_v1_*`.


## V2 recovery protocol

V1 failed before fitting: its calibration window had zero poor-or-worse hours. V2 preserves that failed manifest and uses a separate local prefix and Modal-volume directory. Recorded 2024/2025 source responses are copied on the volume, preserving their bytes; 2023 responses are acquired for training. No weights or expanded archive are downloaded locally.

Training is January–December 2023. The January 2024–January 2025 development pool is allocated chronologically: first development, then calibration, then the remaining threshold-selection period. The first two endings are the earliest daily boundaries that retain at least 20 poor-or-worse and 200 below-poor usable hours after the six-hour target embargo. All three phases and training must meet those support minima, or fitting is refused. Resolved boundaries and measured support are saved remotely before fitting. The same fixed February–April and May–October 2025 evaluation periods are retained; their labels never select the development boundaries.

This is an explicit label-adaptive development design, motivated by the consumed v1 support diagnostic. Hourly pollution observations are correlated; 20 positives are a feasibility minimum, not independent episodes or a statistical-power guarantee. Existing later archive diagnostics inspired the configurations. Calibration is performed only when both classes and the minimum support are present; no fabricated calibration fallback is used. Candidate weights, thresholds, model parameters and false-alarm/accuracy criteria remain unchanged. The result is research-only and cannot automatically change serving.

```powershell
uv run --group modal python scripts/train_forecast_risk_modal.py --submit --version v2
uv run --group modal python scripts/train_forecast_risk_modal.py --fetch --version v2
```

The v2 manifest pins source hashes and the split-selection rule before submission. Returned results preserve resolved boundaries, source-response and dataset hashes, candidate comparisons, and raw predictions. An unsuccessful run remains a recorded failure. A known terminal support failure updates the local manifest to FAILED rather than leaving a stale SUBMITTED status.


## Research recommendation implemented after v2

The research agent recommended correcting the persistence target definition before further fitting. Future rare-air runs now declare instantaneous NAQI at t+6 as their target and compare instantaneous persistence separately from conservative persistence. Evaluation also reports classes absent from training. A no-fitting, hash-verified replay reproduced every target label on the consumed v2 periods. See [target audit](../eval/raw/forecast_risk_v2_target_audit.md). Next modeling requires a separately frozen coverage protocol with pollution episodes and severe-class support, before considering a larger model.

Reproduce this read-only source audit once with `uv run --group modal python scripts/audit_forecast_target.py`; it refuses to overwrite an existing audit. No new training or deployment occurred.


## V3 preregistered coverage ablation

The user authorized hosted fitting and fetching results. V3 compares identical fixed LightGBM configurations trained on January–December 2023 versus January 2023–May 2025. The expanded period includes the recorded March–May severe events. Models are ordinary multiclass and a fixed class-weight vector [1,1,1,4,16,16]; 16 for severe/hazardous is an a priori research choice, not selected on these evaluation labels. The old-period weighted candidate has the same poor weight as before. An expanded-training gate requires at least 20 severe hours. Actual support and episodes (positive hours separated by more than six hours) are reported; a large hourly count does not guarantee independent episodes.

Both training configurations are evaluated on the same February–April and May–September 2026 diagnostic periods. Expanded-training ensemble and matching instantaneous persistence are baselines. Historical conservative persistence is named separately. No probabilities are calibrated and no thresholds are selected in this ablation; Brier/ECE for LightGBM use raw class probabilities, while ensemble/persistence use binary decisions. Severe-or-worse misses/recall, unsupported classes, full classification and poor-or-worse risk are returned for each candidate.

The former v2 2025 evaluation periods are explicitly now used for training. The 2026 archive and earlier window metrics were already consumed in research. These are temporal diagnostics, not new independent holdouts; results cannot support automatic adoption or medical safety. Every phase excludes features with targets reaching its ending boundary. Required raw current/target measurements and contiguous lag history are screened, and each candidate fits medians on its own training partition only. Cached fixtures are copied on the Modal volume, with hashes preserved; no weights or expanded dataset are downloaded locally.

```powershell
uv run --group modal python scripts/train_forecast_risk_modal.py --submit --version v3
uv run --group modal python scripts/train_forecast_risk_modal.py --fetch --version v3
```

No serving artifact is changed. A source-hashed v3 manifest and separate remote directory preserve prior experiments. Offline tests and Ruff passed before submission.


## V4 research synthesis

Three research agents reviewed v3 and recommended target-aligned instantaneous history and a continuous-target comparison. The fixed 2x3 feature/target protocol, episode and onset reporting, source replay and timestamp checks are documented in [the research review](V3_RESEARCH_REVIEW_AND_V4_PROTOCOL.md). No quantile or feature set is selected from consumed diagnostics.
