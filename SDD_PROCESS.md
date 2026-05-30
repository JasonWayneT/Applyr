# SDD Process Enforcement Rule

**Runtime workflow (operators + pipeline):** [docs/ACTIVE_WORKFLOW.md](docs/ACTIVE_WORKFLOW.md)  
**Agent entry:** [AGENTS.md](AGENTS.md)

**STRICT REQUIREMENT:** No agent or developer may modify code in this repository without first following the full Spec-Driven Development (SDD) process. **Changing code alone is a failure.**

## The "Whole Process" Workflow

Every change, regardless of size, must propagate through all three layers of the project:

### 1. Layer 1: Business Documentation (The "Why")
- **Action:** Update the relevant PRD, Design System (`DESIGN.md`), or Rule file (`.agent/rules/`).
- **Goal:** Ensure the business logic and design intent remain the source of truth.

### 2. Layer 2: Specifications (The "What")
- **Action:** 
    1. Create/Update a Change Request (`CR-*`) in `docs/spec/05-change-requests/`.
    2. Update the Requirements Registry (`02-requirements-registry.md`).
    3. Update the relevant Feature Spec (`docs/spec/03-feature-specs/`).
    4. Update the Traceability Matrix (`docs/spec/06-traceability/`).
- **Goal:** Maintain a documented, traceable chain of requirements and acceptance criteria.

### 3. Layer 3: Code Implementation (The "How")
- **Action:** Implement the changes in `scripts/`, `server/`, or `src/`.
- **Constraint:** Include `# Implements <ID>` comments in the code.
- **Goal:** Ensure the implementation matches the spec exactly.

---

## Why this is mandatory
- **Traceability:** We must be able to trace every line of code back to a business requirement.
- **Context Preservation:** Documentation is the only way for future AI agents to understand the "Why" behind the "How."
- **Auditability:** Every claim and metric must be grounded in verified source data.

**IF YOU ONLY CHANGE THE CODE, YOU HAVE FAILED THE MISSION.**

---

## Collection quality changes (scout → evaluate funnel)

When improving job opportunity collection (not drafting/research):

1. **Document first:** `CR-027+` in `docs/spec/05-change-requests/`, registry IDs `FR-170+`, update `FEAT-001`, `FEAT-002`, `FEAT-009`, traceability, and `IMP-CR-*` under `docs/spec/08-implementation/`.
2. **Layer 1:** Update `.agent/rules/job_fit_engine.md` when LLM rubric and deterministic gates must stay aligned.
3. **Gate design rules:**
   - Prefer **deterministic** gates before LLM fit; share logic in `scripts/*_gate.py` when possible.
   - TypeScript scout gates (`scout_local.ts`) must mirror Python semantics or call Python; document any intentional subset scope (e.g. industry: company/title only at scout).
   - New prefs fields must be **preserved** in `materializeJobSearchPrefs()` (ADR-005), not only in example JSON.
   - Aggressive gates (`ANCHOR_GATE_ENABLED`, `must_have_keywords`) ship **off by default** with env flags.
4. **Verify:** Extend `scripts/test_smoke_regression.py` with offline gate fixtures (REG-08+); manual sync log check for `[REJECT] industry_blocked:` / `[ZERO-TOKEN REJECT]`.
5. **Release:** Append Firefox-style notes to `PRODUCT_CAPABILITIES_AND_RELEASE_NOTES.md` before push.
