# Stage 0 new-flow ready plan

> For the next engineer: do these tasks in order. Do not promote the leftover model and do not turn `APPLYR_STAGE0_SUBSCRIPTION_ADAPTER` on until Task 3 passes. Jason marks story boxes.

**Goal:** Make the new Stage 0 path usable on a small real batch, so later batches can improve labels and skip quality.

**What "ready" means:** Uncertain leftover lines and evidence scores go to native Agy and come back with every item id, or park in Review Center for a real reason (timeout, bad JSON, budget). Skip vs pass on the locked 30 stays at zero false skips. The live leftover file `data/stage0_classifier.pkl` stays unchanged until a later promote.

**What "ready" does not mean:** Full scout firehose. Promoting the leftover candidate. Shipping in-office / Aegon / ss_c skip-reason work. Those stay in `docs/spec/08-implementation/stage0-backlog.md`.

**Architecture:** Two knobs. Knob A is the Agy adapter behind `APPLYR_STAGE0_SUBSCRIPTION_ADAPTER`. Knob B is the leftover classifier pkl. Flip A first, keep B on the live 4-class model. Production still fail-closes to review. Real batches become an improvement loop only after Agy returns ids.

**Already true (do not redo):**
- Locked 30 skip/pass: 0 false skips, 0 silent line losses as coded (`data/stage0_locked30_replay.json`).
- Years low-end, exact company match, people-gate negation, `network_page` flag, preferred "also great to have" are in the checkpoint `7e46400`.
- Leftover gold: 375 rows in `data/training_data_approved.csv`. Candidate pkl exists and is unused in production.
- Extraction through Agy on the locked 30: 30/30 `ok`.
- Evidence through Agy on that same run: 1 `ok`, 28 `review` with omitted ids, 1 skipped (`unity` had no evidence items). Harvest of the 5 PASS JDs in chunks of 3 did return levels.

**The blocker:** One long Agy evidence session. First JD returned items. The next 28 came back empty and failed closed. That is not a gold loop. Files: `scripts/replay_stage0_locked30.py` (one `AgySession("evidence")` for all 30), `scripts/stage0_subscription_adapter.py` (`AgySession.classify`), `scripts/smoke_stage0_agy_archive.py` (`_run_task` chunk size 6).

---

## Task 1: Make evidence calls survive past the first JD

**Files:**
- Modify: `scripts/replay_stage0_locked30.py` (evidence loop around line 239)
- Modify: `scripts/stage0_subscription_adapter.py` only if the session itself is the bug (stdin after a result event)
- Test: `scripts/test_stage0_subscription_adapter.py` (session reuse / omitted ids go to review, not ok)
- Prove: `python scripts/replay_stage0_locked30.py --candidate data/stage0_classifier.candidate.pkl` with switch unset

**Do this:**
1. Reproduce on 3 PASS JDs (`eso`, `smartlight_analytics`, `remote`) using the same evidence session. Confirm JD 2+ omit ids.
2. Change the evidence loop to open a fresh `AgySession("evidence")` per JD, or reset the session when `missing_item_ids` is non-empty. Prefer per-JD first. Keep extraction as one session if it stays 30/30 ok.
3. Keep evidence chunks at 3 items (the harvest size that worked), not 6.
4. Do not set `APPLYR_STAGE0_SUBSCRIPTION_ADAPTER`. Do not overwrite `data/stage0_classifier.pkl`.
5. Re-run the locked 30. Pass bar: evidence `ok` or `cache_hit` on every JD that sent items. Omitted ids only allowed when outcome is `review` for timeout / invalid JSON / budget, not empty maps after a live session. False skips still 0. Silent losses still 0.

**Done when:** `data/stage0_locked30_replay.json` shows evidence omitted-id rate near 0, and a short note in this file or the QA record lists the counts.

**Task 1 result (2026-09-18):** Per-JD evidence session plus chunk size 3 plus one retry on omitted ids. Probe of eso / SmartLight / Remote: 2 ok, Remote 3/4 then retry. Full locked 30: extraction 30/30 `ok`. Evidence 29 `ok`, 1 `skipped` (`unity`, no items). JDs with missing ids: 0. False skips 0. Silent losses 0. Elapsed 1228.8s. Live pkl unchanged. Switch unset.

## Task 2: Jason marks the 5-PASS evidence sheet

**Input:** `data/stage0_adjudication_5pass_evidence.csv` (31 rows, `your_mark` blank). Also `data/stage0_adjudication_5pass_evidence.md`.

**Do this:**
1. Jason fills `0`–`4` or `drop`. Suggested drops: `smartlight_analytics:pref:6`–`pref:8` (company bio). Suggested 0: `civicplus:req:14` (mentor other PMs).
2. Do not export these rows into leftover `training_data_approved.csv`. They are scoring gold, not leftover labels.
3. After marks land, a later CR can compare Agy levels to Jason marks. That is quality signal, not a promote gate.

**Done when:** every row has a non-blank `your_mark`.

**Task 2 result (2026-09-18):** Jason marked all 31 rows. 27 scored, 4 dropped. Exact Agy match on 16/27. Comparison of true gaps vs false zeros is in the 2026-09-18 session, not a re-harvest. Do not run `scripts/_harvest_pass5_evidence.py` against this CSV. It overwrites `your_mark`.

## Task 3: Tiny live batch, switch on, leftover pkl unchanged

**Blocked until** the CSV drop-folder / queued-pack / harness-resume / pipeline-UI work in `SESSION-HANDOFF-2026-09-18-csv-drop-queue.md` is done. Jason (2026-09-18): build that, then run this batch. Do not import the four Downloads `applyr_jobs*.csv` files as a 30-at-once one-shot while that CR is open.

**Do this:**
1. Pick 5–10 real pending or archive-PASS JDs. Not a full scout run.
2. Set `APPLYR_STAGE0_SUBSCRIPTION_ADAPTER=1` only for that process. Leave the live leftover pkl in place.
3. Confirm `api_cents` stays null. Timeouts and omitted ids go to Review Center, never to a silent skip.
4. Jason reads: skip vs pass, Review Center pauses, one qualitative evidence card per JD if any scored.
5. Turn the switch off if anything silent-skips or drops lines.

**Done when:** the small batch finishes, Jason has a written pass/fail on "this path is usable for the next real batch," and the live pkl hash is still `77b317467a6018a17e47b28fe3bda59a6901015945fc75d0f770dd04bc775913`.

## Task 4: Only then, leftover promote (optional, later)

**Do not start this in the same sitting as Task 3.**

The candidate still labels `csi:e12` as preferred. Holdout accuracy is 0.69. Junk has no holdout support. Promote is a separate yes/no after Task 3 is boringly clean.

## Out of scope (backlog, not this plan)

- In-office / hybrid skip rule
- `ss_c_technologies` and `aegon` right-skip-wrong-reason
- Reason-accuracy scoring
- Stage 1 evidence-first authoring (CR-120)
- Checking the 38 years-flip postings (Jason's read, not an engineer task)

---

**Hard limits (same as CR-114 close-out):** do not push; do not edit `data/candidate_preferences.json` directly; do not write gold Jason has not approved; do not copy the candidate pkl over the live pkl until Task 4 is an explicit yes.
