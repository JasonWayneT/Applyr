# CR-112 HM Critical-Read Contract — Independent QA Review

**Reviewer:** Independent QA worker subagent
**Date:** 2026-09-13
**Branch:** cr112-hm-critical-read-contract
**Commit:** f22abdb
**Mode:** Read-only review (no files modified)

---

## VERDICT: ACCEPT WITH CHANGES

## Summary

The two-layer contract (policy-level disallowed-disposition gate + runner-level structured review artifact validation) correctly prevents silent self-certification of `hm.critical_read` findings. All 30 acceptance tests and the modified `test_workflow_authority.py` test pass, covering bare strings, filler, stale hashes, missing fields, and Truth-subphase isolation. Two non-blocking gaps exist: verdict-disposition consistency rules from the design doc are not enforced, and several validator edge-case code paths lack explicit test coverage.

---

## Blocking Concerns

None. The core security goal — preventing bare strings, filler, and template dispositions from clearing `hm.critical_read` — is achieved with no identifiable bypass.

---

## Non-blocking Observations

### N-1: Verdict-disposition consistency not enforced

The design doc (section "Validation rules") specifies:
- `ACCEPTED_AS_CORRECT` → verdict must be `"pass"`
- `RESOLVED_EDIT` → verdict must be `"pass"`
- `HUMAN_ACCEPTED_RISK` → verdict may be `"pass"`, `"revise"`, or `"reject"`

The implementation (`validate_hm_review`) only checks that `verdict` is one of the three valid enum values (`pass`/`revise`/`reject`). It does not cross-check verdict against the disposition. An agent could write `ACCEPTED_AS_CORRECT` with `verdict: "reject"` and pass validation. This is low-risk because the substance gate (observations, hashes, reasoning) is the primary protection, and the verdict field is self-declared review metadata. But it is a design-doc deviation.

**Recommendation:** Add a consistency check mapping disposition to allowed verdicts, or document that verdict-disposition consistency is intentionally not enforced.

### N-2: Unused constants create drift risk

Two constants are defined but never imported or used in any logic:
- `HM_REVIEW_REQUIRED` in `scripts/workflow/reviews.py:54` — defined, never referenced outside the design doc.
- `HM_DISALLOWED_DISPOSITIONS` in `scripts/hm_review_contract.py:31` — defined, never referenced. The actual disallowed-disposition check in `policy.py` uses its own `HM_CRITICAL_READ_DISALLOWED` constant.

These serve as documentation but create a risk: a future change to one module's constant set won't propagate to the other. If `NOT_APPLICABLE` were ever removed from `HM_CRITICAL_READ_DISALLOWED` in policy.py, the unused `HM_DISALLOWED_DISPOSITIONS` in the contract module would still say it's disallowed, with no test catching the discrepancy.

**Recommendation:** Either wire these constants into the logic (import from a single source) or remove them and leave the design doc as the only documentation.

### N-3: `overall_reasoning` has no minimum length

The task description lists `overall_reasoning >= 20` as a minimum character requirement, but the implementation only checks `not overall_reasoning.strip()` (non-empty). The design doc's validation table says "presence check" for this field, so the implementation matches the design doc. The 20-char minimum applies to the disposition-level `reasoning` field, not `overall_reasoning`. This is correct per the design but worth noting as a potential source of confusion.

### N-4: Design doc mentions NEEDS_DISPOSITION case for runner validation

The design doc states the runner should validate when the verdict is `PASS` *or* `NEEDS_DISPOSITION` with `hm.critical_read` in `open_finding_ids`. The implementation only validates on `PASS`. This is sufficient: if policy returns `NEEDS_DISPOSITION` for `hm.critical_read`, it means the reasoning was < 10 chars (the policy floor), which is also below the contract's 20-char floor — validation would fail anyway. No real case exists where `NEEDS_DISPOSITION` + valid hm_review occurs. The implementation is correct; the design doc was overly cautious.

---

## Test Coverage Assessment

**Strengths:**
- Negative controls are thorough: bare string, filler reasoning, 10-char filler, generic template, `NOT_APPLICABLE`, `FALSE_POSITIVE` — all proven to fail closed.
- Positive controls cover all three valid dispositions: `ACCEPTED_AS_CORRECT`, `RESOLVED_EDIT`, `HUMAN_ACCEPTED_RISK` (including OVERRIDDEN integrity for the last).
- Staleness is tested at both layers: receipt hash chain (Resume/CoverLetter/JD changes) and review artifact hash mismatch.
- Truth isolation is explicitly tested: existing Truth disposition behavior proven unchanged.
- Idempotency and practice/production parity tested.
- `--force` bypass attempted and proven impossible.
- Unit tests for `validate_hm_review` cover the core validator independently of the runner.

**Gaps (all non-blocking — the validator code handles these cases, they're just not explicitly tested):**

| Gap | Validator handles it? | Risk |
|-----|----------------------|------|
| Missing `review_timestamp` | Yes (non-empty string check) | Low |
| Invalid `verdict` enum (e.g. "approve") | Yes (frozenset check) | Low |
| Invalid `recommendation` enum | Yes (frozenset check) | Low |
| Missing `overall_reasoning` | Yes (non-empty string check) | Low |
| Short `jd_relevance` (< 10 chars) | Yes (min chars check) | Low |
| Missing file on disk (e.g. Resume.md deleted) | Yes ("file that does not exist on disk" error) | Low |
| Wrong types (e.g. `observations` as string) | Yes (`isinstance(observations, list)` check) | Low |
| `Original_JD.txt` hash mismatch at unit level | Yes (REQUIRED_HASH_DOCS loop) | Low — covered at integration level by `test_jd_change_blocks_hm` |
| Verdict-disposition inconsistency (N-1) | No — not implemented | Low |

**Recommendation:** Add unit tests for the untested validator branches (missing `review_timestamp`, invalid `verdict`/`recommendation`, missing `overall_reasoning`, short `jd_relevance`, missing file on disk, wrong types). These are quick to add and would bring the unit test coverage to full branch coverage.

---

## Per-File Review Notes

### `scripts/hm_review_contract.py` (NEW)

Clean, well-structured validation module. Constants are well-named and scoped. The `_sha256_file` helper correctly returns `None` for missing files. The `validate_hm_review` function uses early returns for structural failures (non-dict, missing hm_review) which is appropriate — there's no point checking sub-fields if the container is wrong.

Error messages are descriptive and actionable (e.g., "stale review — document changed since review"). The `REQUIRED_HASH_DOCS` tuple includes `Original_JD.txt` alongside `Resume.md` and `CoverLetter.md`, which is correct for binding the review to the JD that was read.

The per-observation validation loop correctly accumulates `docs_seen` and checks coverage after the loop. The `continue` on non-dict observation prevents cascading errors from a single malformed entry.

**Minor:** `HM_DISALLOWED_DISPOSITIONS` is defined but unused (see N-2).

### `scripts/workflow/policy.py` (MODIFIED)

The `HM_CRITICAL_READ_DISALLOWED` constant and the check in `evaluate_truth_findings` are correctly placed after the invalid-disposition check and before the BLOCK-severity check. This means: invalid disposition → FAIL; `NOT_APPLICABLE`/`FALSE_POSITIVE` for hm.critical_read → FAIL; then BLOCK-severity logic proceeds normally. The ordering is correct.

The check uses `str(fid) == "hm.critical_read"` which is consistent with how `fid` is used elsewhere in the function (it comes from `item.get("id")` and is used as `str(fid)` in `open_ids.append`).

The error message is clear and directs the user to the correct alternative (`ACCEPTED_AS_CORRECT` with structured hm_review).

### `scripts/workflow/runner.py` (MODIFIED)

The HM validation block in `_apply_subphase_verdict` is well-commented and correctly scoped to `phase == "hm"` and `verdict["verdict"] == "PASS"`. The local import of `hm_review_contract` avoids adding a module-level dependency for a phase-specific check.

The downgrade logic creates a new verdict dict with `NEEDS_DISPOSITION` and the validation errors as reasons. This flows correctly into the existing `NEEDS_DISPOSITION` handling below (writes state, emits event, returns).

The loop correctly filters for `fid == "hm.critical_read"` and only validates when `disp_s in HM_REVIEW_DISPOSITIONS`. Since `HM_REVIEW_DISPOSITIONS = {"ACCEPTED_AS_CORRECT", "RESOLVED_EDIT", "HUMAN_ACCEPTED_RISK"}` and these are exactly the three dispositions that can PASS policy for a WARN finding, every path to PASS is covered.

### `scripts/workflow/reviews.py` (MODIFIED)

`HM_REVIEW_REQUIRED` constant added but unused (see N-2). The updated `_write_dispositions` note text correctly describes the structured review requirement for `hm.critical_read` and the disallowance of `NOT_APPLICABLE`/`FALSE_POSITIVE`. The note is templated with the slug placeholder for the resume command, which is helpful for the human filling in dispositions.

### `scripts/test_hm_critical_read_contract.py` (NEW)

Well-organized into 7 test classes with clear separation of concerns:
- `TestBareAndFillerDispositionsFail` — 6 negative controls
- `TestValidStructuredReviewClears` — 3 positive controls
- `TestStalenessViaDocumentChange` — 4 staleness tests
- `TestMalformedReviewFailsClosed` — 6 malformed-artifact tests
- `TestIdempotencyAndParity` — 2 tests
- `TestForceAndTruthIsolation` — 3 tests
- `TestValidateHMReviewUnit` — 6 unit tests

The `HMContractTestBase` shared setup is well-factored. The mock chain through Stage 0 → Stage 1 → Truth → ATS is comprehensive and reaches the HM entry point realistically. The `_valid_structured_review` helper builds a correctly-shaped artifact with real file hashes.

**Minor:** `FakeLint` uses class-level `blocks` and `warns` (empty lists) which is fine for the mock purpose but could be confused with mutable class state. Not a real issue since the tests don't mutate them.

### `scripts/test_workflow_authority.py` (MODIFIED)

The `test_stage2_receipt_after_policy` test correctly provides a valid structured review artifact for `hm.critical_read` with real file hashes, reviewer role, observations, verdict, and overall_reasoning. The test verifies that HM subphase reaches COMPLETE, then proceeds through mech and policy. This is the right update — the test would have failed without the structured review after the contract was added.

### `docs/spec/08-implementation/CR-112-hm-critical-read-contract-design.md` (NEW)

Thorough design document. Clearly articulates the problem, design principles, schema, validation rules, disposition semantics, staleness strategy, and reviewer independence model. The "What This Contract Does Not Prove" and "What This Contract Prevents" sections are particularly valuable for setting expectations. The document is honest about the contract's limitations (it prevents silent self-certification, not self-certification itself).

---

## Bypass Path Analysis (Exhaustive)

| Disposition value for hm.critical_read | Policy verdict | Runner validation | Final outcome | Correct? |
|---|---|---|---|---|
| `None` / missing | NEEDS_DISPOSITION (open) | Not fired (not PASS) | NEEDS_DISPOSITION | Yes |
| `"RESOLVED_EDIT"` (bare string) | PASS (WARN, not in REASONING_REQUIRED) | Not a dict → fail | NEEDS_DISPOSITION | Yes |
| `{"disposition": "RESOLVED_EDIT", "reasoning": "fixed it"}` | PASS | No hm_review → fail | NEEDS_DISPOSITION | Yes |
| `{"disposition": "ACCEPTED_AS_CORRECT", "reasoning": "looks fine"}` | NEEDS_DISPOSITION (reasoning < 10) | Not fired (not PASS) | NEEDS_DISPOSITION | Yes |
| `{"disposition": "ACCEPTED_AS_CORRECT", "reasoning": "long enough...", "hm_review": {valid}}` | PASS | Validated → pass | COMPLETE | Yes |
| `"NOT_APPLICABLE"` | FAIL (disallowed) | Not fired (FAIL) | FAIL (WorkflowError) | Yes |
| `"FALSE_POSITIVE"` | FAIL (disallowed) | Not fired (FAIL) | FAIL (WorkflowError) | Yes |
| `{"disposition": "HUMAN_ACCEPTED_RISK", "reasoning": "risk accepted...", "hm_review": {valid}}` | PASS | Validated → pass | COMPLETE + OVERRIDDEN | Yes |
| Valid review + stale hash | PASS | Hash mismatch → fail | NEEDS_DISPOSITION | Yes |
| Valid review + file deleted after | PASS | File not on disk → fail | NEEDS_DISPOSITION | Yes |

No bypass path identified.

---

## Truth Subphase Isolation Verification

- `HM_CRITICAL_READ_DISALLOWED` check in `policy.py` is gated by `str(fid) == "hm.critical_read"` — no other finding ID is affected.
- Runner HM validation is gated by `phase == "hm"` — Truth, ATS, and Mech phases are unaffected.
- Tests `test_truth_disposition_behavior_not_weakened` and `test_truth_resolved_edit_still_works_without_reasoning` explicitly prove existing Truth behavior is preserved.
- The `evaluate_truth_findings` function's return signature and logic flow are unchanged for non-hm.critical_read findings.

---

## Final Assessment

The implementation is sound, well-tested, and correctly prevents the gap it was designed to close. The two non-blocking observations (verdict-disposition consistency, unused constants) are minor and do not compromise the contract's security goal. The test coverage gaps are all in validator edge-case branches that are handled by the code but not explicitly exercised by tests. Recommend accepting with the optional improvements noted above.
