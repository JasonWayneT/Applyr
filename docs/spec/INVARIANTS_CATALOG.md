# Applyr Invariants Catalog

This catalog defines the non-negotiable invariants enforced across the Applyr submission engine. Every invariant must be automatically testable via `scripts/run_adversarial_pressure_test.py` or deterministic validation gates.

**Adversarial runner column (CR-112 Epic 4):** `programmatic:<case>` means this runner has a named programmatic case. `not this runner` means production code still enforces the invariant, but this harness does not claim it. Unwired `payload_*.txt` files live in `docs/spec/archive/adversarial-payloads/` and are not executed here.

---

## 1. Workflow State & Receipt Invariants (`STATE-***`)

| ID | Name | Constraint Description | Enforced By | Adversarial runner |
|---|---|---|---|---|
| `STATE-001` | Strict Stage Precedence | Downstream stages MUST NOT execute without valid, `COMPLETE` upstream receipts. | `workflow.runner.run_stage1_validate` / `contracts.check_stage1_ready` | programmatic: `case_downstream_no_receipt` + `case_state_001_negative` |
| `STATE-002` | Terminal Skip Lock | A Stage 0 policy `SKIP` decision MUST permanently halt the pipeline. No downstream auto-advancement allowed. | `workflow.runner.run_until_waiting_for_llm` | programmatic: `case_skip_halts` |
| `STATE-003` | Hash Invalidation | If any artifact content diverges from `output_hashes` in its receipt, workflow status MUST transition to `STALE`. | `workflow.invalidate.reconcile_state_against_receipts` | programmatic: `case_stale_hash` (fixture walk skipped as duplicate) |
| `STATE-004` | Incomplete Status Guard | Any workflow with `FAILED`, `STALE`, `SKIPPED`, or `WAITING_*` status MUST return `False` for `check_workflow_complete()`. Inverse: chained COMPLETE receipts return `True`. | `contracts.check_workflow_complete` | programmatic: `case_state_004_incomplete` + `case_state_004_complete` |
| `STATE-005` | Receipt Integrity | Receipt files in `stage_receipts/*.json` MUST be valid JSON matching `StageReceiptSchema`. | `workflow.receipts.load_receipt` | not this runner |

---

## 2. Stage 0 Fit Gate Invariants (`FIT-***`)

| ID | Name | Constraint Description | Enforced By | Adversarial runner |
|---|---|---|---|---|
| `FIT-001` | Valid Decision Enum | Stage 0 decision MUST be exactly `PASS`, `SKIP`, or `NEEDS_DISPOSITION`. | `build_stage0_fit_gate.py` / `contracts` | not this runner |
| `FIT-002` | Mandatory Skip Reason | If decision is `SKIP`, `skip_reason` MUST be present and non-empty. | `stage0_evidence_cascade.py` | not this runner |
| `FIT-003` | Exclusion Zone Hard-Skip | Roles matching explicit candidate exclusion preferences (e.g. founding PM, 0-to-1, people manager) MUST evaluate to `SKIP`. | `stage0_fit_gate` policy checks | not this runner |

---

## 3. Stage 1 & Document Structure Invariants (`DOC-***`)

| ID | Name | Constraint Description | Enforced By | Adversarial runner |
|---|---|---|---|---|
| `DOC-001` | Resume Section Ordering | `Resume.md` MUST contain required headings (`## PROFESSIONAL SUMMARY`, `## PROFESSIONAL EXPERIENCE`, `## EDUCATION`) in canonical order. | `quality_checker.check_resume` | programmatic: `case_missing_resume_section` |
| `DOC-002` | Exact 3-Sentence Summary | `Professional Summary` section in `Resume.md` MUST contain exactly 3 sentences. | `resume_conversion_eval.py` / `quality_checker` | not this runner |
| `DOC-003` | Forbidden Punctuation | `Resume.md` and `CoverLetter.md` MUST NOT contain `LR-014` (semicolons) or `LR-015` (colon-whitespace-letter em-dash tells). | `submission_linter.py` | programmatic: `case_forbidden_punctuation` + `case_doc_003_negative` (linter-direct, not a bare `WorkflowError`) |
| `DOC-004` | No Cover Letter Bullets | `CoverLetter.md` MUST NOT contain markdown bullet lists. | `submission_linter.py` | not this runner |

---

## 4. Truth-Grounding & Attribution Invariants (`TRUTH-***`)

| ID | Name | Constraint Description | Enforced By | Adversarial runner |
|---|---|---|---|---|
| `TRUTH-001` | Claim Index Validity | All claim IDs in `claim_provenance.json` MUST exist in `master_claims.json` / `workExperience.md`. | `claim_provenance.check_claim_provenance` | programmatic: `case_hallucinated_claim` |
| `TRUTH-002` | Prohibited Claims Fence | Generated documents MUST NOT contain claims listed on the explicit DO NOT CLAIM inventory (e.g. direct reports, AI model training). | `submission_linter.py` / `claim_provenance` | not this runner |
| `TRUTH-003` | Employer Attribution | Company experience points MUST only be attributed to employers where that experience occurred. | `claim_provenance.check_employer_attribution` | not this runner |

---

## 5. Verification & Finalization Invariants (`FINAL-***`)

| ID | Name | Constraint Description | Enforced By | Adversarial runner |
|---|---|---|---|---|
| `FINAL-001` | Stage 2 Complete Gate | `contracts.check_stage2_ready()` MUST pass clean before `finalize_submission_job.py` can commit a submission to the database. | `scripts/run_submission.py` | not this runner |
| `FINAL-002` | Compiled PDF Presence | `Resume.pdf` and `CoverLetter.pdf` MUST exist and be non-empty prior to database finalization. | `finalize_submission_job.py` | not this runner |
