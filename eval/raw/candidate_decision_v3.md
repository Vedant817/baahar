# Briefing candidate decision

Run: `20261007T195439Z-1e4b8ff8`.

Status: **PROVISIONAL_PENDING_QUALITATIVE_REVIEW**.

Validation-selected candidate: `qwen3_4b`.

Validation only: zero raw safety errors, then greatest raw accepted fraction, then lowest median latency, then candidate name for a deterministic tie. Selected candidate only: test and stress each require zero raw safety errors, at least 95% raw acceptance and no raw acceptance regression against its own base. No holdout-driven reselection.

| Candidate | Phase | Split | Raw accepted | Raw safety failures | Guarded accepted | Fallbacks | Median seconds |
|---|---|---|---|---|---|---|---|
| qwen3_4b | base | val | 1/80 | 64/80 | 80/80 | 79/80 | 2.425 |
| qwen3_4b | base | test | 3/88 | 74/88 | 88/88 | 85/88 | 2.638 |
| qwen3_4b | base | stress | 0/64 | 61/64 | 64/64 | 64/64 | 2.478 |
| qwen3_4b | adapted | val | 80/80 | 0/80 | 80/80 | 0/80 | 4.978 |
| qwen3_4b | adapted | test | 88/88 | 0/88 | 88/88 | 0/88 | 5.150 |
| qwen3_4b | adapted | stress | 64/64 | 0/64 | 64/64 | 0/64 | 5.278 |
| qwen25_7b | base | val | 0/80 | 46/80 | 80/80 | 80/80 | 0.961 |
| qwen25_7b | base | test | 0/88 | 66/88 | 88/88 | 88/88 | 0.953 |
| qwen25_7b | base | stress | 0/64 | 55/64 | 64/64 | 64/64 | 0.967 |
| qwen25_7b | adapted | val | 78/80 | 2/80 | 80/80 | 2/80 | 3.457 |
| qwen25_7b | adapted | test | 83/88 | 5/88 | 88/88 | 5/88 | 3.548 |
| qwen25_7b | adapted | stress | 63/64 | 1/64 | 64/64 | 1/64 | 3.702 |

Qualitative review pending: True

- Contract checks are finite pattern checks, not comprehensive safety proof.
- Synthetic stress scenarios are not field observations.
- Single seed; no deployment was performed by this report.
- No qualitative quality score or billed cost is invented.
