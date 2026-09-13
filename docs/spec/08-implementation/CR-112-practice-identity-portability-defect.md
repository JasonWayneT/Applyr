---
status: design_only_not_implemented
created: 2026-09-12
from: Cursor (Grok 4.6)
candidate: cr112-integrated-validation-candidate
related: CR-112, SESSION-HANDOFF-2026-09-12-cr112-product-proof-camunda.md
scope: privacy-safe identity for practice runs and clean worktrees
do_not_bundle: completion-floor story (FR-318)
---

# CR-112 practice identity portability

Bounded design. Do not implement in the same commit as the
CONVERT-READY floor gate. Do not copy production SQLite. Do not put
PII in tracked fixtures, logs, commits, prompts, or reports.

## Proven defect (Camunda product-proof)

Claude had to insert a real identity row into this worktree's
`data/jobagent.sqlite` because `profiles.identity` was missing.
Without that row, `scripts/utils.py` `load_identity_profile()` fills
`_DEFAULT_IDENTITY` (John Doe / `555-019-9238` / `email@example.com`).
`quality_checker.check_and_repair_cover_letter` H-001 can then inject
that placeholder header above a real one.

That local DB write unblocked the run. It is not a portable fix for
the next clean worktree or harness.

Canonical header substitution already exists:
`scripts/apply_resume_header.py` reads gitignored
`data/workExperience.md` Section 1.0. Packet and digest have no
contact fields by design.

## Canonical sources (keep them separate)

| Mode | Source | When |
|---|---|---|
| Real local (production or practice against a real JD) | `workExperience.md` §1.0 via `apply_resume_header.py` | Required before authoring a document that will carry a name/contact header |
| SQLite `profiles.identity` | Cache / UI settings projection only | Must not be the only source; must not be copied from production DB into a worktree |
| Synthetic fixture | Explicit `synthetic` / test-only identity, unmistakably fake | Unit tests and sanitized eval fixtures only |

Never emit plausible placeholder identity into a real or practice
document without that synthetic mode. John Doe in `_DEFAULT_IDENTITY`
is fixture-shaped, but it is currently a silent fallback, not a mode.

## Proposed story (not this session)

1. Fail closed **before authoring** when required identity is
   unavailable: no WE §1.0 parse, and no `profiles.identity` row,
   unless `--synthetic-identity` (or equivalent env) is set.
2. Remove the silent `_DEFAULT_IDENTITY` fill from the real/practice
   document path. Tests that need John Doe opt into synthetic mode.
3. Isolated worktrees receive identity by reading gitignored
   `workExperience.md` (copy or worktree-local file), never by cloning
   production `jobagent.sqlite`.
4. Log only `identity_source=we|sqlite|synthetic|missing`. Never log
   name, email, phone, or LinkedIn.
5. Security review required before touching DB/PII code.

## Acceptance sketch

- Clean worktree with WE present, sqlite identity absent: header
  lands from WE, no placeholder, no production DB read.
- Clean worktree with neither WE nor identity: authoring/header step
  raises a clear error; no John Doe document.
- `--synthetic-identity` writes only the documented fake fixture
  identity, and the workflow_state records `identity_mode=synthetic`.
- Tracked tests never contain Jason's real contact fields.

## Out of scope

CONVERT-READY floors. Camunda re-author. Production sqlite. Copying
PII into this design doc.
