---
status: not_started
created: 2026-07-17
related: CR-059 (local-llm-tuning-loop, closed_moot — this CR corrects a scoping gap in its finding), CR-053/054/055 (fit-rubric overhaul, owns the scoring formula this CR relocates but does not change), CR-062 (local-rewrite-harness, untouched), CR-064 (claim-score-formula-rework, untouched)
contains: CR-070 (Claude-Native Generation Pipeline)
---

# CR-070 — Claude-Native Generation Pipeline: Epics & Stories

**Handoff doc, one change request.** Resumable plan for rearchitecting the resume/cover-letter
generation pipeline to run inside Claude Code on the subscription (no API billing), batch-capable
across 24+ JDs with minimal permission-prompt friction, without touching the deterministic
grounding/rubric/voice machinery that already works. A new session can pick up at the first unchecked
story with no other context needed beyond this file, [CR-070 spec](../05-change-requests/CR-070-claude-native-generation-pipeline.md),
and the Phase 1 investigation findings summarized in that spec's Problem section.

## Why this exists (do not re-litigate without re-reading this)

Phase 1 investigation (2026-07-17 session) found CLAUDE.md's inherited claim from CR-059's closure
("the default drafting pipeline calls zero local LLMs") is stale. CR-059's own tracker doc actually
already scoped fit-scoring **out** of its "zero LLMs" finding by name ("Redirecting to the LLM calls
that do run live (fit scoring, research packets, interview cheat sheets) would cross this CR's own
guardrail") — the finding was correct and narrow, but CLAUDE.md's summary of it lost that nuance and
now reads as an unqualified claim. Two call sites are live LLM calls on the default path today:

1. `evaluate_job_fit` → local Ollama, up to 5x per job, up to 180s timeout each (`scripts/batch_pipeline.py:813`, `scripts/llm_stages.py:57`)
2. `audit_and_improve.audit_and_improve_company`, called unconditionally post-draft (`scripts/drafting_engine.py:391`), up to 8 more LLM round trips rewriting already-deterministic output — this one was not previously named by any CR in the registry.

These two, plus 4-10+ Playwright re-renders per job, are the concrete, evidence-backed contributors to
the 5-10 minute per-JD time. No manual-approval prompts exist anywhere in the generation code itself —
if approval-click friction is being felt, it's coming from the Claude-Code-harness layer (Bash
permission prompts on repeated script invocations across a batch), not the Python pipeline. Epic 5
addresses that directly.

## Open decisions — resolved 2026-07-17

- [x] **Is `audit_and_improve.py`'s rewrite loop known to have ever caught a real defect the rubric gate wouldn't?** RESOLVED — investigated directly (code read + `git log --follow`, see spec doc). Answer: no, it's not redundant motion. It does three real things the deterministic draft and the rubric gate don't: company-stage-aware tailoring of summary/cover letter (not just keyword overlap), a second independent numeric/fact grounding check with a retry-feedback loop, and a snapshot/restore safety net so failed runs never leave broken output. Epic 3 below now ports this logic to Claude-native reasoning rather than deleting it, running as a distinct step *before* the rubric gate, not a replacement for it. Original note kept below for record: Epic 3 deletes it on the assumption it's redundant motion, not a safety net. Before deleting, Epic 3's first story should search for any evidence (commit messages, past submission diffs) it fixed something real. If it did, that behavior needs to be preserved inside the new rubric-gate pass, not just dropped.
- [x] **Losing Ollama as a second, independent model for fit evaluation** — RESOLVED, Jason's decision: use the Claude-native reasoner. Single coherent reasoner, no Ollama dependency on the default path. Epic 2 implements this; the old path is kept in the repo (not deleted) behind an opt-in flag per the "keep code intact" decision below. Original note kept below for record: — today `evaluate_job_fit` and Claude's own drafting judgment are two separate reasoners. Moving fit evaluation to Claude-native reasoning makes it one coherent, more auditable reasoner, but removes that independence. Is that a net improvement or a regression worth keeping the Ollama path for, opt-in? Default recommendation: single coherent reasoner (simpler, faster, no infra dependency) — flag for explicit approval before Epic 2 ships.
- [x] **Keep application code intact for research/study** — Jason's explicit instruction (2026-07-17), applies repo-wide to this CR: nothing gets deleted. `audit_and_improve.py` and the Ollama fit-call path stay on disk, unmodified, reachable via an explicit opt-in flag (default off). Every story below that previously said "remove"/"retire" now says "gate off by default" instead.

## Epic 1 — Fix the stale documentation claim

Quick, standalone, no code risk. Do this first regardless of what happens with the rest of the CR.

- [ ] **Story 1.1**: Correct CLAUDE.md's CR-059 reference to name fit-evaluation and `audit_and_improve` as live LLM call sites (not "zero local LLMs" unqualified). Mirror the exact same edit into AGENTS.md per the repo's byte-identical rule.
- [ ] **Story 1.2**: Update CR-059's tracker doc status/related-CRs to reference this CR-070 as the follow-up that acted on the fit-scoring/audit-and-improve call sites it had explicitly scoped out.

## Epic 2 — Fit evaluation: Ollama subprocess → Claude-native reasoning

**Scope corrected 2026-07-17 (superpowers plan Story 2.1 trace).** The original Epic 2 wording targeted `_call_fit_llm`/`_call_fit_scoring_only` (`scripts/batch_pipeline.py:661-946`) — CR-035's legacy holistic 0-100 scorer, up to 5 Ollama calls at up to 180s timeout each. Traced the real live call graph before planning further: `evaluate_job_fit` (`batch_pipeline.py:813`) checks `structured_fit_enabled()` (`structured_fit.py:85-87`, defaults **on** — `STRUCTURED_FIT` env var default `"1"`) and, when true, calls `evaluate_structured_fit` (`structured_fit.py:400-416`, CR-053) and **returns immediately on success** (`batch_pipeline.py:881`) — the entire legacy multi-retry ladder below it (`batch_pipeline.py:883-940`) is dead code on the default path today, only reached if structured scoring is disabled or fails outright.

The real default-path LLM call is `_call_equivalence_llm` (`structured_fit.py:218-281`), invoked once per JD from inside `evaluate_structured_fit` (`structured_fit.py:411-412`). It's already narrowly scoped — yes/partial/no judgments per must-have plus 5 fixed criteria, explicit system instruction "Never output a fit score number" — with `_heuristic_judgments` (`structured_fit.py:191-215`, zero-LLM keyword overlap) as an already-built fallback when the call fails, and all actual scoring math (`compute_fit_report`, `structured_fit.py:306-397`) is deterministic Python, not LLM. This is a much better-designed system than the original Epic 2 wording credited — CR-053 already solved most of what Epic 2 assumed was still broken. Net effect: Epic 2 removes **one** Ollama round trip per job, not five. Correcting this now rather than building against a premise that doesn't match current code.

- [x] **Story 2.1**: RESOLVED — traced above. Real target: `_call_equivalence_llm` (`structured_fit.py:218-281`), input = `(jd_text, work_exp, must_haves)`, output schema = `{"must_haves": [{"text","judgment","justification"}...], "criteria": {<5 fixed keys>: {"judgment","justification"}}}`, consumed by `_normalize_judgments` (`structured_fit.py:284-303`) then `compute_fit_report` (deterministic, unchanged).
- [ ] **Story 2.2**: Build the skill step where Claude reads the JD text + must-haves (from `extract_must_haves`, already deterministic, unchanged) + candidate profile excerpt and produces the same `{"must_haves": [...], "criteria": {...}}` JSON shape directly (Write tool), replacing the `call_llm_stage("fit_equiv", ...)` call in `_call_equivalence_llm`. `compute_fit_report`, `_normalize_judgments`, `_heuristic_judgments`, and all of `fit_policy.py`'s downstream gates stay untouched — only the judgment source changes.
- [x] **Story 2.3**: DONE 2026-07-17 — ran a real 10-JD comparison (`docs/superpowers/plans/2026-07-17-cr070-epic1-epic2.md` Task 4). Method: picked 10 archived JDs (`data/archive/submissions/`) that also have a stored historical `jobs.score` in `jobagent.sqlite` (snapsheet, roadie, quinstreet, pointclickcare, tivity_health, apex_systems, ryan, swarm_aero, rafay, informdata). Ollama is not reachable in this environment (confirmed — `localhost:11434` connection refused), so a live same-session Ollama-vs-Claude-native head-to-head wasn't possible; compared Claude-native judgments (reasoned directly against each real JD + `data/workExperience.md`, written via `fit_judgment_io.write_equivalence_judgment`, run through the real `evaluate_structured_fit(FIT_JUDGMENT_MODE=claude_native)`) against each job's stored historical `jobs.score` instead.

  **Caveat that matters:** the historical scores were not necessarily produced by today's exact `compute_fit_report` code — fit/claim scoring changed multiple times across CR-053/064/065/066/067/068 since those jobs were originally scored, so this is not a clean same-algorithm before/after. It's the best available real-world baseline without a reachable Ollama endpoint, not a controlled experiment.

  | Company | Historical | Claude-native | Decision (72 threshold) | Diff |
  |---|---:|---:|---|---:|
  | snapsheet | 85 | 96 | YES | +11 |
  | roadie | 97 | 100 | YES | +3 |
  | quinstreet | 85 | 68 | **NO** | -17 |
  | pointclickcare | 75 | 90 | **NO** (hard-fail on healthcare must-have) | +15 |
  | tivity_health | 60 | 96 | YES | +36 |
  | apex_systems | 96 | 90 | YES | -6 |
  | ryan | 100 | 88 | YES | -12 |
  | swarm_aero | 78 | 62 | **NO** | -16 |
  | rafay | 85 | 90 | YES | +5 |
  | informdata | 85 | 96 | YES | +11 |

  Mean absolute difference: 13.2 points. **8/10 agree on Decision direction at the min_fit_score=72 threshold; 2/10 disagree** (quinstreet, swarm_aero — both cases where the Claude-native judgment flagged a real domain/craft mismatch: quinstreet is consumer-fintech growth/experimentation work, not Jason's documented platform-stabilization craft; swarm_aero is defense/UAV real-time systems, explicitly stated as not a role "for someone learning the craft"). pointclickcare is a third notable case: Claude-native correctly hard-failed on the healthcare-background must-have even though the weighted score alone (90) would have passed — Jason has zero healthcare/clinical domain experience, and CR-053's own founding diagnosis specifically named domain-mismatch as a failure mode the old scoring missed.

  **Read on this, not just the numbers:** the two decision flips aren't random noise — both are explainable by genuine domain/craft-fit reasoning that plausibly predates CR-053's domain-awareness work. But 10 JDs and one reasoner's pass is not enough to declare this settled either way. **Recommendation: do not flip `FIT_JUDGMENT_MODE` to `claude_native` by default yet.** Widen the sample (aim for 30-50, spanning more of the archive) and, critically, get Jason's read specifically on the quinstreet and swarm_aero calls — do those two flips match his own judgment of those two roles, or does the Claude-native reasoning have a real, correctable bias? That answer should gate the default flip, not an aggregate diff number alone.
- [x] **Story 2.4**: RESOLVED per "keep code intact" decision — gate `_call_equivalence_llm`'s Ollama call behind an explicit opt-in flag (e.g. `FIT_JUDGMENT_MODE=ollama_legacy`, default off) once 2.3 passes. Leave `_call_equivalence_llm` and the dead legacy ladder (`_call_fit_llm`/`_call_fit_scoring_only`) callable, just not on the default path.

## Epic 3 — Port `audit_and_improve.py`'s tailoring + safety-net logic to Claude-native reasoning

Investigated 2026-07-17 (see resolved Open Decision above): `audit_and_improve.py` does real work — company-stage-aware tailoring, a second independent grounding check, and safe rollback on failure — not redundant motion. This epic ports its three `call_llm` functions to Claude-native reasoning and reuses its deterministic guard logic as-is; the file itself is not deleted or modified, only stops being called by default. This step runs *before* the rubric gate (Epic 3), not instead of it — the rubric gate is a separate, later check (folded in as part of Epic 5's skill assembly).

- [x] **Story 3.1**: Investigate whether `audit_and_improve.py`'s rewrite loop has ever fixed a real defect. **Done — see resolved Open Decision above.** Finding: yes, real value in three places — stage-aware tailoring, independent numeric/fact re-check with retry-feedback, snapshot/restore safety net.
- [ ] **Story 3.2**: Build the Claude-native replacement for `analyze_company_context` — Claude classifies company stage/motion/segment/pain points/partners from the JD inline during the skill turn, no `call_llm` subprocess.
- [ ] **Story 3.3**: Build the Claude-native replacement for `improve_resume_summary` and `improve_cover_letter` — Claude rewrites the summary/cover letter for stage-fit using the same factual constraints already encoded in the current prompts (grounded-only metrics, no em-dashes, exactly 3 summary sentences), writing directly via the Edit tool. Do not carry forward `improve_cover_letter`'s hardcoded example closer (see spec doc's implementation note) — let Claude generate a fresh closer per letter.
- [ ] **Story 3.4**: Reuse the existing deterministic guard functions unchanged — `validate_hard_facts`, `audit_text_against_bullet_corpus`, the 3-sentence-count regex check, and the snapshot/restore pair (`_snapshot_submission_assets`/`_restore_submission_assets`) — calling them against Claude's edits instead of the old LLM output. Preserve the retry-with-feedback loop shape (up to 3 attempts, specific error fed back on retry).
- [x] **Story 3.5**: RESOLVED per "keep code intact" — gate the unconditional call to `audit_and_improve_company` in `drafting_engine.py:391` behind an opt-in flag (default off) once 3.2-3.4 are validated on a sample batch; do not delete the function or the file.

## Epic 4 — Reduce redundant PDF renders

- [ ] **Story 4.1**: Confirm the page-pruning loop (`draft_compiler.py:946-981`, capped at 8 iterations) is untouched and still correct in isolation.
- [ ] **Story 4.2**: Make the post-gate re-render (spec step 9) conditional on step 7 (audit-and-improve port) or step 8 (rubric gate) actually having edited Resume.md/CoverLetter.md, not unconditional.
- [ ] **Story 4.3**: Measure real render count per job before/after Epics 2-4, confirm it drops from the observed 4-10+ to at most 2 (initial + conditional re-render).

## Epic 5 — Package as a Skill; fix the manifest gap

- [ ] **Story 5.1**: Write `.claude/skills/generate-submission/SKILL.md` encoding the 11-step flow from the CR-070 spec (including step 7's audit-and-improve port and step 8's rubric gate as sequential, distinct steps), callable per-JD.
- [ ] **Story 5.2**: Fix the `draft_manifest.json` write path so every generated submission actually has it (currently missing from at least 3 checked live folders despite `draft_compiler.py:1199` writing it) — root-cause why it's absent before assuming the write call just needs to be added.
- [ ] **Story 5.3**: End-to-end test: one JD → full flow → verify frontend reads `rubric_score`/`verification_passed`/edit-gating correctly with zero frontend code changes.

## Epic 6 — Batch-run permission-prompt reduction

- [ ] **Story 6.1**: Run a small calibration batch (3-5 JDs) through the new skill, capturing every Bash permission prompt triggered.
- [ ] **Story 6.2**: Run the `fewer-permission-prompts` skill against that transcript to generate a `.claude/settings.json` allowlist scoped to the deterministic script invocations and `data/submissions/**` output paths.
- [ ] **Story 6.3**: Full 24-JD batch run; confirm prompt count matches the CR-070 spec's acceptance criterion (<5 total interruptions).

## Epic 7 — Measurement (close the loop on the estimate)

- [ ] **Story 7.1**: Instrument real wall-clock timing per stage (something the current pipeline has zero of, per Phase 1 finding) — at minimum log start/end timestamps around fit-eval, drafting, gate pass, and each PDF render.
- [ ] **Story 7.2**: Compare timed results on 3+ JDs, old pipeline vs. new, and record actual numbers in this doc (not the "under a minute" estimate in the CR-070 spec, which is reasoned from removed call counts, not measured).

## Epic 8 — Authenticity hardening (research-driven, 2026-07-17)

Jason asked whether output would get "caught in an AI audit or read clearly made by AI" and to research
and fold in real improvements. Key finding (full detail + sources in the CR-070 spec doc's "Research:
authenticity hardening" section): **no major ATS in production use in 2026 (Workday, Greenhouse, iCIMS,
SAP SuccessFactors, Lever, Ashby, Oracle Taleo) detects AI authorship** — zero of 10 tested systems did.
The real risk is a human recruiter's read and interview defensibility, not an automated gate. This epic
is scoped to recruiter-readability hardening, not detector evasion — there's no detector to evade.

- [ ] **Story 8.1**: Extend `submission_linter.py`'s word list with terms found in the research pass but not already in CLAUDE.md's Forbidden Language list: "delve," "robust," "pivotal," "cutting-edge," "unlock the potential/value," "game-changer," "future-ready," "elevate your," "drive impact," "spearheaded," "orchestrated," "It is important to note," "In today's fast-paced world," "Dive into," and "Indeed" as a sentence opener. Mirror the additions into CLAUDE.md/AGENTS.md's Forbidden Language section per the repo's sync rule.
- [ ] **Story 8.2**: Add the structural tells to the `conversion-ready-pass` skill's qualitative read (Pass 3), since these can't be regex-caught: predictable per-bullet formula with no narrative variation across a resume; vague outcome language ("significant growth," "enhanced efficiency") without a named tool/project/obstacle; a summary/skills section that mirrors the JD's exact keywords while adding no information about how the work was actually done.
- [ ] **Story 8.3**: No code change needed, but document explicitly in the spec/skill: the existing VOC/MET/ACC grounding discipline already substantially covers "can this be defended in a screening call" (the research's other named risk) — every claim traces to real work history, nothing is invented. Confirm this stays true once Epic 3's Claude-native tailoring step is live (it rewrites phrasing, not facts — verify it can't introduce ungrounded specifics under the guise of "adding detail").
- [ ] **Story 8.4**: When porting `improve_cover_letter` in Story 3.3, confirm the canned example closer is not carried forward (cross-reference — same finding, different epic).

## Epic 9 — Cover-letter voice integration (Jason's `voice-rewrite` skill)

Added 2026-07-17. Jason asked to keep cover-letter vocabulary within the realm of what he'd actually
say, pointing at his existing `voice-rewrite` skill (`C:\Users\Jason\.claude\skills\voice-rewrite\`).
Checked the actual skill files before agreeing: the `professional` profile
(`profiles/professional.md`) is already scoped for cover letters/bios/emails, is a positive vocabulary
model (Jason's real PM vocabulary vs. corporate filler to strip — "synergy," "alignment," "bandwidth,"
"circle back," "move the needle") rather than a growing deny-list, and its Pass 1 AI-artifact strip
list (`assets/voice_spec.md`) already independently covers most of Epic 8's research findings ("robust,"
"cutting-edge," "revolutionize," "transformative," "unlock," "harness," "leverage" as a verb). It's also
architecturally safe to layer in: the skill explicitly does not invent claims, add metrics, or change
substance — form and register only — which matches the constraint that mattered most when CR-017
originally moved this pipeline away from free-form LLM rewrites.

**Resolved decision (2026-07-17):** when a JD's own required-skill language happens to land on a word
the `professional` profile normally strips as corporate filler, **voice wins outright** — strip it per
the profile every time, no JD-literal carve-out. Jason's call: R2/C2/C3 keyword scoring mostly rewards
named tools/domain terms, not generic corporate connector words, so this is unlikely to cost real
JD-match points, and a hard rule is simpler to implement and audit than a per-case judgment call.

- [ ] **Story 9.1**: Scope Epic 8's linter-word-list work (Story 8.1) to pull from `voice_spec.md`'s
  Pass 1 strip list as the single source of truth rather than hand-duplicating terms into
  `submission_linter.py` independently — reconcile the two lists once, not maintain them in parallel
  going forward. Flag any term one list has and the other doesn't for Jason to confirm before merging.
- [ ] **Story 9.2**: Wire the `professional` profile as a required pass on cover-letter body text inside
  Epic 3's Claude-native tailoring step (`improve_cover_letter`'s replacement) — cover letters only, not
  resume bullets (bullets keep their own tone/word-cap gates in `claim_composer.py`, untouched).
- [ ] **Story 9.3**: Implement the "voice wins outright" rule — no exception path for JD-literal
  corporate-sounding terms. No code branch needed beyond just running the strip unconditionally.
- [ ] **Story 9.4**: After a real batch (post Epic 6), spot-check whether any cover letter visibly lost
  a genuine JD keyword match because of the strip. If it's a real, recurring cost — not just
  theoretical — revisit the "outright" rule with Jason using that evidence, per this repo's
  measure-before-deciding discipline (CR-063/064 precedent). Don't revisit on a single anecdote.

## Rollout priority

Epic 1 first (zero risk, immediate correctness). Then Epic 2 and Epic 3 in parallel — they're
independent rearchitectures of two separate call sites (both already resolved in direction, not risk
level, by the Open Decisions above). Epic 4 depends on Epic 3 being done (its "conditional re-render"
only makes sense once the unconditional audit-loop re-render is gone). Epic 8 can run any time after
Epic 1 — it's independent of the reasoner rearchitecture, touches only the linter word list and the
rubric-gate's qualitative checklist. Epic 9 depends on Epic 3 (needs the tailoring step to exist before
wiring a voice pass into it) and should reconcile its word list with Epic 8 (Story 9.1) before either is
considered done. Epic 5 depends on Epics 2-4, 8, and 9 landing (nothing to package until the flow and
its gates are real). Epics 6-7 are batch validation, last, against the real skill; Epic 9's Story 9.4
follow-up happens after Epic 6.
