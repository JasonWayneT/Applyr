# Feature Spec: FEAT-002 Evaluation & Gating

## Metadata

- Feature ID: `FEAT-002`
- Status: implemented
- Source artifacts: `BMAD-SRC-005`
- Related requirements: `FR-006`, `FR-007`, `FR-008`, `FR-009`

## Problem statement

Most job postings are poor fits. Sending every lead to an LLM for full analysis is expensive and slow. We need a tiered gating system to kill obvious bad fits instantly.

## Goals

- `GOAL-001`: Filter out "Senior", "Lead", and "VP" roles without calling an AI API.
- `GOAL-002`: Use LLM reasoning only for high-probability candidates.
- `GOAL-003`: Enforce a "Two-Anchor" rule to ensure technical alignment.

## Requirements covered

| Requirement ID | Summary | Notes |
|---|---|---|
| `FR-006` | Zero-Token Gate | Uses `TITLE_BLOCKLIST` |
| `FR-007` | 100-point Score | LLM evaluation |
| `FR-008` | Two-Anchor Rule | Mandatory overlap check |

## Acceptance criteria

| AC ID | Requirement ID | Given | When | Then |
|---|---|---|---|---|
| `AC-006` | `FR-006` | Job title is "Senior PM" | Evaluator runs | Job is rejected with score 0 |
| `AC-008` | `FR-008` | Score is 80 but 0 anchors hit | Evaluator runs | Decision is NO |

## Verification plan

| Test ID | Requirement/AC IDs | Test type | Expected result | Status |
|---|---|---|---|---|
| `TEST-002` | `FR-006` | unit | `evaluate_job_fit` returns score 0 for blocklisted words | verified |
