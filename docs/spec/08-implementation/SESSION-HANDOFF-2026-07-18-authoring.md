# Session Handoff — 2026-07-18: Direct Authoring of Conversion-Ready Submissions

**Read this before doing anything else. It supersedes the CR-070 epic tracker as the active thread.**

## The goal, stated plainly

Produce resumes and cover letters that **convert** — that survive a critical hiring manager reading
them next to the JD, and survive a reader trying to work out whether AI wrote them. Everything else
(pipeline architecture, epics, render counts, permission prompts) is subordinate to that and has
repeatedly become a distraction from it. If you find yourself working through a checklist instead of
improving a document, stop and re-read this paragraph.

## How we work now (changed this session — do not revert)

- **Do NOT generate via `draft_compiler.run()` or the deterministic claim-selection pipeline.** JD
  extraction is known-unreliable and the assembled output has needed heavy rewriting every time.
  **You are the author.** Read the JD yourself, read the ground truth, and write the documents.
- **Keep the conventions, drop the mechanism.** Document structure, 1-page rule, grounding discipline,
  forbidden language, rubric targets all still apply. Satisfying them is a matter of judgment while
  writing, not of running the generator.
- **Do use the deterministic safety checks as verification** on text you have already written. They are
  fast, proven, and touch none of the broken extraction code:
  `submission_linter.lint_document`, `quality_checker.check_resume`,
  `audit_improve_native.apply_claude_native_improvement`, `approved_metrics.find_unapproved_metrics`.
- **No PDFs right now.** `.md` only, per Jason 2026-07-18.
- **Applyr only has to be in the loop when real assets need to show up in the UI.** Archive practice
  does not need to route through pipeline file conventions.
- **When you find a defect, fix the cause, not just the instance.** A stale doc, a wrong constant, or a
  guard that blocks a true claim will reproduce the defect next run. This is an explicit standing
  instruction from Jason.

## Source of truth

| What | Where |
| :--- | :--- |
| Career ground truth, metrics, anti-claims, **Attribution Discipline** | `data/workExperience.md` |
| Claim library (64 claims; 9 carry `attribution`/`allowed_claims`/`prohibited_claims`) | `data/master_claims.json` |
| Quality bar (R1–R8 resume, C1–C5 cover letter; 70/65 thresholds) | `data/conversion_rubric.md` |
| Cover letter structure, proof ordering, word count | `data/Cover_Letter_Reference.md` |
| Voice (`professional` profile) | `C:\Users\Jason\.claude\skills\voice-rewrite\` |
| Authoring rules + 7 real mistakes to avoid | `.claude/skills/generate-submission/SKILL.md` |
| Archive of 271 JDs to practice against | `data/archive/submissions/*/Original_JD.txt` |

## Done this session

- **Attribution layer (P0/P1).** Found and fixed a false causal claim that shipped in 4 of 4 resumes:
  `summary_builder.py` hardcoded *"sustained retention near 7% annually **through** a capacity model"*.
  Jason's correction: churn stability was collective across all reliability/security/migration work;
  the capacity model was for **prioritization and roadmap creation**. Added an Attribution Discipline
  section to `workExperience.md` (owned / contributed / influenced, safe verbs, per-metric map) and
  per-claim metadata on the 9 risk-carrying claims.
- **MET-05 corrected to ~$2M** (was a $1M–$2M range) across `workExperience.md`, `CLAUDE.md`,
  `AGENTS.md`, `master_claims.json`, per Jason.
- **Fixed the doc bug that caused a real authoring failure:** CLAUDE.md/AGENTS.md said the summary is
  "3+ sentences"; the enforced rule is **exactly 3** (2 template + max 1 proof — see
  `SUMMARY_TEMPLATE_SENTENCES` / `SUMMARY_MAX_PROOF_SENTENCES` in `resume_conversion_eval.py`).
- **Fixed `BLOCKED_TOOLS` wrongly blocking Pendo** — approved by ACC-117/118/119 (he holds a Pendo
  certification) and named explicitly in some JDs. Was flagged unverified in the CR-070 tracker; now
  confirmed and removed.
- **Three submissions authored directly** and preserved at `data/authored_drafts/{1uphealth,
  accompany_health,instructure}/`. All pass linter, structure, and grounding checks clean.

## The open problem — start here

An independent adversarial review (fresh reviewer, hiring-manager persona) returned:
1upHealth **borderline/no**, Accompany Health **yes with reservations**, Instructure **yes**.

**The one finding that matters, repeated across all three documents:**

Every document runs on the same rhetorical engine — *a longer explanatory sentence, then a short
declarative that reverses or reframes it.*

> "Not everyone got what they asked for. **The point was that they could see why they did not.**"
> "The quantitative signal set the priority. **Customer conversations set the order.**"
> "...I drove the decision to rebuild. **The drop-off went to zero.**"
> "...so scope conversations **stopped being about who argued hardest.**"
> "...costs someone their afternoon **rather than a line on a dashboard.**"

The reviewer's point: *"Individually every one of these is a good sentence. That is precisely the
problem. They are uniformly good, at a consistent interval, in a consistent shape."* It is detectable
**within a single document**, so the "no reader sees two letters" defense does not apply.

**Why our checks missed it:** the burstiness check measures sentence *length* variance (healthy,
stdev 8.9–10.8). The tic is in sentence *structure*, which is uniform. **Length varied; shape did not.**
Any future burstiness check must test structural variety, not just length.

Two related symptoms:
- **Polish substituting for specificity.** The most polished lines carry the least information ("Data
  integrity is where I do my best work," "I am at my best where priorities shift"). The genuinely
  convincing material is delivered plainly.
- **No researched company facts.** Not one of the three letters contains a fact about the company that
  is not inferable from the JD text. The reviewer called this the batch-production tell.

### The working loop (Jason's explicit direction, 2026-07-18)

This is **not** write-then-correct. Each cycle:

1. Author from an archive JD (`data/archive/submissions/*/Original_JD.txt`).
2. Independent critical-hiring-manager review — a **fresh subagent** with that persona, never
   self-review as the final check.
3. For **every** finding: identify why the mistake happened, find the cause in the process (an
   authoring rule that didn't exist, a stale doc, a check that can't see the defect), and fix the
   cause so it cannot recur. Fixing the instance alone does not close a finding.
4. Next batch.

The loop ends when documents convert and survive that scrutiny **on the first pass** — not when a
given batch has been patched into shape. The root-cause fixes for the three findings above landed as
rules 8–10 in `.claude/skills/generate-submission/SKILL.md`'s "Authoring mistakes that have actually
happened" list (that file is gitignored — it lives locally, not in this repo's history).

### Next actions, in order

1. **Rewrite all three** with the tic deliberately flattened — at most **one** landing line per letter,
   everything else just reports what happened — and spend the reclaimed words on one researched,
   specific fact about each company.
2. **Re-run the independent judge** (spawn a fresh subagent with a hiring-manager persona; do not
   review your own work as the final check — you will not see your own tics).
3. **Per-document fixes** the reviewer named: 1upHealth ignores a *required* consumer-facing-product
   qualification while conceding only the optional FHIR gap; Accompany Health's closing paragraph
   compares a B2B user's bad afternoon to a complex-needs patient's care journey (tone-deaf for that
   company); Instructure carries a `## PROJECTS` block advertising a job-application automation tool in
   a letter whose main asset is sounding human, and says nothing about the stated East Coast preference.
4. Then continue through the archive in batches of 5, reporting after each batch.

## Needs Jason's decision (do not decide unilaterally)

**"Six years" vs. the dates.** Resumes say "six years"; the experience section runs June 2017 – January
2026 (8.6 years total, 6.9 since his first PM/PO title). `workExperience.md:36` says "6+ years" and
line 47 targets "Mid-level PM / PM II with 3–7 years" — so the understatement may be **deliberate
positioning** toward mid-level roles rather than staleness. A recruiter subtracting the dates sees a
contradiction. Proposed fix that preserves the positioning: say **"six years as a product manager"**
rather than bare "six years." Confirm with Jason before changing.
