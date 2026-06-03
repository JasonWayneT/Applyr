# CR-034 — Built In Strict Geo-Signal Hardening

## Status

accepted

## Problem

Built In detail pages often omit visible location text in the extracted JD body while location appears on listing cards. Under strict Remote/San Diego policy, legitimate remote roles were rejected by geo gate due to missing textual signal.

## Goal

Preserve strict location policy while reducing false geo rejects by carrying explicit listing-level location evidence (Remote or San Diego-area cues) into the scout description payload before deterministic gates run.

## Requirements

| ID | Summary |
|---|---|
| `FR-181` | Built In scout carries explicit listing location signals into strict geo gate input |
| `FR-182` | Built In scout starts from strict seed URL: Remote + Mid-level + Product Manager + USA + freshness window |
| `FR-183` | Built In card pre-filters: PM title scope + strict remote listing signal before detail-page fetch |
| `AC-184` | Given a Built In card with explicit `remote` (or SD-area) signal and a fetched JD, when scout runs, then geo gate evaluates that signal without broad source bypass |
| `AC-185` | Given non-remote/non-SD Built In listings, when scout runs, then geo gate still rejects out-of-bound roles |
| `AC-186` | Given Built In scout starts, when target URLs are built, then crawler uses strict single seed URL and does not crawl taxonomy fallback |
| `AC-187` | Given Built In card title is Product Marketing or Product Owner-only, when scout processes card, then reject before detail fetch |
| `AC-188` | Given Built In card shows "Remote or Hybrid" or "In-Office or Remote", when strict remote mode, then reject before detail fetch |

## Implementation

| File | Change |
|---|---|
| `scripts/scout_local.ts` | Capture Built In card text; prepend normalized location signal line to description only when explicit remote/SD cues are present |
| `scripts/scout_local.ts` | Replace broad target set with strict seed URL (`/jobs/remote/mid-level?...search=Product Manager...country=USA`) |
| `scripts/domain/gates.ts` | `passesBuiltInPmTitleScope`, `passesBuiltInStrictRemoteCard` for card-level pre-fetch filters |
| `scripts/scout_local.ts` | Apply FR-183 card filters before detail-page fetch when work setting is Remote |
| `tests/unit/gates.test.ts` | Add parse-years guard tests; FR-183 PM title and strict remote card tests |

## Out of scope

- No broad Built In remote-source bypass.
- No relaxation of Remote/San Diego location policy.
