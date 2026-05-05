# Feature Spec: FEAT-004 Drafting & Generation

## Metadata

- Feature ID: `FEAT-004`
- Status: implemented
- Source artifacts: `BMAD-SRC-004`, `BMAD-SRC-006`
- Related requirements: `FR-014`, `FR-015`, `FR-016`, `FR-017`, `FR-018`

## Problem statement

Writing custom resumes for every job is the biggest bottleneck. The system must generate high-quality drafts that emphasize the transition from Platform to Growth roles.

## Goals

- `GOAL-001`: Implement "Bridge Logic" to reframe existing wins for new role priorities.
- `GOAL-002`: Export clean, single-column, machine-readable PDFs.

## Requirements covered

| Requirement ID | Summary | Notes |
|---|---|---|
| `FR-014` | Bridge Logic | Translates Platform → Growth |
| `FR-015` | Resume Generation | Uses `data/Resume.md` as template |
| `FR-016` | PDF Export | ATS-optimized |

## Verification plan

| Test ID | Requirement/AC IDs | Test type | Expected result | Status |
|---|---|---|---|---|
| `TEST-004` | `FR-014` | manual | Resume highlights "User Scaling" even if source says "API Stability" | verified |
