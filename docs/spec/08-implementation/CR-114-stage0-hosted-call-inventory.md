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

## Replay gates

- Default leftover-line tool is native Agy print mode (`agy --print`,
  `--json-schema`, `--sandbox`, `--new-project`, `--add-dir` temp workspace,
  `--disable-slash-commands`). The Applyr classifier packet is `prompt.txt`
  in that temp project. Claudexor remains a non-default harness path.
  Factory is excluded.
- 2026-09-17 1-item synthetic Agy extraction and evidence smokes returned
  valid Applyr JSON. No real work-history excerpt on those runs.
- 2026-09-17 8-JD archived schema smoke (`scripts/smoke_stage0_agy_archive.py`,
  switch unset, no SQLite writes, no gold labels): 1219.9s wall.
  Extraction 4 ok / 2 review / 2 exhausted. Evidence 3 ok / 3 review /
  2 exhausted. Silent line loss: false. Review reasons were 120s harness
  timeouts. Exhaustion was the 1200s smoke wall ceiling on the last two
  JDs, not a missing-item drop. `api_cents` stayed null.
- 2026-09-17 rerun of the same 8 JDs with `gemini-3.8-flash-medium`,
  `--effort medium`, packet on stdin, and two sticky Agy sessions
  (extraction then evidence): 199.3s wall, 8/8 extraction ok, 8/8
  evidence ok, silent line loss false. First leftover turn ~35s
  (session start); later leftover turns often 6-15s. This is latency
  evidence, not an accuracy pass. Switch stays off.
- 2026-09-17 leftover contract v2 rerun of the same 8 JDs (switch unset):
  182.0s wall, 8/8 extraction ok, 8/8 evidence ok, silent line loss false.
  Leftover labels: junk 24, required 42, responsibilities 12, preferred 7,
  culture 6 (culture was 39 on v1). Built In chrome dropped before leftover.
  ActBlue expert-trait line labeled required. Acquia AI preferred scored
  evidence level 3 after `aiProjects.md` entered the excerpt (was 0 on v1).
  Not gold. Switch stays off.
- Measured, not enabled: 120s per call is too tight for some leftover and
  evidence batches; 20 minutes is too little for eight JDs at that timeout.
  Numeric production caps are not set. Switch stays off.
- Local archive has hundreds of JDs, but `data/training_data_approved.csv`
  is absent, so there is no adjudicated 30-JD gold set. Gold labels were
  not manufactured.
- 2026-09-17 leftover contract v2 (switch still off): `junk` is a live leftover
  bucket for ATS chrome only, never a culture hook. Trait/expertise lines with
  no duty verb are required. AI leftover evidence retrieval includes
  `data/aiProjects.md` when the line is about agents/LLMs. Keep-in-mind
  visa/onsite/travel is still a later separate lane.
- Production switch remains off. Rollback is: leave
  `APPLYR_STAGE0_SUBSCRIPTION_ADAPTER` unset, keep `data/stage0_classifier.pkl`
  at its current hash, do not promote a candidate.
