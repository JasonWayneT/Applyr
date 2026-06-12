# IMP-CR-042: Resume Quality Enforcement (Two-Phase)

## Metadata

| Field | Value |
|---|---|
| **CR ID** | `CR-042` |
| **Date** | 2026-06-05 |
| **Status** | Implemented |
| **Requirement IDs** | `FR-226`–`FR-232` |

## Sub-phase task map

| Sub-phase | Task | Owner | Depends |
|-----------|------|-------|---------|
| **1A** | Add `strict_conversion_critique()` to `pipeline_env.py` | agent | — |
| **1A** | Wire raise in `draft_compiler.py` post-critique (mirror `STRICT_COVER_AUDIT`) | agent | 1A flag |
| **1A** | Extend `apply_submission_defaults()` with `STRICT_CONVERSION_CRITIQUE` | agent | 1A flag |
| **1A** | Update `.agent/rules/pipeline_env.md` | agent | 1A flag |
| **1B** | Create `scripts/critique_retry.py` with `FIXABLE_CODES`, `apply_critique_fixes()` | agent | — |
| **1B** | Extract retry-safe summary rebuild hooks in `local_draft_stages.py` if needed | agent | 1B module |
| **1B** | Wrap compile+critique in retry loop in `draft_compiler.py` | agent | 1A, 1B |
| **1C** | Add `attempts`, `retry_log`, `final_codes` to manifest critique object | agent | 1B loop |
| **1C** | `REMEDIATION_HINTS` + formatted `DraftingPipelineError` message | agent | 1B |
| **2A** | Add `scripts/fixtures/jd_archetype_*.txt` (3 files, synthetic) | agent | 1B |
| **2A** | Extend `smoke_draft_compiler.py` with archetype critique PASS asserts | agent | 1B, fixtures |
| **2A** | Register in `test_smoke_regression.py` if separate REG row needed | agent | 2A smoke |
| **2B** | Create `scripts/fleet_conversion_report.py` | agent | 1C manifest shape |
| **2B** | Run baseline fleet report; record pass % in this IMP doc **Verification results** | Jason/agent | 2B script |
| **2C** | ACTIVE_WORKFLOW ship gate section | agent | 1A |
| **2C** | Release note when Phase 1 merges | agent | 1A–1C |

## Code map (target)

| Requirement | File | Symbol |
|---|---|---|
| `FR-226` | `pipeline_env.py` | `strict_conversion_critique()` |
| `FR-226` | `draft_compiler.py` | raise after critique when strict |
| `FR-227` | `pipeline_env.py` | `apply_submission_defaults()` |
| `FR-228` | `draft_compiler.py` | retry loop around PDF + critique |
| `FR-229` | `critique_retry.py` | `apply_critique_fixes()`, `FIXABLE_CODES` |
| `FR-230` | `critique_retry.py` | `REMEDIATION_HINTS` |
| `FR-231` | `smoke_draft_compiler.py` | archetype fixture tests |
| `FR-232` | `fleet_conversion_report.py` | `main()`, `scan_submissions()` |

## Retry loop pseudocode (1B)

```python
max_attempts = conversion_retry_max()  # default 2
for attempt in range(1, max_attempts + 1):
    pdf_path = compile_resume(...)
    critique = evaluate_resume_conversion(...)
    if critique["pass"]:
        break
    if attempt < max_attempts and has_fixable(critique):
        bullets, summary = apply_critique_fixes(critique, bullets, summary, ...)
        retry_log.append(...)
    else:
        break
if strict_conversion_critique() and not critique["pass"]:
    raise DraftingPipelineError(format_critique_failure(critique, retry_log))
```

## Verification results

| Run | Date | Pass rate | Notes |
|-----|------|-----------|-------|
| Fleet baseline | 2026-06-05 | 100% (1/1 with critique) | 10 folders; 9 lack `conversion_critique` until regen |

## Exit criteria (CR-042 done)

1. Phase 1: CVS regen with `SUBMISSION_MODE=1` → critique PASS without manual intervention.
2. Phase 1: Deliberately broken summary fixture → retry heals OR strict error with CW codes + hints.
3. Phase 2: `smoke_draft_compiler.py` green on 3 archetypes.
4. Phase 2: Fleet report executed once; pass rate documented.
5. Registry + traceability updated; no code-only drift.
