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
