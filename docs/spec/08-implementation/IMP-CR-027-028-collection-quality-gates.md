# IMP-CR-027 / IMP-CR-028: Collection Quality Gates

## Metadata

| Field | Value |
|---|---|
| **CR IDs** | `CR-027`, `CR-028` |
| **Date** | 2026-05-30 |
| **Status** | Implemented |
| **Requirement IDs** | `FR-170`, `FR-171`, `FR-172`, `FR-173` |

## Code map

| Requirement | File | Symbol / notes |
|---|---|---|
| `FR-170` | `scripts/industry_gate.py` | `scout_industry_blocked`, `batch_industry_blocked`, `check_industry_gate` |
| `FR-170` | `scripts/scout_local.ts` | `passesIndustryGate()` — must stay aligned with Python |
| `FR-170` | `scripts/batch_pipeline.py` | `passes_jd_keyword_gate()` industry check |
| `FR-171` | `scripts/utils.py` | `passes_keyword_gate`, `get_must_have_keywords` |
| `FR-172` | `scripts/anchor_gate.py` | `check_anchor_gate`, `count_anchor_hits` |
| `FR-172` | `scripts/pipeline_env.py` | `anchor_gate_enabled()` |
| `FR-172` | `server/shared.ts` | Preserves `required_anchors`, `must_have_keywords`, `signal_keywords` |
| `FR-173` | `scripts/scout_local.ts` | Levels skip; Remote-only geo bypass |

## Verification

```bash
python scripts/test_smoke_regression.py
```

Expected: REG-08 through REG-14 pass without backend running.

## Deferred

- `freshness_status` column (CR-029)
- PM role taxonomy LLM (CR-030)
- Structured fit evidence JSON (CR-031)
