# `eval/raw/`

Machine-readable output for every evaluation run. **Every number published in
[`../RESULTS.md`](../RESULTS.md) comes from a file in this directory.** Nothing
here is hand-written.

Each file is a complete, self-describing run:

```jsonc
{
  "run_at": "2026-10-06T05:01:20+05:30",   // when it ran
  "keys_present": { ... },                   // key presence only, never values
  "versions": { "python": "3.14.0", "tabpfn": "9.1.0", ... },
  "dataset": { "n_rows": 8130, "n_train": 6504, "n_test": 1626, ... },
  "results": { "<model>": { "accuracy_mean": ..., "safety": { ... } } }
}
```

## File naming

```
gono_<YYYYMMDD>T<HHMMSS><±TZ>.json        tabular go/no-go
briefing_<YYYYMMDD>T<HHMMSS><±TZ>.json   briefing writers
```

The timestamp in the filename is the run time, so sorting by name is sorting by
recency.

## The published runs

| File | What it is |
|---|---|
| `gono_20261006T050543+0530.json` | The tabular run quoted in RESULTS.md. All six models; TabPFN reported `SKIPPED` with the reason. Includes the SKIP-cause breakdown. |
| `briefing_20261006T050120+0530.json` | The first complete briefing run (36 cases, both writers). Its blind-rubric scores are **superseded** — see the note below. Its generated texts and machine checks are the canonical ones. |

Verify that the published document matches these files:

```bash
uv run python scripts/check_results.py
```

## `_development/`

Fifteen intermediate runs from while the harness itself was being built and
debugged. They are kept rather than deleted, because the bugs they document are
part of the project's record — but **no published number comes from any of
them.**

They include runs of 2–8 cases, and runs produced by a judge that was scoring
every dimension 0 because the rubric prompt's placeholder id collided with the
word `BANNED` on the next line. See RESULTS.md § Failures.

## Reading a run

```bash
# human summary of the tabular results
uv run python -c "
import json, glob
f = sorted(glob.glob('eval/raw/gono_*.json'))[-1]
d = json.load(open(f))
for name, r in d['results'].items():
    if r['status'] != 'OK':
        print(name, r['status'], '-', r['reason'][:70]); continue
    s = r['safety']
    print(f\"{name:<12} acc={r['accuracy_mean']} macroF1={r['macro_f1_mean']} \"
          f\"skip_as_go={s['skip_as_go_rate']} n={s['n_true_skip']}\")
"
```