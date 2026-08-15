# IMP-CR-091: Stage 0 Skip Ledger and Folder Placement

**CR:** `docs/spec/05-change-requests/CR-091-stage0-skip-ledger.md`  
**Requirements:** `FR-264`, `AC-326`–`AC-331`

## Live database

Migration `server/migrations/016_add_stage0_skips.sql` runs on next server boot via `runMigrations()` in `server/db.ts`.

It is **additive only**: `CREATE TABLE IF NOT EXISTS stage0_skips` plus two unique indexes. It does not `ALTER`, `DROP`, or rewrite `jobs` or any other existing table. The new table starts empty. Rows appear only when a production Stage 0 Skip is recorded.

Python `scripts/stage0_skip_ledger.py` `ensure_schema()` uses the same DDL, so Stage 0 still works if a script runs before the server has migrated.

## Changes

- Incoming JDs (CSV import, Sync export) land in `data/pending_review/`
- `stage0_skips` remembers a Skip by normalized URL, then `company||title`
- Production Skip → ledger + `data/archive/skipped/`
- Production PASS from `pending_review/` → `data/submissions/`
- `--force` re-evaluates a ledger hit; PASS clears the row
- Practice mode does not write the ledger
- Reconcile sweeps leftover SKIP fit-gate folders out of `submissions/`

## Verification

```bash
python -m unittest scripts.test_stage0_skip_ledger -v
npx vitest run tests/unit/stage0SkipLedger.test.ts
```

## Out of scope

- Jobs-table cooldown / Self-Rejected behavior
- UI for browsing skips
- Backfill from historical `archive/submissions/`
