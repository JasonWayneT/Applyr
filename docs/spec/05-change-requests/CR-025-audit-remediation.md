# CR-025 — Audit Remediation (Security & Reliability)

| Field | Value |
|-------|-------|
| **Status** | implemented |
| **Implements** | `FR-164`, `FR-165`, `FR-166`, `FR-167`, `FR-168`, `FR-169` |
| **Excludes** | Tailscale binding / NFR-006 network exposure (unchanged) |
| **Layer** | Specs + `server/` + `scripts/` + `src/` |

## Problem

Engineering audit (2026-05-28) found command injection via `exec()`, broken evaluate/skill-gap API contracts, silent PDF failures, missing pipeline mutex, stale FTS index, and path traversal risk on company slugs.

## Solution

| Area | Change |
|------|--------|
| Server | `spawn` without shell; optional `APPLYR_API_TOKEN`; restricted CORS; pipeline lock; evaluate `done` payload; manifest-before-write |
| Python | `generate_pdf` raises; `company_slug.py`; runtime `get_min_fit_score()` |
| Frontend | Skill-gap contract; AI rewrite restore; scout self-reject → `Closed` |
| CI | `npm run build` in smoke workflow |

## Acceptance

| ID | Criterion |
|----|-----------|
| `AC-170` | Rerank/skill-gap use `spawn` array args — no shell interpolation |
| `AC-171` | Evaluate SSE `done` includes score, company, title, summary |
| `AC-172` | Missing PDF after compile raises `DraftingPipelineError` |
| `AC-173` | Concurrent `/api/sync` returns 409 when pipeline busy |
| `AC-174` | Job INSERT/UPDATE syncs `jobs_fts` row |

## Verification

```bash
npm run build
python scripts/smoke_draft_compiler.py
```
