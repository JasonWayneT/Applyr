---
title: HM Critical-Read Disposition Substance Contract
created: 2026-09-13
author: Factory (Droid)
branch: cr112-hm-critical-read-contract
base_commit: c254524
status: corrected_after_final_review
design_review: independent reviewer (worker subagent) — ACCEPT WITH CHANGES (round 1)
closeout_review: user-directed corrections (round 2) — 5 contract/implementation mismatches resolved
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
            "Resume.md": "<sha256 hex before edit>",
            "CoverLetter.md": "<sha256 hex before edit>",
            "Original_JD.txt": "<sha256 hex>"
        },
        "resolution_summary": "Required only for RESOLVED_EDIT: confirms the original concern was resolved."
    }
}
```

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
| `hm_review.prior_document_hashes` | Required for RESOLVED_EDIT only; at least one Resume.md or CoverLetter.md hash must differ from reviewed_document_hashes | Edit proof check |
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
- `prior_document_hashes` showing at least one Resume.md or CoverLetter.md hash differs from `reviewed_document_hashes` (proving an edit occurred).
- `resolution_summary` (>= 20 chars) confirming the original concern was resolved.
- All `reviewed_document_hashes` match current on-disk files (the review is fresh).
- At least one observation per document against the changed files.

A no-op `RESOLVED_EDIT` with identical hashes must not clear.

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

1. **New module: `scripts/hm_review_contract.py`** — validates an HM review artifact. Pure function with file I/O for hashing and span verification. Returns `(ok: bool, errors: list[str])`.

2. **Modify: `scripts/workflow/policy.py`** — imports `HM_DISALLOWED_DISPOSITIONS` from `hm_review_contract` (single source of truth). In `evaluate_truth_findings`, disallow NOT_APPLICABLE and FALSE_POSITIVE for `hm.critical_read`. Pure logic, no I/O.

3. **Modify: `scripts/workflow/runner.py`** — in `_apply_subphase_verdict`, after policy PASS for hm phase, calls `validate_hm_review`. If validation fails, downgrades to NEEDS_DISPOSITION with validation errors.

4. **Modify: `scripts/workflow/reviews.py`** — updated dispositions note text only.

5. **No changes to Truth/ATS/Mech finding evaluation.**

### Files likely to conflict with Cursor

| File | Why | Mitigation |
|---|---|---|
| `scripts/workflow/policy.py` | Shared policy module | Additive: import + disallowed-disposition check. No I/O. |
| `scripts/workflow/runner.py` | Shared workflow runner | Additive: HM artifact validation call in `_apply_subphase_verdict`. |
| `scripts/workflow/reviews.py` | Shared reviews module | Additive: updated note text only. |

## What This Contract Does Not Prove

1. That the reviewer actually exercised judgment.
2. That the observations are correct.
3. That the reviewer read every word of both documents.
4. That an independent reviewer is truly independent (role is declarative).
5. That the review quality meets any hiring-manager standard.
6. That the `prior_document_hashes` are truthful (self-reported; the on-disk hash verification proves freshness, not that a change occurred between two prior states).

## What This Contract Prevents

1. A bare `RESOLVED_EDIT` string clearing `hm.critical_read` with zero evidence.
2. A 10-character filler string clearing it.
3. A generic template clearing it without naming specific document content.
4. A `NOT_APPLICABLE` or `FALSE_POSITIVE` clearing it (both disallowed).
5. A disposition surviving after documents change (hash binding).
6. Silent self-certification (reviewer_role must be declared as a constrained enum).
7. Missing or malformed review evidence completing Stage 2 (fails closed).
8. A no-op `RESOLVED_EDIT` with identical document hashes (prior hash check).
9. A fabricated document location passing without verifiable content (span verification).
10. An automated reviewer minting human acceptance (role-disposition matrix).
11. A malformed or naive timestamp passing (ISO-8601 with timezone required).
