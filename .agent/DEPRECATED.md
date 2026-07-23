# Deprecated Agent Artifacts

These paths are **not** used by the Applyr WebApp or Express pipeline.

| Former path | Archive location | Use instead |
|-------------|------------------|-------------|
| `Instructions.md` | `archive/Instructions.md` | [docs/ACTIVE_WORKFLOW.md](../docs/ACTIVE_WORKFLOW.md) |
| `workflows/scout.md` | `archive/workflows/scout.md` | README + UI **Run Scout** |
| `workflows/evaluate.md` | `archive/workflows/evaluate.md` | `batch_pipeline.py` + SQLite |
| `skills/scout.md` | `archive/skills/scout.md` | `scripts/scout_local.ts` |
| `rules/pipeline_env.md` | `archive/rules/pipeline_env.md` | `AGENTS.md` -> `.claude/skills/generate-submission/SKILL.md` |
| `rules/job_fit_engine.md` | `archive/rules/job_fit_engine.md` | `AGENTS.md` -> `.claude/skills/generate-submission/SKILL.md` Stage 0 |
| `rules/Research_Packet_Contract.md` | `archive/rules/Research_Packet_Contract.md` | N/A -- no web research, any stage, per standing `SKILL.md` rule |

**Retired 2026-07-23 (CR-070 fallout):** the three rule files above described the pre-direct-authoring pipeline (local-Ollama fit scoring, `compose`-mode drafting, Perplexity research) and were still marked `trigger: always_on` despite being stale since 2026-07-19 -- a real risk that an agent reading `.agent/rules/` at face value would follow retired defaults. Moved to `archive/rules/`, `trigger` changed to `manual`, and each file now carries a "Retired, not active" banner. Kept in full (not deleted) for future study or a more robust rebuild -- see each file's banner for what superseded it.

**Active rules:** none with `trigger: always_on`. `rules/claim_verifier.md` remains in place (already `trigger: manual`, reference-only) — see next line.
**Active verification (code):** `scripts/verification_chain.py` — see `rules/claim_verifier.md` (reference only, not `always_on`).
