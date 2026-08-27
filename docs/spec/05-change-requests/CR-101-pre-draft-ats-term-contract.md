# CR-101: Pre-draft ATS term contract

## Problem

Stage 1 previously reported JD-term gaps as warnings after authoring. A draft
could therefore omit truthful, important ATS language even when supporting
evidence existed. Sony exposed three examples: Cross-Functional Planning,
Engagement, and Support.

## Decision

Generate an `ats_term_contract` inside `authoring_packet.json`. A term enters the
contract only when:

1. it comes from verified candidate vocabulary,
2. it appears in the target JD, and
3. the packet contains a supporting claim, either through the evidence map or a
   deterministic JD skill-anchor excerpt.

The authoring prompt requires every contract term in `Resume.md`.
`author_from_packet.py --verify-only` fails when a term is absent or when no
supporting packet claim is cited in resume provenance.

## Safety boundaries

- This does not change Stage 0 fit decisions.
- This does not add unverified vocabulary or claims.
- This does not automatically write resume content.
- Legacy packets without the contract remain readable and report a skip until
  rebuilt.
- Stage 2 ATS review remains a backstop for extractor and authoring edge cases.

## Validation

- Unit coverage verifies packet scoping, skill-anchor recovery, inflected-word
  matching, missing-term failure, and supporting-provenance failure.
- Sony's rebuilt packet includes Cross-Functional Planning, Engagement, and
  Support with supporting claim IDs.
- Sony's pre-change draft fails Stage 1 for all three missing contract terms.
