# CR-096 — Stage 1-3 Audit Remediation (the 6 fixes, implemented)

**Status: implemented, same session (2026-08-21), following on from `docs/spec/08-implementation/SESSION-HANDOFF-2026-08-21-stage1-3-audit-remediation.md`.** That handoff traced 6 findings from a real 12-company batch but implemented none of them ("Nothing has been implemented yet"). This CR is the implementation: a refreshed research pass, all 6 fixes landed and verified against the exact real folders/examples that surfaced them, plus two pieces of cleanup the handoff flagged as blocking (Harbor Compliance's stuck folder, Schellman's token-budget block). Two items from the handoff are explicitly **not** done here and are scoped as a roadmap at the bottom: the self-improving first-draft mechanism, and the decision to re-author the 6 remaining test-batch companies.

**How to use this doc:** each fix section states the confirmed root cause (re-verified against live code and real data, not re-cited from the handoff blind), what changed, and the real evidence it was tested against. Three fixes surfaced findings the handoff didn't know about — flagged inline, not silently folded in.

---

## Fix 1 — Certification hard-gate + 0-to-1 role_exclusion example

**File:** `scripts/evidence_scale.py` — `_GATE_SOURCES` (~168), `_SCHEMA` (~241), `_SYSTEM_PROMPT` (~249-330)

**Root cause confirmed:** only `degree`/`domain`/`role_exclusion` were valid `gate="HARD"` categories. A required certification (Nuaxis Innovations: "...and Certified Project Management Professional (PMP) or equivalent certification.") had no valid category to gate under at all. Separately, `role_exclusion`'s example list never named 0-to-1/founding ownership even though it's a standing Exclusion Zone everywhere else in the system.

**Fix:** added a 4th gate category, `"certification"`, to the schema enum and `_GATE_SOURCES`, with explicit handling for the "or equivalent certification" phrasing (does NOT escape the gate — it still requires holding some certification, just not that exact one; only a line that lets plain work experience substitute for holding any certification at all escapes). Added 0-to-1/founding-ownership language to `role_exclusion`'s example list, phrased close to the real Harbor Compliance wording. Also added `"certification"` to `build_stage0_fit_gate.py`'s absolute-Skip fallback tuple (~1460) so the certification category behaves consistently in the rare no-score-available path.

**Verified:** direct `classify_requirement()` calls confirm `_GATE_SOURCES` now includes `certification`; system prompt reviewed against the exact Nuaxis and Harbor Compliance item text. Full suite (`test_build_stage0_fit_gate.py`, 127 tests) still green.

**New finding this session, not in the original handoff — Fix 1 alone did not flip Harbor Compliance:** re-running Stage 0 live against Harbor Compliance post-fix still returned `Tier 2`, not `Skip`. The actual disqualifying sentence ("...to own the zero to one build of our Client Communications Service...") is real and present in the JD, but it lives in the `responsibilities` bucket, not `required`/`preferred` — and `classify_gaps()` only ever runs `evidence_scale.classify_requirement()` over required/preferred items. The closest required-bucket item ("Experience shaping or maturing an early-stage product area...") scored `gate=NONE`, `evidence_level=3`, `confidence=high` — the model reasonably read it as a satisfied skill/experience line in isolation, with no view of the intro paragraph's actual "zero to one" framing. **Extending role_exclusion gating to the `responsibilities` bucket is a real, separate fix with real LLM-call-volume cost on every future JD** (responsibilities lists commonly run 5-10 lines) — not implemented here, flagged for Jason to decide. Harbor Compliance itself was corrected via a manual, documented override (see Cleanup section below), not by the automated pipeline.

---

## Fix 2 — Reasoning/item consistency check

**File:** `scripts/evidence_scale.py` — `_reasoning_grounded_in_item()`, `_call_once()`, `classify_requirement()` (~406-560)

**Root cause confirmed exactly:** Inspyr Solutions' rejection (`gate="HARD"`, `gap_source="domain"` on "Work Requirements: US Citizen, GC Holders or Authorized to Work in the U.S." — Jason IS a US citizen) carried reasoning entirely about an unrelated "highly regulated industry" line elsewhere in the JD. Confirmed via the archived `stage0_fit_gate.json` directly.

**Fix:** after a `gate="HARD"` verdict, check whether the model's `reasoning` shares any real vocabulary with the `item` text (tokenized, stopwords removed, plus a small filler-word exclusion list — see below). If not: retry once. If the retry is also ungrounded: demote `gate` to `NONE` (never auto-Skip on unverifiable reasoning), force `confidence="low"`, and prefix `reasoning` with an explicit `[REASONING/ITEM MISMATCH -- verify this line manually]` marker so it surfaces in the Stage 0 triage table instead of the job silently vanishing.

**One real refinement beyond the handoff's proposed check:** plain `_STOPWORDS` alone wasn't enough — the real Inspyr case shares the generic word "work" between the two unrelated lines ("authorized to Work in the U.S." / "work experience is in Cision...") and would have false-passed as "grounded." Added `_GROUNDING_CHECK_FILLER` (work, experience, role, candidate, requirement(s), position, job, team, years, skills), scoped only to this check, not merged into the shared `_STOPWORDS` that `build_evidence_context()`'s retrieval ranking also depends on.

**Verified:** `_reasoning_grounded_in_item()` called directly against the real Inspyr item + its real reasoning text returns `False` (correctly flagged); against a genuinely-grounded reasoning ("candidate is a US citizen so this requirement is satisfied") returns `True`; against the real Nuaxis PMP item + reasoning returns `True`. Acknowledged limitation, stated in the code: this is a lexical floor, not semantics — a correct-but-fully-paraphrased reasoning can still false-positive. Given the fallback is "demote + flag for human review," never "auto-discard," this is an acceptable failure mode, not a silent risk.

---

## Fix 3 — Boilerplate extraction gap (+ Schellman diagnosis)

**Files:** `scripts/stage0_extract.py` — `_BOILERPLATE_RE`, `_HEADER_LINE_RE`; `scripts/build_stage0_fit_gate.py` — `_BOILERPLATE_ITEM_RE` (defense-in-depth twin)

**Root cause confirmed — more precise than the handoff's guess:** the handoff pointed at `build_stage0_fit_gate.py`'s `_BOILERPLATE_ITEM_RE`. Live tracing found that regex already matches all three real motivating examples (confirmed by direct regex test) — but it only runs inside `_extract_sections()`, the **legacy** regex bucket-splitter, superseded 2026-08-17 by `_extract_sections_llm()` as the default path. The real default path's own boilerplate filter is `stage0_extract.py`'s `_BOILERPLATE_RE` — a much thinner, 4-pattern regex — and `resolve_labeled_buckets()`'s unresolved-hint fallback force-includes any candidate carrying a required/preferred header hint regardless of what the LLM decided, which compounds the gap.

**Fix:** extended `_BOILERPLATE_RE` (the real default path) with pattern families for: bare currency ranges with K/M suffixes and a `Compensation Range:` label; any line containing an email address (a real requirement line never carries one); "no later than" / "apply by" / "application deadline" phrasing; GDPR / application-method / sign-off boilerplate; background-check consent lines; generic compensation-disclaimer and benefits-paragraph phrasing not already covered. Mirrored the same additions into `_BOILERPLATE_ITEM_RE` for defense-in-depth (that path is still exercised by the test suite under `STAGE0_SECTION_MODE=deterministic`).

**Verified against all 11 real flagged lines** across Point C (bare `$` range, compensation-commensurate disclaimer), Tm2 Group (`Compensation Range: $185.9K - $204.1K`, benefits paragraph, background-check consent), and Alfa Laval (two recruiter name+email lines, an application deadline, a GDPR disclaimer, a sign-off line) — all now correctly filtered. Cross-checked against every other real `required`/`preferred` item in those 6 folders to confirm zero new false positives.

**Schellman diagnosis (was "not yet diagnosed" in the handoff):** confirmed the same family, two additional real contributors to its 8,111-token overflow: a bare section-header leftover ("Education, Work Experience And Certifications", 32 chars, clears `_MIN_CHARS`) and a remote-work culture-framing sentence ("At Schellman, we strive to provide a flexible and balanced environment... opportunity to work remotely...") both landed in `required`, feeding 2 of 27 evidence_map entries. Added a specific header-label pattern to `_HEADER_LINE_RE` and a remote-work-framing pattern to `_BOILERPLATE_RE`. **This alone drops Schellman's evidence_map from 19 to 17 items and its packet from 8,111 to 7,408 tokens (ready, was incomplete)** — see Fix 5 for why it goes back over budget once the excerpt-length change is added on top.

---

## Fix 4 — LW-028 attribution false positives

**File:** `scripts/submission_linter.py` — `_has_unattributed_verb()`, `_ANCHOR_PROXIMITY_CHARS`, `check_attribution_verb_strength()` (~1647-1830)

**Root cause confirmed, plus one the handoff missed:** the handoff claimed all 6 real false positives (Lightcast, Gravitee, Rhino Jetty) shared one shape — "...with the engineer **who built** it." Live verification against the actual documents found this true for 2 of 3 named cases, and found the 3rd had two entirely separate, distinct causes:

1. **Lightcast** — exactly the "who built it" shape. Fixed by excluding a verb match immediately preceded (within 3 tokens) by a relative pronoun ("who"/"that"/"which") introducing a different subject.
2. **Gravitee** — same "who built it" phrase, but the compound run-on sentence *also* independently contains "...and separately designed and built my own AI tooling..." — a real, correctly-owned, unrelated accomplishment (ACC-401) sharing one long comma-spliced sentence with the ACC-120 anchor phrase. The pronoun fix alone did not clear this. Added a proximity constraint (`_ANCHOR_PROXIMITY_CHARS = 100`) scoped to the metricless-claim anchor path only: a verb occurrence only counts if it falls within 100 characters of an actual anchor-phrase occurrence in the same unit.
3. **Rhino Jetty — NOT fixed, root cause is different, out of bounds for this session.** The flagged sentence ("Partnered with Customer Experience and an Upgrades team to build and deploy phased voluntary migration tooling...") is a close paraphrase of `master_claims.json`'s own `ACC-104-OPS.allowed_claims` field: `"Built and deployed phased voluntary migration tooling that transitioned ~700 high-risk legacy accounts at renewal"` — the catalog's own authored allowed-claim text uses ownership-tier language on a project_id whose lenses are tagged `attribution: "contributed"`. This is a data-consistency issue inside `master_claims.json` itself, not a linter parsing bug — the linter is correctly catching a real contradiction in the claims catalog. Per the handoff's own explicit boundary ("do not touch workExperience.md / master_claims.json content — none of this workstream's findings originate there"), this was **not corrected**. Flagged here for a future session that's allowed to touch that file: either loosen `ACC-104`'s attribution tag if the underlying fact is closer to owned, or rewrite `ACC-104-OPS.allowed_claims` to drop "Built and deployed" in favor of partnership framing consistent with its own `attribution: "contributed"` tag.

**Verified:** `check_attribution_verb_strength()` run directly against the real Resume.md/CoverLetter.md for all three companies. Before: 1/1/1 findings. After: 0/0/1 (Lightcast and Gravitee clean, Rhino Jetty's real, separate issue still fires — correctly, given its actual cause). Full `test_submission_linter.py` (54 tests) green throughout.

---

## Fix 5 — Excerpt length + sentence-boundary truncation

**File:** `scripts/build_authoring_packet.py` — `_EXCERPT_MAX_CHARS`, `_truncate_at_sentence()` (~55-80, ~761-870)

**Root cause confirmed, broadly:** every excerpt hitting the old 500-char cap ended with a hard `[:max_chars]` slice regardless of word/sentence boundaries. Confirmed real and common — sampled several not-yet-authored packets (Point C, Tm2 Group) and found the majority of excerpts at exactly 500 chars, ending mid-word ("...go-f", "...consistently read it as i", "...engineering owned what to fix in").

**Fix, two parts, both applied at all 4 truncation sites in the file:**
1. Raised `_EXCERPT_MAX_CHARS` from 500 to 900 chars (research-cited floor for RAG-style fact retrieval is ~1,000 chars; 900 was chosen after the real tradeoff test below).
2. Added `_truncate_at_sentence()`: cuts at the last real sentence boundary at-or-before the limit, falling back to the hard cut only when no boundary exists at all inside the budget.

**Real tradeoff, measured, not hidden — this is the one fix the handoff explicitly asked to be tested against a real batch before finalizing.** Swept `_EXCERPT_MAX_CHARS` across 500-1000 against all 12 real test-batch folders:

| Cap | Schellman (17 req. items) | All other 11 folders |
|---|---|---|
| 500 (post Fix-3 cleanup) | ready, 7,408 tokens | all ready, comfortable margin |
| 600 | incomplete, 8,039 tokens | all ready |
| 700 | incomplete, 8,271 tokens | all ready |
| 800 | incomplete, 8,878 tokens | all ready |
| 900 (chosen) | incomplete, 9,132 tokens | all ready |

Schellman is the only real casualty at any cap above ~580 — it has an unusually large number of real required items (17, most JDs in the batch have 7-12), so nearly every excerpt in its packet hits whatever cap is set, and the token cost compounds linearly with item count. Below ~580 the mid-word-truncation fix is real but the content-completeness gain is marginal; 900 delivers the full researched benefit for every normal-sized JD (10 of 12 real folders, plus Harbor Compliance which is moot — it's Skipped now) at the cost of one already-known, already-flagged outlier. **Chose 900, accepting Schellman needs a separate accommodation** — not solved here. Options for a future session: a per-JD token-budget override, an evidence_map item cap that trims lower-priority rows before shrinking every excerpt uniformly, or accepting Schellman needs human authoring outside this pipeline.

**Verified:** all 4 truncation call sites updated; regenerated packets for Point C, Tm2 Group, Alfa Laval, Meeboss, Amn Healthcare, and Nuaxis Innovations (all "Not started" in the handoff's status table — no Stage 1 draft was run, only the deterministic packet-build step) confirm every excerpt now ends at a real sentence boundary. `test_build_authoring_packet.py` (77 tests) green.

---

## Fix 6 — Authoring digest self-check

**Files:** `scripts/generate_authoring_rule_digest.py` (new `## 11. Before You Finish` section), `data/authoring_rule_digest.md` + `.version` (regenerated)

**Fix:** added a compact, prominent final section restating the three recurring first-draft mistakes from this round (wrong-job content bleed, gap-confession language, forbidden punctuation) as an explicit pre-submission checklist — even though rules 1/5/7 already state each individually, the audit found the model still produced each mistake at least once before Stage 2 caught it. Positioned last in the digest (recency), kept to 3 short bullets to stay inside the token budget.

**Budget tension, real:** the addition initially pushed the digest to 8,481 chars (soft target is 8,000, hard limit 10,000 — both are enforced in code, not just documented). Trimmed wording to land at 7,989 chars, under the soft target. `generate_authoring_rule_digest.py --check` and the 19-test suite both green.

**Downstream effect caught and fixed:** the digest version bump (`9cf82b25708f5234` → `cd876168698d85f1`) meant the 6 packets already regenerated for Fix 5 were stamped with the stale version. Rebuilt all 6 a second time to pick up the correct `rule_digest_version`.

---

## Cleanup — Harbor Compliance folder (blocking issue, not one of the 6 fixes)

The handoff flagged this as a folder sitting in `data/submissions/harbor_compliance/` "as if it passed Stage 0" that needed either a proper Skip or, at minimum, a flag. Given the Fix 1 finding above (the pipeline cannot detect this case automatically — the disqualifying sentence lives in a bucket that's never gate-checked), this was corrected as a manual, documented human override rather than waiting on a future automated fix:

- `stage0_fit_gate.json` corrected in place: `decision`/`tier` → `SKIP`/`Skip`, `extraction_override: true`, an `override_note` explaining exactly why the automated check missed it (see Fix 1), and a corrected `exclusion_zone_check` (was `"clear"`, now explicitly notes the override).
- Ran through `stage0_placement.apply_stage0_placement()` — the real mechanism, not a hand-rolled move — which recorded the skip in the `stage0_skips` SQLite ledger (verified: URL, company, title, skip_reason, timestamp, slug, archive_path all present) and moved the folder to `data/archive/skipped/harbor_compliance/`.

---

## Full verification

`python scripts/run_all_tests.py` — 34/34 suites pass (Python + Vitest), 0 failures, run after every fix above landed. No suite was skipped or excluded to get a clean run.

---

## Addendum (2026-08-21, same-day follow-up) — the 3 findings above are now resolved

Jason asked to address the 3 findings this CR surfaced (not just log them) with a research pass first. All 3 are implemented and verified:

- **Harbor Compliance / responsibilities-bucket gap (Fix 1 follow-up).** Added `screen_responsibilities_for_exclusion()` in `scripts/build_stage0_fit_gate.py`: a two-tier screen matching the cheap-tier/LLM-escalation pattern standard in cost-effective LLM triage research (route the easy majority to a near-free filter, escalate only real candidates to the expensive judgment). Tier A (`_DETERMINISTIC_0TO1_BUILD_RE`) gates unambiguous "own/lead the zero-to-one build" phrasing directly, with no LLM call — found live that escalating this exact phrase to the real classifier collided with Jason's own real employer name "Zero To Sixty" and confused the small local model into reading it as a match. Tier B (team-management/revenue/AI-ownership phrasing, genuinely needs judgment) still escalates to `evidence_scale.classify_requirement()`. Verified end-to-end: Harbor Compliance's real responsibilities text now produces a `gate="HARD"`/`role_exclusion` hit that correctly disqualifies via the existing `compute_fit_score()` path, with zero false positives across every other real folder's responsibilities.
- **Schellman / token-budget outlier (Fix 5 follow-up).** Added `_shrink_excerpts_to_budget()` in `scripts/build_authoring_packet.py`: builds every excerpt at the full 900-char research-backed cap first, and only if the assembled packet actually exceeds `_TOKEN_BUDGET` does it shrink proportionally across every excerpt (down to a 400-char floor, always at a sentence boundary) — adaptive to how many evidence_map items a JD actually has, instead of one hardcoded constant that either shortchanges every normal JD or leaves an outlier blocked. Matches RAG token-budgeting research's "score-weighted truncation, adapt to the retrieval set's real size" pattern. Schellman: 9,132 → 7,400 tokens, now `ready`. Every other real folder unaffected (never enters the shrink path).
- **Rhino Jetty / `master_claims.json` inconsistency (Fix 4 follow-up).** Corrected `ACC-104-OPS`'s `text`/`allowed_claims` in `data/master_claims.json` — "Built and deployed..." (ownership-tier) replaced with "Partnered with Engineering, Upgrades, and CX to deliver..." (partnership-tier), matching WE's own explicit MET-10 hedge verbatim ("CONTRIBUTED... 'Partnered on' / 'designed the export requirements and tooling that enabled'") and ACC-104-OPS's own already-correct `cover_story`, which had never been out of sync. Regenerated `master_claims_tags_only.json` via `generate_context_pack.py` per `CLAIMS_STANDARD.md`'s hygiene checklist; `audit_claims_coverage.py --strict` clean. Corrected the already-authored Rhino Jetty `Resume.md` bullet to match ("build and deploy" → "deliver"); confirmed LW-028 now clears for all 3 real cases (Lightcast, Gravitee, Rhino Jetty). Running the folder through `run_submission.py --resume` correctly detected the content change, restarted Stage 2 from Truth (by design), and re-synced dispositions for every finding whose content was unchanged — the folder is at `WAITING_FOR_HUMAN` on exactly one already-standing, unrelated requirement (`hm.critical_read`, never disposed before this edit either) that needs Jason's own read, not something to fabricate.

Full test suite (`python scripts/run_all_tests.py`) re-run clean (34/34) after all three.

## Roadmap — the two items explicitly deferred, for a future session

Per the handoff's own instruction, these are **not** done here and should not be started ad hoc inside a fixes-only push. See `docs/spec/08-implementation/SESSION-HANDOFF-2026-08-21-stage1-3-audit-remediation.md`'s "New request" section for the full framing.

### Piece A — Self-improving first-draft mechanism (needs a CR of its own)

Jason's ask: "I am particularly interested in getting the first draft to have as little corrections needed as possible and I wonder if the checker can inform the first draft process over time some kind of mechanic to self improve."

Suggested sequencing, in pieces:
1. **Read `scripts/fit_rubric_examples.py` first** — the doc's own-named closest precedent ("retrieval-augmented few-shot, wired into the one live LLM call it can help today"). Understand exactly how it aggregates and surfaces past examples before designing a new mechanism from scratch.
2. **`product-manager` pass**: scope the actual trigger and storage questions as a locked spec, not left open — specifically: (a) what's the durable aggregation point for every real Stage 2 finding across every future submission (today `reviews/dispositions.json` is per-folder, nothing aggregates across folders); (b) what triggers a digest update — a fixed cadence (every N submissions), a manual review pass, or automatic once a pattern repeats twice (matching `generate-submission/SKILL.md`'s existing "fix the mechanism, not the instance" self-repair protocol); (c) is this a rule-list-growth problem or a few-shot-example problem, closer to what `fit_rubric_examples.py` already does for Stage 0.
3. **`tech-lead` pass**: design the actual aggregation + digest-update mechanism against the locked spec, with an explicit answer to the token-budget tension (the digest already sits at 7,989/8,000 chars after Fix 6 — there is very little room left to grow before this mechanism needs a pruning/rotation strategy, not just addition).
4. Implementation only after both passes are locked, per this repo's own SDD process.

### Piece B — Re-author the 6 remaining test-batch companies

amn_healthcare, point_c, meeboss, tm2_group_llc, alfa_laval, nuaxis_innovations — all "Not started," packets rebuilt against the fixed pipeline as part of this CR (see Fix 5/6). Real authoring-LLM cost (cloud, not local) is the reason this isn't done automatically. Decision for Jason: re-author now against the fixed pipeline (arguably the cleaner audit close-out — no pre-fix output to redo later), or hold until Piece A's design is further along so these 6 also benefit from whatever comes out of it.

Two things worth deciding alongside this, surfaced by this session but not resolved:
- Whether to extend Fix 1's role_exclusion gating to the `responsibilities` bucket (real LLM-call-volume cost per JD going forward) — Harbor Compliance's actual root cause, not fixed here.
- Whether to correct `ACC-104`'s attribution tag or its `allowed_claims` text in `master_claims.json` (Fix 4's Rhino Jetty finding) — needs a session explicitly scoped to touch that file, per this session's own boundary.
