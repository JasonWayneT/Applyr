# Agent Operating Rules for Spec Driven Development

This repository uses BMAD-informed Spec Driven Development. All AI agents must follow this file and **[SDD_PROCESS.md](file:///c:/Users/Jason/Desktop/Jason/Resource/Code%20Projects/JobAgent/SDD_PROCESS.md)** before making changes.

## Prime directive

**DO NOT EDIT CODE FIRST.** Every material change must begin with the documentation chain. Changing code without updating specs and business docs is a violation of project integrity.

1. Review the project constitution.
2. Review BMAD intake and existing requirements.
3. Identify or create the relevant requirement IDs.
4. Update feature, design, test, bug, or change specs as needed.
5. Update the traceability matrix.
6. Create or update implementation tasks.
7. Modify code.
8. Run verification.
9. Update docs with results and unresolved issues.

## Required reading order

1. `docs/spec/00-project-constitution.md`
2. `docs/spec/01-bmad-intake.md`
3. `docs/spec/02-requirements-registry.md`
4. Relevant files under `docs/spec/03-feature-specs/`
5. `docs/spec/06-traceability/traceability-matrix.md`

## The Three-Layer Rule

Every change must be reflected across all three layers:
- **Layer 1 (Business):** PRDs (`JobAgent_Architecture_and_PRD.md`), rules (`.agent/rules/`), or design system (`DESIGN.md`).
- **Layer 2 (Specs):** `docs/spec/` directory (Requirements, Feature Specs, Traceability).
- **Layer 3 (Code):** `scripts/`, `server/`, or `src/`.

## Requirement ID rule

Every code change must cite at least one requirement ID (`FR-*`, `NFR-*`, `BUG-*`, etc.) in the task description and implementation summary.

## Prohibited behavior

Agents must not:
- Invent requirements silently.
- Implement a feature that has no acceptance criteria.
- Treat generated code as the source of truth when docs disagree.
- Bypass the `CR-*` workflow for material changes.
- **Perform code-only changes.** (All three layers must be updated).
