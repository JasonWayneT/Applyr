# CR-114 / CR-118 QA record

Independent QA walk of acceptance criteria. Story checkboxes in the CR docs are left unchecked for Jason.

Replay artifact: `data/stage0_locked30_replay.json` (gitignored). Deterministic reason table: `data/stage0_cr118_replay.md`. Checkpoint: `7e464003b5317dae4187c2523c656f7a573bdaa2`. Production switch unset. Live `data/stage0_classifier.pkl` unchanged.

## CR-114

| AC | Verdict | Evidence |
|---|---|---|
| **AC-425** Reviewed-only learning; no unverified feedback; company holdout; candidate only | **Met** | `scripts/test_retrain_stage0.py` (`test_fallback_response_does_not_create_training_feedback`, `test_unreviewed_legacy_feedback_is_not_read_or_promoted`, `test_reviewed_rows_require_human_provenance`, `test_reviewed_rows_reject_claude_review_as_reviewer`, `test_company_split_has_no_group_overlap`, `test_promotion_report_binds_candidate_and_replay_gate`, `test_reviewed_junk_rows_are_accepted`). `scripts/test_export_stage0_adjudication.py` (`test_claude_review_source_cannot_export_even_when_marked`, `test_claude_opus_jason_approved_can_export`, `test_promote_claude_review_only_rewrites_filled_marks`). Gold export 375 rows. Candidate written to `data/stage0_classifier.candidate.pkl`; live hash `77b317467a6018a17e47b28fe3bda59a6901015945fc75d0f770dd04bc775913`. |
| **AC-426** Actual schemas; exhausted/invalid/unavailable never silent-bucket; budgets and subscription minutes separate from API cents | **Met, with a gap** | Adapter unit: `scripts/test_stage0_subscription_adapter.py` (`test_disabled_by_default`, `test_timeout_goes_to_review`, `test_partial_mapping_preserves_missing_ids`, `test_malformed_json_goes_to_review`, `test_call_ceiling_exhausted`, `test_agy_denied_tools_go_to_review`). Locked-30 replay: extraction `ok` on 30/30; evidence `ok` 1, `review` 28 (`harness omitted item_ids`), `skipped` 1 (`unity`, no items). `silent_losses=0` because omitted IDs fail closed to review, not `ok`. Budgets from the run: per-JD wall 120s, per-JD calls 6, batch wall 869s, batch calls 77. `api_cents` null. Switch unset. Gap: evidence session returned empty item maps after the first JD, so the evidence replacement path is not yet a working default. |
| **AC-427** Locked 30: no unreviewed false skips; uncertain items preserved in review; coverage/error/calls recorded | **Met** | Replay `false_skips=0`, `silent_losses=0`, 13 PASS/PASS and 17 SKIP/SKIP against jason marks. Shadow matcher: `scripts/test_stage0_evidence_matcher.py`. Review Center columns: `tests/unit/reviewCenterRepository.test.ts`, `tests/unit/reviewCenterRoute.test.ts`, migration `024_add_review_decision_basis.sql`. The 30 is skip-dense on purpose. |

## CR-118

| AC | Verdict | Evidence |
|---|---|---|
| **AC-435** Exact company match; blank matches nothing; Unity still blocks | **Met** | `scripts/test_cr118_gate_false_skips.py` (`test_remote_does_not_match_remotehunter`, `test_blank_company_does_not_match`, `test_exact_unity_still_blocks`). `scripts/test_blocked_companies.py`. Replay row `unity`: jason SKIP, gate SKIP, `blocked_company`. |
| **AC-436** People-gate negation; network_page flag; CivicPlus years pass | **Met** | `test_smartlight_not_a_people_management_role`, `test_eso_coaching_other_managers_reports`, `test_network_page_does_not_skip_prefs`, `test_role_with_direct_reports_still_skips`. Replay: `smartlight_analytics`, `eso`, `yara_ai` PASS; `civicplus` PASS. `yara_ai` flag `network_page` in `data/stage0_cr118_replay.md`. |
| **AC-437** Preferred lead-in; inline is-required; replay records outcome and reason; Claude marks rewrite | **Met** | `test_also_great_to_have_is_preferred_header`, `test_is_required_overrides_preferred_header`. Export rewrite: `test_promote_claude_review_only_rewrites_filled_marks`; sitting-1 leftover 80 and sitting-1 evidence 10 rewritten to `claude_opus_jason_approved`. Outcome+reason table: `data/stage0_cr118_replay.md` section "30-JD replay (outcome + reason)". Reason mismatches `ss_c_technologies` and `aegon` are backlog, not this AC fail. Story 7 JSON records outcome (`false_skips=0`); reason agreement lives in that markdown table. |

## Not scored here

CR-115 / CR-116 / CR-117 years ACs have tests (`TestCR115ScoredChrome`, `scripts/test_evidence_context.py::RetrievalCoverageTests`, `scripts/test_seniority_years_gate.py`, `scripts/test_audit_years_ceiling.py`) and are in the checkpoint. They are not CR-114/118 ACs.

Story boxes in `docs/spec/05-change-requests/CR-114-*.md` and `CR-118-*.md` are left for Jason.
