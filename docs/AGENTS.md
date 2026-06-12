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

1. `docs/ACTIVE_WORKFLOW.md` — runtime truth (scout, evaluate, draft, verify)
2. `docs/spec/00-project-constitution.md`
3. `docs/spec/02-requirements-registry.md`
4. Relevant files under `docs/spec/03-feature-specs/`
5. `docs/spec/06-traceability/traceability-matrix.md`
6. `docs/spec/01-bmad-intake.md` (historical sources only)

**Deprecated for active work:** `.agent/archive/**`, `.agent/workflows/*` stubs, `docs/history/JobAgent_WebApp_PRD 5.0.md`

## The Three-Layer Rule

Every change must be reflected across all three layers:
- **Layer 1 (Business):** PRDs (`docs/history/JobAgent_Architecture_and_PRD.md`), rules (`.agent/rules/`), or design system (`docs/DESIGN.md`).
- **Layer 2 (Specs):** `docs/spec/` directory (Requirements, Feature Specs, Traceability).
- **Layer 3 (Code):** `scripts/`, `server/`, or `src/`.

## Requirement ID rule

Every code change must cite at least one requirement ID (`FR-*`, `NFR-*`, `BUG-*`, etc.) in the task description and implementation summary.

## GitHub & Release Notes Rule

When pushing changes to GitHub, agents MUST generate and append a Firefox-style release note to `PRODUCT_CAPABILITIES_AND_RELEASE_NOTES.md` before or immediately after the push. All significant changes (New, Fixed, Changed, Developer) must be documented following the established template.

## Prohibited behavior

Agents must not:
- Invent requirements silently.
- Implement a feature that has no acceptance criteria.
- Treat generated code as the source of truth when docs disagree.
- Bypass the `CR-*` workflow for material changes.
- **Perform code-only changes.** (All three layers must be updated).

## Requirement ID namespaces

Every code change must cite at least one requirement ID in the task description and implementation summary. Valid namespaces:

| Prefix | Meaning |
|---|---|
| `FR-*` | Functional requirement |
| `NFR-*` | Non-functional requirement |
| `UX-*` | User experience requirement |
| `DES-*` | Visual or interaction design requirement |
| `ARCH-*` | Architecture requirement |
| `DATA-*` | Data, schema, retention, import, or export requirement |
| `SEC-*` | Security, privacy, auth, permissions, or compliance requirement |
| `INT-*` | Integration requirement |
| `OPS-*` | Deployment, observability, reliability, or operations requirement |
| `AC-*` | Acceptance criterion |
| `TASK-*` | Implementation task |
| `TEST-*` | Test case or verification requirement |
| `BUG-*` | Known bug, regression, or defect |
| `ADR-*` | Architecture decision record |
| `CR-*` | Change request |

Do not reuse an ID for a different meaning. Do not delete an ID without recording a replacement or deprecation.

---

## Coding standards

### TypeScript (`server/`, `src/`, `scripts/*.ts`)

- Strict TypeScript — `"strict": true` in `tsconfig.json`. No `any` without an inline comment explaining why.
- Named exports preferred over default exports.
- Functional style preferred over class-based where logic is stateless.
- All code changes satisfying a requirement must include `// Implements <ID>` inline at the relevant line.
- File naming: camelCase for modules, kebab-case for route and utility files.
- No floating top-level side-effectful code outside named functions.

### Python (`scripts/*.py`)

- PEP 8 style — 4-space indentation, 100-character line limit.
- Type hints on all function signatures.
- Every function needs a one-line docstring stating what it does, its args, and its return value.
- Technical choices not in the spec must be commented inline with the requirement ID they serve.
- No dependencies not already in `requirements.txt` — flag before adding any.

---

## Testing standards

Tests are not optional and are not written after the fact.

### TypeScript unit tests

- Framework: **Vitest** — `npm test` runs the unified test runner (or `npm run test:vitest` for vitest directly)
- Test files live in `tests/unit/`. Mirror the source structure: `server/routes/jobs.ts` → `tests/unit/jobs.test.ts`
- Fixtures live in `tests/fixtures/`
- Write the failing test first, watch it fail, implement, watch it pass, then commit
- Test failure paths and edge cases, not only the happy path
- Every new gate or scoring rule requires a fixture in `tests/fixtures/` and a corresponding test in `tests/unit/`

### Python smoke and regression tests

- Runner: `npm test` runs the unified runner (or `npm run test:python` to run only python tests)
- Every bug fix must add a regression fixture linked to its `BUG-*` ID
- Collection quality changes require offline gate fixtures per `SDD_PROCESS.md` (`REG-08+`)

### Component done criteria

A component is complete when:
- [ ] All unit and regression tests pass (`npm test`)
- [ ] Implementation notes updated in the relevant `docs/spec/08-implementation/IMP-CR-*` file
- [ ] No unresolved `any`-typed code in TypeScript

---

## CHANGELOG format

All significant changes are appended to `PRODUCT_CAPABILITIES_AND_RELEASE_NOTES.md` before or immediately after a push to GitHub.

Use this format:

```
## [Version] — [Date]
[DRAFT] [Plain-language summary of what this version is and what changed.
        Written for a non-technical reader. Human reviews and finalizes before commit.]

### New
- [Feature or component]: what the user can now do

### Fixed
- [BUG-ID]: what was broken and what changed

### Changed
- [Component or CR-ID]: what changed and why

### Developer
- [CR-ID]: internal change, not user-visible
```

Mark new entries `[DRAFT]` until reviewed. Remove the `[DRAFT]` tag only after human sign-off.

---

## Output format for agent work

When finished with any task, report:

- Requirements touched (`FR-*`, `NFR-*`, `AC-*`, etc.)
- Specs updated (which files in `docs/spec/`)
- Code files changed
- Tests run and result
- Traceability matrix updated: yes / no / not applicable
- Open questions or risks

---

## Data Privacy & Public Repo Rule

All agents MUST respect the public/private boundary of this repository. 
- **DO NOT** track or commit real personal career documents (data/*.md, data/*.json).
- If you need to scaffold examples for new features, generate .example.md or .example.json templates using generic text and push those.
- Never override or remove the wildcard ignores in .gitignore covering the data/ directory.
