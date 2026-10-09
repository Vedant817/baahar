# Data evidence for the deeper forecast experiment

The read-only Modal audit completed before fitting. It reused the ten SHA-pinned v3 source fixtures and derived rows; it acquired no additional archive and returned only metadata. The frozen audit is [the manifest](../eval/raw/pollutant_sequence_support_manifest.json), and measured counts and dated episodes are in [the raw result](../eval/raw/pollutant_sequence_support_results.json). Call: `fc-01M4FFF4BPG72WCM00X7XTWTMA`; app: `ap-9ziDnyWUYtOMnqBAIrkxZb`.

## Fixed windows and eligibility

Dates were fixed in code before viewing these support counts. A sample requires every one of the six pollutant concentrations at each hourly timestamp from origin minus 23 hours through origin plus six hours, all finite and contained in the same phase. Future values are labels only. Context values end at the origin. Weather does not change eligibility: the implementation uses training-only weather imputation and masks. These phase-local boundaries change denominators compared with earlier experiments.

| Phase | Dates, end exclusive | Eligible origins | Very Poor or worse target hours | Positive episodes | CPCB Severe target hours |
|---|---|---:|---:|---:|---:|
| Training | 2023-01-01 to 2025-04-01 | 19,663 | 5 | 1 | 0 |
| Development | 2025-04-01 to 2025-06-01 | 1,435 | 22 | 5 | 0 |
| Consumed pollution diagnostic | 2026-02-01 to 2026-05-01 | 2,107 | 11 | 4 | 0 |
| Consumed later-season diagnostic | 2026-05-01 to 2026-10-01 | 3,643 | 0 | 0 | 0 |

Episodes group positive target timestamps separated by at most six hours. They describe correlated archive events, not independent station incidents. There were no missing gas values or missing source timestamps among phase-boundary eligible candidates. All 32,826 original derived rows passed exact timestamp-plus-six-hour reconstruction of canonical numeric NAQI and the preserved legacy category.

The single Very Poor training episode is March 8, 2025, noon through 16:00. Development episodes are April 17 and 24, May 1, 2 and 3, 2025. Pollution diagnostic episodes are March 6, April 10, 20 and 29, 2026. The recorded payload timezone is `Asia/Kolkata`, UTC offset 19,800 seconds; all six pollutant fields, including carbon monoxide, have source units micrograms per cubic metre. Actual per-fixture timezone and units are preserved in the raw metadata. Preserve the canonical NAQI converter's CO unit conversion rather than treating these source values as milligrams per cubic metre.

The earlier two May 1, 2026 Very Poor target hours disappear under this stricter phase-local 24-hour context requirement. Consequently **later-season Very Poor recall is undefined**, not zero or perfect. It remains useful for negative-case false alarms and common-class error. Comparisons must use this experiment's matched eligible samples; earlier table denominators cannot be copied.

## Category and source interpretation

Preserve historical machine artifacts: the repository's legacy raw `severe` label represents index 301–400, which CPCB names **Very Poor**. Legacy `hazardous` represents 401–500, named **Severe** by CPCB. No CPCB Severe support exists in these phases. Past claims about "13 severe hours" therefore referred to Very Poor, not CPCB Severe. See the [Indian Economic Service government NAQI explanation](https://ies.gov.in/arthapedia/concept/national-air-quality-index). The CPCB report URL timed out during this audit; do not imply that this audit successfully downloaded its PDF.

The historical driver audit found the thirteen previously consumed Very Poor target hours ozone-dominated, with reconstructed indices close to 301. The new support check verifies their numeric labels but does not establish station exposure. Hourly modeled concentration passed through instantaneous breakpoints remains a mathematical proxy: official averaging-period rules and station AQI availability requirements must not be silently inferred from it.

[Open-Meteo's official air quality documentation](https://open-meteo.com/en/docs/air-quality-api) identifies global CAMS at approximately 45 km and native three-hourly resolution, with archive availability from August 2022. An hourly returned sequence does not create independent hourly observations. Its provider/model attribution and license requirements must remain visible. No station API access, station validation, human review, or new 2022/October acquisition was performed.

## What deeper training can test

A sequence model can learn pollutant evolution from abundant continuous concentration targets despite sparse categorical threshold crossings. It can be compared with matched causal lag-feature baselines and persistence. It cannot create independent positive events: moving five development events into training would destroy their tuning role. Preserve the pre-fit split and report support before reporting recall. Parameter or epoch search uses development only; the consumed 2026 diagnostics remain retrospective checks, never pristine holdouts.

One Very Poor training episode and no CPCB Severe observations leave large uncertainty around extreme-event generalization. A successful development selection would justify an additional experiment, not deployment or an air-safety guarantee. Additional distinct source events and source-matched station or prospective checks are still needed for those stronger claims.

Reproduce metadata fetch with `uv run --group modal python scripts/audit_pollutant_sequence_support_modal.py --fetch`. The runner refuses a duplicate submission and preserves any completed raw result. Ruff passed on the audit script.
