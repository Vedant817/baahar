# Train on Modal without burdening the laptop

**Live status, 2026-10-07:** the user explicitly authorized payment-method setup
and confirmed adding it, overriding the repository's no-card rule for this run.
The earlier payment gate is retained as
[`historical failure evidence`](../eval/raw/modal_blocked_20261007.json).
The GPU function now starts. The first accepted submission failed during import
because `dotenv` was unavailable remotely; `.env` loading is now local-only.
The following T4 run failed with CUDA memory exhaustion; see
[`failure evidence`](../eval/raw/modal_t4_failure_20261007.json).
The successful L4 run uses batch size 2 and releases large logits between steps:
[`manifest`](../eval/raw/modal_submission_20261007T182316Z-30afa945.json).
Training completed and results were fetched:
[`result JSON`](../eval/raw/modal_20261007T182316Z-30afa945.json).
Three epochs used 198 training and 22 validation examples, with no exclusions.
Validation assistant-token cross-entropy fell from 2.296414 to 0.015992.
The training loop (including per-epoch validation) took 104.2 seconds, excluding
setup, baseline evaluation, sample generation and final evaluation. The adapter
and tokenizer are saved remotely under `runs/20261007T182316Z-30afa945/adapter`
on Volume `baahar-training`. The app has stopped. No inference API is deployed.

The GPU, PyTorch, base weights, training and adapter storage all live on Modal.
The laptop only uploads the two small JSONL datasets and the tokenizer helper,
then submits a job. `--detach` exits after submission; the laptop may sleep or
shut down once the submission manifest has been written.

## Requirements

- Your existing credited Modal workspace `vedantmahajan271`, environment `main`.
  Check the credit balance and account limits in the dashboard. GPU use requires
  a saved payment method; the user explicitly authorized adding one for this run.
- Python 3.12+ and uv, already installed here.
- A Modal login saved on this machine, or the two private Modal token variables
  in `.env`. The dashboard URL alone does not authenticate the SDK.
- `data/ft/train.jsonl` and `data/ft/val.jsonl` (currently 198 / 22 rows).
  They are generated briefing supervision, not field observations. No Hugging
  Face token is needed for the default public Qwen model.

## Steps (PowerShell, repository root)

1. Install only the lightweight client and normal development dependencies:

   ```powershell
   uv sync --group dev --group modal
   ```

   Do not add `--group ml` or `--group tinker` for this workflow. This sync also
   removes unused heavy packages from the project virtualenv; shared uv caches
   and previously downloaded model directories remain on disk.

2. Authenticate and select the intended environment:

   ```powershell
   uv run --group modal modal token new
   $env:MODAL_ENVIRONMENT = "main"
   uv run --group modal modal profile current
   uv run --group modal modal app list
   ```

   Finish the browser flow in workspace `vedantmahajan271`. Keep credentials
   private. If you already authenticated, skip `token new`. The profile name
   can differ from the workspace name; verify the workspace during browser login.

3. Check the plan without spending credits or downloading weights:

   ```powershell
   uv run --group modal python scripts/fine_tune_modal.py --dry-run
   ```

   Defaults: Qwen2.5 1.5B Instruct, L4, rank 16, 3 epochs, batch 2. GPU and model
   overrides are `BAAHAR_MODAL_GPU` and `BAAHAR_BASE_MODEL` in `.env` or the shell.
   L4 supports bfloat16; check current Modal pricing. A previous T4 batch-4 run
   exhausted GPU memory. The runner requires CUDA and uses bfloat16 where
   supported, otherwise float32. It never falls back to laptop CPU training.

4. Submit once and let the laptop rest:

   ```powershell
   uv run --group modal python scripts/fine_tune_modal.py --detach
   ```

   Image building and dataset upload finish before this command exits. The
   submission manifest is `eval/raw/modal_submission_<run_id>.json`. It records
   the call ID and parameters, not a successful training result. Monitor
   `baahar-finetune` at https://modal.com/apps/vedantmahajan271/main.
   There are no automatic training retries; submitting again starts another
   billable run. The function has a one-hour timeout. Cost and duration are
   unmeasured until a real run; compute and persistent Volume storage can bill.

5. Retrieve the small result JSON when the job finishes:

   ```powershell
   uv run --group modal python scripts/fine_tune_modal.py --fetch-call <call_id>
   ```

   Replace `<call_id>` with the manifest value. If still running, the command
   reports that and exits after a short wait. Failed training raises an error.
   A successful fetch writes `eval/raw/modal_<run_id>.json` with baseline and
   adapted assistant-token loss, samples, timing, dataset hashes and exclusions.

6. The reusable LoRA adapter and tokenizer stay in Volume `baahar-training` at
   `runs/<run_id>/adapter`; `runs/<run_id>/results.json` is the durable report.

   ```powershell
   uv run --group modal modal volume ls baahar-training runs
   uv run --group modal modal volume get baahar-training runs/<run_id>/results.json eval/raw/modal_recovered.json
   ```

   The second command recovers results if the function-call result expires.
   No need to download base weights or the adapter to this laptop. To stop a
   cloud run, use its Stop control in the Modal dashboard. Stopping a local
   client does not stop a detached cloud job.

## What this establishes

This runs a fine-tuning experiment through Modal's remote Function API.
It does not deploy an inference API or switch Baahar's live briefing provider.
Evaluate generated briefings for safety and readability before using the adapter.
Lower template loss alone is not a safety or quality acceptance test. Compare
base and adapter within the same run; the older local experiment used a different
base-model size, so its losses are not directly comparable.

No remote training result is claimed until real artifacts exist. Keep the
zero-key offline briefing path available. This is Modal use, not Tinker use.

References: [Modal app lifecycle](https://modal.com/docs/guide/apps),
[detached runs](https://modal.com/docs/reference/cli/run),
[persistent Volumes](https://modal.com/docs/guide/volumes).


## Two-candidate grounded experiment (v2)

The original 1.5B run above is retained as historical evidence. The new experiment
uses two pinned instruction models and a separate safety/grounding contract; see
[MODEL_IMPROVEMENT_PLAN.md](MODEL_IMPROVEMENT_PLAN.md) for the frozen selection rule.
No base weights or adapters are downloaded to the laptop.

```powershell
uv sync --group dev --group modal
uv run --group modal python scripts/build_ft_v2_dataset.py
uv run --group modal python scripts/train_briefing_candidates_modal.py --dry-run
uv run --group modal python scripts/train_briefing_candidates_modal.py --submit --detach --manifest eval/raw/candidate_submission_v2.json
uv run --group modal python scripts/train_briefing_candidates_modal.py --fetch eval/raw/candidate_submission_v2.json
```

**Submit once.** An existing manifest is deliberately rejected to prevent an
accidental duplicate billable pair. Fetch can be repeated: it reports pending
calls without resubmitting. Both jobs run on L40S, with two-hour timeouts and no
automatic retry. The small metrics and generation logs come back to `eval/raw/`;
adapters remain in `baahar-training/candidates/<run_id>/<candidate>/adapter`.

The dataset contains 961 training cases (841 recorded archive conditions plus
120 explicitly synthetic augmentation cases), 80 chronological validation cases,
88 locked archive test cases, and 64 separately reported synthetic stress cases.
Prose targets are deterministic authoring, not human quality ratings. The contract
is a finite language validator, so manual review remains part of promotion.

Optional private serving is implemented in `scripts/serve_briefing_modal.py`.
It refuses to load an adapter without a matching promoted `serving.json` registry.
Do not create that registry or deploy until the selected candidate passes the
registered validation/test criteria and qualitative review. Then the authenticated
SDK path is available through `baahar brief --model modal`; the default provider
selection and zero-key local path remain available. Configure the selected run
and candidate with `BAAHAR_MODAL_RUN_ID` and `BAAHAR_MODAL_CANDIDATE`. These are
artifact identities, not credentials. Modal authentication remains in its private
local profile, never in the repository.
