# CR-114 Stage 0 hosted-call inventory

Date: 2026-09-17. Story 7 evidence only. This is not a release report and does not enable the production switch.

## In-scope Stage 0 hosted calls

| Site | File | Providers today | Notes |
|---|---|---|---|
| Uncertain NLP extraction | `scripts/build_stage0_fit_gate.py` `_resolve_uncertain_extraction_llm` | Groq, then Gemini | Replaced only when `APPLYR_STAGE0_SUBSCRIPTION_ADAPTER` is on. Default remains this path. |
| Local section-split extraction | `scripts/build_stage0_fit_gate.py` `_extract_sections_llm` | `provider_override=["local"]` pinned to `STAGE0_EXTRACT_MODEL` | Not a Groq/Gemini site. Out of CR-114 replacement scope. |
| Uncertain evidence batch | `scripts/stage0_evidence_cascade.py` `classify_requirements_batch` plus retry | Configured Stage 0 evidence chain (default Groq, then Gemini; Local explicit) | Adapter wired behind `APPLYR_STAGE0_SUBSCRIPTION_ADAPTER`. Default remains this path. Unsafe HARD still held. Timeout/invalid output pauses for review. |
| Cost authorization | same cascade + `scripts/cost_eligibility.py` | none until attested or paid-allowlisted | CR-112 pause. Unchanged. |

## Out of scope (Stages 1-3 or non-Stage-0)

`cover_letter_slots.py`, `local_draft_stages.py`, `ai_rewrite.py`, `eval_submission.py`, `audit_and_improve.py`, `bullet_generation.py`, `skill_gap.py`, `research-engine.py`, `generate_experience_summary.py`, `draft_linter.py`, `zero_shot_classifier.py`.

## Replay gates that have not passed

- Python argv + `--prompt-file` is now the real CLI path. A 2026-09-17
  positional prompt containing `|` was executed by Windows `npx.cmd` as a
  pipe (`preferred` is not recognized as a command). That is fixed.
- Cursor 1-item smoke (`--harness cursor --profile cursor-default --access
  readonly`) fail-closed: `cursor-agent` is not on PATH
  (`CLAUDEXOR_CURSOR_BIN`). Flags were accepted; no extraction schema body
  was returned.
- Codex 1-item smoke (`--harness codex --profile codex-default --access
  readonly`) fail-closed: profile over 90% headroom, reset
  `2026-09-17T22:04:03.000Z`. No schema body. Claude and Agy were not used.
- No 5-10 archived-JD actual-schema smoke on a working subscription profile.
- Local archive has hundreds of JDs, but `data/training_data_approved.csv`
  is absent, so there is no adjudicated 30-JD gold set. Numeric call/time
  caps cannot be set from evidence. Gold labels were not manufactured.
- Production switch remains off. Rollback is: leave
  `APPLYR_STAGE0_SUBSCRIPTION_ADAPTER` unset, keep `data/stage0_classifier.pkl`
  at its current hash, do not promote a candidate.
