# Session Handoff — Batch Processing 2026-09-16

**Status:** Codex token overflow; partial batch processing complete. Real NLP classifier retrain landed. Two open blockers remain.

## What Completed This Session

✅ **isolved:** Resume.md + CoverLetter.md authored, linted, PDFs compiled
- **Corrected status (per verify_submission.py, not self-reported):** `mechanically_verified` is currently False and the receipt is stale relative to post-lint edits. Still needs: manual rubric scoring (R1–R8/C1–C5) written into `draft_manifest.json`, then `verify_submission.py --audit`, then `run_submission.py isolved --resume` to actually reach Stage 2 COMPLETE. Do not treat this as done until that command says so.

✅ **Review Center clearance:** 41 confirmations answered across 18 submissions
- 33 false-positive terms marked BAD_DATA (acronyms, regulations, metadata)
- 6 tools marked NOT_PRESENT (StoreKit, DealCloud, Dynamics, Omeda, SEMrush, EHR)
- 2 tools marked CONFIRMED_USE (Git, Codex)
- This clears the *technical* Review Center gate only — it does **not** mean these 18 are good fits. A real per-JD fit assessment (does the role actually match Jason's background, not just "no hard exclusion keyword") still needs to happen before Stage 1 authoring. An earlier attempt in this session to bulk-approve ~37 submissions via keyword-only exclusion screening was **wrong and was corrected mid-session** — don't repeat that shortcut.

✅ **Stage 0 NLP classifier retrained** (the actual fix, not the local-LLM detour below)
- `data/stage0_classifier.pkl` retrained on `scripts/retrain_stage0.py` using the 5,471 rows already accumulated in `data/training_data_feedback.csv` (active-learning feedback that was already being saved — it just hadn't been fed back since 2026-08-30).
- Backup of pre-retrain model: `data/stage0_classifier.pkl.bak-20260916`.
- Verified real reduction in ambiguous-line rate (the thing that drives Groq calls): nava_benefits 9→2 (-78%), tuckernuck 16→10 (-37%), amplify 12→7 (-42%), binance 6→5. sourcegraph roughly flat (30→31).
- **Run `scripts/retrain_stage0.py` periodically** as more feedback accumulates — this is a genuinely free lever (sklearn, no GPU, no API cost) and directly reduces how often Stage 0 needs an LLM call at all.

## Two Real Blockers Remaining

### 1. Groq Rate Limiting still blocks some batches
**Current state:** Even with fewer ambiguous lines post-retrain, dense JDs (e.g. sourcegraph, 50 lines) still generate enough fallback volume to hit Groq's free-tier 429.
**Options:**
- Set Groq cost authorization (paid tier) in settings.json
- Implement batch queuing/backoff retry (CR-108 batching exists; rate-limit backoff handling does not)
- **Do NOT** reach for a bigger local LLM as the fix — this codebase's Stage 0 architecture is deliberately built around a lightweight local sklearn classifier specifically to avoid needing local LLM hardware. The `local` provider in `stage0_evidence_cascade.py` is a different, separate evidence-mapping step (claim-to-requirement gating), not the JD bucketing classifier, and is not the sanctioned fallback path — an earlier version of this doc wrongly treated it as one.
- Jason is independently evaluating a subscription-harness fallback (`claudexor`/Metis — `claude`/`codex`/`agy` CLIs) for Stage 0; see `docs/spec/08-implementation/INVESTIGATION-2026-09-16-claudexor-stage0-fallback-spike.md`. That spike found the right integration point but hit a `claudexor` daemon crash — blocked on Jason's own tool, not an Applyr wiring issue.

---

### 2. Workflow Integration: Agent-Spawned Authoring Doesn't Write Orchestrator Outputs
**Current state:** We spawned agents to author Stage 1 documents, but they don't write:
- claim_provenance.json (required by Stage 2)
- Proper workflow_state.json updates
- isolved: files written but verification stale; sussexdigital: files never written

**Your solution:**
- Use orchestrator's own `run_submission.py --resume` path, which calls cloud author properly
- Do NOT spawn separate agents for Stage 1; they bypass the workflow orchestrator
- If you want cloud authoring outside orchestrator, ensure output captures include all required files

**For now:** Assume Stage 1 must go through orchestrator cloud path (`run_submission.py --resume`). Manual authoring defeats the workflow state tracking.

---

## Batch State Summary

| Stage | Companies | Status |
|---|---|---|
| **PDF ready** | isolved (1) | Awaiting manual rubric scoring |
| **Stage 1 files lost** | sussexdigital (1) | Agent authoring not recovered; needs re-run via orchestrator |
| **Stage 0 technical gate cleared, fit NOT yet assessed** | 18 | Retry Stage 0 extraction (should need fewer LLM calls post-retrain); still needs real per-JD fit review before Stage 1 |
| **Stage 0: extraction review** | habiterre, healthstream, indigo (3) | Manual bucketing needed |
| **Stage 0: never started** | 5+ | Retry now that classifier is retrained; may still hit Groq on dense JDs |

**Production ready:** 0. isolved is the closest (authored, linted, compiled) but not verified — see correction above.

---

## NLP Training Data / Retraining

See `data/reports/nlp_training_data_2026-09-16.md` for the raw error catalog (false-positive skill terms, extraction ambiguity examples) captured this session.

The actual retraining loop is simpler than that doc implies: `data/training_data_feedback.csv` already accumulates every ambiguous-line resolution automatically (5,471 rows as of this session). Running `python scripts/retrain_stage0.py` periodically folds that back into `data/stage0_classifier.pkl` — no manual curation required, though spot-checking the classification_report output after each retrain is worth doing.

The 33 false-positive Review Center *skill-presence* terms (GDPR, HIPAA, PCI, etc. flagged as "tools") are a separate, server-side detector problem — unrelated to the Stage 0 JD classifier — and still needs an EXCLUDE_TERMS fix wherever that detector lives.

---

## For Next Session

1. Retry Stage 0 extraction on the pending submissions now that the classifier is retrained — expect fewer Groq calls, not zero.
2. Do a real fit assessment (not keyword-exclusion screening) on whichever submissions clear Stage 0 extraction before moving them to Stage 1.
3. Manually score isolved's rubric, enter it in `draft_manifest.json`, run `verify_submission.py --audit`, then `run_submission.py isolved --resume`.
4. Recover/re-run sussexdigital's Stage 1 via the orchestrator's own cloud-author path (not a spawned agent).
5. Periodically re-run `scripts/retrain_stage0.py` as feedback accumulates.
6. Follow up on the claudexor/Metis subscription-fallback spike if a Stage-0-sized provider is still wanted for the remaining Groq gap.

---

## Code Locations

- Stage 0 JD classifier (the real fix): `scripts/retrain_stage0.py`, model at `data/stage0_classifier.pkl`, feedback log at `data/training_data_feedback.csv`, classifier logic in `scripts/build_stage0_fit_gate.py::_extract_sections_nlp`
- Evidence-mapping cascade (separate, unrelated to the classifier above): `scripts/stage0_evidence_cascade.py`
- Detector false-positives: Review Center skill-presence detector (server-side); 33 EXCLUDE_TERMS needed
- Workflow orchestrator: `scripts/run_submission.py` (the single source of truth for workflow state)
- Claudexor/Metis fallback spike: `docs/spec/08-implementation/INVESTIGATION-2026-09-16-claudexor-stage0-fallback-spike.md`
- NLP error log: `data/reports/nlp_training_data_2026-09-16.md`

