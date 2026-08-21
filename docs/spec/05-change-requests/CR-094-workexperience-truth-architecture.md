# CR-094: WorkExperience Truth Architecture (WE-primary packet)

## Metadata
- **Status**: Implemented (2026-08-20)
- **Date**: 2026-08-20
- **Source**: Architecture session from `docs/spec/08-implementation/PROMPT-2026-08-20-workexperience-truth-architecture.md`; Jason approved option A
- **Related**: CR-074 (packet), CR-085 (claim `text` excerpts — reversed here), CR-088 (claims as index)
- **Requirement IDs**: CR-094 (this change); grounding non-negotiables in `AGENTS.md`

## Problem

Stage 0 scores retrieval-scoped chunks of `workExperience.md`. Stage 1 authors from `master_claims.json` `text` (CR-085). Attribution / DO NOT CLAIM live in WE and on some claim records, but the packet builder never sends them. `audit_claims_coverage.py` treats every `[ACC-N]` bracket as an accomplishment, including Attribution and DO NOT CLAIM ids (~66 `we_unclaimed`). AGENTS.md still says packet excerpts are WE slices and claim `text` is write-only — runtime disagrees.

Jason's mental model ("claims are the bullets, WE is a reference file") does not match the anti-hallucination contract. WE is the verified corpus. Catalog `text` is a second biography the cloud author actually sees.

## Decision (option A)

1. **WE is source of truth and runtime evidence.** Claims are an index: ids, tags, pointers, attribution, prohibited. Not draftable `text` / `cover_story`.
2. **Packet excerpts come from WE** (`aiProjects.md` for ACC-401). Never prefer claim `text`.
3. **Hedges travel as fields.** Packet `claim_constraints` plus a hedge header on each excerpt. CONTRIBUTED / DO NOT CLAIM are not hoped-for substrings of a 500-char card.
4. **Lens distinctiveness without a second biography.** First lens of a `project_id` carries the WE span. Later lenses get a pointer + lens instruction. If two lenses need different facts, split the WE story.
5. **ACC classes.** Story ids are indexable. Attribution / DO NOT CLAIM ids are metadata on the preceding story, not accomplishments. ACC-119 stays tools catalog. ACC-401 stays side corpus. `ACC-114-COST` stays disabled.
6. **Context pack** strips WE §1.0 / 1.0a (contact / references) so a cloud-bound pack cannot ship PII. Stage 1 still must not load the pack.
7. **When Stage 0 and Stage 1 disagree, WE wins.**

Out of scope: Stage 0 floor recalibration, new JD batch, bulk-writing claim `text`, committing PII, LangExtract, full structured rewrite of WE (option C).

## Acceptance Criteria

| ID | Criterion |
|----|-----------|
| AC1 | `_excerpt_for_claim` returns a WE (or aiProjects) span even when `rec["text"]` is present |
| AC2 | Two lenses of one `project_id` are not byte-identical full WE dumps; the second is a lens pointer |
| AC3 | Assembled packet includes `claim_constraints` with attribution / prohibited when WE or the catalog has them |
| AC4 | `audit_claims_coverage` does not emit `we_unclaimed` for Attribution or DO NOT CLAIM ACC ids |
| AC5 | Story-class WE ACCs without a claim `project_id` still emit `we_unclaimed` |
| AC6 | Provenance valid-id set does not treat Attribution / DO NOT CLAIM ACC tokens as citable accomplishments |
| AC7 | `generate_context_pack` omits WE headings matching contact information / professional references |
| AC8 | AGENTS.md, authoring rule digest, generate-submission SKILL, and packet RULES describe WE-primary excerpts (no "text is what the author sees") |

## Files

- `scripts/we_acc_index.py` — classify WE bracket ACCs; extract hedges onto the preceding story
- `scripts/build_authoring_packet.py` — WE excerpts, constraints, stop merging `text` for authoring
- `scripts/audit_claims_coverage.py`, `scripts/claim_provenance.py`, `scripts/generate_context_pack.py`
- `scripts/generate_authoring_rule_digest.py`, `scripts/author_from_packet.py` preamble
- `AGENTS.md`, `.claude/skills/generate-submission/SKILL.md`, `data/CLAIMS_STANDARD.md`
- `scripts/contracts/authoring_packet_schema.json`, `authoring_packet_RULES.md`
