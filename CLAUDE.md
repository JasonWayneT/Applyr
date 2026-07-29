# Applyr — Agent Context Map

This file is the tool-agnostic counterpart to `CLAUDE.md` (Claude Code reads that one automatically; most other coding agents — Gemini, Cursor, Antigravity, etc. — read this one instead). The content is the same. If you are an LLM editing this repository, these rules are not suggestions: they protect a real candidate's job search from false claims and broken output.

**Keep `CLAUDE.md` and `AGENTS.md` byte-identical.** Whichever file you edit, copy the same change into the other one before you finish the task — do not let them drift again. They went out of sync once already (CLAUDE.md was missing six whole sections as of 2026-07-06, until it was resynced from this file) simply because one file kept getting updated and the other didn't. There is no automated check for this; it's on you to do it manually every time.

If you only do one thing before touching `data/submissions/`, do this: **run the verification commands in "Required Verification Before You're Done" below.** Do not consider a resume or cover letter finished until those commands pass clean.

**Trigger phrase binding:** when Jason says a resume/cover letter should be "conversion ready," "apply ready," "ready to send," or asks you to "review" or "check" one — that always means running the full three-pass workflow in [.claude/skills/conversion-ready-pass/SKILL.md](.claude/skills/conversion-ready-pass/SKILL.md): rubric scoring against `data/conversion_rubric.md` (R1–R8 resume / C1–C5 cover letter), a mechanical truth-grounding sweep, and a qualitative hiring-manager read, looped up to 3 rounds. That file is plain markdown with no Claude-Code-specific mechanism required to use it — if you are a different coding agent and have no automatic skill-loading step, open and follow it directly rather than stopping at the rubric. He should not have to name these files or re-link the research report each time. Don't just eyeball a document for typos and call it done, and don't stop after the rubric score alone — that is Pass 1 of three, not the whole workflow. **Scoping note (2026-07-19):** for a document authored via the `generate-submission` skill, its own Stage 2 already satisfies this trigger — don't run `conversion-ready-pass` a second time on top of it. `conversion-ready-pass` is for checking a document *not* produced by that flow.

**Processing job descriptions today?** Invoke the `generate-submission` skill (`.claude/skills/generate-submission/SKILL.md`) — the single operational entry point for JD triage (fit-gating before any drafting), direct authoring, and verification. It's the current authoritative process, not the CR-070 tracker referenced below (superseded for generation — see the note just below).

---

## Active Engineering Work — Read This First If You're Here to Build, Not Draft

> **START HERE (2026-07-20):
> [SESSION-HANDOFF-2026-07-20-process-hardening.md](docs/spec/08-implementation/SESSION-HANDOFF-2026-07-20-process-hardening.md)**
> — supersedes the 2026-07-18 handoff below as the active thread. The direct-authoring pivot from 07-18
> is done and stable; this doc covers what happened when the resulting process (`.claude/skills/generate-submission/SKILL.md`
> v2.0.0 — the actual authoritative Stage 0-3 process, read it in full) ran against real JDs for the
> first time, in two harnesses, and the self-repair fixes that came out of it: a database check so
> Stage 0 never drafts for a company already marked Rejected/Closed, a mechanical check for resume↔letter
> restatement the rubric couldn't see, and the standing rule that cover letters argue fit rather than
> confess gaps. Six of nine real submissions from that batch are verified clean and ready to apply;
> three are blocked on a database-status decision only Jason can make. The 07-18 handoff below is kept
> for the original pivot's history, not as a second active thread.

The CR-070 epics below are largely complete and are kept for reference. There are three
previously-active engineering threads:

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

This workspace is configured for a **B2B SaaS Platform PM** with 7 years of experience.
To protect candidate privacy:
- All real contact details (PII) are stored locally in the gitignored `data/workExperience.md` (Section 1.0) and inside the gitignored SQLite database `jobagent.sqlite`.
- Do NOT write or commit real names, emails, phone numbers, or LinkedIn URLs to tracked Git files.

---

## File Map — Read These Before Writing Anything

| File | Purpose | Read When |
|------|---------|-----------|
| `data/agent_context_pack.md` | **Generated fast-path digest** of this file's operative sections + `generate-submission/SKILL.md`'s operative sections + `workExperience.md` + `conversion_rubric.md`, built by `scripts/generate_context_pack.py` so a drafting/reviewing agent reads one lean file instead of four full ones (~19% smaller than the sum of sources; excludes engineering-only content this file carries that a drafting agent never needs). **Verify freshness first** — `python scripts/check_context_pack_freshness.py` must print FRESH; if STALE, regenerate before relying on it. Not a replacement for this file when doing engineering/process work — see below. | Before drafting or reviewing any submission, instead of separately reading this file + SKILL.md + workExperience.md + conversion_rubric.md |
| `data/workExperience.md` | **Ground truth.** Every metric, accomplishment, and claim must trace back here. Contains VOC codes (vocabulary translation), MET codes (verified metrics), ACC codes (approved accomplishments), and explicit DO NOT CLAIM lists. | Before writing any bullet, proof paragraph, or metric |
| `data/master_claims.json` | Structured claim catalog. 59+ active claims. Claims with `"disabled": true` are quarantined and must NOT be used. **Read `tags` only as a retrieval index into `workExperience.md`'s full stories** — `text` and especially `cover_story` (a full first-person cover-letter-register paragraph per claim) are legacy write-only artifacts from the retired deterministic pipeline; never place either directly in an output document. | When selecting proof points for cover letters |
| `data/master_claims_tags_only.json` | Generated sidecar of the above with `text`/`cover_story` already stripped from every claim by construction (`scripts/generate_context_pack.py`) — makes "tags only" true by construction instead of relying on every agent to self-police it. Regenerated alongside `agent_context_pack.md`. | Same as `master_claims.json` above — prefer this file when it exists |
| `data/conversion_rubric.md` | Scoring rubric R1–R8 (resume) and C1–C5 (cover letter). **Thresholds: Resume 70+ = CONVERT-READY, Cover Letter 65+ = CONVERT-READY.** Do not chase points above threshold. | When evaluating or scoring a submission — this is the actionable day-to-day tool |
| `data/pm_resume_cover_letter_research_report.md` | Background research the rubric above was built from (same heuristics, cited evidence, narrative form). Not a scoring tool itself. | Only when you need the reasoning behind a specific rubric criterion, or when revising the rubric itself |
| `data/candidate_preferences.json` | Filter preferences: no solo/founding PM roles, no 0-to-1, min fit score 72. | When evaluating job fit |
| `data/Cover_Letter_Reference.md` | Cover letter structural reference | When drafting cover letters |
| `data/external_resume_patterns.md` | Third-party PM resume examples (Enhancv), paraphrased — cross-cutting summary/bullet patterns plus per-example notes. Reference only, never a template; don't copy phrasing verbatim. | When working on summary wording specifically, or wanting an outside comparison point before calling a draft done |
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
| MET-05 | Infrastructure savings (Cision) | ~$2M cumulative |
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
- ACC-120: AI content-generation system — adjacent exposure & joint prompt-engineering research with the PM who built it (added 2026-07-21). **CONTRIBUTED at most, for the joint research only** — Jason did not build, design, or own this system. Never say "I built" or "I designed" about it. Distinct from his own personal AI-tooling project (ACC-401-AITOOLS, `data/aiProjects.md` — six named side projects with real what/why/how/tech detail, a much stronger source for AI-fluency content than the thin "I use Claude and Gemini daily" line that had been recurring).

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

**Cover letters: don't discuss workforce reduction at all, not even via the euphemism (2026-07-21, Jason-supplied, Glint Tech review).** This is stronger than R-011's substitution rule above. R-011 governs word choice everywhere; this is a cover-letter-specific scope rule: don't build any part of a cover letter's argument around headcount shrinking, executive turnover as adversity, or "operating through constraint" framed via team size — not even using an approved euphemism like "resource-constrained cycle." Found running through all three paragraphs of a real letter ("repeated rounds of headcount reduction," "a shrinking engineering bench," "even as the team itself was shrinking") on 2026-07-21. The resume can still reference resource constraints factually where relevant (workExperience.md's own role context does); this rule is about what a cover letter chooses to argue from, not about erasing the fact.

---

## Forbidden Language (Anti-AI Fingerprint)

Never use: em dashes (—), double-hyphen (`--`), "leverage," "passionate," "driven," "dynamic," "innovative," "seamless," "transformative," "synergy," "tapestry," "revolutionize," "revenue-bearing" (added 2026-07-19 — Jason's own correction: he's never heard the phrase and it isn't how he speaks; it had leaked from `workExperience.md`'s own positioning line into an authored resume), "proven track record," "I am excited to apply," "I am excited about," "I am confident that," "Furthermore," "Moreover," "In addition," "Additionally."

The fuller, actively-maintained list (CR-070 Epic 8 authenticity research + Jason's own `voice-rewrite` skill's Pass 1 strip list) lives in `scripts/submission_linter.py`'s `LR-009`/`LW-006`/`LW-007` rules — that's the single source of truth going forward (per CR-070 Epic 9's decision not to hand-duplicate a growing word list in two places); this section stays as the always-hard-blocked core, not the exhaustive set.

**`no-ai-slop` skill integration (2026-07-23, Jason-supplied).** Jason also uses a general-purpose writing skill, [petergyang/no-ai-slop](https://github.com/petergyang/no-ai-slop), installed globally at `~/.claude/skills/no-ai-slop` for any draft, not Applyr-specific. Rather than keep a second parallel word list, its pattern catalog was diffed against the existing `LR`/`LW` rules and the genuine gaps were added as new mechanical `WARN` rules in `submission_linter.py`: `LW-015` (throat-clearing openers — "Here's the thing," "Let me be clear"), `LW-016` (faux-insight/rhetorical setups — "what nobody tells you," "what if I told you"), `LW-017` (importance puffery — "marks a pivotal moment," "a testament to"), `LW-018` (weasel attribution — "experts agree," "studies show"), `LW-019` (fake-strong hub-verb — "serves as a centralized hub"), and `LW-020` (the "It's not X. It's Y." binary-contrast two-sentence shape). `LW-007` was also widened to catch "Ultimately,"/"Overall," as summary-recap sentence-starters (comma-gated so mid-sentence uses like "ultimately responsible for" don't false-positive). Patterns from that skill's list left out as impractical to regex reliably or low-relevance to a 250-400 word professional document (negative listing, dramatic fragmentation, synonym cycling, robotic rhythm, fake-profound kickers, formatting slop) — ask Jason before adding a mechanical rule for any of these; a human read still catches them fine. `submission_linter.py` remains the single source of truth per the paragraph above — this integration extends it rather than starting a second list.

Never open a sentence with transition fluff. Never start a cover letter with "I am writing to express my interest."

No bullet points in cover letters. No em dashes anywhere — including as a stand-in punctuation pattern like `word: word` used to avoid the literal character. If you find yourself writing a colon where an em dash would have gone, restructure the sentence instead; the colon-as-em-dash-substitute pattern is itself a tell. **This is now mechanically enforced as `LR-015` (HARD_BLOCK) in `submission_linter.py`** (added 2026-07-21, Jason-supplied, Stripe review): a colon followed by whitespace then a letter ("compelling: building", "context: how", "work: I built"). It had been named as a tell here for weeks but nothing checked for it — em-dashes (`LR-006`) and semicolons (`LR-014`) were enforced, the colon was not, so it slipped through every "clean" verification and turned up in 7 of 9 real cover letters. Resume label colons ("**Skills:** …") are safe (colon immediately followed by `**`, not whitespace). Reporting reminder that came out of the same miss: **"clean" means "every check in Required Verification passed," never "reads well" — state which checks ran, don't imply more.**

No semicolons anywhere in resumes or cover letters (added 2026-07-21, Jason-supplied — same tell as the em dash, reads as AI-prose rather than how Jason writes; matches the standing rule already applied to `application_question_bank.md` answers). Hard-blocked as `LR-014` in `submission_linter.py`. Split into two sentences instead.

**Collaboration, not coercion (2026-07-21, Jason-supplied).** Never frame Jason's cross-functional work as forcing, making, imposing, or driving other teams "into" a decision ("forced Sales, Legal, DevOps, and engineering into one sequence"). Jason works through influence and alignment, not authority he does not have — this framing is both inaccurate and off-voice. Use "built alignment across," "brought teams to a shared order of priorities," "got everyone to commit to," "aligned X and Y on." Soft-flagged as `LW-010` (WARN, not hard-block — "force" has legitimate uses) in `submission_linter.py`. This appeared in multiple 2026-07-21 cover letters (Nelnet, Principal) framing his quarterly prioritization as coercion. Related word-repetition tell caught the same day: don't lean on "sequence" as the noun for a prioritized plan more than once in a letter — vary it ("plan," "order of priorities," "roadmap").

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
- **The optional bolded positioning subtitle must mirror the specific JD's own framing — never default to "B2B SaaS Platform Product Manager" (2026-07-21, Jason-supplied).** If the JD does not frame the role as B2B SaaS, don't lead the resume with it; it corners Jason into one positioning regardless of what the role actually wants. The subtitle is genuinely optional — when the JD's framing doesn't map to a crisp, honest positioning line, omit it entirely rather than reaching for the B2B SaaS default. It also must not overclaim: a "Data Enrichment" subtitle on an enrichment-PM role Jason is a transferable-skill fit for (not a literal match) is the same overclaim class as asserting a gap-domain as owned experience — found 2026-07-21 on the Relativity resume.
- **The summary is exactly 3 sentences.** `SUMMARY_TEMPLATE_SENTENCES = 2` and `SUMMARY_MAX_PROOF_SENTENCES = 1` in `scripts/resume_conversion_eval.py` cap the mechanically-allowed metric-bearing sentences at one — but **the preferred, default shape is zero** (2026-07-19, Jason-supplied): a summary characterizes the professional — positioning, scope, how he works — it is not the place for achievements. Accomplishments belong in Professional Experience, where they're backed by a bullet, not asserted in prose. Only reach for the one allowed proof sentence if a specific role's summary genuinely needs it; don't treat it as the expected default shape. A 4th sentence fails `CW-013` ("stacks multiple proof sentences, reads like pasted bullet fragments") and `apply_claude_native_improvement` separately rejects any count != 3. This section previously said "3+ sentences," which is wrong and caused a real authoring failure on 2026-07-18 — corrected then. Get sentence-length variety *within* the 3 sentences rather than by adding a 4th. **Cross-functional framing in a summary**: say "cross-functionally" — don't recite the verified partner-team list from `workExperience.md` §2.2 in a characterization sentence; that list is for bullet-level evidence. Jason works cross-functionally across the organization, especially closely with engineering teams — not "embedded" (that reads as confined to engineering, undercutting the broader feature/product work he also owns; corrected 2026-07-19 same day it was first written) — see the "How to use this list" note in §2.2.
- `## CORE COMPETENCIES` is the one approved optional section beyond the three required ones (added by `build_skills_section`, `scripts/local_draft_stages.py`, FR-195 — confirmed 2026-07-18 to be deliberate, not drift: a JD-adaptive skills row sourced from selected claim tags plus a verified-tools row from `data/skills_catalog.json`, both passing through the same `BLOCKED_TOOLS` guard as the rest of the resume). Do not add any *other* undocumented section (`## CORE EXPERTISE`, `## TECHNICAL ENVIRONMENT`, etc.) — those aren't part of the approved template, and adding one is the single most common cause of resumes overflowing to 2 pages. Since there is still no automated page-count gate (see below), a JD with a long competency/tool match can push a resume to 2 pages even with only the approved sections present — check page count manually regardless.
- Most recent role: 5-6 bullets. Earlier roles: 2-3 bullets. All 3 canonical career history roles (Cision, Sterkly, Zero To Sixty) MUST be present (hard-blocked as `LR-020` and `LR-021` in `submission_linter.py`).
- **Lead with the number, don't bury it.** When a bullet has a hard metric, put it close to the verb rather than trailing at the end of a long clause (2026-07-21, Jason-supplied, Kintsugi review).
- **Ordering within a role's bullet list**: JD-relevance is still the primary ordering signal (per the Cover Letter Proof-Point Selection section's same logic, applied here to bullets) — the Cision role's first bullet is always the $40M ARR line regardless. Among bullets of otherwise-comparable relevance to the JD, prefer the one carrying a hard metric. A bullet with no metric can still lead over a metric-bearing one if it is genuinely the single most JD-relevant bullet available (e.g. a compliance-heavy JD naming the compliance-workflow bullet ahead of a same-tier metric bullet) — this is a tiebreaker, not an override.

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

This exact structure is missing on 6 of 9 real submissions from the 2026-07-20/21 batch (Principal, Relativity, Nelnet, Kintsugi, Monks, Stripe) — `check_and_repair_cover_letter()` already existed in `quality_checker.py` and already auto-repairs both the missing header (`H-001`) and the missing sign-off (`H-002`, added 2026-07-21) in place, but nothing in the process ever called it until it was added to Required Verification below. Don't assume `Cover_Letter_Reference.md`'s template alone guarantees this gets followed — it didn't, in practice, across two-thirds of a real batch.

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

**No `Interview_Cheat_Sheet.md` at draft time** (removed 2026-07-23, Jason-supplied) — generating Q&A prep for every submission regardless of whether it reaches an interview wastes tokens and implied web research this pipeline doesn't do. Generate it later, on demand, via `generate_cheat_sheet.py`, only once a real interview is actually scheduled for that company.

**If the job posting URL is known when `Original_JD.txt` is created, it MUST be the file's first line, formatted exactly as `URL: <the url>`, followed by a blank line before the raw JD text starts** (added 2026-07-24, Jason-supplied, after a full 13-submission batch went into the `jobs` database with `url` left `NULL` on every row — the parsing logic for this exact line already existed in `server/submissionFolders.ts`'s `readJdMeta()`, it just had never once been fed a file that used it). This is not cosmetic: `reconcileOrphanSubmissionFolders()` reads this line to populate the `jobs.url` column when a folder gets linked to a DB row, and it silently falls back to `null` if the line is absent — there is no other mechanism that backfills it. If a submission is authored without a known URL (e.g., practice runs, or a JD pasted with no source), leave the raw JD text as the first line exactly as before; do not fabricate a placeholder URL.

To compile MD → PDF: `python scripts/compile_single.py <md_path> <pdf_path>`

---

## Required Verification Before You're Done

**Scope note:** this section applies in full to any resume/cover letter going into a real application. Archive-JD practice runs (offline authoring against `data/archive/submissions/*/Original_JD.txt` to sharpen the process) are exempt from the PDF-compile/page-count steps specifically — they stay `.md`-only in `data/authored_drafts/{company}/` and are never meant to reach the Applyr UI. The `generate-submission` skill's Stage 3 makes this distinction explicit; don't assume PDFs are optional for a real submission just because a recent practice run skipped them.

Never tell Jason a resume or cover letter is finished without running this from the repo root and confirming clean output:

```bash
# 1. Compile to PDF first -- verify_submission.py reads the PDFs for page counts.
python scripts/compile_single.py data/submissions/COMPANY/Resume.md data/submissions/COMPANY/Resume.pdf
python scripts/compile_single.py data/submissions/COMPANY/CoverLetter.md data/submissions/COMPANY/CoverLetter.pdf

# 2. One required verification command -- lint (both documents plus the resume/cover-letter
#    pair checks), resume structure/QA, cover-letter structure/QA (auto-repairs H-001/H-002 in
#    place -- if it reports a repair, recompile the PDFs and re-run this), the unapproved-metrics
#    sweep, and page counts, all in one script, writing verification_receipt.json into the folder.
python scripts/verify_submission.py data/submissions/COMPANY

# 3. After Stage 2's rubric_score is hand-scored into draft_manifest.json (see generate-submission
#    SKILL.md Stage 2 point 1 -- a script cannot assign this, it requires an actual read against
#    conversion_rubric.md with cited evidence per criterion), audit it against every other
#    submission's score, past and present, for the templating failure mode below.
python scripts/verify_submission.py --audit data/submissions/COMPANY
```

**Why one script, not five separate commands (rewritten 2026-07-23):** this section and `generate-submission/SKILL.md`'s own Stage 2 code sample had already drifted from each other twice (2026-07-20, missing the pair-check requirement; 2026-07-21, missing the cover-letter check) before a cross-harness session found the sharper version of the same problem — a harness ran the lint check on the cover letter only, saved that single result as `lint_report.json`, and the resume's lint check silently never ran at all. Two descriptions of the same requirement, however carefully worded, can still drift or get partially followed. `scripts/verify_submission.py` is the one command every harness runs, producing one receipt file instead of a self-report. **The rubric score itself still cannot be mechanized** — `--audit` doesn't verify judgment quality, it catches the one failure mode a script actually can catch: byte-identical rubric sub-scores across different JDs, checked against a persistent cross-session log at `data/.rubric_score_history.json`. Found real 2026-07-23: 8 submissions in one batch had identical resume (94/100) and cover-letter (100/100) sub-scores down to the sub-criterion, across 8 unrelated companies -- a templated pass presented as a genuine one. If `--audit` flags a match, re-score both documents for real; don't dismiss the warning as a false positive without actually re-reading the flagged pair.

If any step fails or the resume is 2 pages, fix the content and re-run — do not hand back a "done" answer with a failing check.

---

## Cover Letter Proof-Point Selection

Choose each letter's proof points purely on fit to that letter's own JD — score against `data/conversion_rubric.md` C2 (Proof Density) and C3 (Role Fit Logic) for that document alone. Do not compare a letter to other companies' letters and do not edit one because it resembles another: each hiring manager only ever reads their own letter, so cross-letter similarity has no direct effect on whether any single letter converts. (Corrected 2026-07-07 — an earlier version of this section framed cross-letter distinctiveness as a goal in itself, which led to reassigning proof points to make letters look different rather than to make them fit better. In practice the two often point the same direction, since a repeated skeleton across many letters is usually a symptom that the proof point was never actually chosen for the JD in front of it. Treat it as exactly that: a symptom to investigate via C2/C3, not a target to optimize directly.)

If two letters for different companies independently land on the same true accomplishment because it is genuinely the strongest fit for both JDs, that is correct — leave it alone. Only revisit reused phrasing if it fails C2/C3 for that letter on its own merits, or if the language itself is generic/AI-sounding within that one letter (a C4 Authenticity issue — see Forbidden Language below), not because it also appears elsewhere.

Keep cover letters 250-400 words, one page, opening with something specific to the company rather than generic enthusiasm (C1 Opening Hook). Avoid generic AI closers (e.g. "I would welcome the opportunity to speak with your team") when they read as filler for that letter — this is a per-letter authenticity check, not a batch-variety check.

**This covers sentence-level phrasing too, not just proof-point selection** (corrected again 2026-07-16 — the 2026-07-07 correction above didn't stop the same mistake from recurring in a different form). Finding that several cover letters share a similar opening-hook structure or closing line is not, by itself, a defect. No hiring manager reads two of Jason's letters side by side, so a shared closer like "I would welcome a conversation about how this maps to X" across many companies carries zero real conversion risk — it is invisible to every actual reader. Before flagging or rewriting anything that spans multiple submissions, ask: would this be noticeable to someone who only ever reads this one document? If answering requires comparing it to another company's letter, it is out of scope — do not raise it, not even as a secondary point stacked alongside a real single-letter issue. Judge each line only on whether it reads as generic or AI-sounding standing completely alone.

**Two compelling-ness anti-patterns, now mechanically flagged (added 2026-07-21, Jason-supplied):** These are the difference between a letter that is merely *clean* (no tells) and one that is actually *compelling*. Both are WARNs, not hard blocks, because both need a judgment call — but the flag forces the call.
- **`LW-011` — JD-paraphrase hook.** The opening paragraph must not read the posting's own descriptive prose back to the reader. Mechanically: if the hook shares 6+ word verbatim sequences with `Original_JD.txt`, it is parroting. Naming the role/team is fine; mirroring the JD's sentences signals nothing to the person who wrote them. Open with a specific observation or insight about the company's problem instead.
- **`LW-012` — assertion-of-fit overclaim.** "maps directly," "exact fit," "the exact shape of," "perfectly suited," "uniquely qualified," etc. These assert a fit instead of demonstrating it, and in practice they paper over a real gap (Stripe's "maps directly" to an API-primitives role, Relativity's "exact shape of" an enrichment role). When one fires, check the underlying claim: if the fit is real, show it with a specific fact; if it is a stretch, name the honest transferable bridge instead of asserting a direct match.

Neither check makes a letter compelling on its own — they raise the floor by killing the two most common ways a letter reads as competent-but-generic. Whether a hook shows genuine *insight* (versus competent paraphrase that happens to share no 6-word runs) is the irreducible judgment a mechanical check cannot make; that still needs a real read.

**Gap-confession language is now hard-blocked, not just a prose rule (`LR-016`, added 2026-07-21, Jason-supplied).** The letter's job is to stress why Jason is a fit, never to acknowledge where he isn't — a rule already stated in the `generate-submission` skill, and one that still got violated in 5 of 11 real letters the same week it was written ("is new territory for me," "I have not yet applied that thinking," "are new to me"), each time as a lead-in to a transferable-skill pivot that should have stood on its own. A prose instruction alone did not survive drafting pressure, hence hard-coding it: cut the confession clause, keep only the positive claim. The narrow exception — a single, plain, factual disclosure of a genuinely unbridgeable hard constraint (e.g. the 15% travel ceiling) — uses different, non-confessional phrasing and does not trip this rule.

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

**Conversion thresholds — a floor, not a stop signal (revised 2026-07-21, Jason-supplied):**
- Resume: 70+ = CONVERT-READY
- Cover Letter: 65+ = CONVERT-READY

These numbers were previously read as "stop improving once reached" — that produced real submissions that barely cleared threshold with real, available ground truth sitting unused (found 2026-07-21: the Bazaarvoice dry run scored 73/100, and an independent reviewer found MET-09's SQL-database footprint and ACC-117's Pendo analytics work were both real, both relevant to explicitly required JD items, and neither made it into the document). **"Done" is not "clears the number." Done is: every required JD item is engaged with the single strongest available piece of ground truth for it, not merely an adequate one, and nothing genuinely usable was left on the table.** This is a real bar, not a bigger number to chase — do not pad, stretch a claim, or force in extra content just to raise a score; the failure mode this is correcting is *unused* evidence, not *insufficient volume* of evidence. If the strongest available evidence is already in the document, stop — that is done, whatever the score reads. Chasing points for their own sake above what real ground truth supports is still wrong.

---

## Exclusion Zones — What Jason Is NOT

- Not a 0-to-1 greenfield PM
- Not an AI/ML product lead
- Not a people manager
- Not a revenue/billing/payments owner

If a job description requires any of the above as a hard requirement, flag it rather than trying to paper over the gap.
