# Five-agent research review — 8 October 2026

## Decision

Fine-tuning materially improves conformity to Baahar's existing briefing contract. Recent iterations do not demonstrate further acceptance improvement for Qwen3 4B. Keep the adapter provisional. The immediate priority is to repair and qualify current-hour walking permission, before spending more credits on training or considering deployment.

This is a review by five AI research agents, not a panel of human researchers. All reviewed the repository read-only. The parent fetched the completed v15 artifacts and generated its decision report; no new training or deployment was submitted during this review.

## Review provenance

The initial three Claude Opus 5.5 tasks failed authentication; the two Grok 4.7 tasks failed with exhausted usage balance. None produced a research opinion. Their exact task statuses are preserved in [provider failures](../eval/raw/five_senior_review_provider_failures_20261008.json). Five replacement Codex agents completed the reviews, inheriting the parent model, GPT-6.1-sol:

| Role | Completed agent | Principal finding |
|---|---|---|
| Safety | `/root/senior_safety` | Future-slot GO becomes immediate walking permission in the contract. |
| Statistics | `/root/senior_statistics` | Recent perfect scores repeat a familiar development benchmark. |
| Architecture | `/root/senior_architecture` | Keep SFT; more rank, epochs, DPO or pretraining lacks demonstrated marginal benefit. |
| Systems | `/root/senior_systems` | Generation timings do not qualify scale-to-zero serving latency or billed cost. |
| Product | `/root/senior_product` | Pocket eligibility can start a walk for WAIT or future GO. |

Reviews used AGENTS.md, docs/MODEL_IMPROVEMENT_PLAN.md, the tuning ledger, v8–v15 manifests/decisions, source contracts and generation logs. Systems and product received the earlier reviewers' findings and explicitly responded to their proposed sequencing. The parent reconciled the five memos below. A follow-up statistics discussion turn could not start because the agent thread limit was reached; no additional response is attributed to that reviewer.

## What improved, and what did not

The [v8 report](../eval/raw/candidate_decision_v8.md) already records Qwen3 4B adapted acceptance of 80/80 validation, 88/88 test and 64/64 stress. The same counts appear throughout v8–v15, with zero checker-detected raw safety failures and zero fallbacks. Recent acceptance improvement on those reported splits is therefore zero percentage points. The statistics reviewer found saturation already at v5.

The base-to-adapter change is substantial: at v14, base acceptance is 1/80 validation, 3/88 test and 0/64 stress, versus full acceptance after adaptation. These are finite contract checks; failures include grounding and wording requirements. They are not outdoor decision accuracy, clinical safety rates or field outcomes.

In v8 and v10 the latency-selected 7B fails test/stress with 86/88 and 63/64 accepted; v9 passes both. Restricting the pool to 4B in v11 avoids that selected failure, but does not improve an already-perfect 4B. v11–v14 seeds 0/101/202/303 support repeatability on the same cases. Removing the latency tie-break in v14 changes selection policy, not model capability.

The newly fetched [v15 report](../eval/raw/candidate_decision_v15.md), run `20261008T112810Z-6067171e`, remains `PROVISIONAL_PENDING_QUALITATIVE_REVIEW`: 80/80 validation, 88/88 test and 64/64 stress accepted. Its test median generation time is 5.390 seconds. All four dataset hashes changed from v14 while the contract hash stayed unchanged. Treat this as a pass on a revised benchmark, not an additional score gain or a strictly identical benchmark comparison.

## Each reviewer's position and strongest objection

**Safety:** repair the temporal action contract first. `score.py` derives overall decision from the selected best slot, including future hours. `build_contract_case()` supplies that slot's facts, and the contract maps GO to a walk now. The reviewer reproduced a current NAQI350/SKIP followed two hours later by NAQI50/GO yielding an accepted immediate invitation. The strongest objection is that the interface displays the selected future time. The spoken permission still contradicts that time.

**Statistics:** freeze one adapter and perform an independently authored qualification audit against deterministic prose. Current test observations span 32 source days; stress consists of 16 settings with four related variations each. Repeated inspection followed by configuration, selection and dataset changes makes these development/regression benchmarks. Chronological splitting and deduplication are valuable controls, but repeated seed success does not multiply the independent denominator. The strongest objection is that stable hashes and seed repeatability still provide useful evidence. The reviewer agrees, provided the claim remains regression reliability rather than independent generalization.

**Architecture:** keep supervised adaptation and improve qualification before considering DPO or pretraining. Training masks prompt tokens and imitates deterministic fallback targets; synthetic perturbations share condition families with evaluation. Increasing capacity cannot repair incorrect trusted timing facts. The strongest objection is that deterministic prose may already provide adequate product value, making even a better-qualified hosted adapter unnecessary. A blind comparison should be allowed to reach that conclusion.

**Systems:** semantic repair takes precedence over a matched latency experiment. v13/v14/v15 test medians are 2.638/5.183/5.390 seconds for the adapter and 1.382/2.597/2.646 for the base. Both phases slow together with nearly unchanged output token counts and the same recorded L40S/dependency names. This supports a shared runtime explanation, without identifying its cause. Evaluation times generation; serving is configured for L4 with scale-to-zero. Cold startup, request latency and actual billing remain unmeasured. The strongest objection is that a fresh independent audit might reveal wider issues; the reviewer recommends it immediately after fixing the known timing defect.

**Product:** use shared current-hour eligibility for briefing and Pocket entry. `build_pocket()` currently enables Pocket for any overall decision other than SKIP, including WAIT. The UI uses that payload to enter Pocket and start its walk timer, without a separate current-hour GO gate. The strongest objection is that WAIT Pocket could mean resting with the screen dark. Current walk-start/timer behavior does not express that distinction. No human field test is recorded in docs/FIELD_TEST.md.

## Discussion and synthesis

Statistics and architecture initially prioritize a frozen-adapter comparison on new scenario families. Safety, product and systems prioritize repairing the reproduced timing defect first. These recommendations differ in order rather than in the need for independent qualification. The parent's decision is: fix and regression-test the trusted temporal contract, then conduct a sealed adapter-versus-template audit; measure deployment latency only after semantic qualification passes.

Additional disagreements with existing project claims:

- The historical checker counterexample, “SKIP … go walking now”, still passes finite checks. Actual WAIT/SKIP model/cache bypass mitigates it, but does not protect a future GO presented as current permission.
- docs/MODEL_IMPROVEMENT_PLAN.md says missing-air hazard reasons accumulate. Current `features.py` returns early for unknown air and can add “Good air” at night despite unavailable readings. Weather code remains available: v15 stress-14-2 actually mentions its thunderstorm. This is a reason/source consistency gap, not evidence of that model omitting the warning.
- One successful injection case does not establish “superior intrinsic safety alignment.” Preserve that individual result and broaden adversarial coverage.
- docs/FIELD_TEST.md instructs walking despite SKIP, conflicting with the safety policy. It explicitly prohibits agent edits; this review records the issue without changing that file or inventing a field outcome.

## Exactly one immediate next action

Repair and qualify the temporal action contract shared by briefing and Pocket eligibility. Preserve future-hour recommendations as scheduled possibilities, withhold current walking permission, and require a fresh assessment before starting that walk.

Proposed acceptance gate, not an achieved result: zero immediate-walk invitations or walk-timer starts when current conditions are WAIT, SKIP, unknown or stale, including a later GO; exercise template, mocked generated draft, fallback and cache paths plus manual, automatic and deep-link Pocket entry. Eligible current GO must remain usable within the project's three-interaction happy path. Publish the finite matrix and actual denominators; use explicit synthetic provenance and verify the browser separately from offline tests.

After this prerequisite, qualify one frozen adapter versus deterministic prose on newly withheld scenario families with preregistered hashes/rubrics and independent semantic review. The existing suite becomes regression coverage. Do not repeatedly retrain on a suite while calling it untouched. No evidence here justifies further pretraining spend, adapter promotion, or a claim that the $400 credit balance has been measured.

## Reproduction and limits

The parent independently reproduced the temporal counterexample offline with [the probe](../eval/raw/reproduce_temporal_contract_review.py), producing [raw evidence](../eval/raw/temporal_contract_review_20261008.json). The current350/future50 plan yields overallGO, an accepted “walk … now” fallback and `pocket_active=true`. Run `uv run python eval/raw/reproduce_temporal_contract_review.py` to reproduce it. This is explicitly synthetic and not a recorded upstream fixture.

No browser walk, hosted serving request, human field test, model deployment, new training, billing inspection or model promotion was performed in this review. Existing source edits were preserved. The scheduled research loop, its done counter and ledger were not advanced or disabled by this reporting turn.
