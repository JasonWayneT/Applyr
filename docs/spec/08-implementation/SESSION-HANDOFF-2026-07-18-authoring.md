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
| The full JD-triage → author → verify process (Stage 0–3), rewritten 2026-07-19 per `C:\Users\Jason\.claude\plans\magical-booping-wilkes.md` — supersedes this doc's own "7 real mistakes" framing below | `.claude/skills/generate-submission/SKILL.md` |
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

### Loop state after rounds 2–3 (updated 2026-07-18, second session)

Round-1 findings were root-caused into SKILL.md rules 8–10 and the three drafts rewritten. A fresh
round-2 judge confirmed the landing-line tic gone but found its successor (the "X rather than Y"
contrast frame, now guarded by `LW-008` in `submission_linter.py` + rule 11), an **ungrounded claim**
("no dedicated security engineering capacity" in the Instructure letter — invented, fixed), the
"200 stakeholders" inflation (rule 13 + ACC-109 framing note in `workExperience.md`), and
stage-mismatched process framing (rule 14). After those fixes, round-3 verdicts: 1upHealth
**YES WITH RESERVATIONS** (was borderline/no in round 1), Accompany Health **BORDERLINE**, Instructure
**YES**. Round-3's new structural findings became rules 16–18 (bullet-skeleton uniformity, kicker-ending
density, triplet frequency).

**Resolved same session:**
- **Travel ceiling**: Jason confirmed 15% max. Added as `workExperience.md` §1.4, rule 19, and fixed
  in the Instructure letter (states the true 15% ceiling against the JD's ~25% ask, plainly, not as a
  second staged-candor beat).
- **Zero To Sixty framing**: Jason confirmed he was hired as an Account Manager and moved into product
  work himself over the tenure, earning the Product Owner title by the end — the automation projects
  (ACC-301/302/303) **are the evidence of that move**, not separate ops work. Documented in
  `workExperience.md` §2.1. All three resumes' Zero To Sixty section now reads "Account Manager →
  Product Owner" with a lead bullet stating the arc (worded differently per resume per rule 15).

**Still open, needs Jason:** whether mission-driven companies get explicit mission-engagement content
in the letter (Accompany's borderline verdict leans on its absence — the letter is procedurally humble
but never engages why the mission itself matters to him), and whether any ship-measure-iterate story
exists in ground truth to counter reviewers' "every accomplishment is defense/triage" observation
(ACC-106, the mobile UVPM competitive-gap fix, is the closest candidate — confirm before using it that
way).

### Next actions, in order

1. **Rewrite all three** with the tic deliberately flattened — at most **one** landing line per letter,
   everything else just reports what happened — and spend the reclaimed words engaging one concrete,
   company-specific detail **from the JD itself**. (Jason, 2026-07-18: **no web research** — the loop
   runs offline from the archive JDs and ground truth only.)
2. **Re-run the independent judge** (spawn a fresh subagent with a hiring-manager persona; do not
   review your own work as the final check — you will not see your own tics).
3. **Per-document fixes** the reviewer named: 1upHealth ignores a *required* consumer-facing-product
   qualification while conceding only the optional FHIR gap; Accompany Health's closing paragraph
   compares a B2B user's bad afternoon to a complex-needs patient's care journey (tone-deaf for that
   company); Instructure carries a `## PROJECTS` block advertising a job-application automation tool in
   a letter whose main asset is sounding human, and says nothing about the stated East Coast preference.
4. Then continue through the archive in batches of 5, reporting after each batch.

## Resolved decisions

**"Six years" vs. the dates — RESOLVED (Jason, 2026-07-18).** `workExperience.md:36` now mandates
**7 years** ("Use 7. Do not write 'six years' or '6+ years' anywhere"), derived from first PM/PO
title Feb 2019 → Jan 2026 = 6.9 years. All three authored resumes already say "seven years."
