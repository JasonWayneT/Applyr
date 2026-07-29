# CR-061: AI-Native Trigger Gap Fix

## Metadata
- **Epic**: Drafting Pipeline Reliability
- **Status**: Implemented
- **Date**: 2026-07-09
- **Source**: `docs/reports/batch2-jd-tailoring-findings.md` defect P-005, confirmed failing on ~13 of ~20 manually-reviewed batch-2 submissions (Cardinal Health, Ceresti Health, Crain Communications, Fleetio, Tropic, PerformYard, Secureframe, OpenRouter, StoneEagle, Tenna, McGraw Hill, Koalafi, Thrivent)

## Problem
JDs that explicitly required AI/LLM fluency ("AI-native," "ship AI features," "prompt engineering," etc.) consistently produced resumes and cover letters with no mention of Jason's real, grounded AI-tooling experience (`workExperience.md` line 44 — daily hands-on use of Claude/Gemini for prompt engineering and agentic tooling, including building this very pipeline). Every fix in the batch-2 log was a human manually writing the same paragraph into the cover letter by hand. Root-caused to two independent gaps, not one:

1. **Resume side**: FR-208 (`build_projects_section`, `local_draft_stages.py`) and its `has_ai_signal` gate already existed, but `draft_compiler.py`'s pruning order stripped the entire PROJECTS section on *any* over-budget render before trimming a single bullet. Given the resume summary-bloat defect this log also documents, resumes were almost always at/over budget at generation time, so the section never survived. 0 of 22 archived resumes had a PROJECTS section at audit time.
2. **Cover letter side**: no mechanism existed at all. `projects_catalog.json` (where the AI project's `cover_story` already lived) was only ever read by the resume renderer; nothing in `cover_letter_plan.py` / `claim_composer.py` / `jd_tailoring.select_cl_claims` touched it, and no equivalent entry existed in `master_claims.json` for `cover_claim_picker.py` to select.

A third, latent bug was found while fixing (2): `pick_cover_proofs`'s metric-density guard forcibly overwrites a selected slot if it lacks a digit. The new AI claim is intentionally metric-free (a qualitative capability claim — inventing a fake number would violate the hard anti-hallucination rules), so it was winning selection on score and then being silently discarded by this guard on every test JD until a targeted exception was added.

A fourth bug, unrelated to the trigger gap but found during verification: all 8 `projects_catalog.json` entries used a literal em-dash in the project name, which would have hard-blocked the linter (`LR-006`) the first time the PROJECTS section ever actually survived to a final resume.

## Decision
- `draft_compiler.py`: reordered the resume pruning loop — trim bullets to each employer's floor first; strip the PROJECTS section only as a last resort if still over budget.
- `local_draft_stages.py`: `build_projects_section` `MAX_PROJECTS` 3 → 1, reducing the section's budget footprint to the single highest-priority (already-approved) project.
- `data/master_claims.json`: added `ACC-401-AITOOLS`, grounded in `workExperience.md` line 44. `"employer": ""` deliberately — `load_employers()` derives the resume's `EMPLOYERS` list from every distinct non-empty `employer` value across the catalog, so a real slug here would have added a 4th resume experience section with no matching header and crashed rendering. An empty employer is excluded from that set (verified: `EMPLOYERS` unchanged after the add) while still flowing normally through `cover_claim_picker.py`'s claim iteration, since its generic render path (`render_proof_body`) uses `cover_story` directly with no employer-name templating for non-legacy claim IDs.
- `cover_claim_picker.py`: added a `has_ai_signal`-gated scoring bonus in `_proof_score` (mirrors the existing `is_product_domain_jd` / `is_connected_devices_jd` / fintech bonus blocks already in this file) and a narrow `_protected_ai_slot` exception in the metric-density guard, scoped to `ACC-401-AITOOLS` on AI-signal JDs only.
- `data/projects_catalog.json`: replaced the em-dash in all 8 project names with a colon.

## Acceptance Criteria
- `scripts/test_ai_signal_routing.py` (new, 5 tests, all passing): AI claim selected on AI-signal JDs, not selected on non-AI JDs, confirmed metric-free, PROJECTS section returns exactly one entry, PROJECTS section output is lint-clean.
- Verified against 15 real archived JDs from this project's own submission history: 12/12 with genuine AI/LLM JD language now select `ACC-401-AITOOLS`; 0/3 without such language do (centegix, thrivent — both correctly have `has_ai_signal() == False`).
- Full relevant suite (`test_cover_claim_picker.py`, `test_claim_preselection.py`, `test_summary_builder.py`, `test_ai_signal_routing.py`): 35/36 passing. The one failure (`test_fintech_jd_prefers_dropoff_story`) is confirmed pre-existing via `git stash` — reproduces identically with none of this CR's changes applied — and unrelated (its fixture JD has no AI signal).

## Out of Scope
- The other repeat defects in the same batch-2 log (Z2S metric stripping, intermittent CORE COMPETENCIES section drop, resume-summary sentence stacking / `CW-013`, cross-company duplicate cover-letter hooks, "worked AT the target company" employer hallucination, missing cover-letter transparency guard for hard domain-requirement gaps). Each is a distinct root cause and was not investigated as part of this CR.
- Whether `ACC-401-AITOOLS` should also get a formal resume bullet slot outside the PROJECTS section — deliberately left resume-bullet-inert (`employer: ""`) this round; revisit only with a real, non-fabricated metric to anchor it if one becomes available.
