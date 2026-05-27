# BUG-013: Past Interviews Shown in Upcoming Schedule

## Metadata
- **Status**: Fixed
- **Severity**: P2
- **Component**: `TodayView.tsx`
- **Related requirements**: `FR-032`

## Description
The dashboard "Next Interview" card and "Upcoming Interviews" grid included jobs whose `interview_date` was in the past. When no future interview existed, the UI fell back to the earliest scheduled row (often yesterday's interview), so users still saw stale calendar entries after the meeting passed.

## Fix
- Filter scheduled interviews to `interview_date > now` before sorting and display.
- Remove the fallback that selected `scheduledInterviews[0]` when no future interview existed.
- Show empty states when all interview dates have passed.
