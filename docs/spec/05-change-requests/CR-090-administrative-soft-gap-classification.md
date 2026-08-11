# CR-090: Administrative Facts Wrongly Classified as Bridgeable Soft Gaps

## Metadata
- **Status**: Implemented (2026-08-10)
- **Date**: 2026-08-10
- **Source**: Real regression found while verifying CR-087 (item-overlap precision) —
  `data/submissions/thermo_fisher_scientific` flipped `ready`→`incomplete` on a fresh
  rebuild with no content change
- **Related**: CR-087 (the scorer fix that exposed this — see Problem), CR-085 (fail-closed
  Rule 2/7 this interacts with), CR-089 (the other cause of the same symptom)

## Problem
`_classify_one_item()`'s fallback ("no hard tool, no anchor → soft gap, domain/methodology
bridgeable") treats *any* required/preferred line with no matching claim tag as a skill gap
needing a transferable-skill bridge. This is correct for real experience gaps, but wrong
for a category of lines that aren't claim-shaped at all: binary eligibility facts (degree
requirement, years-of-experience) that are either genuinely satisfied by Jason's real
profile or already correctly evaluated by a separate, dedicated gate.

This was previously masked: before CR-087, a weak/generic lexical match would often attach
*some* claim_id to these lines, vacuously satisfying the fail-closed gate. CR-087 correctly
stopped doing that (no claim in `master_claims.json` is about "having a bachelor's
degree"), which surfaced the real, pre-existing classification bug — the line was never a
real skill gap to begin with.

Measured across 54 real submissions: 106 non-domain SOFT gaps (before fix), with
Bachelor's-degree and years-of-experience lines the two largest clean-cut categories
(~20+ combined instances — e.g. "Bachelor's degree required" appeared verbatim or near-
verbatim in 10 of 54 companies). Years-of-experience lines are **already** independently
parsed and gated by `seniority_gate.check_years_gate()` against
`candidate_preferences.json`'s real threshold — flagging the same line again here isn't
just redundant, it's wrong: it either duplicates a correct signal or conflicts with it.

A second-order bug surfaced during verification: removing the soft-gap classification for
a *required* item (as opposed to preferred) doesn't fully fix it — with no `claim_ids` and
no `bridge`, the item now trips fail-closed Rule 2 (unmapped required item) instead of
Rule 7 (unbridged soft gap). Same root cause, different rule.

## Decision
1. `build_stage0_fit_gate.py`: new `_is_administratively_satisfied()` check, inserted
   before the generic soft-gap fallback in `_classify_one_item()`. Deliberately narrow —
   only years-of-experience lead-ins and Bachelor's-degree-satisfied lines. Does **not**
   cover citizenship/work-authorization/security-clearance/travel/supervisory-
   responsibility statements — those are left for a separate, more careful pass; some are
   legally sensitive and shouldn't be silently resolved without confirming Jason's actual
   status.
2. The Bachelor's-degree check explicitly does not exempt lines that mandate a *higher*
   degree as required (Master's/MBA/PhD/JD/MD "required") — those remain real gaps. A
   higher degree merely *preferred* alongside a required Bachelor's is not a gap (the
   Bachelor's already satisfies the line).
3. `build_authoring_packet.py`: `build_evidence_map`'s Pass 2 reuses the same
   `_is_administratively_satisfied()` check — when a `required` row ends up with no
   `claim_ids` and no `bridge`, and the item matches the pattern, auto-supply an explicit
   bridge note ("Administratively satisfied ... not a skill claim, no evidence required")
   so Rule 2 doesn't hard-block on a line that was never a real gap.

## Acceptance Criteria
| ID | Criterion |
|----|-----------|
| AC1 | `data/submissions/thermo_fisher_scientific` returns to `packet_status: ready` on a fresh Stage 0 rebuild, with no content change to the claim catalog |
| AC2 | Full test suite passes unmodified |
| AC3 | Re-measuring the 54-company soft-gap sweep shows Bachelor's-degree and years-of-experience lines no longer appear in the flagged list |
| AC4 | Genuine domain/skill soft gaps (e.g. "Experience with Manhattan Associates WMS", "healthcare technology experience") are unaffected — still correctly flagged, still require a real bridge |

## Out of Scope
- Citizenship / work-authorization / security-clearance / travel / supervisory-
  responsibility statements — explicitly deferred, not silently resolved.
- Any change to `seniority_gate.py`'s own years-of-experience logic — this CR only stops
  the generic classifier from duplicating/conflicting with it, doesn't touch it.
- Genuine soft gaps requiring a real transferable-skill bridge — those are the fail-closed
  gate working as designed.
