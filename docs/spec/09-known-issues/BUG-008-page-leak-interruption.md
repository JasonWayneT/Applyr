# Known Issue: BUG-008 Overlapping Page Navigation Leak

## Metadata

- Bug ID: `BUG-008`
- Status: fixed
- Severity: critical
- Found in: v3.2.1
- Fixed in: v3.2.2
- Related requirements: `FR-035`, `FR-052`

## Current behavior

When `scrape_new_jobs.ts` iterates through multiple job links, it reuses a single `page` instance. Background network activities or pending client-side redirects from the *previous* job execution leak into the subsequent loop iteration. When Playwright executes the next `page.goto()`, the delayed previous-hop redirect fires, raising the "interrupted by another navigation" error. 

Because the system interprets this exception as a "dead link" (BUG-007 logic), legitimate jobs—especially those utilizing legitimate multi-hop ad redirection chains like Adzuna—were incorrectly flagged as stale and purged from the active queue.

## Expected behavior

The scraper should properly isolate the execution context of each job URL to prevent cross-execution state leakage.

## Root cause

Reusing the same Playwright `Page` instance without closing it between iterations allowed delayed async navigation triggers from the previous job to interrupt the load cycle of the next job.

## Fix Implementation

Refactored `scrape_new_jobs.ts` to instantiate a fresh `page` instance inside the loop boundary and strictly ensure `await page.close()` fires in the `finally` block before proceeding to the next company. Increased the post-load wait timer to 6s to accommodate heavy aggregators.

## Verification

- **Recovery:** Restored 93 false-positively nuked jobs from `stale_jobs` to `jobs` table using `restore_stale_jobs.ts`.
- **Smoke Test:** Verified using `scripts/test_fixed_scrape.ts` which confirmed sequential Adzuna-to-Monster multi-hop redirect chains resolved successfully without interruption errors.
