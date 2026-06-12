# Test Spec: TEST-002 JD Quality Assessment

## Metadata

- Test ID: `TEST-002`
- Type: unit
- Status: implemented | passing
- Related requirements: `FR-*` (job description scraping and quality validation), `NFR-*` (extraction quality thresholds)
- Related acceptance criteria: `AC-*` in `FEAT-001-scouting.md`

## Purpose

Prove that the JD quality assessment module (`scripts/domain/jdQuality.ts`) correctly identifies whether a scraped job description contains structured role content versus boilerplate, assigns an extraction confidence level, and generates data quality flags. This prevents low-quality JDs from flowing into the LLM scoring stage — which would waste tokens and produce unreliable fit scores.

## Preconditions

- `scripts/domain/jdQuality.ts` compiled and importable via `jdQuality.js`
- `scripts/extract_job_page.ts` compiled and exportable — provides `MIN_JD_CHARS` and `BUILTIN_MIN_JD_CHARS` constants
- Vitest installed (`npm test`)

## Test groups and cases

### Extraction constants sanity check

| Constant | Expected value | Invariant |
|---|---|---|
| `MIN_JD_CHARS` | `200` | Generic extraction threshold — must not change without a CR |
| `BUILTIN_MIN_JD_CHARS` | `500` | BuiltIn-specific threshold — must be greater than `MIN_JD_CHARS` |

These tests function as change detectors: if someone raises or lowers a threshold, the test fails and forces a documented decision.

### `hasRoleSignal` — structured content detection

| Case | Input | Expected |
|---|---|---|
| Contains "Responsibilities" | `Key Responsibilities\n- Own the product roadmap` | `true` |
| Lowercase "responsibilities" | `Your responsibilities include shipping features` | `true` |
| Contains "requirements" | `Requirements\n- 3+ years of product experience` | `true` |
| Contains "qualifications" | `Minimum Qualifications\n- Bachelor degree required` | `true` |
| Contains "you will" | `In this role you will lead cross-functional teams` | `true` |
| Contains "about the role" | `About the Role\nWe are looking for a PM` | `true` |
| Contains "in this role" | `In this role, you will define roadmap priorities` | `true` |
| Case-insensitive | `RESPONSIBILITIES include building a roadmap` | `true` |
| Pure company boilerplate | `We are a fast-growing startup focused on innovation and culture.` | `false` |
| Benefits-only text | `We offer unlimited PTO, health insurance, and 401k matching.` | `false` |
| Empty string | `""` | `false` |

### `classifyConfidence` — extraction confidence level

| Source method | JD content | Expected confidence |
|---|---|---|
| `structured` | Long JD with role signals | `high` |
| `dom` | Long JD with role signals | `medium` |
| `dom` | Boilerplate, no role signal | `low` |
| `body` (fallback) | Any content | `low` — body fallback is always low confidence |
| `structured` | Empty string | `low` |
| `structured` | Under 100 characters | `low` — too short regardless of method |

### `buildDataQualityFlags` — flag generation

| Case | Source | JD content | Expected flags |
|---|---|---|---|
| Clean, structured, long JD | `dom` | Role signals + >2×MIN chars | `[]` (no flags) |
| No role signals | `dom` | Company boilerplate | `['no_requirements_section']` |
| Short JD | `dom` | `<2×MIN chars` | `['short_jd']` |
| Body source | `body` | Clean, long JD | `['body_fallback']` |
| Body source + no signal | `body` | Company boilerplate | `['no_requirements_section', 'body_fallback']` |
| Exactly 2×MIN chars | `dom` | Role signals | `[]` — boundary: at exactly 2×MIN no short_jd flag |

## Expected result

All cases above pass. `npm test` exits 0.

## Regression coverage

- Related bug IDs: any bugs where boilerplate JDs passed fit scoring
- Known failure modes prevented:
  - High-confidence classification of `body`-extracted JDs (always low regardless of content)
  - `short_jd` flag missing on genuinely thin job descriptions
  - Role signals missed due to case-sensitivity

## Automation notes

- Test file: `tests/unit/jdQuality.test.ts`
- Command: `npm test`
- Fixtures: inline — no external fixture files
- Mocking: none — all functions are pure
