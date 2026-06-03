# CR-040 — Theme primary claims (resume + cover alignment)

## Problem
Cover engine v1 can cite catalog metrics (e.g. 90%, ~300 security backlog) that were not composed onto the resume. Pre-verify used full `claim_corpus` while `verify_document_bundle` used `bullet_corpus` only, causing late numeric audit failures.

## Change
- `scripts/theme_primaries.py` — when JD/profile activates a theme (`security`, `platform`, `data`, …), prepend the best matching ACC claim to Stage 2 selection; quota padding prefers the same IDs.
- `draft_compiler.py` — cover audit corpus = resume bullets + catalog truths; verify bundle uses the same union when cover engine v1 is on.
- `jd_tailoring.pick_cover_bullets` / `cover_claim_picker` — security/compliance scoring bonus.

## Requirements
- `FR-193` (theme primary claims + corpus alignment)
- `FR-091` (JD-tailored claim selection)
- `FR-101` (cover proof picker)

## Acceptance
1. JD containing `security` injects `ACC-103-ROADMAP` (or fallback SEC/PM) into selected claims when present in catalog.
2. Cover numeric verify passes when cover cites 90%/300 and matching claim is on resume or in catalog union corpus.
3. `python scripts/smoke_draft_compiler.py` includes `test_theme_primaries_inject_security_claim`.
