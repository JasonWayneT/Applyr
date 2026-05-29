# CR-023 — No layoff tone on submission assets

- Status: implemented
- Implements: `FR-096`
- Layer: specs + `scripts/tone_guard.py` + compose/QA pipeline

## Problem

Resume and cover letter output must not mention layoffs, attrition, or similar workforce-reduction framing. Use **constraints** language instead (e.g. increasing organizational or resource constraints).

## Acceptance criteria

| ID | Given | When | Then |
|---|---|---|---|
| `AC-097` | Compose or regenerate a resume/cover letter | Pipeline finishes | No `layoff`, `laid off`, or `attrition` tokens remain; ACC-110-LEADERSHIP source claim uses constraints wording |

## Implementation

- `scripts/tone_guard.py` — sanitize + detect
- `local_draft_stages.validate_bullet_for_local` — reject blocked tone at Tier 3
- `draft_compiler`, `style_compliance_guard`, `drafting_engine`, `quality_checker` — sanitize and QA rules R-011 / CL-010
- `generate_master_claims.py` — ACC-110-LEADERSHIP text updated
