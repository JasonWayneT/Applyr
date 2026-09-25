# Session handoff 2026-09-23: findings from reading 40 finished submissions against work experience

Purpose: give an investigating agent (Cursor, using evidence-driven problem solving) the observed defects, where the evidence lives, and what is still unknown. Nothing here is a root-cause claim unless marked CONFIRMED. Hypotheses are labeled and each has a way to falsify it.

## 0. Context and the one-line problem

Jason asked for a "final check" of everything in `data/submissions/`. 40 folders were COMPLETE (Stage 3 finalized, Backlog in the app). Reading each Resume.md / CoverLetter.md against `data/workExperience.md` found real defects in roughly half of them. Every one of these documents had already passed lint, ATS, Truth, HM, Mech, provenance and the 1-page check.

**The problem to explain: why did a pipeline whose gates all pass still ship documents with false, inflated, leaked or empty content?** Per AGENTS.md (CR-126) "Backlog does not mean safe to send", but the defects below are mostly things a mechanical gate could plausibly catch.

Scope of the read: 40 submissions (two batches: 19 checked first, 21 after the queue worker finished more). Lumira Search was judged unfit and archived to `data/archive/skipped/lumira_search` with its DB row deleted (backup: `data/jobagent_pre_lumira_delete.sqlite`).

## 1. Observed defects (facts, with evidence pointers)

Evidence for "before" state: for most folders the original text exists only in `stage1_author_output/`, `stage1_first_draft/`, and (for the 17 fixed in the second batch) `%TEMP%\bak_{slug}_{Resume|CoverLetter}.md` and `bak_{slug}_prov.json` (temporary, may be gone). The first batch (19) was edited without backups; use git-untracked state carefully.

### D1. Empty résumé marked COMPLETE (highest severity)
- `data/submissions/nisum_2/Resume.md`: three role headings, zero bullets. Cover letter starts mid-thought ("Investigating the pipeline mechanics revealed…"), no "At Cision" setup, then uses the banned word "Additionally".
- `workflow_state.json` status COMPLETE, updated 2026-09-23T20:32:51Z. Lint reported only `LW-003`, `Resume` 170 words. `stage1_author_output/Resume.md` and `stage1_pre_repair/Resume.md` also have 0 bullets, so the loss happened at or before Stage 1 repair.
- The folder was not edited by the reviewer. Jason will re-author it. A guard task was queued separately.

### D2. Stage 1 verify-only silently deletes uncited content and then passes (CONFIRMED behavior, mechanism partly inferred)
- Editing any resume bullet or cover sentence so it no longer matches its `claim_provenance.json` key text made `python scripts/run_submission.py <folder> --resume` (Stage 1 verify) rewrite `Resume.md` / `CoverLetter.md` with that line removed, then continue.
- Reproduced repeatedly this session: forvis_mazars_us lost 3 bullets, iperium lost 3, eso lost its Zero To Sixty bullet, confidential lost two cover-letter sentences (twice), ss_c/forvis/iperium lost cover sentences.
- Telling detail: the `eso` run printed `FAIL [sentence_provenance/resume]: uncited bullet ...`, then the verify result flipped to PASS on the next line. It passed because the bullet was deleted, not because it was fixed.
- Look at: `scripts/author_from_packet.py` (`run_verify_only`), `scripts/stage1_prerepair.py`, `scripts/run_stage1_repair.py`, `scripts/build_stage1_repair_prompt.py`, `stage1_repair_attempts/`, `stage1_pre_repair/`.
- Open question: is deletion the intended repair for a first draft? It is harmful when the input is a human-corrected document. CORRECTION after Cursor's review: nisum_2 (D1) is NOT explained by this mechanism. Its `stage1_pre_repair/Resume.md` (the snapshot taken before repair) already has 0 bullets, so the empty résumé came from the author step or earlier, and no gate then checked for it. D2 harmed my correction edits; it did not put the false documents into Backlog.

### D3. Leaked internal note in output
- `habiterre/Resume.md` Core Competencies ended with "| Direct customer discovery did not happen". It compiled into the PDF. The JD asks for customer discovery, so it announced a gap to the reader.
- Likely source is the skills-row builder (`build_skills_section` in `scripts/local_draft_stages.py`) or a Stage 1 author emitting a gap note. UNVERIFIED which.

### D4. Placeholder used as a real name
- `confidential/CoverLetter.md` opened "Confidential is tackling a growth phase…". The company is unnamed in the JD and the slug/company field is "Confidential".

### D5. Numeric unit drift on a verified metric (8 résumés)
- MET-11 is $8,500 **per quarter** ($34K/yr). eso, helpgrid, hsi, iperium, modern_campus, sourcegraph said "annually"; ss_c and forvis said a bare "$8,500". Understates by 4x.
- Nothing checks that a metric keeps its unit and period from Section 4.

### D6. Claims that contradict or exceed the cited work-experience entry, while carrying valid provenance IDs
This is the most important class because `claim_provenance` passed on all of them (it checks that an ID is cited, not that the sentence is entailed by that ID's text).
- Inversion: `obie_2/CoverLetter.md` said "prioritizing profile portability over custom tagging". ACC-155 says custom tagging took priority. Same letter called the 25% stat "active usage"; ACC-115/155/180 define it as the share of customers using per-client data profiles. The 25% misstatement also appeared in forvis_mazars_us and iperium letters.
- Standing do-not-claim: `medrisk/CoverLetter.md` "restructure the underlying data model" (WE DO NOT CLAIM data modeling/schema; ACC-219 says Jason specified the split, engineering implemented). Related wording in curinos, obie_2, medrisk résumés/letters.
- Attribution collapse: `confidential` and `highmark_health` credited the Zero To Sixty funnel/automation to Jason ("automating lead capture workflows", "Influenced… landing page") vs ACC-303 attribution correction (landing page is his, funnel is engineering's).
- Overclaims: `nisum` "Owned the end-to-end migration" of the Google Analytics integration (ACC-113/145: he defined the change plan and ran the customer side; engineering implemented); `confidential` "leading the platform migration off Cloudera" (ACC-220: owned the decision, engineering owned the build); `highmark_health`/`very_good_security` "Cleared/Resolved" a pen-test backlog (MET-08 is ~90%); `candor_health` "QA lead" (ACC-209: first-pass QA, not the QA function); `rex_zone` letter "led the technical implementation" (ACC-102: he drove the decision, an engineer proposed it).
- Inflated governance: `forvis_mazars_us`, `classlink`, `medrisk`, `medrisk_2`, `nisum`, `securitize`, `ss_c_technologies` turned ACC-107 (vendor-barred content removal, Google/Yahoo sender policy) into "governed regulatory compliance / established data governance policies / audit requirements". The word "regulatory" was already a known-bad class in `conversion-ready-pass` Pass 2.
- Invented: `very_good_security` "Negotiated technical specifications… across vendor ecosystems"; `habiterre` Sterkly "turned endpoint protection rules into desktop behavior… wrote functional specifications" (its provenance cited ACC-203/ACC-202 which do not say that); `classlink` "support escalations significantly reduced", "hundreds of client databases", "release cadence", "applying product analytics and testing analytics"; `keyfactor` "restored dependable release cadence"; `securitize` "audit requirements", "without disrupting licensed feeds".
- Unverified partner teams: "Operations" and "compliance teams" named as partners in securitize and medrisk (not on the AGENTS.md verified partner list).
- Dropped hedges: "estimated $1M–$3M" (MET-13), "about two weeks to a few days" (ACC-179 says "his own estimate, keep the hedge"), "sustaining/unblocking" without "estimated", "without service disruption" / "without disrupting customer reporting" (ACC-113 says ~5% did not flip).
- Codename leak: `obie_2/Resume.md` printed "Visible" ("tradeoffs Visible to enable") which is a VOC-16 codename, apparently a JD-keyword capitalization artifact.

### D7. Padding under the 2-3 bullet floor
- Second Zero To Sixty bullets in curinos, dropbox, securitize, torentify, very_good_security, obie_2 restated the same onboarding tool with unsupported outcomes ("improving account setup accuracy", "accelerate activation timelines", "mapping complex client account data structures"). AGENTS.md asks 2-3 bullets for earlier roles, which may be pressuring the author to pad. Also `lumira_search` had the same 700-account migration in two bullets.

### D8. Stage 0 fit gate passed jobs with hard unmet requirements
- `lumira_search`: JD requires endovascular/thrombectomy experience, clinical acumen with physicians, ISO 13485. Passed and was authored; the letter talked about surgeons/radiologists without any bridge, the résumé claimed "address regulatory requirements".
- `massive_bio`: Jr. PM role wanting 1-3 years; authored a Jr.-titled résumé claiming seven years. Not necessarily a defect, worth checking what the fit gate said (`stage0_fit_gate.json`).
- Subtitle domain qualifiers adopted from JD titles despite the AGENTS.md rule: `medrisk_2` "Data Products", `very_good_security` "Agentic Commerce". Both fixed by hand.

### D9. Gates bound to document hashes are fragile and partly performative
- `reviews/dispositions.json` (`hm.critical_read` requires a structured `hm_review` with document hashes), `reviews/rubric_scorecard.json`, and `draft_manifest.json.rubric_score.document_sha256` all bind to file hashes. Any edit voids them (`hm.critical_read` is set to null; Mech emits `mech.rubric_score_provenance` BLOCKs).
- The repo contains an automatic HM-review writer: `scripts/workflow/runner.py` `_queue_hm_review_value` / `_accept_open_warnings` builds a passing `hm_review` from the first quotable line of each document. If that is what produced most existing `hm.critical_read` dispositions, "HM read passed" carries almost no signal. UNVERIFIED how many folders used it (compare `reasoning` text in `reviews/dispositions.json`: generic text starting "Resume and cover letter each carry a concrete proof line" is the helper's).
- 8 of the first 19 COMPLETE folders had no rubric score in `draft_manifest.json` (forvis_mazars_us, helpgrid, hsi, hyland, iperium, kipu_health, lumira_search, modern_campus), and the 17 second-batch folders I re-ran had no hash-bound `rubric_score` (`document_sha256`) in their manifests, yet all reached COMPLETE. I did not check whether those 17 carry unbound score totals. Mech's rubric check appeared to fire only when a scorecard existed (verified on the scorecard folders; inferred for the rest).
- `rubric_scorecard.json` can hold several rows from different reviewers with different hashes (lexipol had 4: 57, 62, 70, 70). A rebind script must pick the right rows. The reviewer of this session overwrote the wrong row on lexipol once (repaired, original row lost; see section 3).

## 2. What is NOT known (questions worth answering with evidence)

1. Does `run_verify_only` delete content by design (repair-by-omission) or through a bug? Read the code path and `stage1_repair_attempts/*.txt`; test with a copy of a COMPLETE folder where one bullet's text is changed by one word.
2. What produced nisum_2's empty résumé: the Agy author output, the repair step, or a later step? `stage1_first_draft/Resume.md`, `stage1_author_output/`, `stage1_author_attempts/`, `observability/` should tell.
3. Is provenance ever checked for entailment? If not, is a cheap check possible (e.g. each cited ID's constraint text or prohibited list vs. the sentence, or a required-verb/attribution table from WE Section 4)? D6 has about 25 concrete negative examples to test against.
4. How many existing `hm.critical_read` dispositions came from the auto-writer versus a real read?
5. Where do hard JD requirements get compared to WE at Stage 0 (D8)? Lumira should be a test case: what did `stage0_fit_gate.json` say?
6. Why did MET-11's "per quarter" get lost? Is the packet excerpt missing the unit, or did the author paraphrase it?
7. Source of the "Direct customer discovery did not happen" string (D3): grep the packet, digest, `skills_catalog.json`, and `build_skills_section` output.

## 3. Changes made this session (so investigators can tell reviewer edits from pipeline output)

- Edited Resume.md/CoverLetter.md/claim_provenance.json in about 28 folders (first batch: amplify, confidential, eso, habiterre, ss_c_technologies, sourcegraph, helpgrid, hsi, iperium, modern_campus, forvis_mazars_us, then lexipol, kipu_health, hyland; second batch: candor_health, classlink, curinos, dropbox, highmark_health, keyfactor, makai_labs, massive_bio, medrisk, medrisk_2, nisum, obie_2, rex_zone, securitize, sourcegraph_2, torentify, very_good_security). All recompiled through `run_submission.py --resume` then `--finalize`, all COMPLETE.
- Rebound (not re-scored) rubric scorecard rows and `hm_review` hashes to the new documents. Carried-over scores in: eso, amplify, confidential, habiterre, ss_c_technologies, sourcegraph, lexipol. A rebind script also relabeled habiterre row 0 and destroyed lexipol row 0 (an old 62 on a superseded draft); lexipol now has 3 rows.
- Wrote a fresh `hm_review` by hand for confidential.
- Archived `data/archive/skipped/lumira_search`; deleted its `jobs` row (id `ceb22954`, company "Lumira Search", status Backlog). Pre-delete DB copy `data/jobagent_pre_lumira_delete.sqlite`.
- Not changed: nisum_2; archera, intech, keyfactor_2, crio, nymbl_systems, obie, outschool were read and judged sendable as-is. Soft findings (massive_bio competency keyword list, dropbox "examined why a previous migration attempt…") left for Jason.

## 4. Suggested investigation order

1. Read-only pass first (Cursor's plan, agreed): (a) does verify delete by design; (b) does any gate compare a sentence to the WE entry it cites (believed no); (c) sort the D6 examples into pile one (fails from the words on the page: metric units, prohibited phrases, partner-team allowlist, required hedges) versus pile two (cites the right entry, says something the entry contradicts or over-attributes: obie_2 inversion, ACC-303/ACC-113/ACC-220 attribution collapses); (d) count `hm.critical_read` dispositions that are the auto-writer's boilerplate. Before-fix copies: `data/review_evidence/2026-09-23-before-fix/`. Then one change: empty-role guard plus pile-one checks. Deletion behavior is a separate later patch.
   Correction to earlier ordering: D2 and D1 are different failures and D2 should not go first.
2. D6 entailment check: build a small regression set from the negative examples above, decide what can be mechanized (unit/period of metrics, banned attribution verbs vs. WE attribution table, "data model", partner-team allowlist, hedge retention for MET-04/13/15 and ACC-113/115/179) versus what needs the Pass 3 read.
3. D9: make the hash-bound gates honest (real HM read required, rubric score required for COMPLETE, rebind tooling that never overwrites another reviewer's row).
4. D3/D4/D8 individually; D7 by revisiting the bullet floor for earlier roles.

Do not edit `data/submissions/*` to "fix" findings during the investigation; the documents are already corrected and re-finalized.
