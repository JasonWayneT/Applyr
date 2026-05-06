# BUG-003: "Ready to Apply" Shown Without Assets

## Metadata
- **Status**: Fixed
- **Severity**: P0
- **Component**: `StatusChip.tsx`, `JobDetailPanel.tsx`
- **Related Spec**: `FEAT-006`

## Description
Jobs with `Drafted` status show the "Ready to Apply" label even when no PDF assets have been generated yet. There is no asset-existence check before surfacing this label, leading to a misleading user experience where they expect to apply but find no assets.

## Fix
- Added a `has_assets` check in `server/index.ts` to scan the job's directory for `.pdf` files.
- Updated `StatusChip.tsx` to dynamically show `"Drafting…"` if assets are missing, and updated the paradigm so `Drafted` is no longer the "Ready to Apply" status.
