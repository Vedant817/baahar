# 07 — Eval & Honest Benchmarks (Baahar)

**Rule zero:** If you didn’t run it, you don’t publish a number. Partial results marked `SKIPPED` beat fake completeness.

---

## Domains under test

1. **Go / Wait / Skip** scoring (tabular + heuristic)
2. **Briefing quality** (LLM baseline vs Tinker FT)
3. **System reliability** (latency, failure behavior)
4. **Theme compliance** (Pocket Mode exists; screen time of happy path ≤ ~60s before pocket)

---

## A. Go / Wait / Skip

### Labels (define once in code + docs)

| Label | Meaning |
|---|---|
| GO | Safe enough for a typical healthy adult 20-min walk |
| WAIT | Better window within ≤6 hours |
| SKIP | Hazardous / heavy rain / extreme heat — stay in |

Use Indian NAQI bands + temperature + precipitation. Document exact thresholds in `score.py`.

### Dataset

- Build features from OpenCity Bengaluru station CSVs (subset) ± Open-Meteo historical if used.
- Columns example: `hour`, `pm25`, `pm10`, `naqi`, `temp_c`, `precip_mm`, `label`.
- Split: time-based holdout (e.g., last 20% of timeline) — **no random shuffle leakage**.

### Metrics (publish all)

- Accuracy, macro-F1
- Per-class precision/recall
- Confusion matrix
- **Critical safety metric:** `% of true SKIP predicted as GO` (must be low; call out if high)

### Bold honest tests

1. **Hazard day:** pick known high-PM rows → model must not say GO.
2. **Clean morning:** low PM + mild temp → GO or WAIT acceptable; SKIP is a bug.
3. **Monsoon hour:** high precip → not GO.
4. **API outage:** scorer falls back to heuristic or refuses with explicit error — never empty 200 with “looks fine.”

### Anti-slop

- No tuning thresholds on the holdout.
- Report n_train / n_test and station names.
- If TabPFN unavailable, publish heuristic-only and say so in prize category claims.

---

## B. Briefing quality (LLM)

### Cases

`data/eval/briefing_cases.jsonl` ≥30 rows:

```json
{"id":"blr-01","context":{"naqi":85,"temp_c":28,"precip_p":10,"park":"Cubbon Park","window":"06:30-07:00"},"must_include":["Cubbon","NAQI|AQI|air"],"must_not":["medical cure","guaranteed safe"]}
```

### Rubric (0–2 each; sum /10)

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Actionable time window | missing | vague | concrete |
| Place specificity | none | city only | named park |
| Safety caveat | absent | weak | clear NAQI/heat/rain |
| Length | >160 or <40 words | 40–160 but fluffy | ≤120 tight |
| Sensory outdoor cue | none | generic | concrete notice-this |

Blind scoring: shuffle baseline vs FT outputs; judge without model id; then reveal.

### Metrics

- Mean rubric ± std
- % violating length
- % missing safety caveat (**hard fail rate**)
- Latency p50/p95
- Approx token cost if available

### Bold honest tests

1. **SKIP context:** briefing must tell user to stay in — not “push through.”
2. **Hallucinated park:** park not in `parks_blr.json` → fail.
3. **US foliage bleed:** “fall colors in New England” on Bengaluru case → fail.
4. **Hinglish toggle (if implemented):** still must keep safety caveat.

---

## C. System / product

| Test | Pass |
|---|---|
| Cold `/brief` | Returns JSON with score + text in <8s p95 under normal net (record actual) |
| Missing GEMINI key | Template or clear error — no crash traceback to user |
| Pocket Mode | UI reaches pocket state without extra navigation rabbit hole |
| Screen budget | Happy path ≤3 interactions before Pocket Mode |
| Secrets | `git secrets` / grep: no API keys in tree |

---

## D. Field test (human) — qualitative but structured

Do **not** invent. After walk, score 1–5:

- Trust in GO/SKIP advice vs how the air/heat felt
- Briefing usefulness
- Pocket Mode compliance (did phone stay away?)
- Would use again tomorrow

Publish quotes + scores in `docs/FIELD_TEST.md` and post.

---

## RESULTS.md template

```markdown
# Baahar eval results

Run at: <IST timestamp>
Commit: <sha>
Keys present: Gemma Y/N | Tinker Y/N | TabPFN Y/N | ElevenLabs Y/N

## Go/No-Go
n_train=... n_test=...
accuracy=... macro_f1=...
skip_as_go_rate=...
confusion:
...

## Briefings
n=...
baseline_mean=... ft_mean=...
hard_fail_safety_baseline=... ft=...
latency_p50_ms=... p95_ms=...

## Failures worth reading
1. ...
```

---

## Claims allowed in DEV post

Only mirror RESULTS.md. Soft language (“promising”) OK; numeric lies are not.
