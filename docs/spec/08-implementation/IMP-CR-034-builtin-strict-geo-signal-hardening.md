# IMP-CR-034 — Built In Strict Geo-Signal Hardening

| Field | Value |
|---|---|
| **CR** | `CR-034` |
| **Requirement IDs** | `FR-181`, `FR-182`, `FR-183` |
| **Status** | implemented |

## Code map

| Requirement | File | Notes |
|---|---|---|
| `FR-181` | `scripts/scout_local.ts` | Built In card text parsed for explicit remote/SD cues; normalized location signal prepended to description before geo gate |
| `FR-182` | `scripts/scout_local.ts` | Built In target generation pinned to strict seed URL (`/jobs/remote/mid-level?...search=Product Manager...country=USA`) and taxonomy fallback removed |
| `FR-181` | `scripts/domain/gates.ts` | Strict geo policy unchanged (still requires remote or SD signals; no source-level bypass) |
| `FR-183` | `scripts/domain/gates.ts`, `scripts/scout_local.ts` | Card-level PM title scope + strict remote listing checks before detail-page fetch |
| guard quality | `tests/unit/gates.test.ts` | Large-number parse guard; FR-183 PM title and strict remote card tests |

## Verification

1. Run `SCOUT_BUILTIN_ONLY=1 npx tsx scripts/scout_local.ts`.
2. Confirm strict geo rejects remain for non-remote/non-SD Built In rows.
3. Confirm roles with explicit listing-level remote cue are no longer dropped solely due to missing detail-page location text.
4. Confirm no `required_years_90_exceeds_max_7` / `required_years_100_exceeds_max_7` false positives.
