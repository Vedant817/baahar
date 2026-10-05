# 02 — IDEA.md · Baahar

> Hacktoberfest 2026 Week 1 · Touch Grass  
> Builder: Vedant Mahajan · New repo (not Aaji’s Pill Clerk)

---

## Name

**Baahar** (बाहर — “outside”)

## One-liner

Open-source AI that finds Bengaluru’s next safe outdoor hour (AQI + heat + rain), speaks a ~30-second park briefing, then forces **Pocket Mode** so the screen dies while you walk.

## Tagline options (pick one for README)

- “The screen is the shortest part of the walk.”
- “Your agent’s job is to get you off the agent.”
- “Touch grass. Literally. In Cubbon.”

---

## User story

**As** a Bengaluru builder who lives in terminals,  
**I want** a 20–40 second briefing that tells me *when* to go outside, *where* (nearby park), and *what to notice*,  
**so that** I actually leave the desk — without doomscrolling maps for 15 minutes.

### Happy path (MVP)

1. Open Baahar (CLI or tiny web UI).
2. Confirm city = Bengaluru (default) + optional neighbourhood.
3. Baahar fetches weather + air-quality signals (Open-Meteo; optional WAQI station).
4. TabPFN (or heuristic fallback) scores the next 12–24 hourly slots: **GO / WAIT / SKIP**.
5. Gemma (baseline) or Tinker-fine-tuned model writes a ≤120-word briefing: time window, park pick, heat/AQI caveat, one sensory “notice this” prompt.
6. Optional ElevenLabs: play audio.
7. **Pocket Mode:** UI goes near-black; big text “Phone in pocket. Look up.” Timer for walk length (default 20 min). No feeds.
8. After timer: 3-tap journal (“went / shortened / skipped”) for field notes → used in DEV post.

---

## Why open innovation matters (seed for DEV post)

- **Fine-tune & swap:** Tinker FT on Indian outdoor briefing style; swap Gemma variants without rewriting the product.
- **Cost:** Open-Meteo + AI Studio free path + HF26 promos — no card required to ship.
- **Honesty over closed magic:** Tabular go/no-go on public CSVs beats a black-box “wellness score.”
- **Privacy default:** Location can stay city-level; no continuous GPS tracking in MVP.
- **Screen ethics:** Open stack used to *reduce* screen time, not increase it.

---

## Open-model / partner stack

| Layer | Choice | Partner category | Card/disk |
|---|---|---|---|
| Briefing LLM | Gemma via Google AI Studio (Gemini API free key) | **Gemma** | Free key; no huge local weights |
| Domain FT | Tinker hosted fine-tune on briefing dataset; serve via Tinker API | **Tinker** | Hosted — laptop disk safe |
| Go/no-go tabular | TabPFN on features from historical Bengaluru AQI + weather | **TabPFN** | Free Prior Labs client/API |
| Weather | Open-Meteo Forecast API | — | No key, no card |
| Air quality forecast | Open-Meteo Air Quality (`pm2_5`, `pm10`, `us_aqi`, …) + **Indian NAQI mapping** from concentrations | — | No key |
| Live stations (optional) | WAQI free token for Bengaluru stations | — | Free token form |
| Historical CSVs | OpenCity Bengaluru hourly AQI station dumps | — | Download subset only |
| Voice (stretch→target) | ElevenLabs TTS for briefing | **ElevenLabs** | Promo credits |
| Hosting | Render web service / static+API | **Render** | Promo; abort if card wall |
| Observability (optional) | Sentry traces of agent/tool calls | Sentry | Free tier if no card |
| Live web (optional) | SerpApi for park hours / advisories | SerpApi | Only if free path works |
| Local store | SQLite or JSONL | — | Avoid Atlas card |

**Explicit skips:** DigitalOcean · Arduino UNO Q · huge local GGUF/HF downloads · MongoDB Atlas unless proven no-card.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Baahar CLI / minimal Web (Pocket Mode UI)              │
└───────────────┬─────────────────────────────────────────┘
                │
        ┌───────▼────────┐
        │  Orchestrator  │  (Python FastAPI or Node — pick one; agents choose)
        │  /brief /score │
        └───────┬────────┘
                │
     ┌──────────┼──────────────────────────┐
     ▼          ▼                          ▼
 Weather     AQ + NAQI map           TabPFN scorer
 Open-Meteo  Open-Meteo ± WAQI       (features CSV → GO/WAIT/SKIP)
     │          │                          │
     └──────────┴────────────┬─────────────┘
                             ▼
                    Briefing generator
                 Gemma baseline  vs  Tinker FT
                             │
                    optional ElevenLabs TTS
                             │
                       Pocket Mode
```

### Core modules (suggested repo layout)

```
baahar/
  README.md
  LICENSE (MIT recommended)
  pyproject.toml / package.json
  .env.example
  src/baahar/
    weather.py          # Open-Meteo forecast
    air.py              # Open-Meteo AQ + NAQI conversion
    stations.py         # optional WAQI
    features.py         # build tabular row(s) for TabPFN
    score.py            # TabPFN + heuristic fallback
    brief.py            # Gemma + Tinker FT clients
    pocket.py           # Pocket Mode copy/timer helpers
    parks.py            # curated Bengaluru parks list (static JSON)
  data/
    parks_blr.json
    samples/            # tiny feature CSVs for offline demo
    eval/               # labeled briefing + go/no-go cases
  scripts/
    build_features.py
    fine_tune_tinker.py
    run_eval.py
  eval/
    RESULTS.md          # raw numbers only — no vibes
  docs/
    ADR-*.md
    FIELD_TEST.md
  post.md               # DEV submission draft
```

---

## Data sources (do not invent APIs)

| Source | Use | Notes |
|---|---|---|
| https://open-meteo.com/ | Weather + air quality forecast | Free non-commercial; attribute CC BY 4.0 |
| https://air-quality-api.open-meteo.com/ | AQ endpoint | Global CAMS; map PM to **Indian NAQI** yourself |
| https://data.opencity.in/dataset/bengaluru-hourly-air-quality-reports | Historical station CSVs for TabPFN train/eval | Prefer a few stations, not entire city dump if disk tight |
| https://api.data.gov.in resource `3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69` | CPCB via data.gov.in | **May be stale** — verify `last_update`; do not claim live if stale |
| https://aqicn.org/api/ + token form | Optional live station AQI | Free token |
| https://api.inaturalist.org/v1/ | Stretch: seasonal “notice this bird/plant” priors | Rate-limit politely; research-grade filter |
| Curated static `parks_blr.json` | Cubbon, Lalbagh, neighbourhood parks | Hand-maintained; cite OSM where used |

**Indian NAQI:** Implement CPCB breakpoint mapping from pollutant concentrations (document formula + cite CPCB National Air Quality Index materials). Do **not** pretend Open-Meteo’s `us_aqi` *is* Indian AQI — convert or label clearly.

---

## MVP vs stretch

### MVP (must ship)

- [ ] New GitHub repo + MIT + README
- [ ] Open-Meteo weather + AQ fetch for Bengaluru lat/lon
- [ ] NAQI (or clearly labeled proxy) for next hours
- [ ] Heuristic scorer **and** TabPFN path (TabPFN may fall back if key missing — both must exist in code)
- [ ] Gemma briefing ≤120 words with go window + park + one sensory cue
- [ ] Pocket Mode UI/CLI state
- [ ] Eval harness with **real numbers** (see `07-eval-and-honest-benchmarks.md`)
- [ ] `post.md` draft excellent enough for Vedant to edit
- [ ] `.env.example` + no secrets in git

### Stretch (priority order)

1. Tinker FT with measured win over Gemma baseline (required for strong Tinker category — treat as **MVP+** if credits available)
2. ElevenLabs voice briefing
3. Render deploy
4. WAQI live station blend
5. iNaturalist “notice this” seasonal tip
6. Hinglish briefing toggle
7. After-walk 3-tap journal → markdown for DEV post
8. Sentry tracing screenshots
9. Dual optional: small PRs to upstream open tools (Open-Meteo examples, TabPFN cookbook) — **secondary** to new project

---

## Safety & honesty

- Not a medical device. Copy: “informational outdoor planning — not medical advice.”
- If AQI/heat is hazardous → **SKIP** with plain language; never pep-talk into bad air.
- No stalking GPS trails in MVP.
- No fake bird/plant ID confidence.
- No invented benchmark tables.
- Attribute Open-Meteo, OpenCity, CPCB methodology, iNaturalist if used.

---

## Eval plan (bold honest tests)

See full detail in `07-eval-and-honest-benchmarks.md`. Minimum:

1. **Go/no-go tabular:** holdout hours from historical CSV — accuracy / F1 for SKIP vs GO; publish confusion matrix.
2. **Briefing quality:** blinded rubric (clarity, safety caveat present, ≤120 words, actionable time, India-relevant) on N≥20 prompts — baseline Gemma vs Tinker FT.
3. **Latency:** p50/p95 for `/brief` end-to-end.
4. **Failure modes:** API down → graceful offline sample path; never silent empty brief.
5. **Field test:** one real Bengaluru walk; notes in `docs/FIELD_TEST.md`.

---

## Outdoor demo script (human)

1. Morning or evening (avoid peak heat). Check Baahar once at home.
2. If GO: play briefing (or read once), enable Pocket Mode, walk 15–25 min in Cubbon / Lalbagh / local park.
3. Phone stays pocketed except emergency.
4. After: 3 photos max (park, Pocket Mode screen, sky/trees) + 5 bullets: what matched, what was wrong (AQI feel vs number), would you trust it tomorrow.
5. Agents incorporate notes into `post.md` — Vedant edits voice.

---

## DEV post outline (writing quality = contest)

1. Hook — “I built an agent whose success metric is me leaving the house.”
2. Problem — Bengaluru builders, AQI + heat, map-app rabbit holes.
3. What Baahar does — 30s → pocket → walk.
4. Why open — Tinker FT, Gemma swap, TabPFN on public CSVs, no card.
5. How it works — architecture diagram + NAQI honesty.
6. Evals — **tables with raw numbers**, including failures.
7. Field test — photos + what surprised you.
8. Partner categories list (only real ones).
9. What’s next / license / try it.
10. Optional DevRelay embed.

Tone: first person, ambitious-but-honest newbie builder, concrete, short paragraphs, no corporate AI sludge.

---

## Prize categories to enter (if used)

- Overall Hacktoberfest Week 1
- Best Use of **Tinker**
- Best Use of **Gemma**
- Best Use of **TabPFN**
- Best Use of **Render** (if deployed)
- Best Use of **ElevenLabs** (if voice ships)

Optional only if genuine: SerpApi, Sentry, Entire/DevRelay, Copilot.

---

## Definition of Done (agents)

See master prompt checklist. Short form: repo public · MVP works · evals published with raw numbers · FT comparison if Tinker used · Pocket Mode real · `post.md` ready · field-test doc stub filled after human walk · no card · no huge downloads · secrets safe.
