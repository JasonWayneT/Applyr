# SESSION HANDOFF — 2026-07-28 — Tier 1 + Tier 2 batch complete, handed to Antigravity/Cursor

**Purpose of this doc:** Claude Code drafted and verified 8 real submissions this session and is now at its session limit. This is a cross-harness handoff so Antigravity or Cursor can pick up cleanly — both the current state and Jason's standing quality bar for this pipeline, restated here because he raised it explicitly when asking for this handoff.

## Jason's standing quality bar (not new, but he wants it held explicitly)

Every resume and cover letter in this pipeline has to survive real hiring-manager scrutiny, not just clear the mechanical checks. Three things that means in practice:

1. **Only claims grounded in verified experience.** Every fact traces back to `data/workExperience.md` or `data/master_claims_tags_only.json`'s `tags` field (never `text`/`cover_story` — those are legacy write-only artifacts, not sentences to reuse). If a claim doesn't trace back, it doesn't go in the document, full stop — no stretching, no "familiar with."
2. **Search the complete experience, not a shortcut set.** Before defaulting to the same handful of go-to accomplishments, check whether a JD's specific ask is better matched by something else in ground truth. Several submissions this session scored lower on JD-keyword alignment specifically because a real, relevant piece of evidence existed but hadn't made it into the first draft — caught at Stage 2's required-item fidelity check, not before. Don't skip that check.
3. **Read as human-written.** The forbidden-language list, rubric C4 (Authenticity), and the `no-ai-slop` integration in `scripts/submission_linter.py` exist for exactly this. Hold the line on all of them — no em dashes, no semicolons, no colon-as-elaboration, no gap-confession language, no generic AI closers.

## Instructions for the agent picking this up

1. Read `AGENTS.md` at the repo root first — byte-identical to `CLAUDE.md`, the ground-truth rules doc (anti-hallucination rules, forbidden language, exact document structure, Required Verification commands).
2. Read `data/workExperience.md` (ground truth) and `data/master_claims_tags_only.json` (tags only).
3. Read and follow `.claude/skills/generate-submission/SKILL.md` directly, in full, as plain instructions — there is no automatic skill-loading step in these harnesses, so this file will not surface on its own. It is the authoritative Stage 0/1/2/3 process.
4. Also read `data/agent_context_pack.md` if it prints FRESH from `python scripts/check_context_pack_freshness.py` (Windows: use the venv python below) — a lean digest of the same rules, but not a replacement when doing process/engineering work.
5. **Environment gotcha that cost real time this session**: all Python scripts must run through the project's venv, not system Python — `.venv/Scripts/python.exe scripts/whatever.py` (Windows). Plain `python` resolves to the wrong interpreter here and fails immediately with a CRITICAL error.
6. **Do not skip `verify_submission.py` + `--audit`.** Both must exit clean before anything is reported done. Hand-score the rubric with a one-line evidence citation per criterion — never a plausible-looking number typed into `draft_manifest.json` without doing the read.
7. Folder-naming note: `data/submissions/` currently mixes PascalCase (`Yext`, `BenefitHub`, `LTK`, `Runpod`) and lowercase-underscore (`avenue_code`, `exl`, `the_judge_group`, `union_home_mortgage_corp`) slugs — this predates this session (older folders like `elation_health`, `evlo_ai`, `limble` already existed both ways). Not something to normalize unprompted; just don't assume one convention and accidentally create a duplicate folder for an existing company under a different casing.

## What's done this session — 8 companies, all verified clean, all `Drafted` in the DB

Every row below passed `verify_submission.py` and `--audit` clean, has a 1-page Resume.pdf and a compiled CoverLetter.pdf, and has its `jobs` table row already updated from `New` to `Drafted`. Nothing further needed on these unless Jason asks for a revision.

| Company | Folder | Resume | Letter | Fit note |
|---|---|---|---|---|
| BenefitHub | `data/submissions/BenefitHub/` | 74 | 91 | Clean Tier 1, tagged **Reach Out** (browser-extension work directly echoes Jason's Sterkly background) |
| Runpod | `data/submissions/Runpod/` | 80 | 91 | Tier 2, genuine stretch (AI-infra/GTM-heavy role vs. Jason's platform-stability background) — flagged for Jason to eyeball before sending |
| LTK | `data/submissions/LTK/` | 79 | 90 | Tier 2 — prior LTK rows in the DB are Closed; Jason explicitly approved re-engaging with this distinct req |
| Union Home Mortgage Corp. | `data/submissions/union_home_mortgage_corp/` | 78 | 85 | Tier 2 — **JD never states remote/hybrid/onsite**, see open item below |
| Yext | `data/submissions/Yext/` | 77 | 84 | PASS but low-confidence — scraped JD is almost entirely boilerplate, no real Requirements section |
| The Judge Group | `data/submissions/the_judge_group/` | 77 | 88 | Tier 2, contract role via staffing firm |
| Avenue Code | `data/submissions/avenue_code/` | 74 | 88 | Tier 2 — no retail/POS background, bridged via Cision's liaison/ticket-triage work |
| EXL | `data/submissions/exl/` | 84 | 88 | Tier 2 — real title is a junior/support-level role (Sr. Associate reporting to a Sr. Lead), written honestly rather than as peer-level |

## Skipped this session

**Raptive** (PM, Ad Code) — never imported or drafted. `data/candidate_preferences.json`'s `blocked_industries` hard-blocks "Ad Tech," and Raptive's role is squarely header-bidding/auction-code work. Would auto-reject at Stage 0 anyway.

## Open items for you to pick up

1. **BenefitHub LinkedIn outreach.** Reach-Out-tagged, but the connect message hasn't been drafted — Jason needs a hiring manager's name first. Once he has one, draft a short, text-style message (not cover-letter register) per SKILL.md Stage 3's outreach guidance.
2. **Union Home Mortgage remote status.** The JD is completely silent on remote/hybrid/onsite and the company is Ohio-based. Flag to Jason to confirm directly before he invests further — don't guess.
3. **Tier 3 companies — not yet imported into the DB, ask Jason before touching.** From an earlier manual tiering pass in this session's parent conversation, three companies were named "long shot" and never entered into Applyr at all: SciSure (Product Owner title, biosafety/life-sciences domain lock), Machinify (Senior PM, healthcare + AI/ML technical bar), Motion Recruitment/Intuit contract (Sr PM, wants 10+ years — above Jason's ~7). These aren't in `jobagent.sqlite` yet. Don't import or draft them without Jason explicitly asking — they were tiered low for real reasons, not just deprioritized.
4. **Process cleanup, not blocking.** `master_claims_tags_only.json` has claim IDs `ACC-111`, `ACC-113`, `ACC-115` with tags but no backing story anywhere in `workExperience.md`. Multiple sessions now (including this one, on Runpod) have manually worked around them rather than using them. Worth a real cleanup pass — either restore the backing story if the claim is genuine, or remove the orphaned tags — so they stop surfacing as false matches on future JDs. Confirm with Jason before deciding which.

## What "done" looks like for any new work in this thread

For each company drafted: `data/submissions/{slug}/` containing `Original_JD.txt` (with `URL: <url>` as its first line), `stage0_fit_gate.json`, `Resume.md`/`.pdf`, `CoverLetter.md`/`.pdf`, `draft_manifest.json` (`verification_passed`/`rubric_score` populated with real evidence citations), `verification_receipt.json`. No `Interview_Cheat_Sheet.md`. `jobs` table row updated from `New` to `Drafted` (or `[Reach Out] ` title-prefixed if tagged). Report back to Jason in plain language, no internal codes: fit decision, rubric scores with evidence, any gap and how it was bridged, final page count, confirmation of file locations, and whether both verification commands passed clean.
