# Session handoff — Stage 1–3 real-world audit, findings, and remediation plan

**Date:** 2026-08-21
**Identity for session logs:** Claude Code (Sonnet 5)
**Status:** Audit phases 1–8 done against a real 12-company test batch. 6 root-caused findings, all traced to exact file/function. **All 6 fixes are now implemented, verified against the real folders that surfaced them, and documented in `docs/spec/05-change-requests/CR-096-stage1-3-audit-remediation.md`** — read that doc for full implementation detail, real test-tradeoff data (Fix 5), and 3 additional findings surfaced during implementation that this handoff didn't know about (Fix 1's Harbor Compliance gap lives in the `responsibilities` bucket, never gate-checked; Fix 4's Rhino Jetty case is a `master_claims.json` data inconsistency, not a linter bug; Fix 3's Schellman diagnosis confirmed and fixed). Harbor Compliance's stuck folder is cleaned up (manually Skipped, ledger recorded, archived). The two items below ("New request" and re-authoring the 6 remaining companies) are **still open** — CR-096 ends with a roadmap for both, not an implementation.

---

## What the next session should do first

1. Read this file in full, then open the two artifacts linked below — they carry the plain-language version Jason reviews from, this file carries the engineering detail.
2. **Do one more external-research pass per issue before implementing** — Jason's explicit instruction. The research already done (session that produced this handoff) was one pass; he wants it double-checked/refreshed against current best practice before code changes land, not skipped. See "Research already done" below for what exists — confirm or supersede it, don't just re-cite it blind.
3. Implement all 6 fixes (see "The 6 fixes" table below — exact file, function, and root cause already identified).
4. Design and scope the **self-improving first-draft mechanism** Jason asked for (see "New request — the biggest open item" below). This is not scoped yet, only requested. Needs a real design pass, likely its own CR.
5. After the pipeline fixes land, decide whether to re-author the 6 remaining companies from the test batch (amn_healthcare, point_c, meeboss, tm2_group_llc, alfa_laval, nuaxis_innovations) against the *fixed* pipeline rather than the pre-fix one — arguably the better audit close-out than authoring them now and re-doing later.

Do **not** re-run Stage 0 on a fresh batch, and do not touch `workExperience.md` / `master_claims.json` content — none of this workstream's findings originate there.

---

## Context — what this thread actually is

Jason asked for a real-world validation audit of Applyr's Stage 1 (Author), Stage 2 (Review: Truth/ATS/HM/Mech/Policy), and Stage 3 (Finalize) — following a long, detailed audit brief he pasted (13 phases, evidence-chain discipline, anti-churn rule). Stage 0 was explicitly out of scope *unless* something in Stage 1–3 testing traced back to it — which happened, repeatedly, and is now most of the findings below.

Checkpoint discipline was agreed up front: reconstruct + define stage intent first (Phase 1–2), stop before spending real authoring-LLM cost, get a go-ahead, then execute. Jason gave that go-ahead and said "move forward with the 12 companies."

## Test corpus

Two real CSVs Jason exported (`applyr_jobs.csv`, `applyr_jobs (2).csv`, from Downloads) imported via `scripts/import_csv_to_submissions.py` → 34 JDs → Stage 0 batch (`build_stage0_fit_gate.py --batch-table`) → **1 Tier 1, 11 Tier 2, 22 Skip** (6 of the Skips were DB-cooldown dedupes on the same company appearing twice in the CSVs).

**Real incident worth knowing about:** the first Stage 0 batch run was killed mid-run on a wrong read of a netstat snapshot (looked hung, wasn't — it was genuinely slow local-model VRAM swapping). 22 of 34 results were already correctly written to disk and preserved; the remaining 12 were re-run cleanly. Told to Jason directly at the time, not hidden.

**Separate, already-logged, not-yet-tested item:** whether `gemma2:2b-instruct-q8_0` and `qwen2.5:7b-instruct-q4_K_M` can be VRAM co-resident (would remove a real per-JD reload-cycle cost in Stage 0). Jason's own design choice, made without verifying it — he wants it tested on the *next* real Stage 0 batch, not this session's. Already in [project_applyr.md](../../../../.claude/projects/C--Users-Jason-Desktop-Jason-Resource-CodeProjects-Applyr/memory/project_applyr.md) memory — re-check that file too, this doc doesn't duplicate it.

## Artifacts (Jason's copies — update these in place, don't create new ones)

- **[Workflow Reconstruction & Stage Intent](https://claude.ai/code/artifact/f434732f-3a44-4bac-ae17-a9e289c984c0)** — Phase 1–2 checkpoint. Reconstructs the real Stage 0→1→2(A–E)→3 flow from live code, and flags that the audit brief's generic 3-stage model (retrieval / drafting / rewrite-risk-gate) doesn't map onto Applyr's real stages — Stage 1 bundles retrieval+drafting, Stage 2 is review-only (never edits), Stage 3 never touches content.
- **[What We Found, and How to Fix It](https://claude.ai/code/artifact/3293253e-f908-49ad-9c71-a59cb79069f7)** — the plain-language findings report Jason reads from. Has all 6 issues in non-technical language, cited research links, and a "for whoever builds this" technical table. **This file (the handoff) has the same 6 fixes with more implementation detail — keep both in sync if either changes.**

## Stage 1 authoring — real status of all 12 companies

| Company | Status | Notes |
|---|---|---|
| Advantage Tech | **Stage 2 COMPLETE**, not finalized (no DB write) | Tier 1. Rubric: resume 79, cover letter 81. |
| Lightcast | **Stage 2 COMPLETE**, not finalized | Rubric: resume 84, cover letter 83. AI/ML-adjacent JD — attribution constraints (ACC-120 CONTRIBUTED vs ACC-401 OWNED) handled carefully, see LW-028 finding below. |
| Gravitee | **Stage 2 COMPLETE**, not finalized | Rubric: resume 82, cover letter 80. |
| Rhino Jetty | **Stage 2 COMPLETE**, not finalized | Rubric: resume 80, cover letter 79. Sterkly only had 1 real packet claim available (not the usual 2) — noted, not fixed. |
| Harbor Compliance | **Reverted to Skip, folder move NOT executed** | JD's actual core ask is "own the zero to one build" — a direct hit on the 0-to-1 Exclusion Zone. No honest bridge exists. Documents were never authored. **The folder is still sitting in `data/submissions/harbor_compliance/` as if it passed Stage 0** — next session should either run it through `stage0_placement.py`'s Skip path properly (record in `stage0_skips` ledger, move to `data/archive/skipped/`) or at minimum flag it so it doesn't get accidentally treated as a live Tier 2 later. This is the direct real-world case behind Fix 1 below. |
| Schellman | **Blocked, not authored** | `authoring_packet.json` is 8,111 tokens against an 8,000 cap — refused to build the prompt. Not yet diagnosed why (likely an inflated `evidence_map` from boilerplate-adjacent matching, same family as Fix 3, but not confirmed). |
| amn_healthcare | **Not started** | Packet built, ready at `WAITING_FOR_LLM`. |
| point_c | **Not started** | Packet built. Real example behind Fix 3 (salary range treated as a requirement). |
| meeboss | **Not started** | Packet built. |
| tm2_group_llc | **Not started** | Packet built. Real example behind Fix 3 (salary range + benefits + background-check line treated as requirements). |
| alfa_laval | **Not started** | Packet built. Real example behind Fix 3 (recruiter contact line, application deadline, GDPR disclaimer, sign-off all treated as requirements). |
| nuaxis_innovations | **Not started** | Packet built. Real example behind Fix 1 (required PMP certification, no evidence, not flagged as a hard gap). |
| Inspyr Solutions | **Correctly Skipped by Stage 0, but for a broken reason** | Not part of the 12 (was Skip from the start) — real example behind Fix 2. Its stated rejection reasoning is about "highly regulated industry," completely unrelated to the actual flagged line (US work authorization). Jason is a US citizen — this Skip is very likely wrong. Not re-flipped this session; logged as the concrete case for Fix 2. |

**None of the 4 Stage-2-COMPLETE companies have been `--finalize`d** (no real DB write, nothing sent anywhere) — that's a real decision point for Jason, not an oversight.

---

## The 6 fixes — root cause already traced, not yet implemented

Every one of these was traced to an exact function by reading the live code during this session, not inferred from symptoms. Full plain-language version + cited research is in the findings artifact; this table is the "start here" for implementation.

| # | Plain description | File / function | Confirmed root cause | Proposed fix |
|---|---|---|---|---|
| 1 | Doesn't reliably hard-reject a job that should be an automatic no (0-to-1 role, required certification) | `scripts/evidence_scale.py`, `_SYSTEM_PROMPT` (~line 249–330) + `_GATE_SOURCES` (~line 168) + JSON schema enum (~line 241) | Only 3 valid `gate="HARD"` categories exist: `degree`, `domain`, `role_exclusion`. A required certification/license has **no valid category to gate under at all** — `degree` is academic-degree-only. Separately, `role_exclusion`'s example list (people management, AI/ML ownership, revenue ownership, title above Senior IC) never mentions 0-to-1/greenfield/founding ownership, even though that's a named Exclusion Zone everywhere else in the system (`AGENTS.md`, `candidate_preferences.json`). | Add a 4th gate category `"certification"` to the prompt, schema enum, and `_GATE_SOURCES`. Add "building a product from nothing / solo founding ownership" to `role_exclusion`'s example list. Both are prompt-text edits to an existing, working mechanism — no new architecture. |
| 2 | When it does say no, the stated reasoning sometimes doesn't match the actual requirement it claims to address | `scripts/evidence_scale.py`, `classify_requirement()` (~line 388+) | `_is_administratively_satisfied()`'s own docstring already says citizenship/work-authorization is deliberately unhandled, "left for a separate, more careful pass." The observed failure (Inspyr Solutions: item about citizenship, `reasoning` field about "regulated industry") looks like a single-call LLM attention slip, not a plumbing/pairing bug — `classify_requirement` scores one line per call by design. | Add a cheap, deterministic sanity check right after the LLM call: does `reasoning` share any real (non-stopword) vocabulary with the input `item` text? If not, don't trust the verdict — retry once, then fall back to flagging for human review rather than silently finalizing a rejection. |
| 3 | Job-posting paperwork (salary ranges, recruiter contact lines, deadlines, GDPR/sign-off text) gets treated as real requirements needing evidence | `scripts/build_stage0_fit_gate.py`, `_BOILERPLATE_ITEM_RE` (~line 395–490) + `_is_boilerplate_item()` (~line 574) | A real, substantial boilerplate filter already exists and works for many compensation phrasings. It doesn't cover: bare currency ranges with no surrounding sentence, recruiter name+email lines, "apply by [date]" lines, or generic application-process/GDPR sign-off lines. | Extend the existing regex alternation with 4 new pattern branches (bare `$X–$Y` range; name+title+email; "no later than"/"apply by" deadline phrasing; "we look forward to hearing"/GDPR-application-method sign-offs). Same mechanism, more coverage — not a new filter. |
| 4 | The attribution/credit-checking lint rule (LW-028) throws false positives | `scripts/submission_linter.py`, `check_attribution_verb_strength()` (~line 1734) | It matches an ownership verb (e.g. "built") appearing *anywhere* in the same sentence/bullet as a claim's anchor phrase or metric, with **zero check for whose action the verb actually describes**. Every real false positive this session had the identical shape: "...with the engineer **who built** it" — "who" hands the verb to a different subject, but the check can't parse that. | Add an exclusion: don't count a verb match if it's immediately preceded (within ~3 tokens) by a relative pronoun ("who"/"that"/"which") introducing a different subject. Confirmed against all real instances found this session (Lightcast, Gravitee, Rhino Jetty — all the same "who built it" shape). |
| 5 | Real accomplishment facts get cut off mid-sentence before the writer can use them | `scripts/build_authoring_packet.py`, `_EXCERPT_MAX_CHARS = 500` (line 55) | 500 characters is below even the low end of researched best-practice chunk sizes for this kind of fact-retrieval use (~1,000 characters / ~250 tokens cited as a sensible floor). Confirmed real, multiple times, across several companies' packets this session (excerpts ending mid-word). | Raise the cap toward ~900–1,000 chars, and change the truncation point from a hard character cutoff to the nearest sentence boundary. **Real tradeoff to test, not skip:** the packet also has a separate, deliberate total-token budget (8,000) — this is what blocked Schellman entirely this session. Raising per-excerpt length could push more real jobs over that budget. Test against a real batch before calling this done. |
| 6 | The AI's first draft makes real mistakes on its own (wrong-job content bleed almost happened, gap-confession phrasing almost got written, forbidden punctuation showed up) that only got caught by the safety net | No single file — this is a finding about process, not a bug | Confirms the layered Truth/ATS/HM/Mech safety-net design is doing real, necessary work and should not be loosened. The only real lever here is tightening what the *first* pass is told, not removing any check. | Add this session's specific recurring mistake patterns as an explicit checklist inside `data/authoring_rule_digest.md` (generated by `scripts/generate_authoring_rule_digest.py`) — exact insertion point not yet located, needs a quick read of that script before editing. |

## New request — the biggest open item, not yet scoped

Jason's own words, verbatim, at handoff: *"I am particularly interested in getting the first draft to have as little corrections needed as possible and I wonder if the checker can inform the first draft process over time some kind of mechanic to self improve."*

This is **not** the same thing as fix #6 above (a one-time checklist addition from this session's findings). Jason is asking for a standing feedback loop: every real Stage 2 finding (Truth/ATS/HM/Mech, across every future submission, not just this batch) should somehow accumulate and improve what Stage 1's authoring instructions (the digest) say, so first-draft quality gets measurably better over calendar time instead of staying static.

Real open questions the next session needs to actually think through, not just build against:
- What's the *storage* for this — does every real disposition in `reviews/dispositions.json` across every company get logged somewhere durable and aggregated? There's no such aggregation mechanism today.
- What's the *trigger* for updating the digest — every N submissions? A manual review pass? Automatic the moment a pattern repeats twice (matching this project's own existing "Self-repair protocol" in `generate-submission/SKILL.md`, which already says "fix the mechanism, not the instance" and mechanize a pattern once it recurs)?
- How do you avoid the digest growing indefinitely and blowing the ~1,600-token budget CR-074 was specifically built to protect? This is a real tension against the whole reason the CR-074 packet architecture exists.
- Is this closer to a fine-tuning/few-shot-example problem (add a "here's a real example that was wrong, here's the fix" line, similar to what `scripts/fit_rubric_examples.py` already does for Stage 0's retrieval-augmented few-shot approach) or a pure rule-list growth problem?
- `scripts/fit_rubric_examples.py` (mentioned in `project_applyr.md`'s 2026-08-19 entry: "retrieval-augmented few-shot, wired into the one live LLM call it can help today") is the closest existing precedent in this codebase for "past findings improving a future LLM call" — worth reading that script first before designing something new from scratch.

This needs a real design pass — probably its own CR under `docs/spec/05-change-requests/`, likely via the `product-manager` → `tech-lead` path this repo already uses for anything touching shared architecture, before any code gets written. Don't build this ad hoc inside the same push as the 6 fixes above.

## Research already done (one pass — Jason wants a second pass before implementing)

Sources cited in the findings artifact, by issue:
- **Fix 1** (hard-requirement/certification screening): ATS must-have vs nice-to-have tiering — [Gem](https://www.gem.com/blog/applicant-tracking-system-requirements), [Spark Hire](https://www.sparkhire.com/applicant-tracking-system/best-applicant-tracking-system-features/), [Huntr](https://huntr.co/blog/how-applicant-tracking-systems-work).
- **Fix 2** (reasoning-consistency check): no dedicated search was run — leaned on Fix 4's hybrid-verification research applied to a different pipeline point. **This is the weakest-grounded of the 6 and should be the first one re-researched.**
- **Fix 3** (boilerplate filtering): job-posting NLP "glue text" research — [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2949719124000505), [Hello Recruiter](https://hellorecruiter.ai/glossary/natural-language-processing-in-recruitment), [Candidately](https://www.candidately.com/glossary/nlp-recruitment).
- **Fix 4** (LW-028 false positives): hybrid rule+semantic LLM verification — [Keymakr](https://keymakr.com/blog/preventing-llm-hallucinations-techniques-best-practices-2026/), [hybrid rule+LLM paper](https://eprint.iacr.org/2026/1175), [FutureAGI](https://futureagi.com/blog/what-is-llm-input-output-validation-2026/), [neuro-symbolic verification paper](https://arxiv.org/pdf/2605.26942).
- **Fix 5** (excerpt length): RAG chunk-size best practice — [Milvus](https://milvus.io/ai-quick-reference/what-is-the-optimal-chunk-size-for-rag-applications), [Unstructured.io](https://unstructured.io/blog/chunking-for-rag-best-practices), [Firecrawl](https://www.firecrawl.dev/blog/best-chunking-strategies-rag), [Databricks](https://community.databricks.com/t5/technical-blog/the-ultimate-guide-to-chunking-strategies-for-rag-applications/ba-p/113089).
- **Fix 6 / self-improvement mechanic**: not researched yet at all — this is new as of the handoff instruction itself.

---

## Anti-churn note (per the audit brief's own governing principle)

The core Truth → ATS → HM → Mech → Policy safety-net architecture is **not broken and should not be touched**. Every one of the 4 completed companies had real mistakes caught and corrected before being called done — the net is doing its job. All 6 findings above are upstream of it (screening quality) or inside individual check rules (false positives), never a reason to loosen the net itself. Say this plainly to Jason again if anyone proposes weakening Stage 2 as part of implementing these fixes.
