# Stage 0 Metis Division - 2026-09-17

> Historical coordination record. For current implementation state and Cursor instructions, use `docs/spec/08-implementation/CURSOR-HANDOFF-2026-09-17-CR-114.md`. The prior "do not dispatch" and missing-CR statements below describe the state before CR-114 was written; do not treat them as current blockers for direct Cursor work.

## Scope

Stage 0 only: replace Groq/Gemini free-tier dependency with bounded subscription-harness fallback for uncertain extraction and evidence judgments; improve local NLP/matching through reviewed corrections. Stages 1-3 follow later. Architecture source: `docs/reports/stage0-architecture-research-report.md` Section 18.

Metis team plan: `.metis/team-plans/stage0-2026-09-17-balanced-readonly.json` (local, ignored). Team run `team-2da41dff83f6`, goal `goal-c89c76eeb261`. Factory/droid is excluded. Every packet has one assigned harness, no automatic fallback, read-only access, and a finite timeout. `claudexor@3.12.1` must be passed explicitly because Metis's default 3.12.0 is below the daemon serving floor on this machine.

## Actual dispatch results

| Harness | Packet | Result | Credit control |
|---|---|---|---|
| Claude | Harness fallback architecture audit | Timed out at 600 seconds with no report. Metis verified launcher cleanup; one daemon-owned Claude child remained and was stopped after checking its PID, parent, start time, and command. No retry. | One capped call; do not repeat the broad packet. |
| Agy | NLP feedback-loop audit | A narrowed two-file, 180-second packet completed in about 32 seconds. It confirmed direct ingestion of unverified fallback labels and train/test leakage from pre-split duplication. Full packet scope remains incomplete. | One short call; no fallback. |
| Cursor | Review Center audit | Not dispatched. `claudexor@3.12.1` preflight reports `cursor-agent` unavailable and the named profile unverified, despite local CLI files existing. | Zero calls until a fresh preflight reports routable. |

Metis evidence: Claude `20260917T175702Z-ad290d13.json`; Agy `20260917T175853Z-fdc1ca39.json` under `.metis/evidence/` (local, ignored). Agy's full answer is in claudexor run `run-08b340f1550e/final/answer.md`. No production files or provider settings were changed by either audit.

## Proposed implementation ownership

1. **Codex coordinator:** write the tracked Stage 0 CR, requirement/acceptance IDs, gold-set protocol, and story tracker; integrate and independently verify every packet. Keep the existing uncommitted Review Center false-positive fix separate. Do not ask one harness to own the entire change.
2. **Claude, after a focused dispatch smoke:** implement only the subscription-harness adapter and its failure/budget tests. Limit file scope to a new Stage 0 adapter and focused tests. A separate integration story connects extraction and evidence call sites after the adapter contract passes. Use a shorter task and timeout than the failed broad audit.
3. **Agy:** implement the trusted-label training path and leakage-free evaluation in `scripts/retrain_stage0.py` and focused tests. Remove automatic promotion of fallback labels in a dependent integration story. Promotion requires held-out JD evidence and a rollback artifact.
4. **Cursor, after routing is fixed:** implement the Review Center decision UI and API contract for uncertain lines, evidence-first review, and corrections, with its own tests. Keep this independent of the adapter/training files.

Do not dispatch implementation yet. Applyr's Metis gate currently finds no `docs/spec/APPROVED_FOR_IMPLEMENTATION.md`, and the new Stage 0 CR and acceptance criteria have not been written. The current goal's `failed` status reflects Claude's timeout, not an overall engineering verdict. No further harness calls should be spent on this goal until the packets are narrowed and routing is rechecked.
