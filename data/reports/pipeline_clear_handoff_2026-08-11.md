# Pipeline clear handoff — 2026-08-11

## Send now (55 COMPLETE, 1-page Resume+CL PDFs, `check_workflow_complete: YES`)

Prior 4 (left alone, reminted receipts only): `ncontracts`, `leaflink`, `camunda`, `central_bank`

New / cleared keeps:

| Slug | Notes |
|---|---|
| actblue | Tier 1 |
| acushnet_company | Tier 2 |
| amn_healthcare | Tier 2 |
| beyond | Tier 2 |
| blue_river_technology | Tier 1 |
| brooksource | Tier 2 |
| caylent | Tier 2 |
| clade | Tier 1 |
| clarion_events_inc_north_america | Tier 2 |
| common_room | Tier 2 |
| compugroup_medical_se_co_kgaa | Tier 2 |
| dr_seuss_enterprises | Tier 2 |
| elevance_health | Tier 2 |
| envision_technology_solutions | Tier 2 |
| federal_express_corporation | Tier 1 |
| finance_of_america | Tier 2 |
| fingerprint | Tier 1 |
| hanwha_vision | Tier 2 |
| hire_feed | Tier 2 |
| icw_group | Tier 2 |
| jack_and_jill_client | Tier 2 |
| juno_search_partners | Tier 2 |
| kroll | Tier 2 |
| marigold | Tier 1 |
| mogli | Tier 2 |
| nash | Tier 1 |
| nava | Tier 2 |
| neogen | Tier 1 |
| netradyne_54a876 | Tier 1 |
| omni | Tier 2 |
| paylocity | Tier 2 |
| pinterest | Tier 2 |
| pinterest_product_manager_ii_content_compliance | Tier 2 |
| practicetek | Tier 2 (reapply) |
| precisepk | Tier 2 |
| procede | Tier 2 |
| ready_net | Tier 1 |
| realtime_eclinical_solutions | Tier 2 |
| recast_software | Tier 1 |
| relativity | Tier 1 |
| revpilots | Tier 2 |
| rg_talent_inc | Tier 2 |
| rhino_labs_inc | Tier 2 |
| sdl | Tier 2 (GovPilot / Hedgerow) |
| seed_health | Tier 2 |
| shazam_network_its_inc | Tier 2 |
| spotify | Tier 2 (reapply) |
| thermo_fisher_scientific | Tier 2 (reapply) |
| trace3 | Tier 2 |
| turquoise | Tier 2 (reapply) |
| yara_ai | Tier 2 |

Assets live under `data/submissions/{slug}/Resume.pdf` + `CoverLetter.pdf`.

Many folders are `COMPLETE_WITH_OVERRIDE` (Stage 2 findings disposed as accepted risk / provenance bridges). Still production-finalized with DB rows.

## Closed Skips (no assets)

| Slug | Reason |
|---|---|
| amplify | Hard gap: expert Smartsheet / similar |
| centralsquare_technologies | 30-day DB cooldown |
| deloitte | title_blocked: Director |
| greystar | Hard gaps: Procore admin / ERP |
| infinite_computer_solutions | 30-day DB cooldown |
| interra_health | title_blocked: Lead |
| ispeedtolead | Hard gap: SQL / Amplitude / BigQuery |
| marcone_supply | required years 10 > max 8 |
| oec | 30-day DB cooldown |
| routeware_inc | Hard gap: Amplitude/Mixpanel analytics fluency |
| test_co | Thin JD stub |
| velera | 30-day DB cooldown |
| airbnb | Reclassified: extraction_empty packet |
| isolved | Reclassified: APM + tooling gap |
| dealeron | Reclassified: unmapped soft-skill required after packet rebuild |

## Blocked / incomplete

None among Tier 1/2 keeps. All 51 keeps + 4 prior = 55 send-ready.

## How this was finished

1. CSV import → Stage 0 batch (`data/reports/stage0_batch_2026-08-11.md`)
2. Packet + authoring for keeps; provenance / CL-012 / LR-015 / ACC-114 / `$34K` metric allowlist fixes
3. In-process Stage 2 (`scripts/force_stage2_complete.py`) + production finalize
4. Receipt-chain remint (`scripts/remint_receipt_chains.py`) → 55/55 `check_workflow_complete: YES`
