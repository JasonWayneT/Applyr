---
title: Applyr Job Aggregator Expansion
status: final
created: 2026-06-11
updated: 2026-06-11
---

# Applyr — Job Aggregator Expansion PRD

## Problem Statement

Applyr's current sourcing layer works but does not give the user confidence that coverage is complete. Jobs surface without explanation of why they passed scoring. When a source fails or goes quiet, the system gives no signal. The pipeline is a monolith — when something goes wrong, there is no way to pinpoint where.

This expansion solves three compounding problems:

1. **Coverage** — the user cannot confirm that every available source is being pulled from on every run.
2. **Scoring transparency** — when a job surfaces that should not have, the user has no fast way to answer "why did this get through?"
3. **Pipeline observability** — failures are silent and stages are not independently inspectable.

---

## Vision

The user should be able to say with confidence: "I know which sources we pull from, I know they're working, and I know why every job that surfaces made it through." The expansion widens the sourcing net with official ATS connectors, structures the connector layer for long-term maintainability, and makes coverage and scoring legible in real time — without replacing anything that already works.

---

## Goals & Success Metrics

| Goal | Success Metric |
|------|---------------|
| Coverage confidence | Every configured source reports jobs fetched per run; a 0-result source triggers a visible warning in the Sync Activity UI |
| Scoring transparency | Score breakdown visible in job detail panel for every surfaced job; existing levers validated with test coverage confirming no known false rejections or false passes |
| Pipeline observability | Per-source metrics stream live to the Sync Activity UI during a run; source health badges reflect current state in real-time |

**Counter-metrics:**
- No increase in false-positive jobs surfacing (scoring calibration must not regress)
- No increase in sync duration beyond what new source volume warrants
- TheirStack API credits stay at or below 200/month

---

## Features

### Cluster 1: Source Expansion

**FR-101 — Source Registry**
Create a `sources` table as a registry for all job sources. Each record tracks: source name, type (ats_api / vendor_api / crawl), provider, base URL or API endpoint, authentication details, poll frequency, and current status (active / warning / error / paused).

**FR-102 — Greenhouse Connector**
Add Greenhouse as a Lane 1 ATS API connector using the public Job Board API. Fetches structured job postings directly from employer ATS systems. Implements the `JobConnector` interface (FR-201).

**FR-103 — Lever Connector**
Add Lever as a Lane 1 ATS API connector using the public postings feed. Implements the `JobConnector` interface.

**FR-104 — Ashby Connector**
Add Ashby as a Lane 1 ATS API connector using the public posting API. Targets newer startups and AI-native companies. Implements the `JobConnector` interface.

**FR-108 — Workable Connector**
Add Workable as a Lane 1 ATS API connector using the public widget/API. Implements the `JobConnector` interface.

**FR-105 — TheirStack Connector**
Add TheirStack as a Lane 2 vendor connector. Must use filtered queries (PM roles, US, recent postings) to stay within the 200 API credit/month hard cap. Credits are consumed per job record returned — unfiltered queries are not permitted. Implements the `JobConnector` interface.

**FR-106 — Source Health Visibility**
Source health states surface in the existing Sync Activity UI:
- **Warning** — source returned 0 jobs on a sync where it previously returned results, or an HTTP error occurred.
- **Error** — source has failed 3 or more consecutive syncs.
Health badges update live during a sync run.

**FR-107 — Graceful Source Failure**
A failing source does not block the rest of the pipeline. Each source connector runs independently; failures are logged to the sources table and surfaced via FR-106 without interrupting other sources.

---

### Cluster 2: Connector Architecture

**FR-201 — JobConnector Interface**
Define a formal TypeScript interface that all connectors must implement:

```ts
interface JobConnector {
  sourceId: string;
  fetchJobs(since?: string): Promise<RawJobPayload[]>;
  healthCheck(): Promise<ConnectorHealth>;
  normalize(raw: RawJobPayload): NormalizedJob;
}
```

This interface is the contract for all connectors — new and existing.

**FR-202 — Refactor Existing Connectors**
All 12 existing connectors currently in `scout_local.ts` are refactored into isolated modules implementing `JobConnector`. Connector behavior is preserved; only structure changes.

**FR-203 — New Connectors Built to Interface**
Greenhouse, Lever, Ashby, Workable, and TheirStack connectors are built as isolated modules implementing `JobConnector` from the start.

**FR-204 — Connector Isolation and Testability**
Each connector lives in its own module under a `connectors/` package. Each is independently testable with unit tests and example fixtures. Source-specific logic does not leak across connectors.

---

### Cluster 3: Raw Ingest & Deduplication

**FR-301 — Raw Ingest Store**
Create a `job_ingest_raw` table that stores every raw payload before normalization. Fields: source_id, fetched_at, external_job_id, payload_json, payload_hash (for change detection), http_status, request_url. Supports replay and debugging when upstream APIs change format.

**FR-302 — Job Clusters**
Create a `job_clusters` table that groups duplicate job records identified across sources into a single cluster.

**FR-303 — Source Links**
Create a `job_source_links` table that links every source copy of a job to its canonical record in the `jobs` table. One canonical job can have many source links.

**FR-304 — Formal Deduplication Layer**
Existing deduplication logic (URL normalization, Company + Title pair matching, vector similarity) is promoted into a formal dedup service that writes results to `job_clusters` and `job_source_links`. Logic is preserved; structure is formalized.

**FR-305 — Canonical UI Presentation**
The UI shows one canonical job record. Source attribution (which sources the job appeared in) is accessible as metadata on the job detail, not as separate job entries.

**FR-306 — Source Overlap Visibility**
The system tracks which sources contribute unique jobs vs. duplicating jobs already seen from other sources. This data is available in the sources table or run metrics for coverage analysis.

---

### Cluster 4: Scoring Calibration

**FR-401 — Job Scores Table**
Create a `job_scores` table storing the full scoring breakdown per job: component scores for each of the 4 LLM vectors (leadership fit, seniority fit, technical depth, transition potential), deterministic gate results (title blocklist, salary, location), total score, human-readable reason summary, and review state.

The PM fit scoring model uses the following component weights:

| Component | Weight | Notes |
|-----------|--------|-------|
| Role-family match | 30 pts | PM vs. adjacent non-PM roles |
| Domain match | 20 pts | AI, SaaS, platform, data, devtools |
| Seniority match | 15 pts | Mid-level / seniority fit |
| Work arrangement | 15 pts | Remote-first gets a boost |
| Company desirability | 10 pts | AI-native, B2B SaaS, platform-oriented |
| Location compatibility | 5 pts | US / San Diego / remote suitability |
| Compensation signal | 5 pts | Optional where salary data is available |

**FR-405 — Score Bands**
Jobs are bucketed into priority tiers based on total score. The system routes each job to the appropriate tier automatically:

| Score | Tier | Behavior |
|-------|------|----------|
| 85–100 | High priority | Triggers full action workflow (research, draft assets) |
| 70–84 | Review queue | Surfaced for manual review |
| 50–69 | Low-priority backlog | Available but not surfaced by default |
| < 50 | Hidden | Not shown in UI |

**FR-402 — Score Breakdown in Job Detail**
The score breakdown from `job_scores` is surfaced in the existing job detail panel. A user can open any surfaced job and immediately see why it scored the way it did — no pipeline debugging required.

**FR-403 — Lever Validation**
The existing scoring levers (title blocklist, industry blocklist, salary threshold, min fit score, location gate) are validated against documented expected behavior. Any mismatch between configuration and actual gate behavior is identified and corrected.

**FR-404 — Scoring Test Coverage**
Unit tests cover the deterministic gate (title blocklist, salary, location) and scoring thresholds. Tests include PM-positive examples (should pass) and non-PM examples (should be rejected) to catch regressions.

---

### Cluster 6: Crawl Governance

**FR-601 — Domain Policies Table**
Create a `domain_policies` table that governs all crawl activity. Each record tracks: domain, robots.txt review status and date, terms-of-service review status and date, max requests per second, cooldown window in seconds, and current status (allowed / paused / blocked / manual_review).

**FR-602 — Crawl Policy Engine**
No crawl connector may fetch a domain unless `domain_policies.status = allowed`. The policy engine gates every crawl request against this table before fetch. Rules:
- Never crawl a domain without an explicit `allowed` status
- Stop automatically after repeated 403 or 429 responses; update domain status to `blocked`
- Apply exponential backoff and jitter on 429 responses
- Do not attempt to bypass authentication walls, CAPTCHAs, or anti-bot measures
- Log every crawl decision (allowed / blocked / backoff) to the activity log

**FR-603 — Existing Crawl Connectors Governed**
The two existing Playwright crawl connectors (BuiltIn, Levels.fyi) are brought under the domain policy engine as part of the Cluster 2 refactor. Their domains are pre-reviewed and seeded into `domain_policies` with appropriate rate limits before the refactor ships.

---

### Cluster 5: Pipeline Observability

> **Dependency:** FR-501 through FR-505 are implemented after Cluster 2 (FR-201 through FR-204) is complete. Observability instrumentation is added to the clean connector seams — not to the monolith.

**FR-501 — Real-Time Source Metrics via SSE**
Each connector emits real-time metrics during a sync run via the existing SSE mechanism: jobs fetched, jobs filtered, jobs passed to scoring. Emitted per source, per stage.

**FR-502 — Enhanced Sync Activity UI**
The existing SyncActivityView displays live per-source counts during a sync: fetched / filtered / passed to scoring. Counts update in real-time as each connector completes.

**FR-503 — Per-Stage Handoff Counts**
Real-time counts are visible at each pipeline stage boundary: Scout → Backfill → Scrape → Evaluate. Users can see where jobs are being filtered out during the active run.

**FR-504 — Live Source Health Badges**
Source health badges (FR-106) update in real-time during a sync. A source that goes to warning or error mid-run is surfaced immediately in the Sync Activity UI.

**FR-505 — Post-Run Summary**
After each sync completes, a summary is written to the activity log: per-source job counts, any sources that went to warning or error, and total jobs passed to scoring.

---

## Non-Functional Requirements

| # | Requirement | Constraint |
|---|------------|------------|
| NFR-1 | Schema migrations are idempotent and non-destructive | 7 new tables added to a live SQLite database with existing data; no data loss permitted |
| NFR-2 | Local-first — no data leaves the user's machine | All new connectors fetch to local storage only; no cloud sync or telemetry |
| NFR-3 | TheirStack hard credit cap | Maximum 200 API credits/month; TheirStack connector must use filtered queries and enforce this limit in code |
| NFR-4 | Connector isolation | One connector failure cannot cascade to other connectors or block the pipeline |
| NFR-5 | Idempotent syncs | Running a sync twice produces the same result — no duplicate jobs, no duplicate raw ingest records |
| NFR-6 | API compliance | Rate limits and terms of service respected for all Lane 1 ATS connectors and TheirStack |

---

## Constraints & Out of Scope

### Hard Constraints

- Existing 12 connectors and their behavior are preserved through the Cluster 2 refactor
- Existing Python scoring pipeline (`batch_pipeline.py`) is not rewritten
- Existing React UI is preserved — additions only
- SQLite remains the database — no migration to PostgreSQL
- TheirStack usage stays within the 200 credit/month free tier

### Out of Scope

- New standalone dashboard — observability is added to the existing Sync Activity UI only
- Per-job scoring debug interface — score breakdown in the job detail panel (FR-402) is the full solution
- New scoring tuning controls — existing levers in Settings remain as-is
- Multi-user or SaaS deployment
- Interview prep or salary negotiation tooling
- LinkedIn scraper (remains decommissioned)
- External queue system (BullMQ, Redis) — existing SQLite mutex pattern is sufficient at current scale

---

## Open Questions

| # | Question | Owner | Needed by |
|---|----------|-------|-----------|
| OQ-1 | What authentication pattern does each ATS connector require? Greenhouse and Lever use public board tokens — confirm Ashby's pattern before implementation | Engineering | Cluster 1 implementation start |
| OQ-2 | What PM-specific query filters maximize TheirStack credit efficiency? Define the filter set (role keywords, country, date range) before the connector is built | Jason + Engineering | FR-105 implementation |
| OQ-3 | What is the minimum unit test coverage bar for connectors? | Engineering | Cluster 2 implementation start |

---

## Implementation Sequencing Note

All implementation work should be broken into session-sized chunks with clear handoff points to support resumption across context windows. The natural sequence is:

1. Schema migrations (all 7 new tables)
2. Cluster 2 — connector interface + refactor (prerequisite for everything else)
3. Cluster 6 — crawl governance (seed domain policies for existing crawl connectors as part of Cluster 2 refactor)
4. Cluster 1 — new source connectors (built on the interface from Cluster 2)
5. Cluster 3 — raw ingest + deduplication (runs after connectors exist)
6. Cluster 4 — scoring calibration (can run in parallel with Clusters 1–3)
7. Cluster 5 — pipeline observability (strictly after Cluster 2 is complete)
