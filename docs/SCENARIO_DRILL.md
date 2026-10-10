# Scenario drill — four personas against the offline app

> **This is a simulation, not a field test.** No agent walked anywhere, saw a
> park, or felt weather. Four personas were played by agents against the real
> software, offline, and every finding below is traceable to output the app
> actually printed. `docs/FIELD_TEST.md` remains `STATUS: NOT YET DONE.` and this
> file does not change that.

## Why this exists

`docs/FIELD_TEST.md` and `AGENTS.md` rule 3 are explicit that an agent must not
invent field-test outcomes, and `docs/DOD.md` treats a fabricated field test as a
disqualifying failure. So the walk cannot be delegated.

What *can* be delegated honestly is everything that happens before the walk:
whether a stranger can read the verdict, whether the copy overclaims, whether a
blocked user can talk the app into a walk, and whether the product's own promise
("the screen is the shortest part") is visible in the first minute. Those are
usability questions with checkable answers, and the drill answers them with the
app's own strings.

## Method

Each persona was given a fixed script of commands to run in
`C:\Users\vedan\Documents\Resources\Code\bahaar` with `BAAHAR_OFFLINE=1`, a fixed
set of five questions, and an explicit instruction never to claim an outdoor
experience. They were told to quote real output and to be blunt. The verbatim
reports are in [`eval/raw/scenario_drill_2026-10-10.md`](../eval/raw/scenario_drill_2026-10-10.md).

| # | Persona | Question it answers |
|---|---|---|
| 1 | Priya, 29, first-time user, wants to walk after work | Can a stranger read the verdict and act on it? |
| 2 | Arjun, 34, sceptical data engineer | Does the app admit what it does not know? |
| 3 | Meera, 41, asthmatic, determined to walk on a bad day | Is a "no" a good "no"? |
| 4 | Rahul, 24, non-technical, browser only | Is the screen really the shortest part? |

## What it found, ranked

1. **A slot advertised a live source inside a recorded plan.** `best_slot` and
   `current_slot` serialised `weather_source: "live"` / `air_source: "live"` while
   the plan said `fixture`, because `HourSlot` defaults both fields to LIVE and
   the join never stamped them. `walk.eligibility` happens to check the plan
   first, so the gate held — but any consumer reading the slot was told the
   opposite of the truth, in the unsafe direction. **Fixed** in
   `src/baahar/forecast.py`; regression test in `tests/test_payload_hours.py`.
2. **Three verdict voices on one screen.** `brief` printed `WAIT  Go at 06:00.`;
   the badge said `WAIT`; `score --json` said `"overall": "GO"`. All three are
   true of different hours. **Fixed** in the CLI, Pocket copy, and web headline:
   the badge-facing sentence is now `Next GO hour is 06:00.`; `plan.headline`
   still names the best hour. The briefing sentence is `The next hour to recheck
   is 06:00.` so WAIT prose never contains a GO token.
3. **The headline feature is dead in recorded mode.** Pocket Mode requires a live
   current-hour GO, deliberately, so an offline demo always shows the button
   disabled with "Recorded or unavailable data cannot authorize a walk now." Two
   personas rated this the single biggest problem — and it is the first thing a
   judge who clones the repo will hit.
4. **Attribution named a source never contacted.** The credit line said "Weather
   and air quality: Open-Meteo (CC BY 4.0)" in offline mode. **Fixed** in
   `src/baahar/static/app.js`: a replayed payload now says "Recorded fixture, not
   a live call." first.
5. **Backend jargon on the first screen.** The options panel exposed "heuristic
   policy", "TabPFN", "Tinker fine-tune" before the user had an answer.
   **Fixed** in `index.html`: scorer is "documented outdoor policy"; TabPFN and
   Tinker are labelled advanced. Options stay inside `<details>`.
6. **`journal --markdown` on this machine printed walks that never happened.**
   `data/journal.jsonl` is gitignored local state, so the repository is clean and
   CI guards it — but the file on this laptop contradicted
   `FIELD_TEST.md`'s "NOT YET DONE". **Fixed** in `render_markdown`: every dump
   now opens with a local-journal disclaimer that the field test is still blank.
   The two entries this drill created have been removed; one older entry
   (2026-10-06) remains and is the author's to judge.

## What held up

- The refusal is a *good* no: visible, reasoned, unbypassable through hash links,
  query strings, the countdown and direct handler calls, and it never preached.
- The honesty layer works: `degraded` names the fixture, the disclaimer is
  present, and `eval/RESULTS.md` states the field test was not performed,
  unprompted, in the results file rather than a commit message.
- One button, no login, no card, and a plain-language answer with a real
  alternative hour and its basis ("NAQI 66, from the last 8 h of air, not just
  this hour").

## How to re-run

Personas are agents; the drill is the script plus the constraint, not a program.
To repeat it: give each persona the commands and questions from the verbatim
report, in a clean checkout (`data/journal.jsonl` deleted), with
`BAAHAR_OFFLINE=1`, and require quoted output plus the no-fabrication rule.
