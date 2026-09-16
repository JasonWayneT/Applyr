---
status: implementation_contract_locked
created: 2026-09-12
locked: 2026-09-13
from: Cursor (Grok 4.6)
design_review: Cursor (Claude Opus 4.6)
review_id: 82a6f3d1-c5e0-4e1a-9b3f-d7c412f8a091
candidate: cr112-integrated-validation-candidate
related: CR-112, SESSION-HANDOFF-2026-09-12-cr112-product-proof-camunda.md
scope: privacy-safe identity for practice runs and clean worktrees
do_not_bundle: completion-floor story (FR-318)
verdict: ACCEPT WITH CHANGES
head_at_review: bf84afe
---

# CR-112 practice identity portability

Bounded design. Do not implement in the same commit as the
CONVERT-READY floor gate. Do not copy production SQLite. Do not put
PII in tracked fixtures, logs, commits, prompts, or reports.

## Proven defect (Camunda product-proof)

Claude had to insert a real identity row into this worktree's
`data/jobagent.sqlite` because `profiles.identity` was missing.
Without that row, `scripts/utils.py` `load_identity_profile()` fills
`_DEFAULT_IDENTITY` (John Doe / `555-019-9238` / `email@example.com`).
`quality_checker.check_and_repair_cover_letter` H-001 can then inject
that placeholder header above a real one.

That local DB write unblocked the run. It is not a portable fix for
the next clean worktree or harness.

Canonical header substitution already exists:
`scripts/apply_resume_header.py` reads gitignored
`data/workExperience.md` Section 1.0. Packet and digest have no
contact fields by design.

---

## Locked implementation contract (Story 8.2)

**Requirement:** `SEC-006` (draft). **Verdict:** ACCEPT WITH CHANGES.

Changes folded into this contract vs. the original design sketch:
1. Source order is now fully specified with exact precedence, not a table of modes.
2. Exact fail point named (function, stage, error shape).
3. `_apply_resume_header_if_available` SKIP behavior is reclassified as a FAIL.
4. Synthetic mode mechanism is env-only (no CLI flag on `run_submission.py`).
5. In-scope vs out-of-scope call sites are enumerated, not implied.
6. `load_identity_profile` keeps John Doe only when synthetic mode is active.
7. `quality_checker._candidate_name_upper` second John Doe fallback removed.
8. `workflow_state.json` records `identity_source`, not `identity_mode`.

### Decision 1: Source order

Identity resolution follows this precedence, in order, on every
path that produces or validates a document carrying a name/contact
header:

1. **Synthetic fixture identity** when (and only when)
   `APPLYR_SYNTHETIC_IDENTITY=1` is set in the environment.
   Short-circuits before any WE read so tests never ingest live PII.
   Returns a hardcoded unmistakably-fake identity (see Decision 6).
   Never used on a real or practice submission path unless the env
   var is explicitly set.

2. **workExperience.md** Section 1.0 via `apply_resume_header.load_real_header()`.
   This is the canonical source of truth for real and practice runs.
   If WE is present and parseable, identity comes from here. No
   SQLite read needed. `load_identity_profile()` must call this
   helper; Decision 4 must not raise before trying WE.

3. **Missing.** If WE is absent/malformed and synthetic mode is not
   active, identity resolution fails closed. No SQLite fallback.
   No `_DEFAULT_IDENTITY` fallback. The pipeline stops.

SQLite `profiles.identity` is **not in this precedence chain at all.**
It remains as a UI/Settings cache for the web app's display layer.
The document-authoring pipeline never reads it for identity.
This is the core portability fix: a clean worktree with
`workExperience.md` present works without any SQLite row.

### Decision 2: Exact fail point

The fail point is `author_from_packet.run_verify_only()`, specifically
the existing call to `_apply_resume_header_if_available(folder)` at
line ~511.

**Current behavior:** returns `SKIP [apply_resume_header] - {exc}` as
a non-fatal log line when `load_real_header()` raises (WE missing or
malformed). The verify pass continues and may succeed. `quality_checker`
then runs, calls `load_identity_profile()` which silently fills
`_DEFAULT_IDENTITY`, and H-001 can inject John Doe above a real header.

**Required behavior:** when `_apply_resume_header_if_available` cannot
resolve identity (WE missing/malformed AND synthetic mode not active),
it must return a FAIL result, not SKIP. `run_verify_only` must treat
this as `passed = False`.

**Error shape:**

```
FAIL [identity] - workExperience.md missing or malformed;
set APPLYR_SYNTHETIC_IDENTITY=1 for test/eval mode,
or copy workExperience.md into this worktree
(identity_source=missing)
```

**Stage gate (brief: fail before authoring):** `run_stage1_prompt`
must call the same identity resolver *before* minting
`WAITING_FOR_LLM`. Missing or malformed identity raises `WorkflowError`
with the error shape above. No `authoring_prompt.md` WAITING receipt
is written. Packet assembly may be skipped; do not invite an author
paste when headers cannot be filled.

`run_verify_only` FAIL remains defense in depth for a folder that
already has docs (adopt, `--resume` after a prior prompt, or a
hand-dropped draft).

### Decision 3: `_apply_resume_header_if_available` SKIP reclassification

The function currently returns SKIP strings on three conditions:
- Import of `apply_resume_header` fails
- `load_real_header()` raises (WE missing/malformed)
- No Resume.md/CoverLetter.md in folder

**New behavior:**
- Import failure: FAIL (not SKIP). This is a broken installation.
- `load_real_header()` raises AND synthetic mode is not active: **FAIL**.
  The error text names `identity_source=missing` and the corrective
  action (copy WE or set env var).
- `APPLYR_SYNTHETIC_IDENTITY=1`: SKIP immediately, even if WE exists.
  Tests must not patch live PII into temp documents. Synthetic
  identity is applied via `load_identity_profile` / quality_checker
  H-001, not via `load_real_header`.
- No documents in folder: SKIP remains correct (nothing to patch).

**The caller `run_verify_only` must check:** if the return string starts
with `FAIL`, set `passed = False`.

### Decision 4: `load_identity_profile` and `_DEFAULT_IDENTITY`

`_DEFAULT_IDENTITY` (John Doe dict) stays in the codebase as the
synthetic fixture identity. It is no longer a silent fallback.

**`load_identity_profile()` new behavior:**

1. If `APPLYR_SYNTHETIC_IDENTITY=1` env var is set: return
   `_SYNTHETIC_IDENTITY` immediately, without reading SQLite or WE.
   Log `identity_source=synthetic` (no PII in log).

2. Else try `apply_resume_header.load_real_header()`. On success,
   map that dict into the identity profile shape (name/email/phone/
   linkedin/location; empty portfolio/github). Log `identity_source=we`.

3. If WE is absent or malformed: **raise `IdentityError`**
   (a new, specific exception, subclass of `RuntimeError`) instead of
   silently returning `_SYNTHETIC_IDENTITY`. Message:
   `"No identity source available - workExperience.md missing and `
   `APPLYR_SYNTHETIC_IDENTITY not set"`
   Log `identity_source=missing` (no PII in log).

3. The SQLite read path is **removed** from `load_identity_profile`.
   SQLite identity is a web-app concern, not a pipeline concern.
   If the web app needs identity, it reads SQLite directly through
   its own route handlers, not through this function. (This is the
   smallest change that closes the defect; the web app already has
   its own DB access patterns.)

**Rationale for removing SQLite from `load_identity_profile`:**
The defect's root cause is that `load_identity_profile` has a
three-layer cascade (SQLite row > default dict) that silently
succeeds even when neither real source is available. Keeping SQLite
as a fallback between WE and synthetic creates a second path where
copying production SQLite into a worktree "works" and re-enables the
exact portability defect this story fixes. The cleanest cut is:
pipeline identity = WE or synthetic. Period.

### Decision 5: In-scope vs out-of-scope call sites

**In-scope (canonical `run_submission.py` path, must be changed):**

| File | Function/line | What it does with identity | Change |
|---|---|---|---|
| `scripts/utils.py` ~458-490 | `_DEFAULT_IDENTITY`, `load_identity_profile()` | Silent John Doe fallback via SQLite cascade | Rewrite per Decision 4 |
| `scripts/utils.py` ~506-520 | `format_contact_header_block()`, `format_contact_line()`, `contact_placeholder_map()` | Call `load_identity_profile()` as default | No change needed; these will naturally raise `IdentityError` if identity is missing (callers handle it) |
| `scripts/author_from_packet.py` ~322-348 | `_apply_resume_header_if_available()` | SKIPs on missing WE | Rewrite per Decision 3 |
| `scripts/quality_checker.py` ~10-17 | `_header_block()`, `_candidate_name_upper()` | Calls `load_identity_profile`, second John Doe fallback in `_candidate_name_upper` | Remove `or "John Doe"` fallback; let `IdentityError` propagate to `run_verify_only` which catches exceptions and reports FAIL |
| `scripts/workflow/runner.py` | `run_stage1_prompt`, `run_stage1_validate` | No identity check; WAITING_FOR_LLM can mint without WE | Require identity before WAITING_FOR_LLM; record `metadata.identity_source` |
| `scripts/verify_submission.py` ~172-210 | `_check_pdf_parseability()` | Reads name from `.md` H1 line, not from `load_identity_profile` | No change needed (reads from the document, not from the identity function) |

**Out of scope (not on canonical `run_submission.py` path):**

| File | Why out of scope |
|---|---|
| `scripts/drafting_engine.py` | Legacy pre-CR-074 draft engine. Not imported by `runner.py` or `author_from_packet.py`. Not on the canonical path. Leave as-is; it will naturally fail loudly if `load_identity_profile` raises, which is correct. |
| `scripts/local_draft_stages.py` | Legacy local draft pipeline. Not imported by `runner.py`. Same treatment. |
| `scripts/cover_letter_renderer.py` | Legacy cover letter renderer. Not imported by `runner.py`. Same treatment. |
| `scripts/draft_compiler.py` | Legacy draft compiler. Not imported by `runner.py`. Same treatment. |
| `scripts/candidate_context.py` | Legacy candidate context builder. Not imported by `runner.py`. Same treatment. |
| `scripts/audit_and_improve.py` | Standalone audit script. Not imported by `runner.py`. Same treatment. |
| `scripts/style_compliance_guard.py` | Standalone style guard. Not imported by `runner.py` or `author_from_packet.py`. Same treatment. |
| `scripts/test_utils_header_casing.py` | Test file; updated under Decision 8. |
| `scripts/test_candidate_context.py` | Test file; no change unless it calls `load_identity_profile` without mocking. |

The out-of-scope files all import `load_identity_profile` with
lazy-import (`from utils import ...` inside a function body or at
module top). After this change, they will raise `IdentityError` if
called without WE or synthetic mode. This is **correct and desired**:
those legacy engines should not silently produce John Doe output
either. No wrapping or fallback is added for them. If they are ever
called, the new error is more actionable than silent placeholder
injection.

### Decision 6: Synthetic mode mechanism

**Env var only: `APPLYR_SYNTHETIC_IDENTITY=1`**

No CLI flag on `run_submission.py`. Rationale:
- `run_submission.py` is the production orchestrator. A `--synthetic-identity`
  flag on it implies synthetic identity is a normal workflow option.
  It is not. It is a test/eval escape hatch.
- Env var is the right scope: set it in a test runner, a CI script,
  or a shell session running eval. It does not leak into production
  invocations.
- Tests set it via `os.environ` / `monkeypatch` in their setup.
- `run_cr112_eval.py` (Story 6.1) sets it before assembling eval
  fixtures.

**Synthetic identity values** (reuse existing `_DEFAULT_IDENTITY` as-is):

```python
_SYNTHETIC_IDENTITY = {
    "name": "John Doe",
    "email": "email@example.com",
    "phone": "555-019-9238",
    "location": "City, State",
    "linkedin": "linkedin.com/in/johndoe",
    "portfolio": "johndoe.com",
    "github": "",
}
```

Rename the constant from `_DEFAULT_IDENTITY` to `_SYNTHETIC_IDENTITY`
to make intent clear. Update all references (only in `utils.py`).

### Decision 7: Logging

Every identity resolution logs exactly one of:

```
identity_source=we
identity_source=synthetic
identity_source=missing
```

via `print(f"[identity] identity_source={source}", file=sys.stderr)`.

**Never log:** name, email, phone, LinkedIn URL, location, or any
other PII field. The log line is the source tag only.

The `identity_source` is also recorded in `workflow_state.json` under
`metadata.identity_source` when `run_stage1_validate` completes
(COMPLETE or FAIL). This is informational only (not a gate).

### Decision 8: Test plan

All tests use synthetic identity only. No production DB copy.
No real PII in fixtures.

| Test | What it proves | Fixture |
|---|---|---|
| `test_identity_missing_fails_closed` | `load_identity_profile()` raises `IdentityError` when WE is absent and `APPLYR_SYNTHETIC_IDENTITY` is not set | Temp dir with no `workExperience.md`, no env var |
| `test_identity_synthetic_mode` | `load_identity_profile()` returns `_SYNTHETIC_IDENTITY` when `APPLYR_SYNTHETIC_IDENTITY=1` is set, without reading SQLite or WE | Env var set, no WE, no SQLite |
| `test_identity_we_source` | `load_real_header()` succeeds when WE is present; returns dict with expected fields | Minimal synthetic WE fixture with Section 1.0 fields (fake name/email/phone, not real PII) |
| `test_apply_header_fails_without_identity` | `_apply_resume_header_if_available` returns FAIL (not SKIP) when WE is absent and synthetic mode is off | Temp folder with Resume.md containing placeholder header, no WE |
| `test_apply_header_skips_in_synthetic_mode` | `_apply_resume_header_if_available` returns SKIP when WE is absent but `APPLYR_SYNTHETIC_IDENTITY=1` | Same temp folder, env var set |
| `test_verify_only_fails_on_identity_missing` | `run_verify_only` returns `False` when identity is unavailable | Temp submission folder with Resume.md + CoverLetter.md, no WE, no env var |
| `test_quality_checker_no_john_doe_fallback` | `_candidate_name_upper()` does not return `JOHN DOE` when identity is missing (raises instead) | No WE, no env var |
| `test_h001_inject_uses_synthetic_not_default` | H-001 header inject in `check_and_repair_cover_letter` uses synthetic identity when env var is set, not a hidden default | Synthetic mode on, cover letter missing header |
| `test_no_pii_in_log_output` | Identity resolution stderr output contains `identity_source=` but no name/email/phone/linkedin values | Capture stderr during `load_identity_profile` in synthetic mode |
| `test_existing_header_casing` (update existing) | `test_utils_header_casing.py` passes synthetic profile explicitly, does not rely on DB | Already passes profile; verify no DB read path |

**Negative controls:**
- `test_identity_missing_fails_closed` proves the absence of John Doe.
- `test_verify_only_fails_on_identity_missing` proves the pipeline stops.
- `test_quality_checker_no_john_doe_fallback` proves the second fallback is gone.

**No production DB copy in any test.** Tests that previously relied on
`load_identity_profile()` returning John Doe via the default cascade
must either pass a synthetic profile explicitly or set the env var.

### Decision 9: Security review

**Required after implementation, before merge.** Scope:
- Confirm no PII in tracked files (grep for phone patterns, email patterns, real name).
- Confirm SQLite read path is removed from `load_identity_profile`.
- Confirm `_SYNTHETIC_IDENTITY` values are obviously fake.
- Confirm log lines contain only `identity_source=` tag.
- Confirm no test fixture contains real PII.
- Brief, recorded in this doc or the QA review artifact.

### Decision 10: FR/AC status updates

**SEC-006** status: `draft` -> `in_progress` after implementation begins.
`SEC-006` -> `implemented` after QA PASS.

New acceptance criterion (register in `02-requirements-registry.md`):

| ID | Type | Priority | Status | Statement | Acceptance | Source |
|---|---|---|---|---|---|---|
| `AC-416` | acceptance | P0 | draft | Clean worktree with WE present and no SQLite identity row: `run_verify_only` passes and documents carry WE identity, not John Doe. Clean worktree with neither WE nor SQLite: `run_verify_only` fails with `identity_source=missing`. `APPLYR_SYNTHETIC_IDENTITY=1`: `load_identity_profile` returns synthetic identity without reading SQLite or WE. No PII in tracked test fixtures, logs, or commits. `_DEFAULT_IDENTITY` renamed to `_SYNTHETIC_IDENTITY`. | `SEC-006` | CR-112 |

---

## Canonical sources (keep them separate)

| Mode | Source | When |
|---|---|---|
| Real local (production or practice against a real JD) | `workExperience.md` Section 1.0 via `apply_resume_header.load_real_header()` | Required before authoring a document that will carry a name/contact header |
| SQLite `profiles.identity` | Web app display layer only; **not** in the pipeline identity chain | UI Settings projection; never read by `load_identity_profile` after this story |
| Synthetic fixture | `APPLYR_SYNTHETIC_IDENTITY=1` env var; returns `_SYNTHETIC_IDENTITY` (John Doe) | Unit tests and sanitized eval fixtures only |

Never emit plausible placeholder identity into a real or practice
document without that synthetic mode. John Doe in `_SYNTHETIC_IDENTITY`
is fixture-shaped and explicitly opt-in, not a silent fallback.

## Acceptance criteria (full)

- Clean worktree with WE present, sqlite identity absent: header
  lands from WE, no placeholder, no production DB read.
- Clean worktree with neither WE nor identity: authoring/header step
  raises a clear error naming `identity_source=missing`; no John Doe document.
- `APPLYR_SYNTHETIC_IDENTITY=1` writes only the documented fake fixture
  identity, and the `workflow_state.json` records `identity_source=synthetic`.
- Real identity path records `identity_source=we` in `workflow_state.json`.
- Tracked tests never contain Jason's real contact fields.
- `load_identity_profile()` no longer reads SQLite.
- `_DEFAULT_IDENTITY` renamed to `_SYNTHETIC_IDENTITY`.
- `quality_checker._candidate_name_upper()` no longer has `or "John Doe"` fallback.
- All existing tests pass (with synthetic env var set where needed).
- Security review recorded before merge.

## Out of scope

CONVERT-READY floors. Camunda re-author. Production sqlite. Copying
PII into this design doc. Legacy draft engines (`drafting_engine.py`,
`local_draft_stages.py`, `cover_letter_renderer.py`, `draft_compiler.py`,
`candidate_context.py`, `audit_and_improve.py`, `style_compliance_guard.py`)
are not on the canonical `run_submission.py` path and receive no
wrapping or fallback; they will raise `IdentityError` if called
without WE, which is correct and more actionable than silent John Doe.
