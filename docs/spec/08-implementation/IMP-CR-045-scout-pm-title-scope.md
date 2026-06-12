# IMP-CR-045: Scout PM Title Scope Hardening

## Requirements
- `FR-240`, `AC-209`–`AC-214`

## Changes
- `passesBroadPmTitleScope()` promoted to `scripts/domain/gates.ts`
- WWR: product RSS only; broad PM scope at ingest
- Himalayas: broad PM scope at ingest
- Extended deny patterns for adjacent roles: program manager, solutions engineer, sales development, customer success, account executive.

## Verification
- `npm test -- tests/unit/gates.test.ts -t passesBroadPmTitleScope` — PASS
- `npm test` — PASS
- `python scripts/test_smoke_regression.py` — PASS

## Out of scope
- Remotive / Jobicy / OpenPostings (search-term filtered; no incident data)
- Retroactive DB cleanup of 2026-06-11 junk rows (manual, see Task 6 in plan)
