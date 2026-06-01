# IMP-CR-033 — Built In Detail-Page JD Ingest

| Field | Value |
|---|---|
| **CR** | `CR-033` |
| **Requirement IDs** | `FR-180` |
| **Status** | implemented |

## Code map

| Requirement | File | Notes |
|---|---|---|
| `FR-180` | `scripts/extract_job_page.ts` | Shared Playwright JD extraction |
| `FR-180` | `scripts/scout_local.ts` | `scoutBuiltIn()` fetches JD per card; save `jd_text`, staging `jobs/*.txt`, status `Drafted` |
| `FR-180` | `scripts/scrape_new_jobs.ts` | Reuses extractor for non–Built In `New` rows |

## Verification

1. Run sync with Remote prefs; scout log shows `Built In: Fetching JD` and `JD fetched (N chars)`.
2. Geographic rejects reference full JD (e.g. `remote` in body), not `remote_only_no_location_signal` on title-only stubs.
3. SQLite: new Built In rows have `length(jd_text) > 200` and matching `jobs/*_*.txt` staging file.
