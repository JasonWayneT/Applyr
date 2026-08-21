# IMP-CR-094 — WorkExperience truth architecture

**CR:** [CR-094-workexperience-truth-architecture.md](../05-change-requests/CR-094-workexperience-truth-architecture.md)
**Status:** Implemented 2026-08-20 (option A)

## Stories

- [x] Packet excerpts from WE / aiProjects, never claim `text`
- [x] `claim_constraints` (attribution + prohibited) on the packet
- [x] Second lens of a project is a pointer, not a duplicate WE dump
- [x] `audit_claims_coverage` story-class only; attrib/DNC are fields
- [x] Provenance does not treat attrib/DNC ACC tokens as Fact IDs
- [x] Context pack strips contact / references headings
- [x] AGENTS.md, digest, generate-submission SKILL, packet RULES match the contract

## Not in this CR

- Stage 0 floor recalibration
- Indexing every remaining unlensed story-class ACC into `master_claims.json`
- Rewriting WE to remove attrib/DNC ACC numbers (parser treats them as fields already)
- Option C structured rewrite of WE

**Follow-on (started 2026-08-20, not finished):** see
[SESSION-HANDOFF-2026-08-20-we-truth-and-story-index.md](./SESSION-HANDOFF-2026-08-20-we-truth-and-story-index.md).
Classifier substory/nonclaimable + Docker allowlist landed partially; catalog rows for
the remaining `we_unclaimed` stories were not added.
