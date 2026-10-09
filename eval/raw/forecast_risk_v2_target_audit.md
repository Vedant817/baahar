# Forecast target audit and research recommendation

The delegated research agent recommended establishing the target contract and measuring a matching persistence baseline before further training. Source inspection confirmed that `build_dataset.py` labels future instantaneous NAQI, while the former persistence baseline used current effective (conservative) NAQI. The current conservative feature remains legitimate; persisting it answers a different question from persisting instantaneous NAQI.

The new no-fitting audit read recorded Modal-volume source responses and rows into memory without saving expanded data or weights locally. SHA256 checks matched the archived result provenance. Every selected future target label was reproduced with the canonical NAQI calculation, and conservative persistence predictions exactly matched the original v2 outputs. Current index rounding caused zero band disagreements in these evaluated cases. The original v2 raw results, selections, weights and source hashes remain preserved.

| Consumed period | Baseline definition | Accuracy | Macro-F1 | Poor+ misses/support | False alarms | False-alarm rate |
|---|---|---:|---:|---:|---:|---:|
| locked_pollution | instantaneous_persistence | 0.4103 | 0.2208 | 185/205 | 185 | 0.0961 |
| locked_pollution | conservative_persistence_diagnostic | 0.3042 | 0.1506 | 185/205 | 245 | 0.1273 |
| locked_other_seasons | instantaneous_persistence | 0.4932 | 0.2816 | 41/49 | 41 | 0.0094 |
| locked_other_seasons | conservative_persistence_diagnostic | 0.3862 | 0.2353 | 41/49 | 53 | 0.0122 |

The definitions disagree on 389/2,130 and 616/4,410 rows. Correcting the definition improves measured persistence accuracy and reduces false alarms, but does not reduce poor-or-worse misses on these periods. It changes the comparison, not any learned prediction. The full probability-style diagnostics are in [the audit JSON](forecast_risk_v2_target_audit.json); binary persistence decisions are not calibrated probabilities.

## Class coverage and next model work

Training has 116 poor hours and zero severe or hazardous hours. Evaluation contains 13 severe hours in February–April and 14 in May–October; all four learned candidates predict every severe hour below severe and emit no severe/hazardous predictions. Hazardous performance is unmeasured because these evaluation periods contain zero hazardous cases. A poor-or-worse binary floor can raise a prediction to poor but cannot learn a missing severe class. These are class-band defects, not proof of an unsafe live invitation.

The hybrid pollution-period Brier score worsens from 0.07020 for weighted LightGBM to 0.07602; in other seasons it improves slightly from 0.009746 to 0.009544. Increased risk recall does not establish uniformly improved probability quality.

Implemented: an explicit instantaneous t+6 target contract, a matching instantaneous persistence helper, a separately named conservative-persistence diagnostic for future rare-air runs, and reporting of evaluation classes absent from training. No existing target column or serving policy changed. The audit rejects missing source data, mismatched hashes, target-label mismatches and stale conservative baseline predictions.

Next modeling should use a separately preregistered coverage and target protocol, collect enough distinct pollution episodes for training/development/calibration, and report support at severe thresholds. A larger model alone cannot establish performance on unsupported classes. Already consumed periods may be used for diagnostics but cannot become new pristine holdouts. No further training was launched during this audit.

These remain historical CAMS/ERA5 modeled archive diagnostics with correlated hours and prior selected configurations. They are not station observations, human review, prospective evidence or medical safety qualification. Oracle recorded target weather used in earlier policy tables is not a deployment forecast.
