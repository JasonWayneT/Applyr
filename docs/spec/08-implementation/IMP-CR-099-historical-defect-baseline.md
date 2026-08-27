# IMP-CR-099: Historical Defect Baseline

**CR:** [CR-099-safe-historical-defect-baseline.md](../05-change-requests/CR-099-historical-defect-baseline.md)
**Status:** Implemented 2026-08-24

## Stories

- [x] Add a separate baseline artifact and importer.
- [x] Import only structured `verify_history.json` evidence.
- [x] Require explicit human confirmation with a note and confirmer.
- [x] Make IDs stable and repeated scans idempotent.
- [x] Permanently exclude historical records from live promotion and metrics.
- [x] Add isolation tests for provenance, idempotency, and confirmation.

## Verification

Focused CR-099 tests pass. The importer does not modify the live ledger,
authoring example bank, submission files, or workflow receipts.
