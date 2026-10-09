# Targeted weather-uncertainty development corpus

Reproduce before submission: `uv run python scripts/build_ft_v4_dataset.py`.
The builder refuses to change a submitted v16 corpus.

The sole training intervention is 96 additional synthetic cases: 24 each with
missing apparent heat, missing rain, both missing, and normalized current facts
with a future forecast window. Combined cases include storms, night, missing
air, and hazardous air. Current NAQI is represented by one field; forecast
permission never supplies a competing air number. All targets are deterministic
prose, checked against the pinned current contract.

The 969 original training inputs and historical val/test/stress inputs are
copied from ft_v2, whose files remain unchanged. Targets/messages are rerendered
with the current contract. Historical counts remain 80/88/64; these repeatedly
inspected cohorts are development benchmarks, not independent holdouts.

`development.jsonl` has 32 distinct authored variants of the same missing-data
families. The trainer generates base and adapted outputs on these cases but
does not train or select checkpoints on them. They are development diagnostics,
not an independent test of generalization. The already consumed 24-case v15
qualification suite remains a regression suite and contributes no exact prompts
to training. Dataset and source hashes, overlap checks, provenance, and target
acceptance are recorded in `manifest.json`.

Submit one pinned 4B candidate with unchanged v15 hyperparameters:

```powershell
uv run --group modal python scripts/train_briefing_candidates_modal.py --submit --detach --data-dir data/ft_v4 --manifest eval/raw/candidate_submission_v16.json
```

The two-hour remote timeout bounds requested single-GPU compute to approximately
$4.60 under the runner's recorded estimate; this is not an invoice or a verified
credit balance. No weights are downloaded locally. Submission is not promotion.
