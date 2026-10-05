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
