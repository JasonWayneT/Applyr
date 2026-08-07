# CR-074 Token Baseline (Epic 1.1)

**Date:** 2026-08-06  
**Method:** file bytes ÷ 4 (rough token estimate; good enough for order-of-magnitude)  
**Implements:** `NFR-007` measurement baseline

## What Stage 0–2 agents are told to load today

From `.claude/skills/generate-submission/SKILL.md` + `CLAUDE.md` / `AGENTS.md`:

| File | Role in process | Bytes | Est. tokens |
|------|-----------------|------:|------------:|
| `data/agent_context_pack.md` | Primary drafting digest (intended one-file load) | 156,600 | 39,150 |
| `.claude/skills/generate-submission/SKILL.md` | Stage 0–3 process | 62,927 | 15,731 |
| `CLAUDE.md` / `AGENTS.md` | Full rules (often also loaded; byte-identical pair) | 44,332 each | 11,083 each |
| `data/workExperience.md` | Ground truth stories | 46,476 | 11,619 |
| `data/master_claims.json` | Full claims (legacy; tags-only preferred) | 45,261 | 11,315 |
| `data/master_claims_tags_only.json` | Preferred claim index | 21,504 | 5,376 |
| `data/conversion_rubric.md` | Stage 2 rubric scoring | 10,929 | 2,732 |
| `data/aiProjects.md` | ACC-401 detail when AI fluency needed | 23,239 | 5,809 |
| `.claude/skills/submission-no-ai-slop/SKILL.md` | Stage 2 point 7 | 5,143 | 1,285 |
| `.claude/skills/conversion-ready-pass/SKILL.md` | Separate review skill (sometimes stacked) | 11,758 | 2,939 |
| `data/candidate_preferences.json` | Stage 0 prefs | 2,603 | 650 |
| `data/Cover_Letter_Reference.md` | Letter structure reference | 2,708 | 677 |
| `data/skills_catalog.json` | Tools vocabulary | 343 | 85 |
| Per-company `Original_JD.txt` + drafts | Variable | ~2–8 KB | ~0.5–2k |

**Sum if an agent naively loads “everything useful” once:** ~**120k** est. tokens of fixed corpus (before JD/drafts/tools).

## Realistic per-company cloud loads (today)

| Pass | Typical required inputs | Est. input tokens | Notes |
|------|-------------------------|------------------:|-------|
| Stage 0 (cloud agent) | Skill + prefs + workExperience/claims + JD | ~40–70k | Often also context pack |
| Stage 1 author | Context pack **or** CLAUDE+WE+claims + skill + Stage 0 JSON + JD | ~50–80k | Pack alone is ~39k |
| Stage 2 independent review | Fresh session: JD + drafts + stage0 + rubric + pack/skill | ~50–70k | **Second full reload** by design |
| Optional no-ai-slop / conversion-ready | Extra skill loads | +3–15k | Stacked on verify |

**Conservative “one company, author + independent review”:** ~**100–150k** cloud input tokens.  
**5-company batch with fan-out:** easily **0.5–1M+** input tokens before counting output or fix loops — matches observed session-limit burns.

## Target after CR-074 (Approach A)

| Pass | Inputs | Target est. input tokens |
|------|--------|-------------------------:|
| Stage 0 | Scripts only | **0** cloud |
| Packet build | Scripts only | **0** cloud |
| Stage 1 author | Packet (≤8k) + rule digest (≤2k) + short system prompt | **~5–12k** |
| Stage 2 default | Scripts only | **0** cloud |
| Optional send-batch review | Lean docs only | As needed |

**Success bar for Epic 7:** ≥**5×** reduction in estimated cloud input tokens per company vs the Stage1+Stage2 row above (~100k → ≤20k), with mechanical verify still clean.

## Files already reusable (not rebuilt)

- `score_claim_for_jd` / `jd_tailoring.py` / deterministic JD profile helpers  
- `verify_submission.py`, coverage, `jd_term_extractor.py`, linter  
- `stage0_fit_gate.json` field shape (live example: `data/submissions/camunda/stage0_fit_gate.json`)  
- `finalize_submission_job.py`, `compile_single.py`  
- CR-062 `local_rewrite` (optional later)
