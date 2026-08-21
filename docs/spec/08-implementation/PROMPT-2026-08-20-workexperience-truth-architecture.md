# Prompt — Define how Applyr uses workExperience

Paste this as the first message in a **new** session. Do not start by writing claims or
editing `workExperience.md`. This session defines the contract, maps current usage,
researches alternatives, and recommends a design. Jason approves before any rewrite.

---

You are an architecture session for Applyr, Jason's local job-search system. Follow
`AGENTS.md`. Do not draft a resume or cover letter in this session.

## The job

**Define how the system should use `data/workExperience.md`.**

That is the deliverable, not a side note. Every later recommendation (keep claims, burn
claims, rewrite retrieval, change the packet) exists only to implement that contract.

Jason's mental model was:

> Claims are the resume bullets. `workExperience.md` is just a reference file.

The repo and the code do not agree with each other on this. Stage 0, Stage 1, linters,
and humans currently use WE in different ways. He needs one written contract he can
understand: what WE is, who reads it, what they may do with it, and what they must not
do — so nothing untrue gets claimed and every employer-facing sentence is grounded in
verified truth.

A full rewrite is on the table. Do not protect the current split out of habit.

## Non-negotiables

1. **Grounding.** Employer-facing text (resume, cover letter, outreach that cites work)
   must trace to verified career facts. No invented metrics, tools, titles, teams, or
   causation. Attribution hedges (OWNED / CONTRIBUTED / INFLUENCED) and DO NOT CLAIM
   lists must remain enforceable.
2. **PII.** `workExperience.md` is gitignored. Section 1.0 / 1.0a is real contact and
   references. Do not paste that into a cloud model, a design doc, or a commit. Do not
   commit `workExperience.md` or `jobagent.sqlite`.
3. **WE today is the verified corpus.** Metrics, stories, tools, dates, VOC translations,
   and prohibited claims live there now. You may recommend keeping WE as the runtime
   source, compiling it from structured records, or using it only as a human-edited
   canonical that other artifacts are generated from. You may not invent a second
   biography that can drift from it.
4. **No implementation in this session** unless Jason explicitly says to start coding
   after he accepts the contract. Output is a recommendation he can approve.
5. **Say "can't," don't fake "did."** If you cannot run a path, say so.

Do **not** treat "WE is only a human reference" or "claims are the bullets" as given.
Those are the hypotheses under test.

## What to do, in order

### 1. Write the usage contract first (then prove it against the code)

Produce a short **WorkExperience usage contract**. This is the thing Jason should be
able to reread in six months. Fill every row. If a surface should not read WE at all,
say that explicitly and say what it reads instead.

For each surface, define:

- **Role of WE:** source of truth, retrieval corpus, lint oracle, human notebook, unused
- **What the model/human is allowed to see:** full file, chunks, excerpts, ids only, nothing
- **What they may do with it:** score fit, select evidence, write fresh prose, copy, never
  copy
- **What they must not do:** paste bullets, round CONTRIBUTED into OWNED, use DO NOT CLAIM
  as a story, invent from tags
- **How a new true story in WE becomes usable** on the next resume (or why an extra catalog
  step is required)
- **How a prohibited or hedged line is blocked**

Surfaces you must cover (add any others you find in code):

- Human editing WE
- Stage 0 fit scoring
- Claim / tag selection (whatever `master_claims.json` becomes)
- Authoring packet construction
- Cloud / Stage 1 author (closed-world packet + digest)
- Optional full-pack / process sessions (`agent_context_pack.md`)
- Mechanical verify: linter, provenance, coverage, tools catalog
- Future surfaces if you recommend them (structured store, generated index, etc.)

Also answer, in the contract, not in a later appendix:

- Is WE the runtime evidence the author sees, or only the human canonical?
- Are claims an **index into WE**, a **second narrative**, both, or neither?
- When Stage 0 and Stage 1 disagree about what evidence exists, which file wins, and why?
- What is the one-sentence rule for "where does a resume bullet come from?"

Best practices from step 3 should shape this contract. Draft it after you have mapped
current usage and done the research — but present the contract **before** the option
catalog. The architecture exists to serve the contract, not the other way around.

### 2. Map what the system does *now* (code, not folklore)

Read the code. Treat `AGENTS.md` and CR docs as hypotheses. Confirm or correct them.
This map is the gap analysis against the contract, not the contract itself.

Minimum map (produce a diagram or a tight table):

| Surface | What it reads | What it ignores | What the author/model actually sees | How that differs from the contract |
|---|---|---|---|---|
| Stage 0 fit (`scripts/evidence_scale.py`) | | | | |
| Authoring packet (`scripts/build_authoring_packet.py`) | | | | |
| Cloud author (packet + `data/authoring_rule_digest.md`) | | | | |
| Mechanical verify (`scripts/submission_linter.py`, `claim_provenance.py`, coverage) | | | | |

Facts you must verify in source (do not take this prompt as the last word):

- Stage 0 scores each JD requirement against **retrieval-scoped chunks of
  `workExperience.md`** (`evidence_scale.build_evidence_context`). It does not score
  against `master_claims.json` `text`.
- Stage 1 is **closed-world**: the author is told to use only packet `claim_ids` and
  excerpts (`authoring_rule_digest.md` §1). `AGENTS.md` says do not load
  `agent_context_pack.md` into that author session.
- Packet excerpts currently **prefer `master_claims.json`'s `text` field** over a slice of
  `workExperience.md` (`_excerpt_for_claim` in `build_authoring_packet.py`, CR-085). If
  `text` exists, WE is not what the author sees for that lens. Fallback is a regex slice
  on `[ACC-NNN]` in WE, then a synthetic excerpt from tags.
- `AGENTS.md` still says claim `text` and `cover_story` are **legacy write-only** and must
  not be pasted into documents. The packet nevertheless injects `text` as "grounding
  evidence, not draftable prose." Document whether that is a bug, a hidden design, or
  both.
- Claims are selected by **tags** vs the JD (`master_claims_tags_only.json`). A WE story
  with no claim row (or no distinctive tags) may never enter the packet, so the author
  cannot use it even though it is true.
- WE uses `[ACC-…]` for three different things: (a) real stories, (b) Attribution lines,
  (c) DO NOT CLAIM lines. `scripts/audit_claims_coverage.py` treats every bracket id as
  something that needs a `project_id` in `master_claims.json`. That is why the live audit
  reports ~66 `we_unclaimed` errors. Do not "fix" that by turning warnings into resume
  cards. The contract should say which ACC classes are indexable and which are not.
- `ACC-114-COST` is quarantined. The PIC / Canadian-ingest story in WE is real;
  sole-causation of the ~$800K figure is not. The contract must keep that hedge.
- Linters still grep WE and `skills_catalog.json` for tools, metrics, VOC, forbidden
  claims.

Also skim: `data/CLAIMS_STANDARD.md`, `scripts/claim_provenance.py`,
`scripts/check_ground_truth_coverage.py`, `.claude/skills/generate-submission/SKILL.md`
(Stage 1 vs packet), CR-074 / CR-085 notes in `docs/spec/08-implementation/`.

### 3. External research (required)

Do not write the contract from repo taste alone. Look up current practice on:

- Grounded / closed-world generation: one source-of-truth document vs a derived index
- RAG failure modes when the **index** (claims `text`) can drift from the **source** (WE)
- Resume/ATS systems that retrieve evidence then draft (not "paste the catalog")
- Knowledge-graph or claim-catalog patterns for biography: when a lens/index is worth
  it, when it becomes a second biography
- How attribution and prohibited-claims are usually encoded so models cannot "round up"
  CONTRIBUTED into OWNED
- How production systems decide **which layer** the generator may see (full source,
  retrieved spans, structured facts only)

Cite sources. If a finding conflicts with Applyr's anti-hallucination rules, say so and
prefer the stricter rule. Use the research to justify the contract's answers to "what
does the author see" and "what is claims for."

### 4. Name the failure modes

At least these, plus any you find. Tie each one to a broken or missing line in the
contract:

- Operator mental model: "claims are the bullets, WE is reference"
- Dual corpus: packet shows claim `text`, WE has the hedges and DO NOT CLAIM
- Missing index: true WE stories never selected (ACC-122 storage monitoring, ACC-169 S3,
  ACC-176 translation, etc.)
- Over-index: Attribution / DO NOT CLAIM ids treated as accomplishments
- Lens collapse vs lens `text`: CR-085 used claim `text` so ACC-101-PM and ACC-101-TECH
  are not the same WE slice — that problem is real; using `text` as a second biography
  may have been the wrong fix
- Stage 0 reads WE, Stage 1 reads claims: fit can "see" Pendo in WE while authoring
  never gets that story if tags/selection miss it, or the reverse

### 5. Recommend an architecture that implements the contract (rewrite allowed)

Propose 2–3 options with tradeoffs, then recommend one. Each option must say how it
implements the usage contract from step 1. Options should include at least:

- **A. WE-primary.** Packet excerpts always come from WE (and `aiProjects.md` for
  ACC-401). Claims become tags + pointers + attribution/prohibited only. Delete or stop
  generating author-facing `text` / `cover_story`.
- **B. Keep dual store, make it honest.** Claims `text` stays, but it is generated from
  WE, mechanically checked against WE, and never edited by hand. Drift fails CI.
- **C. Full rewrite.** One structured source (schema on top of WE, or WE compiled from
  structured records). Authors and Stage 0 share the same retrieval. Catalog cards are
  not a parallel narrative.

For the recommendation, specify:

- The contract restated in one paragraph
- What the cloud author is allowed to see
- How a new WE story becomes usable on the next resume without a forgotten catalog step
- How OWNED / CONTRIBUTED / DO NOT CLAIM are enforced
- What happens to `master_claims.json`, `master_claims_tags_only.json`,
  `authoring_packet.json`, `claim_provenance.py`
- Migration: what to keep, what to burn, what to generate once
- Test plan: a known true story must be selectable; a DO NOT CLAIM must never appear; a
  CONTRIBUTED metric must not become sole causation

### 6. Stop for Jason

End with: the usage contract (final), what you decided, what is still open, the next
implementation step. Do not start the rewrite in this session.

## Explicitly out of scope unless Jason expands it

- Recalibrating Stage 0 floors (40/65)
- Drafting submissions or running the new JD batch
- Bulk-writing 60+ claim `text` blobs to silence `we_unclaimed`
- Committing PII files
- LangExtract / swapping Stage 0 models

## Session identity

In any session log, self-identify as `Cursor ([model])` or the harness you are actually
running. Read `AGENTS.md` before editing anything. This work is engineering, not
`generate-submission`.
