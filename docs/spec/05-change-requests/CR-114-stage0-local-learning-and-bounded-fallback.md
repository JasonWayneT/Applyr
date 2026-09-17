---
status: approved
date: 2026-09-17
related: CR-108, CR-112, FEAT-002
---

# CR-114: Stage 0 local learning and bounded fallback

## Decision

Improve Stage 0 only. The production decision path must remain fail-closed while local extraction and evidence matching are measured. A subscription harness may replace the two Groq/Gemini uncertainty paths only after the actual extraction and evidence schemas pass a bounded replay. No model answer is a training label without human adjudication.

## Baseline and release evidence

Record a representative, redacted 30-JD corpus with JD-level grouping and line-level extraction labels, evidence judgments, and skip outcomes. Keep a locked holdout by JD/company, never random line split. Baseline extraction misses, abstentions, evidence errors, false skips, Review Center prompts, provider calls, wall time, and known/unknown cost. Existing score floors stay unchanged. A release candidate must show zero unreviewed false skips on the adjudicated sample, no silent loss of uncertain lines, and completion or explicit resumable review within the chosen finite call/time budget. The numeric budget and error thresholds are to be set from that baseline, not the report's estimates.

## Stories

1. [ ] Quarantine legacy fallback feedback. Stop direct fallback-to-training writes. Only an explicitly reviewed dataset with provenance may be used for retraining. Split held-out JDs before augmentation; save candidate models separately and require a candidate-hash-bound, human-reviewed 30-JD replay report for promotion. Implemented locally; independent QA and full-suite verification remain before checking this story.
2. [ ] Build a Stage 0-only subscription adapter pinned to tested claudexor. Set explicit profile, timeout, call ceiling, schema validation, redaction policy, and cache identity. No metered API fallback. Exhaustion or invalid output yields review.
3. [ ] Connect ambiguous extraction batches to the adapter. Preserve every unresolved line and existing CR-112 review behavior. Measure calls and failures without changing confident NLP routing.
4. [ ] Build a deterministic evidence matcher in shadow, using reviewed aliases/cases and an abstain state. It cannot emit terminal HARD or Skip from unreviewed evidence.
5. [ ] Connect uncertain evidence batches to the adapter only after the matcher and harness pass replay. Preserve the existing hard-gate safeguards and checkpoint/resume contract.
6. [ ] Surface the basis, source excerpt, uncertainty, and correction action for useful Stage 0 decisions in Review Center. Reject generic traits such as critical thinking as named-skill cards.
7. [ ] Inventory all Stage 0 hosted call sites, run 5-10 JD schema smoke and a timed 30-JD replay, set budgets from evidence, and only then enable the replacement path. Record rollback and telemetry. Stages 1-3 are out of scope.

## Implementation gate

Jason authorized autonomous planning and implementation on 2026-09-17. That authorizes reversible code and test work, not a claim that the production release gate has passed. The subscription switch remains disabled until the corpus, schema smoke, and replay pass. Factory is unavailable; Claude's broad Metis audit timed out, Agy completed a narrow audit, and Cursor is not routable. Keep harness implementation packets short and capped; Codex integrates and verifies.

## First candidate measurement (2026-09-17)

`python scripts/retrain_stage0.py` trained only from 3,627 base rows, zero human-reviewed additions. A deterministic 48-company, 721-line holdout produced 71.7% accuracy (macro F1 70.1%). At the current 0.65 confidence threshold, coverage was 32.5%. The live model scored 82.5% and 58.4% coverage on the same slice, but its training lineage may include these examples, so this is not an unbiased live-model comparison. No candidate was promoted. The holdout is useful diagnostic evidence, not the required adjudicated 30-JD release corpus.
