# Stage 0 backlog (post CR-114 / CR-118)

Frozen CR-114/118 work does not pick these up. One line each: what, where, why.

- In-office / another-city hybrid skip rule. `scripts/stage0_prefs_gate.py` has no office-days gate. Eight passing archived JDs state regular in-office days; Aegon skips for other reasons so it is not in that eight.
- Right skip, wrong reason: `ss_c_technologies`. Gate code `exclusion_zone_ai_ml_ownership`. Product is a multi-cloud AI gateway; Jason's skip is 5+ years PM with an AI focus plus build-and-launch.
- Right skip, wrong reason: `aegon`. Gate codes `years_ceiling` and `exclusion_zone_people_management`. Jason's skip is three office days a week in Philadelphia or Denver plus senior signals, not the eight-year digital-experience and/or line.
- Skip-reason accuracy scoring. `data/stage0_cr118_replay.md` records reason agreement for the locked 30. No gate or metric treats a wrong reason as a failure when the skip/pass outcome matches.
- CSI leftover NLP still guesses `preferred` on `csi:e12` ("Financial services, banking, or payments industry experience is required") after the header fix. Deterministic extract routes `is required` under Preferred to required; the live 4-class leftover model does not. Retrain candidate is the check, not a new rule.
- Live leftover classifier has no `junk` class (`culture` / `preferred` / `required` / `responsibilities`). CR-114 Story 8 leftover junk exists in extraction; the candidate may learn junk, the live `data/stage0_classifier.pkl` does not until a later promote.
- `docs/reports/stage0-architecture-research-report.md` is gitignored but was tracked. Untracked 2026-09-17 (`git rm --cached`); file stays on disk.
- Stage 1 evidence-first authoring draft reused `CR-117` / `FR-332`–`FR-336` / `AC-430`–`AC-434`, already owned by years-range CR-117. Rename before any Stage 1 work. Untracked files: `docs/spec/05-change-requests/CR-117-stage1-evidence-first-authoring.md`, `docs/spec/08-implementation/CR-117-stage1-evidence-first-authoring-epics.md`, `docs/spec/08-implementation/CR-117-blind-scorecard.md`, `docs/spec/08-implementation/RESEARCH-2026-09-18-stage1-authoring-shape.md`, `scripts/freeze_cr117_cases.py`.
- Preferred inheritance after `"Who is {Company}:"` about-copy. `scripts/build_stage0_fit_gate.py` `_extract_sections` left SmartLight company-bio sentences in preferred (`smartlight_analytics:pref:6`–`pref:8`). Not a skip/loss bug.
- CSV drop-folder, queued packs, harness lease/resume, pipeline UI. Not backlog: next CR (suggested CR-119). Brief: `SESSION-HANDOFF-2026-09-18-csv-drop-queue.md`. Tiny live batch (PLAN Task 3) waits on it.
