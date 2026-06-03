# CR-037: Required Domain Experience Gate

## Metadata
- **Status**: Superseded by CR-039
- **Date**: 2026-06-02
- **Related Requirements**: `FR-190`, `FR-188`

## Problem
Local fit LLM passes roles that **require** vertical industry experience the candidate lacks (Cotiviti class — score 98 despite mandatory 3–5 years US healthcare payment integrity). CR-035 optional-domain injection also false-positives on `preferably` inside required-domain bullets.

## Decision
1. **Zero-token domain gate** — detect JD clauses that require N+ years in a vertical industry/sector; reject when `domain_experience` in candidate preferences does not include that vertical.
2. **Optional-domain fix** — do not inject `DOMAIN_REQUIREMENT: OPTIONAL` when required-domain years are present; tighten `preferred` vs `preferably` matching.
3. **Fit post-process cap** — force NO when LLM passes despite required-domain gap; skip anchor floor when domain gate fails.

## Out of scope
- LLM provider change; inferring domain from resume automatically (prefs-driven only).

## Acceptance criteria
| ID | Criterion |
|----|-----------|
| `AC-197` | JD requires 3–5 years US healthcare industry; candidate lacks healthcare in `domain_experience` → zero-token reject |
| `AC-198` | JD marks healthcare as optional ("nice plus" / "may not have experience") → domain gate passes; optional note still injected |
| `AC-199` | Cotiviti-class JD with LLM score 98 → post-process forces NO when domain gate fails |

## Implementation
- `scripts/domain_gate.py` — `check_domain_gate`, required-domain extraction
- `scripts/fit_policy.py` — optional-domain fix, anchor floor skip, enforce cap
- `scripts/batch_pipeline.py` — wire zero-token gate
- `data/candidate_preferences.example.json` — `domain_experience` field
