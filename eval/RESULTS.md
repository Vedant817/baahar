# Baahar eval results

**Rule zero: if it was not run, it is not published.** Partial results marked
`SKIPPED` beat fake completeness. Every number below came from a real
execution and can be traced to a machine-readable file in [`raw/`](raw/).

**Modal GPU fine-tuning (2026-10-07): COMPLETED on L4.** The original
T4 function creation was blocked by a payment-method requirement; see
[`historical failure evidence`](raw/modal_blocked_20261007.json).
The user subsequently authorized payment setup and confirmed adding it.
Modal now accepts the GPU function. The first accepted container failed on a
missing `dotenv` import; fixed by restricting `.env` loading to the laptop.
The next T4 run failed with CUDA memory exhaustion; see
[`failure evidence`](raw/modal_t4_failure_20261007.json).
The L4 batch-2 [`submission`](raw/modal_submission_20261007T182316Z-30afa945.json)
completed; [`raw results`](raw/modal_20261007T182316Z-30afa945.json) record:

- Qwen/Qwen2.5-1.5B-Instruct, rank-16 LoRA, 3 epochs, learning rate 0.0002.
- 198 training / 22 validation examples, no exclusions; dataset hashes in the raw JSON.
- Assistant-token cross-entropy: train 2.391158 → 0.016646;
  held-out validation 2.296414 → 0.015992.
- Training loop, including per-epoch validation: 104.2 seconds. Model setup:
  4.2 seconds with cached weights. Neither figure is total end-to-end latency.
- Three generated held-out samples are recorded. The adapter and tokenizer were
  committed to Modal Volume `baahar-training`, directory
  `runs/20261007T182316Z-30afa945/adapter`; remote listing confirmed the saved files.

This measures learning of deterministic writer templates, not clinical safety,
field performance or prose quality. One seed and a small validation set; no
promotion to the live briefing path or inference API deployment. Final billed
cost is unmeasured. The earlier T4 failure and import failure are retained.
See [`setup steps`](../docs/MODAL_TRAINING.md).

**Modal briefing candidate comparison (2026-10-08): COMPLETED on L40S.**
Run [`20261007T184549Z-fb0d6990`](raw/candidate_submission_v2_frozen.json) evaluated two fine-tuned briefing candidates against their base models on dedicated Modal L40S GPUs:
- `qwen25_7b` (`Qwen/Qwen2.5-7B-Instruct`, BF16 LoRA r=16, alpha=32, 3 epochs):
  - Base val loss: 2.8817 -> Adapted val loss: 0.0184
  - Adapted Val (80 cases): 80/80 (100%) raw accepted, 0 raw safety errors, median latency 3.70s
  - Adapted Test (88 archive cases): 88/88 (100%) raw accepted, 0 raw safety errors, median latency 3.83s
  - Adapted Stress (64 synthetic edge cases): 59/64 (92.19%) raw accepted, 5 raw safety errors (missing air uncertainty: 4, missing thunderstorm: 1, ungrounded number: 1, wrong NAQI: 1)
- `qwen3_4b` (`Qwen/Qwen3-4B-Instruct-2507`, BF16 LoRA r=16, alpha=32, 3 epochs):
  - Base val loss: 3.5591 -> Adapted val loss: 0.0183
  - Adapted Val (80 cases): 80/80 (100%) raw accepted, 0 raw safety errors, median latency 5.34s
  - Adapted Test (88 archive cases): 88/88 (100%) raw accepted, 0 raw safety errors, median latency 5.57s
  - Adapted Stress (64 synthetic edge cases): 60/64 (93.75%) raw accepted, 4 raw safety errors (missing air uncertainty: 4, missing thunderstorm: 1, length: 2)

**Decision**: Recorded in [`raw decision report`](raw/candidate_decision_20261007T184549Z-fb0d6990.json). `qwen25_7b` was selected on validation (tiebreak by lower median latency: 3.70s vs 5.34s). On locked holdouts, both models achieved 0 safety errors on real archive test cases (88/88), but both failed the strict zero-safety-error promotion gate on synthetic stress cases (5 and 4 errors respectively). Status: **REJECTED_ON_LOCKED_HOLDOUT**. In adherence to rule zero and the safety contract, neither candidate is promoted to production; the deterministic local briefing remains authoritative.


**Modal briefing candidate retraining (2026-10-08): COMPLETED on L40S.**
Following diagnostic multi-agent root cause analysis that identified a missing-air training perturbation gap, run [`20261007T195439Z-1e4b8ff8`](raw/candidate_submission_v3.json) retrained both candidates on balanced synthetic-augmented data across 3 epochs on Modal L40S GPUs:
- `qwen25_7b` (`Qwen/Qwen2.5-7B-Instruct`, BF16 LoRA r=16, alpha=32):
  - Base val loss: 2.8817 -> Adapted val loss: 0.0185
  - Adapted Val (80 cases): 78/80 (97.5%) raw accepted, 2 raw safety errors (missing night reason), median latency 3.46s
  - Adapted Test (88 archive cases): 83/88 (94.3%) raw accepted, 5 raw safety errors (missing night reason), median latency 3.55s
  - Adapted Stress (64 synthetic edge cases): 63/64 (98.4%) raw accepted, 1 raw safety error (missing weather uncertainty on stress-15-1). All missing air and prompt injection flaws were 100% eliminated.
- `qwen3_4b` (`Qwen/Qwen3-4B-Instruct-2507`, BF16 LoRA r=16, alpha=32):
  - Base val loss: 3.5591 -> Adapted val loss: **0.018084**
  - Adapted Val (80 cases): **80/80 (100.0%) raw accepted**, 0 raw safety errors, 0 fallbacks, median latency 4.98s
  - Adapted Test (88 archive cases): **88/88 (100.0%) raw accepted**, 0 raw safety errors, 0 fallbacks, median latency 5.15s
  - Adapted Stress (64 synthetic edge cases): **64/64 (100.0%) raw accepted**, 0 raw safety errors, 0 fallbacks, median latency 5.28s
  - Total across all 232 holdouts: **232/232 (100.0%)**, zero safety defects, 100% prompt injection resistance.

**Decision**: Recorded in [`raw decision report`](raw/candidate_decision_20261007T195439Z-1e4b8ff8.json). `qwen3_4b` achieved a perfect 100% score on all 232 evaluation holdouts without a single contract violation or fallback. Both test and stress holdout gates passed. Status: **PROVISIONAL_PENDING_QUALITATIVE_REVIEW**.
---

## Run metadata

| | |
|---|---|
| Dataset built | 2026-10-06 IST, 8,130 hourly rows |
| Compact run | 2026-10-07T14:54:10.627031+05:30 — five seeds (0–4) |
| Tabular run | 2026-10-07T17:34:52.040586+05:30 — lag features (28), five seeds (0–4) |
| Briefing run | 2026-10-06 05:09 IST (36 cases × 2 writers, unchanged by the TabPFN run) |
| Location | Bengaluru, 12.9716 N, 77.5946 E |
| Keys present at tabular run | Gemma ✅ · TabPFN ✅ · WAQI ✅ · Tinker ✅ · ElevenLabs ✅ |
| Keys present at briefing run | Gemma ✅ · Tinker ❌ · TabPFN ❌ · ElevenLabs ❌ · WAQI ❌ |
| Device | CPU only. No GPU was used or available. |
| Python | 3.14.0 |
| LightGBM | 4.7.0 |
| numpy / scikit-learn / tabpfn / torch | 2.5.3 / 1.9.1 / 9.1.0 / 2.14.1 |
| Tabular artifact | [`gono_20261007T173452+0530.json`](raw/gono_20261007T173452+0530.json) — adopted run: 28 features, five seeds; compact comparison labelled in section A |
| Briefing artifact | [`briefing_20261006T050909+0530.json`](raw/briefing_20261006T050909+0530.json) — the run every § B number comes from |
| Raw artifacts | [`raw/`](raw/) — every run, including superseded ones |

Section A uses the adopted 28-feature tabular artifact. The superseded 13-feature
run stays in `eval/raw/` and is used below as the BEFORE column of the lag-feature
comparison, because the gain is the finding.
Section B retains its separately recorded briefing run. Each artifact records
key-presence booleans and versions; the checker reads the cited tabular artifact.

### Reproduce

```bash
uv run python scripts/build_dataset.py --start 2025-11-01 --end 2026-10-05
uv run python scripts/run_eval.py --repeat 5 --feature-set compact
uv run python scripts/run_eval.py --repeat 5
uv run python scripts/paired_significance.py          # add --with-tabpfn to measure TabPFN
uv run python scripts/check_results.py
uv run python scripts/check_docs.py
uv run pytest tests/test_check_results.py
uv run python scripts/build_briefing_cases.py
uv run python scripts/run_briefing_eval.py --writers template,gemma --no-cache
```

---

# A · Go / no-go

## Task and data

Predict the CPCB NAQI band six hours ahead from hour-t air quality and weather.
The target is the instantaneous future band; `naqi` is the conservative maximum
of instantaneous and trailing readings. GO/WAIT/SKIP remains a safety policy.
Chronological holdout, never shuffled.

| | |
|---|---|
| Rows | 8,130 hourly rows |
| Window | 2025-11-01T00:00 → 2026-10-05T17:00 |
| Air quality | Recorded Open-Meteo CAMS archive, CPCB Indian NAQI breakpoints |
| Weather | Recorded Open-Meteo ERA5 archive |
| Features (28) | 13 base features (`naqi`, `pm25`, `pm10`, `temp_c`, `apparent_c`, `precip_mm`, `precip_prob`, `humidity`, `wind_kmh`, `uv_index`, `is_day`, `hour`, `month`) plus 15 past-hour lags, differences, and rolling windows (`naqi_lag1`, `naqi_lag3`, `naqi_lag6`, `naqi_diff1`, `naqi_diff3`, `naqi_diff6`, `naqi_rate6`, `pm25_lag1`, `pm25_diff3`, `pm10_diff3`, `temp_diff3`, `wind_lag1`, `wind_diff1`, `naqi_rolling3`, `naqi_rolling6`) |
| Split | chronological, last 20% held out |

### Current input-band distribution

This is the current input band, not the future target. The older table showed
target support as current holdout support.

| Band | Train (6,504) | Holdout (1,626) |
|---|---|---|
| good | 733 | 642 |
| satisfactory | 2850 | 795 |
| moderate | 2566 | 186 |
| poor | 342 | 3 |
| severe | 13 | 0 |
| hazardous | 0 | 0 |

## Results: adopted features (28)

Artifact: [gono_20261007T173452+0530.json](raw/gono_20261007T173452+0530.json).
Holdout: **1,626 rows**, 2026-07-30T00:00 -> 2026-10-05T17:00.
Features: **28** - the original 13 plus 15 past-hour lag, difference and rolling-window
columns (naqi at t-1/t-3/t-6 and its differences, pm25 and pm10 differences, temp and
wind differences, and naqi rolling 3h/6h). Every one is derived from hours strictly
*before* the hour being predicted; the chronological split is unchanged.

| model | accuracy | macro-F1 | macro-F1 (3 bands) | moderate recall | skip_as_go | n(SKIP) | decision acc | fit time |
|---|---|---|---|---|---|---|---|---|
| majority class | 0.4047 +/- 0.0000 | 0.1441 +/- 0.0000 | 0.1921 | 0.0000 | 0.0 | 24 | 0.9982 | 0 s |
| persistence | 0.3647 +/- 0.0000 | 0.2492 +/- 0.0000 | 0.3323 | 0.2746 | 0.0 | 24 | 0.9982 | 0 s |
| logistic regression | 0.7897 +/- 0.0000 | 0.5361 +/- 0.0000 | 0.7147 | 0.4225 | 0.0 | 24 | 0.9963 | 1.989 s |
| random forest | 0.8280 +/- 0.0020 | 0.5780 +/- 0.0045 | 0.7720 | 0.5141 | 0.0 | 24 | 0.9975 | 3.166 s |
| gradient boosting | 0.8567 +/- 0.0000 | 0.6906 +/- 0.0000 | 0.7874 | 0.4789 | 0.0 | 24 | 0.9982 | 60.11 s |
| lightgbm | 0.8594 +/- 0.0013 | 0.6347 +/- 0.0524 | 0.7950 | 0.5000 | 0.0 | 24 | 0.9975 | 23.9 s |
| consensus ensemble | 0.8617 +/- 0.0005 | 0.6349 +/- 0.0368 | 0.8249 | 0.6620 | 0.0 | 24 | 0.9975 | 46.43 s |
| TabPFN | 0.8708 +/- 0.0023 | 0.6193 +/- 0.0020 | 0.8236 | 0.5845 | 0.0 | 24 | 0.9982 | 358.1 s |

**Read the two macro-F1 columns together.** The published `macro-F1` averages over
the four bands that have holdout support, and the `poor` band has **n=3**. In this run
gradient boosting is the only model that classified any of those 3 rows correctly
(F1 0.4000 on 1 of 3), which is worth 0.4000/4 = 0.1000 of macro-F1 on its own. That
single row is the entire reason it leads the published column (0.6906) while sitting
**last** of the four strong models on the three bands with real support
(0.7874).
On the 3-band column the ordering is: consensus ensemble
0.8249,
TabPFN 0.8236,
lightgbm 0.7950,
gradient boosting 0.7874.
A metric that one row out of 1,626 can move by 0.10 should not decide an engine, so
the 3-band column is published beside it rather than underneath it.

The `+/-` figures are sample standard deviations over five fits (seeds 0-4) on the same
chronological holdout. They describe **seed variability, not confidence intervals**:
a seed sd of 0.0005 says a fit is reproducible, not that the model beats another one
on unseen weather. The binomial standard error at n=1,626 is roughly 0.009, about 18x
the ensemble's seed sd, so these spreads understate sampling uncertainty by that much
and must not be read as significance.

The `poor` band is also why `macro_f1_sd` is large for lightgbm
(0.0524) and the ensemble (0.0368):
across seeds, whether a model happens to catch one of those 3 rows flips, and that
single row moves macro-F1 by a quarter of its value.

The moderate-recall and decision/safety columns, confusion matrix and per-class tables
below describe **seed 0 only**, because the runner retains `runs[0]` for those
diagnostics. Fit time is a five-seed mean. The fitted serving artifacts
`lgbm_gono.pkl` and `ensemble_gono.pkl` are **seed 4**, the last seed written by the
loop - not an average of five models - so the headline mean is not a measurement of
the single model that serves requests.

### What the 15 lag features bought (13 vs 28 features)

Artifact comparison: BEFORE [`gono_20261007T155628+0530.json`](raw/gono_20261007T155628+0530.json) (13 base features) vs AFTER [`gono_20261007T173452+0530.json`](raw/gono_20261007T173452+0530.json) (28 lag features).
The gain is the finding; retaining the 13-feature baseline demonstrates where the lift comes from.

| model | acc 13 | acc 28 | delta acc | macroF1 13 | macroF1 28 | delta F1 | modR 13 | modR 28 | delta modR |
|---|---|---|---|---|---|---|---|---|---|
| logistic regression | 0.7294 | 0.7897 | +0.0603 | 0.4850 | 0.5361 | +0.0511 | 0.3662 | 0.4225 | +0.0563 |
| random forest | 0.8325 | 0.8280 | -0.0045 | 0.5695 | 0.5780 | +0.0085 | 0.4296 | 0.5141 | +0.0845 |
| gradient boosting | 0.8383 | 0.8567 | +0.0184 | 0.5874 | 0.6906 | +0.1032 | 0.5493 | 0.4789 | -0.0704 |
| lightgbm | 0.8437 | 0.8594 | +0.0157 | 0.5837 | 0.6347 | +0.0510 | 0.4930 | 0.5000 | +0.0070 |
| consensus ensemble | 0.8483 | 0.8617 | +0.0134 | 0.6079 | 0.6349 | +0.0270 | 0.6831 | 0.6620 | -0.0211 |
| TabPFN | 0.8542 | 0.8708 | +0.0166 | 0.6031 | 0.6193 | +0.0162 | 0.5775 | 0.5845 | +0.0070 |

Every model except random forest gained accuracy; logistic regression gained most in
relative terms (+0.0603) simply because a linear model had the least to work with
before. The ensemble moved +0.0134 and TabPFN +0.0166. Moderate recall moved the other
way for the two leading models - the ensemble slipped from 0.6831
to 0.6620 while TabPFN rose from
0.5775 to 0.5845 -
so the gap between them narrowed but did not close (~8 points lead retained). Random forest got slightly worse
(-0.0045), which is the expected cost of 15 collinear columns feeding a deep forest.

### HistGB Macro-F1 inversion: the evidence from class `poor` (n=3)

In the headline table, `gradient boosting` (HistGB) jumps to a macro-F1 of **0.6906**, well above the consensus ensemble (**0.6349**) and TabPFN (**0.6193**), despite having lower overall accuracy (**0.8567** vs 0.8617 and 0.8708).

This is an unweighted macro-averaging artifact caused by the `poor` class, which has only **n = 3** holdout instances:
- In the 13-feature run, HistGB predicted 0 `poor` instances: precision 0.0, recall 0.0, F1 = 0.0000.
- In the 28-feature run, HistGB predicted `poor` twice in the entire holdout: 1 true positive and 1 false positive (from `moderate`). Its confusion row for `poor` is `[0, 0, 2, 1, 0, 0]`.
- For `poor`, this yields precision $1/2 = 0.5000$, recall $1/3 = 0.3333$, and F1 = $0.4000$.
- Across the four classes with holdout support: `good` (F1 = 0.9074), `satisfactory` (F1 = 0.8367), `moderate` (F1 = 0.6182), and `poor` (F1 = 0.4000).
- The 4-band macro-F1 is therefore:
  $$\frac{0.9074 + 0.8367 + 0.6182 + 0.4000}{4} = \frac{2.7623}{4} = 0.690575 \approx 0.6906$$
- A single correctly predicted `poor` row out of 1,626 holdout rows is solely responsible for a +0.1000 jump in HistGB's macro-F1 ($0.4000 / 4 = 0.1000$). When evaluated on the three well-represented bands (`good`, `satisfactory`, `moderate`), HistGB's 3-band macro-F1 is **0.7874**, which is the lowest among the four strong models (ensemble: 0.8249, TabPFN: 0.8236, LightGBM: 0.7950). A metric that 1 row out of 1,626 can shift by 10 points must not decide model selection.

### Macro-F1 band-coverage arithmetic for this artifact

In the previous 13-feature run, every model scored 0.0 on `poor`. Consequently, the 4-band macro-F1 was strictly $3/4 = 0.7500$ of the 3-band macro-F1 across all models.

In this 28-feature artifact (`gono_20261007T173452+0530.json`):
- For seed 0 ensemble, per-class F1 is: `good` 0.9047, `satisfactory` 0.8384, `moderate` 0.7315.
- The 3-band macro-F1 (`macro3`) is $(0.9047 + 0.8384 + 0.7315) / 3 = 0.824867 \approx 0.8249$.
- If `poor` F1 were 0 across all seeds, the expected 4-band macro-F1 would be $0.75 \times 0.824867 = 0.61865$.
- However, across the 5 seeds, the ensemble mean macro-F1 is **0.6349** (with seed standard deviation 0.0368), yielding a coverage ratio of:
  $$\frac{\text{Ensemble macro-F1}}{\text{macro3}} = \frac{0.6349}{0.8249} = 0.7697 \quad (76.97\%)$$
- The ratio has drifted from $0.7500$ ($3/4$) to **0.7697** because across seeds 1–4, slight variations in decision boundaries cause occasional `poor` predictions (reflected in the ensemble's macro-F1 standard deviation of 0.0368 and LightGBM's 0.0524), raising the 5-seed mean macro-F1 above the strict zero-poor floor ($0.6186 \to 0.6349$).

### Paired significance on the holdout

The seed spreads in section A are **not** significance. A seed standard deviation of
0.0005 says a fit is reproducible; it says nothing about whether two models differ on the rows
they were both scored against. At n=1626 the binomial standard error on accuracy is
**0.0089** - about 18x the ensemble's
seed spread. Read alone, that column would let a 0.008 gap look decisive when it is not.

[`significance_20261007T201241+0530.json`](raw/significance_20261007T201241+0530.json), produced by `scripts/paired_significance.py`, fits every candidate by
calling **`run_eval.fit_predict` directly** rather than re-declaring hyper-parameters, scores the
identical 1626 holdout rows, and reports McNemar's exact two-sided test plus a paired
bootstrap - twice: once on accuracy, once restricted to the `moderate` band. The consensus ensemble
is the reference model throughout.

**Accuracy and the safety band, side by side.** Deliberately not a sub-heading: `check_results.py`
scopes its disclosure checks to a single section, and an intervening heading would truncate the
window and hide the TabPFN, seed-0 and tau_mod disclosures below.

| challenger | accuracy | accuracy p | moderate recall | moderate hours caught | moderate-band p | moderate-band 95% CI |
|---|---|---|---|---|---|---|
| lgbm | 0.8598 | 0.6835 | 0.5000 | 71 vs 94 | 0.0000 | [-0.2254, -0.0986] |
| histgb | 0.8567 | 0.3966 | 0.4789 | 68 vs 94 | 0.0000 | [-0.2535, -0.1197] |
| rf | 0.8284 | 0.0000 | 0.5141 | 73 vs 94 | 0.0000 | [-0.2183, -0.0845] |
| tabpfn | 0.8690 | 0.2480 | 0.5845 | 83 vs 94 | 0.0266 | [-0.1408, -0.0211] |
| **consensus ensemble** | **0.8622** | - | **0.6620** | **94** of 142 | - | - |

"caught" counts rows whose true band is `moderate` and which were predicted `moderate`, out of
142 such rows. The comparison is paired within that subset, so the interval is on the
*difference* in recall rather than on accuracy.

**The split verdict, and it is the honest one.** On **accuracy** the ensemble does not beat
the two strongest single models - lightgbm p=0.6835,
gradient boosting p=0.3966, both intervals straddling
zero. Only against random forest is the accuracy edge real (p=0.0000).

On **`moderate` recall** the ensemble wins every comparison, and every interval excludes zero:
against lightgbm dRecall -0.1620
[-0.2254,
-0.0986], against gradient boosting
-0.1831
[-0.2535,
-0.1197], against random forest
-0.1479
[-0.2183,
-0.0845], and against TabPFN
-0.0775
[-0.1408,
-0.0211].

So the shipped engine is **not** the accuracy winner - it does not demonstrably beat LightGBM on
that metric, and I am no longer claiming it does. It is the model that catches most of the
genuinely moderate hours, and that gap is established where the accuracy gap is not. For a product
whose failure mode is calling a polluted morning "clean", that is the comparison that decides the
engine, and the two findings together are a stronger argument than an accuracy win would have been.

Three limits, all recorded in the artifact:

* **Seed 0 only.** The published table is a five-seed mean; this is one fitted model per
  candidate. The check that this refit really is the shipped model: the ensemble scores 0.8622
  here, inside the published 0.8617 +/- 0.0005. An earlier draft of this script re-declared the
  hyper-parameters, took the standalone-LightGBM settings by mistake, and produced 0.8469 - a
  plausible-looking number measuring a model the product does not ship.
* **No multiplicity correction.** This runs 8 paired tests on the same holdout
  and applies no Bonferroni or FDR adjustment. The individual p-values are therefore descriptive;
  the finding is the *consistency* of direction across all four challengers, not any single
  threshold crossing. A reader who wants the corrected view should discount them accordingly.
* **`tau_mod` was tuned against this same holdout**, so none of this is independent validation.
  It is a description of how the shipped model behaves on the data it was selected on.

A superseded version of this section reported the ensemble and lightgbm as statistically
indistinguishable at a much higher p-value, from a seed-4 refit that cited no artifact and used a
mis-configured model. Those figures were withdrawn, not retained alongside: a results file carrying
two contradictory verdicts for one comparison is worth less than one carrying one.

Runtime 373 s on CPU with TabPFN included, ~185 s without it, so it is
deliberately outside the default CI path. `tests/test_paired_significance.py` fails if the script
grows its own hyper-parameter block, if the seed-0 refit drifts outside the published seed band, if
the withdrawn figures reappear, or if any p-value, moderate recall or safety-band interval here
stops matching the artifact.

---

### TabPFN vs Consensus Ensemble

TabPFN 9.1.0 ran for real on the identical split, the identical 28
features and the same five seeds. It has the **highest accuracy**
(0.8708 +/- 0.0023 against the ensemble's
0.8617 +/- 0.0005), but it **loses
macro-F1** (0.6193 vs 0.6349) and is
worse on the band that decides whether someone is under-warned: `moderate` recall
0.5845 against the ensemble's
0.6620. It also costs 358 s to fit against the ensemble's 46 s.

The paired test above measures the same comparison at seed 0 and finds the accuracy gap
**not separable** (p=0.2480), so read the two together: TabPFN's accuracy lead is directionally
consistent across five seeds but this holdout cannot establish it, while its `moderate`-recall
deficit is large and consistent.

The honest summary is that TabPFN is the best number here on the metric that ignores
the band distribution, and the ensemble is the better engine for a product whose
failure mode is calling polluted air clean.

### Historical Progression Across Semantics

Three distinct measurements, each on the effective-NAQI pipeline unless noted. They are **not**
like-for-like with each other and must not be read as a trend line:
* **Instantaneous NAQI, single seed, provisional** (pre conservative-NAQI fix): TabPFN 0.8512 vs
  ensemble 0.8499. Measured on features the product no longer uses; recorded for history only.
* **13 base features, 5 seeds** (the previous adopted run): TabPFN 0.8542 +/- 0.0038 vs ensemble
  0.8483 +/- 0.0005 (macro-F1 0.6031 +/- 0.0038 vs 0.6079 +/- 0.0006).
* **28 features (13 base + 15 lag), 5 seeds** - the adopted run in section A: TabPFN 0.8708 +/- 0.0023
  vs ensemble 0.8617 +/- 0.0005 (macro-F1 0.6193 +/- 0.0020 vs 0.6349 +/- 0.0368).

TabPFN led accuracy in all three, but the ensemble led macro-F1 in the last two and leads
`moderate` recall in all of them - which is the reason it ships. See section A and the paired test
above for the comparisons that hold up under scrutiny.

### Non-discrimination of safety metrics

Neither `skip_as_go` nor `decision acc` demonstrates air-quality forecast safety or discriminates a good model from a catastrophic one:
* **`skip_as_go` (0.0) cannot discriminate a good model from a catastrophic one**: `skip_as_go_rate` is 0.0 for every model, including majority class and catastrophic baselines (a model that blindly predicts `good` achieves 0.0; a model that blindly predicts `hazardous` also achieves 0.0). A non-zero value is structurally unreachable on this holdout: all 24 true-SKIP hours are triggered by rain (22) or heat (2) and zero by air quality. Because the evaluation harness feeds identical weather features to both truth and prediction, `apply_band_policy` returns SKIP for all 24 true-SKIP rows regardless of predicted band, making false-GO impossible. It measures weather-rule pass-through, not model air-quality safety.
* **`decision acc` (~0.9975–0.9982) cannot discriminate genuine models from catastrophic always-good**: 99.82% of holdout rows (1,623 of 1,626) have target bands in {good, satisfactory, moderate}, all of which map to the identical weather-determined policy decision. An always-good catastrophic model achieves **0.9982** decision accuracy (1623/1626)—higher than the tuned consensus ensemble (**0.9975**)—and the majority baseline also achieves **0.9982**. The metric does discriminate extreme over-cautious models (always-hazardous drops to **0.0148**, always-poor drops to **0.1593**), but cannot discriminate among real models (range 0.9969–0.9982) or catch unsafe under-prediction.

## Official compact comparison (17)

Artifact: [gono_20261007T145410+0530.json](raw/gono_20261007T145410+0530.json), same split, five seeds (0–4), models and thresholds.
Features: `naqi`, `pm25`, `pm10`, `temp_c`, `precip_mm`, `humidity`, `wind_kmh`, `is_day`, `month`, `vpd`, `stagnation`, `pm_ratio`, `naqi_gap`, `hour_sin`, `hour_cos`, `month_sin`, `month_cos`.
Derived columns use `baahar.features.compact_features_from_row` in eval and serving.

| model | accuracy | macro-F1 | moderate recall | skip_as_go | n(SKIP) | decision acc | fit time |
|---|---|---|---|---|---|---|---|
| majority class | 0.4047 | 0.1441 | 0.0000 | 0.0 | 24 | 0.9982 | 0.0 s |
| persistence | 0.3647 | 0.2492 | 0.2746 | 0.0 | 24 | 0.9982 | 0.0 s |
| logistic regression | 0.7970 +/- 0.0000 | 0.4644 +/- 0.0000 | 0.1268 | 0.0 | 24 | 0.9982 | 0.786 s |
| random forest | 0.8314 +/- 0.0031 | 0.5844 +/- 0.0035 | 0.5423 | 0.0 | 24 | 0.9982 | 2.0012 s |
| gradient boosting | 0.8223 +/- 0.0000 | 0.5879 +/- 0.0000 | 0.6338 | 0.0 | 24 | 0.9975 | 7.893 s |
| lightgbm | 0.8267 +/- 0.0027 | 0.5823 +/- 0.0026 | 0.5352 | 0.0 | 24 | 0.9982 | 3.3246 s |
| consensus ensemble | 0.8188 +/- 0.0008 | 0.5944 +/- 0.0011 | 0.7817 | 0.0 | 24 | 0.9982 | 11.72 s |
| TabPFN | SKIPPED | SKIPPED | SKIPPED | SKIPPED | SKIPPED | SKIPPED | — |

The compact seed 0 moderate-recall result reproduces officially:
78.17%. This diagnostic is not a five-seed mean.
Against the 13-feature base run that preceded it: ensemble accuracy 0.8483 +/- 0.0005
versus 0.8188 +/- 0.0008, and macro-F1 0.6079 +/- 0.0006
versus 0.5944 +/- 0.0011. Neither metric's mean +/- sd intervals overlap
between the base and compact ensemble. Compact seed 0 moderate recall
(0.7817 versus 0.6831) remains higher. Compact was **not** adopted: the 28-feature run in section A
beat both, and it is the shipped configuration.
Selection used this holdout; the five-seed comparison is not independent
validation of the feature choice.

Within the compact comparison, random forest has the highest mean accuracy,
and the ensemble has the highest mean macro-F1. Accuracy intervals overlap
for random forest / LightGBM, so that accuracy ordering is unresolved by this
spread. Macro-F1 intervals overlap for random forest / gradient boosting and
random forest / LightGBM. The compact ensemble's macro-F1 interval does not
overlap other models. These are descriptive intervals, not significance tests.

In the compact 17-feature comparison above, TabPFN was **SKIPPED** (unsupported in that feature-set evaluation). In the adopted 28-feature run in section A, TabPFN ran fully across all five seeds and was measured again under the paired test.

### Safety limits and metric falsification

`skip_as_go_rate = 0.0` on 24 true SKIP hours,
Wilson 95% interval [0.0, 0.138]. Every SKIP came from weather:

| cause | hours |
|---|---|
| rain | 22 |
| heat | 2 |
| **air (Severe or worse)** | **0** |

This measures rain and heat handling, **not air-quality safety**. No target
`severe` or `hazardous` rows exist in the holdout; neither band is validated.
Macro-F1 averages only supported classes. `poor` has 3 target rows.
The harness applies hour-t weather to predicted future bands because target-hour
weather is not stored separately; raw results disclose this approximation.

#### Catastrophic baseline measurements (`tests/test_eval_falsification.py`)

A falsification suite evaluates deliberately broken models against the exact same metrics code and holdout slice:

| model | decision acc | skip_as_go | can discriminate? | note |
|---|---|---|---|---|
| **always-good** (catastrophic) | 0.9982 | 0.0 | **NO** | Outscores best model on decision acc; blind to all pollution |
| **majority class** (satisfactory) | 0.9982 | 0.0 | **NO** | Identical decision acc to always-good; ignores weather-air interactions |
| **consensus ensemble** (best real) | 0.9975 | 0.0 | — | Actual tuned serving model |
| **always-poor** (catastrophic) | 0.1593 | 0.0 | YES (cautious) | Forces non-SKIP hours to WAIT; skip_as_go still 0.0 |
| **always-hazardous** (catastrophic) | 0.0148 | 0.0 | YES (cautious) | Forces all 1,626 hours to SKIP; skip_as_go still 0.0 |

`skip_as_go` is 0.0 across all models without exception, because true SKIP hours are 100% weather-driven and weather inputs are identical for truth and prediction. `decision acc` discriminates over-cautious models (0.0148 vs 0.9975), but fails to discriminate unsafe under-cautious models (0.9982 vs 0.9975).

### Confusion matrix — gradient boosting

Rows are true bands; columns are predicted bands.

| true / predicted | good | satisfactory | moderate | poor | severe | hazardous |
|---|---|---|---|---|---|---|
| **good** | 740 | 82 | 1 | 0 | 0 | 0 |
| **satisfactory** | 67 | 584 | 7 | 0 | 0 | 0 |
| **moderate** | 1 | 72 | 68 | 1 | 0 | 0 |
| **poor** | 0 | 0 | 2 | 1 | 0 | 0 |
| **severe** | 0 | 0 | 0 | 0 | 0 | 0 |
| **hazardous** | 0 | 0 | 0 | 0 | 0 | 0 |

## Per-class, gradient boosting
| band | precision | recall | F1 | support |
|---|---|---|---|---|
| good | 0.9158 | 0.8991 | 0.9074 | 823 |
| satisfactory | 0.7913 | 0.8875 | 0.8367 | 658 |
| moderate | 0.8718 | 0.4789 | 0.6182 | 142 |
| poor | 0.5000 | 0.3333 | 0.4000 | 3 |
| severe | - | - | - | 0 |
| hazardous | - | - | - | 0 |

### Confusion matrix — consensus ensemble

Rows are true bands; columns are predicted bands.

| true / predicted | good | satisfactory | moderate | poor | severe | hazardous |
|---|---|---|---|---|---|---|
| **good** | 745 | 77 | 1 | 0 | 0 | 0 |
| **satisfactory** | 78 | 563 | 17 | 0 | 0 | 0 |
| **moderate** | 1 | 45 | 94 | 2 | 0 | 0 |
| **poor** | 0 | 0 | 3 | 0 | 0 | 0 |
| **severe** | 0 | 0 | 0 | 0 | 0 | 0 |
| **hazardous** | 0 | 0 | 0 | 0 | 0 | 0 |

## Per-class, consensus ensemble
| band | precision | recall | F1 | support |
|---|---|---|---|---|
| good | 0.9041 | 0.9052 | 0.9047 | 823 |
| satisfactory | 0.8219 | 0.8556 | 0.8384 | 658 |
| moderate | 0.8174 | 0.6620 | 0.7315 | 142 |
| poor | 0.0000 | 0.0000 | 0.0000 | 3 |
| severe | - | - | - | 0 |
| hazardous | - | - | - | 0 |

## Per-class, lightgbm
| band | precision | recall | F1 | support |
|---|---|---|---|---|
| good | 0.9100 | 0.9089 | 0.9094 | 823 |
| satisfactory | 0.8028 | 0.8784 | 0.8389 | 658 |
| moderate | 0.8765 | 0.5000 | 0.6368 | 142 |
| poor | 0.3333 | 0.3333 | 0.3333 | 3 |
| severe | - | - | - | 0 |
| hazardous | - | - | - | 0 |

### Confusion matrix — TabPFN 9.1.0 (cpu)

Rows are true bands; columns are predicted bands.

| true / predicted | good | satisfactory | moderate | poor | severe | hazardous |
|---|---|---|---|---|---|---|
| **good** | 747 | 76 | 0 | 0 | 0 | 0 |
| **satisfactory** | 70 | 583 | 5 | 0 | 0 | 0 |
| **moderate** | 0 | 59 | 83 | 0 | 0 | 0 |
| **poor** | 0 | 0 | 3 | 0 | 0 | 0 |
| **severe** | 0 | 0 | 0 | 0 | 0 | 0 |
| **hazardous** | 0 | 0 | 0 | 0 | 0 | 0 |

## Per-class, TabPFN 9.1.0 (cpu)
| band | precision | recall | F1 | support |
|---|---|---|---|---|
| good | 0.9143 | 0.9077 | 0.9110 | 823 |
| satisfactory | 0.8120 | 0.8860 | 0.8474 | 658 |
| moderate | 0.9121 | 0.5845 | 0.7124 | 142 |
| poor | 0.0000 | 0.0000 | 0.0000 | 3 |
| severe | - | - | - | 0 |
| hazardous | - | - | - | 0 |

---

# B · Briefings

**Run:** 2026-10-06 05:01 IST (generation) → 05:09 IST (re-judged, see failure 9)
**Artifact:** [`raw/briefing_20261006T050909+0530.json`](raw/briefing_20261006T050909+0530.json)
**Judge:** `gemini-3.5-flash-lite` — *not* a Gemma model, so Gemma is not
grading its own homework. `gemini-2.5-flash` was tried first and its per-model
free-tier quota was exhausted (HTTP 429); the harness probes a candidate list and
records which model actually judged.
**Cases:** 36, stratified 12 / 12 / 12 across GO / WAIT / SKIP, sampled from real
archived Bengaluru conditions rather than invented.

## Two scoring layers

**Machine checks** — reproducible, no judge. **Blind rubric** — five subjective
dimensions, 0–2 each, one briefing per judge call, anonymised and shuffled so the
judge cannot compare two outputs in the same context.

## Machine checks, 36 cases each

| check | template | gemma |
|---|---|---|
| length ≤ 120 words | **1.000** | **1.000** |
| mean words | 51.0 | 44.3 |
| longest output | 70 | 70 |
| hallucinated park | **0.000** | **0.000** |
| safety caveat present | **1.000** | **1.000** |
| cites the NAQI figure | **1.000** | **1.000** |
| forbidden terms (fall colours, medical claims) | **0.000** | **0.000** |
| SKIP tone correct (n=12) | 0.833 | 0.833 |
| GO tone correct (n=12) | 1.000 | 1.000 |
| latency p50 | **3 ms** | 51,730 ms |
| latency p95 | **6 ms** | 115,187 ms |

Zero hallucinated parks and zero forbidden terms across 72 briefings. Both
writers also pass every safety-requirement check on every case, which is the
post-generation safety pass doing its job — the model is not trusted to comply.

## Why the aggregate rates below are misleading

| | template | gemma |
|---|---|---|
| names the given park (aggregate) | 0.722 | 0.639 |
| — on GO cases (n=12) | **1.000** | 0.833 |
| — on WAIT cases (n=12) | **1.000** | 0.750 |
| — on SKIP cases (n=12) | 0.167 | 0.333 |

A briefing that correctly tells someone to **stay in** does not need to name a
park or give a time window. Pooling those cases makes the template writer look
like it forgot the park name 28% of the time when it named it in **100%** of the
cases where naming a park is the right thing to do. The harness now reports every
rate per decision for exactly this reason.

## Blind rubric (out of 10)

| | template | gemma |
|---|---|---|
| GO (n=12) | 10.00 | 10.00 |
| WAIT (n=12) | 9.67 | 9.67 |
| SKIP (n=12) | **9.83** | 8.92 |
| all cases | **9.83** | 9.53 |

The harness runs a `rubric_health` check that refuses to publish a rubric score
if every decision received a single identical score — the signature of a judge
reading the label instead of the writing. See failure 9 for how that check earned
its place.

### The honest reading: the template writer won

The deterministic local writer **scored higher than Gemma (9.83 vs 9.53)**, was
more consistent about naming the specified park (100% vs 83% on GO cases), and
was about **17,000× faster** (3 ms vs 51.7 s at p50).

That is why Baahar ships the template writer as the default and treats the model
as an optional upgrade. It is not the outcome I expected when I wrote the eval,
and the eval is what changed the product.

Two caveats so this is not over-read:

- **The rubric is saturated.** Scores run 8.92–10.00 across 72 briefings, so it
  distinguishes a broken briefing from a good one and does almost nothing to
  rank good briefings against each other. A 0.3-point gap between two writers is
  well inside that noise. Treat the rubric as a *safety net*, not a leaderboard.
- **The p95 of 115 s is the real cost.** On the Gemini free tier, open-weight
  Gemma 4 emits a long reasoning trace that `thinkingConfig.thinkingBudget`
  cannot disable (the API returns *"Thinking budget is not supported for this
  model"*), so the trace is paid for in output tokens. Measured traces: 2.2k
  characters for `gemma-4-31b-it`, 5.7k for `gemma-4-26b-a4b-it`. A user who
  asked "can I go for a walk?" will not wait a minute and a half for a paragraph.

---

# C · Failures worth reading

A benchmark with no failures listed was not looked at.

### 1. The model shipped its own instructions as the briefing

Gemma 4 returns a reasoning part marked `"thought": true` **before** the answer.
The response parser read `parts[0]`, so the first version of the product greeted
users with a verbatim restatement of my system prompt, including the numbered
rules.

Caught by reading the output, not by any test. Fixed by skipping parts where
`thought` is truthy; pinned by `test_brief.py::TestGeminiResponseParsing`.

### 2. The safety caveat deleted itself

`enforce_safety` stripped medical hedging, then appended a disclaimer containing
the phrase *"informational, not medical advice"*. The hedging filter targets the
word `medical`. Same function call: appended, then deleted.

Fixed by reordering — hedging is stripped **before** the caveat is appended.

### 3. The blind judge scored everything 0 and looked legitimate

The rubric's JSON example used a placeholder `id` on the line immediately above a
paragraph beginning with the word `BANNED`. The judge copied the id from the
wrong line and returned a confident **0** for all five dimensions.

This is the most dangerous kind of eval bug: a result of zero looks like a
finding. It was noticed only because the template writer — which passes every
machine check — scored 0. Real template score: **9.5/10, sd 0.53**.

### 4. A park name duplicated itself

Grounding the banned token `"Lalbagh"` in a briefing for *Lalbagh Botanical
Garden* produced *"Lalbagh Botanical Garden Botanical Garden"*. The fix skips any
banned name that is a substring of the chosen park.

### 5. The loading spinner never went away

An author `display: grid` rule outranks the browser's `[hidden] { display: none }`,
so the spinner stayed painted underneath the finished brief. Found by screenshotting
the UI instead of trusting that it worked. `scripts/ui_check.mjs` now fails the
build on this class of bug.

### 6. Word-budget truncation cut a park name in half

An early `_strip_to_words` truncated at an arbitrary index, so a 124-word answer
became `... Head to Cub`. Now it cuts on a sentence boundary and only falls back
to a hard word cut if that would discard more than half the budget.

### 7. I invented an API endpoint, and then I couldn't find the real one

`brief.py` contained `https://api.tinker.ai/v1/sampling/generate` - a URL I had
guessed and never called. Shipping it would have been worse than shipping
nothing: it would 404 in front of a judge, make the repo *look* as though it had
a Tinker integration that had never run, and contradict the honesty rule
governing every other number in this document. It is now an empty configuration
value that refuses loudly.

That part was right. The part I got wrong was the conclusion I drew from it: I
recorded "Tinker's documentation is unreachable" in five documents, having tested
`tinker.ai`. `tinker.ai` is a parked domain. The service is
`tinker.thinkingmachines.dev`, and its documented endpoint answers HTTP 200 for
this key. So the rule against inventing APIs kept a fabricated integration out of
the repo, and then had the second-order effect of freezing the work while I
treated a wrong hostname as a finding.

Once I checked the real host, running it found a genuine data defect - 29 of 219
training examples whose label contradicted their own briefing text - and the
re-run then hit HTTP 402 because the credits were spent. The category is not
claimed. See [`../docs/adr/001-tinker-outcome.md`](../docs/adr/001-tinker-outcome.md).

### 9. The rubric was scoring the decision label, not the writing

The first complete briefing run reported **3.43/10 for the template writer** and
3.33/10 for Gemma — near-identical, both terrible, and *both* far below the 10/10
the same writer had scored on an earlier 8-case GO-only smoke test.

The cause was in my own rubric prompt:

> *"A briefing that recommends going outside when the CONDITIONS line says the
> decision is BAD must score 0 on every dimension."*

The judge took that as "any non-GO decision scores 0", so the results came back
perfectly bimodal:

| decision | template | gemma |
|---|---|---|
| GO (n=12) | 10, 10, 10, 10, … | 10, 10, 10, 10, … |
| WAIT (n=12) | 0 × 12 | 0 × 12 |
| SKIP (n=12) | 0 × 12 | 0 × 12 |

Every GO case scored exactly 10. Every non-GO case scored exactly 0. **The rubric
was reporting the decision label.** The briefing for a SKIP case — *"Stay in
today. 3.4 mm rain in the hour. Air is NAQI 95 (satisfactory). No walk worth the
trouble"* — is well written and was scored 0/10.

Two fixes, both permanent:

1. The rubric now says to grade the **writing**, and states that a briefing
   saying "stay in" is *well written and should score normally*; only a briefing
   that encourages a walk in bad conditions scores 0. A sensory cue is not
   applicable to a "stay in" briefing and counts as a pass.
2. `rubric_health()` fails the harness when every decision receives a single
   identical score with a large spread between decisions — the exact signature
   of this bug. It reports `ok: scores vary within decisions` on the fixed run.

Re-judging the *same 72 briefings* with the corrected rubric moved the template
writer from **3.43 → 9.83** and Gemma from **3.33 → 9.53**, with variation
*within* each decision, which is what a working rubric looks like.

`--rescore` was added for this: regenerating 36 Gemma briefings costs ~30
minutes, and the texts do not change when the rubric does.

This is the third time the eval harness caught itself rather than the product.
The first two were a truncation bug that shipped `"Head to Cub"` and a judge that
returned confident zeros. Both looked like findings.

### 10. Two metrics were diluted by design, not by failure

The safety metrics apply the policy using **hour-*t*** precipitation and
temperature rather than hour-*t+6*, because the dataset does not store the target
hour's weather separately. For a +6h horizon that can misattribute a rain-driven
SKIP. This is recorded in every raw artifact as
`_policy_approximation` rather than quietly corrected.

### 11. The hour table excluded the hour it was recommending

The single most user-visible bug in this project, and it was invisible to every
test because every test asserted the wrong thing.

`build_plan` populated the plan with `scores[:window_hours]` — the first 12 hours
from now. At 13:00 with a 24-hour window those run 13:00 → midnight, while the
best hour was **07:00 the next morning**. So the briefing said *"Go at 07:00"* and
every row of the table beside it read `WAIT` or `SKIP`. The table appeared to
contradict the advice it was meant to justify.

Nothing was wrong with the data, the scorer, or the headline. The bug was purely
one of slicing: "show the next N hours" and "show the hour we are recommending"
are not the same request, and the first was implemented where the second was
meant.

`display_window()` now anchors on the recommendation. If the best hour is already
inside the window, behaviour is unchanged; otherwise the window shifts to end just
after it, keeping lead-in context so the reader can see the hour is better rather
than take it on faith. `tests/test_score.py::TestDisplayWindow` asserts the
property for every position 0–23, that the cap holds, that no invented hours
appear, and — end to end through `build_plan` — that a plan never omits its own
recommendation.

### 12. A station reading 1,727 km away looked entirely plausible

With a WAQI token configured, a query for Bengaluru (`geo:12.9716;77.5946/`)
returned *Dr. Karni Singh Shooting Range, Delhi* at `28.499727, 77.267095` with a
perfectly reasonable AQI of 89 and a well-formed payload. Nothing about it looked
broken — no error field, no nulls, no missing coordinates. It would have put a
Delhi air-quality number on a Bengaluru screen, labelled as a local cross-check,
next to a park name.

`stations.py` now computes the haversine distance and discards anything beyond
`MAX_STATION_KM = 60`. The reading is also deleted rather than shown with a
caveat, because 60 km of "nearby" that turns out to be 1,727 km is not a caveat
anyone reads. The distance is included in the payload for the readings that
survive, so a judge can check the claim rather than take it.

60 km is deliberately generous: it covers the whole city plus a wide margin, so a
Bengaluru park with no station of its own still gets its cross-check. The guard
exists to catch a different city, not to demand a sensor in the park. Absent
coordinates are not a rejection — no distance check is possible, so the reading
stands.

`tests/test_stations.py` covers this with the real response shape, plus the
payload-shape bug found alongside it: WAQI returns `city` as an object for the
geo feed and as a list for some other feeds, and the original code only read the
object form, so the station name silently vanished on one of them.

### 14. The published model could not be the one the product used

The most consequential bug in this project, and it was invisible from the eval's
own side. The accuracy table was always internally consistent — the numbers were
real, measured on a real holdout. What was false was the claim that they
described the shipped pipeline.

**The eval and the app used different feature sets.** `scripts/run_eval.py`
declared its own 13 columns from the archive row shape:

```
naqi, pm25, pm10, temp_c, apparent_c, precip_mm, precip_prob,
humidity, wind_kmh, uv_index, is_day, hour, month
```

`baahar/features.py` independently defined 15 for the live path, substituting
derived encodings:

```
naqi, pm25, pm10, naqi_band_ordinal, temp_c, apparent_c, heat_index_flag,
precip_mm, precip_prob, humidity, wind_kmh, uv_index, is_day, hour_sin, hour_cos
```

So `run_eval.py` fitted a 13-column model, saved it to
`eval/artifacts/tabpfn_gono.pkl`, and `score_tabpfn` then handed it a 15-column
matrix. It raised `X has 13 features, but TabPFNClassifier is expecting 15`
*inside* `predict_proba`, `score_slots` caught it, and every hour silently fell
back to the heuristic. Meanwhile `baahar brief` printed a reassuring note about
the heuristic and nothing else. The 840 MB artifact sat in `eval/artifacts/`
looking authoritative.

Three separate things had to be true for this to be invisible, and each was
individually reasonable:

1. **The feature failure was silent.** It degraded to the documented policy,
   which is the correct behaviour for a missing model — and indistinguishable
   from a fitted one that failed. `score_tabpfn` now compares `n_features_in_`
   against `len(FEATURE_NAMES)` and raises a `ValueError` naming both counts and
   refusing to reorder. A mismatch is a contract violation, not something to pad
   around: the values would silently mean something else.
2. **`load_tabpfn_model()` only looked where `.env` pointed.** With
   `TABPFN_MODEL_PATH` unset it returned `None`, so `choose_scorer("auto")` never
   saw the artifact that `save_tabpfn_model` had written to
   `eval/artifacts/`. Both sides now name `DEFAULT_TABPFN_ARTIFACT`. "Writer and
   reader must agree on the path" is now a test.
3. **The eval redeclared the column list.** `FEATURE_COLUMNS` in `run_eval.py`
   was a second copy of a contract, which is how the two drifted. It now does
   `list(TABPFN_FEATURE_ORDER)` and a test asserts that line is still there.

**The eval was re-run after the fix** — the cited artifact is
`gono_20261006T151017+0530.json`, and every number in § A is unchanged
(0.8512 / 0.6040). The features were already equivalent in what they expressed;
`hour` + `month` and `hour_sin` + `hour_cos` carry the same information. So no
accuracy moved, which is the reassuring outcome — but it was a coincidence, not a
guarantee, and I could not have known that without re-running.

**Verified after the fix:** `baahar brief` reports `scorer=tabpfn`, every hour
carries the `tabpfn` tag, `degraded` is empty, and a NAQI-488 hour still returns
SKIP with the policy's reasons intact. The safety asymmetry is now exercised
against the real fitted model rather than a stub.

The lesson is narrow and worth stating: *an eval that measures a pipeline the
product does not run is a benchmark, not a result.* The numbers were never wrong.
The sentence "the app scores with the exact model this table reports" was.

A related fix fell out of it. `build_plan` defaults to `scorer="auto"`, so once a
fitted artifact existed the offline test suite started behaving differently on a
machine that had run the eval than in CI — same code, different decisions, and two
test failures that meant nothing. `tests/conftest.py` now pins
`TABPFN_MODEL_PATH` to a path that cannot exist, so the suite is deterministic
regardless of local state. The TabPFN tests ask for it explicitly.

### 15. The seasonal cue shipped as four lines of statistics

Not an eval bug, but it belongs here because it is the failure mode the whole
project is built against, caught by looking at a screenshot.

The first version of the species cue put the record count, the radius and the
source into the instruction itself:

> look for a Chocolate Pansy near Bengaluru — researchers have logged around a
> dozen within 5 km this month

The unit tests passed. Every honesty rule was satisfied: it did not promise a
sighting, it named the evidence, it stated the radius. But
`docs/media/03b-pocket-seasonal.png` showed it rendering **four lines tall** with a
footnote in the middle of a screen whose entire purpose is that you should be
looking at a tree. The information was honest and the screen was still wrong.

Fixing it meant splitting `SeasonalCue` into two fields — `text` for the
instruction, `evidence` for the provenance — and then encoding the design rule as
a test: the instruction must stay under 45 characters and must not contain a
digit or the string "km". A reviewer reading only the tests can now see the
constraint that a reviewer looking at a screenshot would otherwise have to notice.

Two more bugs in the same feature, both found by the tests rather than by reading
the code:

* The seasonal cues were **unreachable**. `alternate_cues()` truncated to the first
  two cues, and the pool put three hand-written cues first, so the shuffle button
  could never land on a species. The API now returns the whole remainder, and
  `scripts/ui_check.mjs` clicks the button until the seasonal cue is on screen and
  asserts it got there.
* The provenance line was **one global sentence**, so the number it showed did not
  necessarily belong to the species above it. It is now a per-cue mapping, keyed by
  cue text, because "around a dozen" is a different claim from "several".

The headless UI check now asserts the credit line is **absent** under a hand-written
cue and **present** under a data-backed one. Attributing a data source to a line
the author wrote by hand is the same error as overclaiming a sighting, just quieter.

---

# D · What was not measured

Stated so the gaps are visible rather than inferred.

| Not measured | Why |
|---|---|
| `severe` / `hazardous` band accuracy | Zero such hours in the holdout. Not testable with this split. This is the gap that matters most. |
| `poor` band accuracy | 3 examples. In this 28-feature run, gradient boosting caught 1 row (F1=0.4000) while other models scored 0.0; a 3-row denominator is not a stable signal. |
| Air-quality-driven SKIP safety | Every SKIP in the holdout was rain or heat. `skip_as_go_rate` does not test polluted-day safety. |
| Whether TabPFN beats gradient boosting | Measured across five seeds on the adopted 28 lag features: TabPFN leads gradient boosting in accuracy (0.8708 +/- 0.0023 vs 0.8567 +/- 0.0000). Gradient boosting's macro-F1 jumps to 0.6906 +/- 0.0000 due to a single correctly classified row in the n=3 poor class (see § A), while on the 3 well-supported bands the consensus ensemble leads TabPFN (0.8249 vs 0.8236), leads on 4-band macro-F1 (0.6349 +/- 0.0368 vs 0.6193 +/- 0.0020), and leads on moderate recall (0.6620 vs 0.5845). Paired significance testing shows top models are statistically indistinguishable in holdout accuracy (p=0.25). |
| TabPFN's behaviour on the bands that matter | `severe` / `hazardous` / `poor` are unvalidated for TabPFN too, for the same reason as every other model here. |
| Fine-tuned vs baseline briefings | Measured, at smoke scale and on a CPU. Tinker ran for real before its balance ran out (HTTP 402), which is what surfaced a dataset defect: 29 of 219 examples carried a label contradicting their own briefing text, because labels came from the band-only policy and text from the full policy, which disagree on 45% of the corpus. Fixed, with offline tests. The local re-run is limited to a subset so a CPU run does not make the machine unusable; `scripts/fine_tune_modal.py` runs it in full on a GPU. |
| Field test | Not performed. No human has walked with Baahar. Not fabricated. |
| Independent temporal validation | Five-seed variability on one holdout is now measured; variation across independent holdout periods is not. Feature selection used this same holdout. |
| Rubric discrimination | Scores run 8.92–10.00 across 72 briefings. The rubric catches a broken briefing and does almost nothing to rank good ones. |
| Voice output quality | **Not assessed.** The client is implemented and tested against fixtures. A live call with real credentials returns HTTP 402 `paid_plan_required`: free ElevenLabs accounts cannot call library voices over the API at all. The credentials are valid and the endpoint answers - the free plan is simply not permitted to. No audio was generated or assessed, and no plan was upgraded, because `AGENTS.md` forbids a card wall. See `docs/NEEDS_HUMAN.md` §4. |
| Whether a seasonal cue led to a sighting | The cue wording and its provenance are tested; whether it changed what anyone looked at is not measured, because no human has walked with the app. Same answer as the field test: unknown, and not guessed at. |
| Seasonal cue accuracy | No metric yet. There is no ground truth for "did this person see it", and inventing one from n=0 walks would be a number with no denominator. The tested properties are wording, radius anchoring, and suppression under unsafe conditions. The journal now records the sighting answer (`Entry.species_seen`) and reports a rate at three walks, with a small-denominator caveat. **n=0 so far** — the field test has not happened. |
| A deployed end-to-end latency figure | `/api/brief` with the Gemma writer is 51.7 s p50 / 115.2 s p95 (measured, 36 calls); the template writer is 3 ms / 6 ms. A *hosted* p95 is **SKIPPED** — nothing is deployed. |
| Whether any of this changed behaviour | Only a human can say whether a briefing got someone outside. That is the field test, and it has not happened. |
# Latest qualification status — 8 October 2026

Rare-air forecast experiment `forecast_risk_v1` is SUBMITTED after user authorization. It expands modelled archive dates, separates training/development/calibration/threshold selection from locked historical test periods, and compares weighted LightGBM plus a calibrated binary risk floor against matched baselines. Metrics are PENDING, not estimated. [Manifest](raw/forecast_risk_v1_manifest.json), [approach](../docs/NEXT_MODEL_APPROACH.md), and [progress](../docs/MODEL_QUALIFICATION_PROGRESS.md). Serving models are unchanged.

V16 is provisional, not deployed. Its perfect finite-contract results on reused benchmark splits do not establish independent generalization or universal injection resistance. The consumed 24-case regression improved from 6/24 to 21/24, but two current/future NAQI-band inconsistencies remain. See [qualification progress](../docs/MODEL_QUALIFICATION_PROGRESS.md) and [raw completion summary](raw/v16_completion_summary.json).

A new 48-case, explicitly AI-authored synthetic adapter-versus-template evaluation and four-window hosted rolling forecast diagnostic are SUBMITTED. No scores are claimed before fetching their artifacts. Their manifests are [briefing](raw/qualification_v16_fresh_manifest.json) and [forecast](raw/forecast_rolling_manifest.json). Neither is independently human-authored or a pristine natural-data holdout. Older results below retain their historical context; near-100% policy decision accuracy is not air-safety validation.

Update: rolling forecasts are now COMPLETED. Ensemble accuracy varies from 0.6403 in June to 0.9489 in August; it predicts below poor on 33/33 February and 87/124 April poor-or-worse target hours. August has zero poor-or-worse examples. This exposes rare-band and seasonal weaknesses; the historical headline score is not generalization across seasons. The fresh V16 briefing check completed at 46/48 raw contract passes versus 48/48 deterministic fallback passes. All six current-GO cases passed; 42 withheld-action cases were included. Two finite flags are scheduled-time formatting variants (“5 PM” / “5:00 PM” for 17:00); both outputs withhold walking, but the raw flags remain and the strict zero-flag gate was not met. No current/future NAQI mixing was observed in this sample. Both are synthetic, non-independent diagnostics; V16 remains unpromoted. See [all model/window and family metrics](raw/next_qualification_report.md), [raw briefing results](raw/qualification_v16_fresh_results.json), and [raw forecast results](raw/forecast_rolling_results.json).


### Rare-air v1 failure correction

The submitted rare-air experiment failed before fitting: calibration contained 0/348 poor-or-worse hours. Training support was 97/7,308; development 1/1,458; threshold selection 4/378. These are measured class-support counts, not performance metrics. No accuracy, recall, calibration score or improvement exists for this run. The earlier SUBMITTED/PENDING entry is historical, superseded by FAILED. See [failure summary](raw/forecast_risk_v1_completion_summary.json). No candidate was adopted.


### Rare-air v2 preregistered recovery

Status: SUBMITTED; first direct fetch pending. Performance metrics: PENDING. V2 adds 2023 training and support-aware chronological development/calibration allocation; the locked evaluation dates remain unchanged. See [manifest](raw/forecast_risk_v2_manifest.json) and [protocol](../docs/NEXT_MODEL_APPROACH.md). No performance improvement or model adoption is claimed.


### Rare-air forecast v2 completed

Status: COMPLETED. On February–April, weighted LightGBM had 0.7493 accuracy, 0.4346 macro-F1 and 152/205 poor-or-worse misses; the calibrated hybrid had 0.7418, 0.4526 and 109/205. On May–October, weighted LightGBM had 0.8188 accuracy, 0.4622 macro-F1 and 41/49 misses; the hybrid had 0.8181, 0.4786 and 35/49. False-alarm rates rose from 0.0114 to 0.0405 and 0.0014 to 0.0028, respectively. These are historical CAMS/ERA5 archive results, not station or safety evidence. See [full comparison](raw/forecast_risk_v2_completion_summary.md) and [machine-readable metrics](raw/forecast_risk_v2_completion_summary.json). No model was promoted.


### Persistence definition correction after v2

The historical `persistence` entry used current conservative NAQI against future instantaneous labels. Matching instantaneous persistence accuracy/macro-F1 is 0.4103/0.2208 for February–April and 0.4932/0.2816 for May–October. Poor+ misses are unchanged at 185/205 and 41/49; false alarms fall to 185 and 41. Source bytes and targets were verified without fitting; all original v2 metrics remain preserved under their original definitions. Training has zero severe/hazardous support, and all learned candidates underpredict all 27 severe evaluation hours. [Measured audit and provenance](raw/forecast_risk_v2_target_audit.json), [explanation](raw/forecast_risk_v2_target_audit.md).


### V3 coverage ablation submitted

Performance: PENDING. Fixed class-weighted and ordinary candidates compare 2023-only with expanded 2023–May 2025 training. Previously consumed 2026 windows provide diagnostics, not an independent test. Severe-hour support and episode counts are required. [Manifest](raw/forecast_risk_v3_manifest.json).


## V3 coverage ablation completed

Fixed configurations compare 2023-only training against January 2023–May 2025 training. The latter includes previously evaluated 2025 examples. The 2026 periods have informed prior research and are consumed temporal diagnostics, not independent holdouts.

| Period | Model | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ recall | Poor+ FAR | Severe+ misses/support | Severe+ recall | Severe+ FAR |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| diagnostic_pollution | historical_train_ordinary | 0.7366 | 0.4258 | 221/248 | 0.10887096774193548 | 0.004250797024442083 | 11/11 | 0.0 | 0.0 |
| diagnostic_pollution | historical_train_risk_weighted | 0.7423 | 0.4606 | 200/248 | 0.1935483870967742 | 0.009032943676939426 | 11/11 | 0.0 | 0.0 |
| diagnostic_pollution | expanded_train_ordinary | 0.7592 | 0.4653 | 174/248 | 0.29838709677419356 | 0.011689691817215728 | 11/11 | 0.0 | 0.0037753657385559227 |
| diagnostic_pollution | expanded_train_risk_weighted | 0.7638 | 0.4848 | 144/248 | 0.41935483870967744 | 0.020722635494155154 | 11/11 | 0.0 | 0.0033034450212364322 |
| diagnostic_pollution | expanded_ensemble | 0.7488 | 0.4837 | 155/248 | 0.375 | 0.015409139213602551 | 11/11 | 0.0 | 0.004719207173194903 |
| diagnostic_pollution | instantaneous_persistence | 0.3864 | 0.2113 | 231/248 | 0.06854838709677419 | 0.12274176408076515 | 11/11 | 0.0 | 0.005191127890514393 |
| diagnostic_pollution | conservative_persistence_diagnostic | 0.2812 | 0.1381 | 231/248 | 0.06854838709677419 | 0.15834218916046758 | 11/11 | 0.0 | 0.005191127890514393 |
| diagnostic_other_seasons | historical_train_ordinary | 0.8183 | 0.5075 | 19/23 | 0.17391304347826086 | 0.0016469942355201758 | 2/2 | 0.0 | 0.0 |
| diagnostic_other_seasons | historical_train_risk_weighted | 0.8151 | 0.5001 | 20/23 | 0.13043478260869565 | 0.002744990392533626 | 2/2 | 0.0 | 0.0 |
| diagnostic_other_seasons | expanded_train_ordinary | 0.8301 | 0.5612 | 13/23 | 0.43478260869565216 | 0.0038429865495470767 | 2/2 | 0.0 | 0.0 |
| diagnostic_other_seasons | expanded_train_risk_weighted | 0.8295 | 0.569 | 11/23 | 0.5217391304347826 | 0.004666483667307164 | 2/2 | 0.0 | 0.0 |
| diagnostic_other_seasons | expanded_ensemble | 0.8271 | 0.5683 | 12/23 | 0.4782608695652174 | 0.0041174855888004395 | 2/2 | 0.0 | 0.0 |
| diagnostic_other_seasons | instantaneous_persistence | 0.4506 | 0.2491 | 22/23 | 0.043478260869565216 | 0.0060389788635739775 | 2/2 | 0.0 | 0.0005458515283842794 |
| diagnostic_other_seasons | conservative_persistence_diagnostic | 0.3325 | 0.1959 | 22/23 | 0.043478260869565216 | 0.006587976942080703 | 2/2 | 0.0 | 0.0005458515283842794 |

Full measured class support, episode counts, precision and probability diagnostics: [completion report](raw/forecast_risk_v3_completion_summary.md), [raw results](raw/forecast_risk_v3_results.json). These are consumed modeled archive diagnostics with correlated hours and uncalibrated probabilities. No automatic adoption, human review, field test or measured billing is claimed.


### Measured v3 disposition

Matched weighted models improve from 0.7423 to 0.7638 accuracy and 0.4606 to 0.4848 macro-F1 on February–April 2026; poor-or-worse misses fall from 200/248 to 144/248, with false alarms increasing from 17 to 39. On May–September, accuracy improves from 0.8151 to 0.8295 and macro-F1 from 0.5001 to 0.5690; misses fall from 20/23 to 11/23, with false alarms increasing from 10 to 17. Poor+ Brier/ECE improve against the old weighted model on both windows, but in the later window ordinary expanded LightGBM has lower Brier/ECE than expanded weighted LightGBM. This is a tradeoff, not universal model superiority.

Expanded training contains 469 poor-or-worse hours in 115 episodes, including 27 severe hours in six episodes, using the descriptive six-hour gap rule. All candidates still predict below severe on all 11 severe hours in the pollution window and both severe hours in the later window. Hazardous training/evaluation support is zero; hazardous recall is unmeasured. Expanded weighted training now emits some severe predictions, but its seven pollution-window severe alerts are all false positives. Severe forecasting remains unresolved, so this candidate is research-only and not qualified for adoption. These are consumed modeled archive diagnostics; no human, field, medical or prospective claim follows.

The completed monitor is disabled. Offline pytest, nine focused forecast tests and Ruff passed. No serving artifact or model deployment changed; actual billed costs remain unmeasured.


## V4 completed and reviewed by three research agents

Six fixed candidates completed on Modal: weighted multiclass, median quantile and 90th-percentile quantile, each with 28 original versus 35 instantaneous-history columns. Both diagnostic baseline vectors reproduce v3 exactly; all source/row hashes match. Exact t+6 source checks passed on 32,826 rows, with zero rounded numeric-label disagreements in all periods. No archive refresh or weights download occurred.

Data agent: small mixed feature gains. Pollution classifier accuracy remains 0.7638, macro-F1 declines 0.4848 to 0.4772, poor+ misses stay 144/248, false alarms decline 39 to 34; severe false alarms increase 7 to 9. Other-season accuracy improves 0.8295 to 0.8306, poor+ misses improve 11 to 10/23 and false alarms stay 17; severe false alarms increase 0 to 1. Poor-episode any-hit declines 5 to 4/7 in the later window, despite one more caught hour. Hourly improvement is not broader episode coverage.

Architecture agent: quantile heads expose a tradeoff. Base-feature upper-quantile poor+ recall reaches 0.9073 and 0.9130 versus classifier 0.4194 and 0.5217. Accuracy falls from 0.7638 to 0.6638 and 0.8295 to 0.7474; false alarms rise 39 to 164 and 17 to 59. Its empirical coverage is only 0.7944 and 0.7447, below nominal 0.9. Augmented upper-quantile coverage is 0.8014 and 0.7480. None is a calibrated safety bound. Median MAE improves slightly with instantaneous history (18.21 to 18.00; 9.76 to 9.55), but median poor+ recall is lower than classification.

Safety agent: all six candidates miss all 13 severe hours in five episodes, all severe onsets. Development has 16 poor+ hours in seven episodes and zero severe hours; severe recall there is unmeasured. Training contains 27 severe hours in six episodes, with no hazardous examples. More modeling on these consumed windows does not provide independent severe-risk qualification.

Disposition: retain candidates as research evidence, with no automatic model adoption. All results are consumed CAMS/ERA5 modeled archive diagnostics, not station observations, prospective validation, human field evidence or medical safety. Actual billing is unmeasured. Severe modeling needs distinct severe development episodes and evidence beyond repeated diagnostic tuning. The full offline suite, eleven focused forecast tests and Ruff passed. The completed monitor is disabled.

[All six candidates and metrics](raw/forecast_risk_v4_completion_summary.md).

## Bounded forecast research follow-up

Consumed CAMS/ERA5 archive diagnostics; repeated research comparisons, not independent station or prospective validation.

| Round | Period | Candidate | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ false alarms | Poor+ recall | Severe+ misses/support | Episode any-hit |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| forecast_risk_v5 | development | incumbent | 0.8409 | 0.6552 | 14/16 | 9 | 0.125 | 0/0 | 2/7 |
| forecast_risk_v5 | development | challenger | 0.8470 | 0.6703 | 14/16 | 3 | 0.125 | 0/0 | 2/7 |
| forecast_risk_v5 | diagnostic_pollution | incumbent | 0.7638 | 0.4772 | 144/248 | 34 | 0.41935483870967744 | 11/11 | 34/49 |
| forecast_risk_v5 | diagnostic_pollution | challenger | 0.7596 | 0.4691 | 136/248 | 46 | 0.45161290322580644 | 11/11 | 33/49 |
| forecast_risk_v5 | diagnostic_other_seasons | incumbent | 0.8306 | 0.5696 | 10/23 | 17 | 0.5652173913043478 | 2/2 | 4/7 |
| forecast_risk_v5 | diagnostic_other_seasons | challenger | 0.8312 | 0.5435 | 12/23 | 21 | 0.4782608695652174 | 2/2 | 5/7 |
| forecast_risk_v6 | development | incumbent | 0.8409 | 0.6552 | 14/16 | 9 | 0.125 | 0/0 | 2/7 |
| forecast_risk_v6 | development | challenger | 0.8337 | 0.6729 | 5/16 | 60 | 0.6875 | 0/0 | 6/7 |
| forecast_risk_v6 | diagnostic_pollution | incumbent | 0.7638 | 0.4772 | 144/248 | 34 | 0.41935483870967744 | 11/11 | 34/49 |
| forecast_risk_v6 | diagnostic_pollution | challenger | 0.7592 | 0.5045 | 24/248 | 162 | 0.9032258064516129 | 11/11 | 49/49 |
| forecast_risk_v6 | diagnostic_other_seasons | incumbent | 0.8306 | 0.5696 | 10/23 | 17 | 0.5652173913043478 | 2/2 | 4/7 |
| forecast_risk_v6 | diagnostic_other_seasons | challenger | 0.8200 | 0.5262 | 3/23 | 63 | 0.8695652173913043 | 2/2 | 6/7 |

Completed rounds: 2; consecutive rounds without gated gain: 2. Stop reason: two_consecutive_no_gain.

V5 fitted paired classifiers on Modal. V6 evaluated the fixed poor-band floor using existing v4 classifier and quantile weights on Modal, with no refitting; this is one training round and one hosted architecture evaluation, not two training rounds. Exact incumbent and quantile prediction hashes reproduce v4. The reused bundle hash was observed at read time, not independently pinned before its original training.

Gas history improved some hourly metrics but degraded others and did not resolve severe misses. The fixed quantile floor trades fewer poor+ misses for more false alarms; it cannot raise a prediction to severe. No candidate is promoted. Development has zero severe support; training has only 27 severe hours across six descriptive episodes. Hazardous recall remains unmeasured. Full raw probabilities/reliability and predictions are preserved in the linked JSON artifacts. No human, field, medical or billed-cost evidence is claimed. This finite stopping rule does not establish maximum attainable performance.

Evidence: `eval/raw/forecast_risk_v5_results.json`, `eval/raw/forecast_risk_v6_results.json`, their `_gate_summary.json` files, and `eval/raw/forecast_next_completion_summary.json`. Three data, architecture and safety reviews are recorded for each round under `docs/FORECAST_V5_*_REVIEW.md` and `docs/FORECAST_V6_*_REVIEW.md`. Offline pytest and Ruff passed; eight focused checks cover causal features, rounded boundaries, episode regressions and the frozen stopping criteria.

Next research prerequisite: obtain distinct severe development episodes and a separately frozen future evaluation source, then test whether pollutant-specific forecasting generalizes. Repeating parameter changes on these same consumed windows cannot establish that. A larger transformer is not supported by the present evidence. Keep deterministic safety handling and current serving behavior.


## Deep pollutant sequence v1 measured completion

# Deep pollutant sequence study: measured results

All candidates were evaluated on identical phase-local 24-hour-context origins. Both 2026 periods are consumed modeled-archive diagnostics, not fresh holdouts. The reference is the new matched LightGBM model; old v4-v6 counts are not an identical subset.

Historical raw `severe` means official Very Poor (301–400); `hazardous` means official Severe (401+). This is an instantaneous concentration proxy, not averaging-compliant station AQI.

| Period | Model | n | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ recall | Poor+ precision | Poor+ FAR | Very Poor+ misses/support | Very Poor+ recall | Very Poor+ FAR | Severe misses/support |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| development | tcn_seed_0 | 1435 | 0.720557 | 0.527710 | 105/168 | 0.375000 | 0.887324 | 0.006314 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | tcn_seed_1 | 1435 | 0.726829 | 0.547261 | 79/168 | 0.529762 | 0.839623 | 0.013418 | 22/22 | 0.000000 | 0.002123 | 0/0 |
| development | tcn_seed_2 | 1435 | 0.739373 | 0.569031 | 65/168 | 0.613095 | 0.844262 | 0.014996 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | tcn_fixed_mean | 1435 | 0.738676 | 0.562208 | 75/168 | 0.553571 | 0.885714 | 0.009471 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | paired_lightgbm | 1435 | 0.743554 | 0.560935 | 79/168 | 0.529762 | 0.855769 | 0.011839 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | persistence | 1435 | 0.364460 | 0.257717 | 146/168 | 0.130952 | 0.130952 | 0.115233 | 22/22 | 0.000000 | 0.015570 | 0/0 |
| diagnostic_pollution | tcn_seed_0 | 2107 | 0.783579 | 0.462954 | 112/248 | 0.548387 | 0.719577 | 0.028510 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_1 | 2107 | 0.789274 | 0.518402 | 125/248 | 0.495968 | 0.793548 | 0.017214 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_2 | 2107 | 0.785002 | 0.480535 | 101/248 | 0.592742 | 0.765625 | 0.024207 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_fixed_mean | 2107 | 0.788799 | 0.486780 | 111/248 | 0.552419 | 0.769663 | 0.022055 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | paired_lightgbm | 2107 | 0.794495 | 0.506529 | 129/248 | 0.479839 | 0.815068 | 0.014524 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | persistence | 2107 | 0.385382 | 0.211169 | 231/248 | 0.068548 | 0.068548 | 0.124260 | 11/11 | 0.000000 | 0.005248 | 0/0 |
| diagnostic_other_seasons | tcn_seed_0 | 3643 | 0.851496 | 0.713231 | 12/16 | 0.250000 | 0.800000 | 0.000276 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_1 | 3643 | 0.846555 | 0.720355 | 9/16 | 0.437500 | 0.411765 | 0.002757 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_2 | 3643 | 0.849300 | 0.725629 | 11/16 | 0.312500 | 0.714286 | 0.000551 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_fixed_mean | 3643 | 0.854516 | 0.716318 | 12/16 | 0.250000 | 0.800000 | 0.000276 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | paired_lightgbm | 3643 | 0.839967 | 0.664454 | 13/16 | 0.187500 | 0.333333 | 0.001654 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | persistence | 3643 | 0.451551 | 0.299947 | 16/16 | 0.000000 | 0.000000 | 0.004411 | 0/0 | UNMEASURED | 0.000000 | 0/0 |


Full [measured report](raw/pollutant_sequence_v1_completion_summary.md) and [machine-readable metrics](raw/pollutant_sequence_v1_completion_summary.json). Research-only consumed modeled archive; no automatic adoption or measured billing.


## Deep pollutant sequence v2 measured completion

# Deep pollutant sequence study: measured results

All candidates were evaluated on identical phase-local 24-hour-context origins. Both 2026 periods are consumed modeled-archive diagnostics, not fresh holdouts. The primary reference is the frozen v1 three-seed concentration-average ensemble. Matched LightGBM remains a secondary comparator.

Historical raw `severe` means official Very Poor (301â€“400); `hazardous` means official Severe (401+). This is an instantaneous concentration proxy, not averaging-compliant station AQI.

| Period | Model | n | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ recall | Poor+ precision | Poor+ FAR | Very Poor+ misses/support | Very Poor+ recall | Very Poor+ FAR | Severe misses/support |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| development | tcn_seed_0 | 1435 | 0.703136 | 0.509053 | 109/168 | 0.351190 | 0.867647 | 0.007103 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | tcn_seed_1 | 1435 | 0.733101 | 0.549333 | 84/168 | 0.500000 | 0.857143 | 0.011050 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | tcn_seed_2 | 1435 | 0.723345 | 0.537784 | 92/168 | 0.452381 | 0.844444 | 0.011050 | 22/22 | 0.000000 | 0.002123 | 0/0 |
| development | tcn_fixed_mean | 1435 | 0.730314 | 0.539391 | 97/168 | 0.422619 | 0.922078 | 0.004736 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | paired_lightgbm | 1435 | 0.743554 | 0.560935 | 79/168 | 0.529762 | 0.855769 | 0.011839 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | persistence | 1435 | 0.364460 | 0.257717 | 146/168 | 0.130952 | 0.130952 | 0.115233 | 22/22 | 0.000000 | 0.015570 | 0/0 |
| development | v1_fixed_mean | 1435 | 0.738676 | 0.562208 | 75/168 | 0.553571 | 0.885714 | 0.009471 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_0 | 2107 | 0.780731 | 0.429600 | 135/248 | 0.455645 | 0.753333 | 0.019903 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_1 | 2107 | 0.789274 | 0.465070 | 119/248 | 0.520161 | 0.796296 | 0.017751 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_2 | 2107 | 0.778358 | 0.488864 | 132/248 | 0.467742 | 0.743590 | 0.021517 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_fixed_mean | 2107 | 0.783579 | 0.464440 | 133/248 | 0.463710 | 0.782313 | 0.017214 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | paired_lightgbm | 2107 | 0.794495 | 0.506529 | 129/248 | 0.479839 | 0.815068 | 0.014524 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | persistence | 2107 | 0.385382 | 0.211169 | 231/248 | 0.068548 | 0.068548 | 0.124260 | 11/11 | 0.000000 | 0.005248 | 0/0 |
| diagnostic_pollution | v1_fixed_mean | 2107 | 0.788799 | 0.486780 | 111/248 | 0.552419 | 0.769663 | 0.022055 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_0 | 3643 | 0.841340 | 0.717388 | 11/16 | 0.312500 | 0.714286 | 0.000551 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_1 | 3643 | 0.844085 | 0.697320 | 12/16 | 0.250000 | 0.571429 | 0.000827 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_2 | 3643 | 0.850673 | 0.617154 | 16/16 | 0.000000 | UNMEASURED | 0.000000 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_fixed_mean | 3643 | 0.849575 | 0.695079 | 13/16 | 0.187500 | 1.000000 | 0.000000 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | paired_lightgbm | 3643 | 0.839967 | 0.664454 | 13/16 | 0.187500 | 0.333333 | 0.001654 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | persistence | 3643 | 0.451551 | 0.299947 | 16/16 | 0.000000 | 0.000000 | 0.004411 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | v1_fixed_mean | 3643 | 0.854516 | 0.716318 | 12/16 | 0.250000 | 0.800000 | 0.000276 | 0/0 | UNMEASURED | 0.000000 | 0/0 |


Full [measured report](raw/pollutant_sequence_v2_completion_summary.md) and [machine-readable metrics](raw/pollutant_sequence_v2_completion_summary.json). Research-only consumed modeled archive; no automatic adoption or measured billing.


## V2 disposition and next weighting study

V2 completed in 335.298 seconds of remote run time (not billed cost). Its fixed ensemble failed the paired gate against v1: pollution Poor+ misses 133/248 versus 111/248, false alarms 32 versus 41; later misses 13/16 versus 12/16, false alarms zero versus one. Very Poor+ misses remain 11/11. All four v2 candidates failed the v1 comparison. Keep v1 as research incumbent; no adoption or deployment. V3 is being prepared with only training-origin risk weighting relative to v1 (SmoothL1, multiplier two on canonical Poor+ labels from training only). Completed secondary reviewers remain unavailable through provider quota/authentication/balance; root synthesis is disclosed.


## Deep pollutant sequence v3 measured completion

# Deep pollutant sequence study: measured results

All candidates were evaluated on identical phase-local 24-hour-context origins. Both 2026 periods are consumed modeled-archive diagnostics, not fresh holdouts. The primary reference is the frozen v1 three-seed concentration-average ensemble. Matched LightGBM remains a secondary comparator.

Historical raw `severe` means official Very Poor (301â€“400); `hazardous` means official Severe (401+). This is an instantaneous concentration proxy, not averaging-compliant station AQI.

| Period | Model | n | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ recall | Poor+ precision | Poor+ FAR | Very Poor+ misses/support | Very Poor+ recall | Very Poor+ FAR | Severe misses/support |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| development | tcn_seed_0 | 1435 | 0.730314 | 0.560950 | 94/168 | 0.440476 | 0.860465 | 0.009471 | 21/22 | 0.045455 | 0.000000 | 0/0 |
| development | tcn_seed_1 | 1435 | 0.739373 | 0.570759 | 58/168 | 0.654762 | 0.814815 | 0.019732 | 22/22 | 0.000000 | 0.001415 | 0/0 |
| development | tcn_seed_2 | 1435 | 0.735889 | 0.579122 | 61/168 | 0.636905 | 0.842520 | 0.015785 | 21/22 | 0.045455 | 0.002123 | 0/0 |
| development | tcn_fixed_mean | 1435 | 0.745645 | 0.576626 | 62/168 | 0.630952 | 0.876033 | 0.011839 | 22/22 | 0.000000 | 0.000708 | 0/0 |
| development | paired_lightgbm | 1435 | 0.743554 | 0.560935 | 79/168 | 0.529762 | 0.855769 | 0.011839 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | persistence | 1435 | 0.364460 | 0.257717 | 146/168 | 0.130952 | 0.130952 | 0.115233 | 22/22 | 0.000000 | 0.015570 | 0/0 |
| development | v1_fixed_mean | 1435 | 0.738676 | 0.562208 | 75/168 | 0.553571 | 0.885714 | 0.009471 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_0 | 2107 | 0.786901 | 0.480468 | 99/248 | 0.600806 | 0.726829 | 0.030124 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_1 | 2107 | 0.788799 | 0.523214 | 86/248 | 0.653226 | 0.757009 | 0.027972 | 11/11 | 0.000000 | 0.000477 | 0/0 |
| diagnostic_pollution | tcn_seed_2 | 2107 | 0.787375 | 0.516024 | 86/248 | 0.653226 | 0.733032 | 0.031737 | 10/11 | 0.090909 | 0.000477 | 0/0 |
| diagnostic_pollution | tcn_fixed_mean | 2107 | 0.791172 | 0.486293 | 88/248 | 0.645161 | 0.740741 | 0.030124 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | paired_lightgbm | 2107 | 0.794495 | 0.506529 | 129/248 | 0.479839 | 0.815068 | 0.014524 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | persistence | 2107 | 0.385382 | 0.211169 | 231/248 | 0.068548 | 0.068548 | 0.124260 | 11/11 | 0.000000 | 0.005248 | 0/0 |
| diagnostic_pollution | v1_fixed_mean | 2107 | 0.788799 | 0.486780 | 111/248 | 0.552419 | 0.769663 | 0.022055 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_0 | 3643 | 0.838869 | 0.743890 | 7/16 | 0.562500 | 0.529412 | 0.002206 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_1 | 3643 | 0.845183 | 0.721250 | 6/16 | 0.625000 | 0.333333 | 0.005514 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_2 | 3643 | 0.854516 | 0.760749 | 9/16 | 0.437500 | 0.777778 | 0.000551 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_fixed_mean | 3643 | 0.847928 | 0.789472 | 6/16 | 0.625000 | 0.769231 | 0.000827 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | paired_lightgbm | 3643 | 0.839967 | 0.664454 | 13/16 | 0.187500 | 0.333333 | 0.001654 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | persistence | 3643 | 0.451551 | 0.299947 | 16/16 | 0.000000 | 0.000000 | 0.004411 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | v1_fixed_mean | 3643 | 0.854516 | 0.716318 | 12/16 | 0.250000 | 0.800000 | 0.000276 | 0/0 | UNMEASURED | 0.000000 | 0/0 |


Full [measured report](raw/pollutant_sequence_v3_completion_summary.md) and [machine-readable metrics](raw/pollutant_sequence_v3_completion_summary.json). Research-only consumed modeled archive; no automatic adoption or measured billing.


## V3 completed: passed finite retrospective gate

V3 passed the preregistered research gate versus the frozen v1 ensemble on both consumed 2026 diagnostics. Pollution Poor+ misses fell 111/248→88/248 while false alarms rose 41→56; later misses fell 12/16→6/16 while false alarms rose 1→3. The fixed ensemble still missed all 11 pollution Very Poor+ hours; later Very Poor+ and official Severe recall remain unmeasured. The 296/19,663 training weighting-support check passed. [Full paired review and next-data requirements](POLLUTANT_SEQUENCE_V3_REVIEW.md).


## Deep pollutant sequence v4 measured completion

# Deep pollutant sequence study: measured results

All candidates were evaluated on identical phase-local 24-hour-context origins. Both 2026 periods are consumed modeled-archive diagnostics, not fresh holdouts. The primary reference is the frozen v3 three-seed concentration-average ensemble. Matched LightGBM remains a secondary comparator.

Historical raw `severe` means official Very Poor (301â€“400); `hazardous` means official Severe (401+). This is an instantaneous concentration proxy, not averaging-compliant station AQI.

| Period | Model | n | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ recall | Poor+ precision | Poor+ FAR | Very Poor+ misses/support | Very Poor+ recall | Very Poor+ FAR | Severe misses/support |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| development | tcn_seed_0 | 1435 | 0.698955 | 0.510189 | 100/168 | 0.404762 | 0.871795 | 0.007893 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | tcn_seed_1 | 1435 | 0.724739 | 0.629951 | 55/168 | 0.672619 | 0.856061 | 0.014996 | 16/22 | 0.272727 | 0.004246 | 0/0 |
| development | tcn_seed_2 | 1435 | 0.758188 | 0.660446 | 56/168 | 0.666667 | 0.811594 | 0.020521 | 15/22 | 0.318182 | 0.004246 | 0/0 |
| development | tcn_fixed_mean | 1435 | 0.737282 | 0.580140 | 68/168 | 0.595238 | 0.877193 | 0.011050 | 21/22 | 0.045455 | 0.001415 | 0/0 |
| development | paired_lightgbm | 1435 | 0.743554 | 0.560935 | 79/168 | 0.529762 | 0.855769 | 0.011839 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | persistence | 1435 | 0.364460 | 0.257717 | 146/168 | 0.130952 | 0.130952 | 0.115233 | 22/22 | 0.000000 | 0.015570 | 0/0 |
| development | v3_fixed_mean | 1435 | 0.745645 | 0.576626 | 62/168 | 0.630952 | 0.876033 | 0.011839 | 22/22 | 0.000000 | 0.000708 | 0/0 |
| diagnostic_pollution | tcn_seed_0 | 2107 | 0.789274 | 0.548512 | 116/248 | 0.532258 | 0.776471 | 0.020441 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_1 | 2107 | 0.794495 | 0.583828 | 77/248 | 0.689516 | 0.721519 | 0.035503 | 10/11 | 0.090909 | 0.000954 | 0/0 |
| diagnostic_pollution | tcn_seed_2 | 2107 | 0.795918 | 0.534362 | 76/248 | 0.693548 | 0.738197 | 0.032813 | 11/11 | 0.000000 | 0.002385 | 0/0 |
| diagnostic_pollution | tcn_fixed_mean | 2107 | 0.796393 | 0.548551 | 88/248 | 0.645161 | 0.761905 | 0.026896 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | paired_lightgbm | 2107 | 0.794495 | 0.506529 | 129/248 | 0.479839 | 0.815068 | 0.014524 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | persistence | 2107 | 0.385382 | 0.211169 | 231/248 | 0.068548 | 0.068548 | 0.124260 | 11/11 | 0.000000 | 0.005248 | 0/0 |
| diagnostic_pollution | v3_fixed_mean | 2107 | 0.791172 | 0.486293 | 88/248 | 0.645161 | 0.740741 | 0.030124 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_0 | 3643 | 0.850947 | 0.751999 | 10/16 | 0.375000 | 1.000000 | 0.000000 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_1 | 3643 | 0.842438 | 0.774007 | 4/16 | 0.750000 | 0.545455 | 0.002757 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_2 | 3643 | 0.861378 | 0.789140 | 5/16 | 0.687500 | 0.611111 | 0.001930 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_fixed_mean | 3643 | 0.857260 | 0.802230 | 6/16 | 0.625000 | 0.833333 | 0.000551 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | paired_lightgbm | 3643 | 0.839967 | 0.664454 | 13/16 | 0.187500 | 0.333333 | 0.001654 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | persistence | 3643 | 0.451551 | 0.299947 | 16/16 | 0.000000 | 0.000000 | 0.004411 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | v3_fixed_mean | 3643 | 0.847928 | 0.789472 | 6/16 | 0.625000 | 0.769231 | 0.000827 | 0/0 | UNMEASURED | 0.000000 | 0/0 |


Full [measured report](raw/pollutant_sequence_v4_completion_summary.md) and [machine-readable metrics](raw/pollutant_sequence_v4_completion_summary.json). Research-only consumed modeled archive; no automatic adoption or measured billing.

## Pollutant context support audit (not a model evaluation)

The read-only 24/48/72-hour support audit checked 32,826 canonical target index/band pairs with no missing timestamps or incomplete finite six-gas histories. Eligible row counts at 24/48/72 hours: train 19,663/19,639/19,615; development 1,435/1,411/1,387; pollution diagnostic 2,107/2,083/2,059; other-seasons diagnostic 3,643/3,619/3,595. Poor+ support was unchanged in train (296 hours, 86 episodes), development (168, 28), and pollution (248, 49). Other-seasons Poor+ support was 16/6 episodes at 24h and 13/5 at 48h and 72h. Train has five Very Poor+ hours in one episode and zero official Severe examples; official Severe recall is UNMEASURED. All evaluated time periods are consumed CAMS/ERA5 modeled archive. This audit measures eligibility, not forecast skill. Exact timestamp digests, manifest/result hashes, reviewer synthesis and the next-step decision are in [the support report](../docs/POLLUTANT_CONTEXT_SUPPORT_V1_REVIEW.md) and [raw result](raw/pollutant_context_support_v1_results.json). The three reviews did not establish predictive value from the additional older lags; no 48h model fit was started.

## Fixed older-history probe v1: measured development results

Modal call `fc-01M4FM73AHVNNJFY7F8SGSYD8Q`, app `ap-LOJY41QfJZesEwi80LRam5` completed once. Both fits used the exact same 19,639 train and 1,411 development origins; 21,050 canonical target pairs verified. Median imputation, input scaling and target scales fit only on training. There were 296 Poor+ weighted training origins. No 2026 diagnostic labels entered this study.

| Development period | Context | n | Normalized MAE | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ false alarms | Poor+ episode hits/support | Very Poor+ misses/support |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 24h | 1411 | 0.474160 | 0.759745 | 0.638596 | 64/168 | 23 | 21/28 | 18/22 |
| overall | 48h | 1411 | 0.471746 | 0.751240 | 0.626867 | 64/168 | 22 | 21/28 | 18/22 |
| 2025-04 | 24h | 673 | 0.532290 | 0.760773 | 0.490218 | 48/122 | 7 | 16/21 | 8/8 |
| 2025-04 | 48h | 673 | 0.532371 | 0.760773 | 0.485323 | 48/122 | 7 | 16/21 | 8/8 |
| 2025-05 | 24h | 738 | 0.421149 | 0.758808 | 0.637216 | 16/46 | 16 | 5/7 | 10/14 |
| 2025-05 | 48h | 738 | 0.416461 | 0.742547 | 0.629883 | 16/46 | 15 | 5/7 | 10/14 |

48h relative normalized MAE improvement: 0.509%. Predeclared exploratory context screen passed: **False**.

- overall_normalized_mae_gain_at_least_1pct: False
- neither_month_normalized_mae_worse: False
- poor_misses_not_worse: True
- poor_false_alarms_not_worse: True
- poor_episode_hits_not_worse: True
- very_poor_misses_not_worse: True
- very_poor_false_alarms_not_worse: False

Full raw results include six pollutant MAEs, recalls/precision/FAR, episode counts, monthly scores, negative pre-clipping predictions, train scales, actual and predicted development concentrations, and exact origin hashes. These are consumed CAMS/ERA5 modeled archive diagnostics, not independent station, prospective or medical qualification. Unsupported recall is UNMEASURED. A fixed linear probe cannot disprove nonlinear older-history value. No promotion, deployment or billed cost is claimed.


## Deep pollutant sequence v5 measured completion

# Deep pollutant sequence study: measured results

All candidates were evaluated on identical phase-local 24-hour-context origins. Both 2026 periods are consumed modeled-archive diagnostics, not fresh holdouts. The primary reference is the frozen v3 three-seed concentration-average ensemble. Matched LightGBM remains a secondary comparator.

Historical raw `severe` means official Very Poor (301-400); `hazardous` means official Severe (401+). This is an instantaneous concentration proxy, not averaging-compliant station AQI.

| Period | Model | n | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ recall | Poor+ precision | Poor+ FAR | Very Poor+ misses/support | Very Poor+ recall | Very Poor+ FAR | Severe misses/support |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| development | tcn_seed_0 | 1435 | 0.728223 | 0.558271 | 75/168 | 0.553571 | 0.894231 | 0.008682 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | tcn_seed_1 | 1435 | 0.753310 | 0.579183 | 63/168 | 0.625000 | 0.833333 | 0.016575 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | tcn_seed_2 | 1435 | 0.738676 | 0.563584 | 82/168 | 0.511905 | 0.924731 | 0.005525 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | tcn_fixed_mean | 1435 | 0.747038 | 0.573598 | 70/168 | 0.583333 | 0.899083 | 0.008682 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | paired_lightgbm | 1435 | 0.743554 | 0.560935 | 79/168 | 0.529762 | 0.855769 | 0.011839 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | persistence | 1435 | 0.364460 | 0.257717 | 146/168 | 0.130952 | 0.130952 | 0.115233 | 22/22 | 0.000000 | 0.015570 | 0/0 |
| development | v3_fixed_mean | 1435 | 0.745645 | 0.576626 | 62/168 | 0.630952 | 0.876033 | 0.011839 | 22/22 | 0.000000 | 0.000708 | 0/0 |
| diagnostic_pollution | tcn_seed_0 | 2107 | 0.795444 | 0.529715 | 90/248 | 0.637097 | 0.755981 | 0.027434 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_1 | 2107 | 0.789748 | 0.509684 | 86/248 | 0.653226 | 0.746544 | 0.029586 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_seed_2 | 2107 | 0.789274 | 0.489791 | 102/248 | 0.588710 | 0.772487 | 0.023131 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | tcn_fixed_mean | 2107 | 0.790698 | 0.482729 | 94/248 | 0.620968 | 0.766169 | 0.025282 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | paired_lightgbm | 2107 | 0.794495 | 0.506529 | 129/248 | 0.479839 | 0.815068 | 0.014524 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | persistence | 2107 | 0.385382 | 0.211169 | 231/248 | 0.068548 | 0.068548 | 0.124260 | 11/11 | 0.000000 | 0.005248 | 0/0 |
| diagnostic_pollution | v3_fixed_mean | 2107 | 0.791172 | 0.486293 | 88/248 | 0.645161 | 0.740741 | 0.030124 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_0 | 3643 | 0.852045 | 0.746901 | 9/16 | 0.437500 | 0.636364 | 0.001103 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_1 | 3643 | 0.845732 | 0.723817 | 9/16 | 0.437500 | 0.437500 | 0.002481 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_seed_2 | 3643 | 0.850398 | 0.706675 | 12/16 | 0.250000 | 0.800000 | 0.000276 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | tcn_fixed_mean | 3643 | 0.851222 | 0.741100 | 10/16 | 0.375000 | 0.750000 | 0.000551 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | paired_lightgbm | 3643 | 0.839967 | 0.664454 | 13/16 | 0.187500 | 0.333333 | 0.001654 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | persistence | 3643 | 0.451551 | 0.299947 | 16/16 | 0.000000 | 0.000000 | 0.004411 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | v3_fixed_mean | 3643 | 0.847928 | 0.789472 | 6/16 | 0.625000 | 0.769231 | 0.000827 | 0/0 | UNMEASURED | 0.000000 | 0/0 |


Full [measured report](raw/pollutant_sequence_v5_completion_summary.md) and [machine-readable metrics](raw/pollutant_sequence_v5_completion_summary.json). Research-only consumed modeled archive; no automatic adoption or measured billing.

Three read-only V5 result reviews found no data-pairing defect and recommended no further fit against this consumed archive. Saved development attribution found all 168 Poor+ hours ozone-controlled; V5 missed 70 versus V3's 62 and worsened ozone MAE from 21.86 to 22.88. Full [event and gas analysis](raw/pollutant_sequence_v5_error_analysis.md) and [review synthesis](../docs/POLLUTANT_SEQUENCE_V5_RESULT_REVIEWS.md) are preserved. The evidence gap is recurring, independent station-aligned extreme episodes; no global model maximum is claimed.


# Target-contract audit: measured results

Hosted read-only CPU call fc-01M4FQ5AR38P77DCWRDAZ9N2M3, app ap-EYjomUeIBrjTquMy5bYdOv. All 32,826 historical instantaneous targets verified. Complete-window decomposition identity error was zero in every phase.

| Phase | Paired origins | Hourly Poor+ / VP+ | Trailing Poor+ / VP+ | Conservative Poor+ / VP+ |
|---|---:|---:|---:|---:|
| train | 19663 | 296 / 5 | 74 / 0 | 344 / 5 |
| development | 1435 | 168 / 22 | 94 / 6 | 213 / 27 |
| diagnostic_pollution | 2107 | 248 / 11 | 113 / 0 | 317 / 11 |
| diagnostic_other_seasons | 3643 | 16 / 0 | 0 / 0 | 16 / 0 |

Official Severe support is zero under every target in every phase. Later complete-trailing Poor+ support is also zero: recall is UNMEASURED, not successful detection.

Period averaging changes the task and cannot be reported as an improvement in historical model accuracy. The conservative product approximation retains hourly spikes and additionally includes persistent elevated averages. Training on trailing means alone would remove the five training Very Poor hours and is not justified as a safety improvement.

Causal persistence trailing Poor+ recall/precision: train 0.6216/0.1581; development 0.6489/0.3631; pollution diagnostic 0.6549/0.3020; later recall UNMEASURED with 15 false alarms. These are a baseline on a different target, not neural results.

No station quality, pristine evaluation, prospective, medical, probability calibration or billed-cost claim. Saved neural h6 outputs cannot reconstruct full trajectories; further inference would require the existing hosted checkpoints.

The development-only fixed-linear comparison provides a distinct algorithm hypothesis. Keep its original hourly task and frozen V3 gate for comparability while independently qualifying station sources.


## Deep pollutant GPU linear v2 measured completion

# Fixed pollutant linear study: measured results

All candidates were evaluated on identical phase-local 24-hour-context origins. Both 2026 periods are consumed modeled-archive diagnostics, not fresh holdouts. The primary reference is the frozen v3 three-seed concentration-average ensemble. Matched LightGBM remains a secondary comparator.

Historical raw `severe` means official Very Poor (301-400); `hazardous` means official Severe (401+). This is an instantaneous concentration proxy, not averaging-compliant station AQI.

| Period | Model | n | Accuracy | Macro-F1 | Poor+ misses/support | Poor+ recall | Poor+ precision | Poor+ FAR | Very Poor+ misses/support | Very Poor+ recall | Very Poor+ FAR | Severe misses/support |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| development | ridge_fixed | 1435 | 0.763066 | 0.639753 | 64/168 | 0.619048 | 0.806202 | 0.019732 | 18/22 | 0.181818 | 0.001415 | 0/0 |
| development | v3_fixed_mean | 1435 | 0.745645 | 0.576626 | 62/168 | 0.630952 | 0.876033 | 0.011839 | 22/22 | 0.000000 | 0.000708 | 0/0 |
| development | paired_lightgbm | 1435 | 0.743554 | 0.560935 | 79/168 | 0.529762 | 0.855769 | 0.011839 | 22/22 | 0.000000 | 0.000000 | 0/0 |
| development | persistence | 1435 | 0.364460 | 0.257717 | 146/168 | 0.130952 | 0.130952 | 0.115233 | 22/22 | 0.000000 | 0.015570 | 0/0 |
| diagnostic_pollution | ridge_fixed | 2107 | 0.799241 | 0.498535 | 106/248 | 0.572581 | 0.820809 | 0.016676 | 11/11 | 0.000000 | 0.000477 | 0/0 |
| diagnostic_pollution | v3_fixed_mean | 2107 | 0.791172 | 0.486293 | 88/248 | 0.645161 | 0.740741 | 0.030124 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | paired_lightgbm | 2107 | 0.794495 | 0.506529 | 129/248 | 0.479839 | 0.815068 | 0.014524 | 11/11 | 0.000000 | 0.000000 | 0/0 |
| diagnostic_pollution | persistence | 2107 | 0.385382 | 0.211169 | 231/248 | 0.068548 | 0.068548 | 0.124260 | 11/11 | 0.000000 | 0.005248 | 0/0 |
| diagnostic_other_seasons | ridge_fixed | 3643 | 0.845732 | 0.707854 | 12/16 | 0.250000 | 0.800000 | 0.000276 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | v3_fixed_mean | 3643 | 0.847928 | 0.789472 | 6/16 | 0.625000 | 0.769231 | 0.000827 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | paired_lightgbm | 3643 | 0.839967 | 0.664454 | 13/16 | 0.187500 | 0.333333 | 0.001654 | 0/0 | UNMEASURED | 0.000000 | 0/0 |
| diagnostic_other_seasons | persistence | 3643 | 0.451551 | 0.299947 | 16/16 | 0.000000 | 0.000000 | 0.004411 | 0/0 | UNMEASURED | 0.000000 | 0/0 |


Full [measured report](raw/pollutant_linear_v2_gpu_completion_summary.md) and [machine-readable metrics](raw/pollutant_linear_v2_gpu_completion_summary.json). Research-only consumed modeled archive; no automatic adoption or measured billing.
