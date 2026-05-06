# BUG-004: Dashboard "Active Applications" Includes Pipeline Jobs

## Metadata
- **Status**: Fixed
- **Severity**: P1
- **Component**: `TodayView.tsx`
- **Related Spec**: `CR-001`

## Description
The "Active Applications" section on the dashboard incorrectly includes `Backlog`, `New`, and `Drafted` jobs. These are statuses for jobs that have NOT been applied to yet, which inflates the "active" count and makes it difficult to distinguish between pending applications and submitted ones.

## Fix
- Split the dashboard view into two sections: "Ready to Apply" (for `New` and `Backlog`) and "Active Applications" (for `Applied`, `Recruiter Screen`, etc.).
