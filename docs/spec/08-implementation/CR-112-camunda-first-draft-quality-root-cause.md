---
status: investigation_only_no_implementation
created: 2026-09-13
from: Claude (product-proof run, Camunda correction cycle)
candidate: cr112-integrated-validation-candidate @ 089efec (worktree, local commit)
related: CR-112-stage0-extraction-fallback-defect.md, CR-112-ats-term-contract-eligibility-defect.md
scope_note: |
  Written under an explicit Claude usage-conservation directive (2026-09-12). This is
  investigation and planning ONLY, per Jason's explicit instruction — no code here.
  Implementation of any of these belongs to a later, separately-bounded engineering
  session. The untouched first-draft baseline (Resume 64/100, Cover Letter 57/100,
  severity SECTION_REWRITE, classification FIRST_DRAFT_WEAK) is NOT rescored or
  reopened by this report.
---

# Camunda first-draft quality — root-cause findings (investigation only)

Six concrete first-draft defects, traced to actual cause where the evidence supports it,
flagged as open when it doesn't. A reviewer's classification (one-off variance / known
defect / missing instruction / packet-information loss / missing mechanical guard /
missing example / qualitative-only) is given for each, with the reasoning, not asserted
by fiat.

## 1. Why the $22,100 metric was dropped from its own selected evidence

The Zero To Sixty bullet drafted was "Supported Salesforce-related workflows within
product responsibilities at Zero To Sixty" — no metric. But the packet's own
`excerpts["ACC-302-SALESFORCE"]` (which I personally pasted verbatim into the Stage 1
author's prompt) reads in full: *"ACC-302 Onboarding Workflow Optimization: Co-created
and optimized an internal onboarding automation tool that streamlined new customer data
mapping into Salesforce, reducing manual overhead and **saving $22,100 annually**."* The
figure was available to the author.

**This directly contradicts the Stage 1 author's own self-reported excuse** ("ACC-301-AUTO
and ACC-302-SALESFORCE... had zero narrative content in the packet — just employer + lens
name, no excerpt text") — that claim is factually wrong for ACC-302, checkable against the
packet I built the prompt from. Worth flagging precisely because an agent's own stated
reason for a gap should not be taken at face value without checking it against the actual
input it received; this session did check, and the excuse doesn't hold.

**Classification: one-off author variance, with a plausible missing-instruction
contributor.** Zero To Sixty is the lowest-priority employer (2-bullet budget, no
required/preferred JD item mapped to either of its two claims — both are "filler" bullets
used only because the 3-role rule requires the employer to appear at all). The prompt's
"EVIDENCE PRIORITY" line names six specific claims to foreground; ACC-302 isn't one of
them. A plausible mechanism: the model correctly deprioritized *how much space* to give
this bullet, but over-generalized that into *how much of the cited excerpt's own content*
to use, compressing away the one concrete number in it. The prompt never states "even a
filler-role bullet must still mine every concrete detail in its own cited excerpt" — that
specific instruction doesn't exist today in `authoring_rule_digest.md`.

## 2. Why an unbacked "AI Tools" claim appeared

The resume's Core Competencies row lists "AI Tools & Automation (Claude, Gemini)" — real,
truthful, backed by `ACC-401-AITOOLS` — but `claim_provenance.json`'s first draft cited
that claim only in `cover_letter_claims`, never in `resume_claims`. `ats_term_contract`'s
mechanical check (unchanged by either of this session's two fixes) correctly failed on
this.

**Classification: missing first-draft instruction (prompt schema ambiguity), not a
packet or drafting-behavior defect.** The prompt's `claim_provenance.json` schema
instruction says *"for every resume bullet and factual cover-letter sentence"* — Core
Competencies content isn't phrased as a "bullet," so a model reasonably doesn't infer it
needs its own provenance row. `ACC-401-AITOOLS` also has `"employer": ""` (unassigned to
any of the three canonical roles), so rule 3's "draft a claim only under its own
employer's section" leaves Core Competencies as the *only* place this claim can honestly
appear at all — meaning the schema gap isn't cosmetic, it's structurally guaranteed to
recur for any future personal/unassigned-employer claim used the same way. **Concrete,
low-risk fix for a later session:** state explicitly in the prompt schema that a Core
Competencies line counts as a "resume claim" needing its own `claim_provenance.json` row.

## 3. Why the cover letter opened by paraphrasing the JD

First-draft hook: *"Camunda is running its own operations on agentic AI while building
agentic capability into the product itself."* The JD (packet's own `jd_buckets.culture`
entry): *"transforming into an AI-first organisation, built on our own platform. We use
Agentic AI to automate, orchestrate intelligent processes..."* — same idea, adjacent
wording, not a 6+-word literal match (so `LW-011`'s mechanical detector, which keys off
verbatim shared word-sequences, would likely **not** have fired on this specific
paraphrase — not independently re-run in this session due to budget; flagged as unverified,
not asserted).

**Classification: qualitative judgment the author got wrong despite an explicit,
present instruction.** The digest's own Section 5 already states *"Do NOT paraphrase the
JD's own prose back to the reader as the opening hook"* verbatim — this was not a missing
rule. The author had the instruction and didn't fully follow it in the source-of-truth
sense the instruction intends (adjacent phrasing that still leans on the JD's own framing
rather than an independent observation). This is the kind of failure `LW-011`'s comment in
`submission_linter.py` already anticipates as a class ("naming the role/team is fine;
mirroring the JD's sentences signals nothing") but the mechanical detector's literal
verbatim-sequence threshold may be too narrow to catch a paraphrase this close. **Open
question for the next session, not resolved here:** should `LW-011` widen from literal
sequence-matching to a looser semantic-paraphrase signal, and if so, using what — that is
a design decision, not something to implement off one example.

## 4. Why resume and cover letter reused verbatim phrases (3 separate instances found)

All three (the Java-platform description, the Critical Save program description, the
PTO-capacity-model description) were near-identical sentences in both documents,
mechanically caught by `LW-009-PAIR` / `check_cross_document_repetition` once run — but
this check is **not summarized anywhere in `authoring_rule_digest.md`**, confirmed by
reading the full digest text pasted into the Stage 1 author's prompt: no line instructs
"do not restate a resume bullet's exact wording in the cover letter; use different
vocabulary for the same fact."

**Classification: missing first-draft instruction — the clearest, most mechanical, and
likely single highest-leverage fix candidate of this whole report.** The check already
exists and already has a clear, actionable message
(`"Resume owns the metric/outcome wording; the cover letter must retell the same story
with different vocabulary..."`) — that exact guidance just never reaches the author before
drafting. Low implementation risk: one new line in
`scripts/generate_authoring_rule_digest.py`'s output, no new detection logic needed.

## 5. Why three factual cover-letter sentences lacked provenance

`author_from_packet.py::_cover_factual_sentences` flags a sentence as needing a citation
when it contains first-person phrasing (`\bi\b`, excluding `"i would"`/`"i am
drawn/interested/applying/glad"`), a named employer, an "my experience/background/..."
phrase, or an anaphoric/attributed-outcome opener. All three flagged first-draft sentences
were connective/scene-setting prose ("For the past several years I have owned product
for...", "Requirements and prioritization are where I spend most of my time...",
"Distributed teams are also where I have spent most of my career.") that read, to the
detector, exactly like factual claims, because they use the same first-person
present/past-tense pattern real factual claims use.

**Classification: mixed — missing instruction, with a real detector-precision edge (not
a bug, a known trade-off).** The prompt tells the author every factual cover-letter
sentence needs a citation but never explains *what makes a sentence "factual" versus pure
connective framing* in the mechanical sense the checker actually applies. This is likely
unfixable by instruction alone in every case (natural cover-letter prose often opens a
paragraph with a first-person scene-setter) — the more robust fix is probably on the
*detector* side (exclude a sentence that contains no noun phrase overlapping the packet's
own vocabulary — i.e., a pure transition with zero extractable claim content), which is a
design decision for a future session, not something to design here from one example.

## 6. Why the author needed a section rewrite despite the lean, closed-world packet

Synthesis across all five findings above: the packet's closed-world design is doing
exactly the job it's built for — **zero truth violations, zero attribution violations,
zero extra-packet citations, all high-priority claims used** — the correction cycle never
had to fix a single fabrication or misattribution. Every defect found was in the
**drafting-craft layer**: metric utilization discipline, cross-document repetition,
provenance-schema completeness for non-bullet content, and hook originality. That layer
currently depends on (a) the digest's explicit rule list, which is incomplete relative to
the full mechanical check suite that later grades the draft, and (b) the model's own
general writing judgment, which is inconsistent under a real prompt's competing pressures
(fit every priority claim in, stay within 40-word bullets, stay on one page, avoid
forbidden phrases, avoid JD-paraphrase, avoid repetition — a lot of simultaneous
constraints for a single first pass). None of this reflects a packet-construction defect;
it reflects a digest-completeness gap plus ordinary first-draft variance under load.

## Mechanically detectable vs. qualitative-only (summary table)

| Finding | Mechanically detectable today? | Which check |
|---|---|---|
| 40-word bullet | Yes | `R-013`/`CW-003` |
| Unbacked AI Tools claim | Yes | `ats_term_contract` |
| 3 uncited cover-letter sentences | Yes | `sentence_provenance` |
| Cross-document verbatim repetition (x3) | Yes | `LW-009-PAIR` |
| Dropped $22,100 metric | Partial (heuristic) | `check_ground_truth_coverage.py` — WARN-tier, real false-positive rate, needs a human read per its own documented design |
| JD-paraphrase-adjacent hook | Uncertain, not re-verified this session | `LW-011` — may not fire on a non-verbatim paraphrase; open question |
| Whether ACC-121-SQLFOOTPRINT should have been used | No | Requires the same qualitative HM read this session already did (independent reviewer) |

## Recurrence against prior evidence

**Not checked this session, due to budget.** `data/authoring_defect_ledger.json` (CR-097's
cross-submission occurrence tracker) was not queried. The next session should check
whether any of findings 1-5 above already have occurrences logged there before deciding
whether a fix is a one-off or a recurring pattern worth promoting — do not add a new
mechanical rule from this single Camunda instance without that cross-check, per CR-097's
own stated design ("a repeated skeleton... is usually a symptom" — but repetition across
occurrences is what justifies a rule, not one instance).

## Reviewer classification (for the record, my own judgment above — a second reviewer should confirm before any of this is implemented)

| # | Finding | Classification |
|---|---|---|
| 1 | Dropped $22,100 metric | One-off author variance, missing-instruction contributor |
| 2 | Unbacked AI Tools claim | Missing first-draft instruction (packet-schema ambiguity) |
| 3 | JD-paraphrase-adjacent hook | Qualitative issue; mechanical-guard adequacy is an open question |
| 4 | Cross-document verbatim repetition | Missing first-draft instruction (highest-confidence, lowest-risk fix) |
| 5 | Uncited connective sentences | Missing instruction + real detector-precision trade-off |
| 6 | Section-rewrite severity overall | Digest-completeness gap + first-draft variance, not a packet defect |

## Explicitly NOT decided here

Whether to: widen `LW-011`, tighten `_cover_factual_sentences`, add a digest line about
cross-document repetition, add a digest line about Core-Competencies provenance, or add a
digest line about mining low-priority-claim excerpts fully. Any of these is a small,
separately-reviewable change — bundling them into one story risks the same "stylistic
rules from one draft" mistake Jason's instructions explicitly warn against. Recommended
next step: a fresh product-manager-role pass to decide which of the six findings above
are worth a bounded story at all (per Jason's instruction not to mechanize from a single
draft), starting with #4 (cross-document repetition digest line) as the clearest
candidate.
