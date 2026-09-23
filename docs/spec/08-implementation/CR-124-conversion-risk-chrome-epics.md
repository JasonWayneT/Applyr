---
status: implemented
date: 2026-09-22
change_request: ../05-change-requests/CR-124-conversion-risk-chrome.md
---

# CR-124 execution tracker

Superseded in part by CR-125 (2026-09-23): the product-name withhold in `FR-368` no longer parks the job.

IDs: CR-124, `FR-367`, `FR-368`, `AC-477`, `AC-478`.

Work one unchecked story at a time. Do not raise `skip_floor`. Do not Skip `conversion_risk`. Do not `apply_anyway` live parks. Delta Lake stays `risk`.

## Epic 1: Chrome vs product (`FR-367`, `FR-368`, `AC-477`, `AC-478`)

1. [x] **1.1 Extractor and conversion ignore chrome.** `looks_like_named_tool` drops header fragments and OKR/MVP. `named_skill_candidates` drops the posting employer. `evaluate_conversion_feasibility` ignores chrome and the employer even if `not_present_named_tools` still lists them. Dynamics, including short "Dynamics 365", and Delta Lake stay `risk`. Tests: Businessolver-shaped `ok`, And Experience / OKRs `ok`, Delta Lake `risk`, Dynamics `risk`.

## Epic 2: Docs

2. [x] **2.1** Decision brief marked decided (E). CR-121 notes the narrowing. AGENTS.md, README, CHANGELOG, registry, traceability.

## Note

2026-09-22: `TestConversionFeasibility` plus the new extractor test and the adjacent CR-109 extractor tests passed in this session (16 tests). Independent QA and security agents were not run. Did not requeue Employers or Businessolver. Did not run the worker. Existing `stage0_fit_gate.json` files are unchanged until a later Stage 0.

Pre-existing, not this CR: `test_methodology_fields_and_category_acronyms_are_not_tools` already failed on HEAD. `named_skill_candidates` drops `Microsoft Dynamics 365` because it is hard-blocked. Conversion still sees that surface through `looks_like_named_tool`.
