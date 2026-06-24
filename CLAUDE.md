# Applyr — Claude Code Context Map

This file is automatically loaded when Claude Code opens this project. It maps every critical file and enforces the anti-hallucination rules that protect Jason's job search.

---

## Who This Is For

This workspace is configured for a **B2B SaaS Platform PM** with 6+ years of experience.
To protect candidate privacy:
- All real contact details (PII) are stored locally in the gitignored [data/workExperience.md](file:///c:/Users/Jason/Desktop/Jason/Resource/CodeProjects/Applyr/data/workExperience.md) (Section 1.0) and inside the gitignored SQLite database `jobagent.sqlite`.
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

---

## Forbidden Language (Anti-AI Fingerprint)

Never use: em dashes (—), "leverage," "passionate," "driven," "dynamic," "innovative," "seamless," "transformative," "synergy," "tapestry," "revolutionize," "proven track record," "I am excited to apply," "I am confident that," "Furthermore," "Moreover," "In addition," "Additionally."

Never open a sentence with transition fluff. Never start a cover letter with "I am writing to express my interest."

No bullet points in cover letters. No em dashes anywhere.

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

## What the Pipeline Does vs. What Manual Polish Does

**Pipeline generates automatically:**
- JD parsing and keyword extraction
- Claim selection from master_claims.json
- Initial Resume.md and CoverLetter.md drafts
- cover_letter_plan.json, jd_profile_cache.json, Interview_Cheat_Sheet.md
- PDF compilation

**Manual polish (your job with Claude Code):**
- Score the documents against conversion_rubric.md
- Rewrite cover letter hooks when the pipeline hook is generic
- Tighten resume bullets to match JD language
- Fix any claims that don't trace back to workExperience.md
- Recompile PDFs after edits

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

---

## Active Submissions (as of June 2026)

Located in `submissions/`. Apply-ready: allstate, biggerpockets, cambium_learning_group, dat_freight_analytics, element451, eval_brown_brown_pm, modern_campus, moro_tech, oxio. 
- **stripe** — JD only 3 bullets; needs full JD recapture before applying
- **unity** — Senior TPM / gaming domain; flagged do-not-apply
