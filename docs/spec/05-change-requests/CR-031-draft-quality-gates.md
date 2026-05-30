# CR-031: Draft Quality Gates (Phased)

## Summary

Implements phased resume/cover quality hardening from the CR-031 plan review: baseline reporting, unified metrics policy, catalog validation, anti-claim loading, optional strict fail-closed flags, claim-strength manifest metadata, fit-summary gate, and Document Editor light verification.

## Requirements

| ID | Description |
|----|-------------|
| FR-174 | Unified `approved_metrics.py` single source for numeric validation |
| FR-175 | Catalog validation + anti-claim hints from workExperience |
| FR-176 | Optional strict gates: `STRICT_COVER_AUDIT`, `STRICT_METRICS`, `STRICT_ANTI_CLAIMS`, `STRICT_CATALOG_DRIFT` |
| FR-177 | Document Editor light verify before PDF recompile |
| FR-178 | Claim strength labels in `draft_manifest.json` |
| FR-179 | Baseline quality gate report script |

## Flags (default off)

- `STRICT_COVER_AUDIT=1` — fail compile when cover audit grade != Pass
- `STRICT_METRICS=1` — raise on unapproved numerics in verification chain
- `STRICT_ANTI_CLAIMS=1` — enforce anti-claim hints (always raises on match when hints exist)
- `STRICT_CATALOG_DRIFT=1` — fail compile on catalog validation errors
- `ALLOW_FIT_SUMMARY=1` — allow fit-eval sentence in resume summary (default off)

## Verification

- `python scripts/baseline_quality_gates.py`
- `python scripts/verify_master_claims.py`
- `python scripts/smoke_draft_compiler.py`
