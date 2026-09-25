---
status: approved
date: 2026-09-03
related: CR-019, CR-039, CR-093
---

# CR-110 — Stage 0 gate escapes and header placeholder fixes

## Problem statement

The Stage 0 preference gates allowed several roles through even though the postings
matched Jason's configured exclusion rules. Separately, resume header normalization
left partial contact placeholders in compiled PDFs when the candidate name was already
real. The resulting submissions included roles that should have been skipped and
documents that still exposed template placeholders.

The failures were deterministic and came from narrow or bypassed checks, not from
ambiguous fit judgments. This change closes the confirmed escapes while documenting
remaining structural gaps that need separate design or product decisions.

## Root cause 1: Title gate omitted Junior and Associate

### Evidence

`blocked_title_lists()` in `scripts/seniority_gate.py` preferred the
pipeline-managed `blocked_role_titles` list over the UI-sourced `blocked_titles` list
when both were present. It therefore ignored the UI list instead of evaluating the
union of both configured lists.

The pipeline-managed `blocked_role_titles` in `data/candidate_preferences.json` did
not contain `Junior` or `Associate`. `Junior` existed only in the ignored
`blocked_titles` list. `Associate` existed in neither configured list, even though it
was present in `_DEFAULT_BLOCKED_ROLE_TITLES`; that default was never reached when
the configured pipeline list was available.

The escape affected:

- `cybercoders` — Junior PM
- `hrcap_inc` — Associate PM
- `isolved` — Associate PM
- `cariloop` — Associate PM

### Fix

`blocked_title_lists()` now merges the pipeline-managed and UI-sourced lists before
matching titles. `Associate` and `Junior` were also added to
`blocked_role_titles` in `data/candidate_preferences.json`, so the persisted
pipeline configuration expresses the intended exclusion directly.

### Files changed

- `scripts/seniority_gate.py`
- `data/candidate_preferences.json`

## Root cause 2: Years gate missed apostrophes and spelled-out numbers

### Evidence

The `_LOOSE_YEARS_PATTERNS` expressions used `years?\s+`, which did not match the
apostrophe between `years` and `experience` in `years' experience`, including a
curly apostrophe (U+2019). The `parse_max_years_required` parser used `(\d+)`, so it
could parse numeric values but not spelled-out values such as `Twelve`.

The escape affected:

- `sprezzatura` — `10 years' experience` was not detected
- `hale_products_inc` — `Twelve+ years` was not detected

### Fix

The loose-year patterns now allow an optional apostrophe after `years?`, including
the curly-apostrophe form. `seniority_gate.py` also defines the `_WORD_NUMBERS`
mapping and `_WORD_NUMBER_RE` so spelled-out numbers are parsed. A pattern for
`N years in product management` was added to cover that common JD form.

### Files changed

- `scripts/seniority_gate.py`

## Root cause 3: Revenue and billing exclusion matching was too narrow

### Evidence

`_REVENUE_OWN_RE` in `scripts/stage0_prefs_gate.py` matched only narrow ownership
language such as owning the revenue model, billing, P&L, or pricing strategy. It did
not recognize several equivalent responsibility phrasings used by real postings.

The escape affected:

- `amphenol_rf` — product-line revenue responsibility
- `hale_products_inc` — revenue and margin management
- `beyond` — dynamic pricing algorithm
- `harnham` — pricing and billing systems
- `tenth_revolution_group` — payroll, finance, and billing responsibilities

### Fix

The exclusion regex was broadened to recognize responsibility language covering:

- product-line performance, revenue, and margin management
- revenue and margin ownership
- product-line profitability
- dynamic pricing and pricing algorithms
- billing, ordering, and invoicing
- payroll processing
- finance, payroll, and billing workstreams

### Files changed

- `scripts/stage0_prefs_gate.py`

## Root cause 4: Header repair handled only fully bracketed headers

### Evidence

`_PLACEHOLDER_LINE1` in `scripts/apply_resume_header.py` only recognized a fully
bracketed first line such as `# [Name]`. When line 1 already contained a real name,
the script could skip the header even when line 2 contained partial placeholders
such as:

`San Diego, CA | [phone] | [email] | [LinkedIn]`

The same independent line-2 check was missing for a blank contact line. In the
evidence set, 10 of 20 folders consequently retained partial contact placeholders
in compiled PDFs, including the blank-line-2 case in `tenth_revolution_group`.

### Fix

Header normalization now checks line 2 independently of whether line 1 is already a
real name. A line 2 containing bracket placeholders or no content is repaired
instead of being skipped.

### Files changed

- `scripts/apply_resume_header.py`

## Acceptance criteria

- [x] The title gate evaluates the merged configured title lists and blocks Junior
      and Associate role titles, including the four affected evidence folders.
- [x] The years gate detects `10 years' experience`, curly-apostrophe variants,
      `Twelve+ years`, and `N years in product management`.
- [x] The revenue and billing exclusion gate catches the confirmed product-line,
      revenue/margin, profitability, pricing, billing, payroll, and finance
      phrasings.
- [x] Header repair fixes partial contact placeholders and blank contact lines even
      when line 1 already contains a real candidate name.
- [x] The four confirmed root causes and their file-level fixes are documented
      separately from structural gaps that remain recommendations.

## Structural gaps and recommendations

These are confirmed limitations or observability risks, but were not part of the
deterministic fixes above:

1. **Industry gate is keyword-only.** A posting can avoid naming its own category.
   For example, `loot_labs`/`Boxed.gg` avoids the word `gaming`, and `partner_co`
   avoids `MLM`. Recommendation: add a structured industry signal or a review path
   for postings whose company and product context imply an excluded industry without
   using the keyword.
2. **No ingestion validation for bracket-placeholder templates.** A JD such as
   `invision`'s `[Company X]` can enter the pipeline without a source-template
   validation failure. Recommendation: reject or quarantine unresolved bracket
   placeholders during JD ingestion, before Stage 0 evaluation.
3. **No distinction between a single-employer posting and a talent-matching network
   page.** `yara_ai` demonstrates that a network or matching page can be treated like
   a normal employer posting. Recommendation: classify source type during ingestion
   and route network pages to an explicit review or skip policy.
4. **`run_prefs_gate_safe` fails open and catches exceptions silently.** This was not
   the cause of the confirmed escapes, but it can hide a future gate failure.
   Recommendation: retain process safety while emitting a visible, persisted
   failure signal and making the fail-open decision observable.
5. **Preference-gate results are not stored in `stage0_fit_gate.json`.**
   Recommendation: persist each gate's result, matched evidence, and error state in
   the Stage 0 output so later audits can distinguish PASS, SKIP, and unavailable
   checks.
6. **`experience_levels` includes `Junior (1-2 Years)`.** This may conflict with
   the title exclusion policy. Recommendation: Jason should decide whether the
   experience-level option is intentional. If it is not, remove or remap it through
   the Settings path so the persisted preferences and title gate remain aligned.

## Round 2 — Hardening (2026-09-03)

### Fix 5: `run_prefs_gate_safe` fail-loud with observability

Previously, `run_prefs_gate_safe` caught all exceptions and returned `passed: True`
silently. Every preference gate, including industry, title, years, exclusion zones,
and solo-PM checks, could therefore be skipped with no trace.

The function now logs the error to stderr and includes an `_gate_failed: True` flag
in its result, so the error remains visible in output. Applyr's gates are
availability-sensitive: failing closed on a transient error would block every Stage 0
run and be disruptive. Following the availability-oriented fail-open guidance from
NoOps School, while applying OWASP's recommendation to fail closed for security gates,
this keeps the fail-open behavior but makes the failure observable.

**Files changed**

- `scripts/build_stage0_fit_gate.py`

### Fix 6: Prefs gate results stored in `stage0_fit_gate.json` output

Previously, preference-gate rejects and flags were discarded after evaluation, making
it impossible to audit whether the gates actually ran. The output now stores
`prefs_gate_rejects` as a list of reject codes and `prefs_gate_flags` as a list of
flag codes. This preserves decision provenance for audits and debugging, consistent
with NoOps School policy-gate guidance.

**Files changed**

- `scripts/build_stage0_fit_gate.py`

### Fix 7: Blocking header placeholder validation in `verify_submission.py`

Previously, no validator checked whether the resume or cover-letter header contained
bracket placeholders. PDF parseability was informational only, so a header such as
`[phone]` could pass mechanical verification.

`_check_header_placeholders()` now checks line 2 of `Resume.md` and `CoverLetter.md`
for bracket placeholders or a blank line. Its result is included in
`mechanically_verified`, so a submission with an unresolved header placeholder cannot
pass. This adds defense in depth, as recommended by Palo Alto Networks, by combining
an OWASP-style allow-list for valid headers with the existing deny-list checks.

**Files changed**

- `scripts/verify_submission.py`

### Fix 8: Text normalization for curly quotes and apostrophes

Added `_normalize_quotes()` to `seniority_gate.py` to convert curly and smart quotes
(U+2018, U+2019, U+201A, U+201B, U+201C, and U+201D), en dashes (U+2013), and em
dashes (U+2014) to ASCII equivalents before regex matching. The function is called
at the entry point of `parse_max_years_required()`, so all years-gate patterns operate
on normalized text. This follows canonical-encoding normalization guidance and avoids
duplicating every pattern for each punctuation variant. The approach follows OWASP's
UAX-15 normalization guidance and the standard NLP practice of normalizing all quotes
instead of matching every variant in every pattern.

**Files changed**

- `scripts/seniority_gate.py`

### Round 2 tests

- Added `TestHeaderPlaceholders` with three tests covering clean headers, bracket
  placeholders, and a blank line 2.
- Added `TestPrefsGateObservability` with two tests covering visible error flags and
  persisted reject/flag lists.
- Total: 166 passed, 5 skipped, 0 failures.

## Round 3 — Disposition accountability and vestigial field cleanup (2026-09-04)

### Fix 9: Reasoning required for self-clearing dispositions

Previously, `dispositions.json` stored bare string values (`"FALSE_POSITIVE"`,
`"ACCEPTED_AS_CORRECT"`, etc.) with no reasoning field. The AGENTS.md instruction
to "dispose with real reasoning" was aspirational, not mechanically enforced. An
agent could clear any WARN finding with a one-word disposition and no justification.

The fix introduces a two-shape disposition schema (backward-compatible):
- Bare string: `"RESOLVED_EDIT"` (still valid for dispositions that don't need reasoning)
- Object with reasoning: `{"disposition": "FALSE_POSITIVE", "reasoning": "explanation"}`

`policy.py` now requires substantive reasoning (>= 10 chars) for dispositions that
claim the finding was wrong or accept a risk:
- `FALSE_POSITIVE` — claims the finding misfired; reasoning must explain why
- `ACCEPTED_AS_CORRECT` — claims the flagged content is already correct; reasoning must explain why
- `HUMAN_ACCEPTED_RISK` — accepts a known risk; reasoning must justify the acceptance

`RESOLVED_EDIT` and `NOT_APPLICABLE` do not require reasoning. `RESOLVED_EDIT`
produces a verifiable artifact (the edit itself). `NOT_APPLICABLE` is a scope claim
that is usually self-evident from context.

When reasoning is missing or too short, the finding is re-opened as
`NEEDS_DISPOSITION` with a specific reason explaining what is required. This follows
the self-grading accountability principle: a disposition that claims a finding was
wrong without saying why is not accountable, and should not silently clear.

**Files changed**

- `scripts/workflow/reviews.py` — added `REASONING_REQUIRED`, `REASONING_MIN_CHARS`,
  `parse_disposition()` helper, updated `_write_dispositions` note
- `scripts/workflow/policy.py` — imports `REASONING_REQUIRED`/`parse_disposition`,
  enforces reasoning in `evaluate_truth_findings`, preserves specific reasons in
  `NEEDS_DISPOSITION` verdict
- `scripts/test_workflow_authority.py` — updated 6 existing tests to use object
  format with reasoning; added 8 new tests for reasoning requirement

### Fix 10: Remove vestigial `Junior` from `experience_levels`

Investigation found that `experience_levels` in `candidate_preferences.json` is a
**vestigial dead field**. It was designed (CR-003/FEAT-009) to drive LinkedIn `f_E=`
URL parameters in the old `scout_local.ts`, but LinkedIn scouting was decommissioned
(CR-010) and `scout_local.ts` was deleted. The replacement connector architecture has
no experience-level filtering. No code in `scripts/`, `server/`, or `shared/` reads
`experience_levels`. The field is written by the UI (`SyncActivityView.tsx`) and
`jobSearchPrefs.ts` but never consumed.

Removing `"Junior (1-2 Years)"` from `experience_levels` has zero runtime effect.
Junior roles are blocked by `blocked_titles` and `blocked_role_titles` (both contain
`"Junior"`), not by `experience_levels`. The removal eliminates a cosmetic
inconsistency: the JSON said "accept Junior" while the title blocklist said
"reject Junior." The field itself remains in the JSON for UI compatibility but
should be considered deprecated as a filtering mechanism.

**Files changed**

- `data/candidate_preferences.json`

### Round 3 tests

- 48 tests in `test_workflow_authority.py` pass (8 new reasoning tests + 6 updated
  existing tests), 0 failures.

## Round 4 — Implemented structural gaps (2026-09-04)

### Fix 11: LLM-based industry classification (Gap A)

The keyword industry gate uses regex word-boundary matching and misses JDs that
describe a blocked industry without using the exact term. This fix adds a
supplementary LLM-based classification pass that runs after the keyword gate,
using the same Groq/Gemini plumbing as `evidence_scale.py`.

**Design:**
- The keyword gate runs first (fast, free, deterministic). If it blocks, the LLM
  pass does not run.
- The LLM pass uses `call_llm_stage("industry_semantic", ...)` — a new stage ID
  registered in `llm_stages.py` with `["groq", "gemini"]` providers.
- The LLM sees the JD text (truncated to 2000 chars) and the list of blocked
  industries, and returns a JSON-structured response with `blocked_industry`,
  `confidence`, and `reasoning`.
- High/medium confidence classifications produce a hard reject
  (`blocked_industry_semantic`). Low confidence produces a soft flag
  (`blocked_industry_semantic_low`).
- On LLM failure, the gate fails open (logs to stderr, does not block) — the
  keyword gate's result stands. This follows the same availability-oriented
  fail-open pattern as `run_prefs_gate_safe`.
- The LLM output is normalized: if the returned industry name doesn't match any
  configured blocked industry (case-insensitive substring match), it is treated as
  no match. This prevents the LLM from inventing blocks for industries Jason
  hasn't configured.

**Files changed:**
- `scripts/industry_semantic.py` — new module with `classify_industry()`,
  `classify_industry_safe()`, `_SCHEMA`, `_SYSTEM_PROMPT`
- `scripts/llm_stages.py` — added `"industry_semantic": ["groq", "gemini"]` to
  `STAGE_PROVIDERS`
- `scripts/stage0_prefs_gate.py` — wired `classify_industry_safe` into
  `run_prefs_gate` as gate 2b (after keyword industry gate, before title blocklist)
- `scripts/test_industry_semantic.py` — 21 new tests (7 LLM classification, 8 JD
  content validation, 6 prefs gate integration)
- `scripts/test_build_stage0_fit_gate.py` — added `_INDUSTRY_SEMANTIC_PATCHER` to
  `setUpModule` to mock the LLM call for existing prefs gate tests

### Fix 12: JD content validation — bracket placeholders and network pages (Gap B)

No content validation existed between DB insert and Stage 0. The only check was
`MIN_JD_CHARS = 200` (a character count). Template JDs with bracket placeholders
and talent-matching network pages passed through unchecked.

**Two deterministic checks added to `run_prefs_gate`:**

1. **Bracket-placeholder detection** (`check_jd_placeholders`): regex scan for
   `[Company X]`, `[Your Company]`, `[phone]`, `[email]`, `[Insert ...]` patterns.
   Produces a hard reject with code `jd_placeholder`.

2. **Network-page detection** (`check_network_page`): keyword match for phrases
   like "apply once and get matched", "talent network", "join our talent pool".
   Produces a hard reject with code `network_page`.

Both are deterministic (no LLM, no API cost) and run as gate 9 in the prefs gate
sequence.

**Files changed:**
- `scripts/jd_content_validation.py` — new module with `check_jd_placeholders()`
  and `check_network_page()`
- `scripts/stage0_prefs_gate.py` — wired both checks into `run_prefs_gate` as
  gate 9 (after exclusion zones, before deduplication)

### Round 4 tests

- 21 new tests in `test_industry_semantic.py` (7 LLM classification, 8 JD content
  validation, 6 prefs gate integration) — all pass
- 6 existing prefs gate tests in `test_build_stage0_fit_gate.py` — all pass with
  the new LLM mock
- 57 tests across `test_workflow_authority`, `test_verify_submission`,
  `test_seniority_years_gate`, `test_title_blocklist` — all pass
- Total: 84 tests pass, 0 failures
