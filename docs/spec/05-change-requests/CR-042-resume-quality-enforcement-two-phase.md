# CR-042 — Resume Quality Enforcement (Two-Phase Plan)

| Field | Value |
|---|---|
| **Status** | implemented |
| **Related** | `FR-220`–`FR-225`, `FR-176`, `FR-201`, `CR-027`, `CR-031`, `CR-014` |
| **Source** | CVS conversion loop (2026-06); fleet-quality gap analysis |

## Problem

CR-027 built **detection** (conversion critique, theme guard, PDF layout, framing rules) but not **enforcement** or **fleet proof**:

1. `conversion_critique.pass: false` still exports Resume.pdf — advisory only.
2. `SUBMISSION_MODE` enables `STRICT_COVER_AUDIT` but not conversion critique.
3. No auto-retry when fixable critique failures occur (manual CVS loop was required).
4. Golden tests and smoke do not require critique PASS across JD archetypes.
5. Existing `submissions/*` folders are stale until regen; no fleet rollup.

**Goal:** CVS-quality resumes become the **floor** for every export, not the ceiling for manually iterated jobs.

## Strategy — Two phases, six sub-phases

```
Phase 1 — ENFORCE (block bad exports + self-heal)
  1A  Strict conversion critique gate
  1B  Auto-retry loop (fixable rules)
  1C  Retry action map + manifest telemetry

Phase 2 — PROVE (regression + fleet)
  2A  Golden JD fixtures + smoke PASS requirement
  2B  Fleet quality report + optional batch regen
  2C  Operator workflow + SUBMISSION_MODE defaults
```

Phases are sequential: **1 must ship before 2** (2A tests assume 1B retry exists; 2B assumes strict gate is available).

---

## Phase 1 — Enforce

### Sub-phase 1A — Strict conversion critique gate

**Intent:** Fail closed when human-mirror critique fails, mirroring `STRICT_COVER_AUDIT`.

| ID | Requirement |
|---|---|
| `FR-226` | `STRICT_CONVERSION_CRITIQUE=1` raises `DraftingPipelineError` when `evaluate_resume_conversion().pass` is false after PDF export |
| `FR-227` | `apply_submission_defaults()` sets `STRICT_CONVERSION_CRITIQUE=1` when `SUBMISSION_MODE=1` (setdefault; explicit env override allowed) |

**Implementation targets:**

- `scripts/pipeline_env.py` — `strict_conversion_critique()`
- `scripts/draft_compiler.py` — after critique eval, raise if strict + fail (same pattern as cover audit ~L398)
- `.agent/rules/pipeline_env.md` — document flag

**Acceptance:**

- `AC-251`: With `STRICT_CONVERSION_CRITIQUE=1`, a resume that triggers CW-011 does not write final `Resume.pdf` (or raises before manifest finalize).
- `AC-252`: With flag off (default), behavior unchanged — log + manifest only.

**Out of scope for 1A:** Auto-fix; retry comes in 1B.

---

### Sub-phase 1B — Auto-retry loop

**Intent:** Before strict gate fires, attempt deterministic fixes for critique codes we already know how to heal (the CVS manual loop, automated).

| ID | Requirement |
|---|---|
| `FR-228` | `draft_compiler` runs up to `CONVERSION_RETRY_MAX` attempts (default **2**, env override) when critique fails on **fixable** codes only |
| `FR-229` | New `scripts/critique_retry.py` maps blocking CW codes → retry actions; re-exports PDF and re-evaluates after each pass |

**Fixable code map (v1):**

| Code | Retry action |
|------|----------------|
| `CW-011` | Rebuild summary via `build_summary_deterministic()` with `force_complete_proof=True` |
| `CW-013` | Strip stacked proof; single-proof rebuild |
| `CW-014` | Re-run `summary_focus_phrase()` with next experience-backed theme |
| `CW-015` | Re-select attribution proof with adoption payoff clause |
| `CW-012` | Re-run `enforce_sterkly_context()` + weak-claim swap on bullets |
| `CW-009` | Re-compile PDF only (layout already fixed; catches transient export glitches) |

**Non-fixable (hard fail on final attempt):** Any code not in map; multiple simultaneous failures where retry fixes one but leaves another; missing catalog claims for swap targets.

**Flow:**

```
compose bullets → summary → PDF → critique
  ↓ fail + fixable + attempts < MAX
critique_retry.apply_fixes() → re-summary and/or re-frame → PDF → critique
  ↓ pass OR attempts exhausted
strict gate (1A) if enabled → export or raise
```

**Acceptance:**

- `AC-253`: Fixture resume with truncated proof passes critique within 2 attempts without manual edit.
- `AC-254`: `draft_manifest.json` records `conversion_critique.attempts` and `conversion_critique.retry_log[]` (code + action per attempt).

---

### Sub-phase 1C — Retry telemetry + error surfaces

**Intent:** Operator sees *what* was retried and *why* export still failed.

| ID | Requirement |
|---|---|
| `FR-230` | Console prints retry attempt summary; final FAIL lists unresolved CW codes with one-line remediation hints |

**Implementation targets:**

- `scripts/critique_retry.py` — `REMEDIATION_HINTS` dict
- `scripts/draft_compiler.py` — manifest fields + console formatting

**Acceptance:**

- `AC-255`: On exhausted retries + strict on, error message includes failing codes and hints (not bare stack trace).

---

## Phase 2 — Prove

### Sub-phase 2A — Golden JD fixtures + smoke

**Intent:** CI catches regressions before Jason does.

| ID | Requirement |
|---|---|
| `FR-231` | `smoke_draft_compiler.py` (or `test_smoke_regression.py` REG-* row) runs **3 JD archetype fixtures** end-to-end through summary + framing + critique eval |
| | Archetypes: **analytics-heavy PM**, **platform/data integrity**, **generic B2B PM** (synthetic JD snippets, not real employer text) |
| | Each fixture asserts `conversion_critique.pass is True` after retry loop (retry max = 2 in test env) |

**Acceptance:**

- `AC-256`: `python scripts/smoke_draft_compiler.py` fails if any archetype critique fails.
- `AC-257`: `scripts/test_resume_conversion_eval.py` + `test_experience_theme_guard.py` remain green (no regression).

---

### Sub-phase 2B — Fleet quality report

**Intent:** Answer "what % of submissions are CVS-quality **right now**?"

| ID | Requirement |
|---|---|
| `FR-232` | New `scripts/fleet_conversion_report.py` scans `submissions/*/draft_manifest.json` (and `archive/submissions/` optional flag) |
| | Outputs: total folders, manifests with critique, pass rate, top failing codes, folders missing manifest |
| | Optional `--regen-missing` calls `regenerate_all_resumes.py` logic per folder (off by default) |

**Acceptance:**

- `AC-258`: Report prints pass rate and lists failing company folders sorted by issue count.
- `AC-259`: After full fleet regen with `SUBMISSION_MODE=1`, pass rate ≥ **80%** (baseline target; document failures in report, not block CR close).

**Note:** 80% is a **baseline measurement**, not a permanent gate. Failures become CR-043 input if systemic.

---

### Sub-phase 2C — Operator workflow

**Intent:** Document the ship gate so agents and Jason use the same checklist.

**Updates:**

- `docs/ACTIVE_WORKFLOW.md` — new subsection **"Resume ship gate"**:
  - Real applications: `SUBMISSION_MODE=1` (includes strict critique + cover audit + metrics).
  - Before apply: `conversion_critique.pass === true` in manifest.
  - If fail: read `retry_log`; fix catalog/JD fit; regen — do not hand-edit around guards.
- `PRODUCT_CAPABILITIES_AND_RELEASE_NOTES.md` — entry when Phase 1 ships.

**Acceptance:**

- `AC-260`: ACTIVE_WORKFLOW documents SUBMISSION_MODE flag bundle including `STRICT_CONVERSION_CRITIQUE`.

---

## Environment flags (summary)

| Flag | Default | Phase | Effect |
|------|---------|-------|--------|
| `STRICT_CONVERSION_CRITIQUE` | off | 1A | Fail export on critique fail |
| `CONVERSION_RETRY_MAX` | `2` | 1B | Max auto-retry attempts before strict gate |
| `SUBMISSION_MODE` | off | 1A | setdefault enables strict critique (with existing strict bundle) |

---

## Files (expected touch list)

| Phase | Files |
|-------|-------|
| 1A | `pipeline_env.py`, `draft_compiler.py`, `.agent/rules/pipeline_env.md` |
| 1B | `critique_retry.py` (new), `draft_compiler.py`, `local_draft_stages.py`, `conversion_framing.py` |
| 1C | `critique_retry.py`, `draft_compiler.py` |
| 2A | `smoke_draft_compiler.py`, `test_smoke_regression.py`, fixture JDs under `scripts/fixtures/` |
| 2B | `fleet_conversion_report.py` (new), `regenerate_all_resumes.py` (header/docs only) |
| 2C | `ACTIVE_WORKFLOW.md`, `PRODUCT_CAPABILITIES_AND_RELEASE_NOTES.md` |

---

## Implementation order (checklist)

- [x] **1A** — `strict_conversion_critique()` + raise in compiler
- [x] **1B** — `critique_retry.py` + retry loop in compiler
- [x] **1C** — manifest `attempts` / `retry_log` + remediation hints
- [x] **2A** — three archetype fixtures + smoke assertion
- [x] **2B** — fleet report script + one baseline run (record % in IMP doc)
- [x] **2C** — ACTIVE_WORKFLOW ship gate + SUBMISSION_MODE docs
- [x] Registry + traceability + IMP doc verification commands

---

## Deferred (not in CR-042)

- Promoting CW-001 / CW-003 from advisory to blocking (needs false-positive audit).
- Auto-retry for cover letter audit failures (separate CR).
- Unified "ship score" merging rubric + critique (FR-201 extension).
- WebApp UI badge for `conversion_critique.pass` (FEAT follow-on).

---

## Verification (full CR-042)

```bash
python scripts/test_resume_conversion_eval.py
python scripts/test_experience_theme_guard.py
python scripts/smoke_draft_compiler.py
python scripts/test_smoke_regression.py
# Phase 1 manual:
SUBMISSION_MODE=1 python scripts/draft_cvs_direct.py   # expect PASS or raised error with hints
# Phase 2:
python scripts/fleet_conversion_report.py
```
