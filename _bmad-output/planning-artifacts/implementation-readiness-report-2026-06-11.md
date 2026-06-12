---
date: 2026-06-11
project: Applyr
assessor: bmad-check-implementation-readiness (manual run)
status: complete
stepsCompleted: [1, 2, 3, 4, 5, 6]
---

# Implementation Readiness Assessment Report

**Date:** 2026-06-11
**Project:** Applyr

---

## Document Inventory

| Document | Format | Location |
|---|---|---|
| PRD | Sharded folder | `_bmad-output/planning-artifacts/prds/prd-Applyr-2026-06-11/prd.md` |
| Architecture | Whole | `_bmad-output/planning-artifacts/architecture.md` |
| Epics & Stories | Whole | `_bmad-output/planning-artifacts/epics.md` |
| UX Design | Not found | — |

No duplicates. No conflicts.

---

## PRD Analysis

### Functional Requirements

31 FRs across 6 clusters.

| Cluster | FRs |
|---|---|
| Cluster 1 — Source Expansion | FR-101, FR-102, FR-103, FR-104, FR-105, FR-106, FR-107, FR-108 |
| Cluster 2 — Connector Architecture | FR-201, FR-202, FR-203, FR-204 |
| Cluster 3 — Raw Ingest & Dedup | FR-301, FR-302, FR-303, FR-304, FR-305, FR-306 |
| Cluster 4 — Scoring Calibration | FR-401, FR-402, FR-403, FR-404, FR-405 |
| Cluster 5 — Pipeline Observability | FR-501, FR-502, FR-503, FR-504, FR-505 |
| Cluster 6 — Crawl Governance | FR-601, FR-602, FR-603 |

**Total FRs: 31**

⚠️ Minor: FR-405 (Score Bands) appears in the PRD between FR-401 and FR-402, out of numeric order. Traceability is unambiguous but worth noting.

### Non-Functional Requirements

NFR-1: Idempotent, non-destructive schema migrations — 7 new tables, no data loss  
NFR-2: Local-first — no data egress  
NFR-3: TheirStack hard credit cap — 200 credits/month enforced in code  
NFR-4: Connector isolation — one failure cannot cascade  
NFR-5: Idempotent syncs — no duplicate jobs or raw ingest records  
NFR-6: API compliance — rate limits and ToS respected for all Lane 1 + TheirStack  

**Total NFRs: 6**

### PRD Completeness Assessment

PRD is complete and well-formed. Requirements are specific, bounded, and carry measurable success criteria. Three open questions remain unresolved (OQ-1, OQ-2, OQ-3) — two of which could block specific stories.

---

## Epic Coverage Validation

### Coverage Matrix

| FR | PRD Requirement Summary | Epic | Story | Status |
|---|---|---|---|---|
| FR-101 | Sources registry table | Epic 2 | 2.1 | ✅ Covered |
| FR-102 | Greenhouse connector | Epic 2 | 2.2 | ✅ Covered |
| FR-103 | Lever connector | Epic 2 | 2.2 | ✅ Covered |
| FR-104 | Ashby connector | Epic 2 | 2.3 | ✅ Covered |
| FR-105 | TheirStack connector (credit cap) | Epic 2 | 2.4 | ✅ Covered |
| FR-106 | Source health visibility | Epic 2 | 2.5 | ✅ Covered |
| FR-107 | Graceful source failure | Epic 2 | 1.5 + 2.1 | ✅ Covered (split across epics — see §5) |
| FR-108 | Workable connector | Epic 2 | 2.3 | ✅ Covered |
| FR-201 | JobConnector interface | Epic 1 | 1.1 | ✅ Covered |
| FR-202 | Refactor 12 existing connectors | Epic 1 | 1.2 + 1.3 + 1.4 | ✅ Covered |
| FR-203 | New connectors built to interface | Epic 2 | 2.2 + 2.3 + 2.4 | ✅ Covered |
| FR-204 | Connector isolation & testability | Epic 1 | 1.2 + 1.3 + 1.4 | ✅ Covered |
| FR-301 | Raw ingest store | Epic 3 | 3.1 | ✅ Covered |
| FR-302 | Job clusters table | Epic 3 | 3.2 | ✅ Covered |
| FR-303 | Source links table | Epic 3 | 3.2 | ✅ Covered |
| FR-304 | Formal deduplication layer | Epic 3 | 3.1 + 3.2 | ✅ Covered |
| FR-305 | Canonical UI presentation | Epic 3 | 3.3 | ✅ Covered |
| FR-306 | Source overlap visibility | Epic 3 | 3.3 | ✅ Covered |
| FR-401 | Job scores table | Epic 4 | 4.1 | ✅ Covered |
| FR-402 | Score breakdown in job detail | Epic 4 | 4.2 | ✅ Covered |
| FR-403 | Lever validation | Epic 4 | 4.3 | ✅ Covered |
| FR-404 | Scoring test coverage | Epic 4 | 4.4 | ✅ Covered |
| FR-405 | Score bands (4-tier routing) | Epic 4 | 4.3 | ✅ Covered |
| FR-501 | Real-time source metrics via SSE | Epic 5 | 5.1 | ✅ Covered |
| FR-502 | Enhanced Sync Activity UI | Epic 5 | 5.2 | ✅ Covered |
| FR-503 | Per-stage handoff counts | Epic 5 | 5.1 + 5.2 | ✅ Covered |
| FR-504 | Live source health badges | Epic 5 | 5.1 + 5.2 | ✅ Covered |
| FR-505 | Post-run summary | Epic 5 | 5.1 | ✅ Covered |
| FR-601 | Domain policies table | Epic 1 | 1.4 | ✅ Covered |
| FR-602 | Crawl policy engine | Epic 1 | 1.4 | ✅ Covered |
| FR-603 | Existing crawl connectors governed | Epic 1 | 1.4 | ✅ Covered |

### Coverage Statistics

- Total PRD FRs: **31**
- FRs covered in epics: **31**
- Coverage percentage: **100%**

### Architecture FR Count Discrepancy

⚠️ The architecture document's Requirements Overview states "26 FRs across 6 clusters" but the actual count is 31. The requirements-to-structure mapping table within the same document correctly covers all 31. This is a stale summary line — no FRs are architecturally unaddressed, but the discrepancy could confuse implementation agents reading the doc header.

---

## UX Alignment Assessment

### UX Document Status

Not found.

### Assessment

This is a user-facing web application with two targeted UI additions:
- `JobDetailPanel.tsx` — score breakdown section (FR-402)
- `SyncActivityView.tsx` — live per-source metrics + health badges (FR-502–504)

The epics explicitly acknowledge the absence of a UX document and state that all UI changes are constrained additions to existing components, as defined by the PRD and architecture. Given the scope — two targeted additions to existing components with well-specified behavior in the acceptance criteria — the absence of a formal UX document is acceptable.

### Warnings

⚠️ No UX document. Both UI changes have sufficient behavioral spec in AC form. Not a blocker.

---

## Epic Quality Review

### Epic Structure Validation

#### User Value Focus

| Epic | Title | User Value | Assessment |
|---|---|---|---|
| Epic 1 | Connector Architecture Foundation | Developer/infrastructure | 🟠 Borderline — foundational work, necessary for brownfield |
| Epic 2 | Expanded Source Coverage | Clear user value | ✅ |
| Epic 3 | Raw Ingest & Deduplication | Clear user value | ✅ |
| Epic 4 | Scoring Transparency | Clear user value | ✅ |
| Epic 5 | Live Pipeline Observability | Clear user value | ✅ |

Epic 1 contains three developer stories (1.1, 1.2, 1.3 use "As a developer...") and two user-facing stories (1.4, 1.5). For a brownfield project where the infrastructure layer is a prerequisite for all user-facing work, this is pragmatic and acceptable. An agent cannot deliver Epic 2–5 without Epic 1's foundation.

#### Epic Independence

| Epic | Can Stand Alone | Prerequisite Declared | Assessment |
|---|---|---|---|
| Epic 1 | Yes | N/A | ✅ |
| Epic 2 | Depends on Epic 1 | Implicit (needs JobConnector interface) | ⚠️ Not explicitly declared in epic header |
| Epic 3 | Depends on Epics 1+2 | Not declared | ⚠️ Missing prerequisite declaration |
| Epic 4 | Largely independent | N/A (Python scoring is separate) | ✅ |
| Epic 5 | Depends on Epic 1 | ✅ Explicitly declared | ✅ |

Epics 2 and 3 have natural dependencies that are implicit but not stated in their headers. Epic 5 is the only one that explicitly declares its prerequisite. This is a minor consistency issue — no agent confusion expected given the story sequencing, but explicit declarations would be cleaner.

### Story Quality Assessment

#### Acceptance Criteria Review

All stories use Given/When/Then format. Criteria are specific, testable, and cover error paths. No vague criteria like "user can login." A few targeted observations:

**Story 1.3 — Connector scope vagueness**
🟠 "plus any remaining non-crawl connectors from scout_local.ts not covered in Batch 1" is hedge language. The architecture directory structure lists 9 non-crawl connectors (6 in Batch 1 + 3 in Batch 2). The PRD states 12 existing connectors. With 2 crawl connectors in Story 1.4, that accounts for 11 total. **One connector may be unaccounted for in the architecture listing.** An implementation agent must read `scout_local.ts` directly to confirm the full list before closing Story 1.3.

**Story 4.3 — Lever validation AC vagueness**
🟡 "Any mismatch between configured lever and actual gate behavior is identified and corrected in batch_pipeline.py" does not specify what the expected behavior IS for each lever. The implementation agent must derive expected behavior from the PRD lever descriptions and compare to code. Not a blocker (the PRD is the spec), but the AC could be more precise.

**Story 5.2 — Unstated dependency on Story 5.1**
🟡 Story 5.2 (UI consumes SSE events) clearly requires Story 5.1 (orchestrator emits SSE events) to be complete first, but this is not stated in the story. Within a sequential sprint, ordering is obvious — just worth noting.

#### Dependency Analysis

Within-epic story ordering is correct in all epics. No forward dependencies detected. Database tables are created exactly when first needed:

| Migration | Created In |
|---|---|
| schema_migrations (version table) | Story 1.1 |
| domain_policies | Story 1.4 |
| sources | Story 2.1 |
| job_ingest_raw | Story 3.1 |
| job_clusters + job_source_links | Story 3.2 |
| job_scores | Story 4.1 |

No "create all tables upfront" anti-pattern. ✅

#### Special Checks

**Brownfield project indicators:** ✅ Present and correct
- No starter template story
- Explicit "brownfield expansion" acknowledgment
- Additions-only constraint maintained throughout

**12th connector gap:** As noted in Story 1.3 review — architecture lists 11 existing connectors in the directory structure, PRD says 12. The "plus any remaining" language in Story 1.3 is the hedge. Not a planning failure — the story is written to catch this — but an agent must verify at implementation time.

**OQ-2 not resolved:** Story 2.4 specifies "filtered PM-role / US / recent query" for TheirStack but the exact filter parameters are not defined. The PRD explicitly marks this as needing Jason + Engineering alignment before FR-105 is built. Story 2.4 cannot be implemented fully without resolving the filter set first.

### Best Practices Compliance Checklist

| Check | Epic 1 | Epic 2 | Epic 3 | Epic 4 | Epic 5 |
|---|---|---|---|---|---|
| Delivers user value | ⚠️ Partial | ✅ | ✅ | ✅ | ✅ |
| Independent or explicit prerequisite | ⚠️ N/A | ⚠️ Implicit | ⚠️ Implicit | ✅ | ✅ |
| Stories appropriately sized | ✅ | ✅ | ✅ | ✅ | ✅ |
| No forward dependencies | ✅ | ✅ | ✅ | ✅ | ✅ |
| Tables created when needed | ✅ | ✅ | ✅ | ✅ | N/A |
| Clear acceptance criteria | ✅ | ✅ | ✅ | ⚠️ 4.3 partial | ✅ |
| FR traceability maintained | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## Summary and Recommendations

### Overall Readiness Status

**READY**

### Issues by Severity

#### 🟠 Major Issues (address before implementation of specific stories)

**M1 — Architecture doc states "26 FRs" but there are 31**
The architecture's Requirements Overview header is a stale count. The requirements-to-structure mapping within the same doc correctly covers all 31. Before implementation agents are deployed, update the architecture doc header to read "31 FRs." Risk: an agent counting from the header might assume coverage is complete when it isn't, or vice versa.

**M2 — 12th existing connector unaccounted for in architecture directory listing**
FR-202 says 12 existing connectors are refactored; the architecture lists 11 (9 non-crawl + 2 crawl). Story 1.3 hedges with "plus any remaining." Before beginning Story 1.3, the implementation agent must read `scout_local.ts` to produce a definitive list of all 12 connectors and verify none are missing from the directory structure.

**M3 — OQ-2 (TheirStack filter set) unresolved**
Story 2.4 cannot be fully implemented without defining the exact TheirStack query filter parameters (role keywords, country, date range). This was flagged in the PRD as needing Jason + Engineering alignment before FR-105 is built. Resolve before starting Epic 2.

#### 🟡 Minor Concerns (address during sprint planning or story development)

**m1 — Epic 2 and Epic 3 missing prerequisite declarations**
Both depend on earlier epics but only Epic 5 explicitly declares its prerequisite. Add a "Prerequisite: Epic X must be complete" line to Epic 2 and Epic 3 headers before sprint planning generates the ordered backlog.

**m2 — OQ-1 (Ashby auth) unresolved**
Story 2.3 includes a dev note flagging this. The implementation agent must verify whether Ashby uses a public board token or requires a private API key before starting FR-104. Not a planning blocker — the story already handles this — but Jason should have a decision ready.

**m3 — Story 4.3 lever validation AC is open-ended**
The AC defers to "documented expectations in the PRD" without specifying the expected behavior per lever in the story itself. Acceptable since the PRD is the spec, but an implementation agent will spend time cross-referencing. Consider adding lever-by-lever expected behavior as a dev note in Story 4.3 before sprint starts.

**m4 — Story 5.2 dependency on Story 5.1 unstated**
Implicit from story ordering, but add a dev note for clarity.

**m5 — No `tsconfig.json` path aliases for `shared/*`**
Flagged in the architecture as a nice-to-have. Without it, connectors import `shared/types/connectors.ts` via deep relative paths (`../../../shared/types/connectors.js`). Not a blocker but adds friction. Add to Story 1.1 or as a separate task in the sprint plan.

### Recommended Next Steps

1. **Fix the architecture doc FR count** (2-minute edit): change "26 FRs" to "31 FRs" in the Requirements Overview section.
2. **Resolve OQ-2 before Epic 2**: define the TheirStack filter parameters so Story 2.4 has a complete implementation spec.
3. **Add prerequisite declarations to Epic 2 and Epic 3 headers**: makes the epic dependencies explicit for sprint planning.
4. **Proceed to sprint planning**: all artifacts are ready for `bmad-sprint-planning`.

### Final Note

This assessment identified **2 major issues** and **5 minor concerns** across the planning artifacts. None of the major issues are plan blockers — they require small corrections before specific stories are started, not before sprint planning begins. The core architecture is coherent, FR coverage is 100%, story acceptance criteria are specific and testable, and the brownfield constraints are correctly enforced throughout. The planning is implementation-ready.
