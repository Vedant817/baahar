# 06 — Sequenced Coding-Agent Prompts

Paste in order after Day-1 kickoff (or use master prompt instead). Each fence is one session.

---

## 1) Scaffold (if not done in Day-1)

````markdown
Scaffold Baahar: FastAPI app skeleton, CLI entrypoint `baahar`, MIT, README, .env.example, parks_blr.json (≥8 parks), AGENTS.md with HF26 constraints (no card, no huge disk, new repo, honest evals). Commit.
````

---

## 2) Core loop — weather, AQ, score, brief

````markdown
Implement Baahar core loop:
- Open-Meteo weather + air-quality clients
- Indian NAQI from PM2.5/PM10 (cite CPCB; don’t mislabel US AQI)
- Heuristic GO/WAIT/SKIP for next 12–24h
- Gemma (Google AI Studio / Gemini API) briefing ≤120 words: window, park pick from parks_blr.json, safety caveat, one sensory cue
- Endpoint POST/GET /brief and CLI `baahar brief`
- Fixtures + tests; graceful degrade if GEMINI_API_KEY missing (template brief)
Commit with tests green.
````

---

## 3) Eval harness

````markdown
Build eval harness per docs in the Touch Grass pack (07-eval-and-honest-benchmarks):
- data/eval/go_nogo_cases.csv or jsonl from historical features
- data/eval/briefing_cases.jsonl ≥30
- scripts/run_eval.py writes eval/RESULTS.md with raw metrics, confusion matrix, latency p50/p95
- Forbid invented numbers — if a key is missing, skip that section and mark SKIPPED with reason
Commit RESULTS even if partial.
````

---

## 4) TabPFN integration

````markdown
Add TabPFN go/no-go classifier:
- scripts/build_features.py from OpenCity Bengaluru AQI CSV subset (disk-small) + weather features if available
- Train/predict via tabpfn-client or Prior Labs API using TABPFN_TOKEN
- Compare heuristic vs TabPFN on holdout; log to eval/RESULTS.md
- If token missing: implement interface + offline stub; document NEEDS_HUMAN
No huge local model downloads. Commit.
````

---

## 5) Tinker fine-tune

````markdown
Tinker FT for Baahar briefings:
- Build FT jsonl (Indian parks, AQI language, ≤120 words, safety-first, anti-hallucination)
- Launch hosted Tinker fine-tune — do NOT download base weights to laptop
- Serve via Tinker API; A/B vs Gemma baseline on briefing rubric; raw table in eval/RESULTS.md
- If credits/API fail: docs/ADR-002-tinker-fallback.md and keep Gemma path
Commit dataset scripts + results.
````

---

## 6) Partner integrations — Render + ElevenLabs

````markdown
Optional partners:
1) ElevenLabs TTS for briefing audio when ELEVENLABS_API_KEY set; cache audio; Pocket Mode plays once
2) Deploy API+static Pocket Mode UI to Render using promo/free path; if card required, stop and document in NEEDS_HUMAN.md — do not hack around billing
Pocket Mode UI: near-black screen, huge “Put phone in pocket. Look up.”, 20-min timer, no feeds.
Commit. Record demo GIF if possible.
````

---

## 7) Field-test checklist prep

````markdown
Create docs/FIELD_TEST.md for Vedant’s Bengaluru park walk:
- Pre-walk: run Baahar once at home, screenshot score+brief
- During: Pocket Mode, 15–25 min, phone away
- After: 5 bullet honesty notes + up to 3 photos placeholders
- Safety: skip walk if SKIP / hazardous AQI/heat
Do not invent results. Commit checklist only.
````

---

## 8) post.md writer

````markdown
Write post.md as DEV Challenge submission draft for Baahar / Touch Grass:
- Hook, problem, what it does, why open innovation matters, architecture, evals with tables from RESULTS.md, field-test section stub, prize categories actually used, links
- Voice: first person, ambitious-honest, concrete, short paragraphs — Vedant will edit
- Include tags note: #devchallenge #hf26challenge
- No fake field results; no fake metrics
Also refresh README to match. Commit.
````

---

## 9) Submission checklist agent

````markdown
Audit repo against HF26 Week 1 rules:
- New project in window? Secrets safe? Partner categories honest?
- Deadline buffer: feature freeze; list remaining human steps (promos, outdoor, publish)
- Produce SUBMISSION_CHECKLIST.md with [ ] items and status
Fix any doc/code gaps you can without card/disk violations. Commit.
````
