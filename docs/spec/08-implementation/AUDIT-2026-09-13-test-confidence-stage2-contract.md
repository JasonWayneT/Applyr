---
title: Test-Confidence and Stage 2 Contract Audit (Amended)
created: 2026-09-13
amended: 2026-09-13
author: Droid (independent read-only audit)
branch: cr112-test-confidence-audit
worktree: C:\Users\Jason\Desktop\Jason\Resource\CodeProjects\Applyr-audit
audited_head: b5616c8
candidate_head: a435a80 (cr112-integrated-validation-candidate, not audited — read-only inspection)
status: amended_complete
coordination: Read-only. Does not modify Cursor-owned branches, code, docs, or production data.
---

# Test-Confidence and Stage 2 Contract Audit (Amended)

## Amendment Summary

The original audit was based on HEAD `b5616c8`, which predates accepted CR-112 work on `cr112-integrated-validation-candidate` (`a435a80`). This amendment:

1. Corrects temporal scope — distinguishes findings true at audited HEAD, findings closed on the later candidate, findings still likely open, and findings requiring revalidation.
2. Resolves the test-failure contradiction — classifies each of the five failing scripts accurately instead of blanket-calling them "environment-related."
3. Reclassifies the 42 omitted test scripts into six categories instead of recommending blind addition.
4. Reports a focused HM critical-read investigation against production code.
5. Separates intentional workflow-orchestration mocking from genuinely untested invariants.
6. Reprioritizes likely-open findings.
7. Recommends a single narrow next story that does not duplicate Cursor.

**Do not implement RS-01 from the original report.** Rubric floors were implemented and QA-passed in Story 8.1 on the candidate.

## Environment

| Item | Value |
|---|---|
| Audit worktree | `C:\Users\Jason\Desktop\Jason\Resource\CodeProjects\Applyr-audit` |
| Audit branch | `cr112-test-confidence-audit` |
| Audited HEAD | `b5616c8` (pre-integration) |
| Candidate HEAD inspected | `a435a80` (`cr112-integrated-validation-candidate`) — read-only, not audited |
| Python | 3.14.5 via main repo `.venv` |
| Date | 2026-09-13 |

## Exact Commands and Results

### 1. Adversarial pressure test (at audited HEAD `b5616c8`)

```
$ python scripts/run_adversarial_pressure_test.py
Results: 13/13 passed (0 fail/error, SKIPPED excluded)
```

### 2. Full Python test suite (at audited HEAD `b5616c8`)

```
$ python scripts/run_all_tests.py --python-only
54 passed, 5 failed, Total Time: 200.82s
OVERALL RESULT: FAILURE
```

### 3. Adversarial honesty tests

```
$ python -m unittest scripts.test_cr112_adversarial
4 tests, all PASS
```

### 4. Candidate inspection (read-only, `a435a80`)

No tests were run against the candidate. Production code and test files were read to determine which audit findings are closed.

---

## 1. Corrected Temporal Scope

### Findings closed on the candidate (`a435a80`)

| Original finding | Closed by | Evidence on candidate |
|---|---|---|
| **FC-01: Rubric threshold enforcement unproven** | Story 8.1 (FR-318 / AC-415) | `contracts.py:110-150` defines `RUBRIC_FLOOR_RESUME=70`, `RUBRIC_FLOOR_COVER_LETTER=65`, `check_rubric_floors()`. Called from `check_draft_manifest`, `check_finalize_ready`, `check_stage2_ready`. `runner.py:1333-1357` emits BLOCK `mech.rubric_floor.*` findings. `runner.py:1727` `_require_completion_rubric_floors` called from `run_stage2_policy`. Tests: `test_contracts.py:377-404` (68/69 fails, 69.9 fails, 70/65 passes, NaN fails, missing-score is shape not floor). `test_workflow_authority.py:1351-1470` (practice/production below-floor raises, force cannot skip, exact-floor passes, stage2 policy does not mint COMPLETE). |
| **FC-13 (original): Missing identity produces placeholder** | Story 8.2 (SEC-006 / AC-416) | `utils.py` `_DEFAULT_IDENTITY` renamed to `_SYNTHETIC_IDENTITY`, only returned when `APPLYR_SYNTHETIC_IDENTITY=1`. `load_identity_profile()` reads WE or raises `IdentityError`; no SQLite fallback. `_apply_resume_header_if_available` returns FAIL (not SKIP) when identity missing. `quality_checker._candidate_name_upper` removed `or "John Doe"` fallback. `test_practice_identity.py` with 12+ tests covering missing/synthetic/WE sources, no-PII logging, verify-only fail, quality_checker fallback removal. `test_practice_identity.py` is in candidate's `run_all_tests.py`. |

**Do not claim the current candidate lacks rubric-floor enforcement or privacy-safe practice identity. Both are implemented, tested, and in the canonical runner.**

### Findings still likely open on the candidate

| Finding | Why likely still open | Revalidation needed |
|---|---|---|
| **FC-02: HM critical read can be silently self-certified** | The HM finding (`hm.critical_read`) is a WARN that goes through `evaluate_truth_findings`. `ACCEPTED_AS_CORRECT` requires reasoning >= 10 chars, but `RESOLVED_EDIT` and `NOT_APPLICABLE` require no reasoning. No document hashes, quoted spans, JD relevance, or reviewer identity in the finding. Same agent can self-certify. See Section 5 for full investigation. | Confirm no Story post-8.2 added HM substance requirements. |
| **FC-04: `--resume` idempotency unproven** | No test found at either HEAD. | Confirm candidate has not added an idempotency test. |
| **FC-09: Production-path cost pause unproven** | CR-112 Story 7.1 is planned but blocked on Epic 3 integration review. | Confirm Story 7.1 has not landed. |
| **FC-03 (partially): Omitted test scripts** | Candidate added `test_practice_identity.py` to runner. Most of the 42 omitted scripts are likely still absent. | Diff candidate's `run_all_tests.py` against audited HEAD's. |

### Findings requiring revalidation against the candidate

| Finding | Why revalidation is needed |
|---|---|
| **FC-05: Stage 2 workflow tests mock every production check** | The candidate's `test_workflow_authority.py` may have added integration tests that exercise real check functions. The rubric-floor tests on the candidate do call real `contracts.check_rubric_floors` through the workflow path. |
| **FC-07: Fixture-tier adversarial cases use non-production assertions** | The candidate may have improved fixture handlers. |
| **FC-08: One-page enforcement in workflow path** | The candidate's Mech stage may now exercise real `verify_one` with page-count checks. |
| **FC-11: LR-014/LR-015 have no dedicated unit test** | The candidate may have added linter tests for these rules. |

---

## 2. Accurate Classification of All Five Failing Scripts

The original report's summary said "all five failures were environment-related." That was incorrect. The body identified a fixture defect in `test_workflow_authority.py` but the summary contradicted it. Here is the accurate classification.

| # | Script | Error count | Root cause | Classification | Should in canonical no-paid run? |
|---|---|---:|---|---|---|
| 1 | `test_workflow_authority.py` | 2 errors | `Stage0MissingReceiptDoesNotReExtractTests`: `run_until_stage1_complete` calls `run_stage1_prompt` which calls `build_packet` on a folder with no `authoring_packet.json`. The test setUp writes only `stage0_fit_gate.json` and `Original_JD.txt` — no pre-built packet, no mock for `build_packet`. The real packet builder fails with "Required item unmapped (no claims, no bridge): Own roadmap." | **Defective/incomplete fixture** — the test needs to either mock `build_packet` or provide a pre-built `authoring_packet.json`. Not environment-related. | **Should pass** after fixture fix. |
| 2 | `test_build_stage0_fit_gate.py` | 9 errors, 5 skipped | 7 errors: `batch_report` / `build_stage0_fit_gate` calls `evaluate_db_gate` → `sqlite3.OperationalError: no such table: jobs` (production SQLite not in worktree). 2 errors: `TestPrefsGateObservability` expects `build_stage0_fit_gate` to return a result, but production code now raises `Stage0NeedsInput` for Review Center confirmations. 5 skipped: `TestCompoundClauseSplitting` — CR-093 removed `_split_compound_item`; tests are intentionally obsolete. | **Missing required dependency** (7 errors: SQLite) + **stale test expectation** (2 errors: Stage0NeedsInput) + **obsolete tests** (5 skipped). | 7 SQLite errors: **should skip** with capability check or use temp DB. 2 stale expectations: **should fail** (test needs update). 5 skipped: **should be removed**. |
| 3 | `test_smoke_regression.py` | 1 fail | REG-22 runs `npx vitest` but `vite` package is not installed in the worktree. | **Missing optional dependency** (npm dev dependencies). | **Should skip** with npm-capability check. |
| 4 | `test_stage0_provider_golden.py` | 1 error | `FileNotFoundError` for `data/fit_rubric_golden_set.json` — file is under gitignored `data/` directory, not in worktree. | **Missing required dependency** (gitignored golden file). | **Should skip** with file-existence check. |
| 5 | `test_stage0_confirmations.py` | 1 error | `test_workflow_pauses_then_resumes_after_hard_gate_answer` calls `run_stage0` → `build_stage0_fit_gate` → `evaluate_db_gate` → `sqlite3.OperationalError: no such table: jobs`. | **Missing required dependency** (SQLite). | **Should skip** with capability check or use temp DB. |

### Summary of failure classification

| Classification | Count | Scripts |
|---|---:|---|
| Defective/incomplete fixture | 1 | `test_workflow_authority.py` |
| Missing required dependency (SQLite) | 2 | `test_build_stage0_fit_gate.py` (7 of 9 errors), `test_stage0_confirmations.py` |
| Stale test expectation | 1 | `test_build_stage0_fit_gate.py` (2 of 9 errors) |
| Obsolete tests (should be removed) | 1 | `test_build_stage0_fit_gate.py` (5 skipped) |
| Missing optional dependency (npm) | 1 | `test_smoke_regression.py` |
| Missing required dependency (gitignored file) | 1 | `test_stage0_provider_golden.py` |

**The original summary's claim that "all five failures were environmental" was wrong.** `test_workflow_authority.py` has a fixture defect, and `test_build_stage0_fit_gate.py` has stale test expectations mixed with environment issues.

---

## 3. Classification of All 42 Omitted Test Scripts

The original report recommended adding "the 10 priority scripts" to the runner. That was too blunt. Here is the full classification.

### Category 1: Deterministic unit test — belongs in the default runner

| Script | What it tests | Runtime | Side effects |
|---|---|---|---|
| `test_archive_submission.py` | Stale-PDF hash warning behavior | Fast | Temp files |
| `test_audit_improve_native.py` | Native resume/cover hard-fact, metric, sentence-count checks | Fast | In-process module global |
| `test_bullet_fit_enforce.py` | Bullet word-budget enforcement | Fast | None |
| `test_check_ground_truth_coverage.py` | Provenance claim loading and coverage fallback | Fast | Temp files, mocked catalog |
| `test_check_instruction_drift.py` | Instruction/pointer layout drift detection | Fast | Temp files |
| `test_claim_preselection.py` | Claim scoring, disabled claims, rarity, breadth dampening | Fast | None (pytest, mocked) |
| `test_company_slug.py` | Company-name extraction and slug fallback | Fast | Temp files |
| `test_cover_letter_slots.py` | Hook validation, slot generation, critic/retry, assembly | Fast | None (LLM mocked) |
| `test_extract_job_title_line.py` | Job-title extraction rejecting ATS chrome | Fast | None |
| `test_gap_detector.py` | Domain-gap classification, soft-gap detection | Fast | None |
| `test_import_csv_to_submissions.py` | UTF-8 stdout/stderr reconfiguration regression | Fast | Mutates process encoding |
| `test_industry_semantic.py` | LLM industry classification, JD validation (LLM mocked) | Fast | None |
| `test_jd_profile_keywords.py` | Frequency-sorted JD keyword extraction | Fast | None |
| `test_jd_profile_requirements.py` | Requirements-section heading extraction | Fast | None |
| `test_jd_term_extractor.py` | Stemmed JD/resume term matching, ATS contracts | Fast | None (pytest, mocked) |
| `test_local_rewrite.py` | Rewrite grounding gates and escalation/fallback | Fast | Writes fallback log |
| `test_location_placeholder.py` | Resume/cover `[Location]` placeholder rejection | Fast | Temp files |
| `test_pipeline_env.py` | Stage-0 cascade environment flag always-on | Fast | Temp env changes |
| `test_stage0_direct_evidence_shadow.py` | Direct evidence phrase matching and LLM-agreement shadow | Fast | None |
| `test_stage0_extract.py` | JD cleaning, candidate harvesting, stable IDs | Fast | None |
| `test_utils_header_casing.py` | Contact-header name casing and placeholder formatting | Fast | None |
| `test_verify_submission.py` | Header placeholders, PDF parsing fields, ATS contracts | Fast | Temp files, PDF subprocess mocked |

**Recommendation: add all 22 to the default runner.** They are deterministic, fast, and test production functions directly. None requires network, paid APIs, or production SQLite.

### Category 2: Deterministic integration test — belongs in the default runner

| Script | What it tests | Runtime | Side effects |
|---|---|---|---|
| `test_ai_signal_routing.py` | AI-signal claim/project routing and linter compatibility | Fast | Reads repo catalog |
| `test_check_finalize_ready.py` | Real CLI JSON contract, forged/stale manifest rejection (subprocess) | Fast | Temp files |
| `test_conversion_framing.py` | Sterkly narrative/context enforcement and coherence | Fast | None |
| `test_cover_claim_picker.py` | Cover proof deduplication, ranking, fintech detection | Fast | Reads catalog |
| `test_cover_structure_universal.py` | Analytics/adoption archetype, proof bridge, rendering | Fast | Reads catalog |
| `test_cover_word_padding.py` | Cover-letter word minimums, proof fallback | Fast | Reads optional fixture |
| `test_generate_authoring_rule_digest.py` | Digest generation/versioning, packet version stamping | Fast | Temp files |
| `test_stage0_checkpoint.py` | Stage-0 run/judgment checkpoints, atomic spool writing | Fast | Temp SQLite/spool |
| `test_stage0_db_gate.py` | Job/company matching, cooldowns, DB gate (in-memory SQLite) | Fast | In-memory DB only |
| `test_summary_builder.py` | Deterministic summary construction + optional adaptive tests | Fast | None |
| `test_verify_editor_save.py` | Editor-save CLI argument-count contract (subprocess) | Fast | Temp folder |
| `test_voc_map.py` | Codename replacement, catalog sanitization, linter validation | Fast | Reads repo data |

**Recommendation: add all 12 to the default runner.** They are deterministic integration tests that exercise real CLI boundaries or real production modules. `test_stage0_db_gate.py` uses in-memory SQLite only (no production DB). `test_check_finalize_ready.py` is the only subprocess test for the finalize gate and is critical.

### Category 3: Slow suite — suitable for a separate extended runner

| Script | What it tests | Runtime | Side effects |
|---|---|---|---|
| `test_stage0_extraction_corpus.py` | Corpus ratchet for extraction starvation across archived JDs | Slow | Reads hundreds of archived JDs; skips when absent |

**Recommendation: add to an extended runner, not the default.** Explicitly skips when corpus is absent, which is correct behavior.

### Category 4: Environment-dependent — requires explicit capability check

| Script | What it tests | Dependencies | Side effects |
|---|---|---|---|
| `test_cover_dignifi.py` | Dignifi domain-first cover archetype | Private `data/submissions/dignifi/Original_JD.txt` | Reads private fixture |
| `test_cover_everbridge.py` | Everbridge connected-devices archetype | Private `data/submissions/everbridge/Original_JD.txt` | Reads private fixture |
| `test_cover_splash_golden.py` | Splash marketplace-fintech golden structure | Private `data/submissions/splash_financial/Original_JD.txt` | Reads private fixture |
| `test_verify_submission_integration.py` | Baseline receipt comparison | Missing `data/test_baselines.json` + populated `data/submissions/` | Writes `verification_receipt.json` into submission folders |

**Recommendation: add with file-existence skip guards.** These tests are valuable when their fixtures exist but must skip cleanly when private data is absent. `test_verify_submission_integration.py` writes into submission folders and should never run in CI without explicit setup.

### Category 5: Paid/provider-dependent — must never run by default

| Script | What it tests | Dependencies | Side effects |
|---|---|---|---|
| `test_llm.py` | Live Gemini connectivity and fixed-response generation | `jobagent.sqlite`, Gemini API/key, network | Sends paid API request |
| `test_stage0_archive_replay.py` | Stage-0 cascade replay against archived JDs | Archived private JDs, `workExperience.md`, SQLite, Groq/Gemini APIs | Real API calls; writes results JSON; sleeps between JDs |

**Recommendation: never add to the default runner.** These make real paid API calls. They belong in a separately gated suite that requires explicit provider configuration and budget authorization.

### Category 6: Obsolete, duplicate, diagnostic, or incorrectly named

| Script | What it tests | Why obsolete |
|---|---|---|
| `test_pm_report_audit.py` | Cover-letter forbidden opener and buzzword audit | Diagnostic script, not a regression test. Overlaps with `test_submission_linter.py` and `test_cover_voice.py` which are already in the runner. |

**Recommendation: do not add.** Coverage is already provided by existing runner tests.

### Smallest high-value additions

Rather than adding 10 scripts blindly, the smallest high-value set is:

1. **`test_check_finalize_ready.py`** (Cat 2) — only subprocess test for the finalize gate. Tests forged-manifest rejection via the real CLI boundary.
2. **`test_verify_submission.py`** (Cat 1) — ATS parseability, header placeholders, packet ATS contract. No mocks around the behavior under test.
3. **`test_check_ground_truth_coverage.py`** (Cat 1) — provenance cross-reference. The coverage heuristic has no other test in the runner.
4. **`test_jd_term_extractor.py`** (Cat 1) — ATS term extraction. No other test in the runner covers this.
5. **`test_voc_map.py`** (Cat 2) — codename replacement. Directly tests the anti-hallucination VOC translation.

These 5 are fast, deterministic, have no external dependencies, and fill gaps not covered by any script already in the runner. Adding them would bring the runner from 59 to 64 scripts with no environment risk.

---

## 4. Current Likely-Open Findings (Reprioritized)

Findings are reprioritized based on the candidate inspection. Closed findings are removed from the active list.

### P0: FC-02 — HM critical read can be silently self-certified

**Status: Likely open on candidate.**

See Section 5 for the full investigation. Summary: the `hm.critical_read` finding is a WARN that goes through `evaluate_truth_findings`. `ACCEPTED_AS_CORRECT` requires reasoning >= 10 chars (trivially minimal), `RESOLVED_EDIT` and `NOT_APPLICABLE` require no reasoning at all. No document hashes, quoted spans, JD relevance, or reviewer identity in the finding. The same authoring agent can self-certify its own work.

### P1: FC-04 — `--resume` idempotency unproven

**Status: Likely open on candidate.**

No test at either HEAD runs `--resume` twice and asserts state stability. A non-idempotent `--resume` could re-run checks, overwrite receipts, or transition state backwards.

### P1: FC-03 (partial) — Omitted test scripts

**Status: Partially addressed on candidate (test_practice_identity added).**

42 scripts remain absent from the audited HEAD's runner. The candidate added `test_practice_identity.py`. The 5 smallest high-value additions identified in Section 3 should be evaluated against the candidate's current runner list before implementation.

### P2: FC-09 — Production-path cost pause unproven

**Status: Likely open — Story 7.1 planned but blocked.**

The eval harness proves zero paid calls in eval mode. No test proves the production `run_submission.py` path pauses instead of calling a paid provider when no eligible provider exists.

### P2: FC-05 — Stage 2 workflow tests mock production check functions

**Status: Partially addressed on candidate (rubric-floor tests call real `contracts.check_rubric_floors`).**

The candidate's rubric-floor tests do exercise real contract functions through the workflow path. However, Truth, ATS, HM, and Mech subphase tests still mock `check_claim_provenance`, `check_ground_truth_folder`, `check_jd_term_folder`, `submission_linter.lint_folder`, and `verify_one`. This is **intentional** — these tests prove the state machine, not the check functions. The check functions have their own unit tests. The gap is that no test proves the state machine correctly invokes the real check functions and correctly interprets their real output. This is an integration test gap, not a unit test gap.

**Important distinction:** Mocking workflow orchestration is not the same as the invariant being untested. The state machine's transition logic (NEEDS_DISPOSITION → COMPLETE on disposition, FAILED on BLOCK, etc.) is what these tests prove. The check functions' ability to catch real defects is what their own unit tests prove. The gap is the wiring between them — does `run_stage2_truth` actually call `check_claim_provenance` and interpret its result correctly? That wiring is tested only through mocks.

### Findings requiring revalidation (not classified as open or closed)

| Finding | Action needed |
|---|---|
| FC-07: Fixture-tier adversarial discrimination | Check candidate's `run_adversarial_pressure_test.py` fixture handlers |
| FC-08: One-page enforcement in workflow | Check candidate's Mech stage tests |
| FC-11: LR-014/LR-015 unit tests | Check candidate's `test_submission_linter.py` |
| FC-06: Baseline comparison circularity | Check whether candidate changed `test_verify_submission_integration.py` |

---

## 5. Focused HM Critical-Read Investigation

### Production code path (both HEADs)

1. `collect_hm_findings(folder)` in `workflow/runner.py` builds the findings document. It runs `submission_linter.lint_folder(folder)` for mechanical lint signals, then appends a single finding:
   ```python
   {
       "id": "hm.critical_read",
       "source": "workflow",
       "severity": "WARN",
       "message": "Confirm a hiring-manager read of Resume.md + CoverLetter.md "
                  "(conversion_rubric C1–C5 / qualitative Pass 3). "
                  "Dispose ACCEPTED_AS_CORRECT when done.",
   }
   ```

2. `run_stage2_hm` calls `_apply_subphase_verdict(folder, state, phase="hm", findings_doc=findings_doc, ...)`.

3. `_apply_subphase_verdict` calls `sync_dispositions_for_phase(folder, "hm", findings_doc)` which:
   - Creates null disposition slots for each finding id.
   - Binds the findings content hash to the `hm` phase.
   - If the findings hash changed since last run, clears all hm dispositions to null (stale-disposition invalidation).

4. `_apply_subphase_verdict` calls `policy.evaluate_truth_findings(findings_doc, dispositions)` which iterates each finding:
   - `hm.critical_read` has `severity: "WARN"`.
   - If no disposition exists → `NEEDS_DISPOSITION` (workflow halts).
   - If disposition is `ACCEPTED_AS_CORRECT` → checks `REASONING_REQUIRED` set (yes, `ACCEPTED_AS_CORRECT` is in it) → requires `reasoning` with `len >= REASONING_MIN_CHARS` (10 chars).
   - If disposition is `RESOLVED_EDIT` → **not in `REASONING_REQUIRED`** → passes with no reasoning.
   - If disposition is `NOT_APPLICABLE` → **not in `REASONING_REQUIRED`** → passes with no reasoning.
   - If disposition is `FALSE_POSITIVE` → in `REASONING_REQUIRED` → requires 10+ chars reasoning.
   - If disposition is `HUMAN_ACCEPTED_RISK` → in `REASONING_REQUIRED` → requires 10+ chars reasoning. But `HUMAN_ACCEPTED_RISK` on a WARN is in `OVERRIDE_DISPOSITIONS`, so integrity becomes `OVERRIDDEN`.

5. If all findings pass → `hm` subphase status = `COMPLETE`, `mech` subphase = `READY`.

### What artifact proves `hm.critical_read` occurred?

**The `reviews/hm_findings.json` file.** It contains the findings document with `hm.critical_read` and any lint findings. The `reviews/dispositions.json` file contains the disposition for `hm.critical_read` and the `bound_findings_hashes.hm` hash.

### Does the reviewer must cite actual resume, cover-letter, and JD text?

**No.** The finding message says "Confirm a hiring-manager read of Resume.md + CoverLetter.md" but the disposition requires only a string >= 10 chars. There is no mechanism to verify that the reviewer actually read the documents. No quoted spans, no document hashes, no JD references are required in the disposition reasoning.

### Can a bare or templated `ACCEPTED_AS_CORRECT` disposition clear it?

- Bare string `"ACCEPTED_AS_CORRECT"` (no reasoning) → **does NOT clear** (needs disposition). `parse_disposition` returns `(ACCEPTED_AS_CORRECT, None)`, and `REASONING_REQUIRED` check fails because `reasoning` is `None`.
- `{"disposition": "ACCEPTED_AS_CORRECT", "reasoning": "looks fine"}` (10 chars) → **clears**. "looks fine" is exactly 10 chars.
- `{"disposition": "ACCEPTED_AS_CORRECT", "reasoning": "documents reviewed and acceptable"}` → **clears**.

**But:** `{"disposition": "RESOLVED_EDIT"}` (bare string, no reasoning) → **clears** with no reasoning required. `{"disposition": "NOT_APPLICABLE"}` (bare string) → **clears** with no reasoning required.

### Can the same authoring agent silently certify its own work?

**Yes.** There is no reviewer identity, role, or session separation in the disposition or the findings document. The workflow does not distinguish between "the authoring agent disposed this" and "a separate reviewer disposed this." The finding message itself instructs "Dispose ACCEPTED_AS_CORRECT when done" — guiding whoever is running `--resume` to self-certify.

The AGENTS.md prose says the drafting agent must not silently self-dispose `hm.critical_read` as `ACCEPTED_AS_CORRECT` without a genuine qualitative read. But this is a prose rule, not a mechanical gate. The policy function does not check who is disposing.

### Would reasoning length alone provide meaningful protection?

**No.** `REASONING_MIN_CHARS = 10` is trivially minimal. "looks fine" (10 chars) passes. A templated phrase like "reviewed and acceptable" (23 chars) passes. Character count does not prove judgment quality. A determined agent can always produce 10 characters of filler.

The existing Truth findings have the same 10-char minimum, but Truth findings are backed by concrete claim IDs and coverage checks that can be mechanically verified. HM findings have no such mechanical backing — the entire value of the HM read is qualitative judgment, which character count cannot measure.

### Do stale HM dispositions survive document changes?

**Partially.** The `sync_dispositions_for_phase` function invalidates hm dispositions when the findings content hash changes. But `hm.critical_read` is always the same finding with the same message — its hash only changes if the lint findings (blocks/warns) change. If an agent edits Resume.md after disposing `hm.critical_read` but the lint results don't change, the hm disposition survives.

However, the Stage 1 freshness check (`_require_stage1_fresh` in `run_stage2_hm`) does catch Resume.md/CoverLetter.md edits after Stage 1 COMPLETE — it compares receipt output hashes against on-disk bytes. So an edit between Stage 1 COMPLETE and the HM run would cause Stage 1 to go STALE, which locks Stage 2. The disposition cannot survive a document edit that reaches the workflow.

The gap is: the agent can dispose `hm.critical_read`, re-run HM (same findings hash), and complete — all without any document change. The self-certification path requires no edit, so no stale check fires.

### Does receipt hashing invalidate HM approval after document changes?

**Yes, indirectly.** The Stage 2 COMPLETE receipt records `output_hashes` for `Resume.md`, `CoverLetter.md`, and `verification_receipt.json`. If documents change after Stage 2 COMPLETE, `check_workflow_complete` detects the hash mismatch and returns False. But this is after HM — it protects against post-completion edits, not against self-certification during HM.

### Do practice and production use the same HM contract?

**Yes.** `run_stage2_hm` is the same function for both modes. The mode only affects Stage 3 (practice does not write to DB). The HM findings, dispositions, and policy evaluation are identical.

### Proposed narrow acceptance contract for HM review substance

Instead of character count, require structured finding evidence that can be mechanically verified without pretending to judge judgment quality:

```json
{
  "disposition": "ACCEPTED_AS_CORRECT",
  "reasoning": "Documents read in full. Resume summary is 3 sentences. Cover letter opens with company-specific hook. No forbidden punctuation.",
  "review_evidence": {
    "reviewed_document_hashes": {
      "Resume.md": "<sha256 of Resume.md at review time>",
      "CoverLetter.md": "<sha256 of CoverLetter.md at review time>"
    },
    "observations": [
      {
        "document": "Resume.md",
        "location": "PROFESSIONAL SUMMARY",
        "observation": "3 sentences, positions platform PM experience",
        "jd_relevance": "JD requires 'Own roadmap' — summary references roadmap ownership"
      },
      {
        "document": "CoverLetter.md",
        "location": "opening paragraph",
        "observation": "Opens with company-specific product challenge, not generic enthusiasm",
        "jd_relevance": "JD emphasizes platform scaling — hook references scaling"
      }
    ],
    "verdict": "pass",
    "reviewer_context": "drafting_agent_post_author"
  }
}
```

**What this proves mechanically:**
- `reviewed_document_hashes` bind the disposition to specific document bytes. If documents change, the hash mismatch invalidates the disposition (defense in depth beyond the findings content hash).
- `observations` require at least one entry per document (Resume + CoverLetter), each naming a location and a JD-relevance statement. This is structurally harder to fake than 10 chars of filler.
- `reviewer_context` makes the self-certification explicit rather than hidden. An agent that writes `"drafting_agent_post_author"` is at least being honest that it reviewed its own work.

**What this does NOT prove:**
- That the reviewer actually exercised judgment.
- That the observations are correct.

**What this prevents:**
- A bare `RESOLVED_EDIT` with zero evidence clearing the finding.
- A 10-character filler string clearing the finding.
- A disposition surviving after documents are edited (hash binding).

**Implementation constraint:** Keep this harness-agnostic. Do not require Claude-specific agents, subagent mechanisms, or session identity. The `reviewer_context` field is a self-declared string, not a cryptographic identity. The value is making the self-certification visible and auditable, not preventing it entirely — preventing it would require a separate reviewer, which is a product decision (ladder-2 review), not a test-confidence fix.

---

## 6. Adversarial and Stage 2 Coverage — Retained Findings Only

For every retained finding, the test can pass while its named invariant is broken.

### Retained: FC-02 (HM self-certification)

| Item | Detail |
|---|---|
| Exact production function | `workflow.policy.evaluate_truth_findings` (called from `_apply_subphase_verdict` for phase="hm") |
| Specific assertion | `test_hm_requires_critical_read_disposition`: asserts `NEEDS_DISPOSITION` when no disposition exists. `test_stage2_receipt_after_policy`: asserts `COMPLETE` when `ACCEPTED_AS_CORRECT` with reasoning "critical read finding is a style preference not a defect" (51 chars). |
| Missing negative control | No test proves a bare `RESOLVED_EDIT` (no reasoning) cannot clear `hm.critical_read`. No test proves 10-char filler ("looks fine") cannot clear it. No test proves the same agent cannot self-certify. |
| Mutation that would incorrectly pass | Dispose `hm.critical_read` as `RESOLVED_EDIT` (bare string, no reasoning). The policy function does not require reasoning for `RESOLVED_EDIT`. The test `test_stage2_receipt_after_policy` would still pass because it uses `ACCEPTED_AS_CORRECT` with reasoning — it never tests the `RESOLVED_EDIT` path for HM. An agent could use `RESOLVED_EDIT` to clear the HM finding with zero evidence of any review. |

### Retained: FC-04 (--resume idempotency)

| Item | Detail |
|---|---|
| Exact production function | `workflow.runner.run_until_truth_settled` / `run_stage2_*` / `run_stage3_finalize` (all called via `run_submission.py --resume`) |
| Specific assertion | None — no test exists. |
| Missing negative control | N/A — no test to be a negative control for. |
| Mutation that would incorrectly pass | N/A — the absence of a test means any non-idempotent behavior is unproven. |

### Not retained: FC-05 (Stage 2 mocking)

**Reason:** Mocking workflow orchestration is intentional and correct for state-machine tests. The check functions (`check_claim_provenance`, `check_ground_truth_folder`, `check_jd_term_folder`, `submission_linter.lint_folder`, `verify_one`) each have their own unit tests that exercise real defect detection. The state machine tests prove transition logic. The gap is integration (wiring between state machine and check functions), which is a different class of risk than "the invariant is untested." The invariant "does the check function catch defects" IS tested — in the check function's own test file. The invariant "does the state machine interpret the check result correctly" IS tested — in the workflow test file with mocks. The remaining gap is "does the real check function's output flow through the real state machine correctly" — an integration test, not a unit-test confidence issue.

### Not retained: FC-07 (fixture-tier adversarial discrimination)

**Reason:** The programmatic cases are authoritative. The fixture cases are explicitly labeled as "fixture-tier smoke only" in the runner code (`run_adversarial_pressure_test.py` line 117: "Fixture-tier smoke only: any hard block is enough. Programmatic case_doc_003_negative / check_doc_003_forbidden_punctuation are the authoritative LR-014/LR-015 coverage."). The fixture tier cannot pass while the invariant is broken because the programmatic tier would fail. The fixture tier's weakness is that it could pass for the wrong reason, but it cannot give false confidence about the invariant because the programmatic tier covers the same invariant authoritatively.

### Not retained: FC-01 (rubric floors)

**Reason:** Closed on candidate by Story 8.1. See Section 1.

---

## 7. Smallest Recommended Next Test-Confidence Story

### RS-02: HM critical-read disposition substance contract

**Do not implement RS-01.** Rubric floors are closed.

**Invariant:** `hm.critical_read` disposition must require structured review evidence, not just a 10-character string. `RESOLVED_EDIT` and `NOT_APPLICABLE` on `hm.critical_read` must also require justification.

**Scope:** Test-only story. No production code changes. Create the test, watch it fail against current production code, then propose the production change as a separate story for Cursor or Jason to accept.

**Test fixture:**

1. Build a temp folder through Stage 2 HM entry (reuse the existing mock chain from `test_workflow_authority.py`).
2. Run `run_stage2_hm` — assert `NEEDS_DISPOSITION` for `hm.critical_read`.
3. Dispose `hm.critical_read` as `RESOLVED_EDIT` (bare string, no reasoning) — assert `evaluate_truth_findings` returns `PASS` (this is the bug: it should not pass without evidence).
4. Dispose as `ACCEPTED_AS_CORRECT` with reasoning "looks fine" (10 chars) — assert `PASS` (this is the weakness: 10 chars is not substance).
5. Dispose as `ACCEPTED_AS_CORRECT` with reasoning "Documents read. Resume summary is 3 sentences. Cover letter opens with company-specific hook." — assert `PASS` (this is what should be required).

**What the test proves:** Steps 3 and 4 should fail (the invariant is that HM review requires substance), but they pass today. The test documents the gap.

**Proposed production change (separate story, not this one):**

Add `hm.critical_read` to a new `STRUCTURED_REASONING_REQUIRED` set in `policy.py` that requires:
- At least one observation per document (Resume + CoverLetter).
- Each observation names a document, location, and JD-relevance statement.
- `reviewed_document_hashes` field binding the disposition to specific bytes.

**Do not implement the production change in this audit.** Propose it as a story for Cursor or Jason to accept.

**Dependencies:** None. Does not duplicate Cursor's work (Cursor owns Vanta JD 2, digest efficacy, extraction-review idempotency, evidence-ranking design — none of which is HM disposition substance).

**Priority:** P0. This is the strongest likely-open finding. It is the exact F8 concern from the CR-112 investigation: `hm.critical_read` is a WARN placeholder, not a semantic review, and the drafting agent can auto-dispose it without ever actually reading the documents.

---

## 8. Explicit Statement of What Remains Unproven

1. **HM critical read substance is unproven.** `hm.critical_read` can be cleared with `RESOLVED_EDIT` (no reasoning) or `ACCEPTED_AS_CORRECT` with 10 chars of filler. No document hashes, quoted spans, JD relevance, or reviewer identity are required. The same authoring agent can self-certify. This is likely open on the candidate.

2. **`--resume` idempotency is unproven.** No test at either HEAD runs `--resume` twice and asserts state stability. This is likely open on the candidate.

3. **Production-path cost pause is unproven.** CR-112 Story 7.1 is planned but blocked. The production `run_submission.py` path's behavior when no eligible provider exists is untested. This is likely open.

4. **Integration between state machine and real check functions is unproven.** Stage 2 subphase tests mock check functions. Each check function has its own unit tests, but no test proves the real check output flows through the real state machine correctly. This is an integration gap, not a unit-test gap. It requires revalidation against the candidate.

5. **42 test scripts are absent from the audited HEAD's runner.** The candidate added `test_practice_identity.py`. The remaining gap requires diffing the candidate's runner list against the audited HEAD's. The 5 smallest high-value additions are identified in Section 3.

6. **Rubric floor enforcement was unproven at audited HEAD `b5616c8`** but is **closed on candidate `a435a80`** by Story 8.1. Do not re-investigate without confirming the candidate's test suite.

7. **Practice identity placeholder was a defect at audited HEAD** but is **closed on candidate** by Story 8.2. Do not re-investigate without confirming the candidate's test suite.

8. **The five test failures at audited HEAD include one defective fixture** (`test_workflow_authority.py`: missing packet mock) and **two stale test expectations** (`test_build_stage0_fit_gate.py`: `Stage0NeedsInput` now raised where test expects return). These are not purely environmental and should be corrected regardless of which branch they run on.

---

## 9. Proposed Backlog Amendment (Revised)

The original report proposed an Epic "Test-Confidence Hardening (CR-113 candidate)" with 8 stories. The revised proposal removes RS-01 (closed by Story 8.1) and refocuses on the HM critical-read contract.

### Proposed Story TC-02: HM critical-read disposition substance contract

**Invariant:** `hm.critical_read` disposition must require structured review evidence. `RESOLVED_EDIT` and `NOT_APPLICABLE` on `hm.critical_read` must require reasoning. Character count alone is not sufficient — require at least one structured observation per document with document/location/JD-relevance fields and reviewed document hashes.

**Test (this story):** Create the test that documents the gap. Watch it fail. Do not implement the production fix.

**Production fix (separate story):** Add `hm.critical_read` to a structured-reasoning requirement in `policy.py`. Keep harness-agnostic. Do not require Claude-specific agents or subagent mechanisms.

**Priority:** P0.

### Proposed Story TC-03: `--resume` idempotency test

**Invariant:** Repeated `--resume` on a COMPLETE workflow produces no state changes.

**Test:** Run folder to COMPLETE. Run `--resume` again. Assert `workflow_state.json` byte-identical. Assert no new receipts. Assert no new events.

**Priority:** P1.

### Proposed Story TC-04: Add 5 high-value omitted tests to runner

**Invariant:** The canonical runner includes tests for the finalize gate, ATS parseability, ground-truth coverage, JD term extraction, and VOC translation.

**Work:** Add `test_check_finalize_ready.py`, `test_verify_submission.py`, `test_check_ground_truth_coverage.py`, `test_jd_term_extractor.py`, `test_voc_map.py` to `PYTHON_TEST_SCRIPTS` in `run_all_tests.py`.

**Priority:** P1.

### Deferred stories (from original report)

- TC-05 (one-page enforcement workflow integration) — requires revalidation against candidate.
- TC-06 (`--force-finalize` vs DONE oracle) — requires revalidation against candidate.
- TC-07 (FIT-001/002 negative tests) — requires revalidation against candidate.
- TC-08 (fixture discrimination improvement) — lower priority, programmatic cases are authoritative.

---

## Coordination Boundary Compliance

This amended audit:
- Remained in the separate clean worktree (`Applyr-audit`) on branch `cr112-test-confidence-audit`.
- Did NOT modify Cursor's `cr112-integrated-validation-candidate` or any Cursor-owned branch.
- Did NOT edit production code, live submissions, or production SQLite.
- Did NOT call paid APIs.
- Did NOT push, merge, or upload.
- Did NOT edit Cursor-owned handoff docs.
- Inspected the candidate's code and tests read-only to determine which findings are closed.
- Created only the amended audit report (this file).
