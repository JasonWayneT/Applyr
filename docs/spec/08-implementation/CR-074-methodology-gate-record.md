# CR-074 — Methodology Gate Record

**Project:** Applyr (existing)  
**Change:** Token-conscious authoring packet (Approach A)  
**Mode:** Lightweight (in-repo CR — personal tool cost/quality fix, not a new product)  
**Delivery path:** Software (Superpowers / Cursor implementation against CR + epics)

This is **not** a greenfield Stage 1 idea. Applyr already has BMAD/SDD. Per
`_project-methodology` + Applyr `docs/AGENTS.md`, material changes use **CR → registry →
traceability → epics → code**. Full Idea Validation / Product Brief / PRD for the whole
product are out of scope for this CR.

## Gate mapping (this CR)

| Gate | Methodology meaning | This CR |
|------|---------------------|---------|
| Gate 1 | Verdict + mode | **Passed 2026-08-06** — problem real (session token burn / ~13-agent workflows); verdict **go**; mode **lightweight** |
| Gate 2 | Build + path | **Passed 2026-08-06** — build Approach A; software path; reuse Applyr machinery (not rewrite) |
| Gate 3 | Spec approved → implement | **Passed 2026-08-06** — Jason approved CR-074 + epics (“can go ahead and get started”) |

## Artifacts

| Artifact | Path |
|----------|------|
| Change request | `docs/spec/05-change-requests/CR-074-token-conscious-authoring-packet.md` |
| Epics & stories | `docs/spec/08-implementation/CR-074-token-conscious-authoring-packet-epics.md` |
| Requirements | `FR-252`–`FR-255`, `NFR-007`, `AC-272`–`AC-277` in registry |
| Traceability | `docs/spec/06-traceability/traceability-matrix.md` |
| Token baseline | `docs/reports/cr074-token-baseline.md` (Epic 1) |
| Calibration | `docs/reports/cr074-calibration-report.md` (Epic 7) |

## Closeout

**Closed 2026-08-06.** Epics 1–7 implemented. Counted calibration set (Limble, Camunda, Paylocity)
all mechanical PASS + Jason send-ready Y (Ncontracts skipped). Epic 8 (optional local assists)
remains deferred. Default authoring path is now CR-074 in `generate-submission` v2.1.0 +
AGENTS.md/CLAUDE.md.