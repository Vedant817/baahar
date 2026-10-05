# HF26 Week 1 Touch Grass — Combined Pack (Vedant Mahajan)

Generated for Hacktoberfest 2026 Week 1. Prefer individual files for navigation; this file is a single downloadable dump of core docs.

---


<!-- ========== README.md ========== -->

# Hacktoberfest 2026 · Week 1 Touch Grass — Build Pack (Vedant Mahajan)

Complete, paste-ready agent pack for the [DEV Hacktoberfest Open-Source AI Challenge Week 1: Touch Grass](https://dev.to/challenges/hacktoberfest-week1-2026-10-05).

**Builder:** Vedant Mahajan  
**Recommended project:** **Baahar** — finds Bengaluru’s next safe outdoor hour (AQI + heat + rain), speaks a ~30s park briefing, then Pocket Mode so the screen dies while you walk.  
**Deadline:** **Oct 11, 2026 11:59 PM PDT** = **Oct 12, 2026 12:29 PM IST**  
**Winners:** week of Oct 12, 2026

---

## How to use this pack

1. Read [`00-challenge-brief.md`](./00-challenge-brief.md) — rules, partner YES/NO matrix, checklist.
2. Skim [`01-idea-board.md`](./01-idea-board.md) — 8 scored ideas; recommended + 2 runner-ups.
3. Lock the build with [`02-IDEA.md`](./02-IDEA.md) — full product/tech spec for **Baahar**.
4. Follow [`03-timeline-4p5-days.md`](./03-timeline-4p5-days.md) — continuous agent plan from now → submission buffer.
5. **Primary path (unattended):** paste [`04-agent-master-prompt.md`](./04-agent-master-prompt.md) into a long-running coding agent. Let it burn tokens until Definition of Done.
6. **Staged path:** start with [`05-day1-kickoff-prompt.md`](./05-day1-kickoff-prompt.md), then sequence prompts in [`06-coding-agent-prompts.md`](./06-coding-agent-prompts.md).
7. Keep evals honest with [`07-eval-and-honest-benchmarks.md`](./07-eval-and-honest-benchmarks.md).
8. Cite sources from [`08-sources.md`](./08-sources.md).
9. Combined dump: [`HF26_WEEK1_TOUCH_GRASS_PACK.md`](./HF26_WEEK1_TOUCH_GRASS_PACK.md).
10. Archive: `/workspace/hf26-week1-touch-grass.tar.gz`

### Human-only steps (agents must pause and ask)

- Outdoor field test in a Bengaluru park (Cubbon / Lalbagh / neighbourhood park)
- Claiming promo codes at [hacktoberfest.com/my/promos](https://hacktoberfest.com/my/promos)
- Putting secrets (API keys) into env / hosting dashboards
- Publishing the DEV post
- Optional: DevRelay session embed

Everything else should run unsupervised for ~4.5–5 continuous work days.

---

## Hard constraints (do not violate)

| Constraint | Rule |
|---|---|
| No credit card | Skip DigitalOcean and any paid signup that walls on a card. Prefer free tiers + HF26 promo codes. |
| Limited disk | No downloading/fine-tuning huge local weights (no ~55GB models). Fine-tune via **Tinker hosted**; serve FT via Tinker API. Gemma via **Google AI Studio** free tier when possible. |
| New project | New repo, built inside the challenge window. Not a continuation of Aaji’s Pill Clerk. |
| India outdoor | Prefer Bengaluru / Indian climate demos over US fall-foliage-only ideas. |
| Writing wins | DEV post quality is the heaviest judging criterion. Draft excellent; Vedant edits voice. |
| Screen = shortest part | Pocket Mode / voice / glance UI — then get outside. |

---

## Top partner categories to enter (recommended)

**Featured ($200):** Tinker · Gemma · TabPFN · Render  
**Partner ($100):** ElevenLabs (voice pocket briefing) · optional SerpApi / Sentry if genuine  

**Skip:** DigitalOcean (card), Arduino (no UNO Q assumed), MongoDB/Temporal unless ADR justifies free-tier only.

---

## Pack file index

| File | Purpose |
|---|---|
| `00-challenge-brief.md` | Rules, dates IST+PDT, judging, partner matrix, checklist |
| `01-idea-board.md` | ≥8 ideas scored; recommended + runners |
| `02-IDEA.md` | Full Baahar spec |
| `03-timeline-4p5-days.md` | Hour-level agent plan |
| `04-agent-master-prompt.md` | One mega-prompt for ~5-day unsupervised run |
| `05-day1-kickoff-prompt.md` | Phase-1-only shorter kickoff |
| `06-coding-agent-prompts.md` | Sequenced paste prompts |
| `07-eval-and-honest-benchmarks.md` | Real tests + anti-slop |
| `08-sources.md` | URLs used |
| `HF26_WEEK1_TOUCH_GRASS_PACK.md` | Concatenated core docs |

---

*Built for Hacktoberfest 2026 Week 1 · tags on submit: `#devchallenge` `#hf26challenge`*



<!-- ========== 00-challenge-brief.md ========== -->

# 00 — Challenge Brief (Week 1: Touch Grass)

**Official hub:** https://dev.to/challenges/hacktoberfest-week1-2026-10-05  
**Launch post:** https://dev.to/devteam/join-the-hacktoberfest-open-source-ai-challenge-week-1-touch-grass-2450-in-prizes-across-17-4pom  
**HF26 hub:** https://dev.to/challenges/hf26  
**Credits:** https://hacktoberfest.com/my/promos  

---

## Theme

**Touch Grass** — Build something with open-weight models / open-source AI that gets people **off the screen and into the world**.

Examples from organizers: hiking, gardening, birding, run clubs, fall foliage.  
Design bar: **the screen should be the shortest part of the experience.**  
Bonus: take it outside, use it, report how it went.

## Shared prompt (all HF26 weeks)

Build with open-source AI at the core:

- open-weight model, and/or
- open-source agent harness/framework, and/or
- local inference, or a mix

In the post, explain **why open innovation matters** for what you built (offline, privacy, fine-tune/swap, cost, etc.).

---

## Dates (verify both zones)

| Event | PDT | IST (Asia/Calcutta, UTC+5:30) |
|---|---|---|
| Contest start | Oct 5, 2026 | Oct 5 evening / Oct 6 early IST |
| **Submissions due** | **Oct 11, 2026 11:59 PM PDT** | **Oct 12, 2026 12:29 PM IST** |
| Winners announced | Week of Oct 12, 2026 | Same week IST |

> Always treat **11:59 PM PDT** as the authoritative cutoff. Buffer for publish/network: lock write-up by **Oct 12 ~10:00 AM IST**.

---

## Rules that matter for Vedant

- **New project only** — repo started and completed inside this window. Not PRs to existing projects. Not an old repo. Not a continuation of Aaji’s Pill Clerk.
- **One submission per challenge.** In running for overall + every partner category it qualifies for; **wins at most once** per challenge.
- **Teams ≤ 4.** List DEV handles if collaborating. One post per team.
- **18+.** English preferred for prize eligibility.
- AI tools allowed.
- Show work optionally via **DevRelay** agent session embed.
- Tags: `#devchallenge` `#hf26challenge` (template adds them).
- Credits/promos: Tinker, Render, Backboard, ElevenLabs at hacktoberfest.com/my/promos.

---

## Judging (Writing Quality is heaviest)

1. **Writing Quality** (heaviest) — clear, engaging; what / who / why open matters
2. **Relevance** — open AI core + gets people outside
3. **Creativity**
4. **Technical Execution**
5. **Partner Technology** (optional, if entering categories)

Prizes: Overall $250 + DEV++ + badge · Featured categories $200 · Partner categories $100 · Completion badge for valid submissions.

---

## Partner matrix for Vedant

Legend: **YES** = enter if used genuinely · **MAYBE** = only with ADR + free path · **NO** = skip for card/hardware/disk.

### Featured ($200)

| Category | Vedant | Why |
|---|---|---|
| **Tinker** | **YES** | Hosted fine-tune; no huge local download; already used on weekend challenge — reuse skill, new task/domain. Must show baseline vs FT improvement. |
| **Gemma** | **YES** | Google AI Studio / Gemini API free key path; open-weight core for briefings. |
| **TabPFN** | **YES** | Free Prior Labs client/API for tabular “go outside?” classification on AQI/weather CSVs — strong $200 niche, fewer entrants likely. |
| **Render** | **YES** | Promo/credit history; host demo API/front-end. Stop if card wall appears — document and fall back to local + public tunnel only if free. |
| **Arduino** | **NO** | Assume no UNO Q unless Vedant confirms. Don’t block on hardware. |
| **DigitalOcean** | **NO** | Credit card risk. Skip entirely. |

### Partner ($100)

| Category | Vedant | Why |
|---|---|---|
| **ElevenLabs** | **YES (priority)** | Promo credits; voice pocket briefing = theme fit (screen-off). |
| **SerpApi** | **MAYBE** | Live park hours / local outdoor tips if free trial works without card. |
| **Sentry** | **MAYBE** | Agent tracing screenshots for write-up if free tier OK. |
| **Backboard** | **MAYBE** | Promo exists; only if it meaningfully assists build story. |
| **Entire** | **MAYBE** | If DevRelay/Entire session sharing is used in post. |
| **GitHub Copilot** | **MAYBE** | If used for coding agent / Actions — note honestly. |
| **Mastra** | **MAYBE** | Only if open-model agent orchestration is real, not bolted on. |
| **MongoDB Atlas** | **MAYBE → lean NO** | Often card for Atlas; prefer SQLite/JSONL unless free no-card confirmed. |
| **Temporal** | **MAYBE** | Overkill for MVP; only if durable outdoor-check workflow is core. |
| **Tiger Data** | **MAYBE** | Only if pgvector genuinely needed; prefer lightweight store. |

---

## Credits to claim (human)

1. Open https://hacktoberfest.com/my/promos while logged in.
2. Claim: **Tinker**, **Render**, **Backboard**, **ElevenLabs**.
3. Store keys only in `.env` (gitignored). Never commit secrets.
4. Also create free keys as needed: Google AI Studio (Gemma), Prior Labs TabPFN, optional WAQI token (aqicn.org/data-platform/token/).

---

## Submission checklist

- [ ] New public GitHub repo created **after** Oct 5, 2026 start; first commit in window
- [ ] README: what it is, how to run, why open matters, demo GIF/video, field-test notes
- [ ] Working demo (hosted free/promo **or** clear local run + recorded outdoor video)
- [ ] Honest evals with **raw numbers** (baseline vs FT; tabular metrics)
- [ ] Outdoor field test notes (Bengaluru park) with photos/short video if possible
- [ ] DEV post from official template; tags `#devchallenge` `#hf26challenge`
- [ ] Prize Categories section lists only tech **actually used**
- [ ] Explain open innovation (fine-tune, swap, privacy, cost, offline pieces)
- [ ] Optional DevRelay session linked/embedded
- [ ] Published **before** Oct 11 11:59 PM PDT / Oct 12 12:29 PM IST
- [ ] One prize max awareness; don’t spam fake partner claims

---

## Anti-patterns (disqualify / lose)

- Fake benchmarks / invented API responses
- Huge local model downloads that fill the laptop
- Card-gated cloud you can’t finish
- US-foliage-only story that doesn’t work in Indian October (still monsoon-exit / heat / AQI season — lean into that)
- Thin write-up on a clever repo
- Reusing Aaji’s Pill Clerk as the submission



<!-- ========== 01-idea-board.md ========== -->

# 01 — Idea Board (Touch Grass · Vedant)

Scoring rubric (1–5 each). Higher = better for *this* builder.

| Axis | Meaning |
|---|---|
| Theme fit | Screen shortest; gets body outside |
| Open-AI core | Open-weight / open harness / local / FT is load-bearing |
| Buildability | Agents can ship MVP in ~5 days |
| No-card | Free / promo path only |
| No-huge-disk | No 10s-of-GB local weights |
| India outdoor demo | Works in Bengaluru / Indian climate Oct |
| Prize categories | Meaningful $200/$100 entries |
| Writing story | Personal, differentiated, field-testable |

---

## Idea 1 — **Baahar** (RECOMMENDED WINNER)

**One-liner:** Finds Bengaluru’s next safe outdoor hour (AQI + heat + rain), generates a ~30s park briefing (Gemma ± Tinker FT), optional voice, then **Pocket Mode** — phone goes dark while you walk Cubbon / Lalbagh / neighbourhood park.

| Axis | Score | Notes |
|---|---|---|
| Theme fit | 5 | Pocket Mode is the theme made literal |
| Open-AI core | 5 | Gemma + Tinker FT + TabPFN go/no-go |
| Buildability | 5 | API + CLI + simple web; agents strong here |
| No-card | 5 | Open-Meteo, AI Studio, TabPFN free, promos |
| No-huge-disk | 5 | Hosted FT + API inference |
| India outdoor demo | 5 | AQI/heat is *the* India outdoor story in Oct |
| Prize categories | 5 | Tinker, Gemma, TabPFN, Render, ElevenLabs |
| Writing story | 5 | “I left the house because the agent told me to” |

**Differentiation:** Not US foliage. Not generic chatbot. Not always-on AR. Screen deliberately dies. Indian NAQI bands + park list + Hinglish-capable briefing.

---

## Idea 2 — **BagaanWeek** (runner-up A)

Monsoon/heat-aware “what to plant / water / shade this week” for Indian balcony & terrace gardens (Bengaluru / Pune / Delhi heat waves). Gemma plans; TabPFN on historical weather features; Open-Meteo forecast.

| Axis | Score |
|---|---|
| Theme | 4 | Open-AI | 5 | Build | 4 | No-card | 5 | Disk | 5 | India | 5 | Prizes | 4 | Writing | 4 |

**Why not #1:** Slightly less “leave the house now” urgency; demo can stay on balcony (still outdoor) but Pocket Mode story is weaker than a walk.

---

## Idea 3 — **ChirpBaahar** (runner-up B)

Pre-walk bird briefing for Cubbon/Lalbagh from iNaturalist research-grade seasonal priors + Gemma narration; optional lightweight on-device *text* species checklist (not 55GB vision). Screen: 20s brief → pocket → look at birds.

| Axis | Score |
|---|---|
| Theme | 5 | Open-AI | 4 | Build | 3 | No-card | 5 | Disk | 4 | India | 5 | Prizes | 3 | Writing | 5 |

**Why not #1:** Bird ID accuracy bar is high; fake “ID from audio” is a honesty trap. Keep as stretch or runner-up if TabPFN+AQI path blocks.

---

## Idea 4 — **ElderStep**

Privacy-first morning walk coach for parents/grandparents: stretch script, heat/AQI gate, “text me when home” local reminder. Gemma safety copy; minimal cloud.

| Axis | Score |
|---|---|
| Theme | 5 | Open-AI | 4 | Build | 3 | No-card | 5 | Disk | 5 | India | 5 | Prizes | 3 | Writing | 5 |

**Risk:** Safety/liability copy must be careful; medical overclaim forbidden. Great story, more human review needed.

---

## Idea 5 — **RunSafe BLR**

Park-run / jogging route suggester: shade proxies, AQI window, OpenStreetMap park loops. Agent picks “go at 6:10 or wait until 18:40”.

| Axis | Score |
|---|---|
| Theme | 4 | Open-AI | 4 | Build | 3 | No-card | 4 | Disk | 5 | India | 5 | Prizes | 3 | Writing | 3 |

**Risk:** Routing quality vs time; overlaps Baahar — fold route tips into Baahar stretch instead of separate product.

---

## Idea 6 — **TrailJournal Offline**

Markdown trail journal that works offline; sync later; Gemma summarizes “what you noticed” from voice notes after the walk (screen after, not during).

| Axis | Score |
|---|---|
| Theme | 4 | Open-AI | 4 | Build | 4 | No-card | 5 | Disk | 5 | India | 3 | Prizes | 2 | Writing | 4 |

**Risk:** Weaker partner category hooks; less “AI at core of getting outside.”

---

## Idea 7 — **HeatGate**

Standalone “is it safe to walk a dog / kid / elder for 20 minutes?” classifier with Indian heat index + AQI. TabPFN-heavy.

| Axis | Score |
|---|---|
| Theme | 3 | Open-AI | 4 | Build | 5 | No-card | 5 | Disk | 5 | India | 5 | Prizes | 4 | Writing | 3 |

**Risk:** Feels like a widget, not an experience. Merge into Baahar’s go/no-go engine.

---

## Idea 8 — **FoliageFakeout → FestivalWalk**

US foliage idea remixed for India: “best evening walk for Navaratri lights / lake breeze / tree canopy” using SerpApi + weather. Fun but thinner open-AI core unless Gemma/Tinker carry narrative.

| Axis | Score |
|---|---|
| Theme | 3 | Open-AI | 3 | Build | 3 | No-card | 3 | Disk | 5 | India | 4 | Prizes | 2 | Writing | 3 |

**Skip as primary.**

---

## Decision

### Recommended: **Baahar**

**Rationale (one paragraph):** Maximizes theme (Pocket Mode), India demo (AQI + heat in Bengaluru October), open stack Vedant already knows (Tinker + Gemma) plus a high-leverage new featured category (TabPFN on real CSVs), all without card or huge disk. Outdoor field test is a single park walk. Writing story writes itself: “The open model told me to leave the laptop — and I did.”

### Runner-up A: **BagaanWeek** — if weather/AQI APIs flake or TabPFN onboarding blocks; still India-native outdoor.

### Runner-up B: **ChirpBaahar** — if the writer wants stronger nature-joy narrative; must stay honest (priors + briefing, not fake audio ID).

**Upgrade rule for agents:** Prefer Baahar. Switch to a runner-up only with a written ADR in `docs/ADR-001-idea-switch.md` explaining the blocker and how the runner-up still hits theme + open-AI + no-card/no-disk.



<!-- ========== 02-IDEA.md ========== -->

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



<!-- ========== 03-timeline-4p5-days.md ========== -->

# 03 — Timeline (~4.5 continuous agent days)

**Now (pack time):** ~Tue Oct 6, 2026 early morning IST  
**Hard deadline:** Oct 11, 2026 11:59 PM PDT = **Oct 12, 2026 12:29 PM IST**  
**Write-up lock target:** Oct 12, 2026 **10:00 AM IST**  
**Stop feature work:** Oct 11, 2026 **6:00 PM IST** (buffer for eval polish + post + deploy + human outdoor)

Agents: **keep working until Definition of Done** unless blocked on human-only steps. Do not idle. Parallelize research/build/eval/write.

---

## Phase map

| Phase | IST window (approx) | Hours | Goal |
|---|---|---|---|
| P0 Kickoff | Oct 6 02:30–06:00 | 3.5 | Repo, IDEA lock, env stubs, parks JSON |
| P1 Data + scorers | Oct 6 06:00–18:00 | 12 | Open-Meteo, NAQI map, TabPFN path, heuristics |
| P2 Briefing LLM | Oct 6 18:00 – Oct 7 06:00 | 12 | Gemma client, prompts, baseline eval set |
| P3 Tinker FT | Oct 7 06:00–20:00 | 14 | Dataset, FT job, serve API, A/B numbers |
| P4 Product UI | Oct 7 20:00 – Oct 8 08:00 | 12 | CLI + Pocket Mode web, voice optional |
| P5 Harden + deploy | Oct 8 08:00–22:00 | 14 | Tests, Render, failure modes, Sentry optional |
| P6 Eval lock | Oct 8 22:00 – Oct 9 12:00 | 14 | Full RESULTS.md, anti-slop review |
| P7 Write + polish | Oct 9 12:00 – Oct 10 18:00 | 30 | post.md excellence, README, demo GIF |
| P8 Human outdoor | Oct 10 evening *or* Oct 11 morning | 2–3 human | Field test — **agent prepares kit, waits** |
| P9 Integrate field | After field test → Oct 11 18:00 | 6–10 | Photos into post, final numbers |
| P10 Buffer + submit | Oct 11 18:00 – Oct 12 10:00 | 16 | Freeze features, Vedant edits/publishes |

> Hours overlap agent continuous work; human sleeps — agents continue on non-human tasks (evals, docs, FT monitoring, deploy retries).

---

## Phase details

### P0 — Kickoff (Do not skip)

- Create **new** GitHub repo `baahar` (private→public before submit OK).
- Copy constraints from this pack into `AGENTS.md`.
- Scaffold language stack (prefer Python 3.11+ FastAPI + simple HTML/HTMX or Vite SPA — agents pick one and ADR it).
- `.env.example`: `GEMINI_API_KEY`, `TINKER_*`, `TABPFN_TOKEN`, `ELEVENLABS_API_KEY`, `WAQI_TOKEN`, `RENDER_*`.
- `data/parks_blr.json` with ≥8 parks (Cubbon, Lalbagh, Bugle Rock, Bannerghatta NP day-visit note, neighbourhood placeholders).
- Commit: `chore: scaffold Baahar for HF26 week1`.

### P1 — Data + scorers

- Implement Open-Meteo weather + air-quality clients with timeouts/retries.
- Implement Indian NAQI from PM2.5/PM10 (cite CPCB breakpoints in code comments + README).
- Download **small** OpenCity CSV subset for one/two stations (disk-aware).
- Feature builder → train/eval split → TabPFN classify GO/WAIT/SKIP.
- Heuristic fallback (rules on NAQI + temp + precip) always available.
- Unit tests with recorded JSON fixtures (no live network required in CI).

### P2 — Briefing

- Prompt templates: safety-first, ≤120 words, park name, window, one sensory cue.
- Gemma generateContent path.
- Build `data/eval/briefing_cases.jsonl` ≥30 cases.
- Baseline scores logged.

### P3 — Tinker

- Build FT dataset from synthetic+curated briefings (Indian parks, AQI language, anti-hallucination).
- Launch Tinker job; **do not** download huge base weights locally.
- Serve FT via Tinker API; side-by-side eval vs baseline; write raw table to `eval/RESULTS.md`.
- If FT fails/credits missing: ADR + ship Gemma-only; still enter Gemma/TabPFN/Render.

### P4 — Pocket Mode product

- `/brief` API returns score + text + optional audio URL.
- UI: one screen → results → **Pocket Mode** (near-black, huge “pocket me”, timer).
- CLI: `baahar brief --city Bengaluru`.
- Optional ElevenLabs.

### P5 — Harden + deploy

- Render free/promo deploy; if card wall → document, ship local + recorded demo.
- Chaos: kill AQ API → sample path.
- README quickstart <5 minutes for judges.

### P6 — Eval lock

- Freeze metrics; no cherry-picking.
- Include failures and confidence intervals if possible.
- Anti-slop pass (see 07).

### P7 — Writing

- `post.md` full draft matching DEV template sections.
- Diagram (mermaid or PNG).
- Demo GIF (CLI + Pocket Mode).
- Prize category list.

### P8 — Outdoor (HUMAN)

Agent prepares:
- Checklist PDF/md
- Charged phone instructions
- What to capture

Human does the walk. Agent does not invent field results.

### P9–P10 — Integrate + submit buffer

- Merge field notes.
- Stop features at **Oct 11 6:00 PM IST**.
- Vedant voice edit + publish before **Oct 12 12:29 PM IST** (aim 10:00 AM IST).

---

## Stop / lock gates

| Gate | When (IST) | Rule |
|---|---|---|
| Idea lock | P0 end | Baahar unless ADR switch |
| Feature freeze | Oct 11 18:00 | Bugfixes + docs only |
| Write-up lock | Oct 12 10:00 | Content freeze for publish |
| Hard deadline | Oct 12 12:29 | DEV post live |

---

## Agent work ethic

- Continuous progress; batch commits with real messages.
- If blocked on keys: implement offline fixtures + leave `NEEDS_HUMAN.md`.
- Never stop solely because “waiting for inspiration.”
- Prefer shipping honest MVP over unfinished mega-features.



<!-- ========== 04-agent-master-prompt.md ========== -->

# 04 — Agent Master Prompt (paste-ready)

Copy **everything inside the fence** into a long-running coding agent. Let it work ~4.5–5 continuous days until Definition of Done. Human intervenes only for secrets, outdoor walk, promo claims, and DEV publish.

````markdown
# Baahar — HF26 Week 1 Touch Grass · End-to-End Build Order

You are a tireless senior multi-agent team building **Baahar** for Vedant Mahajan’s Hacktoberfest 2026 DEV Challenge Week 1 submission. You will burn tokens and keep working for approximately **4.5–5 continuous work days** until the Definition of Done is fully checked. Do not idle. Do not stop at “good enough sketches.” Ship a real, evaluable product and an excellent DEV post draft.

## Who you are (spawn personas internally)

Rotate and collaborate as needed:

1. **Staff engineer** — architecture, APIs, reliability, git hygiene  
2. **PM** — scope control, MVP vs stretch, deadline risk  
3. **Outdoor-domain reviewer (India)** — Bengaluru parks, heat, AQI, monsoon-exit Oct reality  
4. **Eval scientist** — metrics, anti-slop, raw numbers, failure analysis  
5. **DEV essayist** — contest-winning writing in Vedant’s ambitious-honest voice (he will edit)

## Challenge facts (authoritative)

- URL: https://dev.to/challenges/hacktoberfest-week1-2026-10-05
- Theme: **Touch Grass** — open-source AI that gets people off the screen into the world. Screen = shortest part.
- Prompt: open-weight model / open agent harness / local inference / mix; explain why open innovation matters.
- Window: started Oct 5, 2026; submissions due **Oct 11, 2026 11:59 PM PDT** = **Oct 12, 2026 12:29 PM IST**.
- Judging: Writing Quality (heaviest), Relevance, Creativity, Technical Execution, Partner tech optional.
- New project only; teams ≤4; one prize per submission max.
- Tags: #devchallenge #hf26challenge
- Credits: https://hacktoberfest.com/my/promos (Tinker, Render, Backboard, ElevenLabs)
- Optional: DevRelay agent session in post

## Hard constraints (NEVER violate)

- Vedant is new to software engineering but ambitious — make the repo approachable; automate everything.
- **NO CREDIT CARD.** Skip DigitalOcean and any signup that requires a card. Prefer free tiers + promo codes.
- **LIMITED DISK.** Do not download or fine-tune huge local models (no ~55GB weights). Fine-tune via **Tinker hosted**; serve FT via Tinker API. Gemma via **Google AI Studio** free API when possible.
- This must be a **NEW repo / NEW project** — not Aaji’s Pill Clerk, not a PR-only submission.
- Prefer **India / Bengaluru** outdoor demo (AQI, heat, parks) over US fall-foliage-only.
- Writing quality wins — `post.md` must be excellent.
- **Forbid fake benchmarks.** Every number in RESULTS.md must come from a real run. Save raw outputs.
- Do not invent APIs. If unsure, WebSearch/WebFetch and cite in `docs/SOURCES.md`.

## Product to build (default)

**Name:** Baahar (बाहर — outside)  
**One-liner:** Finds Bengaluru’s next safe outdoor hour (AQI + heat + rain), generates a ~30s park briefing with open AI, optional voice, then **Pocket Mode** so the phone goes dark while the human walks.

If blocked on a fundamental dependency, you may upgrade to runner-up **BagaanWeek** or **ChirpBaahar** from the idea board **only** after writing `docs/ADR-001-idea-switch.md` with the blocker and why the runner-up still hits theme + open-AI + no-card/no-disk. Prefer Baahar.

## Stack bias

- Gemma (AI Studio) for briefings → category Gemma  
- Tinker hosted FT for domain briefings with measured baseline improvement → category Tinker  
- TabPFN on historical Bengaluru AQI/weather features for GO/WAIT/SKIP → category TabPFN  
- Open-Meteo weather + air-quality (no key) + Indian NAQI mapping from PM concentrations  
- Optional WAQI free token for live stations  
- Optional ElevenLabs voice (promo)  
- Optional Render host (promo); abort cleanly if card wall  
- Skip DigitalOcean; skip Arduino unless human confirms UNO Q  
- Prefer SQLite/JSONL over MongoDB Atlas  
- Dual optional: small upstream PRs to open tools if relevant — **primary deliverable is the NEW project**

## Data sources (verified starting points — re-verify)

- Open-Meteo forecast + air quality APIs (attribute CC BY 4.0)
- OpenCity Bengaluru hourly AQI CSVs
- data.gov.in CPCB resource may be **stale** — verify timestamps; don’t claim live if stale
- WAQI token: aqicn.org/data-platform/token/
- iNaturalist API for stretch seasonal tips only
- Curate static Bengaluru parks JSON

Implement CPCB-style **Indian NAQI** from concentrations; do not label US AQI as Indian AQI.

## Execution plan

Follow pack timeline phases P0→P10. Work continuously. Parallelize. Commit often with proper conventional commits and a readable history.

### Git

- Create new repo `baahar` under Vedant’s GitHub when credentials allow; otherwise scaffold locally and prepare push instructions in `NEEDS_HUMAN.md`.
- Main branch protected by good taste: green README, tests, no secrets.
- Side-by-side history: scaffold → data → score → brief → FT → UI → eval → docs → post.

### When blocked on human-only steps

Write `NEEDS_HUMAN.md` with exact actions (claim promo, paste key into `.env`, do outdoor walk, publish DEV). Continue all other work (fixtures, docs, evals on cached data, UI polish).

### Secrets

`.env` gitignored. `.env.example` complete. Never print secret values.

## Definition of Done (all must be true)

- [ ] Public (or ready-to-public) **new** GitHub repo started in challenge window
- [ ] README: quickstart <5 min, architecture, why open matters, demo, field-test section
- [ ] Working `brief` flow: weather+AQ → score → briefing → Pocket Mode
- [ ] TabPFN path implemented + heuristic fallback; eval numbers for go/no-go
- [ ] Gemma briefing path works
- [ ] Tinker FT attempted; if success, **baseline vs FT table with raw metrics**; if fail, ADR + Gemma-only
- [ ] `eval/RESULTS.md` with honest numbers and at least one documented failure
- [ ] Offline/fixture mode when APIs fail
- [ ] No credit card used; no huge local model downloads
- [ ] `post.md` complete DEV draft (hook, build, open why, evals, field stub, prize categories)
- [ ] `docs/FIELD_TEST.md` checklist ready; filled after human walk (do not fabricate)
- [ ] License MIT; attribution for data sources
- [ ] Prize categories listed only for tech actually used
- [ ] Feature freeze respected near deadline; buffer for publish

## Eval anti-slop rules

- No vibes-only “it feels better.”
- Report sample sizes, splits, timestamps of runs.
- Include confusion matrix or equivalent for SKIP vs GO.
- Blind rubric for briefings when comparing models.
- If a test fails, say so and fix or narrow claims.

## Outdoor demo (human) — prepare, don’t fake

Prepare kit + script for Cubbon / Lalbagh / neighbourhood park. After human returns notes/photos, integrate into post. **Never invent field-test outcomes.**

## Deliverable tree (minimum)

Match IDEA.md layout: `src/baahar/*`, `data/`, `scripts/`, `eval/RESULTS.md`, `docs/`, `post.md`, tests, `.env.example`.

## Now

1. Confirm date/deadline math in README.  
2. Scaffold repo.  
3. Implement P0→P1 without waiting.  
4. Keep going until Definition of Done.  
5. When truly finished, summarize paths, how to run, remaining human steps, and first lines of `post.md` hook.

BEGIN.
````

## First 25 lines of the fenced prompt (for quick visual check)

```
# Baahar — HF26 Week 1 Touch Grass · End-to-End Build Order

You are a tireless senior multi-agent team building **Baahar** for Vedant Mahajan’s Hacktoberfest 2026 DEV Challenge Week 1 submission. You will burn tokens and keep working for approximately **4.5–5 continuous work days** until the Definition of Done is fully checked. Do not idle. Do not stop at “good enough sketches.” Ship a real, evaluable product and an excellent DEV post draft.

## Who you are (spawn personas internally)

Rotate and collaborate as needed:

1. **Staff engineer** — architecture, APIs, reliability, git hygiene  
2. **PM** — scope control, MVP vs stretch, deadline risk  
3. **Outdoor-domain reviewer (India)** — Bengaluru parks, heat, AQI, monsoon-exit Oct reality  
4. **Eval scientist** — metrics, anti-slop, raw numbers, failure analysis  
5. **DEV essayist** — contest-winning writing in Vedant’s ambitious-honest voice (he will edit)

## Challenge facts (authoritative)

- URL: https://dev.to/challenges/hacktoberfest-week1-2026-10-05
- Theme: **Touch Grass** — open-source AI that gets people off the screen into the world. Screen = shortest part.
- Prompt: open-weight model / open agent harness / local inference / mix; explain why open innovation matters.
- Window: started Oct 5, 2026; submissions due **Oct 11, 2026 11:59 PM PDT** = **Oct 12, 2026 12:29 PM IST**.
- Judging: Writing Quality (heaviest), Relevance, Creativity, Technical Execution, Partner tech optional.
- New project only; teams ≤4; one prize per submission max.
- Tags: #devchallenge #hf26challenge
```



<!-- ========== 05-day1-kickoff-prompt.md ========== -->

# 05 — Day-1 Kickoff Prompt (Phase 1 only)

Use this if you want a **staged** start instead of the full master prompt. Paste the fence into your coding agent for the first session only (~3–12 hours). Then continue with prompts in `06-coding-agent-prompts.md`.

````markdown
# Baahar · Phase 1 Kickoff only (HF26 Week 1 Touch Grass)

You are building the scaffold and data plane for **Baahar** — an open-source AI outdoor-window agent for Bengaluru (Hacktoberfest 2026 Week 1: Touch Grass).

## Scope for THIS session only (stop when done)

1. Create/init local project `baahar` (Python FastAPI preferred) with MIT license, README stub, `.gitignore`, `.env.example`.
2. Write `AGENTS.md` summarizing constraints: no credit card, no huge local models, new project, India outdoor, honest evals.
3. Add `data/parks_blr.json` with ≥8 Bengaluru parks (name, lat, lon, one-line vibe).
4. Implement `weather.py` + `air.py` against **Open-Meteo** (forecast + air-quality). Timeouts, retries, typed results.
5. Implement Indian **NAQI** mapping from PM2.5/PM10 concentrations; cite CPCB breakpoints in comments; never relabel US AQI as Indian AQI.
6. Save JSON fixtures from one live call (if network works) under `data/samples/` for offline tests.
7. Heuristic GO/WAIT/SKIP scorer on next 12 hours (rules on NAQI, temp, precip probability).
8. Unit tests for NAQI + heuristic using fixtures (no network in tests).
9. Commit with clean messages. List what’s next for Phase 2 (TabPFN + Gemma).

## Out of scope now

Tinker FT, ElevenLabs, Render deploy, DEV post prose, outdoor field test fabrication.

## Constraints

- No DigitalOcean / card walls.
- No downloading multi-GB model weights.
- Do not invent APIs — Open-Meteo docs only for weather/AQ this phase.

## Done criteria for Phase 1

- `pytest` (or equivalent) green offline
- `python -m baahar.score` (or CLI) prints a 12-hour GO/WAIT/SKIP table for Bengaluru using live or fixture data
- README “Phase 1” section explains how to run

BEGIN Phase 1.
````



<!-- ========== 06-coding-agent-prompts.md ========== -->

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



<!-- ========== 07-eval-and-honest-benchmarks.md ========== -->

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



<!-- ========== 08-sources.md ========== -->

# 08 — Sources

URLs consulted while building this pack (Oct 6, 2026 IST). Re-verify before relying on live API shapes.

## Challenge

- https://dev.to/challenges/hacktoberfest-week1-2026-10-05
- https://dev.to/devteam/join-the-hacktoberfest-open-source-ai-challenge-week-1-touch-grass-2450-in-prizes-across-17-4pom
- https://dev.to/challenges/hf26
- https://dev.to/devteam/hacktoberfest-2026-dev-challenges-five-challenges-one-prompt-a-new-theme-every-week-1e54
- https://hacktoberfest.com/my/promos
- Example community idea post: https://dev.to/devopsdaily/touch-grass-6-project-ideas-for-people-who-live-in-a-terminal-hacktoberfest-dev-challenge-week-1-1e7n
- Note: other Week 1 submissions (e.g. TrailEcho) exist — differentiate with India/AQI/Pocket Mode story

## Weather & air quality

- https://open-meteo.com/
- https://open-meteo.com/en/docs
- https://open-meteo.com/en/docs/air-quality-api
- https://open-meteo.com/en/pricing
- https://github.com/open-meteo/open-meteo
- https://aqicn.org/api/
- https://aqicn.org/data-platform/token/
- https://airquality.cpcb.gov.in/AQI_India/
- http://www.cpcb.gov.in/real-time-air-quality-data/
- https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69 (CPCB via data.gov.in — verify freshness)
- https://data.opencity.in/dataset/bengaluru-hourly-air-quality-reports
- https://medium.com/@atharva-again/cpcbs-aqi-api-everything-you-need-to-know-41f5eff85c5a (community write-up; not official)
- https://cpcb.nic.in/National-Air-Quality-Index/ (methodology reference — confirm live path)

## Biodiversity / parks priors

- https://www.inaturalist.org/api
- https://api.inaturalist.org/v1/
- https://www.inaturalist.org/pages/api+recommended+practices
- https://www.inaturalist.org/pages/api+reference
- https://github.com/ritwikraj16/bangalore-bird-sightings (prior art; do not plagiarize — differentiate)

## Partner / model docs

- Google AI Studio / Gemini API keys: https://ai.google.dev/gemini-api/docs/api-key
- Gemini billing/free notes: https://ai.google.dev/gemini-api/docs/billing
- TabPFN / Prior Labs: https://priorlabs.ai/pricing
- https://github.com/priorlabs/tabpfn-client
- https://docs.priorlabs.ai/quickstart
- Partner categories listed on challenge page (Render, TabPFN, Tinker, Arduino, DigitalOcean, Gemma, Backboard, ElevenLabs, Entire, Copilot, Mastra, MongoDB Atlas, Sentry, SerpApi, Temporal, Tiger Data)

## Time conversion note

- Oct 11, 2026 23:59 PDT (UTC−7) = Oct 12, 2026 06:59 UTC = Oct 12, 2026 12:29 IST (UTC+5:30)


