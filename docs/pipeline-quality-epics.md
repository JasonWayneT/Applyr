# Pipeline Quality Epics — Implementation Handoff

**Created:** June 2026  
**Status:** Ready for implementation — partially in progress (uncommitted; see Related Work below)  
**Context:** This document was produced after a manual audit revealed that the pipeline's generated cover letters and resumes systematically failed on forbidden language, generic hooks, weak proof density, and missing B2B SaaS legibility signals. These epics harden the pipeline to produce application-ready output deterministically.

**Supersedes:** `CODE_FIXES.md` (repo root, dated 2026-06-25, since removed from the repo —
content available in git history) — that file is the earlier, less-structured audit this doc's epics
were built from. Fix 1–7 there map roughly to Epics 1, 7, 3, 6, 5, (completion verification — not yet
its own epic here), 7 respectively. This doc is the working plan.

**Related work — different scope, same session family, do not treat as redundant:**
[docs/spec/08-implementation/CR-053-fit-rubric-overhaul-epics.md](spec/08-implementation/CR-053-fit-rubric-overhaul-epics.md)
covers CR-053 (job-fit scoring accuracy), CR-054 (pipeline silently reporting success on a failed
draft — note Fix 6 in `CODE_FIXES.md` above, the incomplete `napster_corp_` folder, is the same failure
class found independently in that doc's diagnosis; the original `CODE_FIXES.md` audit has been
removed from the repo but is available in git history), and CR-055 (jobs killed before they ever reach
scoring). This doc is about the quality of the *document* once a job has already passed the fit gate
and is being drafted; CR-053/054/055 is about whether the *right job* reached drafting in the first
place, and whether the pipeline tells the truth about whether drafting actually succeeded. Both are
real, both are in flight, neither replaces the other.

---

## Before You Start — Orient Yourself

Read these files first, in order:

1. `CLAUDE.md` — The ground rules: forbidden language, verified metrics (MET codes), ACC codes, anti-hallucination rules. These are the constraints the linter encodes.
2. `scripts/draft_compiler.py` — The main pipeline orchestrator. Most epics hook in here.
3. `scripts/quality_checker.py` — Existing quality checks. The linter extends this.
4. `scripts/cover_letter_renderer.py` — Current CL generation. Epic 2 refactors this.
5. `scripts/jd_tailoring.py` — JD parsing and claim scoring. Epics 3, 7, 9 extend this.
6. `scripts/cover_letter_structure.py` — Current block/prose assembly. Epic 2 replaces this flow.
7. `scripts/critique_retry.py` — Existing retry logic. Epic 6 extends this.
8. `data/conversion_rubric.md` — The scoring rubric (R1–R8 resume, C1–C5 cover letter). Thresholds: Resume 70+, CL 65+ = CONVERT-READY.
9. `data/workExperience.md` — Ground truth for all metrics and claims.

---

## Architecture Context — Current Pipeline Flow

```
JD capture (scrape_new_jobs.ts)
    → pre-score (pre_score_jobs.py)
    → eval opportunity (eval_submission.py)       ← fit score gate
    → draft compilation (draft_compiler.py)
        → select claims (jd_tailoring.py)
        → build resume (local_draft_stages.py)
        → build CL (cover_letter_renderer.py
                     → cover_letter_structure.py
                     → cover_letter_plan.py)
        → quality check (quality_checker.py)      ← current check (insufficient)
        → compile PDF (compile_single.py)
    → eval submission (eval_submission.py)        ← rubric scoring (after the fact)
    → submission stored with status BLOCKED/READY
```

**The core problem:** Quality checks run after compilation. Failures are discovered late, stored as BLOCKED, and require manual intervention. These epics move quality enforcement upstream and make it structural rather than probabilistic.

---

## Build Order and Dependencies

```
Epic 1 (Linter)         ← No dependencies. Build first.
Epic 7 (Hook)           ← No dependencies. Build second.
Epic 3 (Proof Select)   ← No dependencies. Build alongside 7.
Epic 4 (Summary)        ← No dependencies. Build alongside 7.
Epic 2 (Skeleton)       ← Requires Epics 7, 3. Major refactor.
Epic 6 (Critic)         ← Requires Epic 2.
Epic 9 (Gap Ack)        ← Requires Epic 2.
Epic 8 (Eval Gate)      ← Requires Epic 6.
Epic 5 (Library)        ← Separate session. See brief at bottom.
```

**Recommended sprint sequence:**
- Sprint 1: Epics 1, 7, 3, 4 (all independent, high ROI)
- Sprint 2: Epic 2 (skeleton refactor — this is the big one)
- Sprint 3: Epics 6, 9 (build on the skeleton)
- Sprint 4: Epic 8 (gate logic)
- Sprint 5: Epic 5 (separate session)

---

## Epic 1 — Robust Submission Linter

**Goal:** Every submission that violates a hard rule is blocked from compilation before a PDF is generated. No forbidden language, placeholders, or disabled claims ever reach an output file.

**New file:** `scripts/submission_linter.py`  
**Modified files:** `scripts/compile_single.py`, `scripts/draft_compiler.py`, `scripts/quality_checker.py`

### Implementation Notes

Structure the linter as a declarative rule engine. Rules live in a config dict (or YAML if you prefer externalizing them), not as scattered conditionals. Each rule has an ID, severity, check type, and a human-readable message with a suggested fix.

```python
@dataclass
class LintRule:
    rule_id: str
    severity: Literal["HARD_BLOCK", "WARN", "INFO"]
    check_type: Literal["regex", "keyword", "structural", "length"]
    pattern: str | None
    message: str
    suggestion: str

@dataclass
class LintViolation:
    rule_id: str
    severity: str
    message: str
    suggestion: str
    line: int | None

@dataclass
class LintResult:
    passed: bool          # False if any HARD_BLOCK violations exist
    blocks: list[LintViolation]
    warns: list[LintViolation]
    infos: list[LintViolation]
    document_type: Literal["resume", "cover_letter"]
```

The linter detects document type from filename (`CoverLetter.md` vs `Resume.md`) and applies document-specific rules (e.g., no bullet points only applies to cover letters).

**Integrate into `compile_single.py`** as a pre-flight check. If `result.passed` is False, print the blocks, write them to a `lint_report.json` in the submission folder, and exit with code 1 (no PDF generated).

**Integrate into `draft_compiler.py`** after CL/resume text is assembled but before `generate_pdf()` is called. Same gate logic. This catches failures at draft time, not just at manual recompilation.

### Stories

**Story 1.1 — Core linter infrastructure**
- Create `scripts/submission_linter.py` with `LintRule`, `LintViolation`, `LintResult` dataclasses
- Implement `lint_document(text: str, doc_type: str) -> LintResult`
- Implement rule engine: iterate rules, check by type (regex/keyword/structural/length), collect violations
- Acceptance: `lint_document` returns a `LintResult` with correct severity assignments

**Story 1.2 — HARD_BLOCK rules**

Rules to implement (document these in the rule config with IDs):

| Rule ID | Pattern / Check | Applies To |
|---------|----------------|-----------|
| LR-001 | `I am excited to apply` | CL |
| LR-002 | `I am excited about` | CL |
| LR-003 | `I am confident that` | CL |
| LR-004 | `proven track record` | Both |
| LR-005 | `I am writing to express` | CL |
| LR-006 | `—` (em dash character) | Both |
| LR-007 | phone redaction placeholder (LR-007) | Both |
| LR-008 | email redaction placeholder (LR-008) | Both |
| LR-009 | Keywords: leverage, passionate, dynamic, innovative, seamless, transformative, synergy, tapestry, revolutionize | Both |
| LR-010 | Bullet point lines (`^\* ` or `^- `) | CL only |
| LR-011 | Internal codenames: "Airo", "Platform Data Remediation", "Core B2B SaaS Platform", "Critical Save Program", "White Glove Accounts", "Centralized Contact Database" | Both |
| LR-012 | Disabled claim reference: "$800K Canadian" | Both |

- Acceptance: Each rule blocks compilation when the pattern is present; passes when absent

**Story 1.3 — WARN rules**

| Rule ID | Check | Applies To |
|---------|-------|-----------|
| LW-001 | CL word count < 220 or > 450 | CL |
| LW-002 | Resume word count > 750 | Resume |
| LW-003 | Transition openers: "Furthermore", "Moreover", "Additionally", "In addition" | Both |
| LW-004 | Generic qualifiers: "resonated deeply", "aligns perfectly", "highly collaborative" | Both |
| LW-005 | Missing partner from verified list (Engineering, DBA, DevOps, CX, Support, Sales, Account Management, Legal, InfoSec, Product Marketing, Executive Leadership) — warn if a cross-functional partner is mentioned that isn't on this list | Both |

- Acceptance: WARN violations appear in lint report but do not block compilation

**Story 1.4 — INFO rules**

| Rule ID | Check |
|---------|-------|
| LI-001 | CL word count in yellow zone (220–250 or 420–450) |
| LI-002 | No corresponding PDF found for this MD file |
| LI-003 | CL has fewer than 3 paragraphs |

**Story 1.5 — Wire into compile_single.py**
- Before converting MD to HTML, call `lint_document(md_text, doc_type)`
- If `result.passed` is False: print each block violation, write `lint_report.json`, exit(1)
- If warnings exist: print them but continue
- Acceptance: `python scripts/compile_single.py data/submissions/hubspot/CoverLetter.md ...` exits with code 1 and no PDF if a HARD_BLOCK rule fires

**Story 1.6 — Wire into draft_compiler.py**
- After assembling CL/resume text, before calling `generate_pdf`, run `lint_document`
- On HARD_BLOCK: raise `DraftingPipelineError` with lint report details
- Store lint report in submission folder regardless of pass/fail
- Acceptance: Pipeline-generated draft with forbidden language raises before PDF is generated

**Story 1.7 — CLI mode**
- `python scripts/submission_linter.py data/submissions/hubspot/` — lints all MDs in the folder
- `python scripts/submission_linter.py data/submissions/` — lints all submissions
- Outputs a summary table: submission name | document | status | violation count
- Acceptance: Running against the current submissions folder produces a clean report

**Story 1.8 — Tests**
- `scripts/tests/test_submission_linter.py`
- One test per HARD_BLOCK rule: assert `passed=False` when pattern present, `passed=True` when absent
- Test document-type specificity (bullet points only block in CLs)
- Test CLI output format

---

## Epic 2 — Structured CL Skeleton with Sequential Context Injection

**Goal:** Replace free-form CL generation with a four-slot scaffold. Each slot has hard constraints on content type and length. Slots are generated sequentially — each slot sees what came before, so cohesion is preserved. Failures in a single slot trigger slot-level regeneration, not full-letter regeneration.

**New file:** `scripts/cover_letter_slots.py`  
**Modified files:** `scripts/cover_letter_renderer.py`, `scripts/draft_compiler.py`  
**Feature flag:** `COVER_ENGINE=v2` (keep v1 as fallback until v2 is validated)

### Implementation Notes

The four slots:

```
HOOK      → One sentence. Company observation. No "I". Under 35 words.
PROOF_1   → One paragraph. Strongest claim for this JD. 60–100 words.
PROOF_2   → One paragraph. Second claim or gap acknowledgment. 60–100 words.
CLOSING   → One or two sentences. Direct call to action. Under 30 words.
```

Each slot is generated with its own LLM call. The prompt for each slot includes:
- The JD text
- The pre-selected claims (locked before generation starts — see Epic 3)
- All previously generated slots (accumulated context)
- The slot-specific constraints (injected as system-level instructions)

This means slot 4 (closing) sees the full letter so far and can echo themes. But the LLM is only asked to write one thing — the closing — so it can't drift into rewriting the other slots.

```python
@dataclass
class CLSlot:
    slot_type: Literal["HOOK", "PROOF_1", "PROOF_2", "CLOSING"]
    content: str | None = None
    attempts: int = 0
    passed_lint: bool = False

@dataclass 
class CLSlotConstraints:
    max_words: int
    min_words: int
    forbidden_openers: list[str]  # e.g. ["I am", "My background"]
    required_content_type: str    # e.g. "company observation", "proof with metric"
    no_i_statements: bool
```

**Key design decision:** The hook (slot 1) is generated by Epic 7's `generate_hook()` function and is passed in as a locked string. The skeleton generator does not re-generate the hook — it only receives it and passes it as context into the subsequent slots.

**Cohesion mechanism:** Each slot prompt ends with: *"The previous content is: [accumulated slots]. Write only the [SLOT_TYPE]. Do not repeat what has already been said. Echo one word or theme from the opening if natural."*

### Stories

**Story 2.1 — CLSlot and CLSlotConstraints dataclasses**
- Define in `scripts/cover_letter_slots.py`
- Define constraints per slot type as module-level constants
- Acceptance: Dataclasses import cleanly; constraints are readable without code knowledge

**Story 2.2 — Sequential slot generator**
- `generate_cl_slots(hook: str, pre_selected_claims: list, jd_text: str, plan: CoverLetterPlan) -> list[CLSlot]`
- Generates PROOF_1, PROOF_2, CLOSING in sequence (hook is already provided)
- Each call accumulates prior slots into context
- Acceptance: Output is a list of 4 filled CLSlot objects

**Story 2.3 — Per-slot linter validation and retry**
- After each slot is generated, run slot-specific lint checks (word count, no forbidden openers, constraint compliance)
- If slot fails: regenerate that slot only (max 3 attempts)
- If slot still fails after 3 attempts: log WARN, use best attempt, continue
- Acceptance: A slot that triggers a forbidden opener on first attempt is regenerated; the letter still completes

**Story 2.4 — Slot assembly into final CL text**
- `assemble_cl_from_slots(slots: list[CLSlot], header: str) -> str`
- Joins slots with proper paragraph breaks
- Prepends header block (name, contact, salutation) and appends sign-off
- Acceptance: Output is valid markdown CL matching the expected format

**Story 2.5 — Wire into cover_letter_renderer.py with feature flag**
- When `COVER_ENGINE=v2`: use slot generator path
- When `COVER_ENGINE=v1` (default during transition): use existing path
- Acceptance: Both paths produce valid CLs; v2 path uses slots

**Story 2.6 — Wire hook as fixed input**
- `generate_cl_slots` accepts `hook: str` as its first argument
- Hook is generated by `generate_hook()` (Epic 7) before this function is called
- Acceptance: Hook content is identical in generated CL and in cover_letter_plan.json

**Story 2.7 — Tests**
- Test sequential context accumulation (slot 3 context includes slots 1 and 2)
- Test per-slot retry on lint failure
- Test assembly output format
- Mock LLM calls for deterministic testing

---

## Epic 3 — Proof Point Pre-Selection

**Goal:** Before any CL generation begins, rank all active claims against the JD and lock the top 2. The CL generator cannot choose weaker claims because choices are made before it runs.

**Modified files:** `scripts/jd_tailoring.py`, `scripts/draft_compiler.py`, `scripts/cover_letter_plan.py`

### Implementation Notes

The `score_claim_for_jd` function in `jd_tailoring.py` already scores individual claims. This epic adds a selection layer on top.

```python
def select_cl_claims(
    jd_profile: JdProfile,
    catalog: ClaimCatalog,
    resume_claim_ids: list[str],  # exclude claims already in resume
    n: int = 2
) -> list[Claim]:
    """
    Score all active claims against JD profile.
    Filter: disabled claims, claims already prominent in resume.
    Rank: by JD relevance score.
    Return: top n claims.
    """
```

**Important filter:** Claims that are already the lead bullet in the resume for a given employer should be down-weighted — the CL should introduce a different angle, not repeat the resume. This is why `resume_claim_ids` is passed in.

Store selected claim IDs in `cover_letter_plan.json` under a `selected_cl_claims` key. This makes claim selection traceable and auditable.

### Stories

**Story 3.1 — Extend score_claim_for_jd to batch-score full catalog**
- `score_all_claims(jd_profile: JdProfile, catalog: ClaimCatalog) -> list[tuple[Claim, float]]`
- Returns sorted list of (claim, score) tuples, descending by score
- Acceptance: All active claims are scored; disabled claims are excluded

**Story 3.2 — Implement select_cl_claims with filtering**
- Filter out disabled claims
- Filter out claims already used as lead bullets in the resume (pass resume_claim_ids)
- Return top n by score
- Acceptance: Selected claims don't repeat resume lead bullets; disabled claims never selected

**Story 3.3 — Store selected claims in cover_letter_plan.json**
- Add `selected_cl_claims: [{"id": "ACC-102", "score": 0.87}, ...]` to plan
- Acceptance: After pipeline run, cover_letter_plan.json contains selected claims with scores

**Story 3.4 — Pass selected claims into CL generator**
- In `draft_compiler.py`, call `select_cl_claims` before calling any CL generation function
- Pass result into slot generator (Epic 2) or existing renderer (v1 path)
- Acceptance: CL proof points match the pre-selected claims

**Story 3.5 — Tests**
- Test that disabled claims are never selected
- Test that resume-prominent claims are down-weighted
- Test determinism: same JD + same catalog → same selection

---

## Epic 4 — JD-Adaptive Summary Formula

**Goal:** Replace LLM-generated professional summaries with deterministic string assembly. Output always contains B2B SaaS legibility signals (scale, partners, outcomes) without locking Jason into a B2B label.

**Modified files:** `scripts/local_draft_stages.py`, `scripts/candidate_context.py`  
**New file:** `scripts/summary_builder.py`

### Implementation Notes

The summary is built from three components: **context** (years, environment type), **scope** (what was owned at which company, at what scale), **outcomes** (what specifically was achieved).

```python
@dataclass
class SummaryContext:
    years_experience: int           # from workExperience.md
    environment_type: str           # derived from JD: "enterprise SaaS" | "SaaS" | "consumer tech"
    focus_areas: list[str]          # top 3 from JD skill match, max 3 items
    company_name: str               # most recent employer
    scope_description: str          # what was owned
    scale_metric: str               # e.g. "~3,500 enterprise and mid-market accounts"
    partners: list[str]             # from verified cross-functional partner list, JD-relevant subset
    outcome_1: str                  # strongest metric phrase
    outcome_2: str                  # second metric phrase
```

**JD context classifier** — three variants:
- `enterprise`: JD mentions "enterprise", "B2B", "accounts", "ARR" → use scale/partner signals prominently
- `consumer`: JD mentions "users", "growth", "B2C", "DAU", "retention" → use user-volume language, de-emphasize account count
- `neutral`: neither signal is dominant → use "SaaS platforms" without environment qualifier

**Environment type is never "B2B SaaS" as a label.** Use "enterprise SaaS", "SaaS platforms", or "software products" depending on variant. Jason's background speaks for itself through the scale and partner signals — the label isn't needed.

**Fallback:** If required variables (years, scope, scale_metric) cannot be resolved from workExperience.md, fall back to LLM generation with a WARN logged.

### Stories

**Story 4.1 — SummaryContext dataclass and variable extraction**
- `extract_summary_context(jd_profile: JdProfile, candidate_profile: dict) -> SummaryContext`
- Pulls years from workExperience.md Section 1
- Pulls scale metric (MET-02: ~3,500 accounts or MET-03: ~25,000 users) based on JD context
- Pulls top 3 focus areas from JD profile skill match
- Pulls partners from verified list, filtered to JD-relevant subset
- Acceptance: All fields populated from structured data, no LLM calls

**Story 4.2 — JD context classifier**
- `classify_jd_context(jd_profile: JdProfile) -> Literal["enterprise", "consumer", "neutral"]`
- Signal detection: keyword frequency in JD text
- Acceptance: Enterprise JDs return "enterprise"; consumer JDs return "consumer"

**Story 4.3 — Template variants and assembly**
- Three template strings with `{variable}` slots
- `assemble_summary(context: SummaryContext, jd_context: str) -> str`
- Acceptance: Output is one paragraph, under 80 words, contains all required signals for variant

**Story 4.4 — Wire into local_draft_stages.py**
- Replace the LLM summary generation call in `assemble_resume` with `assemble_summary`
- Keep LLM path as fallback (log WARN when used)
- Acceptance: Resume summary is generated without an LLM call on happy path

**Story 4.5 — Tests**
- Test each template variant with representative JD profiles
- Test fallback triggers correctly when required fields are missing
- Test that output never contains "B2B SaaS" as a label

---

## Epic 6 — Multi-Pass Critic with Slot-Level Regeneration

**Goal:** After CL generation, score each slot against its relevant rubric dimension. Any slot below threshold is regenerated in isolation. Full-letter regeneration is never triggered by a single slot failure.

**Modified files:** `scripts/critique_retry.py`, `scripts/cover_letter_slots.py`  
**Depends on:** Epic 2 (skeleton must exist for per-slot targeting)

### Implementation Notes

Rubric dimension to slot mapping:
- C1 (Hook specificity) → HOOK slot
- C2 (Opening energy/voice) → HOOK slot
- C3 (Proof density) → PROOF_1, PROOF_2 slots
- C4 (Role fit logic) → PROOF_2 slot
- C5 (Closing) → CLOSING slot

Each slot has a minimum acceptable score. If below threshold, regenerate that slot with the same accumulated context but a different temperature or constraint variant.

```python
def critique_slot(
    slot: CLSlot,
    jd_profile: JdProfile,
    accumulated_context: str
) -> tuple[float, str]:  # (score, feedback)
    """Score a single slot against its rubric dimension."""
```

Max retries per slot: 3. After 3 failures, log WARN and use the highest-scoring attempt.

### Stories

**Story 6.1 — Per-slot rubric scorer**
- `critique_slot(slot, jd_profile, accumulated_context) -> (score, feedback)`
- Uses a subset of the existing eval prompt, scoped to the slot's rubric dimensions
- Acceptance: Returns a score between 0.0 and 1.0 and actionable feedback text

**Story 6.2 — Slot-level retry loop**
- `retry_slot_until_passing(slot, jd_profile, accumulated_context, threshold, max_attempts=3) -> CLSlot`
- On failure: regenerate slot with feedback injected into prompt ("Previous attempt failed because: [feedback]. Try again.")
- Track all attempts; return best if max reached
- Acceptance: Slot with score below 0.65 on first attempt is retried; second attempt sees feedback

**Story 6.3 — Wire into slot generator**
- After each slot is generated in `generate_cl_slots`, call `retry_slot_until_passing`
- Acceptance: The assembled CL only contains slots that passed their rubric threshold (or the best available attempt)

**Story 6.4 — Tests**
- Mock LLM to return low-score response on first call, passing response on second
- Assert retry is triggered exactly once
- Assert final slot content is from the second (passing) attempt

---

## Epic 7 — Hook Isolation

**Goal:** Generate the opening hook in a dedicated, heavily constrained LLM call before the rest of the CL is generated. The hook is locked before any other slot is written.

**New function:** `generate_hook()` in `scripts/cover_letter_slots.py`  
**Modified files:** `scripts/draft_compiler.py`

### Implementation Notes

The hook generator only sees:
- Company name
- 5 extracted JD facts (see Story 7.1)
- A hard-constrained system prompt

```
System: You write opening sentences for cover letters.
Rules:
- Exactly one sentence.
- Under 35 words.
- No "I" anywhere in the sentence.
- Must contain at least one specific detail from the company or role description.
- Do not express enthusiasm, desire, or excitement.
- Do not describe the applicant.
- Describe something true about the company's situation or the problem this role solves.

Output only the sentence. Nothing else.
```

**Hook validation — three checks, all must pass:**
1. No first-person pronouns ("I", "my", "me", "we") — regex
2. At least one word from the JD facts list appears in the hook — string match
3. Word count ≤ 35 — len check

Max 3 retries. If all 3 fail, raise a `HookGenerationError` with the best attempt attached (the caller can decide whether to use it with a WARN or fail hard).

**JD fact extraction** happens deterministically from the already-parsed `JdProfile` — not a separate LLM call. Pull: company_name, role_mission (from JD summary field), primary_technical_challenge, product_surface_owned, user_or_customer_type. These 5 fields are already parsed by `build_jd_profile()`.

### Stories

**Story 7.1 — JD fact extraction from JdProfile**
- `extract_hook_facts(jd_profile: JdProfile) -> dict[str, str]`
- Pulls: company_name, role_mission, primary_challenge, product_surface, customer_type
- Falls back to raw JD text slice if field is missing
- Acceptance: Returns a dict with at least 3 populated fields for any valid JD

**Story 7.2 — Hook generator with constrained prompt**
- `generate_hook(hook_facts: dict, llm_client) -> str`
- Uses the system prompt above (hardcoded, not templatized)
- Low temperature (0.3) for consistency
- Acceptance: Returns a single sentence under 35 words

**Story 7.3 — Hook validation**
- `validate_hook(hook: str, hook_facts: dict) -> tuple[bool, str]`
- Checks: no pronouns, contains JD-specific word, word count ≤ 35
- Returns (passed, failure_reason)
- Acceptance: Hook with "I" fails; hook with no JD-specific detail fails; valid hook passes

**Story 7.4 — Retry loop with validation**
- `generate_validated_hook(hook_facts, llm_client, max_attempts=3) -> str`
- On validation failure: retry with failure reason appended to prompt
- If all attempts fail: raise `HookGenerationError` with best attempt
- Acceptance: A hook with "I" on attempt 1 is retried; attempt 2 prompt includes "Previous attempt contained first-person pronouns. Try again."

**Story 7.5 — Store hook in cover_letter_plan.json**
- Add `generated_hook` and `hook_attempts` fields to plan
- Acceptance: After pipeline run, plan contains the final hook and how many attempts it took

**Story 7.6 — Wire into draft_compiler.py**
- Call `generate_validated_hook` before any CL slot generation
- Pass resulting hook string into skeleton generator (Epic 2)
- Acceptance: Hook in final CL matches hook in cover_letter_plan.json exactly

**Story 7.7 — Tests**
- Test validation: assert each check fires correctly
- Test retry: mock LLM to return invalid hook on attempt 1, valid on attempt 2
- Test fact extraction across different JD formats

---

## Epic 8 — Eval-Before-Queue Gate

**Goal:** Run a fast rubric check on C1 (hook) and C3 (proof density) immediately after draft generation, before the submission enters the queue. If either fails, trigger slot-level regeneration immediately rather than storing a BLOCKED file.

**Modified files:** `scripts/draft_compiler.py`, `scripts/eval_submission.py`  
**New function:** `fast_eval_cl()` in `scripts/eval_submission.py`  
**Depends on:** Epic 6 (slot-level regeneration must exist)

### Implementation Notes

The fast eval is not a full rubric score — it's a targeted check on the two dimensions most likely to block a submission. Full rubric scoring still runs after for reporting.

```python
@dataclass
class FastEvalResult:
    hook_score: float           # C1 score (0.0–1.0)
    proof_density_score: float  # C3 score (0.0–1.0)
    passed: bool                # True if both >= threshold
    failing_slots: list[str]    # ["HOOK"] or ["PROOF_1"] or both

FAST_EVAL_THRESHOLD = 0.65
```

**Gate flow in draft_compiler.py:**
```
generate slots
  → fast_eval_cl()
  → if passed: proceed to PDF compilation
  → if failed: retry failing slots (Epic 6)
              → fast_eval_cl() again
              → if passed: proceed
              → if still failed after max_retries: store with WARN flag (don't block, but log)
```

The key decision: don't hard-block if fast eval fails after retries. Instead, flag it and let it through with a WARN. Hard blocking would create stuck pipelines. The WARN surfaces for manual review.

### Stories

**Story 8.1 — fast_eval_cl function**
- `fast_eval_cl(cl_text: str, jd_profile: JdProfile) -> FastEvalResult`
- Scores C1 and C3 only, using the existing eval LLM prompt but scoped to those dimensions
- Acceptance: Returns scores and failing slot list within one LLM call

**Story 8.2 — Gate loop in draft_compiler.py**
- After slot generation: call `fast_eval_cl`
- If failed: call `retry_slot_until_passing` for each failing slot (Epic 6)
- Re-run `fast_eval_cl` after retry
- Cap total retries at 2 cycles
- Acceptance: A draft that fails C1 on first eval gets the HOOK slot regenerated before PDF compilation

**Story 8.3 — WARN flag on persistent failure**
- If fast eval still fails after 2 retry cycles: add `fast_eval_warning: true` to eval_report.json
- Continue to PDF compilation (don't block)
- Acceptance: Submission with persistent fast eval failure compiles PDF but has WARN in eval report

**Story 8.4 — Tests**
- Test gate triggers retry on C1 failure
- Test gate proceeds without retry on pass
- Test WARN flag is set after max retries

---

## Epic 9 — Gap Acknowledgment Injection

**Goal:** When a JD has a specific requirement that scores low against Jason's profile (soft gap) but overall fit is still above threshold, automatically inject a one-paragraph honest gap acknowledgment as the last body paragraph. Turns a potential rejection reason into a conversation opener.

**New file:** `scripts/gap_detector.py`  
**Modified files:** `scripts/cover_letter_slots.py`, `scripts/draft_compiler.py`  
**Depends on:** Epic 2 (skeleton must have a configurable slot for gap content)

### Implementation Notes

**Gap detection logic:**
```python
@dataclass
class SoftGap:
    requirement_text: str       # The JD requirement that scored low
    relevance_score: float      # Score against candidate profile (< 40%)
    gap_area: str               # Human-readable label: "fintech/payments", "CRM ownership", etc.
    transfer_skill: str         # What Jason has that's adjacent

def detect_soft_gaps(
    jd_profile: JdProfile,
    candidate_profile: dict,
    overall_fit_score: float
) -> list[SoftGap]:
    """
    Returns soft gaps only when:
    - A specific JD requirement scores < 0.40 relevance
    - Overall fit score >= 72 (submission is still worth sending)
    - The gap is a DOMAIN gap (industry, product type) not a SKILL gap (missing hard skills)
    """
```

**Only one gap acknowledgment per CL** — the highest-priority gap. If there are multiple soft gaps, pick the one most likely to come up in a phone screen (highest-scoring in the JD's requirements section).

**Gap template (locked — no LLM generation):**
```
"I'll be direct about [gap_area]: [honest_statement]. 
What I bring instead is [transfer_skill]. 
If there's room to develop [gap_area] on the job, I'd welcome the chance to make that case."
```

**honest_statement** is generated from a lookup table keyed on gap_area type. Pre-write honest statements for common gap types:
- `fintech/payments`: "I don't have direct payments or fintech product experience."
- `healthcare/domain`: "I haven't worked in the healthcare domain specifically."
- `crm/lifecycle`: "My CRM experience is adjacent — I've owned the data that powers lifecycle tools, not the CRM product itself."
- `consumer/b2c`: "My background is in enterprise SaaS rather than consumer product."
- `industry_domain` (generic): "My background doesn't include [gap_area] specifically."

**transfer_skill** is derived from the SoftGap's context — the system looks at what Jason does have that's most adjacent to the gap.

### Stories

**Story 9.1 — SoftGap dataclass and detect_soft_gaps**
- `detect_soft_gaps(jd_profile, candidate_profile, overall_fit_score) -> list[SoftGap]`
- Fires only when: requirement_score < 0.40 AND overall_fit >= 72 AND gap is domain type (not hard skill)
- Returns empty list if no soft gaps or if overall fit < 72
- Acceptance: Snapsheet (fintech gap) returns one SoftGap; element451 (strong fit) returns empty list

**Story 9.2 — Gap type classifier**
- `classify_gap_type(requirement_text: str) -> str`
- Maps requirement text to gap area label using keyword matching
- Builds lookup from: fintech/payments, healthcare, CRM/lifecycle, consumer/B2C, domain (generic)
- Acceptance: "Experience with fintech, payments, transactions" → "fintech/payments"

**Story 9.3 — Gap acknowledgment template assembly**
- `build_gap_paragraph(gap: SoftGap) -> str`
- Looks up honest_statement from pre-written table keyed on gap_area
- Fills transfer_skill from candidate_profile based on gap_area
- Assembles from locked template
- Acceptance: Output is 2–3 sentences, uses no LLM, matches template exactly

**Story 9.4 — Wire as optional PROOF_2 slot in skeleton**
- If a SoftGap is detected: use gap paragraph as PROOF_2 slot content (skip PROOF_2 generation)
- If no SoftGap: generate PROOF_2 normally from pre-selected claims (Epic 3)
- Acceptance: CL for Snapsheet contains gap acknowledgment paragraph; CL for element451 does not

**Story 9.5 — Store gap detection in cover_letter_plan.json**
- Add `detected_gaps: [{"gap_area": "fintech/payments", "score": 0.31}]` to plan
- Add `gap_acknowledged: true/false`
- Acceptance: Plan file reflects whether a gap was detected and acknowledged

**Story 9.6 — Pre-write honest_statement lookup table**
- Build the lookup table as a module-level constant (not a config file — this is intentional content)
- Cover at minimum: fintech/payments, healthcare, CRM/lifecycle, consumer/B2C, IoT/hardware, domain (generic)
- Each entry reviewed and approved by Jason before being activated
- Acceptance: Each entry reads naturally, is honest, and reframes without apologizing

**Story 9.7 — Tests**
- Test detect_soft_gaps fires at correct thresholds
- Test gap_type classifier for each supported gap area
- Test assembled gap paragraph for each gap type in the lookup table
- Test that only one gap paragraph is injected per CL

---

## Epic 5 — Golden Example Library + Matching (Separate Session)

This epic is scoped for a dedicated session. Brief for that session:

### What We're Building
A searchable library of approved cover letters and resumes, tagged with metadata, used as few-shot examples during generation. The goal is to make the LLM imitate approved output rather than inferring quality from instructions alone.

### Session Inputs
The implementing session should read this document first, then:
- `data/submissions/` — source of approved examples (anything that's been manually approved)
- `data/master_claims.json` — claim IDs for tagging
- `scripts/draft_compiler.py` — where few-shot examples will be injected

### Scope

**Part 1 — Library storage format**
A JSON library file at `data/approved_examples.json`. Schema per entry:
```json
{
  "id": "ex_hubspot_cl_001",
  "type": "cover_letter",
  "company": "hubspot",
  "role_type": "data_platform_pm",
  "company_type": "enterprise_saas",
  "hook_pattern": "company_observation",
  "proof_claims": ["ACC-102", "ACC-103"],
  "gap_acknowledged": false,
  "word_count": 285,
  "approved": true,
  "notes": "strong hook — foundational PM angle",
  "content_path": "data/submissions/hubspot/CoverLetter.md"
}
```

**Part 2 — Tagging CLI**
`python scripts/tag_example.py data/submissions/hubspot/CoverLetter.md`
Interactive CLI that walks through each tag field and writes the entry to `approved_examples.json`.

**Part 3 — Retrieval function**
`retrieve_examples(jd_profile: JdProfile, doc_type: str, n: int = 2) -> list[str]`
- Primary match: role_type (exact)
- Secondary match: company_type (exact)
- Fallback: highest-rated examples regardless of type
- Returns content strings (the actual CL text) for few-shot injection

**Part 4 — Wire into generation**
In `draft_compiler.py`, before calling the CL generator: retrieve 2 examples and inject as few-shot context in the system prompt. Format: "Here are two approved examples of the style and quality expected: [example 1] --- [example 2]"

**Part 5 — Embedding upgrade path (document only, don't build)**
Document the interface change needed to switch from tag-based retrieval to embedding-based retrieval when the library has 50+ examples. The retrieval function signature stays the same — only the internals change. This keeps the upgrade non-breaking.

### Out of Scope for Epic 5
- Training a classifier
- Negative examples (rejected CLs)
- Automatic tagging (all tagging is manual and intentional)
- Embedding generation (tag-based retrieval only for now)

---

## Summary Table

| Epic | New Files | Modified Files | LLM Calls | Sprint |
|------|-----------|----------------|-----------|--------|
| 1 — Linter | `submission_linter.py` | `compile_single.py`, `draft_compiler.py`, `quality_checker.py` | None | 1 |
| 2 — Skeleton | `cover_letter_slots.py` | `cover_letter_renderer.py`, `draft_compiler.py` | 3 (one per slot) | 2 |
| 3 — Proof Select | — | `jd_tailoring.py`, `draft_compiler.py`, `cover_letter_plan.py` | None | 1 |
| 4 — Summary Formula | `summary_builder.py` | `local_draft_stages.py`, `candidate_context.py` | None (fallback only) | 1 |
| 5 — Library | `approved_examples.json`, `tag_example.py` | `draft_compiler.py` | None | Separate |
| 6 — Critic | — | `critique_retry.py`, `cover_letter_slots.py` | 1 per slot retry | 3 |
| 7 — Hook | `cover_letter_slots.py` (add fn) | `draft_compiler.py` | 1 (low temp) | 1 |
| 8 — Eval Gate | — | `draft_compiler.py`, `eval_submission.py` | 1 (fast eval) | 4 |
| 9 — Gap Ack | `gap_detector.py` | `cover_letter_slots.py`, `draft_compiler.py` | None | 3 |
