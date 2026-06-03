# Feature Spec: FEAT-002 Evaluation & Gating

## Metadata

- Feature ID: `FEAT-002`
- Status: implemented
- Source artifacts: `BMAD-SRC-005`
- Related requirements: `FR-006`, `FR-007`, `FR-008`, `FR-009`, `FR-035`, `FR-039`, `FR-109`, `FR-170`, `FR-171`, `FR-172`, `FR-188`, `FR-189`, `FR-190`, `FR-191`, `FR-192`
- Related change requests: `CR-027`, `CR-028`, `CR-035`, `CR-036`, `CR-037`, `CR-038`, `CR-039`

## Problem statement

Most job postings are poor fits. Sending every lead to an LLM for full analysis is expensive and slow. We need a tiered gating system to kill obvious bad fits instantly, and a background sync to automatically handle this pipeline.

## Goals

- `GOAL-001`: Filter out Lead, Director, and VP-tier titles without calling an AI API; allow Senior when years fit (CR-019).
- `GOAL-002`: Use LLM reasoning only for high-probability candidates.
- `GOAL-003`: Enforce a "Two-Anchor" rule to ensure technical alignment.
- `GOAL-004`: Fully automate the end-to-end sync, scraping, evaluation, and asset generation in the background.
- `GOAL-005`: Dynamic evaluation parameters parsed from user-editable JSON configurations.

## Requirements covered

| Requirement ID | Summary | Notes |
|---|---|---|
| `FR-006` | Zero-Token Gate | Uses `TITLE_BLOCKLIST` |
| `FR-007` | 100-point Score | LLM evaluation |
| `FR-008` | Two-Anchor Rule | Mandatory overlap check |
| `FR-035` | Background Sync Pipeline | End-to-end automation of scraping, evaluation, and asset creation |
| `FR-039` | Dynamic Gating | Reads blocklists and experience targets dynamically from JSON |
| `FR-170` | Industry blocklist gate | `industry_gate.py` in zero-token path (`CR-027`) |
| `FR-171` | Must-have / signal keywords | `passes_keyword_gate()` (`CR-028`) |
| `FR-172` | Two-anchor optional gate | `ANCHOR_GATE_ENABLED` (`CR-028`) |
| `FR-190` | Required domain experience gate | superseded by FR-192 (CR-039) — informational gaps only |
| `FR-191` | B2C role openness | `open_to_b2c` preference + fit prompt (`CR-038`) |
| `FR-192` | Transferable skills scoring | No domain zero-token gate; fit prompt (`CR-039`) |
| `FR-188` | Fit scoring hardening | Scoring-only primary path, location lock, anchor floor on full JD (`CR-035`) |
| `FR-189` | Solo PM trap + years policy lock | `solo_pm_gate.py`, `fit_policy.py` (`CR-036`) |

## Acceptance criteria

| AC ID | Requirement ID | Given | When | Then |
|---|---|---|---|---|
| `AC-006` | `FR-006` | Job title is "Lead PM" | Evaluator runs | Job is rejected with score 0 |
| `AC-006b` | `FR-109` | Job title is "Senior PM" with 3-6 years in JD | Title gate runs | Job passes title gate |
| `AC-008` | `FR-008` | Score is 80 but 0 anchors hit | Evaluator runs | Decision is NO |
| `AC-035` | `FR-035` | Jobs added as New | Background pipeline triggers | Descriptions are scraped, fit is evaluated, assets are drafted, and SQLite status is updated to Backlog |
| `AC-040` | `FR-039` | Dynamic Routing | User changes candidate preferences | Evaluation run | System dynamically adjusts title blocklists and scoring anchors |

## Verification plan

| Test ID | Requirement/AC IDs | Test type | Expected result | Status |
|---|---|---|---|---|
| `TEST-002` | `FR-006` | unit | `evaluate_job_fit` returns score 0 for blocklisted words | verified |
