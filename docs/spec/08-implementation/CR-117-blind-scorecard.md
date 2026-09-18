---
status: draft_pre_registered
date: 2026-09-18
change_request: ../05-change-requests/CR-117-stage1-evidence-first-authoring.md
---

# CR-117 blind authoring scorecard

## Scope and lock

Apply this card to one resume and cover-letter pair at a time. The five CR-112 fictional JDs are the pilot set; the three CR-117 fictional JDs are a holdout. Freeze this card before any candidate holdout draft is viewed. The current path and candidate use the same packet, digest, model capability tier, document contract, and allowed repair rounds. Label pairs with random opaque IDs; reviewers must not see the arm, prompts, plan, model transcript, or token usage until their judgments are submitted. Preserve the first draft before editorial or repair, and score first and final pairs separately.

## Independent reviewer card

Two reviewers read the JD and the blinded pair independently. They can inspect the source-backed packet only for truth and evidence-use judgments; they cannot use arm-identifying metadata. Each records:

| Field | Allowed values / instruction |
| --- | --- |
| `readiness` | `SEND`, `ONE_PASS`, or `REWORK`. `SEND` means no substantive edit before application; `ONE_PASS` means a bounded edit Jason could make in one sitting; `REWORK` means the argument, evidence selection, truth, or voice needs a new draft. |
| `readiness_reason` | Cite exact sentences or missing JD needs, without quoting candidate PII into a tracked report. |
| `truth` | `CLEAR`, `MINOR_AMBIGUITY`, or `BLOCK`. `BLOCK` includes invented metrics, false employer attribution, prohibited work, unsupported tool/domain/management claims, or a claim that cannot be backed by packet evidence. Identify claim IDs and affected units in the private review artifact. |
| `evidence_selection` | `STRONG`, `ADEQUATE`, or `MISSED_HIGH_VALUE`. Name the strongest packet evidence that the pair underused or omitted, including soft-gap bridges. Do not reward sheer claim count. |
| `resume_fit` | `STRONG`, `ADEQUATE`, or `WEAK`. Judge top-third positioning, relevant accomplishments, metric framing, honest seniority, and one-page readability. |
| `letter_argument` | `DISTINCT`, `PARTLY_REPEATED`, or `RESUME_RECAP`. Judge whether the letter adds role-specific logic rather than paraphrasing bullets or the JD. Fictional companies have no external research; do not penalize absence of invented company news. |
| `voice` | `NATURAL`, `NEEDS_EDIT`, or `GENERIC_AI`. Note robotic transitions, inflated language, repetition, or phrasing unlike Jason. |
| `repair_effort` | Estimated meaningful edit actions: `0`, `1-2`, `3-5`, or `6+`. Count substantive changes, not spellcheck. |
| `critical_example` | One concrete sentence/bullet that drove the judgment and why. |

After individual reviews, show paired outputs under randomized A/B labels in separate order for each reviewer. Record `A`, `B`, or `TIE` for (1) resume, (2) cover letter, and (3) complete pair, with a reason. A tie is permitted; do not force a winner. Reveal arm labels only after both cards and preferences are saved. Resolve disagreements in a separate adjudication record without overwriting individual judgments. Jason's `SEND` / `ONE_PASS` / `REWORK` judgment and pair preference are the product decision inputs, but truth blocks cannot be voted away.

## Mechanical companion checks

Run existing Stage 1 and Stage 2 checks on both arms, with the same versions and configuration. Record exact validator names, versions/commit, and outcomes for structural validity, provenance completeness, evidence utilization, ATS term coverage, repeated phrasing, specificity, and PDF page count where PDFs are produced. The conversion rubric's 70/65 thresholds are floors, not a proxy for readiness or a reason to omit stronger grounded evidence. Do not count a mechanical PASS as a qualitative review.

## Operational record

For each arm, case, attempt, and draft stage, record: frozen case hashes; model and transport; session ID (local-only); prompt/packet version; Agy result status; nonempty contract-output check; input, output, and cache-read token deltas when reported; token-estimate method when not reported; number of turns and restarts; allowance/context-limit signal; elapsed time; editor/repair actions; subscription minutes if measured; and paid API cents separately. Include failed and incomplete runs. Never sum subscription minutes and API cents or interpret cached tokens as free context. Store raw drafts, private review cards, and transcripts only under gitignored `data/eval/cr117/`.

## Decision rule

The candidate is not promoted for a higher mechanical score alone. It must show a meaningful improvement in first-draft readiness or blind pair preference, with no increase in serious truth or attribution errors. Final-pair quality and repair burden determine whether the extra authoring stages pay off. If reviewers split, report the split and inspect the underlying examples rather than averaging labels into a false winner. A poor holdout result sends the candidate back for revision; it does not trigger automatic relaxation of the truth bar or a weaker model cascade.
