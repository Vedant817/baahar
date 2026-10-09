# Recorded pollutant-driver diagnostic

A read-only hosted CPU audit reconstructed the consumed v3 severe targets with
`baahar.naqi.compute_naqi`, using the exact recorded archive responses. It did
not fit a model, change recorded responses, or download archive files or weights.

## Measured results

| Cases | Severe hours | Dominant future pollutant |
|---|---:|---|
| Expanded training, January 2023–May 2025 | 27 | O3: 27 |
| February–April 2026 diagnostic | 11 | O3: 11 |
| May–September 2026 diagnostic | 2 | O3: 2 |

Among the 13 severe evaluation targets, current instantaneous NAQI is dominated
by ozone in ten cases and PM2.5 in three. Current recorded ozone concentrations
range from 28 to 159 micrograms per cubic metre. The future instantaneous indices
are narrowly between 301.2 and 301.9 under the repository's CPCB breakpoint
calculation. They represent crossings into the repository's severe band, rather
than evidence across the entire severe range.

The current 28-column matrix includes explicit PM2.5 and PM10 concentrations
and their selected histories, but excludes explicit ozone, NO2, SO2 and CO.
Instantaneous NAQI supplies the maximum pollutant subindex; this scalar hides
the other pollutant concentrations when they are not dominant. The audit
therefore provides a measured motivation to test explicit gas signals. It does
not establish that adding them improves forecasting or reveals the causal
origin of ozone episodes.

The all-four-gas feature comparison was proposed before this diagnostic.
Retain that declared comparison for the next iteration: original 28 columns
versus original columns plus current NO2/O3/SO2/CO and their timestamp-based
lag1/3/6 and difference1/3/6 columns. Do not select an ozone-only subset from
these consumed evaluation outcomes. Keep training/configuration and candidate
comparison fixed before fitting, and report both candidates regardless of the
result.

## Reproducibility and integrity

- Runner: [inspect_pollutant_drivers_modal.py](../scripts/inspect_pollutant_drivers_modal.py).
- [Diagnostic protocol and call manifest](../eval/raw/forecast_risk_v4_pollutant_drivers_manifest.json).
- [Small measured metadata](../eval/raw/forecast_risk_v4_pollutant_drivers_results.json), including all 13 current/future subindex vectors.
- Modal call: `fc-01M4ECY6GHASEEB4SKCS7Z1S9Y`.
- [Modal app](https://modal.com/apps/vedantmahajan271/main/ap-PyRAs1uQ0si2j03prifumD): `ap-PyRAs1uQ0si2j03prifumD`.
- All ten pinned v3 source fixture SHA-256 values and the derived row SHA-256 were verified before calculation. Targets were reconstructed at exactly `t+6h` and checked against the saved bands.
- Original fixtures and rows remain on `baahar-training` under `/forecast_risk_v3`; only 23,970 bytes of measured result metadata were saved locally.
- Ruff passed for the diagnostic runner. This audit is auxiliary explanatory work, not a training iteration.

```powershell
uv run --group modal python scripts/inspect_pollutant_drivers_modal.py --fetch
```

The runner preserves an existing saved result and refuses a duplicate launch
when its manifest exists.

## Limits

The 27 training severe hours comprise six previously measured episodes, and the
13 evaluation hours comprise five. These are correlated hours from already
consumed CAMS modeled air-quality archive responses; weather inputs in the
training experiments come from ERA5 reanalysis. This audit has no prospective,
station, independent human-review, field-test or medical-safety evidence.
Applying CPCB breakpoints to instantaneous hourly concentrations is the
declared research target, not an official averaged station NAQI observation.
The development period has no severe examples, so it cannot establish severe
forecast performance. Source hashes demonstrate byte integrity, not the
physical accuracy of the archive model. Billing was not measured.
