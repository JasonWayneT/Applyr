# CR-060: Conversational Manual-JD Triage (Chat-Based Fit Review)

## Metadata
- **Epic**: Manual Evaluation UX
- **Status**: Not started — deferred to roadmap (2026-07-09)
- **Date**: 2026-07-09

## Problem
The "Add Job" page (`FindNewJobsView.tsx` → `JDInputForm.tsx`) runs manual single-JD evaluation as one atomic call: `POST /api/evaluate` → `batch_pipeline.py --mode single` executes gate → fit-score → draft → PDF in a single pass with no pause. The fit stage already computes and streams a `Summary` explaining the score ([batch_pipeline.py:1016](../../../scripts/batch_pipeline.py)), but the UI has no point where the user can read that reasoning, push back on it, supply missing context, or ask follow-up questions before assets get drafted.

Today Jason gets that back-and-forth by pasting JDs into Cursor chat instead — Cursor gives him the score explanation, tiering discussion, and room to edit before committing. But because there's no standing instruction for how a coding agent should run this task programmatically, that conversational path has led to agents improvising one-off scripts around the pipeline (e.g. the untracked `run_csv_batch2_draft.py` written same-day, which crashed a 28-job batch on an unguarded `verify_company()` call) instead of calling the pipeline's existing, tested entrypoint.

## Decision (deferred)
Build a real chat surface on the existing "Add Job" → Single Paste flow: after the `fit` stage returns (score + `Summary` + `TopFitReasons`/`RiskFlags`), pause instead of falling through to drafting, and let the user exchange follow-up messages with the fit-scoring model (Gemini 2.5 Flash Lite, per `DEFAULT_MODEL` in `utils.py`) — e.g. contesting a rejection, supplying context the JD omitted, asking why a gate fired — with the ability to trigger a re-score from the conversation. Only once satisfied does the user explicitly advance to drafting, reusing the existing `draft_only=True` code path.

This needs, at minimum: a new stateful chat endpoint that holds JD + score + prior turns as context, a chat UI component on `FindNewJobsView.tsx`, and a re-score action distinct from the current one-shot `evaluate_job_fit()` call.

**Why deferred, not built now**: this is a genuinely new stateful feature, not a tweak to the existing form, and is motivated by a future public/cloud release rather than a current blocking need. Until then, Jason continues dogfooding the JD-triage workflow through Cursor as-is; this CR is the parking spot for that feature so the idea isn't lost.

## Acceptance Criteria (when picked up)
- User can paste a JD, receive the fit score + reasoning, and send at least one follow-up message that results in a materially different response (not just an echo).
- A follow-up message can trigger a re-score using the same `evaluate_job_fit()` logic already in the pipeline, not a parallel implementation.
- Drafting only fires on explicit user action after the conversation, never automatically.

## Out of Scope
- Any change to the CSV bulk-import path — this CR is single-JD manual triage only.
- Replacing Cursor for this workflow before this ships — no interim in-app chat is being built as a stopgap.
- The separate, narrower fix of constraining coding agents to call the existing `--mode single` entrypoint instead of writing new glue scripts — not part of this CR; would need its own decision if pursued.
