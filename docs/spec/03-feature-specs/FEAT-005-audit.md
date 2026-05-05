# Feature Spec: FEAT-005 Audit & Quality

## Metadata

- Feature ID: `FEAT-005`
- Status: implemented
- Source artifacts: `BMAD-SRC-006`
- Related requirements: `FR-019`, `FR-020`, `FR-021`, `FR-022`

## Problem statement

AI tends to "hallucinate" or inflate metrics to match JDs. This creates a trust issue. The system must hard-verify every claim against the source work experience.

## Goals

- `GOAL-001`: Perform a deterministic sweep for metric mismatch.
- `GOAL-002`: Block prohibited phrases (e.g., "Led a team of...").

## Requirements covered

| Requirement ID | Summary | Notes |
|---|---|---|
| `FR-019` | Hard Fact Validation | Metric-to-metric check |
| `FR-020` | Hallucination Guard | Replacement logic |

## Verification plan

| Test ID | Requirement/AC IDs | Test type | Expected result | Status |
|---|---|---|---|---|
| `TEST-005` | `FR-019` | integration | Audit report flags any metric not found in `workExperience.md` | verified |
