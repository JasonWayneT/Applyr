# CR-009 — Built In Text Search Integration & Dual-Archetype Scraper

**Status:** Accepted
**Date:** 2026-05-14
**Author:** Antigravity

## Overview

Remedies a critical scouting gap where the application was missing the majority of matching Built In opportunities. Currently, the Built In crawler strictly scrapes the `/product-management` taxonomy page and relies on `.job-item` CSS card selectors. This Change Request integrates active text search (`/jobs?search=`) for all configured `SEARCH_TERMS` and introduces support for the `div[data-id="job-card"]` DOM structure natively utilized on Built In's search pages.

## Motivation

- **Scout Gap Elimination:** A diagnostic live crawl revealed **21 additional eligible new jobs** present on the Built In text-search results page that were fully absent from the high-level taxonomy page.
- **Selector Parity:** Built In applies completely different DOM layouts for standard search pages compared to taxonomy pages. The application must consume both to maximize pipeline coverage.
- **Query Coverage:** Expanding Built In scouting to process configured search terms like "Product Owner" or "Technical Product Manager" brings it into parity with the LinkedIn and Remotive ingestion pipelines.

## Requirements

| ID | Title | Description |
|----|-------|-------------|
| FR-078 | Dual-Archetype Built In Scraper | Upgrade `scoutBuiltIn` selector mapping to consume both `.job-item` (taxonomy) and `div[data-id="job-card"]` (search) layouts dynamically using combined selectors and resilient attributes like `[data-id="company-title"]`. |
| FR-079 | Multi-Term Built In Search Processing | Modify `scoutBuiltIn` to iterate across all candidate `SEARCH_TERMS`, generating dynamic `/jobs?search={term}` endpoints while maintaining backwards compatibility with the high-level taxonomy fallback. |

## Non-Functional Requirements

| ID | Description |
|----|-------------|
| NFR-006 | Total crawler time capped by reusing the browser page and adding deliberate 3-second random humanizing delays between queries to avoid rate-limiting. |

## Traceability Mapping

| File | Action |
|------|--------|
| `scripts/scout_local.ts` | Replace single `buildBuiltInUrl()` with a multi-endpoint iterator; rewrite selector queries to support `div[data-id="job-card"]` and data-attributes. |
