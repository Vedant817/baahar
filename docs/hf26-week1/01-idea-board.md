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
