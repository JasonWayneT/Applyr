# Change Requests Index

**Active runtime:** [docs/ACTIVE_WORKFLOW.md](../../ACTIVE_WORKFLOW.md)

## How to use

| Need | Read |
|------|------|
| Current scout/evaluate/draft behavior | `ACTIVE_WORKFLOW.md`, `FEAT-001`–`004`, `.agent/rules/pipeline_env.md` |
| Implement a new feature | New `CR-*` + registry + FEAT + traceability |
| Historical context | Closed CR below (audit only) |

## Active / recent CRs (maintainers)

| CR | Topic | Status |
|----|-------|--------|
| CR-ARCH-000–006 | Server/process refactor | Implemented |
| CR-027 | Industry blocklist gate | Implemented |
| CR-028 | Keywords / anchors | Implemented |
| CR-031 | Draft quality gates | Implemented |
| CR-026 | Sync evaluate visibility | Implemented |
| CR-035 | Fit scoring hardening | Implemented |
| CR-036 | Solo PM trap + years policy lock | Implemented |
| CR-037 | Required domain experience gate | Implemented |
| CR-038 | B2C role openness | Implemented |
| CR-039 | Transferable skills over domain gate | Implemented |
| CR-040 | Theme primary claims (resume/cover numeric alignment) | Implemented |
| CR-041 | ATS watchlist — no example.json at runtime | Implemented |
| CR-042 | Resume quality enforcement (strict gate + retry + fleet proof) | Implemented |
| CR-043 | Deterministic cover letter voice | Implemented |
| CR-044–052 | *(table not maintained for this range — see individual `CR-0XX-*.md` files in this directory)* | `[VERIFY]` |
| CR-053 | Fit rubric overhaul — evidence-tiered scoring, replaces holistic LLM score | In progress — see [docs/spec/08-implementation/CR-053-fit-rubric-overhaul-epics.md](../08-implementation/CR-053-fit-rubric-overhaul-epics.md) |
| CR-054 | Pipeline integrity & failure transparency (silent-success-on-failed-draft bug) | In progress — same doc as CR-053 |
| CR-055 | Collection gate accuracy (years-gate regex bug, title-blocklist false positives) | In progress — same doc as CR-053 |

**Note:** CR-053/054/055 supersede the scoring policy set by CR-039 (transferable-skills-over-domain
gate) — domain fit is being reinstated as a bounded scored signal rather than ignored. If CR-039's
text and the CR-053 doc disagree, CR-053 wins until this table is updated to mark CR-039 superseded.

## Archive (implemented — do not treat as daily instructions)

CR-001 through CR-025, CR-021 (detail), CR-024, etc. remain for audit traceability. If code and an old CR disagree, **code + ACTIVE_WORKFLOW + registry** win.
