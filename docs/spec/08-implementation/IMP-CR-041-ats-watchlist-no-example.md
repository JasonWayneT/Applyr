# IMP-CR-041 — ATS watchlist no example fallback

**CR:** [CR-041-ats-watchlist-no-example-fallback.md](../05-change-requests/CR-041-ats-watchlist-no-example-fallback.md)  
**Requirements:** `FR-194`, `FR-147`

## Tasks

| ID | Task | File(s) | Status |
|----|------|---------|--------|
| T1 | Remove `ats_watchlist.example.json` from scout candidate paths | `scripts/scout_local.ts` | done |
| T2 | Update template notes | `config/ats_watchlist.example.json` | done |

## Verification

Run scout; confirm no jobs with `company: Example Corp` and `source: ATS Watchlist` unless `data/ats_watchlist.json` exists.
