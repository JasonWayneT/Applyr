# CR-092 — Implementation Plan for 9 Bugs Found in 2026-08-15 Real-JD Batch

**Status: implemented, same session (2026-08-15).** Originally written by a research agent (external best-practice review + code-grounding, no file edits) after a real 9-job CSV batch run surfaced these across Stage 0 triage, Stage 1 authoring, and Stage 2 verification. Jason reviewed the plan and said to execute the recommendations directly, including the flagged open judgment calls. See "Implementation Log" at the bottom for what actually landed, file by file, and what's still open.

**How to use this doc:** each bug below has a scoped fix, an effort/confidence rating, and — where one exists — an explicit open judgment call for Jason. The Prioritized Roadmap at the bottom is the actual sequencing recommendation, including the one real dependency in the set (Bug 2 → Bug 3).

---

## Bug 1 — JD-extraction parser drops real requirements / lets boilerplate leak into buckets

**File:** `scripts/build_stage0_fit_gate.py` — `_extract_sections()` (~539), `_recover_mixed_responsibilities()` (~667), `_is_boilerplate_item()` (~473)

**Problem, confirmed against code:** `_extract_sections()` is a single-pass line-state-machine: each line either matches a `_SECTION_HEADERS` regex and flips the active bucket, matches `_IGNORE_SECTION_HEADERS` and kills the bucket, or gets appended to whatever bucket is active. Every fix landed here so far (CR-086, CR-089, CR-090, several 2026-08-10/11 batches) is a new named-header alternative or a new boilerplate phrase added to an ever-growing regex. This is why it's still catching real JDs 15+ months into hardening: closed-world pattern matching against an open-world problem. McKesson (5/6 "Skills You'll Need" items never bucketed) is a header the regex didn't know; the Greenhouse footer case is ATS chrome that leaked because the ignore-list didn't have that literal string.

**Research:** Boilerplate/footer detection in scraped documents is a studied web-content-extraction problem — `jusText` and the "Boilerplate Detection using Shallow Text Features" line of work use shallow statistical features per text block (link density, sentence length, stopword ratio, block position) rather than exhaustive phrase lists, precisely because phrase lists don't generalize. Current job-posting-parsing literature (2024–2026: "Job description parsing with explainable transformer based ensemble models," ScienceDirect; "Deep Learning-based Computational Job Market Analysis" survey, arXiv 2402.05617) treats JD section/skill extraction as a genuine ML classification task because real-world JD structure is too heterogeneous for a rule table to converge. Practitioners explicitly flag that ATS-platform detection should happen first — a small, closed set of page-chrome strings per platform — as a fundamentally more tractable problem than "detect boilerplate in arbitrary prose."
*(Sources: pypi.org/project/jusText; ccs.neu.edu "Boilerplate Detection using Shallow Text Features"; sciencedirect.com/science/article/pii/S2949719124000505; ar5iv.labs.arxiv.org/html/2402.05617)*

**Fix, scoped:**
1. **Quick win (S):** ATS-platform footer stripping as its own pre-pass, before `_extract_sections()` runs — a small closed set of known page-chrome strings per platform (Greenhouse's "Powered by / Privacy Policy Security Vulnerability Disclosure" is one; Lever/Workday/iCIMS have their own). New `_strip_ats_chrome(jd_text)` called right after `_parse_url_and_jd()`. Fixes 3/9 confirmed boilerplate cases immediately.
2. **Starved-required-bucket problem (M-L), the harder 15.5% (62/401):** add a fallback classifier that fires only when the primary header-match path yields 0-1 required items on a non-thin JD (extends the existing `thin_incomplete`/`extraction_empty` fail-closed shape). For that fallback tier only, score each line by shallow features (bullet-list membership, sentence length, verb-first vs noun-first, tool/degree/years pattern presence) instead of requiring a literal header match. Keeps the deterministic path as default; reserves an isolated, fresh-context LLM read (Jason's own stated acceptable fallback) only for a residual subset even the fallback scorer can't resolve — surfaced as a distinct `extraction_low_confidence` tier in `stage0_fit_gate.json`, never silently drafted against.
3. **Regression fixture (S):** freeze the 62+9 flagged archived JDs as `tests/fixtures/stage0_extraction_corpus/` so every future header/boilerplate tweak is checked against the full known-bad set, not just whichever JD prompted the fix.

**Effort/confidence:** Fix 1 = S/high. Fix 2 = M-L/medium (sound design, needs tuning iteration against the real 62-JD set). Fix 3 = S, ship alongside either.

**Open call for Jason:** what confidence threshold routes a JD into the fresh-context-LLM fallback vs. just flagging `extraction_low_confidence` for human review — a real cost/coverage tradeoff, not a default I should pick.

---

## Bug 2 — Hard-coded tool blocklist is a deny-list; will always miss unseen tools

**File:** `scripts/blocked_tools.py`, `HARD_BLOCKED_TOOLS` (~18)

**Problem:** A flat ~40-entry hand-curated frozenset, imported into both Stage 0 gap classification and `submission_linter.py`'s LR-026. Guidewire's absence isn't a missing entry, it's the entire failure mode: any tool nobody thought to add in advance silently passes through as if Jason had it.

**Research:** Textbook allow-list-vs-deny-list territory (OWASP Input Validation Cheat Sheet, GitHub Security Blog). Consistent finding: allow-lists are preferred whenever the safe set is enumerable and the unsafe set is not — Jason's verified tool set (`data/skills_catalog.json`) is small and enumerable; the universe of tools a JD might name is not. OWASP's standard hybrid — allow-list primary, deny-list as a supplementary "known-definitely-bad" layer — is exactly the two-tier shape already proposed.
*(Sources: cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html; github.blog/2022-03-21-validate-all-things-input-validation)*

For "does this line even name a specific tool" — product-name NER research (arXiv 1812.04662; Fast Data Science's NER survey) converges on gazetteer matching as the cheap reliable baseline when a reference list exists, with capitalization + rule-based heuristics as fallback. Full ML NER is the tool researchers reach for on informal text where gazetteers can't keep up — heavier than this problem needs.
*(Sources: arXiv 1812.04662; fastdatascience.com/natural-language-processing/named-entity-recognition)*

**Fix, scoped:**
1. **Allow-list layer (M):** promote the existing `_load_skills_catalog_terms()` (currently local to `build_stage0_fit_gate.py` ~912) into a shared function in `blocked_tools.py`, mirroring how `HARD_BLOCKED_TOOLS` is already shared.
2. **Tool detection (M):** a requirement line "names a specific tool" if it contains mixed-case mid-sentence capitalization not at line-start (excluding a stoplist of common capitalized JD words), or a known tool-suffix pattern (".com", version numbers, "API"/"SDK"/"Platform" as trailing qualifier).
3. **Three-tier decision in `_classify_one_item()`:** in `HARD_BLOCKED_TOOLS` → hard Skip (unchanged); looks like a named tool and not in the allow-list → **new** soft WARN gap class ("unconfirmed tool — flag for bridge or disclosure"), not silent pass-through; looks like a named tool and is allow-listed → clean anchor (unchanged path).

**Effort/confidence:** M / medium-high on allow-list mechanics (low risk, additive), medium on detection-heuristic precision (needs real-JD tuning against false positives like "Agile" as a capitalized methodology).

**Open call for Jason:** does a step-2 WARN ever escalate to Skip-equivalent, or does it always stay soft? Decide this before Bug 3's fix consumes the same primitive.

---

## Bug 3 — Compound-requirement anchor-matching false-negative

**File:** `scripts/build_stage0_fit_gate.py` — `_item_has_anchor()` (~881), `_classify_one_item()` (~946)

**Problem:** `_item_has_anchor()` iterates the whole anchor vocabulary and returns every substring match anywhere in the line, with zero structural awareness of which part of the line each match covers. "Guidewire Policy Center... policy rating, rules engine" matches on generic "sales"/"workflows" tags and the whole line clears `gap: false`. The fix was already prescribed in prose — `.claude/skills/generate-submission/SKILL.md` (~line 102, the "Humana finding," 2026-07-21): "Compound requirement lines must be split into their sub-concepts before anchor-checking, never evaluated as one unit." That instruction is three weeks old and was never mechanized.

**Research:** The general false-positive failure mode in requirement/compliance-matching systems — matching presence of *any* keyword across a whole clause instead of requiring the match to cover the clause's discriminating content. Closest applied match: "Rapid quality assurance with Requirements Smells" (arXiv 1611.08847) and "From Regulation to Requirements" (arXiv 2607.04448, GDPR/EU AI Act clause extraction, F1 0.815/0.779) — both operate at clause level, not sentence level, because a compliance-relevant sentence usually bundles multiple distinct obligations. Standard mitigation: segment on coordinating conjunctions/commas before matching; weight rare/proper-noun terms higher than common domain vocabulary; require the match to cover the clause's head noun phrase specifically.
*(Sources: arXiv 1611.08847; arXiv 2607.04448)*

**Fix, scoped:**
1. **Clause segmentation (S-M):** `_split_compound_item(item)` — split on `, and `, `,`, ` and `, `/` at conservative boundaries (avoid splitting inside a parenthetical or a multi-word tool name like "Power BI"). Literal mechanization of the existing Humana rule.
2. **Per-clause anchor check (S):** `_classify_one_item()` calls `_item_has_anchor()` once per sub-clause. A line is `gap: false` only if every sub-clause independently anchors; any sub-clause with zero anchor produces a flagged gap citing that specific sub-clause.
3. **Rare/proper-noun weighting (M), sequenced after Bug 2:** once Bug 2's tool-detection primitive exists, use it here — a sub-clause containing a detected tool token requires *that token specifically* to be the anchor. This directly fixes the Mercury Insurance Guidewire case.
4. Extend the Bug-1 regression fixture (or start one) with the Mercury Insurance and Humana lines specifically.

**Effort/confidence:** M / high on segmentation-and-per-clause mechanics (target behavior already specified in writing); proper-noun weighting depends on Bug 2 landing first.

**Open call for Jason:** none major. Confirm the split boundary heuristic stays separate from the existing "or similar" alternatives handling (`_ALT_HEDGE_RE`/`_alt_list_anchor`) rather than merging — different semantics (and vs. or).

---

## Bug 4 — Ground-truth coverage checker groups by claim family, not lens

**File:** `scripts/check_ground_truth_coverage.py`, `_load_claims()` (~68)

**Problem:** Buckets every claim by base `project_id` and unions tags/metrics across every lens sharing that ID (`ACC-111-SCOPE` + `ACC-111-ENTERPRISE` merge). Flags a project "possibly unused" if none of the *merged* tag/metric set appears in the doc, even when only one lens was ever offered in this submission's closed-world packet. The check has no visibility into `authoring_packet.json`'s `evidence_map` at all — always checks against the full global catalog grouped by base ID.

**Research:** A data-modeling correctness bug, not really an external-research question (confirmed correctly scoped by Jason's own framing) — the general shape (over-broad grouping key → false-positive "unused" flags) is well known in dead-code/lint tooling generally. Fix is standard: key by the most specific identifier in play, constrain "available" to what the scope actually offered.

**Fix, scoped:**
1. Key `_load_claims()`'s output by full claim key (`ACC-111-SCOPE`) as `master_claims_tags_only.json` already provides, no unioning across lenses.
2. `check_folder()` reads the target submission's `authoring_packet.json.evidence_map` and checks "unused" only against claim IDs actually offered in that packet's `evidence_map`/`soft_gaps` — not the full catalog.
3. **Guard against reintroducing a false-negative:** if a submission's packet is missing/stale, fall back to current global-catalog behavior with a `note` field explaining the fallback, rather than silently under-checking.

**Effort/confidence:** S-M / high. Contained, one file, immediate regression check (the 3-of-4-runs false-flag pattern from today).

**Open call for Jason:** none — straightforward correctness fix.

---

## Bug 5 — CSV company-name mismatch defeats DB dedup for job-board-mirrored postings

**File:** `scripts/stage0_db_gate.py`, `evaluate_db_gate()` (~234)

**Problem:** Queries `jobs` with `WHERE lower(company) LIKE '%{company_lower}%'` using only the literal CSV `Company` column. A job board mirroring a posting under its own brand ("AdaMarie" carrying a Pinterest listing) means the DB gate runs against a company with no history and never touches Pinterest's real 4-day-old `Applied` row. No code path anywhere reads the JD body text itself.

**Research:** Company-name extraction from free text without full NLP is a decades-old pattern-matching problem (Google Patents US5287278A) and remains the recommended lightweight approach specifically for this shape of input — job postings overwhelmingly self-identify their employer in a small, predictable phrasing set ("About [Company]," "Why [Company]?," "[Company] is looking for," "Join [Company]"). Full NER (spaCy/Stanford) is the heavier alternative for genuinely unstructured text; unnecessary here.
*(Sources: patents.google.com/patent/US5287278; walidamamou.medium.com "How to Automate Job Searches Using Named Entity Recognition")*

Notably: `build_stage0_fit_gate.py`'s own `_SECTION_HEADERS` "culture" bucket regex (~207-233) **already recognizes and captures these exact self-identification phrasings** for a different purpose (bucket routing) — directly reusable, not new ground.

**Fix, scoped:**
1. **New `_extract_self_identified_company(jd_text)` (S-M)** in `stage0_db_gate.py` or a shared util, using the same conservative pattern shape the existing culture-header regex already uses.
2. **Dual-name DB check:** when a self-identified name is found and differs (via the existing `company_token_match()`) from the CSV company, query both names and union terminal rows. Surface the mismatch itself as a new signal (`db_gate_result["company_mismatch"]`) regardless of whether either name has DB history — valuable independent of dedup, flags "this is a board-mirror" for Jason's own awareness.
3. New field in `stage0_fit_gate.json`'s output so a mismatch is visible in the batch table.

**Effort/confidence:** S-M / medium-high. Real misses expected on JDs that never self-identify — acceptable, visible gap (falls back to CSV-name-only, same as today), not a regression.

**Open call for Jason:** when both names have DB history pointing different directions (one clean, one in cooldown) — does the more restrictive result always win (conservative default), or surface as Tier 2 for a human look? Recommend conservative-wins given the pipeline's existing fail-closed posture, but it's a real behavior choice.

---

## Bug 6 — `claim_provenance.json` missing on 2 of 4 real Stage 1 runs

**Files:** `scripts/author_from_packet.py` (~65-105, ~613-623), `scripts/workflow/runner.py` (~372-466), `scripts/contracts.py` (`check_stage1_ready`, ~303-337)

**Root cause, confirmed by direct investigation (not external research):** `claim_provenance.json` is not written by any script. Stage 1 is a human pasting `authoring_prompt.md` into a fresh LLM session, instructed via `_PREAMBLE` to output three fenced blocks (Resume.md, CoverLetter.md, claim_provenance.json) and write each to its own file — nothing mechanically enforces the third file actually lands. The `--invoke` flag that would make this a real code-controlled call is explicitly "not implemented in v1" (`author_from_packet.py` ~613-623). Downstream, `check_stage1_ready()` — the actual orchestrator gate — only hard-requires `authoring_packet.json` (status ready) plus Resume.md and CoverLetter.md. `claim_provenance.json` is read conditionally (`runner.py` ~422) and is explicitly WARN-tier by design (`contracts.py` comment ~377-379: "AC9: claim_provenance is a WARN-tier signal for a human to read, not a blocking gate"). The only hard enforcement is `author_from_packet.py --verify-only`'s `_check_optimization_bar_provenance()` (~398) — documented in both AGENTS.md and CLAUDE.md as a debug worker, not the default orchestrator path.

This is a real instance of a known class worth naming: non-atomic multi-artifact generation where enforcement covers a subset of the promised artifacts. Nothing distinguishes "the LLM forgot the third block" from "the human forgot to save it" — both produce the identical symptom (2 of 3 files present, workflow shows COMPLETE).

**Fix, scoped:**
1. **Close the gate (S), highest-value fix here:** add `claim_provenance.json` to `check_stage1_ready()`'s existing file-existence loop alongside Resume.md/CoverLetter.md — a one-line addition to `for doc in ("Resume.md", "CoverLetter.md"): ...`. Converts silent-missing into "workflow blocks at Stage 1 exit until the human notices and re-runs the author session or `--verify-only`," matching the fail-closed posture already used for the other two files.
2. **Do not** promote `check_claim_provenance()`'s *content* checks (unknown/disabled claim IDs) to a hard gate in this same change — explicitly WARN-tier by design (AC9); conflating "file exists" with "citations are valid" is scope creep beyond this bug.

**Effort/confidence:** S / high. Small, low-risk gate addition against an existing, well-understood gate function. Both known-bad folders already re-authored and now pass (confirmed on disk) — immediate regression check.

**Open call for Jason:** none. Closes a documented gap between AGENTS.md's own claim ("Submissions authored after CR-075 emit claim_provenance.json at compose time") and what the code enforces. Worth a CHANGELOG note once landed, per this repo's own doc-update convention.

---

## Bug 7 — CSV-import report uses a hardcoded date, silently overwrites

**File:** `scripts/import_csv_to_submissions.py`, line ~172

**Problem:** `out = ROOT / "data" / "reports" / "csv_import_slugs_2026-08-14.txt"` — a literal string, not `datetime.now()`-derived. Every invocation, any date, writes to that exact same path via `out.write_text(...)` — full overwrite, no append, no existence check.

**Research:** Standard log/audit-trail rotation convention (Elastic audit trail docs, Wallarm log-rotation guide) converges on: append within a period, rotate to a new timestamped file at a boundary — not one perpetually-reused filename, and not one-file-per-invocation-forever for a high-frequency logger.
*(Sources: elastic.co/blog/elasticsearch-audit-trail-and-log-file-filter-policies-explained; wallarm.com/what/log-rotation)*

Applied to this script's actual usage (confirmed pure audit log, no downstream reader; invoked once per "import session," not continuously): **one-file-per-run, timestamped to the second, is the better fit.** Matches actual usage as an occasional batch job, needs zero merge/append logic, makes "what happened in run N" trivially greppable.

**Fix, scoped:**
```python
out = ROOT / "data" / "reports" / f"csv_import_slugs_{datetime.now():%Y-%m-%dT%H%M%S}.txt"
```
One line at ~172, plus the `datetime` import if not already present.

**Effort/confidence:** S / high. Trivial, no downstream consumers to break.

**Open call for Jason:** none. If a retention cap (auto-prune reports older than N days) is wanted, that's a separate small follow-on, not bundled here.

---

## Bug 8 — Windows move-vs-copy permission errors + PDF hash going stale after recovery

Two sub-issues, investigated separately.

### 8a. `mv` (rename) fails, `copytree` + `rm -rf` succeeds

**Checked directly on this machine — the OneDrive hypothesis does not hold:** `$env:OneDrive` = `C:\Users\Jason\OneDrive`; `[Environment]::GetFolderPath('Desktop')` resolves to plain `C:\Users\Jason\Desktop`. This repo is not under OneDrive folder redirection.

**Research, broader Windows failure class still applies:** Microsoft's own threads on this exact symptom ("explorer.exe locking folders and prevents rename," MS Q&A) converge on any process holding an open handle somewhere under the directory tree blocking a Windows rename — AV real-time scanning, Windows Search Indexer, a backup agent, a lingering git-bash/MSYS process, or a file-watcher (VS Code, a Python process with the folder open) are the common general causes, not cloud-sync specifically. `os.rename`/MSYS `mv` needs one atomic, all-at-once exclusive lock across the whole tree; `shutil.copytree` + separate `rm -rf` never needs that — it proceeds file-by-file even while something transiently touches one file, and the delete step can retry independently.
*(Sources: techcommunity.microsoft.com/discussions/onedrivedeveloper; learn.microsoft.com/en-us/answers/questions/5546965)*

**Fix, scoped:** wherever this repo does a directory move for archive/promote (`scripts/archive_submission.py` ~30/33 uses `shutil.move()`, which tries `os.rename` first and only falls back to copy+delete on cross-device errors, **not** on `PermissionError`), add a retry-with-copy-fallback wrapper: try `os.rename`, catch `PermissionError` specifically, fall back to `shutil.copytree` + `shutil.rmtree` using the same short-backoff-retry pattern already in `scripts/workflow/receipts.py`'s `_atomic_write_json()` (8 attempts, 0.05s×attempt backoff) — reusing an established, already-working pattern in this codebase, not inventing a new one.

**Effort/confidence:** S / high. Small, localized, proven pattern already exists here.

### 8b. Does a plain copy change a SHA-256 hash?

**Checked directly in code — no.** `scripts/workflow/invalidate.py`'s `sha256_file()` is `hashlib.sha256(f.read())` on raw bytes only, no metadata anywhere in the hash. A byte-identical copy cannot legitimately change this hash. The "STALE (Resume.pdf hash mismatch vs receipt)" symptom is therefore evidence the **archived PDF was already out of sync with its receipt before the copy happened** — most likely archived before a later Resume.md edit should have triggered a recompile, or the receipt was recorded against a version compiled after the archive snapshot. Recompiling from the untouched source `.md` fixing it corroborates this.

**Fix, scoped:** no hash-function change needed. Investigate whether `archive_submission.py` (or whatever moved these folders) ever calls a recompile step, or is a pure file move — if pure move, and Resume.md can be edited after archiving with no forced recompile+re-receipt, that's the actual gap, independent of any move/copy question.

**The unexplained mid-session folder move:** no scheduled task, watcher, or background process found in this repo from static code alone that would move folders unprompted. Needs runtime evidence (Windows Event Log around the timestamp, Task Scheduler entries, an IDE auto-archive extension, AV quarantine action) — genuinely unresolved from code, not guessed at.

**Effort/confidence:** 8a = S/high. 8b hash function = confirmed no bug/high confidence. 8b stale-PDF root cause = needs investigation before scoping. Mid-session move = unresolved, needs Jason's runtime forensics.

**Open calls for Jason:** (1) worth an audit-log wrapper around folder moves generally, given this happened once with zero record of cause? (2) should PDF compile become a hard dependency check ("Resume.pdf's hash must match a fresh compile of current Resume.md, or block") rather than trusting the receipt alone? Real design decisions, not bug fixes.

---

## Bug 9 — Mercury Insurance's `verification_passed` never set to `True`

**Files:** `scripts/author_from_packet.py`, `data/authoring_rule_digest.md`, `AGENTS.md` (~247)

**Root cause, confirmed by direct investigation:** `data/submissions/mercury_insurance/draft_manifest.json` has `"verification_passed": false` explicitly (not merely absent), while the sibling KBS manifest has `true`. `verification_passed` does not appear anywhere in `data/authoring_rule_digest.md`, nor in the generated `authoring_prompt.md`/`authoring_prompt_meta.json` for any of these four folders (grepped directly, zero matches). The only place in the whole repo this field is mentioned to a human/agent at all is `AGENTS.md` ~247 — and there it appears only as a historical aside describing the *old, replaced* behavior ("agents used to self-report stage completion (`verification_passed`...)"), immediately followed by an instruction that names only `rubric_score` explicitly as the thing to hand-enter. It never says "and also set `verification_passed: true`." The contract genuinely is silent on this — not buried, absent — and 3 of 4 agents got it right anyway (likely pattern-matching against `rubric_score`'s explicit shape, or seeing a sibling manifest in the same batch); the 4th didn't.

**Fix, scoped:**
1. **S, immediate:** add one explicit line to the generator source behind `data/authoring_rule_digest.md` (`scripts/generate_authoring_rule_digest.py`, not the generated file directly) stating both fields together: "Enter `rubric_score` **and** `verification_passed: true` into `draft_manifest.json` by hand once scoring is complete" — matching `rubric_score`'s existing explicit treatment, closing the asymmetry.
2. Worth knowing: `check_finalize_ready.py`'s own docstring already says it deliberately does not trust `verification_passed` directly — it shells out to real checks instead. This bug is annoying (inconsistent manifests, blocked a real finalize) but not a safety gap.

**Effort/confidence:** S / high. Documentation-generator edit, not a logic change; root cause fully confirmed (absence, not ambiguous wording).

**Open call for Jason:** should `verification_passed` be removed from the schema entirely, given `check_finalize_ready.py` already treats it as untrustworthy and shells out to real checks? Would eliminate this bug class rather than document around it — but it's a schema/contract change (`contracts.py` ~140 currently hard-requires the field present and boolean) touching more surface than the documentation fix needs. Worth asking, not deciding unilaterally.

---

## Prioritized Roadmap

**The one real dependency:** Bug 2 (allow-list + tool-detection primitive) must land before Bug 3's rare/proper-noun weighting step, since Bug 3 explicitly reuses Bug 2's tool-detection output. Everything else is independently sequenced by effort/impact/risk.

**Tier 1 — quick, safe, do first (all S, all high-confidence, no design discussion needed):**
1. Bug 7 — one-line hardcoded-date fix. Zero risk, already destroyed real data once.
2. Bug 6 — add `claim_provenance.json` to `check_stage1_ready()`'s existing file-existence loop. Closes a real silent-data-loss gap; two known-bad folders as instant regression check.
3. Bug 9 — add the missing instruction line to the rule-digest generator. Pure documentation fix, fully root-caused.
4. Bug 1's ATS-chrome pre-pass (independently shippable piece of the larger Bug 1 fix) — fixes 3 confirmed cases today with a bounded, low-risk regex addition.

**Tier 2 — contained, one-file, real logic changes, no cross-bug dependency:**
5. Bug 4 — ground-truth coverage re-keying + packet-scoped check. Self-contained, built-in regression test.
6. Bug 8a — copy-fallback wrapper around directory moves, reusing the existing retry pattern from `receipts.py`. Low risk, real operational pain already hit once.
7. Bug 5 — self-identified-company extraction + dual-name DB check. Reuses existing regex patterns from a sibling module.

**Tier 3 — sequenced pair, needs the design decision first:**
8. Bug 2 — build the allow-list + tool-detection primitive. Has the real open judgment call (does WARN ever escalate?) — decide with Jason before or during implementation, since it shapes the primitive Bug 3 consumes.
9. Bug 3 — clause segmentation + per-clause anchor check (steps 1-2) can ship *before* Bug 2; hold the proper-noun-weighting refinement (step 3) until Bug 2's detection primitive exists, then land as a fast follow-on.

**Tier 4 — larger effort or needs investigation before scoping:**
10. Bug 1's starved-required-bucket fallback classifier — highest-effort item (M-L), real open design question (fallback threshold, LLM-fallback trigger) needs Jason's input before/during build. Recommend building the regression fixture corpus first, independent of the classifier — useful immediately for validating every other Stage-0-adjacent fix in this list (Bugs 2, 3, 5 all touch the same extraction/classification pipeline).
11. Bug 8b (stale-PDF-vs-receipt root cause) — needs a short standalone investigation (does the archive path ever skip a recompile?) before a fix can be scoped. Not blocked on anything else here.
12. Bug 8 (mid-session unexplained folder move) — not a code fix; needs Jason to check Windows Event Viewer / Task Scheduler / AV logs around the relevant timestamp while logs are still fresh. Runs independently of everything else on this list.

**Suggested build order:** 7 → 6 → 9 → 1(ATS pre-pass) → 4 → 8a → 5 → 2 → 3 → 1(fallback classifier + fixture corpus) → 8b investigation, with 8's mid-session-move forensics done by Jason in parallel at any point.

---

**Files read/cited during this research:** `scripts/build_stage0_fit_gate.py`, `scripts/blocked_tools.py`, `scripts/check_ground_truth_coverage.py`, `scripts/stage0_db_gate.py`, `scripts/import_csv_to_submissions.py`, `scripts/claim_provenance.py`, `scripts/author_from_packet.py`, `scripts/workflow/runner.py`, `scripts/workflow/receipts.py`, `scripts/workflow/invalidate.py`, `scripts/contracts.py`, `scripts/patch_optimization_provenance.py`, `scripts/archive_submission.py`, `AGENTS.md`, `.claude/skills/generate-submission/SKILL.md`, `data/authoring_rule_digest.md`, plus direct inspection of the four real submission folders from today's batch.

---

## Implementation Log (2026-08-15, same session)

All 9 bugs / 12 roadmap items addressed. Every code change has a real regression test (not just a manual check) unless noted. Full suite: `python -m unittest discover -s scripts -p "test_*.py"` — 632 tests, 6 failures + 11 errors, **all 17 confirmed pre-existing and unrelated** (missing fixture data folders like `data/submissions/dignifi`, an unrelated `gap_detector.py` classification test, and a pre-existing ~53-item workExperience.md↔master_claims.json catalog-sync gap that predates this session). 3 real regressions this work caused (test fixtures in `test_stage_gate.py` and `test_workflow_authority.py` missing the newly-required `claim_provenance.json`) were found and fixed.

- **Bug 7** (`scripts/import_csv_to_submissions.py`): hardcoded date → `datetime.now()`-derived, one file per run.
- **Bug 6** (`scripts/contracts.py` `check_stage1_ready`): `claim_provenance.json` added to the existence gate. New test in `test_contracts.py`; fixed 3 pre-existing fixtures elsewhere that assumed the old 2-file contract.
- **Bug 9** (`AGENTS.md`): explicit `verification_passed: true` instruction added alongside `rubric_score`'s existing one.
- **Bug 1a** (`scripts/build_stage0_fit_gate.py`): `_strip_ats_chrome()` pre-pass strips the Greenhouse footer before bucketing. Verified against the real corpus: 9→5 boilerplate-leak cases.
- **Bug 4** (`scripts/check_ground_truth_coverage.py`): `_load_claims()` re-keyed by full lens ID instead of `project_id`; adds an `in_packet` signal per flagged claim. Verified: KBS's false ACC-111 flag is gone.
- **Bug 8a** (`scripts/utils.py` new `move_folder_robust()`, wired into `scripts/archive_submission.py` and `scripts/stage0_placement.py`): retry-then-copy+delete fallback for the Windows rename `PermissionError` hit twice this session.
- **Bug 5** (`scripts/stage0_db_gate.py`): `extract_self_identified_company()` + `evaluate_db_gate(jd_text=...)` dual-name check, conservative-wins on disagreement. 11 new tests. **Caveat found during implementation:** the DB gate only checks terminal (Rejected/Closed/Self-Rejected) rows — an `Applied` (in-progress) duplicate, which is what the real Pinterest/AdaMarie case actually was, still isn't caught by this mechanism; the `company_mismatch` signal is surfaced regardless so a human sees it, but this is a narrower fix than the original bug report implied. Worth a follow-up if "already applied under a different name" dedup matters enough to build directly.
- **Bug 2** (`scripts/blocked_tools.py`): `guidewire`/`duck creek`/`majesco` added to the deny-list (immediate fix); new allow-list layer (`load_skills_catalog_terms()`, `looks_like_named_tool()`) flags any other detected-but-unverified tool as a new SOFT gap class rather than silently passing. 3 new tests.
- **Bug 3** (`scripts/build_stage0_fit_gate.py`): `_split_compound_item()` mechanizes the 3-week-old prose-only "Humana finding" rule from `generate-submission/SKILL.md` — a real Oxford-list line (2+ commas) is split and every sub-clause checked independently; one unanchored sub-clause flags the whole line regardless of what else matched. Deliberately conservative (won't split a bare "X and Y" with no commas). 5 new tests; verified against a 40-JD real-corpus sample with zero exceptions.
- **Bug 1b** (`scripts/test_stage0_extraction_corpus.py`, new): a ratchet test against the real `data/archive/submissions/` corpus (not a copied fixtures/ dir, to avoid duplicating private JD data) — fails if the starved-required or boilerplate-leak counts ever regress above today's post-fix baseline, plus hard-locks the 3 confirmed Greenhouse cases.
- **Bug 8b** (investigation only, no code change): confirmed `archive_submission.py` is a pure `shutil.move`, no recompile-before-archive step exists anywhere. This is a real, confirmed gap, but per the original plan's own framing it's a design decision ("should archiving force a fresh-compile-verify, or trust the receipt") that belongs to Jason, not something to decide unilaterally mid-batch. Flagging here rather than picking one.

## Follow-up round (same session, 2026-08-15) — the 4 open items, decided

Jason: "make your best judgment on what is open." Decided and acted on each rather than leaving them pending:

1. **Bug 5's `Applied`-status gap — fixed.** New `_find_active_applications()` in `scripts/stage0_db_gate.py` checks non-terminal (Applied/Backlog/etc.) rows independently of the cooldown/reject path, under both the CSV name and any self-identified mismatch name. Surfaced as `active_application` in `stage0_fit_gate.json` and a batch-table note — flagged for a human look (Tier 2), never an automatic Skip, matching `generate-submission/SKILL.md`'s existing "Kroll-style... belongs in Tier 2" reasoning for same-title active-row duplicates. 5 new tests.

2. **Bug 8b's archive-recompile gap — fixed, WARN not forced-recompile.** Reconsidered the original plan's framing on implementation: forcing every archive operation through a Playwright PDF recompile would make a lightweight file-mover depend on a working Chromium install for a problem that's really about *silent* staleness, not staleness itself. `archive_submission.py` now compares each PDF's hash against its Stage 2 receipt before moving and prints a clear `[WARNING]` (with the exact recompile command) if they don't match — archiving still proceeds, nothing is blocked, but nothing goes silent either. 3 new tests.

3. **Bug 9's schema question — decided against.** `verification_passed` stays in the schema. `check_finalize_ready.py` already doesn't trust it blindly (shells out to real checks instead), so removing it buys little; it does still serve as a human-readable summary field, and removing it would touch `contracts.py`'s hard-required-boolean validation plus every historical submission folder for marginal gain. The actual bug (the field going undocumented) is what got fixed.

4. **Bug 1's fallback classifier — deliberately deferred, not attempted.** The largest, most design-heavy item in the original plan (tuning against the real 61-JD starved-required set, plus an LLM-fallback-threshold decision) — building it at the tail end of an already-large implementation session risked a poorly-tuned heuristic doing more harm than good. The regression fixture (Bug 1b) is explicitly the prerequisite groundwork; building the classifier against it is real future work, not skipped work.

**Real product miss found and fixed in the same pass, not from the original 9-bug list:** Mercury Insurance's Guidewire requirement was in the JD's **Preferred** section, not Required. Even after the Bug 2 fix correctly classified it `gap_class: HARD`, `classify_gaps()` only ever escalated a preferred-bucket item into the REJECT-triggering `flagged_gaps` list when it was a domain-soft SOFT gap — never when it was HARD. So a genuinely unbridgeable, deny-listed tool requirement sitting in "Preferred" instead of "Required" could still clear Stage 0 and reach drafting. Jason: *"it requires experience on a tool i dont have experience with we should have gotten rid of that."* Fixed the mechanism (`classify_gaps()` now escalates preferred `gap_class == "HARD"` items too — this only ever fires for the confirmed deny-list class, never the softer Bug-2 "unconfirmed tool" WARN tier, so it doesn't turn every preferred miss into a Skip) and fixed the instance (Mercury Insurance retracted from `data/submissions/` to `data/archive/skipped/`, ledger entry recorded, re-verified with `python scripts/build_stage0_fit_gate.py data/submissions/mercury_insurance` now correctly printing `Skip — Mercury Insurance: Hard gap(s): ...Guidewire...`). It was never finalized, so no DB row needed cleanup. 2 new tests.

Full suite after this round: 642 tests, same 17 pre-existing/unrelated failures as before, zero new regressions.
