---
status: implemented
date: 2026-09-23
related: CR-074, CR-093, CR-125
---

# CR-126: Cited spans stay whole

## Decision sought

Stop a finished resume or cover letter from contradicting the career file when the author was handed a cut-off fact, or when the draft changes the unit, the actor, or a process note.

## Problem

Eight packets ended at `saving $8,500 p`. The author wrote "annually," "monthly," or a bare `$8,500`. The metric check only compares digits, so every one of those passed. Confidential's funnel card stopped at the landing-page sentence. The letter then said Jason created the funnel. Truth review accepted the sentences because the claim id was real. The queue hiring-manager pass quoted a line and marked the pair read.

Lumira scored 25 against a floor of 40 and still passed. The empty-required waiver treats "no qualification-shaped line" as a pass. A classified required line can still be evidence 0.

A denial the linter allows, "Direct customer discovery did not happen," was pasted into Core Competencies to satisfy a term check. "Confidential is" was used as the company name because that string was the posting's company field.

## Product outcome

If shortening an excerpt would separate a number from its unit, or drop an engineering-built clause, that claim is omitted. The evidence map loses the id. The packet records `constraint_omissions`. The rest of the packet can still be authored.

The linter blocks a drafted currency figure whose unit does not match the career spans, a percent those spans do not contain, a line that takes an object the spans assign to engineering, a process note in Core Competencies, and "Confidential is" in the letter. `$8,500 quarterly` and `$22,100 annually` still pass when the spans say so.

The fit-score waiver for an empty required extract stays for logistics-only extracts. It does not stay when a classified required row is explicitly evidence 0 and the score is under 40.

A queue row that reaches Backlog has passed the mechanical gates. It is not safe to send until someone reads it against work experience. This change does not add a model judge and does not add a phrase list for the last bad sentence.

## Out of scope

Re-authoring the finished pairs. Stopping the queue's hiring-manager stamp. Binding every noun around a true percent ("25% of platform usage"). Raising the global excerpt cap.

## Requirements and acceptance

| Requirement | Acceptance |
| --- | --- |
| `FR-383` Omit a card that would drop a unit or an engineering-built clause | `AC-493` The $8,500 cut and the funnel cut omit the claim. A full "per quarter" card stays |
| `FR-384` The draft must match the span's unit, percent, and actor. Notes and placeholder names block | `AC-494` The six bad shapes fail. The two true units and the engineering credit pass |
| `FR-385` Evidence 0 on a required row skips under the floor. Logistics-only still passes | `AC-495` Score 25 with one evidence-0 row is Skip. Score 0 with none is Tier 2 PASS |

## Evaluation

Replay the fixture sentences. Then read one omitted packet and one intact packet against the career file. A later pair that fails the same kind of read becomes a fixture before any new phrase rule.
