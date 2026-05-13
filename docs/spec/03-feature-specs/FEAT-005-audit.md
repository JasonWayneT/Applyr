# Feature Spec: FEAT-005 Audit & Quality

## Metadata

- Feature ID: `FEAT-005`
- Status: implemented
- Source artifacts: `BMAD-SRC-006`, `CR-007`
- Related requirements: `FR-019`, `FR-020`, `FR-021`, `FR-022`, `FR-073`, `FR-074`, `FR-075`

## Problem statement

AI tends to "hallucinate" or inflate metrics to match JDs. This creates a trust issue. The system must hard-verify every claim against the source work experience. Additionally, small local models produce structurally corrupt output (forbidden sections, wrong name headers, unfilled placeholders, education sections in cover letters) that must be caught and corrected deterministically before PDFs are compiled.

## Goals

- `GOAL-001`: Perform a deterministic sweep for metric mismatch.
- `GOAL-002`: Block prohibited phrases (e.g., "Led a team of...").
- `GOAL-003`: Detect invented numeric claims in generated bullets without any LLM call. *(CR-007)*
- `GOAL-004`: Enforce style structure at the file level — strip forbidden sections, normalize headers, remove placeholders. *(CR-007)*
- `GOAL-005`: Suppress irrelevant validation checks based on document type (resume vs. cover letter). *(CR-007)*

## Requirements covered

| Requirement ID | Summary | Notes |
|---|---|---|
| `FR-019` | Hard Fact Validation | Metric-to-metric check against `APPROVED_METRICS` |
| `FR-020` | Hallucination Guard | `KNOWN_HALLUCINATIONS` replacement + Cision title guard |
| `FR-073` | Deterministic Numeric Fact Preservation | `preserves_core_facts()` in `verify_claims.py`; called per-bullet in two-phase local generation |
| `FR-074` | Style Guard Forbidden Section & Header Normalization | `strip_forbidden_sections()`, `strip_placeholders()`, `normalize_resume_headers()` in `style_compliance_guard.py` |
| `FR-075` | `validate_hard_facts()` Document-Type Awareness | `doc_type` param; education check gated; Cision title auto-corrected; placeholder tokens stripped |

## Design notes (CR-007 additions)

### `preserves_core_facts(source_text, bullet)` — `verify_claims.py`
Extracts all numeric tokens matching `\$\d+`, `\d+%`, and `\b\d{2,}\b` from both source and bullet. Any number in the bullet with no equivalent substring in the source set is returned as an "invented" value. This check is zero-cost (no LLM) and runs as the first gate in the two-phase local generation loop.

### `strip_forbidden_sections(content)` — `style_compliance_guard.py`
Scans the resume line by line. When a `##` or `###` header matches `_FORBIDDEN_SECTION_RE` (covering Core Competencies, Technical Skills, Technical Skills & Tools, Technical Proficiencies, Key Projects & Achievements, Projects & Achievements, Key Achievements & Impact Summary, Skills & Tools, Technical Environment, Core Expertise, Additional Information, Summary of Qualifications, Highlights), the header and all subsequent lines up to the next `##` boundary are dropped.

### `validate_hard_facts(doc_type='resume')` — `drafting_engine.py`
- `doc_type='cover_letter'`: education presence check skipped; company check still runs.
- Cision title guard: any line containing "cision" AND "product owner" has "Product Owner" replaced with "Product Manager" (log entry produced).
- Placeholder catch-all: `re.compile(r'\[(?:[A-Z][A-Za-z0-9\s/&,\-]+)\]')` strips unfilled tokens from all output.

## Verification plan

| Test ID | Requirement/AC IDs | Test type | Expected result | Status |
|---|---|---|---|---|
| `TEST-005` | `FR-019` | integration | Audit report flags any metric not found in `workExperience.md` | verified |
| `TEST-073` | `FR-073`, `AC-075` | unit | `preserves_core_facts("3,500 accounts", "5,000 accounts")` returns `(False, ["5,000"])` | verified |
| `TEST-074` | `FR-074`, `AC-076` | integration | Guard run on resume with `## Core Competencies` section strips it; `# JASON TAYLOR` header restored from `## JASON TAYLOR` variant | verified |
| `TEST-075` | `FR-075`, `AC-077` | integration | `validate_hard_facts(cl_text, master, doc_type='cover_letter')` produces zero "MISSING FACT: Education" warnings | verified |
