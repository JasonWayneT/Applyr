# CR-088: master_claims Catalog Hygiene + Claim-Construction Standard

## Metadata
- **Status**: Implemented (2026-08-10)
- **Date**: 2026-08-10
- **Source**: session-007 R14–R18 (Jason green-lit; Cursor builds; Claude Code peer ack R15–R16)
- **Related**: CR-085 (packet text wiring), CR-086/087 (matching precision); catalog is now the bottleneck after packaging/scoring fixes
- **Requirement IDs**: None formally registered — retrieval catalog integrity

## Problem
Packet retrieval scores `master_claims` tags/metadata. Catalog gaps and uneven claim fields therefore look like matcher bugs:

1. `ACC-119` (tools inventory) exists in `workExperience.md` but has no claim lens — correct path is `skills_catalog.json`, which was missing **Pendo** (and other ACC-119 tools) despite `ACC-117-PENDO` and `_JD_SKILL_ANCHORS`.
2. `check_ground_truth_coverage.py` still treated `ACC-111`/`113`/`115` as `UNVERIFIED` after they landed in WE (2026-08-10).
3. High-risk lenses (`ACC-204-*`, `ACC-111-SCOPE`) lacked `attribution` / `prohibited_claims` that WE already states.
4. No written standard for claim shape, including **rollup/synthesis** claims (e.g. `ACC-101-RETENTION` / MET-04 collective attribution).
5. No mechanical WE↔claims coverage audit (mis-keys and missing ACCs only found by hand).

(ACC-101-RETENTION `project_id` ACC-116→ACC-101 was fixed by Claude Code before this CR's build; not duplicated.)

## Decision
1. **No ACC-119 claim lens.** Tools stay on `skills_catalog.json`. Add missing ACC-119 tools (Pendo required; Productboard/Zoom/Airtable added for inventory parity).
2. Clear stale `UNVERIFIED_PROJECT_IDS` for ACC-111/113/115.
3. Document `ACC-401` as intentional **side corpus** (`data/aiProjects.md`), not a WE ACC.
4. Land `data/CLAIMS_STANDARD.md` (construction rules, including rollup/synthesis).
5. `scripts/audit_claims_coverage.py` — ERROR for mis-key / phantom / missing WE ACC (ACC-119 allowlisted); WARN for high-risk missing attribution/prohibited. Default WARN-print; `--strict` fails on ERROR. Wired into `run_all_tests.py`.
6. Fill P4 priority fields: `ACC-204-QA`/`GLOBAL`, `ACC-111-SCOPE` (mirror ENTERPRISE + WE DO NOT CLAIM; plain-language SCOPE `text` without printing Visible).

## Acceptance Criteria
| ID | Criterion |
|----|-----------|
| AC1 | `skills_catalog.json` includes Pendo; Productboard/Zoom/Airtable present if listed in WE ACC-119 |
| AC2 | `UNVERIFIED_PROJECT_IDS` no longer contains ACC-111/113/115 |
| AC3 | `CLAIMS_STANDARD.md` exists and names rollup/synthesis + ACC-401 side corpus |
| AC4 | `audit_claims_coverage.py` clean on ERROR tier; ACC-119 allowlisted; ACC-401 allowed |
| AC5 | ACC-204 both lenses + ACC-111-SCOPE have attribution + prohibited_claims grounded in WE |
| AC6 | Packet eval should-surface floor **≥ 28/35**; Camunda ACC-120 FP must not return |
| AC7 | Context pack / tags_only regen FRESH after claim edits |

## Out of Scope
- Ontology / BM25 / embeddings / further scorer CRs
- Mass rewrite of healthy lenses
- New ACC-119 claim entries
- Rewriting legacy `cover_story` as author input
