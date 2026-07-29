# CR-069: `ACC-401-AITOOLS` / `ACC-204` Under-Scoring Diagnostic (Phase 1 — Measurement + Root Cause, No Fix)

## Metadata
- **Epic**: Local-LLM Drafting Pipeline (see `docs/reports/local-llm-builder-architecture-options.md`)
- **Status**: Scoped, not started. This is the handoff brief for the session that runs it.
- **Date**: 2026-07-15
- **Source**: Direct follow-up in the CR-063 → CR-064 → CR-065 → CR-066 → CR-067 → CR-068 investigation
  arc. CR-063 named TWO failure modes in `jd_tailoring.py`'s claim-selection: `ACC-105-EXECUTION`
  over-representation (now substantially fixed — top-5 count dropped 9/12 → 5/12 per CR-066, all 3
  remaining `requirements`-extraction companies fixed per CR-068 Round 2) and `ACC-401-AITOOLS`/`ACC-204`
  under-scoring, which has never been fixed or even directly root-caused by anything in this arc. Every
  downstream CR that measured these two claims found the same result — see Problem below.

## Global Constraints
(Pulled verbatim from `docs/spec/00-project-constitution.md`.)

### Goals
- `GOAL-001`: Automate multi-source job scouting (BuiltIn, APIs, OpenPostings; LinkedIn decommissioned per CR-010).
- `GOAL-002`: Implement deterministic fit scoring to minimize LLM token waste.
- `GOAL-003`: Generate application materials (Resume, Cover Letter) grounded in verified `workExperience.md`.
- `GOAL-004`: Maintain absolute data privacy by running the core engine on `localhost`.
- `GOAL-005`: Provide a real-time dashboard for monitoring the automation pipeline.

### Non-goals
- `NG-001`: Cloud hosting or multi-user access (privacy violation).
- `NG-002`: Direct ATS submission (requires human-in-the-loop for safety).
- `NG-003`: "General purpose" career coaching (focused strictly on PM roles).

### Global quality bar
- Performance: Sub-second UI response; sub-15-minute end-to-end job evaluation.
- Accessibility: Standard WCAG compliance for internal use.
- Security: Zero-knowledge architecture; API keys restricted to local `.env`.
- Reliability: 100% "Context Firewall" success between job iterations.
- Maintainability: SDD-compliant code with full requirement traceability.
- Documentation: Spec-first workflow enforced for all changes.

### Agent constraints
- Agents must update specs before code.
- Agents must cite requirement IDs in tasks and implementation summaries.
- Agents must preserve existing accepted behavior unless a change request says otherwise.
- Agents must record open questions instead of guessing when the decision changes product behavior.

## Problem

`ACC-401-AITOOLS` (AI tooling / prompt engineering / agentic workflows) and `ACC-204` (Sterkly
dev-coordination, split across `ACC-204-QA`/`ACC-204-GLOBAL`) are real, grounded, high-value claims —
not hypothetical. The eval set (`docs/reports/jd-theme-claim-eval-set.md`) names `ACC-401-AITOOLS` as a
should-surface claim on 6 of 16 JDs, including two where the JD states the exact skill as a **hard,
explicit requirement**: Remote ("Proficiency in Cursor and/or Claude Code") and Covideo (AI-fluency named
as a hard requirement). `ACC-204` is named should-surface on 2 (Buyers Edge Platform, PAR), both of which
literally contain "scrum"/"agile"/"sprint"/"backlog" in their JD text (confirmed by grep in CR-063 Round
4). Despite this, every measurement across three separate investigation arcs found the same result:

| Source | ACC-401-AITOOLS hit rate | ACC-204 hit rate |
|---|---|---|
| CR-063 Round 1 baseline (16 JDs) | 0/6 | 0/2 |
| CR-063 Round 3 (added `genai`/`agentic`/`llm`/`cursor`/`claude` to `THEME_KEYWORDS`) | 0/6 (unchanged) | not retested this round |
| CR-064 Round 1 hand-check, Remote (dedup+rarity design, pre-implementation) | rank 43→24 of 63 (up 19, still outside top-5) | not hand-checked |
| CR-064 Round 3 (dedup+rarity, live, 14-JD set) | 0/6 | 0/2 |
| CR-064 Round 5 (dedup+rarity+DCG dampener, live, 7-JD subset) | 0/2 | 0/2 |
| CR-065 Part E (corrected `keywords`+`requirements` profile, 6-company sample) | False→False in every sampled company | not in this sample |
| CR-066 Round 1 (shipped `keywords` frequency-sort fix, live) | still MISS in every company listed (DataGrail, PointClickCare, Redox — all `ACC-401-AITOOLS MISS`) | not in this table's sample |

No round in this arc has directly answered *why* — every measurement so far has been a side-effect
check inside a CR scoped at a different target (`ACC-105-EXECUTION`'s over-representation, `keywords`'
alphabetical bias, `requirements`' boilerplate capture). This CR is the first to scope the under-scoring
problem itself as the primary target.

### Evidence gathered directly against real code/data before scoping this diagnostic (not hypothesis alone)

**1. The claim's own text has a real, checkable vocabulary gap — confirmed by reading `data/master_claims.json` directly.**
`ACC-401-AITOOLS`'s full body: *"Daily hands-on use of Claude and Gemini for prompt engineering and
agentic tooling, including designing and building an end-to-end job-search automation pipeline
(JobAgent/Applyr) that scouts listings, scores JD fit, and drafts grounded application materials from a
verified claims catalog."* Tags: `AI Tools`, `Prompt Engineering`, `Agentic Workflows`, `Automation`,
`Python`. The claim body and tags contain **"Claude" but never "Cursor"** — and Remote's JD literally
frames these as an either/or pair ("Cursor and/or Claude Code"). No scoring mechanism, however tuned,
can credit a substring match that doesn't exist in the source text. This is directly checkable and
already checked; it needs to be confirmed across the other 5 should-surface JDs, not just Remote.

For `ACC-204`: `ACC-204-QA`'s body contains "backlog" verbatim (a real, if generic, token match
candidate); `ACC-204-GLOBAL`'s body ("Coordinated with a globally distributed engineering team across
three countries to maintain a consistent release cadence") contains **none** of
`scrum`/`agile`/`sprint`/`backlog` — the exact vocabulary both should-surface JDs use. CR-063 Round 4
flagged this and hand-calculated that even adding `backlog` as a `THEME_KEYWORDS` entry would not close
either gap (Buyers Edge: 8→11 vs. cutoff 13; PAR: 1/4→still nowhere close vs. cutoff 10) — but that
hand-calc predates CR-064's rarity/DCG mechanisms and CR-066/068's extraction fixes, so it needs
re-verification against the current shipped state, not inheritance as still-true.

**2. A previously unexamined mechanism, found by direct code reading this session:
`priority_themes`' hard 4-item cap truncates in `THEME_KEYWORDS`' declared table order, not by
relevance — and the AI-tooling entries were appended last.** `build_jd_profile_deterministic`
(`scripts/jd_tailoring.py:126-157`) iterates the full 36-entry `THEME_KEYWORDS` tuple top to bottom,
appending every distinct-phrase match to `themes`, then returns `themes[:4]` — the first 4 matches *in
table order*, not the 4 most relevant. `THEME_KEYWORDS`' first ~8 entries are `platform`, `data`,
`ingest`, `migration`, `security`, `roadmap`, `saas`, `stakeholder` — generic B2B SaaS vocabulary that
Round 1's own measurement shows tripping on nearly every JD in the eval set (e.g. Remote's extracted
themes were literally "platform reliability, data integrity, stakeholder alignment, API integration" —
already 4 slots, all generic, before the table even reaches `integration`/`api`/`cursor`/`claude`, which
sit near the very end of the tuple, added reactively in CR-063 Round 3 rather than reordered by
priority). If this pattern holds, the AI-tooling theme phrase **never enters `priority_themes` for any
JD that also trips 4 earlier-positioned generic themes** — which appears to be nearly every JD in this
catalog per Round 1's raw table. That would mean `score_claim_for_jd`'s theme-token loop (loop 3, which
reads only `profile.priority_themes`) can never credit AI-tooling tokens (`tooling`, `prompt`,
`engineering`, `agentic`) for `ACC-401-AITOOLS`, regardless of what CR-063 Round 3 added to the table —
only the separate, profile-independent full-table loop (loop 4, which checks the *entire*
`THEME_KEYWORDS` list directly against `jd_text`/`claim_text`, bypassing the 4-item cap) can still fire,
and only for whichever literal keyword *is* present in both texts (`claude`, not `cursor`, per finding 1
above). This is consistent with CR-064's own Cresta/ACC-105 vs. Remote/ACC-401 hand-checks, which found
exactly one matched token (`claude`, via loop 4) contributing to `ACC-401-AITOOLS`'s Remote score, not
the three additional tokens (`tooling`/`prompt`/`engineering`) loop 3 should also credit if the AI theme
survived truncation. **This has not been directly confirmed by tracing `themes` before truncation for a
should-surface JD — it is a code-reading finding, not yet a measured one.** No equivalent `THEME_KEYWORDS`
entry exists at all for `scrum`/`agile`/`sprint`/`backlog`, so this mechanism is moot for `ACC-204` (loop
3 and loop 4 both have nothing to match on regardless of truncation order).

**3. `cover_claim_picker.py` already has a claim-specific guard for `ACC-401-AITOOLS`, but not for
`ACC-204`, and it only covers the cover-letter path.** `has_ai_signal()` (`jd_tailoring.py:449`) and
`_protected_ai_slot()` (`cover_claim_picker.py:347`) are a special-case mechanism, independent of
`score_claim_for_jd`'s base score, that guarantees an AI-signal claim wins a cover-letter proof slot when
the JD trips `_AI_SIGNAL_RE`. Every CR-064 round that hand-checked `pick_cover_proofs`
(`cover_claim_picker.py:134`, the real production cover-letter path) found `ACC-401-AITOOLS` winning
slot 0 on every sampled company regardless of base-score changes — this guard, not the underlying
formula, is why. No equivalent mechanism exists for `ACC-204`, and neither claim has any equivalent
protection on the *other* consumers of `score_all_claims`/`score_claim_for_jd`
(`draft_compiler.py:100/406/496`, `claim_composer.py:154/216`, `local_draft_stages.py:438` — resume-side
selection and the `pick_cover_bullets` fallback path). This means the "0/6 top-5" metric may represent
different real-world severity depending on which consumer is looked at: already-mitigated for
`ACC-401-AITOOLS` on the cover-letter-proof path specifically, but fully unmitigated everywhere else and
for `ACC-204` everywhere. This distinction has never been made explicit in any prior CR in this arc.

## Decision

Run a diagnostic-only Phase 1 — measurement and root-cause, no fix, following the exact discipline this
arc has held throughout (CR-063/CR-065/CR-067's pattern: instrument, measure against real data, write an
evidence-backed finding, gate any fix on a separate follow-up CR).

1. **Fresh baseline, current shipped code.** Re-run the eval set's `ACC-401-AITOOLS`/`ACC-204` hit-rate
   measurement against the pipeline exactly as it ships today (post CR-064-final dedup+rarity+DCG,
   CR-066's frequency-sorted `keywords`, CR-068 Round 1+2's `requirements` fixes) — every number cited in
   Problem above was taken at an earlier point in this arc's history and the code has changed underneath
   since. Do not assume any earlier round's 0/6 or 0/2 figure still holds; confirm it directly.
2. **Direct vocabulary-gap check (evidence item 1 above), extended to all should-surface JDs.** For each
   of the 6 (`ACC-401-AITOOLS`) and 2 (`ACC-204`) should-surface JDs, list which JD-stated skill terms
   have zero literal substring presence anywhere in the relevant claim's body/tags. This is checkable
   directly against `Original_JD.txt` and `master_claims.json` with no new instrumentation.
3. **Trace `priority_themes`' pre-truncation match list (evidence item 2 above) for each should-surface
   JD.** Instrument `build_jd_profile_deterministic` (via a standalone script, not a production edit — same
   "parallel measurement tool" pattern CR-063/CR-065 used) to log the *full* `themes` list before the
   `themes[:4]` cap is applied, not just the truncated result. Confirm or refute directly whether the
   AI-tooling theme phrase is present in the untruncated list but displaced by earlier table entries, for
   each of the 6 `ACC-401-AITOOLS` should-surface JDs. Separately confirm there is genuinely no
   `THEME_KEYWORDS` entry that could ever produce a Scrum/coordination theme for `ACC-204`'s 2
   should-surface JDs (already established by CR-063 Round 4, re-confirm rather than re-derive).
4. **Full loop-by-loop matched-token trace (evidence item 2's downstream consequence).** For each of the
   8 should-surface (claim, JD) pairs, instrument `score_claim_for_jd` (standalone wrapper, not a
   production edit) to report which of its 4 scoring loops fired, which token(s) each contributed, each
   token's tier/rarity-weight/DCG-discount, the resulting total score, and that JD's actual top-5 cutoff
   score. This reproduces and extends CR-064's two isolated hand-checks (Cresta/`ACC-105-EXECUTION`,
   Remote/`ACC-401-AITOOLS`) to the full should-surface set for these two specific claims, using the
   current shipped formula.
5. **Confirm the guard-mitigation asymmetry (evidence item 3 above) with real output, not inference.** Run
   `cover_claim_picker.pick_cover_proofs` (the real production cover-letter path) for all 6
   `ACC-401-AITOOLS` should-surface JDs and both `ACC-204` should-surface JDs, current shipped code.
   Confirm which of the 6 actually get `ACC-401-AITOOLS` in a proof slot via the guard (expected: most, per
   prior rounds' sampling) and confirm `ACC-204` never does (no guard exists). Separately confirm what
   `draft_compiler.py`'s resume-side selection path (`score_all_claims` consumer at line 100/406/496) and
   `pick_cover_bullets`' fallback path actually produce for the same 8 pairs, since neither has the guard.
6. **Write a named root cause, or ranked set if more than one contributes**, citing the specific
   measurement (step 2, 3, 4, or 5) that supports it, per claim (`ACC-401-AITOOLS` and `ACC-204` may have
   different dominant causes — do not assume they share one just because they were grouped together by
   the CR-063 problem statement). State explicitly whether the vocabulary gap (step 2), the
   `priority_themes` truncation-order effect (step 3), a `score_claim_for_jd` formula property distinct
   from what CR-064 already tested (step 4), or something else entirely is dominant for each claim.
7. **Follow the exact checkpointing/round protocol this arc has used throughout**: write a tracker doc
   (`docs/spec/08-implementation/CR-069-rare-claim-under-scoring-diagnostic-tracker.md`) with the plan as
   checkboxes before executing, log real findings as you go, and fill in a Session Handoff block before
   ending any session.

## Acceptance Criteria

1. A fresh, current-code hit-rate baseline for `ACC-401-AITOOLS` (6 JDs) and `ACC-204` (2 JDs) is measured
   and logged, explicitly noting whether it matches or differs from the last-known 0/6 and 0/2 figures.
2. A per-JD vocabulary-gap table exists for all 8 should-surface pairs, listing which JD-stated terms have
   no literal substring match anywhere in the relevant claim's body/tags.
3. A per-JD, pre-truncation `priority_themes` trace exists for all 6 `ACC-401-AITOOLS` should-surface JDs,
   directly confirming or refuting the truncation-order hypothesis (evidence item 2) with the actual
   untruncated theme list shown, not inferred.
4. A per-pair (8 total), loop-by-loop `score_claim_for_jd` trace exists, showing every matched token, its
   tier/weight/discount, the claim's final score, and that JD's top-5 cutoff score — real numbers, not a
   qualitative "matched/didn't match" summary.
5. A confirmed, evidenced answer (not assumed) to whether `cover_claim_picker.py`'s AI-signal guard
   mitigates `ACC-401-AITOOLS`'s real-world cover-letter impact, and confirmation that no equivalent
   mitigation exists for `ACC-204` or for either claim on the resume-side/fallback selection paths.
6. A named root cause per claim (or explicitly ranked set if more than one contributes), each citing which
   of the above measurements it rests on. A finding that hedges without naming a dominant cause per claim
   does not satisfy this criterion.
7. Zero changes to `scripts/jd_tailoring.py`, `scripts/cover_claim_picker.py`, `scripts/draft_compiler.py`,
   `scripts/claim_composer.py`, `scripts/local_draft_stages.py`, or `data/master_claims.json`. Confirm via
   `git diff --stat` at close-out.
8. Full `scripts/` pytest suite (`python -m pytest -q --ignore=test_domain_gate.py
   --ignore=test_fit_policy.py --ignore=test_llm.py`) shows identical pass/fail/skip counts before and
   after — no production code changes means no test-count change; a mismatch means something outside
   this CR's intended scope was touched.

## Out of Scope

- **Any fix.** No changes to `score_claim_for_jd`'s formula, `build_jd_profile_deterministic`'s truncation
  behavior or `THEME_KEYWORDS` table, `cover_claim_picker.py`'s guard mechanism, or any other production
  code path. This phase is measurement and a written finding only.
- **`data/master_claims.json` edits** (e.g. adding "Cursor" to `ACC-401-AITOOLS`'s body/tags, adding
  scrum/agile/sprint vocabulary to `ACC-204`'s) **without Jason's explicit sign-off**, even where this
  diagnostic's own evidence points at it as a cheap, direct fix — the standing rule this entire CR arc has
  followed (CR-063 Guardrails, CR-064/CR-065/CR-067's Out of Scope) is that the catalog is source-of-truth
  and any edit to it is Jason's call, flagged as a finding here, not acted on here.
- **Reopening already-shipped, already-measured mechanisms** — `keywords`' frequency-sort (CR-066),
  `requirements`' section-scoping and length-cap fixes (CR-068 Round 1+2), or `score_claim_for_jd`'s
  dedup/rarity/DCG mechanisms (CR-064-final) — unless this diagnostic finds a specific, evidenced defect
  in one of them that disproportionately harms these 2 claims. Do not re-litigate their already-closed
  findings from architectural reasoning alone.
- **Re-deriving or expanding the 16-JD eval set** (`docs/reports/jd-theme-claim-eval-set.md`). It is fixed
  ground truth for this diagnostic, same as every prior CR in this arc.
- **Investigating `ACC-105-EXECUTION`'s over-representation.** Already substantially addressed (CR-066/068).
  This CR's target is the two under-scoring claims specifically; note incidental overlap if found, but
  don't expand scope to re-verify `ACC-105`'s fix.
- **Piloting or reopening embeddings-based semantic re-ranking, `jd_profile_mode="llm"` broadly, or Hybrid
  Anchor + Polish.** CR-063's Final round already ruled the first two out for the ranking question with
  real measured data. Do not default back to these as a fallback; if this diagnostic finds genuinely new
  evidence specific to these 2 claims that contradicts CR-063's finding, name it explicitly as an open
  question for Jason rather than piloting it inside this phase.

## Open Questions

1. **`ACC-401-AITOOLS`'s empty `employer` field.** `master_claims.json` shows `"employer": ""` for this
   claim — I confirmed by reading `score_claim_for_jd`'s signature that it does not take `employer` as an
   input at all (only `claim_text`, `profile`, `jd_text`), so this is very likely a dead end for the
   scoring question specifically. I did not exhaustively trace every `employer_for_claim_id` consumer
   across the codebase (11 files reference `employer` in some form) to confirm it plays no role in any
   other selection/display/filter path. Flagging rather than asserting a clean bill of health — worth a
   quick confirm-or-rule-out inside the diagnostic if it's cheap, not worth a dedicated investigation
   thread if it isn't.
2. **Should this diagnostic's finding include a recommendation on whether `ACC-204` should get an
   equivalent guard to `ACC-401-AITOOLS`'s `has_ai_signal`/`_protected_ai_slot` mechanism as a stopgap, or
   is that exactly the kind of narrow per-claim patch CR-063 already flagged as a smell (the "oddly
   specific one-offs" problem `THEME_KEYWORDS` had before Round 2-4's cleanup attempt)?** This is a real
   mechanism-design question — a guard is cheap and already proven to work for one claim, but stacking a
   second bespoke guard instead of fixing the general formula is a different kind of technical debt than
   this arc has otherwise been trying to avoid. This diagnostic should surface the evidence for both paths
   but the choice between them is Jason's, not something to resolve or default on here.
3. **Given CR-064 already spent 5 rounds on `score_claim_for_jd`'s general formula without closing this
   specific gap, is Jason open to this diagnostic concluding that a general-formula-only approach is
   structurally insufficient for these 2 claims** (e.g., if `ACC-401-AITOOLS` turns out to be a genuine
   catalog outlier — the only claim whose sole differentiator is a single named-tool token that isn't even
   fully present in its own body — and `ACC-204` splits its relevant vocabulary across 2 separate claim
   variants, diluting whichever one would otherwise win) **such that a claim-content fix is the load-bearing
   lever rather than more formula tuning?** This diagnostic should surface evidence either way (per
   Acceptance Criterion 6); which lever to pull next is explicitly not this phase's decision.

## Traceability Mapping

| File | Action |
|------|--------|
| `docs/spec/08-implementation/CR-069-rare-claim-under-scoring-diagnostic-tracker.md` | New — round-by-round measurement log, checkpointing protocol, Session Handoff block. Created by whoever picks up this CR. |
| `scripts/jd_tailoring.py` | **No changes in this CR** — diagnostic only. `build_jd_profile_deterministic`'s `themes[:4]` truncation and `score_claim_for_jd`'s 4 scoring loops are the two sites this diagnostic instruments (via standalone wrapper scripts) but does not edit. |
| `scripts/cover_claim_picker.py` | **No changes in this CR** — `has_ai_signal`/`_protected_ai_slot` (lines 210, 347) are read and exercised via the real production function, not edited. |
| `data/master_claims.json` | **No changes in this CR** — read only, per Out of Scope. |
| `docs/spec/05-change-requests/README.md` | Add CR-069 registry row (this CR). |
