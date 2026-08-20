# Active Workflow (Source of Truth)

**Status:** Active · **Replaces:** `.agent/workflows/*`, `.agent/Instructions.md` for WebApp operations  
**See also:** [README.md](../README.md) (setup), [AGENTS.md](../AGENTS.md) (SDD changes)

---

## 1. Operator workflow (WebApp)

| Step | Action | Output |
|------|--------|--------|
| 1 | **Settings** — keys, profile, experience | SQLite settings; `data/workExperience.md` |
| 2 | **Job Search** — criteria + **Run Scout** | `data/candidate_preferences.json` |
| 3 | Scout pipeline (automatic) | New rows in `jobagent.sqlite`; activity logs |
| 4 | Review **Sync / Opportunities** | Scores, gate rejects, backlog |
| 5 | Optional **Evaluate** (paste JD) | SSE stages → submission folder |
| 6 | **Edit** assets → save | Verify + PDF recompile |
| 7 | **Status** transitions | `data/submissions/` or `data/archive/submissions/` |
| 7b | **Stage 0 triage** | Incoming JDs: `data/pending_review/`. Skip: `data/archive/skipped/` + `stage0_skips` ledger. PASS: `data/submissions/`. |

### Scout pipeline (code order)

1. **Scout** — `server/scout.ts` → `scripts/scout_local.ts` (API + browser sources)
2. **Backfill** — missing detail URLs
3. **Scrape** — full JD text
4. **Review export** — gate-passed jobs with JD text → `data/pending_review/` (`server/services/exportPendingReview.ts`). No LLM fit-scoring runs here; that happens per-JD at Stage 0 via `scripts/run_submission.py` (see "Fit threshold" above). `batch_pipeline.py` is now a DB/JD helper library only, not a live evaluate/draft step.

**LinkedIn:** Decommissioned (CR-010). Logs show `LinkedIn: Bypassed`. Do not re-enable without a new CR.

### Fit threshold

- Pass/skip floor = `data/fit_rubric_calibration.json` → **`score_bands.skip_floor: 40`** / **`tier1_floor: 65`** (CR-093 Story 3.3, locked 2026-08-20). Research-grounded working floor, not yet calibrated against Applyr interview outcomes.
- Engine: `scripts/evidence_scale.py`, wired into `scripts/build_stage0_fit_gate.py` Step 5.5. Spec: `data/fit_rubric_spec.html`.
- `candidate_preferences.json`'s `min_fit_score` (was default 72) and `.agent/rules/job_fit_engine.md` (archived) no longer exist / apply — do not resurrect either.

### Data sources of truth

| Asset | Path |
|-------|------|
| Experience | `data/workExperience.md` |
| Fit summary | `data/workExperience_summary.md` |
| Search prefs | `data/candidate_preferences.json` |
| Jobs DB | `data/jobagent.sqlite` |
| Submissions | `data/submissions/`, `data/archive/submissions/` |
| Stage 0 inbox / skips | `data/pending_review/`, `data/archive/skipped/`, `stage0_skips` in `jobagent.sqlite` |

---

## 2. Pipeline developer workflow

Before editing `batch_pipeline.py`, gates, or draft compiler:

1. Read `.agent/rules/pipeline_env.md`
2. Call `init_pipeline_prefs()` at script entry (see `scripts/utils.py`)
3. Prefer **deterministic gates** before LLM (`industry_gate`, title blocklist, keyword/anchor gates)
4. Draft verification: **`scripts/verification_chain.py`** (not `claim_verifier.md` prose alone)
5. Spawn Python only via **`server/pipeline/processRunner.ts`**

### Verification (run before push)

```bash
npm ci   # uses repo .npmrc (legacy-peer-deps for Toast UI + React 19)
npm test # runs the unified runner executing all python and vitest suites
npm run build
```

### Resume ship gate (CR-042)

Real employer submissions should use **`SUBMISSION_MODE=1`**, which enables the strict bundle (`STRICT_METRICS`, `STRICT_COVER_AUDIT`, `STRICT_ANTI_CLAIMS`, **`STRICT_CONVERSION_CRITIQUE`**, compose-only drafts).

| Check | Where | Pass condition |
|-------|--------|----------------|
| Conversion critique | `submissions/<co>/draft_manifest.json` → `conversion_critique.pass` | `true` before apply |
| Cover audit | same manifest → `cover_letter_audit.grade` | `Pass` when `STRICT_COVER_AUDIT=1` |
| Rubric (advisory) | `rubric_score.overall` | Review if `< 60` or `threshold_flag` |

If critique fails after auto-retry (CR-042 Phase 1B), read `conversion_critique.retry_log` and fix root cause (catalog gap, JD/theme mismatch) — **regen**; do not hand-edit around guards.

Fleet health (CR-042 Phase 2B): `python scripts/fleet_conversion_report.py`

Cover voice (CR-043): deterministic phrasing in `scripts/cover_phrasing.py`; spec `docs/spec/03-feature-specs/cover_voice.example.md`; target 300–400 words.

---

## 3. Spec-driven change workflow (agents)

**Reading order:** `AGENTS.md` → constitution → registry → relevant `FEAT-*` → traceability → **this file**.

**Material changes:** `CR-*` → registry → FEAT → traceability → code (cite `FR-*`) → verification → `CHANGELOG.md` + `PRODUCT_CAPABILITIES.md`.

**Do not use for active work:** `.agent/archive/**`, `docs/history/JobAgent_WebApp_PRD 5.0.md` (archived UX), chat `/scout` / `/evaluate` workflows.

**Change-request index:** [docs/spec/05-change-requests/README.md](spec/05-change-requests/README.md)
