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
| 7 | **Status** transitions | `submissions/` or `archive/submissions/` |

### Scout pipeline (code order)

1. **Scout** — `server/scout.ts` → `scripts/scout_local.ts` (API + browser sources)
2. **Backfill** — missing detail URLs
3. **Scrape** — full JD text
4. **Evaluate & draft** — `scripts/batch_pipeline.py`

**LinkedIn:** Decommissioned (CR-010). Logs show `LinkedIn: Bypassed`. Do not re-enable without a new CR.

### Fit threshold

- Pass threshold = `candidate_preferences.json` → **`min_fit_score`** (default **72**).
- Rubric text for LLM: `.agent/rules/job_fit_engine.md` (loaded by Python).
- Do **not** use legacy **78** from archived WebApp PRD or chat instructions.

### Data sources of truth

| Asset | Path |
|-------|------|
| Experience | `data/workExperience.md` |
| Fit summary | `data/workExperience_summary.md` |
| Search prefs | `data/candidate_preferences.json` |
| Jobs DB | `jobagent.sqlite` |
| Submissions | `submissions/`, `archive/submissions/` |

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
python scripts/test_verify_chain.py
python scripts/test_batch_gate.py
python scripts/test_smoke_regression.py
python scripts/smoke_draft_compiler.py
python scripts/check_spawn_paths.py
npm test
npm run build
```

---

## 3. Spec-driven change workflow (agents)

**Reading order:** `AGENTS.md` → constitution → registry → relevant `FEAT-*` → traceability → **this file**.

**Material changes:** `CR-*` → registry → FEAT → traceability → code (cite `FR-*`) → verification → `PRODUCT_CAPABILITIES_AND_RELEASE_NOTES.md`.

**Do not use for active work:** `.agent/archive/**`, `JobAgent_WebApp_PRD 5.0.md` (archived UX), chat `/scout` / `/evaluate` workflows.

**Change-request index:** [docs/spec/05-change-requests/README.md](spec/05-change-requests/README.md)
