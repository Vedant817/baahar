# Scenario drill — persona reports (verbatim)

This is a scenario drill (a simulation), not a field test. No agent walked
anywhere and no agent observed real weather. Run date: 2026-10-10. The software
was run offline with BAAHAR_OFFLINE=1 on Windows against the repo at commit
state 7426d74. The four personas were played by agents. The method and the
ranked findings live in docs/SCENARIO_DRILL.md. The verbatim persona reports
follow.

---

# Persona 1 — Priya, first-time user

## Commands run (1-line verdict each)
- `check` → env table: `offline mode on`, then a wall of `yes` key presence (`waqi yes`, `elevenlabs yes`) and `keys are never printed, only presence.` Did not answer my question.
- `brief --city Bengaluru --offline --model template` → `WAIT  Go at 06:00.`
- `score --offline --json` → `"overall": "GO"`, `"current_decision": "GO"`, `"headline": "Go at 06:00."`
- `parks --limit 3` → `Cubbon Park 0.6 km high` — actually useful.
- `journal --markdown` → printed a finished field test: `### The walk — 6 Oct 2026, 13:59 IST` … `Outcome: went`, `Reached for the phone: 3 times`, `Species cue: a Chocolate Pansy — did not see it`.

## Answers

**1.** The verdict read as "not now" — badge `WAIT`, body `WAIT. Hold off on the walk and recheck conditions.` — but the same line said `Go at 06:00.` and the table showed `GO` at 06:00 and 07:00. So I was told to skip tonight and walk at 6 tomorrow *morning*. My question was "after work today," and the 12-hour table runs 20:00→07:00; 17:00–19:59 simply isn't covered, and nothing says so.

**2.** `NAQI` (`Indian NAQI is 130, in the moderate band`), `heuristic scorer in use (TabPFN not installed (tabpfn); using the documented policy.)`, `not a replacement for the official CPCB advisory`, and `"naqi_basis": "cpcb_24h_breakpoints_applied_to_hourly_concentrations..."`. Broken English: `Forecast window 06:00.` used as a whole sentence, twice. Mislabelled: NAQI `106`/`105.5` called `Good air` while the app's own band for it is `moderate`.

**3.** Yes, twice. `score --json` has `"weather_source": "live"` and `"air_source": "live"` *inside* `best_slot`, while the top level says `"weather_source": "fixture"` and `degraded` lists `air quality from recorded fixture, not a live forecast`. Separately, the brief told me `Refresh conditions before walking.` while I had explicitly run `--offline`.

**4.** I got the idea from four plain strings in index.html — `Pocket the phone`, `Phone in pocket.`, `notice this`, `another thing to notice`, `20:00 / walk`. I never found how to *use* it: the CLI said `Pocket Mode — Not yet.` and FIELD_TEST.md says "Tap **Pocket the phone**" — a tap, in a web app nobody told me to launch.

**5.** Yes — offline runs with no key, `latency=3ms`. But in 5 minutes I'd hit `brief` saying WAIT while `score` says GO, jargon on screen one, and `journal --markdown` printing a walk that never happened. I'd stop trusting the numbers.

## Three problems, ranked
1. `journal --markdown` printed `Outcome: went` / `a Chocolate Pansy` from gitignored `data/journal.jsonl`. FIELD_TEST.md says `STATUS: NOT YET DONE.` One command apart, they contradict each other. A fresh clone is clean; this working copy and any demo on this machine prints a fake field test.
2. Two answers to "can I walk now": `WAIT  Go at 06:00.` vs `"current_decision": "GO"` — plus a `WAIT` badge beside a `Go at 06:00.` headline on the same screen.
3. Provenance contradiction in JSON (`live` inside `best_slot`, `fixture` at top level), with `Refresh conditions before walking.` shown in `--offline` mode.

## Better than expected
The park copy: `Canopy first. Old rain trees, a lot of shade, and the walking crowd that makes 6am feel safe. High early morning and Sunday evening; quietest weekdays 07:00-09:00.` That's the one output I'd actually act on.

---

# Persona 2 — Arjun, sceptical fact-checker

## Commands run (with the 1-line result each produced)
| Command | Result |
|---|---|
| `$env:BAAHAR_OFFLINE="1"; $env:GEMINI_API_KEY=""` | set |
| `uv run baahar brief --city Bengaluru --offline --model template` | top line `WAIT  Go at 06:00.` |
| `uv run baahar score --offline --json` | `"overall": "GO"`, `"current_decision": "GO"` |
| `uv run baahar score --offline` | `GO: Go at 06:00.` |
| `uv run baahar journal --outcome went … --note "drill entry, not a real walk"` | `recorded -> …\data\journal.jsonl` |
| `uv run baahar journal --markdown` | `2 walks recorded` |
| `Invoke-WebRequest http://127.0.0.1:8123/api/brief?offline=1&model=template` | `pocket.active: False` |
| `uv run ruff check .` | `All checks passed!` |

*Port 8000 was already bound by a stale server; used 8123. Killed after.*

## Answers

**1. Plain language when data is fake?** Yes, loudly, at the human-facing layer: `! weather from recorded fixture, not a live forecast`, `! air quality from recorded fixture, not a live forecast`, and `pocket.safety_note: "Recorded or unavailable data cannot authorize a walk now."` `plan.degraded[]` lists all three. That is the behaviour AGENTS.md demands and it delivered.

**2. NAQI vs US AQI?** Distinguished, and a careful reader would notice: `"naqi": 130.1`, `"us_aqi_reference": 77.0`, `"naqi_basis": "cpcb_24h_breakpoints_applied_to_hourly_concentrations+…"`, and the string `Indian NAQI computed with CPCB 2014 sub-index breakpoints applied to hourly concentrations`. A *casual* reader would not — the briefing says "Indian NAQI is 130" while the hour table beside it shows `106` at 20:00, because the briefing reads the 15:00 current slot and the table starts at 20:00. Same screen, two different numbers, no reconciliation.

**3. Overclaims.** `Briefing writer: template.` is honest. `(plan.overall, "GO")` with `headline: "Go at 06:00."` printed under a `WAIT` heading is muddled. Worst: `Weather and air quality: Open-Meteo (CC BY 4.0)` is emitted verbatim in offline mode, naming a source that was never contacted.

**4. Pocket Mode.** `pocket.active: false` with the fixture refusal — correct. But the same payload says `best_slot.weather_source: "live"` and `best_slot.air_source: "live"` while top-level says `"fixture"`, and `plan.overall`/`current_decision` both `"GO"`. `walk.py:21` gates on `plan.air_source is not DataSource.LIVE`, but a per-slot consumer reading the nested `"live"` would conclude the walk is authorised. The payload contradicts its own gate.

**5. Before trusting GO/WAIT/SKIP:** that the recommendation is 15 h out, not now; that `dominant_pollutant` is `"o3"` throughout; that `scorer_note` says `using the documented policy` — i.e. a hand-written rule, not the measured model; and that `naqi_trailing_hours: 8` breakpoints are applied to 8-hour means, not CPCB's 24-hour averages.

## Three concrete problems, ranked
1. **`best_slot.weather_source` / `air_source` = `"live"` inside a `"fixture"` plan** (`baahar score --offline --json`). The nested slot objects carry the enum default rather than `wsrc`/`asrc`. `"live"` is precisely the value the eligibility gate trusts.
2. **`weather_source: "live"` on `current_slot` too** — the current hour is labelled live, and `current_decision: "GO"`. Any integration reading the slot rather than the plan is wrong in the unsafe direction.
3. **`--markdown` reports `2 walks recorded`** for entries whose note is `"drill entry, not a real walk"` and `"tried to force a pocket walk, drill only"`. A drill is being counted as field data.

## One place honesty beat expectations
`eval/RESULTS.md` § A "Safety limits and metric falsification" states the always-good catastrophic model reaches `decision acc 0.9982` — higher than the tuned ensemble — and that `skip_as_go_rate = 0.0` with **all 24 SKIP hours weather-driven, zero air quality**. § D then lists `Field test | Not performed. No human has walked with Baahar. Not fabricated.` That is the exact admission I came to find, unprompted, in the results file rather than buried in a commit message.

---

# Persona 3 — Meera, bad-air day

## Commands run
- `uv run baahar brief --city Bengaluru --offline --model template` → printed `WAIT  Go at 06:00.`
- `uv run baahar score --offline --json` → `overall=GO`, `current_decision=GO` at NAQI 130.1 Moderate.
- `uv run baahar serve --port 8000` → bind failed, port already in use (server not mine; left running). The existing server answered every request below; no real browser click was possible, so deep-link behavior was read from `app.js`.
- `Invoke-WebRequest "http://127.0.0.1:8000/api/brief?offline=1&model=template"` → `pocket.active=False`, `headline=Not yet.`, `safety_note=Recorded or unavailable data cannot authorize a walk now.`
- Same URL with `#pocket`, `?journal=1`, `?auto=1&model=template` → byte-identical refusal each time; nothing armed.
- `app.js` read: `enterPocket`, the button handler, and `scheduleAutoPocket` all bail on `state.pocketActive`; button `disabled`, reason rendered in `#pocket-blocked`.
- `uv run baahar journal --outcome went --phone 0 --note "tried to force a pocket walk, drill only"` → recorded; `--markdown --all` shows `Baahar said: —`.

## Answers
1. In its own words: "WAIT. Hold off on the walk and recheck conditions. Indian NAQI is 130, in the moderate band. It feels like 29 C." The JSON carries "Breathing discomfort for people with lung, asthma or heart conditions." — but the printed briefing never says it. Pocket Mode said "Not yet." and pointed to an hour: "Go at 06:00."
2. None succeeded. The API returned `pocket.active=False` for the plain URL and all three deep-link variants; `app.js` refuses again at three layers (disabled button, `if (!state.pocketActive) return` in the handler, `enterPocket`, `scheduleAutoPocket`). The refusal was a stated decision, not a dead button — the reason sat under it: "Not yet. — Recorded or unavailable data cannot authorize a walk now."
3. No preaching, no shaming. "Hold off on the walk and recheck conditions." is dry; the softest line is the cue "Listen for the first two birds, then ignore the traffic."
4. Yes — a later hour, not a shorter walk: "Go at 06:00." (NAQI 66), with the honest basis "NAQI 66, from the last 8 h of air, not just this hour" — an 8-hour average, not one lucky hour, which is the right thing to show an asthmatic. Helpful, though nothing about today indoors.
5. Trust more. The no was visible, reasoned, unbypassable, and gave a concrete hour, so I'd wait till 06:00. Nags: `score --json` says GO for the hour `brief` calls WAIT, and the journal accepted "went" on a blocked day.

## Problems, ranked
1. `"current_decision": "GO"` from `score --offline --json` vs `WAIT` from `brief`, same fixture, NAQI 130.1 Moderate — one command reads as a green light to walk now.
2. The only reason under the disabled button is "Recorded or unavailable data cannot authorize a walk now." — data freshness, not lungs; the asthma line never reaches the printed briefing.
3. `journal --outcome went` took a blocked-day walk with `Baahar said: —`; the record drops the verdict the app just gave.

## What the refusal got right
Disabled, not hidden: I could see Pocket Mode was deliberately off with the reason underneath, and every bypass (hash, query params, timer, deep link) hit the same gate. A "no" you can see is a "no" you can trust.

---

# Persona 4 — Rahul, non-technical web user

## Commands run (with the 1-line result each produced)
- `$env:BAAHAR_OFFLINE="1"; $env:GEMINI_API_KEY=""; uv --version` → `uv 0.12.22 … 2026-10-01`.
- `uv run baahar serve --port 8000` → **failed**: `[WinError 10048]` port in use (a *non-offline* server was already there; its health said `"offline":false`).
- Started my **own offline** server `… --port 8011` → `Uvicorn running on http://127.0.0.1:8011`.
- `GET /api/health` → 200 `{"status":"ok",…,"offline":true}`.
- `GET /api/brief?offline=1&model=template` → 200, fields below. Then killed PID 13612 (port 8011); left 8000 alone.

Printed fields: `overall:GO`, `headline:"Go at 06:00."`, `current_decision:GO`, `pocket.active:False`, `pocket.headline:"Not yet."`, `subline:"Forecast window 06:00. Refresh conditions before walking."`, `notice_this:"Listen for the first two birds, then ignore the traffic."`, `walk_minutes:20`, `briefing.text` opens `"WAIT. Hold off on the walk…"`, `disclaimer:"Informational outdoor planning only. Not medical advice…"`, `safety_note:"Recorded or unavailable data cannot authorize a walk now."`

## Answers to the five questions
1. It doesn't ask — it promises. Big `Baahar`, `बाहर · outside`, then `"Finds your next safe outdoor hour from air quality, heat and rain — then turns this screen off."`, one button `"Find my hour"`, hint `"Live data from Open-Meteo. No account, no card."`
2. 3 screens (ask, brief, pocket) + an after-walk journal. Path: open → tap `"Find my hour"` → brief; then tap `"Pocket the phone"` (2nd tap) or let a **45s** auto-countdown darken it. So 1–2 taps, meets "≤3". **But** here `pocket.active:false`, so the button is disabled and auto-enter never arms (gated by `pocketActive`, app.js:548/345) — the dark screen is unreachable.
3. Yes — the Options panel: `"Scorer … heuristic policy"`, `"TabPFN"`, `"Gemma via AI Studio"`, `"Tinker fine-tune"`, `"auto (open model if keyed)"`. Exact string I'd choke on: `"heuristic policy"`.
4. No — ask/brief/pocket never appear as labels. User-facing text is only `"Find my hour"`, `"Pocket the phone"`, `"back"`; the stage names (`screen-ask` etc.) are code-only. The `WAIT/GO/SKIP` badge itself is clear.
5. Not right now — if the one thing I open it for (screen going dark) is disabled as `"Not yet."`, there's no reason to reopen it at the wrong hour.

## Three concrete problems, ranked
1. **Headline feature is dead in recorded mode.** `"Pocket the phone"` disabled with `"Not yet. — Recorded or unavailable data cannot authorize a walk now."`; the auto-prompt `Pocket Mode in Ns — tap "Pocket the phone" now…` never shows. This breaks "screen is the shortest part" exactly for a browser user at the wrong hour.
2. **Backend jargon on the first screen.** `"heuristic policy"`, `"TabPFN"`, `"Tinker fine-tune"` in a Writer/Scorer dropdown before any answer.
3. **Three verdict voices at once.** Badge `WAIT` (app.js:227), headline `"Go at 06:00."`, briefing `"WAIT. Hold off…"`, and raw JSON `overall:GO` — someone asking "now?" reads "Go" and "WAIT" together.

## One thing that felt effortless
One button, no login, `"No account, no card."` — click once and get a plain answer plus an honest disclaimer.
