---
title: HM Critical-Read Disposition Substance Contract
created: 2026-09-13
author: Factory (Droid)
branch: cr112-hm-critical-read-contract
base_commit: c254524
status: story_8.3.1_authoritative_edit_proof
design_review: independent reviewer (worker subagent) — ACCEPT WITH CHANGES (round 1)
closeout_review: user-directed corrections (round 2) — 5 contract/implementation mismatches resolved
story_8.3.1: user-directed correction (round 3) — RESOLVED_EDIT edit proof moved from self-reported prior_document_hashes to receipt-derived prior_output_hashes (committed workflow state)
scope: hm.critical_read evidence and disposition contract only
coordination: Does not modify Cursor-owned areas. Narrowly shared workflow/policy contract only.
---

# HM Critical-Read Disposition Substance Contract

## Problem

`hm.critical_read` is a WARN finding that asks the reviewer to confirm a hiring-manager read of Resume.md + CoverLetter.md. Without this contract it can be cleared with:

- `RESOLVED_EDIT` as a bare string (no reasoning, no evidence of any edit)
- `NOT_APPLICABLE` as a bare string (no reasoning, no justification)
- `ACCEPTED_AS_CORRECT` with 10 chars of filler ("looks fine")
- Generic templated reasoning that names no specific document content
- No JD reference
- No reviewer identity or role
- Self-certification by the same authoring agent with no independent review record
- A no-op `RESOLVED_EDIT` where no document actually changed
- A fabricated document location that passes merely because it has enough characters

The existing Stage 0/1 receipt hash chain already prevents document changes (Resume.md, CoverLetter.md, Original_JD.txt) from reaching HM without going STALE. That protection is solid. The gap is not staleness but substance. The contract must prove a qualitative read occurred without pretending character count proves judgment quality.

## Design Principles

1. **Structured evidence over character count.** Require at least one observation per document (Resume + CoverLetter), each naming a location, a verifiable document span, a JD span, and a JD-relevance statement. Character counts are structural friction only; they do not prove review quality.
2. **Document hash binding as defense-in-depth.** The HM review artifact records hashes of Resume.md, CoverLetter.md, and Original_JD.txt at review time. The existing receipt chain is the primary staleness gate; hash binding is secondary.
3. **Harness-agnostic reviewer roles.** No hard-coded Claude, Cursor, Factory, Codex, or any harness name. Reviewer role is a constrained enum: `author`, `reviewer`, or `human_reviewer`. Role identity is declarative, not cryptographic.
4. **No hidden chain-of-thought.** Require concise review evidence and conclusions only.
5. **Do not require inventing defects.** A clean review can pass, but it must still demonstrate specific engagement with both documents and the JD.
6. **Do not weaken Truth disposition behavior.** The HM contract is additive.
7. **Token-practical.** No separate agent per JD. The contract prevents silent self-certification, not mandates an expensive harness architecture.
8. **RESOLVED_EDIT must prove an edit.** A no-op edit with identical document hashes must not clear the finding.
9. **HUMAN_ACCEPTED_RISK requires a human.** An automated reviewer must not mint human acceptance.

## Structured HM Review Artifact Schema

```json
{
    "disposition": "ACCEPTED_AS_CORRECT",
    "reasoning": "Concise role-specific explanation of why no edit is required.",
    "risk_explanation": "Required only for HUMAN_ACCEPTED_RISK: the specific risk accepted.",
    "hm_review": {
        "reviewed_document_hashes": {
            "Resume.md": "<sha256 hex>",
            "CoverLetter.md": "<sha256 hex>",
            "Original_JD.txt": "<sha256 hex>"
        },
        "reviewer_role": "author | reviewer | human_reviewer",
        "review_timestamp": "<ISO 8601 with timezone, e.g. 2026-09-13T12:00:00Z>",
        "observations": [
            {
                "document": "Resume.md",
                "location": "<section name or stable text span reference>",
                "finding": "<what was observed>",
                "jd_relevance": "<how this relates to a specific JD requirement>",
                "document_span": "<verbatim quote from the document, >= 10 chars>",
                "jd_span": "<verbatim quote from Original_JD.txt, >= 10 chars>",
                "recommendation": "pass | revise | reject"
            },
            {
                "document": "CoverLetter.md",
                "location": "<paragraph or stable text span reference>",
                "finding": "<what was observed>",
                "jd_relevance": "<how this relates to a specific JD requirement>",
                "document_span": "<verbatim quote from the document, >= 10 chars>",
                "jd_span": "<verbatim quote from Original_JD.txt, >= 10 chars>",
                "recommendation": "pass | revise | reject"
            }
        ],
        "verdict": "pass | revise | reject",
        "overall_reasoning": "<concise summary>",
        "prior_document_hashes": {
            "Resume.md": "<sha256 hex>",
            "CoverLetter.md": "<sha256 hex>"
        },
        "resolution_summary": "Required only for RESOLVED_EDIT: confirms the original concern was resolved."
    }
}
```

> **Story 8.3.1 (2026-09-16):** `prior_document_hashes` above is **display-only and untrusted**. The RESOLVED_EDIT edit proof is derived from the Stage 1 COMPLETE receipt's `prior_output_hashes` — committed workflow state minted only by `workflow/receipts.py` — never from the reviewer payload. A self-reported prior hash proves nothing because an agent can invent one and pair it with a matching fabricated narrative. See [Story 8.3.1 — Authoritative Edit Proof](#story-831--authoritative-edit-proof).

### Required fields

| Field | Requirement | Validation |
|---|---|---|
| `disposition` | Must be ACCEPTED_AS_CORRECT, RESOLVED_EDIT, or HUMAN_ACCEPTED_RISK | Enum check |
| `reasoning` | >= 20 chars | `HM_REASONING_MIN_CHARS = 20` |
| `risk_explanation` | Required for HUMAN_ACCEPTED_RISK only, >= 20 chars | `RISK_EXPLANATION_MIN_CHARS = 20` |
| `hm_review` | Must be a dict | Presence check |
| `hm_review.reviewed_document_hashes` | Must contain Resume.md, CoverLetter.md, Original_JD.txt with sha256 matching on-disk | Hash verification |
| `hm_review.reviewer_role` | Must be `author`, `reviewer`, or `human_reviewer` | Enum check |
| `hm_review.review_timestamp` | Must be a parseable ISO-8601 timestamp with timezone info, not > 1 hour in the future | `datetime.fromisoformat` + tz check |
| `hm_review.observations` | List with >= 2 entries | Count check |
| `hm_review.observations[*].document` | Must be `Resume.md` or `CoverLetter.md` | Value check |
| `hm_review.observations[*].location` | >= 5 chars | Min-length check |
| `hm_review.observations[*].finding` | >= 15 chars | Min-length check |
| `hm_review.observations[*].jd_relevance` | >= 10 chars | Min-length check |
| `hm_review.observations[*].document_span` | >= 10 chars, must appear as substring in the named document (whitespace-normalized) | Verifiable span check |
| `hm_review.observations[*].jd_span` | >= 10 chars, must appear as substring in Original_JD.txt (whitespace-normalized) | Verifiable span check |
| `hm_review.observations[*].recommendation` | `pass`, `revise`, or `reject` | Enum check |
| `hm_review.verdict` | `pass`, `revise`, or `reject`; must be consistent with disposition | Enum + consistency check |
| `hm_review.overall_reasoning` | Non-empty string | Presence check |
| `hm_review.prior_document_hashes` | Display-only. NOT trusted for the edit proof (Story 8.3.1) | Ignored by the validator |
| `hm_review.resolution_summary` | Required for RESOLVED_EDIT only, >= 20 chars | Resolution check |
| Document coverage | At least one observation for Resume.md and one for CoverLetter.md | Coverage check |

### Reviewer Role Semantics

Role identity is declarative. The contract does not claim cryptographic independence. It prevents an `author` from silently masquerading as an independent reviewer by requiring an explicit role declaration.

| Role | May clear ACCEPTED_AS_CORRECT | May clear RESOLVED_EDIT | May clear HUMAN_ACCEPTED_RISK |
|---|---|---|---|
| `author` | No | Yes (they made the edit) | No |
| `reviewer` | Yes | Yes | No |
| `human_reviewer` | Yes | Yes | Yes |

An automated reviewer must not mint human acceptance. `HUMAN_ACCEPTED_RISK` requires `reviewer_role == "human_reviewer"` and a separate `risk_explanation` field stating the specific risk accepted.

If the workflow permits a separate review pass within the same harness, record it as `reviewer` while acknowledging that role identity is declarative.

### Disposition Semantics

**ACCEPTED_AS_CORRECT:** Clears only when the review artifact matches all current document and JD hashes, the reviewer role is `reviewer` or `human_reviewer`, reasoning >= 20 chars, verdict = "pass", and at least one observation per document with verifiable spans.

**RESOLVED_EDIT:** Does not clear merely because files match. Requires:
- An edit proven from **committed workflow state** (Story 8.3.1): the Stage 1 COMPLETE receipt's `prior_output_hashes` (authoritative, workflow-minted pre-edit hashes) must show at least one **implicated** document differing on disk now. Reviewer-supplied `prior_document_hashes` are display-only and never used for the proof.
- `resolution_summary` (>= 20 chars) confirming the original concern was resolved.
- All `reviewed_document_hashes` match current on-disk files (the review is fresh).
- At least one observation per document against the changed files.

A no-op `RESOLVED_EDIT` with identical hashes must not clear. An edit to a file **not implicated** by the finding must not clear. First-validation folders (no receipt `prior_output_hashes` yet) fail closed with a re-validation instruction — the enabled mechanics are: edit the implicated document, re-run `run_submission … --resume` (which rewrites the Stage 1 COMPLETE receipt preserving the pre-edit hashes as `prior_output_hashes`), then dispose `RESOLVED_EDIT`.

**HUMAN_ACCEPTED_RISK:** Requires `reviewer_role == "human_reviewer"` and `risk_explanation` (>= 20 chars). Verdict may be "pass", "revise", or "reject". Integrity becomes `OVERRIDDEN`.

**NOT_APPLICABLE and FALSE_POSITIVE:** Not allowed for `hm.critical_read`. A hiring-manager read is always required and is not a mechanical check that can misfire.

### Staleness

Any change to Resume.md, CoverLetter.md, or Original_JD.txt invalidates the prior HM review and disposition. Enforced by:
- **Primary gate:** Stage 0/1 receipt hash chain (`_require_stage1_fresh` in `run_stage2_hm`).
- **Secondary gate:** HM review artifact document hash verification. If the artifact's hashes don't match on-disk files, the disposition fails closed.

### Filler Resistance

Character counts are structural friction only. The primary filler resistance is the `document_span` and `jd_span` verification: each observation must include a verbatim quote from the named document and a verbatim quote from the JD. The validator normalizes whitespace and checks substring presence against the actual file contents. A made-up location string must not pass merely because it has enough characters.

At least one observation must be verifiably grounded in Resume.md and one in CoverLetter.md.

## Implementation Approach

### Production changes

1. **New module: `scripts/hm_review_contract.py`** — validates an HM review artifact. Pure function with file I/O for hashing and span verification. Returns `(ok: bool, errors: list[str])`. Story 8.3.1: adds `implicated_documents` to the signature and the receipt-derived edit proof (see below).

2. **Modify: `scripts/workflow/policy.py`** — imports `HM_DISALLOWED_DISPOSITIONS` from `hm_review_contract` (single source of truth). In `evaluate_truth_findings`, disallow NOT_APPLICABLE and FALSE_POSITIVE for `hm.critical_read`. Pure logic, no I/O.

3. **Modify: `scripts/workflow/runner.py`** — in `_apply_subphase_verdict`, after policy PASS for hm phase, calls `validate_hm_review(..., implicated_documents=item.get("implicated_documents"))`. If validation fails, downgrades to NEEDS_DISPOSITION with validation errors. Story 8.3.1: `collect_hm_findings` stamps `implicated_documents` (Resume.md + CoverLetter.md) on the `hm.critical_read` finding from code; `run_stage1_validate` preserves the previous COMPLETE receipt's output hashes as `prior_output_hashes` on re-validation.

4. **Modify: `scripts/workflow/receipts.py`** — `build_receipt` gains a conditional `prior_output_hashes` body field (absent when None), so pre-8.3.1 receipts stay byte-identical and `receipt_id` consumers (`contracts.check_workflow_complete`, `workflow.invalidate.reconcile_state_against_receipts`) need no changes.

5. **Modify: `scripts/workflow/reviews.py`** — updated dispositions note text only.

6. **No changes to Truth/ATS/Mech finding evaluation.**

### Files likely to conflict with Cursor

| File | Why | Mitigation |
|---|---|---|
| `scripts/workflow/policy.py` | Shared policy module | Additive: import + disallowed-disposition check. No I/O. |
| `scripts/workflow/runner.py` | Shared workflow runner | Additive: HM artifact validation call in `_apply_subphase_verdict`; `implicated_documents` stamp; prior-preserving re-validation. |
| `scripts/workflow/reviews.py` | Shared reviews module | Additive: updated note text only. |
| `scripts/workflow/receipts.py` | Workflow-owned receipt builder (not Cursor-owned) | Additive: conditional `prior_output_hashes` kwarg. |

## Story 8.3.1 — Authoritative Edit Proof

### Why self-reported priors were rejected

`507855b` cleared RESOLVED_EDIT when the payload's `prior_document_hashes` differed from `reviewed_document_hashes`. That proof was narrative: an agent could invent a prior hash, write it into the payload, and claim "I edited the summary" without any edit having occurred or been committed. The on-disk verification only proved the *review* was fresh — it never proved a change happened between two prior states.

### The authoritative source

`run_stage1_validate` (the canonical Stage 1 validation path, the sole writer of Stage 1 receipts alongside `workflow/receipts.py`) preserves each re-validation's predecessor: when Stage 1 was already COMPLETE, the new COMPLETE receipt carries `prior_output_hashes` = the previous COMPLETE receipt's output hashes (once set, the ORIGINAL prior is carried forward through multi-edit chains — a second edit still compares against the first pre-edit state, never the intermediate). First-validation receipts keep the field absent, so there is no pre-edit state to cite and RESOLVED_EDIT fails closed with a re-validation instruction.

This is the **smallest workflow-owned state addition** that makes the proof authoritative: no new files, no schema migration, no new receipt stage. The receipt is minted by the existing workflow writer; the field rides a re-validation event that already occurs whenever a fix round re-runs `--resume`.

### The validator (`validate_hm_review` RESOLVED_EDIT path)

1. `implicated_documents` normalized from the finding's own stamped field (code-supplied, not reviewer-supplied; defaults to Resume.md + CoverLetter.md).
2. Read `stage_receipts/stage1.json`; fails closed if missing/unreadable.
3. **Anti-forgery:** recompute `receipt_id` from the canonical body (sort_keys, compact separators — mirrors `build_receipt`); fails closed on mismatch, on `issued_by != scripts/run_submission.py`, on status != COMPLETE, and on `stage != "stage1"` (duplicated/misplaced receipt from another stage).
4. Require a non-empty `prior_output_hashes`.
5. **Staleness:** declared `output_hashes` must match current disk; missing files fail closed.
6. **Edit proof:** at least one implicated document's hash must differ prior → disk now. Missing/malformed prior entries for an implicated document fail closed (ambiguous history). If no implicated document changed, the disposition fails with the no-op/unrelated-edit error.
7. Payload `prior_document_hashes` are ignored for the proof (display-only).

### Adversarial controls (12, in `scripts/test_hm_critical_read_contract.py::TestResolvedEditAdversarial` + receipt-based `TestResolvedEditProof`)

| # | Bypass | Result |
|---|---|---|
| 1 | Invented `prior_document_hashes` in payload, no committed history | NEEDS_DISPOSITION (receipt has no prior); negative control with committed history clears |
| 2 | Change only a non-implicated file (`claim_provenance.json`) | NEEDS_DISPOSITION |
| 3 | Hand-edit receipt prior slot (prior := current) without recomputing receipt_id | NEEDS_DISPOSITION (receipt_id mismatch) |
| 4 | Restore the pre-edit receipt over the post-edit one (duplicate) | WorkflowError, "Stage 1 outputs stale" (freshness chain) |
| 5 | Delete stage_receipts/stage1.json | WorkflowError, "Stage 1 receipt missing" |
| 6 | Honest receipt records no change + payload fabricates a prior | NEEDS_DISPOSITION; negative control with real committed change clears |
| 7 | Relabel reviewer_role = human_reviewer to waive the edit proof | NEEDS_DISPOSITION |
| 8 | No-op re-validation (committed prior == current) with a valid review | NEEDS_DISPOSITION |
| 9 | Bare RESOLVED_EDIT string | NEEDS_DISPOSITION |
| 10 | RESOLVED_EDIT on a first-validation receipt (no prior) | NEEDS_DISPOSITION |
| 11 | RESOLVED_EDIT without `resolution_summary` | NEEDS_DISPOSITION |
| 12 | Multi-edit chain: second edit must still compare against the ORIGINAL prior | clears only because v3 != v1 (positive control) + intermediate-carried-forward assertion |

### Remaining limitations

- `prior_output_hashes` exists only after at least one re-validation; a first-validation RESOLVED_EDIT correctly fails (documented behavior).
- The contract proves a correlated change happened; it cannot prove the change specifically *fixed the finding*. Judgment lives in `resolution_summary` + observations, same as always.
- Trust boundary: any actor who can rewrite `stage_receipts/` after the fact can mint a new canonical receipt. This is the same trust boundary as every workflow receipt (there is no external notary).

## What This Contract Does Not Prove

1. That the reviewer actually exercised judgment.
2. That the observations are correct.
3. That the reviewer read every word of both documents.
4. That an independent reviewer is truly independent (role is declarative).
5. That the review quality meets any hiring-manager standard.
6. That a RESOLVED_EDIT was the *right* fix, only that an implicated document demonstrably changed relative to committed pre-edit state (the receipt proves the change happened; the review observations and resolution_summary carry the judgment about whether the change resolved the concern).
7. That the committed `prior_output_hashes` themselves were not tampered with — the receipt_id is a canonical-body hash so tampering breaks the anti-forgery check, but any actor who can rewrite `stage_receipts/` after the fact is outside this contract's threat model (same trust boundary as all workflow receipts).

## What This Contract Prevents

1. A bare `RESOLVED_EDIT` string clearing `hm.critical_read` with zero evidence.
2. A 10-character filler string clearing it.
3. A generic template clearing it without naming specific document content.
4. A `NOT_APPLICABLE` or `FALSE_POSITIVE` clearing it (both disallowed).
5. A disposition surviving after documents change (hash binding).
6. Silent self-certification (reviewer_role must be declared as a constrained enum).
7. Missing or malformed review evidence completing Stage 2 (fails closed).
8. A no-op `RESOLVED_EDIT` with identical document hashes (receipt prior == current).
9. A fabricated document location passing without verifiable content (span verification).
10. An automated reviewer minting human acceptance (role-disposition matrix).
11. A malformed or naive timestamp passing (ISO-8601 with timezone required).
12. (Story 8.3.1) An invented self-reported prior hash clearing RESOLVED_EDIT with no real edit — the receipt has no `prior_output_hashes` and the proof fails closed.
13. (Story 8.3.1) An edit to a non-implicated file (e.g. only `claim_provenance.json`) clearing the finding — only Resume.md/CoverLetter.md changes count.
14. (Story 8.3.1) A forged/corrupted/hand-edited receipt — `receipt_id` must match the canonical body hash.
15. (Story 8.3.1) A receipt from another stage, a non-COMPLETE receipt, or a receipt not issued by `run_submission` — all fail closed.
16. (Story 8.3.1) A stale receipt whose declared output hashes no longer match disk — fails closed.
