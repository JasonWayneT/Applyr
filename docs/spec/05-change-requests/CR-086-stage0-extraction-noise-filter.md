# CR-086: Stage0 Extraction-Noise Filter (Non-Requirement Headers + Physical/Comp/Legal)

## Metadata
- **Status**: Implemented (2026-08-10)
- **Date**: 2026-08-10
- **Source**: session-007 R11–R12 (Jason green-lit; Cursor builds)
- **Related**: CR-085 (packet packaging/domination — distinct; phrase boilerplate stays there),
  CR-074 Stage0, packet-level eval `scripts/eval_packet_selection.py` / `data/reports/cr086-packet-eval/`
- **Requirement IDs**: None formally registered — extraction hygiene

## Problem
Packet-level selection eval after CR-085 hit **30/35 (86%)** should-surface recall. Residual
defect class is **unsupported promotion of lines that were never hire criteria**:

Measured on live AMN Healthcare Stage0 extraction (reproduced 2026-08-10):

| Line captured into `required` | Should be |
|---|---|
| `Job Responsibilities` | responsibilities **section header** (switch bucket) |
| `Our Core Values` | culture **section header** |
| `Work Environment / Physical Requirements` | ignore / end quals collection |
| `Work is performed in an office/home office environment.` | physical boilerplate |
| `Team Members must have the ability to operate standard office equipment…` | physical boilerplate |
| `AMN Healthcare will provide reasonable accommodations…` | ADA/legal boilerplate |
| `Final pay rate is dependent on experience…` | compensation boilerplate |

These consume evidence_map rows and pull arbitrary claims (ACC-113, ACC-120, ACC-303, etc.).
Camunda-class false positives remain a separate scoring issue; this CR only stops **non-requirements
from being scored at all**.

Distinct from CR-085's `_BOILERPLATE_PHRASES` in `build_authoring_packet.py` (generic-but-real
phrases like "team player" on preferred/responsibilities only, never required).

## Decision
1. Expand Stage0 `_SECTION_HEADERS` so mid-JD headers switch buckets instead of becoming items:
   - responsibilities: `job responsibilities`
   - culture: `(our) core values`
   - preferred (optional lead-in headers): `key capabilities (for success)`
2. Expand `_IGNORE_SECTION_HEADERS` for work-environment / physical-requirements style headers
   (ends current quals bucket; discards following body until a known quals header).
3. Expand `_is_boilerplate_item` / `_BOILERPLATE_ITEM_RE` for physical office, ADA accommodations,
   and "final pay rate / pay dependent on experience" compensation lines.
4. Add orphan-header safety net: short Title-Case / trailing-colon lines with no requirement verb
   that still slip through as items are dropped (logged).
5. Remeasure packet-level eval + AMN/Camunda/Thermo supplemental after land. Success bar:
   AMN/Thermo header rows gone from evidence_map; should-surface hit rate must not regress below
   ~30/35.

## Acceptance Criteria
| ID | Criterion |
|----|-----------|
| AC1 | AMN JD: `Job Responsibilities` / `Our Core Values` / `Work Environment…` are not in `required` items; following real duties route to responsibilities; core-values body to culture or ignored |
| AC2 | AMN JD: office/physical/ADA/final-pay lines not in any scored bucket (required/preferred/responsibilities) |
| AC3 | Existing `test_build_stage0_fit_gate.py` suite still passes |
| AC4 | Packet eval should-surface hit rate ≥ 30/35 on the same resolvable corpus (no recall regression) |
| AC5 | New unit tests cover AMN-shaped header bleed and physical/comp boilerplate |

## Out of Scope
- Min-relevance scoring threshold, capability ontology, BM25, embeddings/LLM primary retrieval
- CR-085 phrase boilerplate on required ("strong communication skills")
- ACC-101-RETENTION `project_id` mis-key (separate tiny hygiene)
- Camunda lexical false positives on *real* responsibility lines (scoring signal — later)
