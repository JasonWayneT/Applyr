---
status: implemented
date: 2026-09-24
related: CR-127, FR-386, FR-390
---

# CR-130: Cited sentence must match the fact

## Decision sought

Block a sentence that cites a real fact and says something that fact does not say. A high conversion score does not clear the block.

## Problem

Obie's letter cited ACC-155 and said profile portability was prioritized over custom tagging. ACC-155 says custom tagging took priority. Provenance passed because the fact id exists. The conversion rubric can still score that sentence highly for being specific.

## Product outcome

Stage 1 verify and Stage 2 block the sentence when the cited id is one of the known contradiction pairs and the sentence matches that pair's phrase. The same words cited to a different fact do not block. A folder with no provenance file does not block on this rule.

## Out of scope

A general entailment model. Partner-team wording. The codename Visible. Raising the fit floor. Raising the conversion-rubric point total.

## Requirements and acceptance

| Requirement | Acceptance |
| --- | --- |
| `FR-390` A cited contradiction is a hard block. A different fact id, or no provenance, is not | `AC-500` The ACC-155 inversion and the ACC-115 "active usage" line block. ACC-104 on the inversion does not. The true custom-tagging sentence cited to ACC-155 does not |
