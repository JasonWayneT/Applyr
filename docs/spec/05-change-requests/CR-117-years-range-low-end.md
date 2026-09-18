---
status: in_progress
date: 2026-09-17
related: CR-019, CR-055, CR-110, CR-114, FR-109
---

# CR-117: Years range gates on the low end

## Problem

`_hit_from_match` took `max(nums)` on a range, so "3-7 years" parsed as 7. Combined with the 2026-09-03 `>=` boundary (`experience_range.max=7`), every range ending in 7 skipped as over-senior. ActBlue sitting 1 is marked PASS and the gate skipped it on "5-7". `iconsultera`, `mckesson`, `the_cool_company`, and `verra_mobility` are 3-7 mid-level postings. 23 of 31 inferred audit rows were ranges with a low end under 7.

The years audit compared the gate to its own parse, so it could not see this. Tests encoded "4-6 → 6" and "8-12 → 12" instead of guarding the floor.

Word-number and loose hits also treated "eighteen years of age" and company tenure ("fourteen years", "with over 20 years") as experience floors (`the_home_depot`, `gridium`, `system_soft_technologies_llc`).

## Decision

A range gates on its low end, the minimum the posting will accept. 3-7, 4-7, 5-7, 5-8, and 6-10 pass. 7-10 and 8-12 still skip. A single stated figure is unchanged: "7+ years" still skips.

Age, company history, and tenure are not years-of-experience hits, including word-number and loose full-JD matches.

The years audit flags a winning figure that came from a range top, an age, or company history. It does not bless self-consistent arithmetic.

## Out of scope

- Changing `experience_range.max` or the `>=` comparison for a single stated figure
- Skip-marking sittings 2–3
- Interpretive skip codes (0-to-1, solo, people, AI/ML, title)

## Acceptance

- **AC-430:** Range 3-7 parses as 3 and passes; 7-10 parses as 7 and skips; "must be eighteen years of age" is not a hit
- **AC-431:** Remaining archived years skips have no range-top, age, or company-history winning figure
