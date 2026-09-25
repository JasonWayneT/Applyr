---
status: in-progress
date: 2026-09-21
change_request: ../05-change-requests/CR-121-unsupervised-conversion-feasibility.md
---

# CR-121 execution tracker

IDs: CR-121, `FR-353`–`FR-356`, `AC-460`–`AC-464`.

Work one unchecked story at a time. Do not raise `skip_floor`. Do not Skip `conversion_risk`. Do not wire `eval_submission.py`. Do not rebuild parked floor folders.

## Epic 1: Operator LLM path (`FR-353`, `AC-460`)

1. [x] **1.1 Canonical docs.** AGENTS.md, README queue/CR-108 paragraph, ACTIVE_WORKFLOW, PRODUCT_CAPABILITIES, constitution, CHANGELOG, FIXQUEUE: Agy is Stage 0/1. Groq/Gemini API keys are free-tier and do not serve production. That is expected, not a blocker.

## Epic 2: Feasibility band (`FR-354`, `AC-461`)

2. [x] **2.1 Write `conversion_feasibility` on the Stage 0 gate.** Helper after classify + `not_present_named_tools`. `risk` on required `NOT_PRESENT` tools or required named-tool evidence 0 (`looks_like_named_tool`, single-token hits skipped unless they match a NOT_PRESENT name). Distinctive WE overlap was killed by live replay (all five parks already have required PM evidence 3–4). Hire-site chrome and empty-required washout do not use this band. Tests: Dynamics-required → risk; UEM-required → risk; Kafka-required with evidence → ok; Optum hire-site-only → not this band. Deliverable: field on `stage0_fit_gate.json`, `decision` still PASS.

3. [x] **2.2 Replay parked gates without rebuilding drafts.** Live 2026-09-21 helper replay: velosio `risk` (Dynamics); omnissa `risk` (Android / Workspace ONE UEM); certara/outschool/goodrx `ok`. No domain gazetteer this pass.

## Epic 3: Withhold authoring (`FR-355`, `AC-462`)

4. [x] **3.1 Queue `paused_reason=conversion_risk`.** After Stage 0 PASS + `risk`, do not call `run_stage1_prompt`. Stage 0 receipt COMPLETE. Workflow WAITING_FOR_INPUT. Skip ledger untouched. Tests: risk folder is not authored; apply_anyway then prompt.

5. [x] **3.2 `requeue --reason apply_anyway`.** Only that reason promotes a conversion_risk pause. Other requeue reasons refuse. Marker `conversion_risk_apply_anyway.json`.

## Epic 4: Agy scorecard (`FR-356`, `AC-463`)

6. [x] **4.1 `run_stage2_rubric.py`.** Sandboxed no-tools Agy, CR-112 row, manifest copy. Second session for independent-blind in band. Disagree-low binds. Tests with fixture JSON (no live Agy): parse, hash bind, low-on-disagree, refuse `call_llm`.

7. [x] **4.2 Worker in-lease hook.** Behind `APPLYR_STAGE2_AGY_RUBRIC=1` (default off). After Mech needs a scorecard, one rubric call, then `--resume`. Missing docs or existing current-hash scorecard does not call. Failed call stays paused.

## Epic 5: Frozen calibration (`AC-464`)

8. [ ] **5.1 Offline Agy pass on parked Resume.md files.** velosio, certara, omnissa, outschool, goodrx. Fail if any below-70 honest resume scores ≥ 70. Record totals. Production hook stays off until this passes.

9. [ ] **5.2 Release review.** Product: withhold vs Skip still correct. Security: scorecard has no extra WE dump. QA: stories 2–4 tests plus one live size-1 risk pause. EM: scope vs out-of-scope.
