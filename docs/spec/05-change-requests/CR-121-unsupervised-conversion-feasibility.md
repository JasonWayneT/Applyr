---
status: in-progress
date: 2026-09-21
implementation_plan: ../08-implementation/CR-121-unsupervised-conversion-feasibility-epics.md
related: CR-087, CR-093, CR-112, CR-114, CR-119, CR-120
---

# CR-121: Unsupervised conversion feasibility and Agy rubric scoring

## Decision sought

Stop authoring jobs that Stage 0 already knows WE cannot make look native, and score finished drafts through Agy instead of a Cursor agent sitting on Mech. Do not raise the fit skip floor. Do not Skip those jobs. Do not point `eval_submission.py` at Agy.

## Problem

Live 2026-09-21 parks: velosio resume 63, certara 64, omnissa 64, outschool 66, goodrx 64. All Stage 0 PASS. Honest `mech.rubric_floor.resume` BLOCK.

Stage 0 measures PM-eligibility with SOFT bridges (skip floor 40). Conversion R2/R3 measure whether the top of the resume looks like this JD's domain. Those are different questions. Velosio was Tier 1 fit 71, then 63. Raising 40 would not have caught it.

Two mapping bugs made some of those drafts worse and are already fixed for future packets: Dynamics still received claim IDs after `NOT_PRESENT`, and Kafka `exposure` won Omnissa frontline. The remaining miss is structural. WE has no Dynamics, no UEM/Android, no clinical/biostats native proof, no pharmacy-adjudication native proof. Authoring still ran. Agy spend, then a floor park.

A second unsupervised hole is rubric entry. Mech needs `reviews/rubric_scorecard.json` plus `draft_manifest.json`. Today a coding agent types that. `eval_submission.py` still calls `utils.call_llm` (Groq/Gemini API). Those keys are free-tier and do not serve production. That is not a product hold. Agy is already the Stage 0/1 LLM. The 2026-08-17 pop_up_talent miss still stands: that script scored a cover letter 92 against an honest 69. Switching the transport does not make that prompt a judge. New scorer, CR-112 scorecard contract, frozen calibration.

## Product outcome

The queue can run size-1 without a human between Stage 0 PASS and the next slug, including jobs that will never clear 70. Those jobs pause as `conversion_risk` before authoring. Jason can later `requeue --reason apply_anyway` in a batch. That is minimal supervision, not mid-pipeline questions.

Drafts that do author get an Agy scorecard. Independent-blind still fires in the CR-112 band. Floors stay 70/65. Honest below-floor stays parked.

## Operator LLM path (lock this in docs)

| Path | LLM |
|---|---|
| Stage 0 extract / classify / evidence, Stage 1 author / repair | Agy. Worker sets `APPLYR_STAGE0_SUBSCRIPTION_ADAPTER=1`. |
| Groq / Gemini API (`utils.call_llm`) | Leftover cascade. Free-tier keys are present and do not work. Tests may pin `APPLYR_STAGE0_CLOUD_LLM=1`. Production must not. |
| Settings → API Gemini / Groq rows | Scout research, Gmail, editor rewrite. Not the CSV queue. Dead free-tier on those rows is expected until paid keys exist. |

Do not write "Groq/Gemini are off" as if the pipeline has no LLM.

## Conversion-feasibility band

After fit PASS, before packet/authoring, write `conversion_feasibility` on `stage0_fit_gate.json`:

```
{
  "verdict": "ok" | "risk",
  "reasons": ["not_present_required_tool:Microsoft Dynamics 365", "..."]
}
```

`risk` when any of:

1. A required JD item names a tool in `not_present_named_tools` (velosio Dynamics, omnissa Workspace ONE / Android).
2. A required item has evidence_level 0 and `looks_like_named_tool` (multi-token hits, or a single token that matches a NOT_PRESENT display name).

Story 2.2 killed "zero distinctive required overlap with WE." All five parked gates already have required PM items at evidence 3–4. Clinical/pharmacy identity sat in preferred or at evidence 1 and stays out of this band. Do not add a domain gazetteer in the same change.

`ok` when no required identity tool is `NOT_PRESENT` and no required named-tool evidence 0 hit fires. Outschool (fit 62) and certara/goodrx stay `ok` and can still park below 70. v1 accepts that miss rather than a noun list that false-risks transferable PM jobs.

Not `risk`: hire-site chrome, preferred-only tools, culture lines, empty-required Tier 2 washout (Optum-shaped).

Decision on `risk`: **withhold authoring**. `decision` stays PASS. Folder is not skipped. Queue `paused_reason=conversion_risk`. Worker releases the lease and claims the next slug. Explicit `queue_claim.py requeue --slug SLUG --reason apply_anyway` is the only promote path.

Do not auto-Skip. A Skip writes the skip ledger and hides a job Jason might still want.

Do not raise `skip_floor`.

## Agy rubric scorer

New `scripts/run_stage2_rubric.py`, same sandbox / no-tools / stream-json pattern as `run_stage1_author.py`.

Input: `conversion_rubric.md`, `Resume.md`, `CoverLetter.md`, `Original_JD.txt`, packet excerpts already on disk. Not `eval_submission.py`'s prompt. Not Groq/Gemini.

Output: one CR-112 `reviews/rubric_scorecard.json` row (`authoring_session`), copy binding totals into `draft_manifest.json.rubric_score`, set `verification_passed` only after Mech's other checks already passed. Boundary band `[67,73]` / `[62,68]` starts a second fresh Agy session as `independent_blind`. Disagree-low binds. No averaging. No picking the high score.

Worker: after Stage 2 Mech is waiting on a missing scorecard (or after compile, before policy), one in-lease rubric call, then `--resume`. Same shape as AC-458 author-then-resume.

Release gate: frozen parked floors (velosio, certara, omnissa, outschool, goodrx). Agy must not emit resume total ≥ 70 on a document whose honest parked total is below 70. Prefer within ±5 of the parked total. If it CONVERT-READY those folders, the scorer is not production. Do not lower 70/65 to make it pass.

## Out of scope

- CR-120 evidence-first authoring (separate quality path, switch still off).
- HM critical-read automation (Stage 2C). Agents still dispose WARN findings.
- Rebuilding parked floor folders.
- Auto-requeue of optum, origami, nava.
- Paid Groq/Gemini keys.
- Domain noun gazetteer beyond distinctive overlap.

## Requirements and acceptance

| Requirement | Acceptance |
| --- | --- |
| `FR-353` Operator LLM path is Agy | `AC-460` AGENTS.md, README queue section, ACTIVE_WORKFLOW, and PRODUCT_CAPABILITIES state Agy as the Stage 0/1 LLM. Groq/Gemini API is leftover cascade with non-working free-tier keys, not a missing product. `eval_submission.py` is not the scoring path. |
| `FR-354` Conversion feasibility after PASS | `AC-461` Gate writes `conversion_feasibility`. Required `NOT_PRESENT` tools and zero distinctive required overlap are `risk`. Hire-site-only and empty-required washout are `ok` or Skip by existing rules, never this band. Skip floor unchanged. Tests use velosio/omnissa-shaped fixtures plus an Optum-shaped non-risk. |
| `FR-355` Withhold, do not Skip | `AC-462` `risk` pauses `conversion_risk`, leaves `decision=PASS`, does not write skip ledger, does not author. Worker continues. `requeue --reason apply_anyway` is the only promote. |
| `FR-356` Agy CR-112 scorecard | `AC-463` `run_stage2_rubric.py` writes a valid scorecard + manifest copy. Independent-blind in band. No `call_llm`. Worker one-shot in-lease. |
| `FR-356` continued | `AC-464` Frozen parked resumes below 70 must not score ≥ 70. Fail closed on that gate. |

## Release

Story 1 (docs) can land alone.

Stories 2–3 change who gets authored. Independent QA on fixtures, then one live size-1 worker that must pause a Dynamics-shaped job and claim the next slug.

Stories 4–5 stay off-default until AC-464 passes on the frozen parks. Then worker hook.
