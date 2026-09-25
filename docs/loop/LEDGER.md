# Loop ledger

## HANDOFF

Iteration 29 removes a country list and a geography use of distributed when the posting never asks (FR-418). A line about distributed data systems stays. The warning still fires on the original wording. Holdout 17 does not qualify. It failed Stage 1 on the 10th folder. Queue restore count was 0. Start holdout 18 after this commit, then holdout 19 with no further pipeline change. Definition of done is not met. Do not loosen a gate. Do not stage the parallel edits. Stop if Agy quota actually exhausts.

## Iteration 29 — unasked geography

1. OBSERVE: holdout 17 failed Stage 1 on the 10th folder. The block was LW-039.
2. ROOT CAUSE: CONFIRMED. The posting never asked for geography. One line named a country list. Another called stakeholders distributed.
3. EXPLORE: exempt the wording, or remove it.
4. CHOOSE: remove it. A line about distributed data systems stays. A posting that asks for distributed work keeps the line.
5. IMPLEMENT: `strip_unsolicited_geography` in `scripts/stage1_prerepair.py`.
6. EVALUATE: `python -m unittest scripts.test_stage1_prerepair` passed, 24 tests. A copy of the failed resume no longer trips the check.
7. CONFIRM: holdout 18 has not run. This is not definition of done.

## Iteration 28 — stale hiring-manager read

1. OBSERVE: holdout 16 parked at the hiring-manager pass on the 3rd folder. The open items were the pair warning, three audience warnings, and the hiring-manager read.
2. ROOT CAUSE: CONFIRMED. Those warnings were already accepted. Policy passed. The stored read hashed the previous resume bytes. This pass rewrites the documents, and the finding ids do not change, so the old read stays bound.
3. EXPLORE: accept the stale hash, or rebuild the read from the current files.
4. CHOOSE: rebuild the read. The hash check stays. An open warning other than the read is not closed here. A review that fails for any other reason stays parked.
5. IMPLEMENT: `_refresh_stale_queue_hm_read` in `scripts/workflow/runner.py`.
6. EVALUATE: the three new contract tests passed. A copy of the parked folder rebuilt a read that validates.
7. CONFIRM: holdout 17 has not run. This is not definition of done.

## Iteration 27 — design

1. OBSERVE: holdout 15 parked at the hiring-manager pass on the 3rd folder. The warning was LW-028. The verb was design.
2. ROOT CAUSE: CONFIRMED. The rewrite caught designed and built. It did not catch design.
3. EXPLORE: accept the warning, or reword the verb.
4. CHOOSE: reword the verb. An owned built line stays.
5. IMPLEMENT: the ownership rewrite in `scripts/stage1_prerepair.py` now includes design.
6. EVALUATE: the contributed-claim tests passed. A copy of the parked letter no longer trips the warning.
7. CONFIRM: holdout 16 has not run. This is not definition of done.

## Iteration 26 — leverage

1. OBSERVE: holdout 14 failed Stage 1 at the 3rd folder. The block was LR-009. The token was leverage, inside high-leverage.
2. ROOT CAUSE: CONFIRMED. The hyphen still leaves the banned word. The summary is one sentence, so deleting the sentence would break the three-sentence shape.
3. EXPLORE: allow the compound, or remove it.
4. CHOOSE: remove the compound. Standalone leverage becomes use. data-driven stays.
5. IMPLEMENT: `replace_leverage_buzzwords` in `scripts/stage1_prerepair.py`.
6. EVALUATE: `python -m unittest scripts.test_stage1_prerepair` passed, 21 tests. A copy of the failed summary lost the compound and kept the sentence.
7. CONFIRM: holdout 15 has not run. This is not definition of done.

## Iteration 25 — unverified tool

1. OBSERVE: holdout 13 failed Stage 1 at the 9th folder. One block was LR-026. The token was Python, in the competencies row.
2. ROOT CAUSE: CONFIRMED. That tool is not in the career history. The row also named tools that are allowed.
3. EXPLORE: add the tool to the career history, or remove the token.
4. CHOOSE: remove the token. The other tools stay.
5. IMPLEMENT: `strip_unverified_tools` in `scripts/stage1_prerepair.py`.
6. EVALUATE: `python -m unittest scripts.test_stage1_prerepair` passed, 20 tests. A copy of the failed row lost Python and kept SQL. LR-026 was clear after that.
7. CONFIRM: holdout 14 has not run. This is not definition of done.

## Iteration 24 — knowledge overlap

1. OBSERVE: holdout 12 failed Stage 1 at the 19th folder. The block was unused required evidence. The only shared word was knowledge.
2. ROOT CAUSE: CONFIRMED. That word is not proof the claim belongs on the line.
3. EXPLORE: attach the unused id, or stop treating that one word as proof.
4. CHOOSE: stop treating that one word as proof. A real shared term still requires the cite.
5. IMPLEMENT: knowledge is a generic overlap token in `scripts/build_authoring_packet.py`.
6. EVALUATE: the overlap test and the optimization-bar tests passed. The failed folder's cite check now passes.
7. CONFIRM: holdout 13 has not run. This is not definition of done.

## Iteration 23 — distributed systems

1. OBSERVE: holdout 11 failed Stage 1 at the 11th folder. The block was LW-039. The token was distributed.
2. ROOT CAUSE: CONFIRMED. The line said distributed data systems. The check treats that word as team geography.
3. EXPLORE: delete the line, or stop matching the technical use.
4. CHOOSE: stop matching the technical use. A team distributed across offices still fails.
5. IMPLEMENT: the geography pattern in `scripts/submission_linter.py`.
6. EVALUATE: the two new geography tests passed. The failed resume no longer trips the check. The older rentana file test still cannot find its folder. That miss was already there.
7. CONFIRM: holdout 12 has not run. This is not definition of done.

## Iteration 22 — thin letter

1. OBSERVE: holdout 10 parked at the hiring-manager pass. The warning was LW-001. The body was 172 words.
2. ROOT CAUSE: CONFIRMED. The letter was under the 220-word floor. Eleven cited resume bullets were unused.
3. EXPLORE: lower the floor, or add a cited sentence from the resume.
4. CHOOSE: add a cited sentence. The floor stays 220.
5. IMPLEMENT: `extend_thin_cover` in `scripts/stage1_prerepair.py`, also called at the start of the hiring-manager pass.
6. EVALUATE: `python -m unittest scripts.test_stage1_prerepair` passed, 19 tests. A copy of the parked letter went from 172 words to 244.
7. CONFIRM: holdout 11 has not run. This is not definition of done.

## Iteration 21 — cover length

1. OBSERVE: holdout 9 failed Stage 1. The block was CL-006. The letter was 2976 characters.
2. ROOT CAUSE: CONFIRMED. Three body sentences had no cite. One of them was long enough to bring the letter under the limit.
3. EXPLORE: raise the character limit, or remove an uncited sentence.
4. CHOOSE: remove an uncited sentence. The limit stays 2800.
5. IMPLEMENT: `trim_cover_to_page` in `scripts/stage1_prerepair.py`, after the employer sentence is added.
6. EVALUATE: `python -m unittest scripts.test_stage1_prerepair` passed, 18 tests. A copy of the failed letter went from 2976 to 2750.
7. CONFIRM: holdout 10 has not run. This is not definition of done.

## Iteration 20 — ownership overlap

1. OBSERVE: holdout 8 failed Stage 1. The block was unused required evidence for ACC-111-SCOPE and ACC-101-SCOPE.
2. ROOT CAUSE: CONFIRMED. The only shared word was ownership.
3. EXPLORE: attach the unused id to an existing sentence, or stop treating that one word as proof.
4. CHOOSE: stop treating that one word as proof. A real shared term still requires the cite.
5. IMPLEMENT: ownership is a generic overlap token in `scripts/build_authoring_packet.py`.
6. EVALUATE: the overlap test and the optimization-bar tests passed. The failed folder's cite check now passes.
7. CONFIRM: holdout 9 has not run. This is not definition of done.

## Iteration 19 — cited contradiction

1. OBSERVE: holdout 7 failed Stage 1. The remaining block was LR-049 on ACC-103.
2. ROOT CAUSE: CONFIRMED. The drop looked for hard blocks without the cite file, so a cited contradiction was invisible.
3. EXPLORE: leave the line for another repair pass, or load the cite file and remove the line.
4. CHOOSE: load the cite file and remove the line. A neighboring bullet stays.
5. IMPLEMENT: `drop_blocked_units` in `scripts/stage1_prerepair.py` now loads `claim_provenance.json`.
6. EVALUATE: `python -m unittest scripts.test_stage1_prerepair` passed, 17 tests.
7. CONFIRM: the local check behaves as tested. Holdout 8 has not run. This is not definition of done.

## Iteration 18 — contributed claim

1. OBSERVE: holdout 6 parked at the hiring-manager pass. The warning was LW-028 on ACC-120. The verbs were built and designed.
2. ROOT CAUSE: CONFIRMED. That claim is tagged contributed. The approved wording is contributed to. The hiring-manager pass cannot accept the warning without an edit.
3. EXPLORE: accept the warning, or reword the verbs.
4. CHOOSE: reword the verbs. An owned built line stays.
5. IMPLEMENT: `soften_contributed_ownership` in `scripts/stage1_prerepair.py`, also called at the start of the hiring-manager pass.
6. EVALUATE: `python -m unittest scripts.test_stage1_prerepair` passed, 16 tests.
7. CONFIRM: the local check behaves as tested. Holdout 7 has not run. This is not definition of done.

## Iteration 17 — drop-off story is not an ingestion pipeline

1. OBSERVE: holdout 5 parked at the hiring-manager pass. The block was LR-038. The letter called the 40% drop-off story an ingestion pipeline.
2. ROOT CAUSE: CONFIRMED. That block was not in the Stage 1 fidelity list, so the hiring-manager pass was the first place it could stop the draft, and that pass cannot rewrite it.
3. EXPLORE: drop the sentence, allow the phrase, or rename the phrase and fail Stage 1 on the same check.
4. CHOOSE: rename the phrase to ETL path. The 40% outcome stays. Stage 1 now fails on the same check.
5. IMPLEMENT: `rewrite_bypass_ingestion` in `scripts/stage1_prerepair.py`. `check_bypass_authorship` is in `collect_fidelity_hard_blocks`.
6. EVALUATE: `python -m unittest scripts.test_stage1_prerepair` passed, 15 tests.
7. CONFIRM: the local check behaves as tested. Holdout 6 has not run. This is not definition of done.

## Iteration 16 — unverified partner clause

1. OBSERVE: holdout 4 parked at the hiring-manager pass. The resume said it partnered with operational stakeholders. That group is not a verified team.
2. ROOT CAUSE: CONFIRMED. The warning is a WARN, so Stage 1 did not rewrite the sentence, and the hiring-manager pass cannot accept it without an edit.
3. EXPLORE: add the group to the verified list, accept the warning, or cut the clause.
4. CHOOSE: cut the clause. A verified partner stays.
5. IMPLEMENT: `strip_unverified_partner_clauses` in `scripts/stage1_prerepair.py`, also called at the start of the hiring-manager pass.
6. EVALUATE: `python -m unittest scripts.test_stage1_prerepair` passed, 14 tests.
7. CONFIRM: the local check behaves as tested. Holdout 5 has not run. This is not definition of done.

## Iteration 15 — hiring-manager park

1. OBSERVE: holdout 4 reached a practice-complete folder, then parked the next drafted folder at hiring manager. Mech had not run.
2. ROOT CAUSE: not yet a code change. The warning names a partner group that is not on the verified list.
3. Next change has to delete or rewrite that claim. Accepting the warning without an edit is forbidden.

## Iteration 14 — hedged figure and uncited employer sentence

1. OBSERVE: holdout 3 had one Stage 1 failure and one mechanical park. The park was a 6-digit dollar amount that is the hedged career figure written in precise form. The failure was invalid provenance. The only employer sentence was uncited, and deleting it would leave no past employer.
2. ROOT CAUSE: CONFIRMED for both. The metric check runs after Stage 1, so the precise form parked at Stage 2. The employer drop is refused when it would create that new hard block, so repair ran and its provenance was rejected.
3. EXPLORE: allow the precise number, drop the whole sentence, or rewrite only the hedged form. For the letter, invent a cite, or copy a cited resume sentence and then drop the uncited one.
4. CHOOSE: rewrite only when a hedge word is already in the sentence. Copy one cited resume sentence, then let the existing uncited drop remove the old sentence.
5. IMPLEMENT: `collapse_hedged_100k` and `anchor_uncited_employer` in `scripts/stage1_prerepair.py`. The metric rewrite also runs before Stage 2 verify.
6. EVALUATE: `python -m unittest scripts.test_stage1_prerepair` passed, 13 tests.
7. CONFIRM: the local checks behave as tested. Holdout 4 has not run. This is not definition of done.

## Iteration 13 — non-factual blocked sentence

1. OBSERVE: holdout 2 failed one folder at Stage 1. Live rule LR-009. The repair outcome was no progress. Mechanical fixes applied nothing.
2. ROOT CAUSE: CONFIRMED. The buzzword sat in a cover sentence that states no personal fact. The drop only walked personal-fact sentences.
3. EXPLORE: leave the sentence for repair, or delete every body sentence that is itself a hard block.
4. CHOOSE: delete the body sentence. The refusal when deletion creates a new hard block stays.
5. IMPLEMENT: `_cover_body_sentences` in `scripts/stage1_prerepair.py`.
6. EVALUATE: `python -m unittest scripts.test_stage1_prerepair` passed, 11 tests.
7. CONFIRM: the local check behaves as tested. Holdout 3 has not run. This is not definition of done.

## Iteration 12 — drop a blocked sentence

1. OBSERVE: four Stage 1 failures. Two were the same findings after one repair, so a second repair was refused. The sentences were cited hard blocks.
2. ROOT CAUSE: CONFIRMED. `drop_uncited_units` keeps a cited sentence. Repair cannot clear a sentence that is itself the block, and it must not invent a hedge.
3. EXPLORE: invent the missing hedge, allow the tool, or delete the blocked sentence.
4. CHOOSE: delete the sentence. Refuse the delete when it creates a new hard block. Leave a line whose only blocked-tool hit is the word epic.
5. IMPLEMENT: `drop_blocked_units` in `scripts/stage1_prerepair.py`, called after `drop_uncited_units`.
6. EVALUATE: `python -m unittest scripts.test_stage1_prerepair` passed, 10 tests.
7. CONFIRM: the local checks behave as tested. Holdout 2 has not run. This is not definition of done.

## Holdout 1 — started

No pipeline change. Driver: `docs/loop/evidence/h1/drive_holdout.py`. Practice mode on every orchestrator call, including resume and finalize. Rubric stays off. Cloud LLM stays off. Do not open the holdout folders.

## Iteration 0 — setup

1. OBSERVE: `docs/loop/` was missing. Working tree on main had 990 uncommitted lines in 12 pipeline files.
2. ROOT CAUSE: not a pipeline defect. Prior session left a mixed diff uncommitted.
3. EXPLORE: apply the diff, or revert and record it.
4. CHOOSE: revert. Several hunks add allowlist entries or suppressions. The mission forbids those. The patch stays as evidence.
5. IMPLEMENT: branch `loop/2026-09-23`, STATE/CHECKLIST/LEDGER, no product code.
6. EVALUATE: `git diff --stat` empty for scripts. Eligibility census printed 412.
7. CONFIRM: branch point is `6c68377`. Prior WIP is not in the tree.
8. Not a failed fix. No revert of product code.

## Iteration 0 — F0 feasibility, stopped

1. OBSERVE: `1uphealth` Stage 0 COMPLETE via Agy. Author wrote files. First resume parked at HM with BLOCK LR-045 and LR-047. Evidence: `docs/loop/evidence/00-f0/`.
2. ROOT CAUSE: CONFIRMED. Those hard blocks run in `lint_folder` after Stage 1 is COMPLETE. `needs_stage1_repair` requires status FAILED, so nothing rewrites the draft.
3. EXPLORE: leave the park, dispose the blocks, or fail Stage 1 on the same checks. Disposing is forbidden.
4. CHOOSE: fail Stage 1 on `collect_fidelity_hard_blocks`. Then a second confirmed cause: `drop_uncited_units` deleted the repaired employer sentence. Refuse a drop that creates a new hard block.
5. IMPLEMENT: commits `702d2e6` and `330115b`. Tests named in the evidence file.
6. EVALUATE: re-verify failed LR-045 and LR-047. After the guard, resume kept the Cision sentence and failed provenance. Repair 3 removed the sentence. Resume failed LR-045 again.
7. CONFIRM: the local checks behave as tested. The live draft does not. Stage 3 was not reached.
8. Stop. Same defect after two fixes. Do not run another repair on this folder.

## Iteration 0 — F1 evaluator

1. OBSERVE: pipeline gates are not the judge. The before-fix bak files still contain the sentences in `docs/loop/evidence/f1/gold.json`.
2. ROOT CAUSE: not a pipeline fix. This step only measures. A model judge was not called. The check is deterministic against the cited id and a small phrase list.
3. EXPLORE: call a second model per sentence, or score locally from the findings' contradiction patterns. A per-sentence model call would spend the remaining Agy budget before any holdout run.
4. CHOOSE: local checks in `scripts/loop_eval.py`. No pipeline edit.
5. IMPLEMENT: evaluator, gold quotes, `scripts/validate_loop_eval.py`, `scripts/test_loop_eval.py`.
6. EVALUATE: `python scripts/validate_loop_eval.py` printed recall 0.939 and false-positive rate 0.028. Unit tests passed.
7. CONFIRM: both bars hold. Two classlink Sterkly bullets stay unflagged on purpose. Evidence: `docs/loop/evidence/f1/validation.txt`.
8. Not a failed fix. No pipeline revert.

## Iteration 0 — F2 split

1. OBSERVE: DEV and HOLDOUT were empty. Eligible folders are now 426, up from 412 on 2026-09-23.
2. ROOT CAUSE: not a defect. The split had not been frozen.
3. EXPLORE: a pure shuffle of all 426, or hold the already-read slugs in DEV.
4. CHOOSE: seed 20260923, holdout 60 from the unread pool. `1uphealth` and the before-fix review slugs that still exist as archive folders stay in DEV. Seven review names are not archive folders.
5. IMPLEMENT: slugs in STATE.json. Draw check in `scripts/check_loop_split.py`. No pipeline edit. No job text opened.
6. EVALUATE: `python scripts/check_loop_split.py` printed MATCH, dev 366, holdout 60.
7. CONFIRM: overlap 0. Evidence: `docs/loop/evidence/f2/split.txt`.
8. Not a failed fix.

## Iteration 1 — hedge line deleted

1. OBSERVE: accertify SKIPPED on fit 36. nisum SKIPPED on a 30-day cooldown. accion_labs and adly were ALREADY_HANDLED. affinity_co reached PRACTICE_COMPLETE. Evidence: `docs/loop/evidence/01-i1/`.
2. ROOT CAUSE: CONFIRMED. The author left a cited drafting-time line without "estimated". Repair added the word and changed the sentence, so provenance no longer matched. `drop_uncited_units` then removed it. That deletion does not create LR-047, so the guard allowed it. The first draft still has the week-and-day line. The finished draft does not.
3. EXPLORE: leave the deletion, or insert "estimated" on the existing line and resync the cite before uncited lines are dropped.
4. CHOOSE: insert the hedge in place. Do nothing leaves a true proof on the cutting-room floor. Another repair call is what broke the cite.
5. IMPLEMENT: `keep_required_hedges` in `scripts/stage1_prerepair.py`, called before uncited lines are dropped. Test `test_missing_estimate_hedge_is_inserted_without_dropping_the_cite` failed, then passed. The other 7 pre-repair tests passed.
6. EVALUATE: unit test, then a live DEV run on ait_global_inc_.
7. CONFIRM: the live verify failed LR-047 on an unhedged $1M to $3M sentence, the mechanical pass inserted estimated, the sentence stayed cited, and the second verify passed with no repair call. Evaluator findings 0. PRACTICE_COMPLETE. The week-and-day arm did not appear in this draft. The unit test covers it. Evidence: `docs/loop/evidence/01-i1/ait_global_inc_-stage3.txt`.
8. Not reverted.

## Iteration 2 — disruption hedge

1. OBSERVE: the before-fix letters say a migration finished without disruption. Work experience says about 5 percent of customers never flipped, and it never uses the word disruption.
2. ROOT CAUSE: CONFIRMED. `submission_linter.py` had no check for that phrase. Stage 1 verify uses `collect_fidelity_hard_blocks`, so the gap was in that list.
3. EXPLORE: do nothing, or hard-block a no-disruption sentence that omits the 5 percent.
4. CHOOSE: hard-block. Do nothing leaves the known-bad sentence able to pass. The block is a tightening.
5. IMPLEMENT: `check_disruption_hedge` as LR-048, called from `collect_fidelity_hard_blocks`. The new test failed, then passed. The linter script's other tests passed. One pre-existing error remains: the rentana geography test looks for a submission folder that is not in this checkout.
6. EVALUATE: the check flags 5 sentences on the before-fix copies, one each in obie_2, classlink, nisum, securitize, and very_good_security. Those are the five no-disruption lines from the review. No extra hit in that folder.
7. CONFIRM: a bare "without service disruption" sentence is now a hard block. A sentence that keeps "5 percent" is not. A plain rollout sentence is not.
8. Not reverted.

## Iteration 3 — cited contradiction

1. OBSERVE: an uncommitted check was already in the tree. A sentence can cite a real fact id and say something that fact does not say. Provenance only checks that the id exists.
2. ROOT CAUSE: CONFIRMED. Before this check, `collect_fidelity_hard_blocks` did not compare the sentence to the cited id.
3. EXPLORE: do nothing, or hard-block the known pairs when that id is cited.
4. CHOOSE: keep the check, and do not block a funnel sentence that credits engineering with deploying it. That sentence was a false block.
5. IMPLEMENT: LR-049 in `check_cited_contradiction`. Stage 1 verify and Stage 2 both pass the folder provenance. The test passed, including the engineering-credit case.
6. EVALUATE: 102 linter tests, one pre-existing rentana error. On the before-fix copies the check caught 11 gold quotes whose cite matched the pair.
7. CONFIRM: ACC-155 inversion blocks. The same words cited to ACC-104 do not. No provenance does not. The Obie file cites ACC-115 for the portability line, so this rule does not catch that file. Evidence: `docs/loop/evidence/03-i3/cited.txt`.
8. Not reverted.

## Iteration 4 — portability inversion

1. OBSERVE: the Obie letter reverses the tagging priority and cites ACC-115. LR-049 does not fire.
2. ROOT CAUSE: CONFIRMED. The check requires the cite to be ACC-155. The phrase is false on any cite.
3. EXPLORE: do nothing, or hard-block the phrase with no cite requirement.
4. CHOOSE: hard-block the phrase. Do nothing leaves the reversed sentence able to pass.
5. IMPLEMENT: LR-050. The new test failed, then passed. LR-049 still does not fire when the cite is ACC-104.
6. EVALUATE: 103 linter tests, one pre-existing rentana error. On the before-fix copies the phrase fires only on the Obie letter.
7. CONFIRM: the inversion blocks with an ACC-115 cite and with no provenance. The true direction does not. Evidence: `docs/loop/evidence/04-i4/portability.txt`.
8. Not reverted.

## Iteration 5 — QA lead

1. OBSERVE: the Candor resume says he served as first-pass QA lead and cites ACC-204. LR-049 does not fire.
2. ROOT CAUSE: CONFIRMED. The check requires the cite to be ACC-209. He was not a QA lead on any cite.
3. EXPLORE: do nothing, or hard-block the title with no cite requirement.
4. CHOOSE: hard-block the title. Do nothing leaves the claim able to pass.
5. IMPLEMENT: LR-051. The new test failed, then passed.
6. EVALUATE: 104 linter tests, one pre-existing rentana error. On the before-fix copies the phrase fires only on the Candor resume.
7. CONFIRM: the title blocks with an ACC-204 cite and with no provenance. A test-suite sentence without the title does not. Evidence: `docs/loop/evidence/05-i5/qa-lead.txt`.
8. Not reverted.

## Iteration 6 — hundreds of client databases

1. OBSERVE: the Classlink letter says consistency was restored across hundreds of client databases. The cite is ACC-102 and ACC-121.
2. ROOT CAUSE: CONFIRMED. MET-09 is roughly 200 SQL databases. No linter rule blocked the phrase.
3. EXPLORE: do nothing, or hard-block the phrase with no cite requirement.
4. CHOOSE: hard-block the phrase. Do nothing leaves the changed scale able to pass.
5. IMPLEMENT: LR-052. The new test failed, then passed.
6. EVALUATE: 105 linter tests, one pre-existing rentana error. On the before-fix copies the phrase fires only on the Classlink letter.
7. CONFIRM: the phrase blocks with that cite and with no provenance. "Roughly 200 SQL databases" does not. Evidence: `docs/loop/evidence/06-i6/hundreds.txt`.
8. Not reverted.

## Iteration 7 — support escalation reduction

1. OBSERVE: the Classlink letter says the data-remediation work significantly reduced customer support escalations. The cite is ACC-102.
2. ROOT CAUSE: CONFIRMED. Work experience does not use the word escalation. ACC-102 is the 40 percent drop-off. No linter rule blocked the reduction.
3. EXPLORE: do nothing, or hard-block the reduction with no cite requirement.
4. CHOOSE: hard-block the reduction. Do nothing leaves the invented outcome able to pass. The Jira formula that says streamline stays allowed, because that formula is real.
5. IMPLEMENT: LR-053. The new test failed, then passed.
6. EVALUATE: 106 linter tests, one pre-existing rentana error. On the before-fix copies the check fires only on the Classlink letter.
7. CONFIRM: the reduction blocks with an ACC-102 cite and with no provenance. Streamline does not. Stale-data complaints do not. Evidence: `docs/loop/evidence/07-i7/escalations.txt`.
8. Not reverted.

## Iteration 8 — release cadence

1. OBSERVE: the Classlink resume says he guided release cadence and cites ACC-204.
2. ROOT CAUSE: CONFIRMED. Work experience does not use the phrase release cadence. No linter rule blocked it.
3. EXPLORE: do nothing, or hard-block the phrase with no cite requirement.
4. CHOOSE: hard-block the phrase. Do nothing leaves the invented outcome able to pass. A deletion cadence stays allowed.
5. IMPLEMENT: LR-054. The new test failed, then passed.
6. EVALUATE: 107 linter tests, one pre-existing rentana error. On the before-fix copies the phrase fires on the Classlink resume and the Keyfactor letter.
7. CONFIRM: the phrase blocks with an ACC-204 cite and with no provenance. Defect triage does not. A rolling deletion cadence does not. Evidence: `docs/loop/evidence/08-i8/cadence.txt`.
8. Not reverted.

## Iteration 9 — testing analytics

1. OBSERVE: the Classlink resume says the Parallels test work applied testing analytics and cites ACC-214.
2. ROOT CAUSE: CONFIRMED. Work experience does not use that phrase. No linter rule blocked it.
3. EXPLORE: do nothing, or hard-block the phrase with no cite requirement.
4. CHOOSE: hard-block the phrase. Do nothing leaves the invented outcome able to pass. Pendo product analytics stays allowed.
5. IMPLEMENT: LR-055. The new test failed, then passed.
6. EVALUATE: 108 linter tests, one pre-existing rentana error. On the before-fix copies the phrase fires only on the Classlink resume.
7. CONFIRM: the phrase blocks with an ACC-214 cite and with no provenance. A Pendo product-analytics sentence does not. Evidence: `docs/loop/evidence/09-i9/testing-analytics.txt`.
8. Not reverted.

## Iteration 10 — Visible codename

1. OBSERVE: the Obie resume prints Visible in the middle of a sentence.
2. ROOT CAUSE: CONFIRMED. Work experience says never print that name. No linter rule blocked the capitalized form.
3. EXPLORE: do nothing, or hard-block a capitalized Visible after a space.
4. CHOOSE: hard-block that form. Do nothing leaves the codename able to pass. Lowercase visible stays allowed.
5. IMPLEMENT: LR-056. The new test failed, then passed.
6. EVALUATE: 109 linter tests, one pre-existing rentana error. On the before-fix copies the check fires only on the Obie resume. The before-fix gold quotes now each sit in a blocked sentence.
7. CONFIRM: the codename blocks with a cite and with no provenance. Lowercase visible does not. Evidence: `docs/loop/evidence/10-i10/visible.txt`.
8. Not reverted.












