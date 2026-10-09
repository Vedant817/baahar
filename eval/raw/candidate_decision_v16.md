# Briefing candidate decision

Run: `20261008T133038Z-eb8923e8`.

Status: **PROVISIONAL_PENDING_QUALITATIVE_REVIEW**.

Validation-selected candidate: `qwen3_4b`.

Validation only: zero raw safety errors, then greatest raw accepted fraction, then candidate name for a deterministic tie. Selected candidate only: test and stress each require zero raw safety errors, at least 95% raw acceptance and no raw acceptance regression against its own base. No holdout-driven reselection. Raw latency is reported as a diagnostic, not a selection input.

| Candidate | Phase | Split | Raw accepted | Raw safety failures | Guarded accepted | Fallbacks | Median seconds |
|---|---|---|---|---|---|---|---|
| qwen3_4b | base | val | 1/80 | 64/80 | 80/80 | 79/80 | 2.533 |
| qwen3_4b | base | test | 3/88 | 74/88 | 88/88 | 85/88 | 2.712 |
| qwen3_4b | base | stress | 0/64 | 59/64 | 64/64 | 64/64 | 2.606 |
| qwen3_4b | base | development | 1/32 | 30/32 | 32/32 | 31/32 | 2.541 |
| qwen3_4b | adapted | val | 80/80 | 0/80 | 80/80 | 0/80 | 4.993 |
| qwen3_4b | adapted | test | 88/88 | 0/88 | 88/88 | 0/88 | 5.134 |
| qwen3_4b | adapted | stress | 64/64 | 0/64 | 64/64 | 0/64 | 5.436 |
| qwen3_4b | adapted | development | 32/32 | 0/32 | 32/32 | 0/32 | 5.824 |

Holdout gate per candidate (diagnostics, not selection):

- qwen3_4b: PASS


Qualitative review pending: True

- Contract checks are finite pattern checks, not comprehensive safety proof.
- Synthetic stress scenarios are not field observations.
- Single seed; no deployment was performed by this report.
- No qualitative quality score or billed cost is invented.
