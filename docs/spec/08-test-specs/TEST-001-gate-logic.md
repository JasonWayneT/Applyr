# Test Spec: TEST-001 Deterministic Gate Logic

## Metadata

- Test ID: `TEST-001`
- Type: unit
- Status: implemented | passing
- Related requirements: `FR-001` (job discovery), `FR-170+` (collection quality), `NFR-*` (zero-token rejection)
- Related acceptance criteria: `AC-*` in `FEAT-001-scouting.md`, `FEAT-002`, `FEAT-009`

## Purpose

Prove that the deterministic pre-filter gates in `scripts/domain/gates.ts` correctly classify jobs based on title, industry, geography, and seniority criteria — without making any LLM calls. These gates are the zero-token rejection layer; if they pass noise through, every downstream LLM call wastes tokens on a job that should have been rejected instantly.

## Preconditions

- `scripts/domain/gates.ts` is compiled and importable via `gates.js`
- `tests/fixtures/` contains any fixture data used by these tests
- Vitest is installed (`npm test` invokes `vitest run`)

## Test groups and cases

### `titleMatchesBlocked` — whole-word blocking

| Case | Input title | Block term | Expected |
|---|---|---|---|
| Whole word match | `Staff Product Manager` | `staff` | `true` |
| Substring inside word (not blocked) | `Staffing Coordinator` | `staff` | `false` |
| Case-insensitive match | `VP of Product` | `vp` | `true` |

### `parseMaxYearsRequired` — experience year extraction

| Case | Input text | Expected |
|---|---|---|
| Explicit minimum | `Minimum 5 years of experience required.` | `5` |
| Plus notation | `8+ years of product management experience.` | `8` |
| Range — takes max | `5-10 years experience preferred.` | `10` |
| "requires" phrasing | `Requires 3 years of experience.` | `3` |
| No years present | `Passion for product, great communicator.` | `null` |
| Multiple matches — takes highest | `3 years preferred, minimum 5 years required.` | `5` |
| Implausible values ignored (90 days, 100%) | `Onboarding in 90 days. 100% remote role.` | `null` |
| Plausible + outlier — keeps plausible | `Requires 8+ years; team supports 100+ products.` | `8` |

### `passesTitleBlocklist`

| Case | Input | Expected |
|---|---|---|
| Clean PM title | `Product Manager` | `true` |
| Staff prefix | `Staff Product Manager` | `false` |
| VP | `VP of Product` | `false` |
| Director | `Director of Product` | `false` |
| Junior | `Junior PM` | `false` |
| Empty string (no title) | `""` | `true` |

### `passesIndustryGate`

| Case | Expected |
|---|---|
| Clean tech company | `true` |
| Company name contains blocked word as whole word | `false` |
| Company name containing blocked word as substring only (e.g. DraftKings / gambling) | `true` |
| Title contains blocked industry word | `false` |
| Short description (≤120 chars) contains blocked word | `false` |
| Long description (>120 chars) contains blocked word | `true` — only title/company scanned in long JDs |
| Empty blocked industries list | `true` |

### `passesGeographicGate`

| Case | Expected |
|---|---|
| Description contains "remote" | `true` |
| US city mention in description ≥50 chars | `true` |
| UK-only role, no remote | `false` |
| Remote-only source (Remotive) with empty description | `true` |
| Non-remote source (Built In) with empty description, workSetting=Remote | `false` |
| Both UK and US mentioned | `true` |

### `passesBuiltInPmTitleScope` (BuiltIn-specific)

| Case | Expected |
|---|---|
| `Product Manager` | `true` |
| `Senior Product Manager` | `true` |
| `Product Owner, CIS` | `false` |
| `Product Owner / Product Manager` (dual title) | `true` |
| `Product Marketing Manager, SMB` | `false` |
| `DevOps Engineer` | `false` |

### `passesBuiltInStrictRemoteCard` (BuiltIn-specific)

| Case | Expected |
|---|---|
| `Remote United States Mid level` | `true` |
| `Remote or Hybrid United States` | `false` |
| `In-Office or Remote 10 Locations` | `false` |
| `San Diego, CA, USA` | `true` |

### `passesSeniorityGate`

| Case | Expected |
|---|---|
| Mid-level PM, 5 years required (within max 7) | `true` |
| Required years exceed max, description ≥80 chars | `false` |
| Blocked title (`Lead`) regardless of years | `false` |
| Description too short (<80 chars) to extract years | `true` — no rejection without evidence |
| Exactly at max years | `true` |
| One year over max, description ≥80 chars | `false` |

## Expected result

All cases above pass. `npm test` exits 0. No LLM call is made during any gate evaluation.

## Regression coverage

- Related bug IDs: `BUG-*` any gate regression bugs
- Known failure modes prevented:
  - Substring false positives on industry gate (DraftKings / gambling)
  - Overly aggressive year extraction from non-year numbers (percentages, day counts)
  - Geographic gate passing UK-only roles to the LLM
  - BuiltIn hybrid cards leaking through when workSetting=Remote

## Automation notes

- Test file: `tests/unit/gates.test.ts`
- Command: `npm test`
- Fixtures: `tests/fixtures/` (inline fixtures defined in the test file via `baseJob()` factory)
- Mocking: none — all functions are pure and deterministic
