---
status: implemented
created: 2026-08-27
related: CR-073, CR-102
---

# CR-103 — ATS Retrieval Evidence & PDF Parser QA

## Problem

CR-073 identifies missing JD-specific terms and checks section reading order, but
its output does not distinguish a supported, actionable term gap from a term that
is merely present in the global vocabulary. PDF verification confirms page count
and heading order, but a text layer can still omit an important identity, contact,
role, employer, or date field.

## Decision

Extend the existing `verify_submission.py` receipt with two WARN-only reports:

1. `ats_retrieval` — the packet's evidence-backed ATS term contract, with each
   supported term, claim IDs, JD items, and whether the term is present in the
   resume.
2. `pdf_parseability` — field-level checks against text extracted from each PDF:
   name, contact line, required section headings, experience title/company/date
   fields, and cover-letter greeting/sign-off where applicable.

Neither report changes `mechanically_verified`. A false positive must not block a
submission, while a missing actionable field remains visible for human review.
No external ATS or candidate data is contacted.

## Requirements

- `FR-266`: Verification reports actionable, packet-supported ATS term coverage
  separately from global vocabulary gaps.
- `FR-267`: Verification reports whether required resume and cover-letter fields
  survive PDF text extraction.
- `NFR-008`: ATS and parser checks are local, deterministic, and WARN-only.

## Acceptance criteria

- `AC-339`: If an authoring packet contains an ATS term contract, the receipt
  records each term, its claim IDs/JD items, and resume presence.
- `AC-340`: A PDF with missing extracted name, contact, employer, title, date,
  section, greeting, or sign-off fields reports those fields in
  `pdf_parseability`.
- `AC-341`: A clean fixture reports all checked fields present.
- `AC-342`: Existing mechanical verification behavior is unchanged by WARN-only
  ATS and parser findings.

## Verification

- Unit tests cover clean and missing-field extraction cases.
- Existing submission verification and the full Python test suite pass.
