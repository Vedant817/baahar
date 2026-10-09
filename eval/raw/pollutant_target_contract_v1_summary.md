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
