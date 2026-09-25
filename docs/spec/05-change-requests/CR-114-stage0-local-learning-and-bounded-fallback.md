---
status: approved
date: 2026-09-17
related: CR-108, CR-112, FEAT-002
---

# CR-114: Stage 0 local learning and bounded fallback

## Decision

Improve Stage 0 only. The production decision path must remain fail-closed while local extraction and evidence matching are measured. A subscription harness may replace the two Groq/Gemini uncertainty paths only after the actual extraction and evidence schemas pass a bounded replay. No model answer is a training label without human adjudication.

## Baseline and release evidence

Record a 30-JD corpus with JD-level grouping and line-level extraction labels, evidence judgments, and skip outcomes. Keep a locked holdout by JD/company, never random line split. The adjudicated 30 is deliberately skip-dense: sitting 1 is eight Pass-shaped JDs already marked PASS; sittings 2–3 are 22 class-weighted skip cases. That shape is the right instrument for proving `false_skips = 0` and does not resemble the live pipeline distribution. Do not read it as a representative sample. `years_ceiling` is ~70% of the skip population; it is asserted arithmetically across the full class (`scripts/audit_years_ceiling.py`), not by stuffing the 22 with extra years rows. Baseline extraction misses, abstentions, evidence errors, false skips, Review Center prompts, provider calls, wall time, and known/unknown cost. Existing score floors stay unchanged. A release candidate must show zero unreviewed false skips on the adjudicated sample, no silent loss of uncertain lines, and completion or explicit resumable review within the chosen finite call/time budget. The numeric budget and error thresholds are to be set from that baseline, not the report's estimates.

## Stories

1. [ ] Quarantine legacy fallback feedback. Stop direct fallback-to-training writes. Only an explicitly reviewed dataset with provenance may be used for retraining. Split held-out JDs before augmentation; save candidate models separately and require a candidate-hash-bound, human-reviewed 30-JD replay report for promotion. Implemented locally; independent QA and full-suite verification remain before checking this story.
2. [ ] Build a Stage 0-only subscription adapter. Default tool is native Agy print+schema+sandbox. Claudexor remains a non-default harness path. Independent QA remains. Production switch off.
3. [ ] Connect ambiguous extraction batches to the adapter. Preserve every unresolved line and existing CR-112 review behavior. Measure calls and failures without changing confident NLP routing. Extraction call site exists locally behind the off switch (2026-09-17); independent QA remains. Confident NLP routing is unchanged.
4. [ ] Build a deterministic evidence matcher in shadow, using reviewed aliases/cases and an abstain state. It cannot emit terminal HARD or Skip from unreviewed evidence. Shadow matcher exists locally (2026-09-17); independent QA remains. Not wired into production scoring.
5. [ ] Connect uncertain evidence batches to the adapter only after the matcher and harness pass replay. Preserve the existing hard-gate safeguards and checkpoint/resume contract. Call site wired behind the off switch (2026-09-17): cascade uses the adapter only when `APPLYR_STAGE0_SUBSCRIPTION_ADAPTER` is on, still holds unsafe HARD, and pauses on timeout/invalid output. Default hosted-tool chain is unchanged. Independent QA remains. Production switch off until replay.
6. [ ] Surface the basis, source excerpt, uncertainty, and correction action for useful Stage 0 decisions in Review Center. Reject generic traits such as critical thinking as named-skill cards. Named-tool filter landed in `6941020`. Requirement, excerpt, `decision_basis`, and `uncertainty` are now stored and rendered. Independent QA remains.
7. [ ] Inventory all Stage 0 hosted call sites, run 5-10 JD schema smoke and a timed 30-JD replay, set budgets from evidence, and only then enable the replacement path. Record rollback and telemetry. Stages 1-3 are out of scope. Hosted-call inventory written. Native Agy 1-item synthetics plus an 8-JD archived schema smoke ran 2026-09-17 (switch unset, no SQLite writes, no silent line loss). Timeouts and a 20-minute wall ceiling fail-closed; numeric production caps are not set. Sitting 1 (8 Pass JDs) is marked. The remaining 22 are class-weighted skip cases, harvested locally without Agy. `years_ceiling` arithmetic is a full-class machine assertion, not extra hand-marks. The final 30 is skip-dense on purpose and is not a representative pipeline sample. Adjudicated 30-JD gold (`training_data_approved.csv`) still absent. Production switch off.
8. [ ] Leftover `junk` bucket is chrome only, visible on the fit gate, never a culture hook. Checkable qualifications with no duty verb (shipped X, track record, working knowledge) go to required, not responsibilities. Personality / 'you are a person who' lines go to culture, never scored. Stage 0 evidence retrieval includes `data/aiProjects.md` for AI/agent/LLM leftover lines so a starved WE window cannot score a genuine AI gap as 0. Keep-in-mind visa/onsite/travel is a later separate lane. Independent QA remains. Production switch off.

## Implementation gate

Jason authorized autonomous planning and implementation on 2026-09-17. That authorizes reversible code and test work, not a claim that the production release gate has passed. The subscription switch remains disabled until the corpus, schema smoke, and replay pass. Factory is unavailable; Claude's broad Metis audit timed out, Agy completed a narrow audit, and Cursor is not routable. Keep harness implementation packets short and capped; Codex integrates and verifies.

## First candidate measurement (2026-09-17)

`python scripts/retrain_stage0.py` trained only from 3,627 base rows, zero human-reviewed additions. A deterministic 48-company, 721-line holdout produced 71.7% accuracy (macro F1 70.1%). At the current 0.65 confidence threshold, coverage was 32.5%. The live model scored 82.5% and 58.4% coverage on the same slice, but its training lineage may include these examples, so this is not an unbiased live-model comparison. No candidate was promoted. The holdout is useful diagnostic evidence, not the required adjudicated 30-JD release corpus.
