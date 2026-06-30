# Applyr — Agent Context Map

This file is the tool-agnostic counterpart to `CLAUDE.md` (Claude Code reads that one automatically; most other coding agents — Gemini, Cursor, Antigravity, etc. — read this one instead). The content is the same. If you are an LLM editing this repository, these rules are not suggestions: they protect a real candidate's job search from false claims and broken output.

If you only do one thing before touching `data/submissions/`, do this: **run the verification commands in "Required Verification Before You're Done" below.** Do not consider a resume or cover letter finished until those commands pass clean.

---

## Active Engineering Work — Read This First If You're Here to Build, Not Draft

There is an active, resumable scoring/pipeline overhaul in progress:
**[docs/spec/08-implementation/CR-053-fit-rubric-overhaul-epics.md](docs/spec/08-implementation/CR-053-fit-rubric-overhaul-epics.md)**
(covers CR-053 fit-rubric rebuild, CR-054 pipeline-failure-transparency hardening, CR-055
collection-gate accuracy fixes). It is a self-contained handoff doc with checkbox-tracked epics/stories,
file:line references, real production-log evidence, and an explicit cross-CR priority ranking at the
bottom. Open it, find the first unchecked story, and start there. It supersedes the scoring policy in
CR-039 (`docs/spec/05-change-requests/`) — if the two disagree, the CR-053 doc wins until it's closed
out and the registry below is updated to reflect it.

This doc was written before being formally registered in the CR registry
(`docs/spec/05-change-requests/README.md`) or split into the repo's usual `CR-XXX.md` (spec) +
`IMP-CR-XXX.md` (implementation notes) pair — it's a hybrid of both. If you create the formal CR-053/
054/055 entries as part of this work, keep this file as the working epics tracker rather than
duplicating the checkboxes elsewhere.

---

## Who This Is For

This workspace is configured for a **B2B SaaS Platform PM** with 6+ years of experience.
To protect candidate privacy:
- All real contact details (PII) are stored locally in the gitignored `data/workExperience.md` (Section 1.0) and inside the gitignored SQLite database `jobagent.sqlite`.
- Do NOT write or commit real names, emails, phone numbers, or LinkedIn URLs to tracked Git files.

---

## File Map — Read These Before Writing Anything

| File | Purpose | Read When |
|------|---------|-----------|
| `data/workExperience.md` | **Ground truth.** Every metric, accomplishment, and claim must trace back here. Contains VOC codes (vocabulary translation), MET codes (verified metrics), ACC codes (approved accomplishments), and explicit DO NOT CLAIM lists. | Before writing any bullet, proof paragraph, or metric |
| `data/master_claims.json` | Structured claim catalog used by the pipeline. 59+ active claims. Claims with `"disabled": true` are quarantined and must NOT be used. | When selecting proof points for cover letters |
| `data/conversion_rubric.md` | Scoring rubric R1–R8 (resume) and C1–C5 (cover letter). **Thresholds: Resume 70+ = CONVERT-READY, Cover Letter 65+ = CONVERT-READY.** Do not chase points above threshold. | When evaluating or scoring a submission |
| `data/candidate_preferences.json` | Filter preferences: no solo/founding PM roles, no 0-to-1, min fit score 72. | When evaluating job fit |
| `data/Cover_Letter_Reference.md` | Cover letter structural reference | When drafting cover letters |
| `submissions/{company}/Original_JD.txt` | The actual job description for that role | Before tailoring any submission |

---

## Verified Metrics (MET Codes) — Never Extrapolate These

All metrics below are from `data/workExperience.md` Section 4. Use them exactly as stated. Do not round up, combine, or imply causation beyond what is written.

| Code | Metric | Value |
|------|--------|-------|
| MET-01 | Platform ARR | $40M (approx) |
| MET-02 | Active accounts | ~3,500 |
| MET-03 | Active users | ~25,000 |
| MET-04 | Platform churn rate | 7% annually |
| MET-05 | Infrastructure savings (Cision) | $1M–$2M cumulative |
| MET-06 | Contact data drop-off (pre-fix) | 40% |
| MET-07 | Data drop-off post-remediation | 100% reduction |
| MET-08 | Security backlog resolved | ~90% of ~300 items |
| MET-09 | Customer databases managed | ~200 SQL databases |
| MET-10 | Voluntary migrations | ~700 accounts |
| MET-11 | Fulfillment contract value | $288K; saved $34K/yr |
| MET-12 | Onboarding automation savings | $22,100/yr |
| MET-13 | Sterkly revenue sustained | ~$1M–$3M (estimated) |
| MET-14 | Certificate cost savings | ~$100/certificate |
| MET-15 | Conversion improvement (Z2S) | ~40% (estimated) |
| MET-16 | Fulfillment scale | 10/day → 100+/day |

**ACC-114 ($800K Canadian platform deprecation) is DISABLED** — do not use this claim until Jason confirms it is real and it is added to workExperience.md.

---

## Approved Accomplishments (ACC Codes)

Full text in `data/workExperience.md` Sections 5.1–5.3. Quick reference:

**Cision (ACC-101 to ACC-110)**
- ACC-101: Platform stabilization / indexing server crashes
- ACC-102: Data remediation — 40% drop-off → zero
- ACC-103: Security backlog triage — 90% resolved
- ACC-104: Migration tooling — ~700 accounts
- ACC-105: Capacity modeling / T-shirt sizing
- ACC-106: Mobile UVPM competitive gap
- ACC-107: Compliance & privacy workflows
- ACC-108: Jira ticket prioritization system
- ACC-109: Quarterly PI planning (~200–300 stakeholders)
- ACC-110: Cross-team knowledge transfer through layoffs

**Sterkly (ACC-201 to ACC-204)**
- ACC-201: Workflow standardization
- ACC-202: Technical-to-business translation
- ACC-203: Certificate bottleneck / $1M–$3M revenue sustained
- ACC-204: QA ownership, global team coordination

**Zero To Sixty (ACC-301 to ACC-303)**
- ACC-301: Laptop fulfillment automation
- ACC-302: Salesforce onboarding automation
- ACC-303: Conversion funnel / landing page

---

## Hard Anti-Hallucination Rules

These are absolute. Violating any of these requires immediate rewrite.

**Never claim:**
- People management, direct reports, hiring/firing, or managing other PMs
- Titles above PM II (no Director, Head of, Principal, VP, Staff)
- AI/ML model training, ownership, or engineering
- Revenue, billing, or payment system ownership
- Tools not in Jason's history (no Snowflake, Tableau, FHIR, Docker, etc. unless in workExperience.md)
- "Familiar with," "awareness of," or "literacy in" any tool — if it's not a hard skill in the source, it doesn't exist
- Internal codenames (see VOC table below) — always translate to plain-language equivalents
- $800K Canadian platform deprecation (ACC-114 — disabled pending verification)

**Cross-functional partners — only from this verified list (Cision):**
Engineering, DBA, DevOps, Customer Experience (CX), Customer Support, Sales, Account Management, Legal, InfoSec, Product Marketing, Executive/Presidential Leadership. Do NOT add teams from a JD that aren't on this list.

**Codename translation (VOC codes):**
| Codename | Use Instead |
|----------|------------|
| Platform Data Remediation | Centralized platform data remediation initiative |
| Core B2B SaaS Platform | Customer-facing B2B SaaS media monitoring & contact database platform |
| Centralized Contact Database | Centralized contact source-of-truth database |
| Critical Save Program | High-risk account retention program |
| White Glove Accounts | Premium high-revenue enterprise clients |
| Airo (Sterkly product) | "A macOS security product" — under NDA, never name it |

**Forbidden tone (R-011 / tone_guard.py):** never use "layoff(s)" — use "resource constraints," "resource-constrained cycle," or "organizational transitions" instead. The drafting engine has produced this violation before; double-check it specifically.

---

## Forbidden Language (Anti-AI Fingerprint)

Never use: em dashes (—), double-hyphen (`--`), "leverage," "passionate," "driven," "dynamic," "innovative," "seamless," "transformative," "synergy," "tapestry," "revolutionize," "proven track record," "I am excited to apply," "I am excited about," "I am confident that," "Furthermore," "Moreover," "In addition," "Additionally."

Never open a sentence with transition fluff. Never start a cover letter with "I am writing to express my interest."

No bullet points in cover letters. No em dashes anywhere — including as a stand-in punctuation pattern like `word: word` used to avoid the literal character. If you find yourself writing a colon where an em dash would have gone, restructure the sentence instead; the colon-as-em-dash-substitute pattern is itself a tell.

---

## Required Document Structure (frequently broken by non-Claude-Code agents)

A resume MUST contain these exact section headings, in this order, or it will fail `quality_checker.check_resume()`:

```
# [Name]
[contact line]

## PROFESSIONAL SUMMARY
**[Optional bolded positioning subtitle]**
[3+ sentence paragraph — fewer than 3 sentences fails R-010]

## PROFESSIONAL EXPERIENCE
### [Title] | [Company] | [Start] - [End]
[Location]
* [bullet]
...

## EDUCATION
[degree line]
```

- The heading must be literally `## PROFESSIONAL SUMMARY` — not a custom title line like `## PRODUCT MANAGER | Domain | B2B SaaS`. That exact substitution has happened before and silently fails `R-005`/`R-012`.
- Do not add `## CORE EXPERTISE` or `## TECHNICAL ENVIRONMENT` sections. They are not part of the approved template, and adding them is the single most common cause of resumes overflowing to 2 pages.
- Each bullet must be ≤40 words (`R-013`/`CW-003`).
- Most recent role: 5-6 bullets. Earlier roles: 2-3 bullets. (Engine has produced 7-8 before; trim down.)

---

## The 1-Page Resume Rule

**Resume.pdf MUST be exactly 1 page.** This has been violated by external tools before — every resume came out 2 pages because of the extra sections + bullet bloat described above. There is no automated page-count gate in this pipeline yet, so you must check it yourself manually after compiling (see Required Verification below). Do not submit, and do not tell Jason something is done, without confirming the page count.

---

## Submission Folder Structure

Every complete submission lives at `data/submissions/{company_name}/` and must contain:

```
data/submissions/
  {company_name}/
    Original_JD.txt          — raw job description (required)
    Resume.md                — tailored resume in Markdown
    CoverLetter.md           — tailored cover letter in Markdown
    Resume.pdf               — compiled PDF (via compile_single.py)
    CoverLetter.pdf          — compiled PDF
    cover_letter_plan.json   — pipeline plan metadata (pipeline-generated)
    jd_profile_cache.json    — parsed JD profile (pipeline-generated)
    Interview_Cheat_Sheet.md — Q&A prep (pipeline-generated)
```

To compile MD → PDF: `python scripts/compile_single.py <md_path> <pdf_path>`

---

## Required Verification Before You're Done

Never tell Jason a resume or cover letter is finished without running all of these from `scripts/` and confirming clean output:

```bash
# 1. Lint check (forbidden phrases, em dashes, placeholders)
python -c "
from submission_linter import lint_document
for doc in ['Resume.md', 'CoverLetter.md']:
    with open(f'../data/submissions/{COMPANY}/{doc}', encoding='utf-8') as fh:
        text = fh.read()
    r = lint_document(text, filename=doc)
    print(doc, 'blocks:', [b.rule_id for b in r.blocks], 'warns:', [w.rule_id for w in r.warns])
"

# 2. Resume structure/QA check
python -c "
from quality_checker import check_resume
ok, msg = check_resume('../data/submissions/COMPANY/Resume.md')
print(ok, msg)
"

# 3. Compile to PDF
python compile_single.py ../data/submissions/COMPANY/Resume.md ../data/submissions/COMPANY/Resume.pdf
python compile_single.py ../data/submissions/COMPANY/CoverLetter.md ../data/submissions/COMPANY/CoverLetter.pdf

# 4. Page count — Resume.pdf MUST be 1, CoverLetter.pdf MUST be 1
pdfinfo ../data/submissions/COMPANY/Resume.pdf | grep Pages
pdfinfo ../data/submissions/COMPANY/CoverLetter.pdf | grep Pages
```

If any step fails or the resume is 2 pages, fix the content and re-run — do not hand back a "done" answer with a failing check.

---

## Cover Letter Distinctiveness

Cover letters across different companies should NOT share the same paragraph skeleton or sentence shapes (e.g. reusing "I diagnosed X, designed a remediation initiative that bypassed Y, and drove it to completion" verbatim across multiple letters with only the domain swapped). This reads as templated/AI-generated to a human reviewer even when every individual fact is accurate. Vary the structure, opening, and proof-point selection per company — there is no automated check for this, so make a deliberate pass per letter.

Keep cover letters 250-400 words, one page, opening with something specific to the company rather than generic enthusiasm. Avoid generic AI closers used identically across letters (e.g. "I would welcome the opportunity to speak with your team" appearing unchanged letter after letter) — vary the close too.

---

## What the Pipeline Does vs. What Manual Polish Does

**Pipeline generates automatically:**
- JD parsing and keyword extraction
- Claim selection from master_claims.json
- Initial Resume.md and CoverLetter.md drafts
- cover_letter_plan.json, jd_profile_cache.json, Interview_Cheat_Sheet.md
- PDF compilation

**Manual polish (your job as the agent):**
- Score the documents against conversion_rubric.md
- Rewrite cover letter hooks when the pipeline hook is generic
- Tighten resume bullets to match JD language
- Fix any claims that don't trace back to workExperience.md
- Recompile PDFs after edits
- Run the Required Verification steps above before reporting anything as complete

**Conversion thresholds (stop improving once reached):**
- Resume: 70+ = CONVERT-READY
- Cover Letter: 65+ = CONVERT-READY

---

## Exclusion Zones — What Jason Is NOT

- Not a 0-to-1 greenfield PM
- Not an AI/ML product lead
- Not a people manager
- Not a revenue/billing/payments owner

If a job description requires any of the above as a hard requirement, flag it rather than trying to paper over the gap.
