# Feature Spec: FEAT-002 Evaluation & Gating

## Metadata

- Feature ID: `FEAT-002`
- Status: implemented
- Source artifacts: `BMAD-SRC-005`
- Related requirements: `FR-006`, `FR-007`, `FR-008`, `FR-009`, `FR-035`, `FR-039`

## Problem statement

Most job postings are poor fits. Sending every lead to an LLM for full analysis is expensive and slow. We need a tiered gating system to kill obvious bad fits instantly, and a background sync to automatically handle this pipeline.

## Goals

- `GOAL-001`: Filter out "Senior", "Lead", and "VP" roles without calling an AI API.
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

## Acceptance criteria

| AC ID | Requirement ID | Given | When | Then |
|---|---|---|---|---|
| `AC-006` | `FR-006` | Job title is "Senior PM" | Evaluator runs | Job is rejected with score 0 |
| `AC-008` | `FR-008` | Score is 80 but 0 anchors hit | Evaluator runs | Decision is NO |
| `AC-035` | `FR-035` | Jobs added as New | Background pipeline triggers | Descriptions are scraped, fit is evaluated, assets are drafted, and SQLite status is updated to Backlog |
| `AC-040` | `FR-039` | Dynamic Routing | User changes candidate preferences | Evaluation run | System dynamically adjusts title blocklists and scoring anchors |

## Verification plan

| Test ID | Requirement/AC IDs | Test type | Expected result | Status |
|---|---|---|---|---|
| `TEST-002` | `FR-006` | unit | `evaluate_job_fit` returns score 0 for blocklisted words | verified |
