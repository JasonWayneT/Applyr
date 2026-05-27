# CR-018: Zero-Touch Draft Polish

## Metadata

| Field | Value |
|---|---|
| **CR ID** | `CR-018` |
| **Status** | Implemented |
| **Priority** | P1 |
| **Date** | 2026-05-21 |
| **Builds on** | `CR-017` |
| **Implements** | `FR-105`, `FR-106`, `FR-107`, `FR-108` |

## Decision

Close post-CR-017 quality nits without manual per-resume editing: sentence-complete bullets, one bridge per job, fresh DB summaries on success, template-first cheat sheets.

## Acceptance criteria

- **AC-106:** No incomplete-clause bullets (recruiter_qa)
- **AC-107:** At most one bridged resume bullet per job
- **AC-108:** Cover proof paragraphs have no bridge prefix strings
- **AC-109:** Backlog `jobs.summary` has no stale audit error text after success
- **AC-110:** Cheat sheet exists when research packet present (template mode)

## Files

| File | Action |
|------|--------|
| `scripts/bullet_fit.py` | New |
| `scripts/claim_composer.py` | Bridge + fit |
| `scripts/recruiter_qa.py` | Incomplete bullet check |
| `scripts/batch_pipeline.py` | `_draft_success_summary` |
| `scripts/generate_cheat_sheet.py` | Template-first |
| `scripts/refresh_backlog_summaries.py` | One-time DB fix |
