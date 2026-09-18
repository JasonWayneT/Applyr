---
status: in_progress
date: 2026-09-17
related: CR-054, CR-110, CR-114, CR-117, FR-247
---

# CR-118: False skips, skip-reason agreement, and preferred-header harvest

## Problem

Jason marked 22 skip-dense JDs. 17 SKIP, 5 PASS, all `source=jason`. Every one of the 22 was a gate skip, so the five PASS marks were false skips:

1. **remote.** `"Remote"` matched blocked `"RemoteHunter"` because `_check_blocked_company` also tested `company in entry`. The same condition skipped a blank company against every blocked entry (`"" in entry` is True).
2. **smartlight_analytics.** `"This is not a people-management role and carries no direct reports."` hit `_PEOPLE_MGT_REQUIRED_RE` on `"direct reports"` and ignored the negation.
3. **eso.** `"Provide direct support and coaching to all levels of management as they help their direct reports."` The reports belong to other managers. Mentoring and coaching are not managing.
4. **yara_ai.** `network_page` is not a skip in policy. A hidden employer on a real in-band JD is a flag.
5. **civicplus.** Fixed by the CR-117 range low-end change.

Two SKIP marks were the right outcome with the wrong reason: `ss_c_technologies` (AI/ML ownership vs a multi-cloud gateway plus a 5+ years PM/AI line) and `aegon` (eight-year and/or line vs three office days in Philadelphia or Denver plus senior signals). Replay that only records skip vs pass counts those as clean.

Extraction harvest dropped ESO's `"Also great to have:"` heading, so a nice-to-have certification could take the hard_gap path. NLP labeled CSI `e12` `"Financial services, banking, or payments industry experience is required"` as preferred because it sat under a preferred header.

## Decision

Match blocked companies on the whole normalized name. Never match a blank name. Skip people-management only when this role has reports or manages people. Move `network_page` to flags. Treat `"Also great to have"` / `"great to have"` as preferred headers, and route an `"is required"` line under a preferred header to required.

Jason-approved Claude leftover marks export as `source=claude_opus_jason_approved`, not `source=jason`, so they can be filtered later. `source=claude_review` still cannot export until rewritten.

The 30-JD replay records skip-reason agreement, not only skip vs pass. Do not invent an in-office-days gate in this CR; count passing JDs that require regular in-office days first.

Do not overwrite jason skip marks. Re-harvest leftover lines after the header fix and flag inherited-heading changes.

## Out of scope

- Changing the AI/ML ownership regex for `ss_c_technologies`
- Adding an in-office / another-city hybrid gate
- Retraining or promoting the leftover classifier
- Turning `APPLYR_STAGE0_SUBSCRIPTION_ADAPTER` on

## Acceptance

- **AC-435:** `"Remote"` does not match `"RemoteHunter"`. A blank company name matches nothing. Exact `"Unity"` still blocks.
- **AC-436:** SmartLight's negated-reports sentence and ESO's coaching-other-managers sentence do not skip. `network_page` is a flag, not a reject. CivicPlus passes the years gate.
- **AC-437:** `"Also great to have:"` is a preferred header. `"… is required"` under Preferred goes to required. Replay of the 30 records outcome and reason agreement. Filled `claude_review` marks rewrite to `claude_opus_jason_approved`.
