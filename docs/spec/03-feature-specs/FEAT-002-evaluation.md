# Feature Spec: FEAT-002 Evaluation & Gating

## Metadata

- Feature ID: `FEAT-002`
- Status: implemented
- Source artifacts: `BMAD-SRC-005`
- Related requirements: `FR-006`, `FR-007`, `FR-008`, `FR-009`, `FR-035`, `FR-039`, `FR-109`, `FR-170`, `FR-171`, `FR-172`, `FR-188`, `FR-189`, `FR-190`, `FR-191`, `FR-192`, `FR-242`, `FR-243`, `FR-246`, `FR-247`, `FR-278`–`FR-285`, `NFR-009`–`NFR-012`, `DATA-002`–`DATA-004`
- Related change requests: `CR-027`, `CR-028`, `CR-035`, `CR-036`, `CR-037`, `CR-038`, `CR-039`, `CR-053`, `CR-054`, `CR-108`

## Problem statement

Most job postings are poor fits. Sending every lead to an LLM for full analysis is expensive and slow. We need a tiered gating system to kill obvious bad fits instantly, and a background sync to automatically handle this pipeline.

## Goals

- `GOAL-001`: Filter out Lead, Director, and VP-tier titles without calling an AI API; allow Senior when years fit (CR-019).
- `GOAL-002`: Use LLM reasoning only for high-probability candidates.
- `GOAL-003`: Enforce a "Two-Anchor" rule to ensure technical alignment.
- `GOAL-004`: Fully automate the end-to-end sync, scraping, evaluation, and asset generation in the background.
- `GOAL-005`: Dynamic evaluation parameters parsed from user-editable JSON configurations.

## Requirements covered

| Requirement ID | Summary | Notes |
|---|---|---|
| `FR-006` | Zero-Token Gate | Uses `TITLE_BLOCKLIST` |
| `FR-007` | 100-point Score | LLM evaluation |
| `FR-008` | Two-Anchor Rule | Mandatory overlap check |
| `FR-035` | Background Sync Pipeline | End-to-end automation of scraping, evaluation, and asset creation |
| `FR-039` | Dynamic Gating | Reads blocklists and experience targets dynamically from JSON |
| `FR-170` | Industry blocklist gate | `industry_gate.py` in zero-token path (`CR-027`) |
| `FR-171` | Must-have / signal keywords | `passes_keyword_gate()` (`CR-028`) |
| `FR-172` | Two-anchor optional gate | `ANCHOR_GATE_ENABLED` (`CR-028`) |
| `FR-190` | Required domain experience gate | superseded by FR-192 (CR-039) — informational gaps only |
| `FR-191` | B2C role openness | `open_to_b2c` preference + fit prompt (`CR-038`) |
| `FR-192` | Transferable skills scoring | No domain zero-token gate; fit prompt (`CR-039`) |
| `FR-188` | Fit scoring hardening | Location lock, anchor hits as risk flags only (score promotion retired — `FR-242` / CR-053) |
| `FR-189` | Solo PM trap + years policy lock | `solo_pm_gate.py`, `fit_policy.py` (`CR-036`) |
| `FR-242` | Structured evidence-tiered fit | `structured_fit.py` default path; LLM judgments only (`CR-053`) |
| `FR-243` | Extended location zero-token gate | `zero_shot_classifier.py` non-SD onsite/hybrid, Canada, EST/CST-only remote (`CR-053`) |
| `FR-246` | Audit convergence transparency | Failed post-draft audit → `passed: false` (`CR-054`) |
| `FR-247` | Blocked companies gate | `passes_jd_keyword_gate` company blocklist (`CR-054`) |
| `FR-278` | Deterministic evidence cascade | Zero-cost evidence index before model escalation (`CR-108`, rollout-flagged) |
| `FR-279` | Configurable Stage 0 evidence providers | Groq -> Gemini default, explicit Local option, task/model settings (`CR-108`, rollout-flagged) |
| `FR-280` | Batched ambiguous evidence judgment | One structured request per opportunity with strict item validation (`CR-108`, rollout-flagged) |
| `FR-281` | Asymmetric HARD safety policy | Low-confidence or ungrounded HARD cannot disqualify (`CR-108`, rollout-flagged) |
| `FR-282` | Durable Stage 0 checkpoint and resume | Per-item persistence, crash recovery, and per-opportunity pause (`CR-108`, rollout-flagged) |
| `FR-283` | Durable skill confirmation memory | Deduplicated user decisions for unknown tools and skills (`CR-108`, rollout-flagged) |
| `FR-284` | Attestation versus authoring evidence boundary | User confirmation cannot create unsupported resume claims (`CR-108`, implemented) |
| `FR-285` | Review / Questions workflow | Standalone UI and harness adapter share one confirmation resolver (`CR-108`, rollout-flagged) |

## Acceptance criteria

| AC ID | Requirement ID | Given | When | Then |
|---|---|---|---|---|
| `AC-006` | `FR-006` | Job title is "Lead PM" | Evaluator runs | Job is rejected with score 0 |
| `AC-006b` | `FR-109` | Job title is "Senior PM" with 3-6 years in JD | Title gate runs | Job passes title gate |
| `AC-008` | `FR-008` | Score is 80 but 0 anchors hit | Evaluator runs | Decision is NO |
| `AC-035` | `FR-035` | Jobs added as New | Background pipeline triggers | Descriptions are scraped, fit is evaluated, assets are drafted, and SQLite status is updated to Backlog |
| `AC-040` | `FR-039` | Dynamic Routing | User changes candidate preferences | Evaluation run | System dynamically adjusts title blocklists and scoring anchors |
| `AC-358` | `FR-278` | Requirement has a high-precision verified match | Stage 0 evidence cascade runs | The item is resolved without a provider call and without emitting HARD |
| `AC-359` | `FR-279` | Stage 0 evidence task is configured | Stage 0 runs | The configured provider/model policy is used; Local is never an implicit fallback |
| `AC-360` | `FR-280` | An opportunity has multiple unresolved lines | Evidence classification runs | One structured batch request covers those lines and every response item maps to one stable item ID |
| `AC-361` | `FR-281` | Model returns low-confidence or ungrounded HARD | Postprocessing runs | The opportunity is not disqualified; the result is escalated or held for review |
| `AC-362` | `FR-282` | A Stage 0 process stops after persisted judgments | The opportunity resumes | Completed work is reused and only missing work is executed |
| `AC-363` | `FR-283` | A named tool is absent from verified ground truth | Stage 0 evaluates the opportunity | One durable grouped confirmation is created and only that opportunity pauses |
| `AC-364` | `FR-284` | User answers Yes without verified evidence details | Stage 1 packet is built | The attestation cannot create an authorable claim |
| `AC-365` | `FR-285` | User answers in the UI or harness | Confirmation resolver runs | Both surfaces update the same durable decision and the opportunity can resume |
| `AC-366` | `FR-281` | A proposed HARD requires user review | User selects a hard-gate action | `KEEP_ELIGIBLE`, `CONFIRM_HARD`, and `NEEDS_MORE_INFO` produce their documented state transitions |

## Verification plan

| Test ID | Requirement/AC IDs | Test type | Expected result | Status |
|---|---|---|---|---|
| `TEST-002` | `FR-006` | unit | `evaluate_job_fit` returns score 0 for blocklisted words | verified |
| `TEST-108A` | `FR-278`–`FR-281`, `AC-358`–`AC-361` | unit/integration | Cascade, response validation, and asymmetric HARD policy preserve the CR-093 gate/source bar | verified offline; release gate pending |
| `TEST-108B` | `FR-282`–`FR-285`, `AC-362`–`AC-366` | integration/UI | Checkpoint resume, grouped confirmations, hard-gate actions, UI/harness resolution, and attestation boundary pass | verified offline; live UI/release gate pending |
