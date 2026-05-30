# CR-027: Deterministic Industry Blocklist Gate

## Metadata

| Field | Value |
|---|---|
| **CR ID** | `CR-027` |
| **Date** | 2026-05-30 |
| **Status** | Implemented |
| **Priority** | P1 |
| **Author** | Jason Taylor / Agent |
| **Implements** | `FR-170` |
| **Related** | `FEAT-001`, `FEAT-002`, `FEAT-009`, `CR-021` |

## Problem statement

Job Search UI persists `industryBlocklist` → `blocked_industries` in `candidate_preferences.json`, and `job_fit_engine.md` instructs the LLM to reject blocked industries. Scout and batch zero-token gates **did not enforce** this field, so unwanted sectors (gaming, crypto, ad tech, etc.) entered scrape and fit evaluation despite user configuration.

## Solution overview

1. Add `scripts/industry_gate.py` — single source of truth for word-boundary industry matching.
2. Scout (`scout_local.ts`) — reject when **company name or job title** matches a blocked industry term (short description snippet only if &lt; 120 chars).
3. Batch (`passes_jd_keyword_gate`) — reject when company/title/header (first 600 JD chars) matches; **does not** scan full JD body to avoid false positives on client-industry mentions.
4. Unit tests in `test_smoke_regression.py` (no network).
5. Log pattern: `[REJECT] … industry_blocked:{term}` / `[ZERO-TOKEN REJECT] industry_blocked:{term}`.

## Acceptance criteria

| AC ID | Given | When | Then |
|---|---|---|---|
| `AC-175` | `blocked_industries` includes `Crypto` | Scout ingest company `Crypto.com` | Job rejected before DB insert |
| `AC-176` | `blocked_industries` includes `Crypto` | Batch zero-token gate on JD header mentioning crypto employer | Rejected before LLM fit |
| `AC-177` | `blocked_industries` empty | Scout + batch run | Industry gate is no-op |
| `AC-178` | B2B SaaS employer, no blocked term in company/title/header | Gates run | Job passes industry check |

## Out of scope (deferred)

- Full-JD industry NLP scan
- UI for `required_anchors` (see CR-028)
- Post-scrape HTTP liveness (CR-029 planned)

## Files changed

| File | Change |
|---|---|
| `scripts/industry_gate.py` | New gate module |
| `scripts/batch_pipeline.py` | Wire gate in `passes_jd_keyword_gate` |
| `scripts/scout_local.ts` | Wire gate in Phase 3 filter |
| `scripts/test_smoke_regression.py` | REG-08–REG-11 industry tests |
| `.agent/rules/job_fit_engine.md` | Note deterministic enforcement |
| `docs/spec/02-requirements-registry.md` | `FR-170`, `AC-175`–`AC-178` |

## Verification

```bash
python scripts/test_smoke_regression.py
```

Manual: set industry blocklist in Job Search UI, run sync, confirm `[REJECT] … industry_blocked:` in activity log for known sector employers.
