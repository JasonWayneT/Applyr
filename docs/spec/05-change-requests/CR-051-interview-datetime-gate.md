# CR-051 — Require interview date/time on screening transitions

| Field | Value |
|-------|-------|
| **Status** | implemented |
| **Related** | `FR-251` |

## Problem

Moving a job from Applied → Recruiter Screen or Recruiter Screen → Core Interviews did not require scheduling date/time, so pipeline stages could advance without a concrete interview slot.

## Solution

1. Shared rule module `shared/domain/jobPipeline.ts` defines statuses that require `interview_date`.
2. `PATCH /api/jobs/:id/status` returns 400 when target status is `Recruiter Screen` or `Core Interviews` without a valid `interview_date` (request body or existing job value).
3. `JobDetailPanel` blocks progression buttons until Interview Schedule is set and sends `interview_date` with the status update.

## Acceptance criteria

- [x] Applied → Recruiter Screen blocked without date/time (UI + API).
- [x] Recruiter Screen → Core Interviews blocked without date/time (UI + API).
- [x] Valid datetime persists on successful transition.
- [x] Unit tests for shared validation helpers.
