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
| `skills/researcher.md` | `archive/skills/researcher.md` | N/A -- superseded by `generate-submission/SKILL.md`'s own Stage 1 authoring + `research-engine.py`'s targeted calls; not a standalone agent role anymore |
| `skills/writer.md` | `archive/skills/writer.md` | `AGENTS.md` -> `.claude/skills/generate-submission/SKILL.md` (Markdown + `compile_single.py`, not LaTeX) |

**Retired 2026-07-23 (CR-070 fallout):** three rule files (`pipeline_env.md`, `job_fit_engine.md`, and `Research_Packet_Contract.md` -- the last since un-retired, see 2026-08-06 note below) described the pre-direct-authoring pipeline (local-Ollama fit scoring, `compose`-mode drafting, Perplexity research) and were still marked `trigger: always_on` despite being stale since 2026-07-19 -- a real risk that an agent reading `.agent/rules/` at face value would follow retired defaults. Moved to `archive/rules/`, `trigger` changed to `manual`, and each file carried a "Retired, not active" banner. Kept in full (not deleted) for future study or a more robust rebuild -- see each file's banner for what superseded it.

**Retired 2026-08-04:** `skills/researcher.md` and `skills/writer.md` were missed in the 2026-07-23 sweep above -- both sat in the live `.agent/skills/` folder, not archived, despite describing the same retired pre-direct-authoring pipeline (API-based company research; a LaTeX resume/cover-letter/cheat-sheet output writing to `submissions/[company]/`). Found while building Cursor/Antigravity wrapper files for `generate-submission`. Same treatment: moved to `archive/skills/`, `trigger: manual`, "Retired, not active" banner.

**Un-retired 2026-08-06 (`rules/Research_Packet_Contract.md` only, narrowly):** the "no web research, any stage" rule this file's retirement leaned on is no longer absolute -- `generate-submission/SKILL.md` Stage 1 now allows a small, separate cover-letter fact-finder for Tier 1 / `Reach Out` Tier 2 fits (`research-engine.py`'s `fetch_cover_letter_hook_fact()`, not this contract). This six-module packet itself stays scoped to its original purpose only: on-demand interview prep, invoked once a real interview is actually scheduled, never at draft time. Restored to `rules/Research_Packet_Contract.md` (live, `trigger: manual`) with an updated banner reflecting the narrow scope; the pre-2026-08-06 archived copy stays in `archive/rules/` as a historical snapshot, not the active version.

**Active rules:** none with `trigger: always_on`. `rules/claim_verifier.md` remains in place (already `trigger: manual`, reference-only) — see next line.
**Active verification (code):** `scripts/verification_chain.py` — see `rules/claim_verifier.md` (reference only, not `always_on`).
