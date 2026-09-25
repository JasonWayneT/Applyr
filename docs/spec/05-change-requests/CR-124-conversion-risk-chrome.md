---
status: implemented
date: 2026-09-22
implementation_plan: ../08-implementation/CR-124-conversion-risk-chrome-epics.md
related: CR-109, CR-121, CR-122
---

# CR-124: Conversion-risk chrome is not a product gap

**Superseded in part (CR-125, 2026-09-23):** a missing required product stays in the reason list and is not claimed. It does not withhold the job. Chrome is still not a product gap.

## Decision sought

Keep CR-121 withhold for a required product Jason does not have. Stop withholding when Stage 0's noun is the employer, a chopped section header, or a methodology.

Decision brief: `docs/spec/08-implementation/DECISION-2026-09-22-conversion-risk-after-cr122.md`. Option E. Delta Lake is identity, same class as Dynamics, and stays `risk`.

## Problem

CR-122 stopped the Review Center quiz. CR-121 still parks a Stage 0 PASS when a required line looks like an unknown named tool. Live 2026-09-22 that phrase included:

- Businessolver, the employer, inside a data-handling sentence
- "And Experience", a chopped "Background And Experience/Expertise" header
- OKRs, a methodology
- Delta Lake, a real product on a data PM posting

The first three are parser chrome. Delta Lake is the velosio-shaped gap. They were sitting in the same `conversion_risk` list.

## Product outcome

`conversion_feasibility` stays the withhold. `decision` stays PASS. No Skip. No skip-ledger write. `apply_anyway` stays the only promote.

Chrome does not enter `not_present_named_tools` and does not produce a `risk` reason:

- This posting's employer name (exact normalized match, legal suffixes stripped)
- A section-header fragment (`And Experience`, and any Title-Case run that contains experience / expertise / qualifications / responsibilities / requirements / background / skills)
- Methodology tokens already in the stopword class, plus OKR / OKRs / MVP
- Business-model labels (B2B, B2C, B2B2C, SaaS) and industry compounds ending in Tech (EdTech, FinTech). A parked hold whose stored reasons are only this chrome continues without `apply_anyway` and without another Stage 0 extract.

Still `risk` when a required line is evidence 0 and names a real product the extractor still sees: Microsoft Dynamics 365, Dynamics 365 (the `-ics` ending does not make it a field name), Workspace ONE, Delta Lake.

Preferred unknown tools stay CR-122: no pause, no withhold.

## Out of scope

- Raising skip floor 40
- Skipping `conversion_risk`
- `apply_anyway` on live Employers or Businessolver
- Rebuilding parked-below-70 folders
- Turning on `APPLYR_STAGE2_AGY_RUBRIC` (AC-464)
- A closed product gazetteer (option C)
- Retracting FR-355 (option D)
- Filling Review Center skill cards

## Requirements and acceptance

| Requirement | Acceptance |
| --- | --- |
| `FR-367` Chrome is not a required product | `AC-477` Employer-shaped, "And Experience"-shaped, and OKRs-shaped required evidence 0 stay `ok`, including when an older extract listed them in `not_present_named_tools`. Those surfaces are not named-skill candidates. |
| `FR-368` Product names stay in the reason list. CR-125 removed the withhold | `AC-478` Dynamics-shaped and Delta Lake-shaped names can remain as reasons. The verdict stays `ok`. The draft does not claim them. |

## Release

Tests in `scripts/test_build_stage0_fit_gate.py` and `scripts/test_stage0_confirmations.py`. Existing Stage 0 gates on disk are not rewritten. A later Stage 0 run is what applies the new rule to a live slug.
