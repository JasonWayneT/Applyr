# CR-032 — Documentation & Process Cleanup

**Status:** Implemented  
**Date:** 2026-05-30  
**Requirements:** NFR-MAINT-001, FR-039

## Summary

Usefulness audit implementation: single runtime doc, deprecated chat-era agent artifacts, aligned thresholds and scout sources, verification SoT clarified.

## Changes

| Area | Action |
|------|--------|
| `docs/ACTIVE_WORKFLOW.md` | New operator + pipeline + SDD pointer |
| `.agent/archive/**` | Moved Instructions, scout/evaluate workflows, scout skill |
| `.agent/workflows/*`, `Instructions.md` | Stubs → ACTIVE_WORKFLOW |
| `claim_verifier.md` | `trigger: manual`; points to `verification_chain.py` |
| `job_fit_engine.md` | Document `min_fit_score` default 72 |
| README, constitution, FEAT-001 | LinkedIn decommission; threshold wording |
| `readMinFitScore()` | Server draft-only uses prefs (fixes hardcoded 72) |
| `05-change-requests/README.md` | CR index |
| AGENTS.md / SDD_PROCESS.md | Reading order + links |

## Verification

- `npm ci` / `npm run build`, `npm test` (see repo `.npmrc` for CI peer-deps)
- Python smoke suite unchanged
- No removal of CR history or release notes

## Risks mitigated

| Risk | Mitigation |
|------|------------|
| Agents follow dead workflows | Stubs + DEPRECATED.md + AGENTS reading order |
| Wrong fit threshold | `readMinFitScore()` + doc alignment |
| claim_verifier always_on confusion | Changed to manual reference |
| Lost history | Archive folder, not delete |
