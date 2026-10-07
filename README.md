# Baahar (बाहर) — Bengaluru outdoor-planning assistant

> *Find Bengaluru's next clean outdoor hour (NAQI + heat + rain), generate a ~30s
> park briefing with open AI, then Pocket Mode so your phone goes dark while you
> walk.*

Built for the **Hugging Face / DEV Challenge 2026** (Week 1). MIT-licensed,
India-first, beginner-friendly, runnable in five minutes with zero API keys and
no paid services.

---

![Baahar web UI: 12-hour decision strip and one-tap park briefing](docs/media/01-briefing.png)

## Why this exists

Bengaluru is a walking city with a particulate problem. The air is not Delhi's,
but in October the monsoon exits, construction dust picks up, and a 07:00 walk
can hit NAQI 65 while a 10:00 walk hits NAQI 180. The data to know the difference
is public; the habit to check it before leaving the house is not.

Most weather apps fail this in one of two ways:

1. They report **US AQI**, which uses different breakpoints and different
   reference times from the Central Pollution Control Board (CPCB) standard. A
   "Moderate" reading in US AQI is not the same physical condition as
   "Moderate" in Indian NAQI.
2. They are **engagement surfaces**. They want you scrolling an hourly forecast,
   looking at a map, reading a news card.

Baahar's opinion is that an outdoor-planning assistant should do its job in
**thirty seconds**, hand you a reason to walk and a safety boundary, and then
**shut up and get out of the way**. That is what Pocket Mode is.

It is deliberately *not* a social app, a tracker, or a feed. It has no streak
counter and nothing to come back to. The success metric is you leaving.

---

## What it actually does

1. Pulls **hourly weather + air-quality signals** for Bengaluru from
   [Open-Meteo](https://open-meteo.com/) (no API key, no signup, no card).
2. Converts those pollutant concentrations into **Indian NAQI** using the CPCB
   sub-index breakpoints — *not* a US AQI number wearing an Indian label.
3. Scores the next hours **GO / WAIT / SKIP** with a 28-feature tabular model
   (the shipped consensus ensemble, or optional [TabPFN](https://priorlabs.ai/))
   on weather and past-hour air-quality signals, falling back to a documented
   heuristic when ML dependencies are absent.
4. Generates a **≤120-word park briefing** with an open model
   (Gemma via [Google AI Studio](https://aistudio.google.com/)), optionally
   fine-tuned on Indian outdoor-briefing style via hosted
   [Tinker](https://tinker.ai).
5. Optionally speaks it aloud, then drops into **Pocket Mode**: near-black
   screen, one line of text, a walk timer. No feeds, no badges, no notifications.

If the air is bad or it is genuinely too hot, Baahar says **SKIP** and means it.
It will not cheer you into bad air.

---

## Quickstart (under 5 minutes)

Requires [Python 3.12+](https://www.python.org/downloads/). Nothing else — no
Node, no Docker, no account, **no credit card**.

```bash
git clone https://github.com/Vedant817/baahar.git
cd baahar

# Option A — uv (fastest)
uv sync --group dev
uv run baahar brief --city Bengaluru          # live Open-Meteo, offline LLM template

# Option B — plain pip
python -m venv .venv && . .venv\Scripts\activate   # Windows
python -m pip install -e .
python -m baahar brief --city Bengaluru
```

That command prints a 12-hour GO/WAIT/SKIP table and a real briefing from live
forecast data. **No API keys are needed** — without a `GEMINI_API_KEY`, Baahar
uses a deterministic local briefing writer, and everything still works.

Now try it with a real open model:

```bash
cp .env.example .env      # then put your free Google AI Studio key in .env
uv run baahar brief --city Bengaluru --model gemma
```

Open the web UI — this is the part that matters:

```bash
uv run baahar serve         # http://127.0.0.1:8000
```

![Pocket Mode: one instruction, a timer, no scroll](docs/media/03-pocket.png)

Tap **"another thing to notice"** a few times to reach a species suggestion, which
carries its own provenance line rather than pretending to be hand-written:

![A seasonal cue with its evidence underneath](docs/media/03b-pocket-seasonal.png)

Regenerate the screenshots yourself, with a layout audit that fails on console
errors or horizontal overflow:

```bash
uv run baahar serve &
node scripts/ui_check.mjs --out docs/media
```

| | |
|---|---|
| **Try the CLI** | `uv run baahar brief --city Bengaluru` |
| **Try Pocket Mode** | `uv run baahar serve`, then tap "Pocket the phone" |
| **Record a walk** | `uv run baahar journal --outcome went --note "..."` |

## The three commands

```bash
uv run baahar brief      # decision, hour table, briefing, Pocket Mode payload
uv run baahar serve      # the web app -- two screens and a clock
uv run baahar journal    # after the walk: three taps, one line, markdown out
```

`journal` is the one most people will not expect. It asks what actually
happened, counts how many times you reached for the phone, and prints markdown
ready to paste into a write-up. Local only: a JSONL file or `localStorage`, no
account, no sync. A journal about where you walk is exactly the data this
project should not be collecting anywhere.

### Add the TabPFN tabular model (optional)

TabPFN pulls PyTorch (~2.5 GB), so it lives in a separate dependency group — the
5-minute quickstart stays honest and the disk-frugal constraint stays respected.
Install it only if you want the learned scorer:

```bash
uv sync --group dev --group ml
uv run baahar score --city Bengaluru --scorer tabpfn
```

> **One human step is required.** `tabpfn >= 2.x` refuses to download model
> weights until a Prior Labs licence acceptance is recorded in `TABPFN_TOKEN`,
> *even though the weights are public on Hugging Face* — I verified the repo is
> not gated. That is a licence gate, not a technical one, so Baahar does not route
> around it. Until it is accepted, the scorer says so in plain language and uses
> the policy instead. See [`docs/NEEDS_HUMAN.md`](docs/NEEDS_HUMAN.md).

Baahar tells you which scorer produced every decision, and the heuristic path is
a first-class fallback rather than a stub. Without the licence, `run_eval.py`
reports TabPFN as **`SKIPPED`** with the reason and still publishes the
conventional baselines.

**With the licence accepted and token configured**, TabPFN runs for real on the
1,626-row chronological holdout on 28 features (13 base + 15 past-hour lags) across
5 seeds (0–4) and scores **0.8708 +/- 0.0023 accuracy / 0.6193 +/- 0.0020 macro-F1**
(averaged over the 4 supported bands; two bands have zero holdout support; `poor` has n=3).
It achieves the highest raw accuracy in the evaluation (+0.0091 over the consensus ensemble
0.8617 +/- 0.0005), but loses macro-F1 to the shipped consensus ensemble (0.6349 +/- 0.0368;
on the 3 bands with real support, ensemble 0.8249 vs TabPFN 0.8236) and is substantially worse
on moderate recall (0.5845 vs 0.6620 on seed 0) — the critical under-warning direction for an
air-safety product. TabPFN also costs 358.1 s per fit (~6 minutes on CPU) vs 46.43 s for the ensemble.
The +/- figures describe seed spreads (sample standard deviations over 5 seeds 0–4), not confidence
intervals (binomial SE at n=1,626 is ~0.009, roughly 18× larger). The consensus ensemble is the
shipped engine. *(The earlier 13-feature run scored 0.8542 / 0.6031; an older provisional single-seed
run cited in older commits was 0.8512 / 0.6040 on instantaneous NAQI, not like-for-like with current features).*
Three things worth knowing before you trust it:

- TabPFN guards against >5,000 rows on CPU. `score.py` sets
  `TABPFN_ALLOW_CPU_LARGE_DATASET=1` for you, **before importing tabpfn** (setting
  it afterwards does nothing — the guard snapshots its settings at import). Full
  eval is ~6 minutes (358 s fit).
- The fitted classifier is **840 MB**, so `eval/artifacts/` is gitignored and
  `run_eval.py` recreates it. No weights in this repo, by design.
- The eval and the app share **one** 28-feature definition. They didn't for a while:
  the eval fitted on 13 archive columns while the app built 15 library features, so
  a fitted model could never actually be used at request time — it failed inside
  `predict_proba` and every hour silently fell back to the heuristic while the
  published table described a pipeline nobody ran. `score_tabpfn` now raises on a
  feature-count mismatch instead of reordering columns to fit. Full account in
  [`eval/RESULTS.md`](eval/RESULTS.md) § C.14.

---

## Deadline & provenance

This repo was started on **6 October 2026**, inside the challenge window that
opened 5 October 2026.

| Event | PDT | IST (UTC+5:30) |
|---|---|---|
| Challenge opens | Oct 5, 2026 | Oct 5 evening / Oct 6 early IST |
| **Submissions due** | **Oct 11, 2026 23:59** | **Oct 12, 2026 12:29** |
| Feature freeze | — | Oct 11, 2026 18:00 |
| Write-up lock | — | Oct 12, 2026 10:00 IST |

PDT is UTC−7, so Oct 11 23:59 PDT = Oct 12 06:59 UTC = Oct 12 12:29 IST.

---

## Architecture

```
                    Baahar CLI  ·  Baahar Web (Pocket Mode)
                                  │
                          ┌───────▼────────┐
                          │  orchestrator  │   brief / score
                          └───────┬────────┘
            ┌─────────────────────┼─────────────────────┐
            ▼                     ▼                     ▼
   ┌────────────────┐   ┌──────────────────┐   ┌──────────────────┐
   │ weather.py     │   │ air.py           │   │ score.py         │
   │ Open-Meteo     │   │ Open-Meteo AQ +   │   │ Ensemble (ship)  │
   │ forecast       │   │ CPCB Indian NAQI │   │ · or TabPFN      │
   └────────┬───────┘   └────────┬─────────┘   │ · or heuristic   │
            │                    │             └────────┬─────────┘
            └────────────────────┼──────────────────────┘
                                 ▼
                      ┌──────────────────────┐
                      │ brief.py             │  Gemma  ──or──▶  Tinker FT
                      │ ≤120 words + caveats │  (optional ElevenLabs voice)
                      └──────────┬───────────┘
                                 ▼
                          Pocket Mode
```

**Status of each box:** weather, air quality, Indian NAQI, the heuristic scorer,
the Gemma briefing and Pocket Mode all run today with zero keys. The **consensus ensemble**
(LightGBM, HistGradientBoosting, Random Forest) is the shipped engine (**0.8617 +/- 0.0005 acc /
0.6349 +/- 0.0368 macro-F1** over 28 features). **TabPFN** runs for real with `TABPFN_TOKEN`
configured ([how](docs/NEEDS_HUMAN.md)) — **0.8708 +/- 0.0023 acc / 0.6193 +/- 0.0020 macro-F1**
(4 supported bands) over 5 seeds on 28 features. It leads headline accuracy, but loses macro-F1
and moderate recall (0.5845 vs 0.6620) to the ensemble. *(Earlier 13-feature run was 0.8542 / 0.6031;
older provisional single-seed run was 0.8512 / 0.6040 on instantaneous NAQI, not like-for-like).*
**Tinker** is verified reachable — the API is `tinker.thinkingmachines.dev`, not `tinker.ai` —
and a LoRA fine-tune ran against it. Its balance then ran out (HTTP 402) and recharging needs a
card, so the category is **not claimed**; the same experiment re-runs locally on CPU or on a Modal
GPU ([adr/001](docs/adr/001-tinker-outcome.md)). **ElevenLabs** voice is implemented against
fixtures and blocked at the vendor's paid plan; `baahar brief --voice` now says so instead of
silently returning no audio.

Full module-by-module detail: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
Decision records: [`docs/adr/`](docs/adr/).

---

## Why open models make sense here

- **Zero API bill.** Open-Meteo has no key; Gemma runs on the AI Studio
  free tier; TabPFN runs locally on CPU under an open research licence;
  iNaturalist provides CC-licensed biodiversity records; Hugging Face is the
  free research library. The whole demo runs on a laptop with no paid account,
  which is the only reason a solo first-time builder could ship it in five days.
- **Privacy by default.** Location stays at city granularity. There is no GPS
  trail, no background tracking, no account. Baahar cannot follow you, so it
  does not try.
- **Open used to *reduce* screen time.** The interesting engineering problem
  was not "how do we add another surface" — it was "how little screen can this
  survive on." That constraint is only worth meeting with models you can run
  small and cheap.

---

## Honest evals

Every number in [`eval/RESULTS.md`](eval/RESULTS.md) comes from a real run, and
every run's raw output is committed under [`eval/raw/`](eval/raw/) so it can be
re-checked. If something was not measured, `RESULTS.md` says `SKIPPED` and why.

The headline metric is deliberately not accuracy. It is
**`skip_as_go_rate`** — the fraction of genuinely hazardous hours that Baahar
told you to go walk in. A go/no-go classifier that is 94% accurate but sends you
out on the three worst air days of the quarter is worse than useless.

There is a documented failure section too. It is not optional; a benchmark with
no failures listed is a benchmark that was not looked at.

---

## Field test

[`docs/FIELD_TEST.md`](docs/FIELD_TEST.md) holds the checklist for a real
Bengaluru park walk and, separately, the honest record of what actually happened
once a human did it. **The walk is performed by a human; the results are never
invented by the agent.** If it has not happened yet, the doc says so.

---

## What Baahar is not

- **Not a medical device.** Informational outdoor planning only.
- **Not a replacement for the CPCB official advisory.** It reads public
  forecast data, not the official monitoring network, and it will say when it
  is working from a fallback.
- **Not a tracker.** No GPS history, ever.
- **Not a wellness score.** It will refuse to give you a green light in
  conditions that do not warrant one.

---

## Layout

```
baahar/
  src/baahar/
    config.py      settings + .env loading, offline switch
    naqi.py        CPCB Indian NAQI from pollutant concentrations
    weather.py     Open-Meteo forecast client (+ fixture fallback)
    air.py         Open-Meteo air quality (+ optional WAQI stations)
    parks.py       curated Bengaluru parks
    features.py    tabular features for the go/no-go model
    score.py       TabPFN scorer + documented heuristic fallback
    brief.py       Gemma / Tinker / offline briefing writers
    pocket.py      Pocket Mode state + copy
    seasonal.py    research-grade species cues from recorded iNaturalist data
    app.py         FastAPI: /api/brief, /api/score, static UI
    cli.py         Typer CLI
  data/
    parks_blr.json
    samples/       recorded real API responses (offline mode + tests)
    seasonal/      committed monthly iNaturalist snapshots
    eval/          briefing cases, labelled go/no-go rows
  scripts/         feature build, eval runners, seasonal snapshot recorder
  eval/            RESULTS.md + raw/ run artifacts
  docs/            ADRs, architecture, field test, human-only steps
  post.md          DEV submission draft
```

---

## Data & attribution

| Source | Use | Licence / credit |
|---|---|---|
| [Open-Meteo](https://open-meteo.com/) | Hourly forecast + air-quality forecast | Free non-commercial; © Open-Meteo, CC BY 4.0 attribution |
| CPCB | Indian NAQI sub-index breakpoints methodology | Central Pollution Control Board |
| OpenStreetMap | Park extents and footpaths, curated by hand | © OpenStreetMap contributors, ODbL 1.0 |
| Bengaluru CPCB station data via [OpenCity](https://data.opencity.in/dataset/bengaluru-hourly-air-quality-reports) | Historical rows for go/no-go train/eval | CPCB data via OpenCity |

More detail, including re-verification dates: [`docs/SOURCES.md`](docs/SOURCES.md).

---

## License

MIT — see [`LICENSE`](LICENSE).

Built by [Vedant Mahajan](https://github.com/Vedant817) as a first-time open
source project. Contributions welcome.
