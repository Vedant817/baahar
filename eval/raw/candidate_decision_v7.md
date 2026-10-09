# Briefing candidate decision

Run: `20261007T232243Z-333955e2`.

Status: **PROVISIONAL_PENDING_QUALITATIVE_REVIEW**.

Validation-selected candidate: `qwen3_4b`.

Validation only: zero raw safety errors, then greatest raw accepted fraction, then lowest median latency, then candidate name for a deterministic tie. Selected candidate only: test and stress each require zero raw safety errors, at least 95% raw acceptance and no raw acceptance regression against its own base. No holdout-driven reselection.

| Candidate | Phase | Split | Raw accepted | Raw safety failures | Guarded accepted | Fallbacks | Median seconds |
|---|---|---|---|---|---|---|---|
| qwen3_4b | base | val | 1/80 | 64/80 | 80/80 | 79/80 | 2.461 |
| qwen3_4b | base | test | 3/88 | 74/88 | 88/88 | 85/88 | 2.664 |
| qwen3_4b | base | stress | 0/64 | 61/64 | 64/64 | 64/64 | 2.491 |
| qwen3_4b | adapted | val | 80/80 | 0/80 | 80/80 | 0/80 | 5.067 |
| qwen3_4b | adapted | test | 88/88 | 0/88 | 88/88 | 0/88 | 5.217 |
| qwen3_4b | adapted | stress | 64/64 | 0/64 | 64/64 | 0/64 | 5.430 |
| qwen25_7b | base | val | 0/80 | 46/80 | 80/80 | 80/80 | 0.955 |
| qwen25_7b | base | test | 0/88 | 66/88 | 88/88 | 88/88 | 0.901 |
| qwen25_7b | base | stress | 0/64 | 55/64 | 64/64 | 64/64 | 0.969 |
| qwen25_7b | adapted | val | 77/80 | 3/80 | 80/80 | 3/80 | 3.499 |
| qwen25_7b | adapted | test | 82/88 | 6/88 | 88/88 | 6/88 | 3.571 |
| qwen25_7b | adapted | stress | 62/64 | 2/64 | 64/64 | 2/64 | 3.801 |

Qualitative review pending: True

- Contract checks are finite pattern checks, not comprehensive safety proof.
- Synthetic stress scenarios are not field observations.
- Single seed; no deployment was performed by this report.
- No qualitative quality score or billed cost is invented.
