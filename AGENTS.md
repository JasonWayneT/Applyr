# Applyr — Agent Context Map

This file is the canonical always-on instruction set for Applyr. Claude Code loads it through `CLAUDE.md` via `@AGENTS.md`. Cursor, Gemini, Antigravity, and other agents load this file directly. If you are an LLM editing this repository, these rules are not suggestions: they protect a real candidate's job search from false claims and broken output.

**Do not copy this file into `CLAUDE.md`.** `CLAUDE.md` is an import stub plus Claude-only notes, not a second copy. Edit rules here. Claude-specific notes stay in `CLAUDE.md` below the import.

If you only do one thing before touching `data/submissions/`, do this: **run the verification commands in "Required Verification Before You're Done" below.** Do not consider a resume or cover letter finished until those commands pass clean.

**Trigger phrase binding:** when Jason says a resume/cover letter should be "conversion ready," "apply ready," "ready to send," or asks you to "review" or "check" one — that always means running the full three-pass workflow in [.claude/skills/conversion-ready-pass/SKILL.md](.claude/skills/conversion-ready-pass/SKILL.md): rubric scoring against `data/conversion_rubric.md` (R1–R8 resume / C1–C5 cover letter), a mechanical truth-grounding sweep, and a qualitative hiring-manager read, looped up to 3 rounds. That file is plain markdown with no Claude-Code-specific mechanism required to use it — if you are a different coding agent and have no automatic skill-loading step, open and follow it directly rather than stopping at the rubric. He should not have to name these files or re-link the research report each time. Don't just eyeball a document for typos and call it done, and don't stop after the rubric score alone — that is Pass 1 of three, not the whole workflow. **Scoping note (2026-07-19):** for a document authored via the `generate-submission` skill, its own Stage 2 already satisfies this trigger — don't run `conversion-ready-pass` a second time on top of it. `conversion-ready-pass` is for checking a document *not* produced by that flow.

**Processing job descriptions today?** Invoke the `generate-submission` skill (`.claude/skills/generate-submission/SKILL.md`). CSV/scout JDs land in `data/pending_review/`, not `data/submissions/` (CR-091). Stage 0 Skip is recorded in the `stage0_skips` ledger (URL, then company+title) and the folder moves to `data/archive/skipped/`. Only PASS folders are promoted into `data/submissions/`. **Canonical entry point is `python scripts/run_submission.py data/submissions/{slug}`** (or a pending_review slug) (CR-076–084): sole writer of `workflow_state.json` + `stage_receipts/`; sequences Stage 0 → packet/prompt → WAITING_FOR_LLM → Stage 1 validate → Truth/ATS/HM/Mech/Policy → optional `--finalize`. Under the hood it still uses CR-074 workers (`build_stage0_fit_gate`, packet/digest, `author_from_packet`, `verify_submission`, `finalize_submission_job`) and CR-075 gates — do not call those as the default sequencing path. Do **not** load `agent_context_pack.md` into the Stage 1 author session. Multi-agent / full-pack Stage 2 review (`.claude/workflows/generate-submission-batch.js`) is opt-in only. Not the CR-070 tracker (superseded for generation).

**Drafting a message to reach out to someone at a target company?** Invoke the `networking-outreach` skill (`.claude/skills/networking-outreach/SKILL.md`) — covers both a hiring-manager/role-relevant contact and an unrelated-department warm connection (alum, former coworker), since those need different message structures. Added 2026-07-30 after two drafts of a message to a CivicPlus contact missed the mark (too soft, then no relationship framing) before the pattern got written down.

---

## Active Engineering Work — Read This First If You're Here to Build, Not Draft

Not needed for drafting/reviewing submissions or networking outreach — this section is engineering-only
(same reason it's excluded from `data/agent_context_pack.md`'s digest). Skip it unless you're building.

**Canonical authoring entry point:** `python scripts/run_submission.py data/submissions/{slug}` (CR-076–084) — sole writer of `workflow_state.json` + `stage_receipts/*.json`. Full design + every landed CR independently spot-checked against real data: `harness-bridge/shared-sessions/session-006-applyr-workflow-authority.md`. Do not call the underlying CR-074 workers directly as an alternate sequencing path — see "Required Verification Before You're Done" below.

**Active threads, docs, and current state:** live in `docs/spec/08-implementation/` — CR-094 (WE-primary packet), CR-070 (native generation pipeline), CR-053/054/055 (fit-rubric overhaul), CR-064 (claim-score formula rework, direct conclusion of CR-063's diagnostic work). Each is a self-contained handoff doc with checkbox-tracked stories — open it, find the first unchecked item, start there. Treat those docs as the current source of truth for status, not this file — this section previously carried a full per-CR status table that went stale faster than it could be kept in sync here.

---

## Documentation Update Checklist — Where to Update When You Change Pipeline Behavior

Don't consider a pipeline/connector/gate change finished until the relevant docs are updated too — `CHANGELOG.md`, `README.md`, and `PRODUCT_CAPABILITIES.md` have gone stale before this way (CR-056). Quick map: connector change → `CHANGELOG.md` + `README.md`'s connector table + `PRODUCT_CAPABILITIES.md` §1; gate/threshold change → `CHANGELOG.md`, and confirm it actually reached `data/candidate_preferences.json` via the real Settings route, never a direct file edit (`materializeJobSearchPrefs` overwrites direct edits on the next Settings save); a meaningful multi-file change → a new `docs/spec/05-change-requests/CR-XXX-slug.md`.

**Anything in this file:** edit `AGENTS.md` only. `CLAUDE.md` is an `@AGENTS.md` import stub, not a copy.

**Where the engineering surface lives:** `README.md`'s "Project structure" section is the one source of truth for `server/`/`scripts/` layout and the scout/connector architecture (connector implementations, wiring, gates, Settings UI) — check there before grepping the codebase to relocate something, and fix it in place if it's gone stale rather than re-deriving the map here.

---

## Who This Is For

This workspace is configured for a **B2B SaaS Platform PM** with 7 years of experience.
To protect candidate privacy:
- All real contact details (PII) are stored locally in the gitignored `data/workExperience.md` (Section 1.0) and inside the gitignored SQLite database `jobagent.sqlite`.
- Do NOT write or commit real names, emails, phone numbers, or LinkedIn URLs to tracked Git files.

---

**WorkExperience contract (CR-094):** `workExperience.md` is the source of truth and the runtime evidence. Claims are an index (ids, tags, attribution, prohibited), not a second biography. Stage 1 authors from packet WE spans plus `claim_constraints`, never from claim `text`/`cover_story`. When Stage 0 and Stage 1 disagree, WE wins.

## File Map — Read These Before Writing Anything

| File | Purpose | Read When |
|------|---------|-----------|
| `data/authoring_packet.json` (per submission) | **CR-074 Stage 1 input.** Evidence map + WE excerpts + `claim_constraints`. Built by `scripts/build_authoring_packet.py`. Excerpts are `workExperience.md` spans, not catalog `text`. | Default cloud authoring pass — with the rule digest below; **not** the full context pack |
| `data/authoring_rule_digest.md` | **CR-074 lean rules** (~1.6k tokens) for the cloud author. Generated by `scripts/generate_authoring_rule_digest.py`. | Every CR-074 Stage 1 author session (SYSTEM block) |
| `data/authoring_example_bank.json` | **CR-097 retrieval bank.** Curated before/after examples injected into Stage 1 packets. `few_shot_eligible` is a human flip; `--promote` cannot set it. | When promoting a 2-occurrence review, or debugging why a packet has `learned_examples` |
| `data/authoring_defect_ledger.json` | **CR-097 cross-submission ledger** (gitignored). Occurrences + pending promote/decline reviews. Written by `scripts/scan_authoring_defects.py`. | After Stage 2, or on the every-3-submissions / send-batch sweep (`--status`) |
| `data/agent_context_pack.md` | **Generated fast-path digest** of this file's operative sections + `generate-submission/SKILL.md`'s operative sections + `workExperience.md` + `conversion_rubric.md`, built by `scripts/generate_context_pack.py`. **Not** the default Stage 1 author load after CR-074 — keep for process/engineering sessions and optional send-batch review. **Verify freshness first** — `python scripts/check_context_pack_freshness.py` must print FRESH; if STALE, regenerate before relying on it. | Process work, optional ladder-2 review, or pre-CR-074 flows — not default Stage 1 |
| `data/workExperience.md` | **Ground truth.** Every metric, accomplishment, and claim must trace back here. Contains VOC codes (vocabulary translation), MET codes (verified metrics), ACC codes (approved accomplishments), and explicit DO NOT CLAIM lists. | Before writing any bullet, proof paragraph, or metric |
| `data/master_claims.json` | Retrieval index into WE (ids, tags, attribution, prohibited). Not a second biography. `text`/`cover_story` are not author-facing (CR-094). `"disabled": true` is quarantined. Construction: `data/CLAIMS_STANDARD.md`. ACC-401 is `data/aiProjects.md`. | When selecting proof points (tags only) |
| `data/CLAIMS_STANDARD.md` | CR-088 claim-construction checklist (id/project_id match, distinctive tags, rollup/synthesis claims, ACC-119→skills_catalog, ACC-401 side corpus). | Before adding or editing claims |
| `data/master_claims_tags_only.json` | Generated sidecar with `text`/`cover_story` stripped (`scripts/generate_context_pack.py`). Retrieval index only. | Same as `master_claims.json` — prefer this file when it exists |
| `data/skills_catalog.json` | Verified tools for Core Competencies / JD term gaps. Keep aligned with WE ACC-119 (no ACC-119 claim lens). | When tools rows or skills matching drift from WE |
| `data/conversion_rubric.md` | Scoring rubric R1–R8 (resume) and C1–C5 (cover letter). **Thresholds: Resume 70+ = CONVERT-READY, Cover Letter 65+ = CONVERT-READY.** Do not chase points above threshold. | When evaluating or scoring a submission — this is the actionable day-to-day tool |
| `data/pm_resume_cover_letter_research_report.md` | Background research the rubric above was built from (same heuristics, cited evidence, narrative form). Not a scoring tool itself. | Only when you need the reasoning behind a specific rubric criterion, or when revising the rubric itself |
| `data/candidate_preferences.json` | Filter preferences: no solo/founding PM roles, no 0-to-1, min fit score 72. | When evaluating job fit |
| `data/Cover_Letter_Reference.md` | Cover letter structural reference | When drafting cover letters |
| `data/external_resume_patterns.md` | Third-party PM resume examples (Enhancv), paraphrased — cross-cutting summary/bullet patterns plus per-example notes. Reference only, never a template; don't copy phrasing verbatim. | When working on summary wording specifically, or wanting an outside comparison point before calling a draft done |
| `submissions/{company}/Original_JD.txt` | The actual job description for that role | Before tailoring any submission |

---

## Verified Metrics (MET Codes) and Approved Accomplishments (ACC Codes)

Canonical, full text: `data/workExperience.md` Section 4 (MET-01 through MET-17) and Sections 5.1–5.3
(ACC-101 through ACC-303, plus later IDs). Use every value exactly as stated there — do not round up,
combine, or imply causation beyond what is written. This file no longer carries a quick-reference copy
of either table (moved out 2026-08-14, harness-bridge session-009 R25-R32, Phase 2) — read
`workExperience.md` directly rather than relying on a duplicate here.

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
- Inventing the PIC acronym expansion or claiming sole causation of the full ~$800K Canadian-ingest savings without the ACC-114 CONTRIBUTED hedge

**Cross-functional partners — only from this verified list (Cision):**
Engineering, DBA, DevOps, Customer Experience (CX), Customer Support, Sales, Account Management, Legal, InfoSec, Product Marketing, Executive/Presidential Leadership, Upgrades (per ACC-104). Do NOT add teams from a JD that aren't on this list.

**Codename translation (VOC codes):**
| Codename | Use Instead |
|----------|------------|
| Platform Data Remediation | Centralized platform data remediation initiative |
| Core B2B SaaS Platform / C3 | Customer-facing B2B SaaS media monitoring & contact database platform (updated Cision Communications Cloud stack) |
| CPRE | Legacy enterprise Cision Communications Cloud platform (~38 high-value orgs; never invent a user count) |
| Visible | News content ingestion and enrichment platform for C3 media monitoring (Java; never print Visible) |
| PIC | Dedicated Canadian news content ingestion platform (never invent acronym expansion) |
| Centralized Contact Database | Centralized contact source-of-truth database |
| Critical Save Program | High-risk account retention program |
| Datagroups | Per-client data profiles (e.g. agency keeps Cisco vs AT&T data separate in one account) |
| White Glove Accounts | Premium high-revenue enterprise clients |
| Airo (Sterkly product) | "A macOS security product" — under NDA, never name it |

**Forbidden tone (R-011 / tone_guard.py):** never use "layoff(s)" — use "resource constraints," "resource-constrained cycle," or "organizational transitions" instead. The drafting engine has produced this violation before; double-check it specifically.

**Cover letters: don't discuss workforce reduction at all, not even via the euphemism.** Stronger than R-011's word-substitution rule above — this is a cover-letter-specific scope rule: don't build any part of a cover letter's argument around headcount shrinking, executive turnover as adversity, or "operating through constraint" via team size, not even using an approved euphemism like "resource-constrained cycle." Found running through all three paragraphs of a real letter on 2026-07-21. The resume can still reference resource constraints factually where relevant (workExperience.md's own role context does) — this rule is about what a cover letter argues from, not about erasing the fact.

---

## Forbidden Language (Anti-AI Fingerprint)

Never use: em dashes (—), double-hyphen (`--`), "leverage," "passionate," "driven," "dynamic," "innovative," "seamless," "transformative," "synergy," "tapestry," "revolutionize," "revenue-bearing" (added 2026-07-19 — Jason's own correction: he's never heard the phrase and it isn't how he speaks; it had leaked from `workExperience.md`'s own positioning line into an authored resume), "proven track record," "I am excited to apply," "I am excited about," "I am confident that," "Furthermore," "Moreover," "In addition," "Additionally."

The fuller, actively-maintained list (CR-070 Epic 8 authenticity research + Jason's own `voice-rewrite` skill's Pass 1 strip list) lives in `scripts/submission_linter.py`'s `LR-009`/`LW-006`/`LW-007` rules — that's the single source of truth going forward (per CR-070 Epic 9's decision not to hand-duplicate a growing word list in two places); this section stays as the always-hard-blocked core, not the exhaustive set.

**`no-ai-slop` skill integration.** Jason also uses a general-purpose writing skill, [petergyang/no-ai-slop](https://github.com/petergyang/no-ai-slop), installed globally at `~/.claude/skills/no-ai-slop`. Its pattern catalog was diffed against the existing `LR`/`LW` rules for genuine gaps, added as `WARN` rules: `LW-015` (throat-clearing openers — "Here's the thing"), `LW-016` (faux-insight setups — "what nobody tells you"), `LW-017` (importance puffery — "marks a pivotal moment"), `LW-018` (weasel attribution — "experts agree"), `LW-019` (fake-strong hub-verb — "serves as a centralized hub"), `LW-020` (the "It's not X. It's Y." binary-contrast shape). `LW-007` widened to catch "Ultimately,"/"Overall," as summary-recap openers (comma-gated so "ultimately responsible for" doesn't false-positive). Left un-mechanized as impractical to regex or low-relevance here (negative listing, dramatic fragmentation, synonym cycling, robotic rhythm, fake-profound kickers, formatting slop) — ask Jason before adding a rule for these; a human read still catches them. `submission_linter.py` stays the single source of truth for the full list — see CHANGELOG.md for the integration's full rationale.

Never open a sentence with transition fluff. Never start a cover letter with "I am writing to express my interest."

No bullet points in cover letters. No em dashes anywhere — including the colon-as-em-dash-substitute pattern (`word: word` used to avoid the literal character; restructure the sentence instead, that pattern is itself a tell). **Mechanically enforced as `LR-015` (HARD_BLOCK)**: a colon followed by whitespace then a letter ("compelling: building", "context: how"). Resume label colons ("**Skills:** …") are safe (colon immediately followed by `**`, not whitespace). **Reporting reminder:** "clean" means every check in Required Verification passed, never "reads well" — state which checks ran, don't imply more.

No semicolons anywhere in resumes or cover letters — same tell as the em dash, matches the standing rule already applied to `application_question_bank.md` answers. Hard-blocked as `LR-014`. Split into two sentences instead.

**Collaboration, not coercion.** Never frame Jason's cross-functional work as forcing, making, imposing, or driving other teams "into" a decision. Jason works through influence and alignment, not authority he doesn't have. Use "built alignment across," "brought teams to a shared order of priorities," "got everyone to commit to," "aligned X and Y on." Soft-flagged as `LW-010` (WARN — "force" has legitimate uses). Related tell: don't lean on "sequence" as the noun for a prioritized plan more than once in a letter — vary it ("plan," "order of priorities," "roadmap").

---

## Required Document Structure (frequently broken by non-Claude-Code agents)

A resume MUST contain these exact section headings, in this order, or it will fail `quality_checker.check_resume()`:

```
# [Name]
[contact line]

## PROFESSIONAL SUMMARY
**[Optional bolded positioning subtitle]**
[EXACTLY 3 sentences. Fewer fails R-010; more fails CW-013/R-012.]

## CORE COMPETENCIES
[optional — see below]

## PROFESSIONAL EXPERIENCE
### [Title] | [Company] | [Start] - [End]
[Location]
* [bullet]
...

## EDUCATION
[degree line]
```

- The heading must be literally `## PROFESSIONAL SUMMARY` — not a custom title line like `## PRODUCT MANAGER | Domain | B2B SaaS`. That exact substitution has happened before and silently fails `R-005`/`R-012`.
- **The optional bolded positioning subtitle must mirror the specific JD's own framing — never default to "B2B SaaS Platform Product Manager" (2026-07-21, Jason-supplied).** If the JD does not frame the role as B2B SaaS, don't lead the resume with it; it corners Jason into one positioning regardless of what the role actually wants. The subtitle is genuinely optional — when the JD's framing doesn't map to a crisp, honest positioning line, omit it entirely rather than reaching for the B2B SaaS default. It also must not overclaim: a "Data Enrichment" subtitle on an enrichment-PM role Jason is a transferable-skill fit for (not a literal match) is the same overclaim class as asserting a gap-domain as owned experience — found 2026-07-21 on the Relativity resume. **Mechanically enforced as `LR-031` (HARD_BLOCK, promoted from WARN `LW-013` on 2026-08-11):** if the Professional Summary (subtitle or body) contains "B2B SaaS" and `Original_JD.txt` never uses the word "SaaS", Mech fails. Experience bullets may still describe Cision as B2B SaaS when true; this gate is summary-only.
- **Mirror the JD's base role title when honest; never adopt its domain/industry qualifier unless genuinely backed by real experience (2026-08-05, Jason-supplied, per the planning doc's title-match research — exact title match measurably improves callback rates, so the base title is worth mirroring when true).** "Product Manager," "Product Owner," "Technical Product Manager" — whichever the JD literally uses — is fair to mirror if it honestly describes Jason's role. A domain qualifier is different: a JD titled "Product Manager, Insurance" does not license "Product Manager, Insurance" as the resume subtitle if Jason has no insurance background — that's the title-mirroring version of the same overclaim this section already guards against for "Data Enrichment" above. "Data-Enabled Product Manager" is fine specifically because data enablement is real and backed by bullets. Default to the bare base title, or an honestly-earned qualifier, never the JD's own domain word when that part isn't true.
- **The summary is exactly 3 sentences.** `SUMMARY_TEMPLATE_SENTENCES = 2` and `SUMMARY_MAX_PROOF_SENTENCES = 1` in `scripts/resume_conversion_eval.py` cap the mechanically-allowed metric-bearing sentences at one — but **the preferred, default shape is zero** (2026-07-19, Jason-supplied): a summary characterizes the professional — positioning, scope, how he works — it is not the place for achievements. Accomplishments belong in Professional Experience, where they're backed by a bullet, not asserted in prose. Only reach for the one allowed proof sentence if a specific role's summary genuinely needs it; don't treat it as the expected default shape. A 4th sentence fails `CW-013` ("stacks multiple proof sentences, reads like pasted bullet fragments") and `apply_claude_native_improvement` separately rejects any count != 3. This section previously said "3+ sentences," which is wrong and caused a real authoring failure on 2026-07-18 — corrected then. Get sentence-length variety *within* the 3 sentences rather than by adding a 4th. **Cross-functional framing in a summary**: say "cross-functionally" — don't recite the verified partner-team list from `workExperience.md` §2.2 in a characterization sentence; that list is for bullet-level evidence. Jason works cross-functionally across the organization, especially closely with engineering teams — not "embedded" (that reads as confined to engineering, undercutting the broader feature/product work he also owns; corrected 2026-07-19 same day it was first written) — see the "How to use this list" note in §2.2.
- `## CORE COMPETENCIES` is the one approved optional section beyond the three required ones (added by `build_skills_section`, `scripts/local_draft_stages.py`, FR-195 — confirmed 2026-07-18 to be deliberate, not drift: a JD-adaptive skills row sourced from selected claim tags plus a verified-tools row from `data/skills_catalog.json`, both passing through the same `BLOCKED_TOOLS` guard as the rest of the resume). Do not add any *other* undocumented section (`## CORE EXPERTISE`, `## TECHNICAL ENVIRONMENT`, etc.) — those aren't part of the approved template, and adding one is the single most common cause of resumes overflowing to 2 pages. Since there is still no automated page-count gate (see below), a JD with a long competency/tool match can push a resume to 2 pages even with only the approved sections present — check page count manually regardless.
- Most recent role: 5-6 bullets. Earlier roles: 2-3 bullets. All 3 canonical career history roles (Cision, Sterkly, Zero To Sixty) MUST be present (hard-blocked as `LR-020` and `LR-021` in `submission_linter.py`).
- **Lead with the number, don't bury it.** When a bullet has a hard metric, put it close to the verb rather than trailing at the end of a long clause (2026-07-21, Jason-supplied, Kintsugi review).
- **Ordering within a role's bullet list**: JD-relevance is the primary ordering signal for every role, Cision included (per the Cover Letter Proof-Point Selection section's same logic, applied here to bullets) — **reversed 2026-08-04**; a prior version hardcoded the Cision role's $40M ARR line first no matter the JD, Jason's explicit 2026-07-19 standing preference at the time. Re-reviewed during an audit pressure-test and reversed — Cision no longer gets a special-cased position. Among bullets of otherwise-comparable relevance to the JD, prefer the one carrying a hard metric. A bullet with no metric can still lead over a metric-bearing one if it is genuinely the single most JD-relevant bullet available (e.g. a compliance-heavy JD naming the compliance-workflow bullet ahead of a same-tier metric bullet) — this is a tiebreaker, not an override.

---

## Required Cover Letter Structure (added 2026-07-21 — found missing on 6 of 9 real submissions)

A cover letter MUST contain a name/contact header block before the greeting, and a sign-off phrase before the closing name, or it fails `quality_checker.check_and_repair_cover_letter()`:

```
# [Name]
[contact line]

Dear Hiring Manager,

[body paragraphs]

Best regards,

[Name]
```

This exact structure was missing on 6 of 9 real submissions in the 2026-07-20/21 batch — `check_and_repair_cover_letter()` already existed in `quality_checker.py` and auto-repairs both the missing header (`H-001`) and missing sign-off (`H-002`) in place, but nothing called it until it was added to Required Verification below. Don't assume `Cover_Letter_Reference.md`'s template alone guarantees this gets followed.

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
```

**No `Interview_Cheat_Sheet.md` at draft time** — generating Q&A prep for every submission regardless of whether it reaches an interview wastes tokens and implied web research this pipeline doesn't do. Generate it later, on demand, via `generate_cheat_sheet.py`, only once a real interview is actually scheduled for that company.

**If the job posting URL is known when `Original_JD.txt` is created, it MUST be the file's first line**, formatted exactly as `URL: <the url>`, followed by a blank line before the raw JD text starts. Not cosmetic: `reconcileOrphanSubmissionFolders()` reads this line to populate the `jobs.url` column when a folder gets linked to a DB row, and silently falls back to `null` if absent — there is no other mechanism that backfills it. If a submission is authored without a known URL (practice runs, a JD pasted with no source), leave the raw JD text as the first line as before; don't fabricate a placeholder URL.

To compile MD → PDF: `python scripts/compile_single.py <md_path> <pdf_path>`

---

## Required Verification Before You're Done

**Scope note:** this section applies in full to any resume/cover letter going into a real application. Archive-JD practice runs (offline authoring against `data/archive/submissions/*/Original_JD.txt` to sharpen the process) are exempt from the PDF-compile/page-count steps specifically — they stay `.md`-only in `data/authored_drafts/{company}/` and are never meant to reach the Applyr UI. The `generate-submission` skill's Stage 3 makes this distinction explicit; don't assume PDFs are optional for a real submission just because a recent practice run skipped them.

Never tell Jason a resume or cover letter is finished without running this from the repo root and confirming clean output:

```bash
# Canonical completion path (CR-076–084). Prefer this over hand-assembling workers.
# After docs land: --resume advances Stage 1 validate + Truth/ATS/HM/Mech/Policy
# (stops at WAITING_FOR_HUMAN for dispositions in reviews/dispositions.json).
# After Stage 2 COMPLETE: --finalize mints stage3 (production writes jobs DB).
python scripts/run_submission.py data/submissions/COMPANY
python scripts/run_submission.py data/submissions/COMPANY --resume
python scripts/run_submission.py data/submissions/COMPANY --status   # read-only
# Done means: workflow COMPLETE / COMPLETE_WITH_OVERRIDE (or PRACTICE_COMPLETE in practice),
# and check_workflow_complete prints YES for production COMPLETE*.

# Workers still exist for debug — the orchestrator already calls them. Do not treat the
# block below as an alternate "done" path that skips run_submission receipts:
#   python scripts/author_from_packet.py data/submissions/COMPANY --verify-only
#   python scripts/compile_single.py ... / verify_submission.py / coverage / jd_terms /
#   claim_provenance.py / verify_submission.py --audit
# If you must run workers by hand (debug), still finish with:
#   python scripts/run_submission.py data/submissions/COMPANY --resume
# so workflow_state + stage_receipts stay authoritative.
```

**Why the orchestrator, not five separate commands:** agents used to self-report stage completion (`verification_passed`, hand-assembled lint runs, skipped pair checks). `scripts/run_submission.py` + `scripts/workflow/` is the sole writer of workflow receipts; Mech (2D) still runs `verify_submission.py` underneath and writes `verification_receipt.json` as evidence. **The rubric score itself still cannot be mechanized** — enter `rubric_score` **and** `verification_passed: true` into `draft_manifest.json` by hand (shape: `rubric_score.{resume|cover_letter}.{total, breakdown}`), then `--resume` so Mech/Policy can clear `check_stage2_ready`. `--audit` (inside or via `verify_submission.py --audit`) catches byte-identical rubric sub-scores across different JDs against `data/.rubric_score_history.json`. If `--audit` flags a match, re-score both documents for real. **Both fields, not just `rubric_score`** (CR-092, 2026-08-15, found real: a manifest with `rubric_score` populated but `verification_passed` still `false` blocked `--finalize` on a fully-verified real submission — mechanically clean per `verify_submission.py` and `--audit`, just never marked so — because this line previously named only `rubric_score` explicitly and an agent reasonably inferred that was the whole requirement).

**`check_ground_truth_coverage.py` exists because the "ask whether ground truth was left unused" instruction below it in this same file was already written down once (after the Bazaarvoice dry run), and still recurred on a real 10-submission batch on 2026-07-31, caught by Jason, not by the prose.** It cross-references every claim's tags in `master_claims_tags_only.json` against the target JD and flags claims whose metrics/tags don't appear in the drafted documents. It's a heuristic — freshly-authored bullets won't always contain a tag's literal words, so it produces real false positives — check each `ATTENTION` flag against the actual document rather than blindly forcing every one in, but it must be run and its output actually read before a submission is called done.

**`claim_provenance.py` (CR-075) is the same WARN tier:** every drafted resume bullet / cover-letter proof point must cite at least one real, non-disabled Fact ID (`ACC-*`/`MET-*`/`VOC-*`). Findings never block `mechanically_verified` on their own — read them the same way you read coverage ATTENTION flags. Submissions authored after CR-075 emit `claim_provenance.json` at compose time; older folders correctly report the file missing until re-authored.

If any step fails or the resume is 2 pages, fix the content and re-run — do not hand back a "done" answer with a failing check.

---

## Cover Letter Proof-Point Selection

Choose each letter's proof points purely on fit to that letter's own JD — score against `data/conversion_rubric.md` C2 (Proof Density) and C3 (Role Fit Logic) for that document alone. Do not compare a letter to other companies' letters and do not edit one because it resembles another: each hiring manager only ever reads their own letter, so cross-letter similarity has no direct effect on whether any single letter converts. (Corrected 2026-07-07 — an earlier version framed cross-letter distinctiveness as a goal in itself, which led to reassigning proof points to look different rather than to fit better. A repeated skeleton across letters is usually a symptom the proof point was never actually chosen for the JD in front of it — investigate via C2/C3, not by optimizing distinctiveness directly.)

If two letters for different companies independently land on the same true accomplishment because it is genuinely the strongest fit for both JDs, that is correct — leave it alone. Only revisit reused phrasing if it fails C2/C3 for that letter on its own merits, or if the language itself is generic/AI-sounding within that one letter (a C4 Authenticity issue — see Forbidden Language below), not because it also appears elsewhere.

Keep cover letters 250-400 words, one page, opening with something specific to the company rather than generic enthusiasm (C1 Opening Hook). Avoid generic AI closers (e.g. "I would welcome the opportunity to speak with your team") when they read as filler for that letter — this is a per-letter authenticity check, not a batch-variety check.

**This covers sentence-level phrasing too, not just proof-point selection** (a 2026-07-16 correction to the 2026-07-07 note above, which didn't stop the same mistake recurring in a different form). A shared opening-hook structure or closing line across letters is not, by itself, a defect — no hiring manager reads two of Jason's letters side by side, so a shared closer carries zero real conversion risk. Before flagging anything spanning multiple submissions, ask: would this be noticeable to someone who only reads this one document? If answering requires comparing to another letter, it's out of scope. Judge each line only on whether it reads as generic or AI-sounding standing completely alone.

**Two compelling-ness anti-patterns, mechanically flagged:** the difference between a letter that's merely *clean* (no tells) and one that's actually *compelling*. Both WARN, not hard block — both need a judgment call, but the flag forces it.
- **`LW-011` — JD-paraphrase hook.** The opening paragraph must not read the posting's own prose back to the reader. Mechanically: 6+ verbatim word sequences shared with `Original_JD.txt` means parroting. Naming the role/team is fine; mirroring the JD's sentences signals nothing. Open with a specific observation or insight instead.
- **`LW-012` — assertion-of-fit overclaim.** "maps directly," "exact fit," "the exact shape of," "perfectly suited," "uniquely qualified." These assert fit instead of demonstrating it, and in practice paper over a real gap. When one fires: if the fit is real, show it with a specific fact; if it's a stretch, name the honest transferable bridge instead of asserting a direct match.

Neither makes a letter compelling on its own — they raise the floor. Whether a hook shows genuine *insight* versus competent paraphrase is the judgment a mechanical check can't make; that still needs a real read.

**Gap-confession language is hard-blocked (`LR-016`).** The letter's job is to argue why Jason is a fit, never to acknowledge where he isn't. Cut the confession clause, keep only the positive claim — a prose instruction alone didn't survive drafting pressure (violated in 5 of 11 real letters the same week it was written: "is new territory for me," "I have not yet applied that thinking," "are new to me"), hence hard-coding it. Narrow exception: a single, plain, factual disclosure of a genuinely unbridgeable hard constraint (e.g. a travel ceiling) uses different, non-confessional phrasing and doesn't trip this rule.

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

**Conversion thresholds — a floor, not a stop signal (Round 4 optimization bar — hard):**
- Resume: 70+ = CONVERT-READY floor
- Cover Letter: 65+ = CONVERT-READY floor

These numbers were previously read as "stop improving once reached" — that produced real submissions that barely cleared threshold with real, available ground truth sitting unused (found 2026-07-21: the Bazaarvoice dry run scored 73/100, with MET-09's SQL-database footprint and ACC-117's Pendo analytics work both real, both relevant to explicitly required JD items, and neither used). **"Done" is not "clears the number." Done is: every required JD item and every Stage 0 soft gap / domain soft stretch is engaged with the single strongest available piece of ground truth for it (the packet's mapped soft_gap claim_ids), not merely an adequate proxy, and nothing genuinely usable for that item was left on the table.** Hard gaps stay Skip / never claimed as owned. This is fail-closed at Stage 1: `author_from_packet.py --verify-only` fails when soft_gap or required evidence_map claim_ids are unused in `claim_provenance.json`. Do not pad, stretch a claim, or force in extra content just to raise a score; the failure mode being corrected is *unused* evidence, not *insufficient volume*. If the strongest available evidence is already in the document, stop — that is done, whatever the score reads. Chasing points above what real ground truth supports is still wrong.

---

## Exclusion Zones — What Jason Is NOT

- Not a 0-to-1 greenfield PM
- Not an AI/ML product lead
- Not a people manager
- Not a revenue/billing/payments owner

If a job description requires any of the above as a hard requirement, flag it rather than trying to paper over the gap.
