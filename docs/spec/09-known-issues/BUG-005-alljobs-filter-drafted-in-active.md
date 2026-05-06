# BUG-005: AllJobsView "Active" Filter Includes Drafted Status

## Metadata
- **Status**: Fixed
- **Severity**: P1
- **Component**: `AllJobsView.tsx`
- **Related Spec**: `CR-001`

## Description
The "Active" filter tab in `AllJobsView.tsx` groups `Drafted` status jobs alongside jobs that have already been applied to. This means "Ready to Apply" (or drafting) jobs are mixed with active, submitted applications, confusing the user about their real active pipeline.

## Fix
- Redesigned the filter tabs to `All | Backlog | Active | Interviewing | Closed`.
- `Active` now only includes `Applied`.
- `Drafted` is hidden from all tabs except `All`, and `Backlog` includes both `New` and `Backlog` statuses (jobs ready to apply).
