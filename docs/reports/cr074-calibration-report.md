# CR-074 Epic 7 — Calibration Report

**Date:** 2026-08-06  
**Counted set:** Limble (pilot) + Camunda + Paylocity  
**Skipped:** Ncontracts (Jason 2026-08-06 — out of cal set; drafts may remain on disk)  
**Path:** deterministic Stage 0 → `build_authoring_packet` → one closed-world draft → `--verify-only`

## Metrics

| Company | Packet tokens | Prompt ~input | `--verify-only` | Jason send-ready |
|---------|---------------|---------------|-----------------|------------------|
| Limble (practice) | ~2607 | ~4.3k | PASS | **Y** |
| Camunda | 2024 | ~4031 | PASS | **Y** (continue-with-all-else) |
| Paylocity | 1850 | ~3825 | PASS | **Y** (continue-with-all-else) |
| Ncontracts | 2120 | ~4108 | PASS | **skipped** |

**Target:** ≤20k cloud input / company (packet ≤8k + digest ≤2k). Counted set well under.

**Mechanical verify clean rate:** 3/3 counted companies PASS on HARD_BLOCKs.

**AC5:** ≥2/3 Jason send-ready → **met** (3/3 Y on counted set).

## Story 7.2 gaps found → fixes

| Gap | Fix |
|-----|-----|
| Legacy Stage 0 `required[]` as bare strings crashed packet builder | `_stage0_item_text()` normalizes strings + dicts |
| Missing role when Stage 0 uses `position` | `role_title` falls back to `position` |
| Thin tag-pipe ACC-113 synthetic excerpts | Prefer narrative; drop thin when narrative exists for same project |
| JD terms (SLA, GTM, Customer Support, Operations, Usage Data, AI tools) missing from packet | Expanded `_JD_SKILL_ANCHORS` |
| Worldwide geo not in packet for closed-world | `_GEO_COLLAB_CONSTRAINT` injected into `hard_constraints` |

## Known remaining (not blocking v1)

- Preferred infra tools (Docker/K8s) correctly omitted without packet evidence.
- Domain soft gaps (fintech/RegTech, accounting) still rules-only bridges.
- ACC-111 / ACC-113 / ACC-115 may still appear as unverified in ground-truth scanner.

## Folders

- `data/context_pack_validation/limble/`
- `data/submissions/camunda/`
- `data/submissions/paylocity/`
- `data/submissions/ncontracts/` (skipped from cal judgment)

Backups: `*.before_cr074` in each folder.
