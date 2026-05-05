# BMAD Intake

Paste or summarize BMAD outputs here. This is the staging area before requirements are normalized into project specs.

## Source artifacts

| Source ID | BMAD artifact | Owner/agent | Date | Link or location | Status |
|---|---|---|---|---|---|
| `BMAD-SRC-001` | Architecture & PRD | PM/Arch | 2024-05 | `JobAgent_Architecture_and_PRD.md` | imported |
| `BMAD-SRC-002` | Applyr Design System | UX | 2024-05 | `DESIGN.md` | imported |
| `BMAD-SRC-003` | WebApp PRD 5.0 | PM | 2024-05 | `JobAgent_WebApp_PRD 5.0.md` | imported |
| `BMAD-SRC-004` | Pipeline Controller | Dev | 2024-05 | `.agent/Instructions.md` | imported |
| `BMAD-SRC-005` | Job-Fit Engine | PM | 2024-05 | `.agent/rules/job_fit_engine.md` | imported |
| `BMAD-SRC-006` | Claim Verifier | PM | 2024-05 | `.agent/rules/claim_verifier.md` | imported |
| `BMAD-SRC-007` | Research Contract | PM | 2024-05 | `.agent/rules/Research_Packet_Contract.md` | imported |

## Artifact mapping

| BMAD output | Destination spec |
|---|---|
| Core Philosophy / Goals | `00-project-constitution.md` |
| Scoring Rules | `02-requirements-registry.md`, `FEAT-002-evaluation.md` |
| Drafting Logic | `02-requirements-registry.md`, `FEAT-004-drafting.md` |
| Design System | `DESIGN-001-applyr-ui.md` |
| Pipeline Sequence | `FEAT-001` through `FEAT-005` |

## Normalization notes

- **Import Log (2024-05-04):** Retroactive import of all existing project documentation.
- **Assumptions:** Existing Python scripts are treated as the baseline implementation of these requirements.
- **Conflicts:** None found; PRD and code are currently in sync regarding the 6-stage pipeline.

## Import log

| Date | Imported by | Source IDs | Result | Follow-up |
|---|---|---|---|---|
| 2026-05-04 | Antigravity | BMAD-SRC-001 to 007 | Success | Normalize IDs in Registry |
