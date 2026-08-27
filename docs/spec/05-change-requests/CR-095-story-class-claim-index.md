# CR-095: Complete the WorkExperience Story-Class Claim Index

## Status

Implemented 2026-08-24

## Purpose

Complete the CR-094 follow-on that makes every indexable `story`-class ACC in
`data/workExperience.md` discoverable through `data/master_claims.json`.

The claim catalog remains an index only. New rows carry identifiers, lens
metadata, retrieval tags, literal verified metrics where applicable, and
attribution/prohibited-claim fields. They must not add a second author-facing
biography. Runtime authoring continues to retrieve evidence from
`workExperience.md`.

## Acceptance criteria

- [ ] `audit_claims_coverage.py --strict` reports zero errors.
- [ ] Every new row's ACC prefix matches its `project_id`.
- [ ] New rows reference only story-class ACCs, except the existing Docker
      personal-use boundary is represented without making professional Docker
      use citable.
- [ ] New rows contain no hand-authored `text` or `cover_story` used as
      authoring evidence.
- [ ] `master_claims_tags_only.json` is regenerated from the canonical catalog.
- [ ] Existing disabled/quarantined claims remain disabled.
- [ ] Packet, provenance, and classifier regression tests remain passing.

## Scope

In scope: the remaining story-class index rows, the derived tags-only sidecar,
and the packet budget regression test isolation.

Out of scope: changing the WorkExperience source, bulk rewriting legacy claim
text, recalibrating Stage 0, or authoring new submissions.
