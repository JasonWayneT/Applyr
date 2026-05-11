# Known Issue: BUG-007 Scraper Interrupted Navigation Loop

## Metadata

- Bug ID: `BUG-007`
- Status: fixed
- Severity: medium
- Found in: v3.2
- Fixed in: v3.2.1
- Related requirements: `FR-035`, `FR-052`

## Current behavior

When Adzuna (or other sources) automatically redirects an expired job link to a recommended job link, Playwright's `page.goto` throws an "interrupted by another navigation" error. The scraper catches the error, logs it, but leaves the job in the `New` status in the database. This causes the background scraper to enter an infinite loop re-processing the same dead link on every sync run.

## Expected behavior

If a job details URL triggers a server-side or client-side redirect that interrupts the primary navigation (indicating a dead or stale link), the system should recognize it as expired, log the event gracefully, and move the job to `stale_jobs` to prevent duplicate crawls and remove it from the active `New` queue.

## Root cause

`scripts/scrape_new_jobs.ts` only transitions jobs to `Drafted` if text extraction succeeds. Any exception in `page.goto` simply logs and continues without updating the job state, meaning the job persists as `New` indefinitely.

## Verification

- **Fix approach:** In `scripts/scrape_new_jobs.ts`, catch specific "interrupted by another navigation" errors, remove the job from `jobs`, and insert into `stale_jobs`.
- **Result:** Verified via `scripts/test_bug_007.ts` simulation and real run monitoring. Successfully cleaned artifacts.
