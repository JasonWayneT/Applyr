# CR-010 — Decommission LinkedIn Scouting Pipeline

**Status:** Accepted
**Date:** 2026-05-14
**Author:** Antigravity

## Overview

Decommissions the LinkedIn browser-based ingestion module within the local scraping utility (`scout_local.ts`). This mitigates severe security and session risks associated with automated LinkedIn scraping, aligning the application with the user's directive to minimize high-risk automation vectors while maintaining support for remaining board sources.

## Motivation

- **Risk Mitigation:** Automated browser logins and scraping heuristics on LinkedIn present an extremely high probability of account restriction and captchas.
- **Consolidation:** Removing the LinkedIn pipeline guarantees zero high-risk automated activity originates from the app's browser session on that domain, prioritizing stable and compliant sources (Built In, Remotive, WWR, Adzuna).

## Requirements

| ID | Title | Description |
|----|-------|-------------|
| FR-080 | LinkedIn Scouting Decommission | Permanently disable or excise LinkedIn data collection logic within `scripts/scout_local.ts`. Zero requests shall be dispatched to `linkedin.com` during routine pipeline execution. |

## Traceability Mapping

| File | Action |
|------|--------|
| `scripts/scout_local.ts` | Remove LinkedIn configuration consts, URL builders, `scoutLinkedIn` function body, and its main-thread invocation. |
