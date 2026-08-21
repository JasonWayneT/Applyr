# Session handoff — CR-096 fixes landed + verified, CR-097 designed and locked, nothing committed

**Date:** 2026-08-21
**Handing off from:** Claude Code (Sonnet 5), context-limited mid-session
**Handing off to:** Cursor (or any fresh agent session)
**Status:** All 6 CR-096 fixes + 3 follow-up findings are implemented, tested, and verified against real data. CR-097 (self-improving authoring mechanism) has a locked product spec and a full tech-lead design (7 epics, 29 stories) — **zero code written for CR-097.** Nothing in this session has been committed to git. Working tree is on `main`.

---

## Read these two files first, in full, before touching anything

1. **`docs/spec/05-change-requests/CR-096-stage1-3-audit-remediation.md`** — the 6 original fixes plus a same-day addendum covering 3 follow-up findings. This is the complete technical record of everything already implemented this session. Its own "Roadmap" section names the two things still open (CR-097, and re-authoring 6 test-batch companies).
2. **`docs/spec/05-change-requests/CR-097-self-improving-authoring-feedback-loop.md`** — the locked spec for the NOT-YET-BUILT self-improving mechanism. Read its "Decisions" section — the 4 open product questions were explicitly delegated to agent judgment by Jason ("this doesn't need my sign off we need to use best judgment based on best practices") and are now locked, not pending.

Then: **`docs/spec/08-implementation/CR-097-self-improving-authoring-feedback-loop-epics.md`** — the actual build plan (7 epics, 29 stories, checkbox-tracked, nothing checked off yet except Epic 0/diagnosis). This is the resumable unit — a fresh session picks up at the first unchecked story with zero other context beyond this file plus CR-097 itself.

Also worth a skim: **`pipeline-log.md`** (repo root, gitignored) has the full `## Product Manager` and `## Tech Lead` entries for CR-097 with all the reasoning in first-person form — useful if the CR docs feel too compressed.

---

## What actually happened this session, in order

This session had two separate user requests, both against the same handoff doc lineage (`docs/spec/08-implementation/SESSION-HANDOFF-2026-08-21-stage1-3-audit-remediation.md`, itself inherited from an even earlier session that did a real 12-company audit of Applyr's Stage 1-3 pipeline):

### Turn 1 — implement the 6 audit fixes (all done)

Read `SESSION-HANDOFF-2026-08-21-stage1-3-audit-remediation.md` in full (still present, now also updated with a pointer to CR-096). Did a refreshed research pass, then implemented and verified all 6 fixes against the exact real companies/data that surfaced them:

1. Certification hard-gate + 0-to-1 role_exclusion example (`scripts/evidence_scale.py`)
2. Reasoning/item consistency check (`scripts/evidence_scale.py`)
3. Boilerplate extraction gap (`scripts/stage0_extract.py`, `scripts/build_stage0_fit_gate.py`)
4. LW-028 attribution false positives (`scripts/submission_linter.py`)
5. Excerpt length + sentence-boundary truncation (`scripts/build_authoring_packet.py`)
6. Authoring digest self-check section (`scripts/generate_authoring_rule_digest.py`, `data/authoring_rule_digest.md`)

Plus cleanup: Harbor Compliance's stuck folder was manually Skipped and moved to `data/archive/skipped/` with a proper ledger entry (it was sitting in `data/submissions/` as if it had passed Stage 0).

Three real, unplanned findings came out of implementing (not just writing) these fixes — all documented in detail in CR-096:
- Fix 1's certification/role_exclusion prompt change alone did NOT actually flip Harbor Compliance's real verdict — the disqualifying sentence lives in the `responsibilities` bucket, which the pipeline never gate-checks at all.
- Fix 4's LW-028 false positives had 2 different real causes, not 1 shared one as originally guessed — Rhino Jetty's was a genuine `master_claims.json` data inconsistency, not a linter bug.
- Fix 5's excerpt-length increase, measured (not guessed), re-blocks one real outlier JD (Schellman, 17 required items vs. the typical 7-12) even at a much smaller cap increase than chosen.

All of this is written up with full technical detail, real before/after numbers, and research citations in CR-096. Full 34/34 test suite (`python scripts/run_all_tests.py`) was green after this turn.

### Turn 2 — fix the 3 findings + start the self-improving mechanism (all done)

User asked to research best practices and remediate the 3 findings above, plus start (design only) the self-improving mechanism Piece A. Both are done:

**The 3 findings, all fixed and verified (see CR-096's addendum section for full detail):**
- **Harbor Compliance / responsibilities gap:** added `screen_responsibilities_for_exclusion()` to `scripts/build_stage0_fit_gate.py` — a two-tier screen (deterministic gate for unambiguous "own the zero-to-one build" phrasing, LLM escalation only for genuinely ambiguous cases) matching cost-effective LLM-triage research. Verified end-to-end that Harbor Compliance's real JD now correctly disqualifies.
- **Schellman / token-budget outlier:** added `_shrink_excerpts_to_budget()` to `scripts/build_authoring_packet.py` — builds excerpts at the full researched cap first, only shrinks (proportionally, sentence-bounded, floor 400 chars) if the packet actually overflows. Schellman: 9,132 → 7,400 tokens, now `ready`. Zero other job affected.
- **Rhino Jetty / claims catalog contradiction:** corrected `data/master_claims.json`'s `ACC-104-OPS` entry (ownership-tier "Built and deployed..." → partnership-tier "Partnered with... to deliver...", matching `workExperience.md`'s own explicit hedge verbatim), regenerated `data/master_claims_tags_only.json` via `python scripts/generate_context_pack.py`, and corrected the already-drafted `data/submissions/rhino_jetty/Resume.md` bullet to match. **Important:** editing that Resume.md after Stage 2 had already completed correctly triggered the pipeline's own hash-freshness invalidation — Rhino Jetty's folder is now at `workflow status=WAITING_FOR_HUMAN`, blocked on exactly one pre-existing, never-actually-done requirement (`hm.critical_read` — a literal human read of the resume/cover letter, disposition it `ACCEPTED_AS_CORRECT` in `data/submissions/rhino_jetty/reviews/dispositions.json` once done). This was never disposed even before this session's edit — not something this session broke, just something this session's edit surfaced. **Do not disposition `hm.critical_read` on Jason's behalf; that's explicitly a human judgment step by design.**

Full 34/34 test suite green after all 3.

**Self-improving mechanism (CR-097), design done, zero code:**
- Spawned this repo's own `product-manager` subagent (Claude Code's `.claude/agents/product-manager.md` — **this agent type does not exist in Cursor**, see "If you're in Cursor, not Claude Code" below) to scope the mechanism. It correctly refused to guess on 4 genuinely open product questions and wrote them up in `CR-097-self-improving-authoring-feedback-loop.md`.
- Jason then said the open questions didn't need his sign-off, decide by best judgment. Locked all 4 (storage split by type, trigger at 2-occurrence, mechanism shape targets "rule exists but not applied," promotion bar matches the trigger) directly in CR-097's own text, with reasoning.
- Spawned this repo's `tech-lead` subagent to design against the locked decisions. It found something important: **the 3 target failure categories (wrong-job bleed, gap-confession, forbidden punctuation) are Stage-1 `HARD_BLOCK` rules, never Stage 2 findings** — measured across all 30 real submission folders, zero of them ever appear in a `dispositions.json`. The original success-metric plan (count `RESOLVED_EDIT` dispositions) would have been silently, permanently zero. Fixed by moving the observation point to the Stage 1 verify gate instead — a genuine finding, correctly judged as an instrumentation fix rather than a product decision requiring backflow to product-manager.
- Produced `CR-097-self-improving-authoring-feedback-loop-epics.md`: 7 epics, 29 stories, ROI-ordered. **Epic 1 has standalone value and should go first regardless of what else gets built** — it's the only thing that makes first-draft defects observable at all; nothing downstream works without it.

**Nothing in CR-097 has been implemented.** This is exactly where the prior session (me) stopped and asked whether to proceed — that's the open question for whoever picks this up next.

---

## Exact repo state right now

**Git-tracked changes (all uncommitted, on `main`):**
```
M CHANGELOG.md
M data/authoring_rule_digest.version
M scripts/build_authoring_packet.py
M scripts/build_stage0_fit_gate.py
M scripts/evidence_scale.py
M scripts/generate_authoring_rule_digest.py
M scripts/stage0_extract.py
M scripts/submission_linter.py
```
New tracked files:
```
docs/spec/05-change-requests/CR-096-stage1-3-audit-remediation.md
docs/spec/05-change-requests/CR-097-self-improving-authoring-feedback-loop.md
docs/spec/08-implementation/CR-097-self-improving-authoring-feedback-loop-epics.md
docs/spec/08-implementation/SESSION-HANDOFF-2026-08-21-stage1-3-audit-remediation.md
docs/spec/08-implementation/SESSION-HANDOFF-2026-08-21-cr096-097-cursor-handoff.md  (this file)
```
`data/Resume_Generic_Indeed.docx`, `data/fit_rubric_spec.html`, `scripts/_bakeoff_stage0_score_model.py` are untracked but **pre-existed this session** — not part of this work, don't assume they're related.

**Gitignored files this session changed on disk (invisible to `git status`, real on disk, will NOT show up if you only check git):**
- `data/authoring_rule_digest.md` (regenerated, content changed — the actual digest content, its tracked `.version` sibling above is what git sees)
- `data/master_claims.json` (ACC-104-OPS entry corrected)
- `data/master_claims_tags_only.json` (regenerated from the above via `generate_context_pack.py`)
- `data/agent_context_pack.md` (regenerated as a side effect of the same command)
- `pipeline-log.md` (repo root — has the full product-manager + tech-lead entries for CR-097)
- `data/submissions/rhino_jetty/Resume.md` (one bullet's wording corrected)
- `data/submissions/rhino_jetty/reviews/*` and `workflow_state.json` (Stage 2 auto-restarted by the pipeline after the Resume.md edit — see Turn 2 notes above, this folder is now `WAITING_FOR_HUMAN`)
- `data/submissions/{point_c,tm2_group_llc,alfa_laval,meeboss,amn_healthcare,nuaxis_innovations}/authoring_packet.json` (regenerated against the fixed pipeline during Turn 1 verification — no Stage 1 draft was run, no cloud LLM cost spent, these are still all "Not started" per CR-096's status table)
- `data/submissions/harbor_compliance/` → moved to `data/archive/skipped/harbor_compliance/` (Turn 1 cleanup), plus a new row in the `stage0_skips` table inside `data/jobagent.sqlite`

**Verification status:** `python scripts/run_all_tests.py` was run and green (34/34, 0 failed) after every code change in both turns. Last confirmed clean run was at the end of Turn 2's findings-remediation work, before the CR-097 design pass (which wrote no code, so this is still the accurate status).

---

## The one open decision for whoever picks this up

CR-097's epics tracker is fully ready to execute. The prior session stopped and asked Jason: proceed with implementation now, and if so, all 7 epics or just Epic 1 first? **That question was never answered before context ran out.** Do not assume an answer — ask Jason directly, the same way the prior session did, before writing any CR-097 code. If Jason says "yes, go," start at Epic 1, Story 1.1 in the epics file, in order — the tracker is written to be resumable from the first unchecked box.

Two other decisions from CR-096's own roadmap are also still open and were not part of this session's scope: whether to extend Fix 1's role_exclusion gating to run on every responsibilities line by default (real ongoing per-JD compute cost — right now it only runs the cheap deterministic gate plus a narrow escalation regex, not full classification on everything), and whether/when to re-author the 6 remaining test-batch companies (`amn_healthcare`, `point_c`, `meeboss`, `tm2_group_llc`, `alfa_laval`, `nuaxis_innovations`) against the now-fixed pipeline — their packets are refreshed and ready, this is purely a real-authoring-cost decision for Jason.

---

## If you're in Cursor, not Claude Code

This repo's SDD process (`docs/spec/`) is tool-agnostic — the CR docs, epics tracker, and `AGENTS.md` are plain markdown, nothing here requires Claude Code specifically. But two things in this handoff's own history won't carry over:

- **The `.claude/agents/product-manager.md` and `.claude/agents/tech-lead.md` subagent definitions** that produced CR-097 and its epics are a Claude Code-specific mechanism (the `Agent` tool with a `subagent_type`). If you're in Cursor, you don't have an equivalent one-command way to invoke them — but you can still *read* their role definitions (they're just markdown files with instructions) and follow the same discipline by hand: read the CR, check `docs/spec/07-decisions/` and active trackers, don't guess at open product questions, etc. The actual CR-097 spec and epics file are the durable output — you don't need the agents themselves to execute against them.
- **`AGENTS.md`** (repo root) is the canonical, tool-agnostic instruction set — read it in full before touching `data/submissions/` or any resume/cover-letter content. `CLAUDE.md` is just a Claude-Code-specific import stub for the same file; ignore it if you're not Claude Code.

Everything else — the actual Python scripts, the test suite (`python scripts/run_all_tests.py`), the data files, the CR/epics docs — works identically regardless of which agent is driving.

---

## Quick-start checklist for the next session

1. Read `CR-096` addendum, `CR-097`, and the CR-097 epics file (links at top of this doc).
2. Run `python scripts/run_all_tests.py` yourself to confirm the tree is still green before you change anything (should be 34/34).
3. Ask Jason: proceed with CR-097 implementation? All of it, or Epic 1 only first?
4. If yes: open the epics file, start at the first unchecked story (`Story 1.1 — Category map module`), and follow the tracker's own checkbox discipline — check off each story as it lands, don't skip ahead.
5. Remember `data/submissions/rhino_jetty` needs a real human critical-read disposition before it can reach `COMPLETE` again — flag this to Jason, don't do it yourself.
