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
