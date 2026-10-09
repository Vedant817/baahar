# Frozen v15 qualification

This is hosted inference qualification of the existing v15 Qwen3 4B adapter, with no training, promotion, or deployment. Its manifest records the immutable suite, contract, and rubric hashes before submission. The original runner matching the rubric hash is preserved as `qualification_v15_preregistered_runner.py`; a later client-only fix catches the builtin timeout exception during fetch.

The suite has 24 synthetic diagnostic scenarios in six structural families: missing heat, missing rain, nonfinite weather normalized to missing, compound unknown air/weather plus night and thunderstorm, future forecast permission, and paraphrased instruction injection. These scenarios are authored challenges, not recorded fixtures, field evidence, or blind human review. Exact prompt overlap with the existing `data/ft_v2/*.jsonl` files was measured as zero; this does not establish independent generalization.

Submission: app `ap-4gmcYJGKZdWMxqwaD4IWky`, call `fc-01M4DTS2VP0KQ8PN7S9B6RG3GB`. GPU timeout is 1200 seconds with no retry. Compute estimate is $0.767088, not an invoice. No local model weights were downloaded.

## Preregistered rubric limitations discovered locally

`qualification_v15_local_baseline.json` records an actual local comparison using the frozen contract snapshot. The refresh-before-walk anchor was included in all cases, but its regex does not recognize the fallback phrase “must be checked”. Thus that anchor flags 20 non-temporal fallback cases; this is a wording-check limitation and must not be presented as evidence of harmful walking permission. The four future-permission fallback cases fail `ungrounded_number` under the snapshot because scheduled-time digits are outside its numeric allowance. Root subsequently repaired live time formatting/allowance; qualification deliberately retains the preregistered older snapshot.

Always report contract defects, anchor defects, harmful invitations, and raw prose separately. Do not adjust the preregistered rubric after seeing results. This suite has no positive GO scenarios and cannot establish whether model prose improves the happy path over deterministic prose.

Fetch the bounded inference result with:

```powershell
uv run --group modal python scripts/qualify_briefing_modal.py --fetch eval/raw/qualification_v15_manifest.json
```

No remote success/failure count is recorded in this note until the actual result is fetched.
