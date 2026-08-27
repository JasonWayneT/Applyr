# CR-100 - Stage 0 Model-Independent Hard Gates

**Status:** Implemented, 2026-08-25

## Problem

Stage 0 evaluated deterministic preference exclusions but continued into
model-dependent JD extraction and evidence scoring. A missing local model could
therefore prevent an already-obvious exclusion from being recorded.

## Decision

After the deterministic preferences/exclusion gate rejects a role, Stage 0
returns `SKIP` immediately. It does not call the extraction model, evidence
classifier, or any fallback model. The output is marked
`extraction_source: "not_run"` so this cannot be mistaken for a model-backed
fit judgment.

This hardens availability without introducing a weaker fit heuristic. Roles
that are not deterministically excluded still require the normal evidence
model and remain fail-closed when it is unavailable.
