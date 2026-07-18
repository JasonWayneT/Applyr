# Applyr — Agent Context Map

This file is the tool-agnostic counterpart to `CLAUDE.md` (Claude Code reads that one automatically; most other coding agents — Gemini, Cursor, Antigravity, etc. — read this one instead). The content is the same. If you are an LLM editing this repository, these rules are not suggestions: they protect a real candidate's job search from false claims and broken output.

**Keep `CLAUDE.md` and `AGENTS.md` byte-identical.** Whichever file you edit, copy the same change into the other one before you finish the task — do not let them drift again. They went out of sync once already (CLAUDE.md was missing six whole sections as of 2026-07-06, until it was resynced from this file) simply because one file kept getting updated and the other didn't. There is no automated check for this; it's on you to do it manually every time.

If you only do one thing before touching `data/submissions/`, do this: **run the verification commands in "Required Verification Before You're Done" below.** Do not consider a resume or cover letter finished until those commands pass clean.

**Trigger phrase binding:** when Jason says a resume/cover letter should be "conversion ready," "apply ready," "ready to send," or asks you to "review" or "check" one — that always means running the full three-pass workflow in [.claude/skills/conversion-ready-pass/SKILL.md](.claude/skills/conversion-ready-pass/SKILL.md): rubric scoring against `data/conversion_rubric.md` (R1–R8 resume / C1–C5 cover letter), a mechanical truth-grounding sweep, and a qualitative hiring-manager read, looped up to 3 rounds. That file is plain markdown with no Claude-Code-specific mechanism required to use it — if you are a different coding agent and have no automatic skill-loading step, open and follow it directly rather than stopping at the rubric. He should not have to name these files or re-link the research report each time. Don't just eyeball a document for typos and call it done, and don't stop after the rubric score alone — that is Pass 1 of three, not the whole workflow.

---

## Active Engineering Work — Read This First If You're Here to Build, Not Draft

There are three active, resumable engineering threads:

1. **[docs/spec/08-implementation/CR-070-claude-native-generation-pipeline-epics.md](docs/spec/08-implementation/CR-070-claude-native-generation-pipeline-epics.md)**
   — the most recently active thread (2026-07-17 session). Rearchitects the generation pipeline to run
   inside Claude Code natively instead of calling local Ollama models, batch-capable across the 271-JD
   archive with minimal permission-prompt friction. 9 epics, checkbox-tracked. **Current state:**
   Epic 1 done (docs corrected). Epic 2 (fit evaluation) validated against 34 real archived JDs —
   judgment quality holds up, but the real blocker to flipping the default is that no automated
   mechanism exists yet to populate a fit judgment during a live run (that's Epic 5's job). Epic 3
   (`audit_and_improve.py` port) has a built, reviewed module (`scripts/audit_improve_native.py`) with
   one known, well-scoped bug left: it treats every `validate_hard_facts` warning as blocking, when at
   least one class of warning (education-section self-healing) represents a successfully auto-corrected
   condition, not a real problem — **fix that first**, then continue to Epic 5. Two superpowers-format
   execution plans track exact task-by-task state:
   [Epic 1-2 plan](../superpowers/plans/2026-07-17-cr070-epic1-epic2.md),
   [Epic 3 plan](../superpowers/plans/2026-07-17-cr070-epic3.md). Spec:
   `docs/spec/05-change-requests/CR-070-claude-native-generation-pipeline.md`.
2. **[docs/spec/08-implementation/CR-053-fit-rubric-overhaul-epics.md](docs/spec/08-implementation/CR-053-fit-rubric-overhaul-epics.md)**
   — scoring/pipeline overhaul (covers CR-053 fit-rubric rebuild, CR-054 pipeline-failure-transparency
   hardening, CR-055 collection-gate accuracy fixes). It is a self-contained handoff doc with
   checkbox-tracked epics/stories, file:line references, real production-log evidence, and an explicit
   cross-CR priority ranking at the bottom. Open it, find the first unchecked story, and start there.
   It supersedes the scoring policy in CR-039 (`docs/spec/05-change-requests/`) — if the two disagree,
   the CR-053 doc wins until it's closed out and the registry below is updated to reflect it. CR-070
   Epic 2 relocates *where* fit judgment happens but does not change this scoring formula — coordinate,
   don't re-litigate.
3. **[docs/spec/08-implementation/CR-064-claim-score-formula-rework-tracker.md](docs/spec/08-implementation/CR-064-claim-score-formula-rework-tracker.md)**
   — rework `score_claim_for_jd`'s scoring formula (dedup + rarity weighting) so a claim with rare,
   precise vocabulary (a named tool, a specific compliance regime) can outrank a claim whose generic PM
   vocabulary happens to overlap the JD everywhere. This is CR-063's own root-caused conclusion, not a
   new hypothesis: CR-063 (below) measured a 16-JD eval set, tested both of its own proposed fallbacks
   (semantic re-ranking via cached embeddings, `jd_profile_mode="llm"`) with real local infra, found both
   made things worse or made no difference, and pinned the defect to this one function. Start here, not
   by reopening the fallback paths CR-063 already ruled out. Spec:
   `docs/spec/05-change-requests/CR-064-claim-score-formula-rework.md`.

**Diagnostic work, done — read before touching CR-064 above, not instead of it:**
[docs/spec/08-implementation/CR-063-jd-theme-claim-selection-loop-tracker.md](docs/spec/08-implementation/CR-063-jd-theme-claim-selection-loop-tracker.md)
ran the test-and-iterate loop measuring whether JD theme-extraction and claim-selection
(`jd_tailoring.py`) surface the right grounded claims per JD, against a 16-JD human-verified eval set
(`docs/reports/jd-theme-claim-eval-set.md`). Baseline: 14/45 should-surface codes, 0/16 companies with a
full pass. Three `THEME_KEYWORDS` rounds left that flat; a Final round tested embeddings (made the
aggregate monotonically *worse*, 14/45 → 11/45) and `jd_profile_mode="llm"` (byte-identical selection
accuracy to the deterministic path despite better theme extraction) and ruled out both with real
measured data, not architectural reasoning alone. Full trail — including a documented mid-session
section-ordering bug that got caught and fixed — is in the tracker; the conclusion is CR-064 above.

This doc was written before being formally registered in the CR registry
(`docs/spec/05-change-requests/README.md`) or split into the repo's usual `CR-XXX.md` (spec) +
`IMP-CR-XXX.md` (implementation notes) pair — it's a hybrid of both. If you create the formal CR-053/
054/055 entries as part of this work, keep this file as the working epics tracker rather than
duplicating the checkboxes elsewhere.

**Closed, not active:**
[docs/spec/08-implementation/CR-059-local-llm-tuning-loop.md](docs/spec/08-implementation/CR-059-local-llm-tuning-loop.md)
was closed 2026-07-08 as moot before any round ran — the default *drafting* pipeline (JD profiling,
claim selection, bullet/summary/cover-letter assembly) calls zero local LLMs (deliberate architecture
since CR-017, not a bug). This does NOT extend to fit evaluation or the post-draft rewrite step —
`structured_fit.py`'s `_call_equivalence_llm` (one Ollama call per JD, CR-053) and, until CR-070 Epic 3
lands, `audit_and_improve.py`'s rewrite loop both call local LLMs on the default path today. CR-059's
own tracker doc scoped fit-scoring out of its finding by name; this note previously lost that nuance.
See [CR-070](docs/spec/05-change-requests/CR-070-claude-native-generation-pipeline.md) for the
rearchitecture of both. See CR-059's doc top section for the original finding. Its predecessor,
**[docs/spec/05-change-requests/CR-058-generation-defect-fixes.md](docs/spec/05-change-requests/CR-058-generation-defect-fixes.md)**
(7 confirmed generator bugs fixed same session, uncommitted as of 2026-07-07 — check `git status` before
assuming these are live), remains a valid reference for drafting-pipeline defect history. Full
investigation trail:
`_bmad-output/implementation-artifacts/investigations/applyr-generation-defects-investigation.md`
(parent `Resource/CodeProjects` dir, shared BMAD install, not inside this repo).

---

## Documentation Update Checklist — Where to Update When You Change Pipeline Behavior

Don't consider a pipeline/connector/gate change finished until the docs below are updated too. This is how CHANGELOG.md, README.md, and PRODUCT_CAPABILITIES.md have gone stale before (see CR-056 — the README connector table was missing several already-active connectors and had wrong OpenPostings setup instructions before it got fixed).

| You changed... | Also update... |
|---|---|
| A connector (added/removed/fixed an API endpoint) | `CHANGELOG.md` (Fixed/Removed/Added under `[Unreleased]`), `README.md` connector table (`## Core workflows` → `### Scouting`), `PRODUCT_CAPABILITIES.md` §1 sourcing-engine line |
| A gate (geographic, industry, title, years, fit-score threshold) | `CHANGELOG.md`. If it's a policy/threshold decision rather than a bug fix, confirm the change actually reached `data/candidate_preferences.json` post-materialization (see next row) |
| Anything that should end up in `data/candidate_preferences.json` | Update it through the real Settings route (`/api/profile/job_search` for search/gate prefs, or the relevant `/api/profile/:key`), not a direct file edit. `materializeJobSearchPrefs` (`server/domain/jobSearchPrefs.ts`) regenerates this file from the DB `profiles.job_search` row on every Settings save, so a direct file edit gets silently overwritten the next time Jason touches the Settings UI |
| A meaningful, multi-file change worth a formal record | New `docs/spec/05-change-requests/CR-XXX-slug.md`, following the CR-053/054/055/056 format (Metadata / Problem / Decision / Acceptance Criteria / Out of Scope — keep it short, these run ~25-50 lines) |
| Anything in this file | `CLAUDE.md` — copy the exact same edit over. Resynced byte-identical on 2026-07-06 after CLAUDE.md was found missing six sections; see the note at the top of this file. |

**Where the scout/connector architecture actually lives** (so this doesn't need re-discovering by grep next time):
- Connector implementations: `packages/connectors/{name}/index.ts` — each is a self-contained `JobConnector` (`fetchJobs` / `normalize` / `healthCheck`)
- Connector wiring: `server/services/scoutOrchestrator.ts` — `buildDefaultConnectors()` is the single source of truth for which connectors actually run
- Gates (title/industry/geographic/blocklist): `shared/domain/gates.ts`
- Geo helpers (local area terms, remote-signal detection): `shared/domain/geoPrefs.ts`
- Settings UI: `src/components/SettingsView.tsx` — uses a per-settings-key debounce timer map (fixed in CR-056, was previously one shared timer that let unrelated field edits silently cancel each other's pending saves); don't reintroduce a single shared timer
- OpenPostings: lives at `data/archive/OpenPostings-extracted/OpenPostings-main/`, not project root. Only needs 4 real deps (`cors`, `express`, `sqlite`, `sqlite3`) — do not run its full `npm install`, which pulls in an unrelated Expo/React Native app tree

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
| `data/conversion_rubric.md` | Scoring rubric R1–R8 (resume) and C1–C5 (cover letter). **Thresholds: Resume 70+ = CONVERT-READY, Cover Letter 65+ = CONVERT-READY.** Do not chase points above threshold. | When evaluating or scoring a submission — this is the actionable day-to-day tool |
| `data/pm_resume_cover_letter_research_report.md` | Background research the rubric above was built from (same heuristics, cited evidence, narrative form). Not a scoring tool itself. | Only when you need the reasoning behind a specific rubric criterion, or when revising the rubric itself |
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
- Titles above Senior IC PM (no Director, Head of, Principal, VP, Staff, Group PM)
- AI/ML model training, ownership, or engineering
- Revenue, billing, or payment system ownership
- Tools not in Jason's history (no Snowflake, Tableau, FHIR, Docker, etc. unless in workExperience.md)
- "Familiar with," "awareness of," or "literacy in" any tool — if it's not a hard skill in the source, it doesn't exist
- Internal codenames (see VOC table below) — always translate to plain-language equivalents
- $800K Canadian platform deprecation (ACC-114 — disabled pending verification)

**Cross-functional partners — only from this verified list (Cision):**
Engineering, DBA, DevOps, Customer Experience (CX), Customer Support, Sales, Account Management, Legal, InfoSec, Product Marketing, Executive/Presidential Leadership, Upgrades (per ACC-104). Do NOT add teams from a JD that aren't on this list.

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

## Cover Letter Proof-Point Selection

Choose each letter's proof points purely on fit to that letter's own JD — score against `data/conversion_rubric.md` C2 (Proof Density) and C3 (Role Fit Logic) for that document alone. Do not compare a letter to other companies' letters and do not edit one because it resembles another: each hiring manager only ever reads their own letter, so cross-letter similarity has no direct effect on whether any single letter converts. (Corrected 2026-07-07 — an earlier version of this section framed cross-letter distinctiveness as a goal in itself, which led to reassigning proof points to make letters look different rather than to make them fit better. In practice the two often point the same direction, since a repeated skeleton across many letters is usually a symptom that the proof point was never actually chosen for the JD in front of it. Treat it as exactly that: a symptom to investigate via C2/C3, not a target to optimize directly.)

If two letters for different companies independently land on the same true accomplishment because it is genuinely the strongest fit for both JDs, that is correct — leave it alone. Only revisit reused phrasing if it fails C2/C3 for that letter on its own merits, or if the language itself is generic/AI-sounding within that one letter (a C4 Authenticity issue — see Forbidden Language below), not because it also appears elsewhere.

Keep cover letters 250-400 words, one page, opening with something specific to the company rather than generic enthusiasm (C1 Opening Hook). Avoid generic AI closers (e.g. "I would welcome the opportunity to speak with your team") when they read as filler for that letter — this is a per-letter authenticity check, not a batch-variety check.

**This covers sentence-level phrasing too, not just proof-point selection** (corrected again 2026-07-16 — the 2026-07-07 correction above didn't stop the same mistake from recurring in a different form). Finding that several cover letters share a similar opening-hook structure or closing line is not, by itself, a defect. No hiring manager reads two of Jason's letters side by side, so a shared closer like "I would welcome a conversation about how this maps to X" across many companies carries zero real conversion risk — it is invisible to every actual reader. Before flagging or rewriting anything that spans multiple submissions, ask: would this be noticeable to someone who only ever reads this one document? If answering requires comparing it to another company's letter, it is out of scope — do not raise it, not even as a secondary point stacked alongside a real single-letter issue. Judge each line only on whether it reads as generic or AI-sounding standing completely alone.

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
