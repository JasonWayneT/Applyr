# CR-114 Stage 0 hosted-call inventory

Date: 2026-09-17. Story 7 evidence only. This is not a release report and does not enable the production switch.

## In-scope Stage 0 hosted calls

| Site | File | Providers today | Notes |
|---|---|---|---|
| Uncertain NLP extraction | `scripts/build_stage0_fit_gate.py` `_resolve_uncertain_extraction_llm` | Groq, then Gemini | Replaced only when `APPLYR_STAGE0_SUBSCRIPTION_ADAPTER` is on. Default remains this path. |
| Local section-split extraction | `scripts/build_stage0_fit_gate.py` `_extract_sections_llm` | `provider_override=["local"]` pinned to `STAGE0_EXTRACT_MODEL` | Not a Groq/Gemini site. Out of CR-114 replacement scope. |
| Uncertain evidence batch | `scripts/stage0_evidence_cascade.py` `classify_requirements_batch` plus retry | Configured Stage 0 evidence chain (default Groq, then Gemini; Local explicit) | Adapter evidence schema exists. Production wiring is blocked until matcher replay and actual-schema smoke pass. |
| Cost authorization | same cascade + `scripts/cost_eligibility.py` | none until attested or paid-allowlisted | CR-112 pause. Unchanged. |

## Out of scope (Stages 1-3 or non-Stage-0)

`cover_letter_slots.py`, `local_draft_stages.py`, `ai_rewrite.py`, `eval_submission.py`, `audit_and_improve.py`, `bullet_generation.py`, `skill_gap.py`, `research-engine.py`, `generate_experience_summary.py`, `draft_linter.py`, `zero_shot_classifier.py`.

## Replay gates that have not passed

- Cursor subscription profile is still unverified. A 2026-09-17 PowerShell-quoted smoke swallowed CLI flags, dropped Cursor, and ran Codex with `workspace_write` in the Applyr tree. That run is not schema-contract evidence.
- No 5-10 archived-JD actual-schema smoke on the Python argv adapter.
- No locked adjudicated 30-JD corpus, so numeric call/time caps and error thresholds cannot be set from evidence.
- Production switch remains off. Rollback is: leave `APPLYR_STAGE0_SUBSCRIPTION_ADAPTER` unset, keep `data/stage0_classifier.pkl` at its current hash, do not promote a candidate.
