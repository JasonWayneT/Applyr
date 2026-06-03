# CR-041 — ATS watchlist: no example file at runtime

## Problem
When `data/ats_watchlist.json` and `config/ats_watchlist.json` were absent, scout loaded `config/ats_watchlist.example.json` and ingested **Example Corp** jobs from Greenhouse’s demo board (`source: ATS Watchlist`).

## Change
- `scripts/scout_local.ts` — `scoutAtsWatchlist()` only reads user-owned watchlist paths; skips channel when neither exists.
- `config/ats_watchlist.example.json` — notes clarify template-only, not loaded by scout.

## Requirements
- `FR-147` (ATS watchlist channel)
- `FR-194` (no example fallback)

## Acceptance
1. Fresh clone with no `data/ats_watchlist.json` → ATS Watchlist health log `skipped`, zero Example Corp rows.
2. Copy example to `data/ats_watchlist.json` and edit → channel runs for real companies only.
