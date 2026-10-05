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
