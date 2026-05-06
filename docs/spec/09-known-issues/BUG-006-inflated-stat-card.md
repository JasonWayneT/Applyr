# BUG-006: Inflated "Total Active" Stat Card

## Metadata
- **Status**: Fixed
- **Severity**: P2
- **Component**: `TodayView.tsx`
- **Related Spec**: `CR-001`

## Description
The "Total Active" stat card on the dashboard counts all non-Closed jobs. This includes unreviewed `New`, `Backlog`, and `Drafted` jobs, which artificially inflates the metric and gives a false sense of how many applications are actually submitted and active.

## Fix
- Changed the filter scope for the stat card from `!['Closed']` to explicitly count only submitted states: `['Applied', 'Recruiter Screen', 'Core Interviews', 'Offer and Negotiation']`.
- Renamed the stat card from "Total Active" to "Submitted" to be unambiguous.
