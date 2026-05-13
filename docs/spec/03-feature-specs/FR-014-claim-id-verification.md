# FR-014 Claim‑ID Verification

## Requirement ID
FR-014

## Summary
Every claim generated in a resume or cover letter must be anchored to a concrete identifier from `data/workExperience.md`. The drafting engine must:
1. Instruct the LLM to embed an inline marker `[ACC-<id>]` for each factual statement.
2. After generation, run `verify_claims.verify()` to cross‑reference each marker against the source file.
3. If any marker is missing or does not match a source entry, the draft is **auto‑rejected**, a new generation is attempted (up to two retries). After the final failure the draft is flagged for manual review.

## Acceptance Criteria
- Drafts contain only IDs that exist in `workExperience.md`.
- The verification step returns a boolean and, on failure, provides a list of offending claim strings.
- The system logs verification results to `logs/claim_verification.log`.

## Non‑Functional Requirements
- Verification must complete in < 200 ms for a typical ~1500‑word draft.
- No external network calls; all processing is local.

## Traceability
- Implements business rule **Claim‑ID Traceability** from `RULE[claim_verifier.md]`.
- Linked to `FR-014` in the traceability matrix.
