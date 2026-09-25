## [Unreleased] - 2026-09-23
[DRAFT] A finished queue row is not a send decision. The author no longer receives a career sentence that was cut in front of its unit or its "engineering built" clause. A draft that changes that unit, invents a percent, takes the funnel, pastes a process note into Core Competencies, or calls the company Confidential is blocked. A required line scored zero no longer slips under the fit floor. An empty role, a letter that names no past employer, a data-model phrase, and a dropped "estimated" on the hedged figures are blocked. A required demand for depth in a field he has not worked in, such as wealth-management pricing, is skipped.

### Fixed
- Stage 1 no longer parks a draft for an unused claim when that claim does not share distinctive wording with the job line. A remote or travel posting term is not a proof obligation. A JD term already inside a cited bullet counts as supported. A term whose story was left out does not have to be stuffed into the resume. A repair that changes the blocking findings is kept. The previous draft is put back only when those findings did not change (FR-375 / FR-381).
- An excerpt that cannot keep the unit on a number, or an engineering-built clause, is left out of the packet instead of being cut mid-fact. That cut is how $8,500 became "annually" and the landing page became Jason's funnel (CR-126 / FR-383).
- A drafted $8,500 with the wrong unit or no unit, a percent the career spans do not contain, a percent applied to a different group than the career span (25% of customers written as platform usage or as a usage profile), a funnel line that does not credit engineering, a "did not happen" note in Core Competencies, and "Confidential is" in the letter are hard blocks (CR-126 / FR-384).
- A classified required line with evidence 0 skips when the fit score is under 40, even if the qualification regex did not count it. A logistics-only extract with no such line still passes (CR-126 / FR-385).
- An experience role with no bullet, a cover letter that never names Cision, Sterkly, or Zero To Sixty, a "data model" phrase, and a $1M to $3M or drafting-time line that drops "estimated" are hard blocks at Stage 2 (CR-127 / FR-386). The $8,500 unit check stays the one already added in CR-126.
- A required line that demands deep or strong understanding of a vertical outside his background, such as wealth-management pricing, skips at Stage 0. "Develop a deep understanding," a preferred-only line, and a vertical already in domain experience do not. AUM is assets under management, not a product name (CR-128 / FR-387).
- Those same hard blocks now fail Stage 1 verify, so repair runs before the hiring-manager pass. A block that first appeared at Stage 2 left the unsupervised run parked, because that pass cannot rewrite the draft (CR-127 / FR-386).
- An uncited sentence is no longer deleted when that deletion creates a new hard block, such as removing the only sentence that names a past employer (CR-127 / FR-386).
- When the letter names no past employer, Stage 1 copies one cited resume bullet into a sentence that names that employer and cites the same claim. The repair prompt also forbids deleting the only employer mention (CR-127 / FR-386).
- When a drafting-time line or a $1M to $3M line is missing the word estimated, Stage 1 inserts it on that same sentence and updates the cite. The proof is no longer dropped as uncited after a repair rewrites it (CR-127 / FR-386).
- A sentence that says a migration finished without disruption is blocked unless it keeps the estimate that about 5 percent of customers never flipped (CR-127 / FR-386).
- A sentence that cites a real fact and says something that fact does not say is a hard block at Stage 1 and Stage 2. "Portability over custom tagging" cited to ACC-155 fails. The same words cited to a different fact do not. A high resume score does not clear it (CR-130 / FR-390).
- "Profile portability over custom tagging" is a hard block even when the sentence cites a different fact, or cites nothing. The true line is that custom tagging took priority (CR-131 / FR-391).
- "QA lead" is a hard block even when the sentence cites a different fact, or cites nothing. He walked test suites. He did not hold that title (CR-132 / FR-392).
- "Hundreds of client databases" is a hard block on any cite. The career entry is roughly 200 SQL databases (CR-133 / FR-393).
- A sentence that says support escalations were reduced is a hard block on any cite. The career file does not say that. A Jira priority formula that says streamline does not match this check (CR-135 / FR-395).
- "Release cadence" is a hard block on any cite. The career file does not use that phrase. A deletion cadence does not match (CR-137 / FR-399).
- "Testing analytics" is a hard block on any cite. The career file does not use that phrase. Pendo product analytics does not match (CR-138 / FR-400).
- A capitalized Visible after a space is a hard block on any cite. That is the codename. Lowercase visible does not match (CR-139 / FR-401).
- A cited resume bullet or cover-letter sentence that is itself a hard block is removed before repair. The line stays if removing it would create a new hard block, such as the only sentence that names a past employer. A line whose only blocked tool word is epic stays. The check is not loosened and no hedge is invented (CR-140 / FR-402).
- A cover sentence that states no personal fact is removed when it is a hard block, including a forbidden buzzword. A neighboring sentence that names a past employer stays (CR-140 / AC-513).
- A hedged `$100,000` is rewritten to `$100K` before the metric check. An unhedged `$100,000` stays. The precise number is not added to the approved list (CR-141 / FR-403).
- When the only past-employer sentence is uncited, Stage 1 adds a cited resume sentence that names that employer and removes the uncited sentence (CR-141 / FR-404).
- A clause that names a partner group outside the verified list is removed before the hiring-manager pass. A clause that names engineering stays. The warning still fires on the original wording (CR-142 / FR-405).
- A 40% contact-data drop-off sentence that calls the story an ingestion pipeline is rewritten to ETL path. The 40% outcome stays. The same block now fails Stage 1 (CR-143 / FR-406).
- A contributed claim that says designed or built is reworded to contributed to before the hiring-manager pass. An owned claim that says built stays (CR-144 / FR-407).
- A resume bullet that cites a fact and contradicts it is removed. A neighboring bullet stays (CR-145 / FR-408).
- A required line that shares only the word ownership with a mapped claim does not fail Stage 1. A line that shares a real term still requires the cite (CR-146 / FR-409).
- A cover letter over 2800 characters loses an uncited sentence until it fits one page. The limit stays (CR-147 / FR-410).
- A cover letter under 220 words gains a cited resume sentence. The floor stays (CR-148 / FR-411).
- A line about distributed data systems does not fail the geography check. A team distributed across offices still does (CR-149 / FR-412).
- A required line that shares only the word knowledge with a mapped claim does not fail Stage 1. A line that shares a real term still requires the cite (CR-150 / FR-413).
- A competencies row that names a tool outside the career history loses that token. The other tools stay (CR-151 / FR-414).
- A summary that says high-leverage loses that compound. Standalone leverage becomes use. data-driven stays (CR-152 / FR-415).
- A contributed claim that says design is reworded to contributed to. An owned claim that says built stays (CR-153 / FR-416).
- A hiring-manager read bound to the previous file bytes is rebuilt after this pass rewrites the documents. The hash check stays (CR-154 / FR-417).
- A country list and a geography use of distributed are removed when the posting never asks. A line about distributed data systems stays (CR-155 / FR-418).
- An opening sentence that repeats six or more words from the posting is dropped when another opening sentence stays. A one-sentence hook stays (CR-156 / FR-419).
- A contributed claim that says build is reworded to contributed to. An owned claim that says built stays (CR-157 / FR-420).
- A tilde in front of a number is rewritten to about. The digits stay (CR-158 / FR-421).
- A required line that shares only the word communication with a mapped claim does not fail Stage 1. A line that shares a real term still requires the cite (CR-159 / FR-422).

### Changed
- Backlog after the queue finishes means the mechanical gates passed. It does not mean the pair is safe to send (CR-126).

## [Unreleased] - 2026-09-18
[DRAFT] CSV drop-folder ingest, leased harness packs, and a pipeline panel in Review Center. Drop a jobs CSV in `data/inbox/csv/` (or upload from the panel), then run `run_queue_worker.py`. Resume each job with the same `run_submission.py {slug} --resume` path as before.

### New
- Drop `applyr_jobs*.csv` into `data/inbox/csv/` and run `python scripts/ingest_csv_queue.py`. Valid rows become queued opportunities plus `pending_review/{slug}/Original_JD.txt`. Bad rows and broken files go to a durable quarantine list instead of disappearing from the terminal (CR-119 / FR-340–FR-342).
- Claim a pack with `python scripts/queue_claim.py claim --worker <id> --size 8` (inspection only). The default run path is `python scripts/run_queue_worker.py --worker <id>`, which claims its own pack. Two harnesses can share one SQLite queue. A killed worker does not leave a second runner on the same slug (CR-119 / FR-343–FR-344).
- Review Center shows queue depth, current leases, stuck items, and quarantine file/line/error codes, and can upload a CSV into the same inbox (CR-119 / FR-345, FR-347).

### Changed
- A missing required line counts as zero in the fit score. It is not dropped to make the number higher. A written hard gate still skips with no card. Any other required miss only skips when the score is under 40. Review Center no longer holds the queue. A card appears only when a named tool is why a job never went out. "I have used this" writes that tool into work experience and does not rerun the other jobs. The pipeline page shows Continuing, Skipped, Running, or Failed. CR-125 / FR-379 / FR-380 / FR-381 / FR-382.
- A required healthcare, health-industry, health-tech, medical, or ceramic years line skips without a Review Center card. A sentence that says that domain experience is required skips too. Medical benefits, "healthy," and a preferred-only tail do not. A stored Keep eligible answer does not keep that job alive. A Stage 1 provider timeout can be tried four times, with a wait between tries so the queue can take another job. The same findings still stop that job. FR-378.
- A requirements line that starts with "Strong …", such as clinical acumen, counts as a real requirement. A fit score under 40 then skips. An empty requirements extract still does not skip on the score alone. Lumira Search had scored 25 and still passed. FR-330.
- A required healthcare or ceramic years line, a people-manager posting, product-line profitability, and a hands-on KYC must-have skip in Stage 0. "Nice to haves" stays optional, so a founder bonus cannot hold the job. A model hard label that is not one of those counts as zero. It does not open a card and it does not hold the job. Very Good Security's payments-platform line was queued under that rule. CR-125. FR-287 / FR-338.
- A lowercase "unified" is not the company Unified, and a second posting labeled "Medrisk 2" is still Medrisk. A hiring-manager pause frozen on a warning the current check no longer emits is claimed again. A Stage 1 repair that put the previous draft back can run once more. The second miss stays paused. A missing cover-letter thanks and an em dash are filled in during verify instead of parking the draft. FR-265 / FR-319 / FR-344 / FR-375.
- A later No on a skill card replaces an earlier Yes in skill memory. A first No still does not create a career-long record. GCP is No: no hands-on use. FR-283.
- A title that lists Staff beside PM and Senior PM, such as "Product Manager (APM/PM/Sr PM/Staff PM)", is not blocked as a Staff role. "Staff Product Manager" still is.
- "Lead a small team of analysts" is people management and skips. "Lead a team of stakeholders" does not. NLP in "AI/NLP" is a method, not a product card.
- Claiming customer discovery fails Stage 1, so repair can remove it before the queue parks. "An adjacent team built" is that team's verb, not an ownership claim. LW-028 / FR-370.
- A Stage 1 repair that returns cites as a flat sentence-to-id map is stored on the resume or the letter, whichever contains that line. A job already parked because that map was rejected is claimed again and the saved repair is applied. FR-265.
- A queue run does not wait for a hand-typed rubric score while the Agy rubric is off. The manifest records that verification passed, and the packet can save. The worker sees that rule when it claims and when it writes the job, so a save that failed only for the missing score is picked up again. A manual run still requires the score. AC-464 stays off. FR-371.
- "Partnered with a peer product manager" is not an unverified department. Design beside that role still warns. LW-005.
- The lowercase adjective "unified" in front of words like stakeholder or management is not the company Unified. LW-032.
- A duplicated company label such as "Sourcegraph 2" still counts as the employer Sourcegraph. Eastern Time and North America are not products. LTV, CDP, MMIS, MDM, and MCP are category acronyms, not products. Member 360 is a concept name, not a product. A required tool that is missing from work experience no longer pauses the job, including one already parked on that reason. The draft must not claim it. A card appears only when that tool is why a job never went out. CR-125.
- A queue run closes hiring-manager pair and density warnings, and records the hiring-manager read from lines that are actually in the resume, letter, and job description. A warning that is not one of those heuristics still waits. FR-319.
- The repeated-phrase warning lists its examples in a stable order. A later resume no longer wipes the hiring-manager dispositions just because the example list shuffled. LW-009-PAIR.
- A required line that only names a tool as an example ("for example", "such as", "including", "or similar") no longer withholds the job when a different tool in that same list is already in the skills catalog. Claude anchors Magic Patterns. AWS anchors Azure, Google Cloud, and IBM Cloud. Google Analytics does not count as Google Cloud. A missing product stays in the reason list. It does not pause the job. A card appears only when that tool is why a job never went out. CR-125. A job already parked on only that example list continues without `apply_anyway`. FR-374.
- If a repair leaves Stage 1 failed with the same blocking findings, the previous draft is put back. A repair that changes those findings is kept. The same findings then park the job. FR-375.
- A blank company on `claim_provenance.json` is filled from the Stage 0 gate. Truth no longer blocks on a label the gate already has. FR-376.
- When a resume bullet already uses a packet JD term but the cite is missing, that cite is added from the packet when the employer matches, and the draft is checked again before a full rewrite. FR-377.
- A paused Stage 1 failure can be requeued when the only conversion hold is a market or industry label (EdTech, B2B2C). A missing product does not require `apply_anyway`. FR-367.
- A Stage 1 repair that returns citations as a bullet-text map is stored as `resume_claims` rows, including the company name. A job parked on that map, or on a cite file with no company, is claimed so verify can repair the file. Unused-tag coverage warnings are recorded and the packet continues. An empty provenance object does not replace the draft. Customer Discovery stays off the ATS miss list because claiming that work is already blocked. FR-265 / FR-370.
- A Stage 1 verify failure on a draft that already exists now runs one in-lease repair (`build_stage1_repair_prompt.py`, then `run_stage1_repair.py`) and resumes in the same worker pass. A timeout or a repair that never produced a draft stays paused. One rollback can be claimed again. A second rollback stays paused. FR-344 / FR-375.
- The queue worker keeps taking the next batch until nothing left can move. It does not stop after one batch, and it does not run the same paused job in a circle. FR-373.
- A finished packet saves itself into the app. The queue no longer waits for a finalize button. The job shows up for review and edits. If the save does not complete, that job stays waiting and is not picked up again. FR-371.
- The pipeline page lists each job as Continuing, Skipped, Running, or Failed, with one sentence. There is no Waiting state for a question. FR-372 / FR-382.
- A 40% contact-data line that says Jason connected or bypassed the path himself, says he owned that integration, says he conceived it, calls that story an ingestion path, or adds frontend screens, now blocks that sentence only. The rest of the resume stays. Wording that says he drove the decision, or that an engineer proposed the bypass, still passes. FR-369.
- Career-file "do not claim" notes that were never given an id now attach to the story above them, and stop at the next section. Claiming customer discovery as something he already did blocks that line. Saying he did not, or only naming what the job asks for, still passes. FR-370.
- Stage 0 `conversion_risk` no longer treats the employer name, a chopped section header ("And Experience"), or methodology (OKRs, MVP) as a required product gap. Dynamics and Delta Lake stay named in the reason list. They do not withhold the job. CR-124 / FR-367–FR-368.
- Market labels (B2B2C, SaaS) and industry labels (EdTech) are the same chrome. A job already parked on only those labels continues into Stage 1 without `apply_anyway` and without another Stage 0 extract. A missing product is recorded and the job continues. CR-124 / FR-367.
- `scripts/import_csv_to_submissions.py` is a legacy wrapper. It no longer hardcodes Downloads paths and requires explicit CSV arguments. Prefer `ingest_csv_queue.py`.
- Cooldown NULL dates fall back to `applied_at`, then `created_at`, instead of blocking forever.
- AI/ML hard-skip is train / fine-tune / build models, or an ML engineering / data science background. Product copy like "deploy AI models" and "shipped AI features" no longer skip.
- `apply_resume_header.py` always overwrites name/contact, role headings and location lines, education, cover-letter greeting, and sign-off from `workExperience.md`. The author writes only summary, competencies, bullets, and letter body.
- Stage 1 verify failures use a repair prompt (`scripts/build_stage1_repair_prompt.py`) instead of a full fresh authoring resample. Loop until verify passes or a round makes no progress. Truth/format blocks stay blocking; other findings forward to Stage 2.
- A job paused at `NEEDS_DISPOSITION` stays paused across claims until `reviews/dispositions.json` is newer than `paused_at`. `WAITING_FOR_INPUT` stays paused until Review Center questions for that slug are all completed, or a cascade/extraction-review import is newer than `paused_at`. `WAITING_FOR_LLM` still promotes when Stage 1 files are ready. `FAILED` never auto-promotes (CR-119 / FR-346). `claim_pack` leases ready paused jobs first (oldest `paused_at`), up to pack size, then fills with the oldest queued rows. Extra paused rows stay paused. `WAITING_FOR_INPUT` without new input returns the last Stage 0 receipt instead of re-running Agy.
- Unused high-priority packet claims are forwarded in `stage1_forwarded_findings.json` instead of failing Stage 1. Cover letters argue 1-2 stories that each cover several top requirements, not one story per requirement.
- `agy_quota_tracker` now records agent-step count and cache-read tokens. Agy's final `result.usage` is the sum of internal agent steps, not a misread field. Size batches from five-hour percentage-point drops; cache-read is not 1:1 with those drops. Stage 0 Agy calls write `observability/agy_quota.jsonl` receipts (stage, slug, task, cache status, usage, weekly/five-hour before and after). A failed `/usage` read is `missing`, never a silent zero. `run_submission.py` binds the active slug and turns receipts on.
- Stage 1 is not ready on empty `Resume.md` / `CoverLetter.md` or empty/invalid `claim_provenance.json`. Agy `SUCCESS` with no author artifacts stays `WAITING_FOR_LLM`.
- Packet `hard_constraints` and the authoring digest self-check now include total PM experience read from `workExperience.md` §1.0 (write seven/7 years; never 4, 5, or 6).
- Before any Agy Stage 1 repair, mechanical lint findings are auto-fixed in place: wrong years figures become 7/seven, and a single semicolon, em dash, or colon-as-dash is split into two sentences. Unsafe punctuation is skipped. Auto-fixes are logged in `stage1_repair_state.json`. Agy is only called for what remains.
- Stage 1 repair prompts carry ranked rule/file/line/offending/suggestion rows, the full current Resume.md and CoverLetter.md, the matching digest sections, and packet excerpts for cited claims. They do not re-send the full authoring prompt or the packet. Target is under 16KB. The model returns full corrected documents; `claim_provenance.json` is optional and the existing file is kept when omitted. Raw model output is always saved to `stage1_repair_attempts/{n}.txt`. The repair event cap counts tool/non-text steps, not streaming `agent_response` deltas.
- Stage 1 validation failure writes workflow `FAILED`. The worker runs one in-lease repair and resume before it pauses that row. A no-progress, timeout, or failed repair stays paused `FAILED` and is not auto-promoted. A later hand repair can still requeue after valid artifacts are written.
- Stage 1 Agy repair is a sandboxed one-shot `--print` call: text in, text out, no tools, no workspace files. A tool request or permission denial fails the call. Wall time (default 180s) and event count (default 20) caps kill the process and record `repair_timeout`.
- Stage 2 COMPLETE / Stage 3 READY maps to `paused` with `paused_reason=ready_to_finalize`. The lease is released. Review Center counts it separately from other paused jobs and never auto-promotes it. `--finalize` maps the row to `done`.
- Cover letters and resumes mention countries, team locations, time zones, or "global/distributed" work only when the JD asks for global, international, distributed, cross-timezone, or multi-region work. Otherwise describe the collaboration itself. `LW-039` WARNs when a draft names that geography and the JD does not.
- A rebuilt `authoring_packet.json` / `authoring_prompt.md` refreshes the Stage 1 `WAITING_FOR_LLM` receipt hashes instead of leaving `STALE: stage1` on resume.
- Evidence-first Stage 1 authoring is reserved as CR-120 (`FR-348`–`FR-352`). Years-range keeps CR-117. The production Stage 1 default is unchanged.
- Stage 0 Agy evidence uses 3-item chunks and retries omitted IDs once. An incomplete Agy evidence batch pauses as `subscription_review`, not cost authorization. Queue `WAITING_FOR_INPUT` and `FAILED` map to `paused` so the lease clears. An omitted-ID pause keeps `.stage0_spool`, writes `missing_item_ids` on the Stage 0 receipt, and continues later chunks instead of aborting the rest of the batch.
- A paused `FAILED` or `subscription_review` queue row can be put back on the queue only with `python scripts/queue_claim.py requeue --slug SLUG --reason TEXT`. Leased, in-progress, done, and ready-to-finalize rows are refused. The reason and who requeued it are stored on the row.
- Stage 0 subscription adapter caches each returned item and re-asks only missing IDs once, then fail-closed. Evidence example ids are live-shaped (`required:0:<hex>`), not `req-001`. Replay/smoke Agy sessions are one per job.
- CSV ingest strips a role title that was appended to the Company cell (bookmarklet first-line company on LinkedIn). `ESO Product Manager` with Position `Product Manager` slugs as `eso`, so cooldown and skip-ledger match. Punctuation-stripped title suffixes (`Product Manager (Remote)`) also strip. False-skip rows from the Agy shakedown were cleared and re-queued (omnissa, optum, origami_risk, goodrx, businessolver, eso, velera, employers, ss_c_technologies).
- `queue_claim.py requeue` on a `subscription_review` pause caused by a harness item-ID omission now actually re-attempts Stage 0 instead of bouncing back to the same stale `WAITING_FOR_INPUT` receipt. `run_until_waiting_for_llm`'s resume check previously required a manual `stage0_cascade_import.json` for every `subscription_review` pause; it now also resumes when the receipt shows `missing_item_ids` or an "omitted item_ids" reason, since that failure is transient and the evidence cascade already retries just the missing items from cache. A genuine cost-authorization `subscription_review` pause (no omission signal) still requires the manual import. Found live on `casper_studios`, stuck across two explicit requeues.
- `scripts/run_stage1_author.py` runs the fresh, isolated Stage 1 author call as a real script instead of a hand-typed command: reads `authoring_prompt.md`, sends it to a sandboxed Agy session over stdin as stream-json (the CLI `--print` argument form hits Windows's command-line length limit on a 40-50KB authoring prompt), and writes all three required artifacts (Resume.md, CoverLetter.md, claim_provenance.json). Reuses `run_stage1_repair.py`'s stream-consumption and artifact-extraction helpers.
- `stage1_prerepair.py`'s deterministic LR-014/LR-006/LR-015 punctuation auto-fixes now also resync the matching `claim_provenance.json` bullet/sentence text when a fix changes a line's wording. Previously a colon/semicolon/em-dash split rewrote the document but left provenance pointing at the old wording, so the next verify pass falsely reported a fully-cited bullet as uncited.
- `tone_guard.py`'s workforce-reduction guard no longer blocks "customer attrition" (standard churn vocabulary). Bare `attrition` preceded by "customer"/"client"/"subscriber" is excluded; workforce/employee/bare attrition and layoffs/RIF language are still blocked.
- An over-token-budget `authoring_packet.json` (`packet_status` not `ready`) now persists a `FAILED` Stage 1 receipt before raising, instead of leaving `workflow_state.json` at whatever it was mid-run. Previously the queue worker had no terminal status to map, so the row sat `in_progress` on an active lease until it expired instead of releasing immediately.
- Named-tool extraction no longer queues Review Center cards for title-cased methodology phrases (`Minimum Viable Product`), scientific fields (`Biostatistics`), or category acronyms (`PSA`, `ERP`). Live miss on certara and velosio. `Microsoft Dynamics 365` on the same line still asks. `FR-286` / CR-109.
- A Stage 0 evidence-cascade extract failure (`Stage0ExtractError`) now persists `FAILED` on `workflow_state.json` before raising, same as the Stage 1 over-budget path. Live miss on nava_benefits: Groq 429 with no authorized next provider left the row `in_progress` until lease expiry because the worker only maps terminal workflow statuses. `FR-343`.
- Stage 0 production path is Agy again. `run_queue_worker.py` forces `APPLYR_STAGE0_SUBSCRIPTION_ADAPTER=1` on the spawned runner, and `run_submission.py` sets it when unset. Groq/Gemini are not the default fallback; they require explicit `APPLYR_STAGE0_CLOUD_LLM=1`. Live miss: a worker pack with the switch unset burned Groq 429s while Agy quota was at weekly 55% / five-hour 91%. `FR-328`.
- Same-posting Applied+ (`Applied` / `Recruiter Screen` / `Core Interviews` / `Offer and Negotiation`) or a pack already under `archive/submissions/` or `archive/skipped/` is already-handled at CSV ingest, claim, status update, and Stage 0. No new queue row, no new `pending_review/` folder, no skip-ledger write. Unlocked queue rows go `done`. Stage 0 is `ALREADY_HANDLED`, not PASS-with-flag and not Skip. Pre-apply still reuses. Different-role at the same company still only flags. Close stale mirrors with `python scripts/ingest_csv_queue.py --reconcile-already-handled` (no new CSV). Queue close does not fire when a live `pending_review` or `submissions` folder exists for that slug. CR-123 / FR-361–FR-366. Extends FR-342 lookup; does not rewrite it.

### Developer
- CR-119: additive SQLite tables `pipeline_queue`, `csv_ingest_ledger`, `csv_quarantine` (migration 025 + Python `ensure_schema`). `paused_at` on `pipeline_queue` (migration 026). `paused_reason` on `pipeline_queue` (migration 027, `ready_to_finalize`). Manual requeue audit columns `requeued_by` / `requeue_reason` / `requeued_at` (migration 028). Per-slug OS lock at `data/queue_locks/{slug}.lock`. Windows runner children sit in a Job Object with `KILL_ON_JOB_CLOSE`. `POST /api/pipeline-queue/upload` writes a server-chosen `.csv` under `data/inbox/csv/` then runs ingest. `run_submission.py` remains the canonical runner and marks a `ready_to_finalize` queue row `done` after `--finalize`.
- CR-123: `resolve_opportunity()` adds `already_handled` (jobs Applied+ and archive trees) after skip ledger and before live reuse. `LEGAL_TRANSITIONS` gains `queued→done` and `leased→done`. Claim, worker, `applyJobStatusUpdate`, and Stage 0 close unlocked matches; live leases stay fenced. `reconcile_already_handled()` plus `--reconcile-already-handled`. Extends FR-342; does not rewrite it.

## [Unreleased] - 2026-09-17

### New
- Stage 0 now has a bounded, switch-off `claudexor@3.12.1` subscription adapter
  (`scripts/stage0_subscription_adapter.py`) with separate extraction and
  evidence schemas, item_id binding, cache keys, readonly spawn, `--prompt-file`
  (so Windows `npx.cmd` cannot pipe on `|` in the prompt), and
  `subscription_minutes` tracked separately from `api_cents`. Failed,
  substituted, or non-readonly runs go to explicit review. When
  `APPLYR_STAGE0_SUBSCRIPTION_ADAPTER` is on, uncertain extraction and
  uncertain evidence use that adapter and never Groq/Gemini; the production
  default stays on the existing uncertainty path until replay passes (CR-114).
- Shadow Stage 0 evidence matching can only return match or abstain from
  human-reviewed tool aliases. It cannot emit HARD or Skip and is not used
  in production scoring (CR-114).

### Changed
- Blocked-company match is exact on the normalized name. `"Remote"` no longer matches `"RemoteHunter"`, and a blank company name no longer matches every blocked entry (CR-118 / FR-337).
- People-management skip fires only when this role has reports or manages people. Negated-role sentences and coaching other managers' reports do not skip. `network_page` is a flag, not a reject (CR-118 / FR-338).
- `"Also great to have"` / `"great to have"` are preferred headers. A line that says `"is required"` under a preferred header goes to required. The 30-JD replay records skip-reason agreement, not only skip vs pass (CR-118 / FR-339).
- Stage 0 extraction fallback responses no longer write into `training_data_feedback.csv`. Retraining ignores that unverified file and accepts only human-reviewed rows with provenance.
- Retraining uses a company-held-out set without pre-split feedback duplication, writes a candidate model/report, and requires explicit replay acknowledgment for promotion. The first candidate was not promoted (CR-114).
- Adjudication export (`scripts/export_stage0_adjudication.py`) writes `source=jason` or `source=claude_opus_jason_approved` rows with a non-blank `your_mark`. `source=claude_review` cannot reach `training_data_approved.csv` until rewritten. Claude/Agy/harness names are not human reviewers (CR-114 / CR-118 / FR-327).
- Years ranges now gate on the low end, the minimum the posting will accept. 3-7 and 5-7 pass; 7-10 and 8-12 still skip; 7+ still skips. Age and company-tenure figures are not experience floors. The years audit flags a winning range-top, age, or history figure instead of blessing self-consistent arithmetic (CR-117 / FR-332).
- Sitting-1 8-JD review found section headings scoring as required (CR-115). Required/preferred now drop heading, job-board metadata, and truncated-fragment chrome before evidence scoring. Leftover junk semantics stay unchanged. Replay is not a promotion gate until independent QA checks the stories.
- Evidence retrieval now force-includes corpus-backed distinctive tokens and windows huge inventory chunks so Acquia Jira/Confluence and executive-briefing evidence can reach the scorer. `coverage_ok` is not AI-token-gated (CR-116). Replay is not a promotion gate while that check can fail.
- Applyr Stage 0 leftover-line rules live in `scripts/stage0_classifier_contract.py`.
  Tools only transport that packet. Leftover buckets now include `junk` for ATS
  chrome (visible on the fit gate, never a cover-letter hook). Checkable
  qualifications with no duty verb are required, not responsibilities.
  Personality / "you are a person who" lines are culture and are never scored.
  AI leftover evidence retrieval includes `data/aiProjects.md` when the line is
  about agents/LLMs (CR-114).
- Stage 0 leftover-line subscription transport defaults to native Agy
  print mode (`--json-schema`, `--sandbox`, `--new-project`). The Applyr
  packet is `prompt.txt` in an isolated temp project, not argv. Denied
  tool calls fail closed to review. Production switch stays off (CR-114).
- Review Center cards now store and render why Stage 0 paused (`decision_basis`) and the uncertainty label beside the existing requirement and evidence excerpt (CR-114 / FR-329).

### Fixed
- Stage 0 model-flagged confirmations now require a tool flag plus named-tool
  and JD-grounding checks before creating a Review Center question. Generic
  traits such as "critical thinking" no longer create binary "have you used
  it?" cards through the model-only path.
- Re-running the CR-109 confirmation table rebuild no longer drops Review Center
  basis columns on the next Python connect (CR-114).

## [Unreleased] — 2026-09-15
[DRAFT] CR-112 consolidation maintenance reconciles the current candidate
after Stories 8.6 through 8.9. Focused offline checks pass. The supervised
real-JD dry run remains a future verification step, so readiness stays
`SUPERVISED_SMALL_BATCH_READY`.

### New
- CR-112 Story 7.3 (`FR-326` / `AC-424`): an operator can now certify Groq
  or Gemini as free-tier-only Stage 0 routes through a structured, expiring
  attestation in the `llm_settings` blob (`freeTierAssertions`, exact
  canonical statement, strict acknowledgement, 30-day expiry). Default
  installs are unchanged: without a valid attestation plus a declared
  `free_only` cost class, both providers stay `unknown` and the run still
  pauses at `WAITING_FOR_INPUT` / `pause_kind=cost_authorization`. Paid
  allowlist, budget, estimate, free-to-paid stripping, cascade import, and
  pause contracts are unchanged. No provider, network, or paid route is
  called by the mechanism.

### Fixed
- CR-112 Story 1.2 (`FR-297` / `AC-394`): over-budget authoring packets
  now remove redundant author-only omitted-candidate summaries before
  shrinking evidence excerpts. The full ranking audit remains in
  `evidence_selection_trace.json`, and attribution constraints are never
  dropped.
- CR-112 Story 8.7 (`FR-325` / `AC-423`): deterministic identity repair now
  replaces unbracketed contact placeholders and removes stacked placeholder
  headers.
- CR-112 Story 8.8 (`FR-323` / `AC-421`): distributed and event-driven
  requirements now favor item-specific messaging or architecture evidence
  over broad savings evidence, while cost and ARR/reliability controls retain
  their metric-bearing winners.
- CR-112 Story 8.9 (`FR-324` / `AC-422`): catalog validation now accepts the
  CR-094 tags-and-constraints claims-index shape while still rejecting
  unconstrained empty claims and ungrounded metrics.

### Changed
- CR-113 (`FR-322` / `AC-420`): rubric scorecard metadata gate requires `schema_version: 1`, current `rubric_sha256`, timezone-qualified `scored_at`, non-empty `reviewer_run_id` or `spawned_by`, and complete numeric per-criterion breakdowns (R1-R8, C1-C5) matching total scores with no unknown keys.
- CR-112 Story 8.6 (`FR-322` / `AC-420`): score provenance is implemented,
  hash-bound, role-tagged, boundary-band blind-read aware, and fail-closed on
  current-hash disagreement.
- CR-112 status records now identify the supervised real-JD dry run as future
  product proof. No provider, paid API, production SQLite, or submission data
  was used during this maintenance verification.

## [Unreleased] — 2026-09-13
[DRAFT] CR-112 Vanta blind adjudication, ranking characterization
corpus, and JD 3 Newsela on the isolated candidate. Blind Vanta resume
score 71 keeps Vanta `PRACTICE_COMPLETE`. Ranking fixtures characterize
current behavior, including the known Camunda defect, without changing
the formula. Score provenance is design-only. Newsela first draft
Resume 61 stayed below floor after honest recovery (62) and is left
blocked. No paid APIs. No push. CR-112 remains open. Batch readiness:
NOT_READY.

### New
- CR-112 Story 8.5 (`FR-321` / `AC-419`): executable ranking
  characterization tests for Camunda distributed-systems, Pearl and
  SupplyHouse REPLACE controls, cost-reduction, ARR/reliability, and
  near-tie. Camunda SAVINGS-over-messaging is a known-defect report,
  not a desired rank.
- CR-112 Story 8.6 (`FR-322` / `AC-420`): score-provenance design.
  Hash-bound scorecards, reviewer role, 3-point floor band, fail-closed
  disagreement. Not implemented this pass.

### Notes
- Vanta corrected resume blind adjudication
  ([Review](51bee1b0-e969-4cc0-af2e-5b9bfcfa27cc)): Resume **71**.
  R4 classified ~200 SQL databases as unpaired scale, not an outcome.
  Floor rule: blind >= 70 retains completion. Manifest 70 is not
  averaged with 71. Independent 68 is recorded, not selected.
- JD 3 Newsela (`data/authored_drafts/newsela_cr112_proof/`):
  independent first-draft Resume **61** / Cover **80**
  ([Review](adef9c23-397e-4ce3-8744-6eb88b4f6d23)). Mechanical recovery
  only. Implementer post-edit Resume **62**. `mech.rubric_floor.resume`
  BLOCK left undisposed. No HAR.
- Batch-readiness this pass: **NOT_READY**. Durable handoff:
  `docs/spec/08-implementation/SESSION-HANDOFF-2026-09-13-cr112-jd3-newsela.md`.
- Header-stack defect recorded, not fixed:
  `docs/spec/08-implementation/CR-112-unbracketed-placeholder-header-stack-defect.md`.

## [Unreleased] — 2026-09-13
[DRAFT] CR-112 Story 8.4 durable consumed extraction-review on the
isolated candidate. Stage 0 `--resume` after cost-authorization no longer
re-asks a review that was already consumed. No paid APIs. No push.
CR-112 remains open.

### Fixed
- CR-112 Story 8.4 (`FR-320` / `AC-418`): `try_load_review_import` reuses a
  valid `.consumed.json` when the live import is absent and the JD plus
  queue still bind. Unreadable consumed JSON fails closed. Live import
  still wins for a deliberate correction.

### Notes
- Design review ACCEPT WITH CHANGES
  ([Review](221eed13-6cf1-45e0-ba82-14c298ba0877)).
- Vanta JD 2 practice folder reached `PRACTICE_COMPLETE` after an honest
  resume `RESOLVED_EDIT` (65 → 70). First-draft baseline preserved.
- Story 8.3 follow-up design review ACCEPT no further digest paragraph
  ([Review](8b6fe4c0-479a-4ea9-bbd1-3d84be8d488b)).
- Ranking investigation design review ACCEPT WITH CHANGES, no formula
  this pass ([Review](0562aa4a-a797-4c15-8663-02c2f2819fb7)).


### Changed
- CR-112 Story 8.3 (`FR-319` / `AC-417`): lean authoring digest §5 now
  includes the locked keep-fact / change-language line. Generated Stage 1
  prompt SYSTEM BLOCK carries the same instruction. `LW-009-PAIR`
  detector and Stage 1 pair FAIL are unchanged.

### Notes
- Story 8.1 follow-up QA PASS recorded 2026-09-13. Floors stay 70/65.
- Story 8.2 security CLEAR and QA PASS recorded 2026-09-13.
- Story 8.3 design review DR-001 ACCEPT WITH CHANGES
  ([Review](ffcef2c9-5020-4992-9558-c6feb91f7997)). Independent QA PASS
  ([Review](de184edd-f4e3-4249-88ce-193500cb8161)).

## [Unreleased] — 2026-09-13
[DRAFT] CR-112 Story 8.2 practice identity on the isolated candidate.
Silent John Doe fallback is gone from the document pipeline. Identity
comes from gitignored `workExperience.md` or explicit
`APPLYR_SYNTHETIC_IDENTITY=1`. No paid APIs. No push. CR-112 remains open.

### Fixed
- CR-112 Story 8.2 (`SEC-006` / `AC-416`): `load_identity_profile` no
  longer reads SQLite or fills John Doe. Missing identity fails before
  `WAITING_FOR_LLM` and at `run_verify_only`. Tests use synthetic
  identity only.

### Notes
- Story 8.1 follow-up QA PASS recorded 2026-09-13. Floors stay 70/65.
- Story 8.2 security CLEAR and QA PASS recorded 2026-09-13.

## [Unreleased] — 2026-09-12
[DRAFT] CR-112 Camunda follow-up on the isolated candidate. CONVERT-READY
floors (Resume 70, Cover Letter 65) are now completion gates, not
warnings. Practice finalize can no longer mint `PRACTICE_COMPLETE` at
Resume 68. No paid APIs. No push. No merge to main. CR-112 remains open.

### Fixed
- CR-112 Story 8.1 (`FR-318` / `AC-415`): `check_rubric_floors` runs
  after rubric shape. `check_draft_manifest`, `check_stage2_ready`, and
  `check_finalize_ready` fail below floor. Practice and `--force` Stage 3
  cannot skip the helper. Mech emits BLOCK `mech.rubric_floor.resume` /
  `mech.rubric_floor.cover_letter`. `check_submission_status` DONE fails
  closed once the manifest floors fail. Follow-up QA PASS
  ([Review](3cd059c0-ba53-42b7-b66a-a6677a310de5)) 2026-09-13.

### Notes
- Camunda practice artifacts stay gitignored. Do not re-finalize that
  folder to inflate the resume score. First-draft baseline remains
  Resume 64 / Cover Letter 57, classification `FIRST_DRAFT_WEAK`.
- Practice identity (`SEC-006`) implemented on this candidate, pending
  security and QA review.

## [Unreleased] — 2026-09-11
[DRAFT] CR-112 local integration onto clean main. Epic 1 fail-closed
Stage 0 IDs and packet constraints, Stories 2.1 + 2.3 lean default spawn,
Story 3.1 closed-world extra-packet completion block (detection only), Story 3.2 omitted_reasons
plus sibling ranking trace, and Story 3.3 advisory swap report, and Story 3.4 admin-line skip, and Epic 4 adversarial fail-closed, plus Story 5.1 F7 gerund reporter
(advisory only), and Stories 6.1/6.2 sanitized offline eval harness, plus Story 2.2
force-added batch runner (never default). Extra-packet detection FAILs
Stage 1 verify. Recovery (remove / rewrite / widen / human) is Story 3.6
and is not in this detector. SupplyHouse is not rewritten.

On committed `main` (`8bbc497`) the hash-tail `len >= 8` matcher already
rejected `req-001`, and `assemble_packet` already omitted the wipe. The
list-position remap and the constraint wipe lived in an uncommitted
candidate tree, never on HEAD.

### Fixed
- CR-112 Story 1.1 (`FR-296` / `AC-393`): `_resolve_item_id` must not map
  invented sequential ids (`req-001`, `req-002`, `pref-1`) onto the Nth
  item in the current batch. Unknown ids raise `unknown batch item_id`
  even under `partial=True`, so the caller falls back instead of retrying
  a positional guess. Hash-suffix (`len >= 8`) and unique ordinal/suffix
  fallbacks remain.
- CR-112 Story 1.2 (`FR-297` / `AC-394`): `assemble_packet` must not wipe
  `claim_constraints` to `{}` to squeeze under `_TOKEN_BUDGET`. Over-budget
  after dropping `learned_examples` and shrinking excerpts to
  `_EXCERPT_MIN_CHARS` stays `incomplete` via Rule 5.
- CR-112 Story 1.4 (`FR-298` / `AC-395`): read-only
  `scripts/audit_packet_integrity.py` flags already-shipped ready packets
  with empty `claim_constraints` while `evidence_map` or `soft_gaps` is
  non-empty. Live scan 2026-09-10: 7 folders, 1 flagged (`supplyhouse`).
  Detector writes nothing. A sidecar file is informational and is not
  authorization. Unreadable packets (including invalid UTF-8), a missing
  root, and invalid field types are an incomplete inspection (exit 2), not
  a clean scan. An unreadable informational disposition sidecar does not
  abort the scan or clear a packet flag.
  SupplyHouse recovery is not on the active backlog
  (Jason, 2026-09-10: already corrected; do not rebuild, re-author, or
  request risk acceptance). General detector and tests remain.

### Notes
- FINDING 2026-09-10: Cursor (Grok 4.6) wrote a gitignored live
  `packet_integrity_disposition.json` with `HUMAN_ACCEPTED_RISK` and a
  reason attributed to the candidate. Origin:
  `docs/spec/08-implementation/FINDING-2026-09-10-agent-packet-integrity-disposition.md`.
  Tracked stand-in: `tests/fixtures/packet_integrity_disposition.sanitized.json`.
  The live original stays local only. No workflow treats that sidecar as
  human authorization.

### Changed
- CR-112 Story 7.1 (`FR-316` / `AC-413`): Stage 0 cost-pause status now
  reads `pause_kind` from the Stage 0 receipt. Cost-authorization copy
  states that no model API call occurred, Stage 0 is incomplete, and
  import, certified zero-charge, or paid authorization can resume the
  run. It prohibits pasting `authoring_prompt.md`. Older receipts without
  `pause_kind` keep the existing Review Center copy.
- CR-112 Stories 7.1 / 7.2 (`FR-316` / `FR-317` / `AC-413` / `AC-414` /
  `NFR-015`): model calls require `offline` / `manual_paste` / `free_only` /
  `paid_with_budget`. Unknown is not callable. Groq/Gemini stay unknown
  without a zero-charge adapter assertion. `free_only` cannot fall back
  to paid. Unknown cost omits `api_cents` instead of recording 0. Eval
  stays zero-call offline. No live-folder rewrite.
- CR-112 Story 3.6 (`FR-315` / `AC-412`): extra-packet recovery is a
  separate step. KEEP and sibling extras `REMOVE_EXTRA`. True AMBIGUOUS
  pauses for qualitative review. Same-item TRACE REPLACE widens the
  packet, invalidates the leaked draft, and returns `WAITING_FOR_LLM`.
  Recovery helpers do not write workflow receipts. No live-folder rewrite.
- CR-112 Story 3.5 (`FR-313` / `FR-314` / `AC-410` / `AC-411`): after
  Top-2, a deterministic comparator may REPLACE an omitted eligible
  claim that clearly dominates the weakest same-item pick.
  `displaced_by_dominance` is the packet omitted reason. Pearl and
  SupplyHouse SAVINGS do not REPLACE. No `call_llm`. No live-folder
  rewrite. Story 3.3 stays read-only.
- `scripts/run_all_tests.py` now runs `test_stage0_evidence_cascade.py`
  and `test_audit_packet_integrity.py`.
- The offline Stage 0 provider golden harness now explicitly certifies
  its mocked provider as zero-charge instead of relying on provider names.
- `.codex/skills/generate-submission/SKILL.md`
- `AGENTS.md` (root trigger paragraph only)
- `scripts/author_from_packet.py` `run_verify_only` FAILs extra-packet cites
  (`recovery_state=UNRESOLVED` or `CLOSED_WORLD_UNREADABLE`)
- `scripts/build_authoring_packet.py` `build_evidence_map` records why
  scored claims lost Top-2 without changing who wins
- `scripts/build_stage0_fit_gate.py` `_is_administratively_satisfied`
- `scripts/build_authoring_packet.py` `_enqueue` skip-scoring for eligibility
  fingerprint / nights-and-weekends lines

### Added
- CR-112 Story 7.4 (`FR-316` / `AC-413`): Review Center now includes a
  compact operator for Stage 0/1/2 status and explicit Start, Resume, and
  Finalize actions through the authenticated backend routes. Cost-pause copy
  states that no model API call occurred, no API cost was incurred, and Stage
  0 remains incomplete until cascade JSON is imported, a zero-charge provider
  is certified, or paid use is authorized. This slice adds no provider
  configuration or cascade-import UI.
- CR-112 Story 7.3 (`FR-316` / `AC-413`): authenticated backend operator
  routes for starting, resuming, inspecting, and finalizing
  `scripts/run_submission.py`. The service returns an allowlisted workflow
  status projection, uses the centralized no-shell process runner, and rejects
  overlapping mutating commands for the same submission folder. UI remains
  out of scope.
- `scripts/cost_eligibility.py`
- `scripts/test_cr112_story71.py`
- `scripts/closed_world_recovery.py`
- `scripts/test_cr112_story36.py`
- `scripts/evidence_dominance.py`
- `scripts/test_cr112_story35.py`
- `scripts/test_cr112_lean_spawn.py` (2.1 + 2.3)
- `scripts/packet_closed_world.py`
- `scripts/test_cr112_story31.py`
- `evidence_selection_trace.json` written by `build_packet`
- `scripts/test_cr112_story32.py`
- `scripts/report_evidence_swaps.py`
- `scripts/test_cr112_story33.py`
- `scripts/test_cr112_story34.py`
- `scripts/run_adversarial_pressure_test.py`, `scripts/test_cr112_adversarial.py`
- `tests/fixtures/adversarial/workflow_cases/`, fixtures README
- `docs/spec/INVARIANTS_CATALOG.md`
- `docs/spec/archive/adversarial-payloads/`
- `scripts/report_resume_gerund_rate.py`
- `scripts/test_cr112_story51.py`
- `scripts/run_cr112_eval.py`
- `scripts/test_cr112_story61.py`
- `tests/fixtures/cr112_eval/`
- `.claude/workflows/generate-submission-batch.js` (force-added)
- `scripts/test_cr112_story22.py`

## [Unreleased] — 2026-09-09
[DRAFT] Stage 0 cascade cutover complete — live provider validation, archive replay,
partial-result recovery, proactive batch sizing, and legacy classifier removal.
The CR-108 evidence cascade is now the sole Stage 0 classification path.

### Changed
- CR-108 (Epic 7.7): Removed the legacy per-line local classifier and STAGE0_EVIDENCE_CASCADE
  rollback flag. The cascade is now the only classification path. `stage0_evidence_cascade_enabled()`
  always returns True, the `cascade_enabled` parameter was removed from `classify_gaps` and
  `screen_responsibilities_for_exclusion`, and the sequential per-line fallback was removed.

### Fixed
- CR-108: Groq API calls were missing `max_tokens`, causing truncated JSON responses on
  21-item batches. Set to 8192.
- CR-108: Cascade system prompt described required JSON fields in prose but never gave an
  explicit schema or example. Groq omitted the `reasoning` field on first live run. Added
  a `RESPONSE FORMAT` section with all required fields and a full example object.
- CR-108: Golden test did not pass evidence excerpts to the model, so all non-gate items
  scored evidence_level=0. Added `evidence_excerpt` fields to golden entries expecting
  evidence_level > 0 and wired them through `_items()`.
- CR-108: Added `_repair_truncated_json()` to recover individual result objects from
  truncated provider responses via balanced-brace scan inside the `results` array.
- CR-108: `validate_batch_response` rejected partial results entirely when items were
  missing, forcing the fallback provider to re-send the full batch. Added partial mode
  that returns recovered items + missing set so only the missing items are retried.
- CR-108: Batch sizing only considered item count (`MAX_BATCH_ITEMS=24`), not output size.
  Added proactive split based on estimated output tokens derived from prompt size, so
  batches with long evidence excerpts are split before truncation can happen.
- CR-108: `_resolve_item_id` couldn't match model-returned ids in three formats: ordinal-only
  ("0"), mangled prefix ("req-7-hash"), and abbreviated prefix ("req-001"). Added ordinal
  matching and hash-suffix matching for real JD replay.
- CR-108: found on review — the same-provider retry call added for partial-result recovery
  was not wrapped in the same broad `except Exception` as every other `call_llm` call in
  `classify_requirements_batch`'s provider loop. A transport error during the retry (timeout,
  connection reset, rate limit) crashed the whole classification instead of falling back to
  the next configured provider, even when it was available — the exact failure mode this
  robustness pass was meant to handle. Reproduced live, fixed, added a regression test.
- CR-108: found on review — Epic 7.7's legacy-classifier removal made a
  `screen_responsibilities_for_exclusion` batch failure raise, contradicting that function's
  own still-documented fail-open contract ("one line's LLM error should never abort a Stage 0
  run"). It also raised the wrong exception type for `workflow/runner.py`'s
  `run_stage0()` to catch (only `Stage0NeedsInput`/`Stage0ExtractError` are handled there),
  so it escaped uncaught rather than becoming a clean `WorkflowError`. Reproduced live, fixed
  by catching the batch failure and returning whatever Phase 1 already found instead of
  raising — without resurrecting the removed legacy per-line classifier. Added a regression
  test.
- CR-104: URL state sync race condition — the sync effect could strip the `job` param
  before the restore effect read it on initial load. Captured the initial job ID at mount.
- CR-104: `SyncActivityView` (Job Search tab) ran its own independent `fetchMatchedJobs()`
  on a 3s interval hitting `/api/jobs` directly, duplicating the shared `useJobs()` query
  Story 5.2 converted. Now takes `jobs` as a prop and derives `matchedJobs` via `useMemo`;
  the three spots that called `fetchMatchedJobs()` for an immediate refresh now invalidate
  the shared query instead.

### Developer
- CR-108 (Epic 7.3/7.4): Archive replay harness (`test_stage0_archive_replay.py`)
  validates the cascade against real archived JDs. 5 JDs replayed with Gemini: 27 items
  classified, 2 HARD gates found. Comparison with legacy per-line classifier on 2 JDs:
  87% call reduction (15→2), 58% time reduction (25.92s→10.88s), 87% gate agreement
  (mismatches are legacy errors, not cascade errors).
- CR-108 (Epic 7.5): Live provider-backed golden validation complete. Both Groq
  (openai/gpt-oss-120b) and Gemini (gemini-3.5-flash-lite) pass 21/21 against the active
  CR-093 golden set using credentials stored in SQLite. All seven categories hold.
  Gemini shows minor non-determinism on tool-002-v2 (20-21/21 across runs). Four fixes
  were required: explicit JSON schema in prompt, evidence excerpts in golden set, JSON
  repair for truncated responses, and Groq max_tokens increase. Two robustness improvements
  added: partial-result acceptance with same-provider retry for missing items, and proactive
  batch splitting based on estimated output token count. 4 new unit tests cover both.
- CR-104: Browser verification complete for Stories 1.11 (component decomposition) and
  2.5 (fail-closed bind + API key masking). All sections exercised, no regressions.

## [Unreleased] — 2026-09-08
[DRAFT] Generic cover-letter hook guard (CR-098 follow-on): cover letters that open by
labeling the role ("shows what makes this role interesting") instead of stating a concrete
company fact are now caught and warned against.

### Changed
- CR-098: `LW-038` (WARN) fires when the opening hook uses the self-referential "what makes
  this role/opportunity/position interesting/compelling/exciting" shape. The author prompt's
  COVER LETTER VOICE block now states the same rule so the shape is prevented at first draft,
  not only caught in review. The check is narrow by design: a specific hook and the same
  words outside the opening hook pass.

### Developer
- CR-098: Registered as `FR-295` / `AC-392`; mapped in `FEAT-013`, the traceability matrix,
  and the canonical no-ai-slop skill. The rule ID was renumbered from the earlier draft's
  `LW-036` to `LW-038` because `LW-036` already belongs to the closed-lost jargon rule.
- CR-108 (Epic 7.1/7.2): Stage 0 cascade golden validation now reports per-category
  results (`--category` filter added to `test_stage0_provider_golden.py`); the previously
  dead Layer C model-flagged confirmation tunnel is implemented — the cascade validator
  honors `needs_user_confirmation` / `canonical_skill` / `skill_kind` (fail-closed when a
  flag lacks a skill key) and the fit gate creates a durable `skill_presence` pending item
  for a model-detected tool the extractor missed, pausing that opportunity and resuming on
  a `CONFIRMED_USE` answer without repeating the provider call. Offline golden fixtures
  remain 21/21 for Groq and Gemini with one routed batch call each and every category PASS.

## [Unreleased] — 2026-09-03
[DRAFT] Stage 0 gate escapes and header placeholder fixes — multiple deterministic gates failed to catch roles that should have been skipped, and resume/cover letter headers with partial placeholders were left unfixed in compiled PDFs.

### Fixed
- CR-110: Title gate now blocks "Junior" and "Associate" titles — blocked_title_lists() merges blocked_role_titles with blocked_titles instead of ignoring the UI list; "Associate" and "Junior" added to blocked_role_titles in candidate_preferences.json
- CR-110: Years gate now detects "10 years' experience" (apostrophe) and "Twelve+ years" (spelled-out numbers) — regex patterns fixed and word-number mapping added
- CR-110: Revenue/billing exclusion zone regex broadened to catch real JD phrasings (product line revenue/margin, dynamic pricing, payroll/billing workstreams)
- CR-110: Header placeholder fix now handles partial placeholders (real name + bracketed contact info) and blank contact lines, not just fully-bracketed headers
- CR-110: `run_prefs_gate_safe` now logs errors to stderr and includes `_gate_failed` flag — previously caught all exceptions silently and returned passed=True, skipping every deterministic gate with no trace
- CR-110: Prefs gate rejects and flags now stored in stage0_fit_gate.json output as `prefs_gate_rejects` and `prefs_gate_flags` — previously discarded, making gate auditing impossible
- CR-110: Header placeholder check now blocking in verify_submission.py — resumes with [phone]/[email]/[LinkedIn] in the header cannot pass mechanical verification
- CR-110: Text normalization for curly quotes/apostrophes added to seniority_gate.py — prevents future regex misses on smart-quote variants from HTML-exported JDs
- CR-110: Self-clearing dispositions (FALSE_POSITIVE, ACCEPTED_AS_CORRECT, HUMAN_ACCEPTED_RISK) now require substantive reasoning in dispositions.json — bare strings no longer clear these findings; RESOLVED_EDIT and NOT_APPLICABLE remain bare-string compatible
- CR-110: LLM-based industry classification added as supplementary gate — uses Groq/Gemini to catch blocked industries the keyword gate misses (e.g., a gambling company that never says "gambling"); high/medium confidence blocks, low confidence flags, LLM failure fails open
- CR-110: JD content validation now blocks template JDs with bracket placeholders ([Company X], [phone], [email]) and talent-matching network pages ("apply once and get matched") — previously only a 200-char minimum check existed between DB insert and Stage 0

### Changed
- CR-110: blocked_title_lists() in seniority_gate.py now merges blocked_role_titles and blocked_titles instead of preferring one over the other
- CR-110: `mechanically_verified` conjunction now includes `header_placeholders.ok` — bracket placeholders in resume/cover letter headers are a blocking failure
- CR-110: Removed "Junior (1-2 Years)" from `experience_levels` in candidate_preferences.json — field is vestigial (no code reads it since CR-010 decommissioned LinkedIn scouting), removal eliminates cosmetic inconsistency with title blocklist

[DRAFT] **CR-111 — Instruction-authority hygiene (2026-09-07).**

### Changed
- CR-111: Declared one canonical copy for the four duplicated instruction skills and
  replaced the other copies with small pointer stubs, preventing cross-harness skill drift.

### Developer
- CR-111: Added `scripts/check_instruction_drift.py` with fixture tests and wired it into
  `check_context_pack_freshness.py`; the guard checks pointer size, canonical targets,
  absolute file URLs, and known stale instruction patterns.

- **Fix: `check_submission_status.py` / `verify_submission.py` / `stage_gate.py` crashed on non-ASCII
  company folder names (2026-09-03).** A submission folder with a diacritic in its name (e.g.
  `collēctīvus_holdings`) crashed all three scripts with `UnicodeEncodeError` on a cp1252 Windows
  console, before any PASS/FAIL/STATUS line printed. A Stop hook reading the crash as "can't verify"
  correctly refused to accept a completion claim for that folder even though the submission itself
  was mechanically clean. Fixed by routing the status-line prints through an encode/decode-with-
  `errors="replace"` helper (the same pattern `run_submission.py`'s event printing already used) in
  all three files — a non-ASCII name now degrades to `?` characters in console output instead of
  crashing the process. 40 existing tests across `test_check_submission_status.py`,
  `test_stage_gate.py`, `test_verify_submission.py` still pass.

[DRAFT] **CR-109 — Review Center queue UX, extraction precision, bad-data loop (2026-09-02).**

### Fixed
- [BUG-001] Review Center no longer asks "Have you used Spirit/Preferred/Thinking in your
  work?": named-tool extraction now rejects JD label shapes (a candidate followed by `:` or
  `)`), knows trait/qualifier/role-title/generic-tech vocabulary as stopwords, and blocks any
  candidate containing a hard-blocked tool as a token run (closes the "Workday Ecosystem /
  Workday Web Services / Workday Recruiting" hole, since `workday` itself was always blocked).

### Changed
- Review Center answers are now single-tap: selecting an answer saves it immediately and the
  next card in the queue appears with a short transition. There is no "Save answer" step.
  Mistakes are corrected from the Completed queue, where each card now shows its recorded
  answer and a Change answer button; every change is preserved in the answer history.
- Optional where/what/when details for a "Yes" answer now live only on the Strengthen
  evidence card that a Yes automatically creates, instead of a duplicate inline form.

### New
- "Not a real skill" (BAD_DATA) answer on skill cards: flags an extraction false positive so
  Applyr permanently stops asking about that candidate and accumulates a learning record for
  future extraction improvements. Supported end to end (UI, API, harness, durable memory).

### Developer
- [CR-109] Migration `022_add_bad_data_answer.sql` adds BAD_DATA to the answer/decision CHECK
  vocabularies via idempotent table rebuild; review answers/skill memory/history remain only
  in the gitignored `data/jobagent.sqlite` (DATA-005, verified via `git check-ignore`).

---

- **Stage 0 improvement plan — 10 improvements (2026-09-01).** All 9 Stage 0
  bugs were previously fixed and verified; this batch covers *improvements*
  (faster, more accurate, better matching), not bug fixes. All 244 existing
  tests pass (80 authoring packet + 152 stage0 fit gate + 12 cascade).
  (1) **Few-shot examples in batch prompt** (`stage0_evidence_cascade.py`):
  expanded the 6-line `_SYSTEM_PROMPT` to include evidence scale 0-4
  definitions, OR-alternative handling, forbidden evidence, and HARD gate
  categories — aligning the batch path with the single-item path's
  `evidence_scale._SYSTEM_PROMPT`. Added k=2 few-shot example retrieval from
  `data/fit_rubric_golden_set.json` in `_build_batch_prompt`.
  (2) **Batched responsibilities exclusion scanner**
  (`build_stage0_fit_gate.py`): `screen_responsibilities_for_exclusion()`
  now batches all non-deterministic responsibility lines into a single
  `classify_requirements_batch()` call when the cascade is enabled, instead
  of one sequential `classify_requirement()` call per line. Eliminates the
  primary cause of 100+ second Stage 0 times on JDs with 8+ responsibilities.
  Falls back to sequential on batch failure.
  (3) **Track 429 failures and skip rate-limited providers** (`utils.py`):
  added `_log_rate_limited()` to log real HTTP 429 responses to
  `activity_log`; `check_rate_limits()` now counts recent RATE_LIMITED
  entries and skips a provider with >3 in the last 5 minutes (configurable
  via `data/llm_rate_limits.json`). Replaced the blocking `time.sleep(60)`
  on RPM approach with `return False` (cascade to next provider).
  (4) **Automatic chunking for batches >24 items**
  (`stage0_evidence_cascade.py`): `classify_requirements_batch()` now
  splits large batches into MAX_BATCH_ITEMS-sized chunks, classifies each
  independently, and merges results. Failed chunks retry items
  individually (partial acceptance) so one bad chunk doesn't discard valid
  results from others.
  (5) **Expanded deterministic exclusion zone regex**
  (`build_stage0_fit_gate.py`): `_DETERMINISTIC_0TO1_BUILD_RE` now catches
  "founding PM", "build from scratch", "greenfield product", "shaping an
  early-stage product area", and "where none previously existed" — common
  exclusion-zone phrasing the original regex missed.
  (6) **TF-IDF-weighted evidence context retrieval** (`evidence_scale.py`):
  `build_evidence_context()` now applies `_rarity_weight()` from
  `jd_tailoring.py` to each overlapping token before computing similarity,
  so a chunk mentioning "roadmap" and "Jira" ranks higher than one
  mentioning "roadmap" and "cooking". Increased k from 6 to 8 for WE
  documents >50K chars. Falls back to unweighted Jaccard if the rarity
  table is unavailable.
  (7) **Deferred fit-score modifiers** (`evidence_scale.py` +
  `fit_rubric_calibration.json`): implemented the repetition modifier
  (+1, capped at 4, when same evidence_level appears 3+ times across
  required items) and the hedge modifier (-1, floored at 0, when reasoning
  contains hedge language like "contributed to" / "partnered on"). Moved
  weights and confidence multipliers from hardcoded constants to
  `data/fit_rubric_calibration.json`. Lowered "low" confidence multiplier
  from 0.65 to 0.5.
  (8) **Anchor-vocabulary matching in specificity scoring**
  (`build_stage0_fit_gate.py`): `_requirement_specificity_score()` now
  adds +1.0 for items containing terms from the anchor vocabulary (claims
  tags + skills catalog), prioritizing specific, decision-bearing
  requirements over generic ones when capping.
  (9) **More stage signal patterns** (`build_stage0_fit_gate.py`):
  `_STAGE_SIGNALS` reordered by priority (enterprise > public > PE-backed >
  VC-backed > startup > unknown) and expanded with bootstrapped, profitable,
  hypergrowth, scale-up, post-Series-B, and employee-count-range patterns.
  (10) **Configurable rate limit thresholds** (`utils.py` +
  `data/llm_rate_limits.json`): thresholds now loaded from a new config
  file at import time, with Claude and Perplexity entries added. Hardcoded
  defaults remain as fallback when the file is absent or a key is missing.

- **Stage 2 parallel PDF compilation + pre-collect findings (2026-09-01).**
  Two optimizations to `scripts/workflow/runner.py` that reduce Stage 2 wall-clock
  time and `--resume` cycle friction without changing any verification gate:
  (1) `_compile_pdfs()` now launches Resume.pdf and CoverLetter.pdf compilation
  in parallel via `subprocess.Popen` instead of sequentially, with a sequential
  fallback if either parallel compile fails (resource-contention recovery);
  (2) when a lightweight Stage 2 subphase (Truth/ATS/HM) returns
  `NEEDS_DISPOSITION`, the orchestrator pre-collects findings from remaining
  lightweight subphases and syncs their dispositions in the same pass, so the
  agent can dispose all WARN findings in one `--resume` cycle instead of one per
  subphase. Mech is not pre-collected (requires PDF compilation). Documentation
  updated in `.claude/skills/generate-submission/SKILL.md`,
  `.codex/skills/generate-submission/SKILL.md`,
  `.claude/workflows/generate-submission-batch.js`, and
  `scripts/stabilization_orchestrator_corpus.py`.

- [DRAFT] **CR-108 Stage 0 evidence cascade and Review Center hardening (2026-08-31).**
  Added the accuracy-first deterministic evidence cascade, batched Groq-to-Gemini
  classification, explicit Local selection, durable Stage 0 checkpoints, and shared
  UI/harness confirmation workflows. The Review Center backend and UI are enabled
  behind the rollout flag. Deterministic Groq and Gemini fixtures cover all 21 active
  CR-093 entries, Python and TypeScript policy normalization is parity-tested,
  checkpoint failure injection and isolated API coverage pass, and evidence promotion
  now waits for exact local source verification. Live provider sampling, archive replay,
  and default cutover remain deferred until the CR-093 release gate is complete.

- **Stage 0-3 observability MVP (2026-08-30/31).** Ahead of replaying `data/submissions/*`
  through Stages 0-3 to find bugs, added the instrumentation designed in
  `docs/spec/08-implementation/OBSERVABILITY-DESIGN-2026-08-30-stage0-3-replay-reporting.md`:
  duration is now captured at the top of each `run_stageN` wrapper in
  `scripts/workflow/runner.py` (not inside `build_receipt`, which only ever runs after a
  stage's real work already finished — confirmed by tracing the actual call sites, not
  assumed); a new append-only `observability/run_events.jsonl` per submission (new
  `scripts/workflow/observability.py`), generalizing the pattern
  `stage1_first_draft/verify_history.json` already proved for Stage 1, with finding-severity
  and disposition-type breakdowns per Stage 2 subphase; a per-opportunity Markdown report
  (`scripts/observability_report.py`, writes `{folder}/observability/report.md`) that degrades
  gracefully for submissions with no recorded events yet; and a compact per-stage console
  summary in `run_submission.py`. Running the report generator against all 15 real submissions
  during development caught a real bug it wasn't looking for: `partner_co`'s
  `truth_findings.json` emits the same finding id twice, which the report now flags explicitly
  as a data-quality warning instead of silently producing a disposition table whose numbers
  didn't add up. Batch reporting (comparing many opportunities at once) and disposition
  causal-attribution are designed but intentionally not built yet — see the design doc's Epic
  E/F. 43/43 test suites pass (`run_all_tests.py`), `tsc --noEmit` clean.

- **Workflow authority audit fixes (2026-08-30).** End-to-end functional audit of
  the submission generation workflow found and fixed 5 defects in the receipt-chain
  system. (1) `run_stage1_validate` was writing the Stage 1 COMPLETE receipt's
  `prior_receipt_id` to the Stage 1 WAITING receipt's ID instead of Stage 0's
  receipt ID, breaking the chain that `check_workflow_complete` verifies — fixed
  to always cite `r0.receipt_id`. (2) `reconcile_state_against_receipts` only
  checked hash freshness, not chain integrity — added a `prior_receipt_id` chain
  check that marks a stage STALE and cascades when its `prior_receipt_id` doesn't
  match the previous stage's current `receipt_id`. (3) Added `--stop-after-mech`
  CLI flag to `run_submission.py` (the parameter existed in the runner but had no
  CLI surface). (4) `--resume --stop-at-waiting` was silently ignored in the
  `else` branch (hardcoded `False`) — now passes `args.stop_at_waiting` through.
  (5) No test verified `check_workflow_complete` returns True on a workflow
  produced by the actual `run_stage1_validate` code path (Stage 3 tests used a
  manual `_seed_stage2_complete` helper that bypassed it) — added
  `EndToEndChainIntegrityTests` class with two tests covering the real code path
  and broken-chain detection after a Stage 0 rerun. Updated the existing
  `test_stage1_complete_chains_and_unlocks_stage2` assertion that validated the
  old broken behavior. 129 Python tests pass.

- **Application hardening audit fixes (2026-08-30).** Comprehensive security and
  reliability audit across all server routes, middleware, services, database
  schema, migrations, and CI/CD. Fixed 6 confirmed defects. (1) `systemRouter`
  had no `requireApiToken` middleware — POST routes (`/api/system-status`,
  `/api/stream/local-model`, log endpoints) were unauthenticated; added
  `router.use(requireApiToken)`. (2) `POST /api/stream/local-model` fetched an
  attacker-controllable URL from DB-stored settings with no protocol
  validation (SSRF) — added `isSafeHttpUrl(baseUrl)` check before fetch. (3)
  Server bound to `0.0.0.0` by default, exposing it to the entire network —
  changed to `127.0.0.1` with `APPLYR_HOST` env var override for Tailscale access.
  (4) FTS5 search endpoint interpolated raw user input into a MATCH query
  string — added double-quote escaping (`"` to `""`) per FTS5 spec. (5)
  `POST /api/jobs/:id/ai-rewrite` accepted unsanitized `:id` (path traversal
  risk) — added `isValidJobId(id)` validation. (6) Migration runner executed
  `db.exec(sql)` and the migration-record insert as separate statements with
  no transaction — a mid-migration failure left the DB in a partial state with
  the migration marked as applied — wrapped both in `db.transaction()`. Added
  13 new tests: `tests/unit/routerAuth.test.ts` (12 tests covering
  `requireApiToken`, `isSafeHttpUrl`, `isValidJobId`) and a migration rollback
  regression test. 336 Vitest tests pass, 129 Python tests pass, `tsc --noEmit`
  clean.

- **CR-107: renamed WAITING_FOR_HUMAN to NEEDS_DISPOSITION (2026-08-30, Jason-directed).** The
  Stage 2 "a WARN finding needs a decision recorded" workflow state was named after the exact
  behavior it should never trigger — an agent reading "WAITING_FOR_HUMAN" has a defensible literal
  reading that it should stop and wait, which directly caused a real incident (a batch left 2 of
  15 submissions stuck there for Jason to find, one with its disposition already written and just
  never re-run). Renamed everywhere it's live code or an enforced test (`scripts/workflow/{runner,
  policy}.py`, `run_submission.py`, `contracts.py`, `stabilization_orchestrator_corpus.py`,
  `test_workflow_authority.py`); `WAITING_FOR_LLM` (a genuinely different, correctly-named state —
  a human really does need to paste an LLM's output back in there) is untouched. `AGENTS.md`'s
  governing rule reframed around "resolve and retry immediately," not "the agent's stop." No
  on-disk `workflow_state.json` held the old value, so this is a pure code/doc rename with no data
  migration. Historical CR docs (CR-079/080/081/096) keep the old name as an accurate record of
  what was true when written. See `docs/spec/05-change-requests/CR-107-needs-disposition-rename.md`.

- **CR-106: interview auto-status, cascade notifications, AI Usage table (2026-08-30).**
  Interview invites now extract a date/time (regex first, Groq LLM fallback, Gemini opt-in) and
  auto-advance the matched job when the current status is eligible — same no-confirm shape as
  rejection auto-close. Free-tier exhaustion writes a real Notifications row instead of a stderr
  print, from either Python or Node, via `GET /api/llm-usage/notifications`. Claude and Perplexity
  now cascade past a 30s `retry-after` the way Groq already did. Settings → AI Usage gained rows
  for the work-experience scoring summary and the document-editor AI rewrite; company research
  stays Gemini-only (it needs live search grounding) and the legacy UI Draft path keeps its own
  per-stage picker. Defaults are unchanged unless you set an override.

- **CR-105: opt-in Gemini fallback for Gmail sync email classification (2026-08-30, Jason-directed).**
  `classifyEmailWithLLM` (`server/services/emailClassifier.ts`) always tries Groq first, unchanged.
  Setting `taskProviderOverrides.email_classification` to `gemini` (Settings → API or Connections →
  AI Usage) now actually works — it adds Gemini as a second attempt only when Groq comes back empty,
  never ahead of it — via a new `server/services/geminiClient.ts` (REST `generateContent`, mirrors
  `scripts/utils.py`'s `_call_gemini` model default). Off by default: this task sees real email
  content and Gemini's free tier trains on submitted data, unlike Groq's, so the fallback stays
  opt-in rather than automatic. Settings UI: the Groq key moved out of its own "Gmail sync" card
  into the main AI providers key table (it's still just an API key, no reason for a separate pill),
  and the AI Usage card's email-classification row now has a real dropdown instead of static text.
  `README.md`'s "Add your LLM provider" and Project-structure sections updated to match (the latter
  was already stale, describing the classifier as "keyword-only, no LLM call" from before Groq was
  added).

- **Removed JobsCollider and We Work Remotely connectors (2026-08-30, Jason-directed).**
  Neither is a source Jason actually uses. Removed from `scoutOrchestrator.ts`'s
  `buildDefaultConnectors()`, deleted `packages/connectors/{jobscollider,weworkremotely}/`,
  and dropped their rows from the `sources` table via migration 017. Also fixed a
  separate, unrelated truncation bug in `scripts/bookmarklet/applyr-job-grabber.js`:
  the LinkedIn/BuiltIn "show more" click was followed by a flat 300ms/200ms
  `setTimeout` before reading the DOM, which could read a still-collapsed JD on a
  slow render with no error — replaced with polling the JD element's text length
  until it stabilizes (same technique the Welcome to the Jungle extractor already
  used), matching the CR-076 workflow's own "no stop in the middle" 8/30 finding.

- **CR-099: safe historical defect baseline (2026-08-24).** Added an opt-in,
  provenance-preserving importer for structured archived first-draft verification
  records. Historical candidates require human confirmation and remain excluded
  from the live CR-097 ledger, example-bank promotion, and post-launch metrics.

- **CR-100: model-independent Stage 0 hard gates (2026-08-25).** Deterministic
  preference exclusions now finish before model-dependent extraction and evidence
  scoring. Obvious no-go roles can be classified even when the local models are
  unavailable, while non-excluded roles remain fail-closed.
- **Stage 0 batch VRAM lifecycle optimization (2026-08-25).** Batch runs can set
  `STAGE0_BATCH_KEEP_ALIVE=1` to retain the final score model until the next
  role's mandatory pre-extraction purge. This removes the redundant end-of-role
  unload while preserving the Qwen/Gemma handoff and single-role default.

# Changelog — Applyr

All notable changes are documented here at the major milestone level.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
System capabilities reference (what the app can do today) is in [PRODUCT_CAPABILITIES.md](./PRODUCT_CAPABILITIES.md) (local only, gitignored).

---

## [Unreleased]

### Changed
- **Stage 0-3 self-report hardening + Stage 0 quality passes (2026-08-28, Jason-supplied — from
  the Applyr Findings & Fixes report's Issues 7-8, plus follow-up items).**
  - `server/submissionFolders.ts`: `reconcileOrphanSubmissionFolders()` and
    `reconcileDraftedJobsWithAssets()` now require `workflow_state.json`'s terminal `status`
    (`COMPLETE`/`COMPLETE_WITH_OVERRIDE`), not just Resume.pdf/CoverLetter.pdf file presence,
    before promoting a folder to a live job. Closes the gap where any tool could get a job marked
    ready by writing two plausible PDFs without the real Truth/ATS/HM/Mech review ever running.
    Legacy folders with no `workflow_state.json` at all keep today's behavior.
  - New shared `Stop` hook (`scripts/hooks/verify_submission_claims.py`) blocks a turn from
    ending on an unverified completion claim about a recently-touched `data/submissions/` folder
    — runs `check_submission_status.py` for real and feeds the actual result back instead of
    trusting the assistant's own words. Wired for both Claude Code (`.claude/settings.json`) and
    Factory.ai's droid (`.factory/hooks.json`, added after Jason confirmed Factory was the tool
    behind a real repeating incident) — the two platforms' Stop events differ (Factory doesn't put
    the assistant's last message in the hook payload; it has to be read from the JSONL
    `transcript_path` instead), so the script auto-detects which shape it's given. Includes its
    own debounce (`data/.stop_hook_debounce.json`, 5 min) as defense-in-depth against a blocking
    loop, independent of whichever anti-loop guard each platform provides. Confirmed live end to
    end in a real Factory droid session, not just tested in isolation: a droid ending its turn on
    a false completion claim against an intentionally-incomplete test folder was blocked, fed the
    real itemized status, and corrected its own report accordingly.
    **Same-day follow-up, found live, not guessed at:** the claim regex originally matched bare
    words ("complete", "finished", "clean") anywhere in the message, and fired repeatedly during a
    real 23-company Stage 0-only triage batch — ordinary "Stage 0 triage complete" / "batch gate
    finished" progress narration kept getting misread as a claim that a specific submission was
    ready, even though nobody claimed that. Tightened to require the claim to actually be about a
    submission/resume/cover letter/application being ready, or an explicit Stage 1-3
    completion/finalize claim — Stage 0 passing is a cheap, frequent, low-stakes event this hook
    was never meant to gate on.
  - `scripts/build_stage0_fit_gate.py`: `screen_responsibilities_for_exclusion()` now runs the
    real classifier on every responsibilities-bucket line (previously pre-filtered by a signal-word
    regex before escalating) — accepted per-JD compute-cost tradeoff for not depending on a
    signal-word list staying complete against novel exclusion phrasing.
  - New requirement-bucket cap (`_cap_requirement_bucket`, `MAX_REQUIREMENT_ITEMS_PER_BUCKET = 12`):
    an outlier JD with an unusually long requirements list now keeps only the highest-scoring
    (most concrete/specific) items per bucket, recorded in `stage0_fit_gate.json`'s new
    `requirements_capped` field.
  - New best-effort `salary_range` capture (`extract_salary_range()`) from raw JD text at Stage 0,
    surfaced in the job detail panel and synced to `jobs.salary_range` (new
    `reconcileStage0SalaryRanges()`) only when a connector's own API-supplied value isn't already
    present.
- **CR-103 ATS retrieval evidence and PDF parser QA (2026-08-27).** Verification now
  separates packet-supported ATS terms from global vocabulary and checks that identity,
  contact, role, employer, date, section, greeting, and sign-off fields survive PDF
  text extraction. Findings remain WARN-only so false positives do not block a real
  submission.
- **Job Search's Location field now takes a country/region preset OR a specific city, in the
  same field (2026-08-26, Jason-supplied — matches how real job boards do it, not two separate
  controls).** Was a fixed `<select>` limited to 5 country-level presets with no way to express
  a specific city at all. First pass made it free text; Jason correctly pushed back — a typo
  ("San Deigo") would silently produce an unmatchable term with no feedback, so it's a `<select>`
  with two `<optgroup>`s instead (`COUNTRY_LOCATIONS`, `CITY_LOCATIONS` — currently just "San
  Diego, CA") in `src/pages/SyncActivityView.tsx`, guaranteeing only known-good values reach the
  server. `resolveLocation()` (`server/domain/jobSearchPrefs.ts`) splits whichever's selected: a
  country preset sets `location_preference` and clears `local_area_terms`; a city sets
  `location_preference: "United States"` (the only case this tool needs today) plus
  `local_area_terms`, expanded via a small `METRO_EXPANSIONS` map so "San Diego, CA" also matches
  Carlsbad/La Jolla/Encinitas/etc. postings that don't literally say "San Diego." Adding a new
  city later means adding it to both `CITY_LOCATIONS` and (optionally) `METRO_EXPANSIONS` — a
  dropdown means that's the only way to change it, by design.
  Removed `local_area_terms` from `PRESERVE_PIPELINE_PREF_KEYS`: it's actively derived from the
  Location field on every save now, so preserving the old value would have silently overwritten
  whatever was just selected. Also had to fix the stored `job_search` profile row directly (DB,
  not code) — it still said "United States" from the old dropdown, which would have made the
  very first Settings save after this shipped wipe San Diego back out. Verified end-to-end
  against the running dev server: selected a value, watched `candidate_preferences.json` update
  correctly, restored the real value after.
  **Broadened to 36 major cities across all 4 supported countries (2026-08-26, Jason-supplied:
  "in case I ship this for public use").** Added a `CITY_COUNTRY` lookup
  (`server/domain/jobSearchPrefs.ts`) so `resolveLocation()` resolves each city's real country
  instead of assuming United States — a UK/Canadian/Australian city would otherwise have been
  silently mislabeled. Verified live: selected "Toronto, ON," confirmed
  `candidate_preferences.json` set `location_preference: "Canada"` (not the old hardcoded US
  default), restored San Diego after. A curated list, not a claim of exhaustive/global
  coverage — extend `CITY_LOCATIONS` and `CITY_COUNTRY` together any time.
- **OpenPostings connector had the same remote-only bug as TheirStack, now fixed
  (2026-08-26).** It hardcoded `&remote=remote` on every query to its own local server,
  so a San Diego-based (non-remote) posting could never surface even after the
  geographic gate learned to accept one. OpenPostings' server already supports a
  `counties` filter; the connector just never used it. Now runs a second pass per
  search term with `counties=<local_area_terms>` when `localAreaTerms` is configured,
  deduped against the remote pass by URL. Wired from `prefs.localAreaTerms` in
  `scoutOrchestrator.ts`, same as the TheirStack fix above. Found while checking
  whether Settings' Job Search options actually reach every connector — worth noting
  the Job Search page (`src/pages/SyncActivityView.tsx`) still has no UI field for a
  local area at all (location is a country-level dropdown only), so this only works
  today because `local_area_terms` was set by a direct data-file edit.
- **CR-102 Stage 1 first-draft quality contract (2026-08-26).** Stage 1 now
  fails on substantive resume/letter repetition, insufficient JD specificity,
  deterministic resume/cover quality failures, defensive disclaimers, and
  missing exact bullet/factual-sentence provenance for rebuilt packets. Added
  corrected Sony/Solace retrieval examples and fixed confirmed false positives
  in audience bleed, ACC-303 attribution, and wrong-company detection. Stage 2
  remains an independent audit.
- **TheirStack connector now runs a remote pass + a local-area pass instead of one unfiltered
  US-wide query (2026-08-26).** Previously `job_title_or` + `job_country_code_or: ['US']` pulled
  every matching US job regardless of work setting, most of which the app's own geographic gate
  discarded after already being billed (TheirStack charges 1 credit per job *returned*). Now
  splits the per-run credit budget across a `workplace_types_or: ['remote']` pass and a
  `job_location_pattern_or` pass using `local_area_terms` (San Diego terms, see below), deduping
  before credits are attributed. Still on the free tier (200 credits/month) — declined the paid
  upgrade (2026-08-26 discussion); this just stops spending free credits on jobs that were never
  going to survive the gate anyway. `createTheirstackConnector` now takes `localAreaTerms`,
  wired from `prefs.localAreaTerms` in `scoutOrchestrator.ts`.
- **New `scripts/expand_openpostings_companies.py` (2026-08-26).** Replaces hand-guessing company
  names from memory (the previous session's approach) with a systematic source: the ~15,800
  Greenhouse/Lever/Ashby board-token lists from
  [Feashliaa/job-board-aggregator](https://github.com/Feashliaa/job-board-aggregator)'s `data/`
  folder (Common-Crawl-harvested, free, no TheirStack credits spent), downloaded to
  `data/archive/ats_company_seed_lists/` (gitignored). For each candidate not already tracked,
  hits the real public board API and only inserts the company if it currently has a live
  posting in the product-manager title family that survives Jason's own
  `blocked_titles`/`blocked_role_titles`/`blocked_focus_area_words`/`blocked_industries` from
  `data/candidate_preferences.json` — a live-relevance filter, not a bulk import, since
  OpenPostings' own sync already can't finish a full pass over ~7,800 companies in one run
  (README.md) and padding that list with irrelevant companies would only dilute it further.
  Also filters obvious non-companies (all-digit tokens — auto-generated trial ATS accounts) and
  boards with under 3 total postings (likely abandoned/demo accounts). Known limitation: the
  industry blocklist catches named categories (crypto, gambling, etc.) but not geography or
  domain fit generally — a foreign or off-domain company with a qualifying title can still get
  added; Applyr's own per-job gates catch that at sync time, so the cost is a diluted company
  list, not a wrong job reaching Jason. Progress is checkpointed
  (`data/archive/ats_company_seed_lists/scan_progress.json`) so runs resume rather than re-scan.
  Re-download the seed lists periodically (see script docstring) to catch newly-added companies.
  **First real batch (2026-08-26): checked 900 candidates (300/ATS), added 80.** Manually
  re-verified all 80 and pruned 32: 22 whose only qualifying hit was bare "program manager"
  (aerospace/defense contractors, nonprofit/government programs, manufacturing NPI, HR/events
  program managers — a generic title collision, not a product role) and 10 the industry/geo
  filter missed by keyword alone (Brazil/Germany/UK-only postings, a Vietnamese mobile-games
  studio, an Avalanche-blockchain company, a staffing agency reposting other employers' jobs).
  Net 48 kept. Removed "program manager" as a standalone qualifying signal in the script
  itself so future runs don't reproduce that 22-company class of noise; the 10 foreign/brand-name
  misses are the documented keyword-matching limitation above and still need a human pass.
- **`local_area_terms` now survives Settings saves (2026-08-26).** The geographic
  gate (`passesGeographicGate`) already supported "remote OR local-area match"
  scoring via `local_area_terms`, but the field wasn't in
  `PRESERVE_PIPELINE_PREF_KEYS`, so a value set outside the (nonexistent) Settings
  UI field would be silently dropped on the next Settings save. Added it to the
  preserve list; `data/candidate_preferences.json` (gitignored, local data) now
  carries a San Diego-area term list so Remote-or-San-Diego roles pass the gate.
  No UI field yet — still requires a direct edit to add/change terms.
- **OpenPostings company-list gap: Greenhouse coverage was 6 companies (2026-08-26).**
  Diagnosed low scout-connector yield for PM/PO roles: OpenPostings' bundled
  `companies` table (~7,748 rows, gitignored local data) skews toward
  Workday/iCIMS/Taleo/UltiPro-style enterprise ATS platforms and had only 6
  Greenhouse-hosted companies tracked, none of them recognizable B2B SaaS names.
  `fetchGreenhouseJobBoard`/`fetchLeverJobBoard` (OpenPostings server) already
  support running a company list against the real public Greenhouse/Lever board
  APIs — no per-search company targeting needed, since OpenPostings searches by
  title across every row in its own list. Verified 44 real, live Greenhouse/Lever
  board tokens for well-known B2B SaaS companies (451 PM/PO/Program Manager
  postings found pre-filter, 265 surviving Jason's title blocklist) and inserted
  them into the local `companies` table. Not tracked in git (`data/archive/` is
  gitignored); a future contributor regenerating that OpenPostings checkout from
  scratch won't inherit this seed and would need to re-add it.
- **Data-infrastructure/data-pipeline company coverage (2026-08-26).** Confirmed
  title-scope matching already treats "Data Product Manager" / "Platform Product
  Manager" / "Infrastructure Product Manager" as in-family via
  `PRODUCT_MANAGER_FAMILY_TITLE` (`shared/domain/gates.ts`) — no search-term
  change needed. The gap was company coverage again: verified and added 11 more
  real, live Greenhouse/Ashby boards for data-infra companies (Fivetran,
  ClickHouse, Hightouch, Cribl, Sigma Computing, Collibra, Cockroach Labs,
  Starburst, Honeycomb, Airbyte, Materialize) — 48 PM/PO/Program Manager
  postings survive the title blocklist across just these, several literally
  "Reverse ETL"/"Data Federation"/"Streaming Platform" titled. Snowflake,
  Confluent, Astronomer, Monte Carlo, Atlan, and Prefect were already present
  (lowercased company_name) but not yet crawled for postings — no insert needed,
  just needs a sync to reach them.
- **Stage 1 packet evidence utilization guard (2026-08-26).** `author_from_packet.py`
  now ranks only claims already selected in an authoring packet by their mapped
  JD importance and soft-gap relevance. Repeatedly mapped high-priority evidence
  must be cited in `claim_provenance.json` before Stage 1 can pass. The guard
  never selects new claims, writes resume content, or changes Stage 0 fit
  decisions.
- **CR-101: pre-draft ATS term contract (2026-08-26).** Authoring packets now
  identify verified JD terms that the packet can support, including deterministic
  skill-anchor excerpts when Stage 0 omitted the relevant line. The Stage 1
  prompt requires those exact terms in `Resume.md`, and verification fails unless
  the resume contains each term and cites a supporting packet claim. ATS review
  remains a backstop rather than the first place predictable term gaps appear.
- **CR-095: completed the WorkExperience story-class claim index (2026-08-24).**
  Added tags-only catalog metadata for the remaining indexable stories, kept
  personal Docker use nonclaimable, regenerated the derived claim sidecar, and
  fixed the packet-budget regression test so it is independent of live bank
  contents. The strict claims audit and full test suite are clean.
- **CR-093 fit-rubric spec is now tracked (`data/fit_rubric_spec.html`, 2026-08-21).** Local leftover `data/*.docx` and `scripts/_bakeoff*.py` are gitignored.
- **`closed-lost` and design-team claims are now WARNs (`LW-036`/`LW-037`, 2026-08-21).** Salesforce Closed Lost is Cision CRM jargon: say lost subscriptions / lost subscription opportunities. Design is not a verified partner. "I designed a formula" still passes.
- **CR-098: no-ai-slop is harness-agnostic (2026-08-21).** First draft is constrained by `author_from_packet.py`'s COVER LETTER VOICE preamble plus two `cover_voice_kicker` bank examples. Check is `LW-033`/`LW-034`/`LW-035` in `submission_linter.py`. Judgment-only Detect lives at `.agents/skills/submission-no-ai-slop/SKILL.md` (Cursor and Antigravity); Claude Code keeps a pointer. Digest budget unchanged.
- **Cover-letter slop: `lives or dies on` is now a WARN (`LW-033`, 2026-08-21).**
  Same class as the intersection-metaphor rule. `multifaceted` joined the
  existing `LW-006` AI-tell list. Sourced from the no-ai-slop catalog after
  the phrase hit multiple letters in one batch.
- **CR-097 Epic 1: first-draft defects are now observable (2026-08-21).** Stage 1
  verify records each attempt to `{folder}/stage1_first_draft/verify_history.json`
  (rule id, category, hashes, digest version) and snapshots Resume.md /
  CoverLetter.md write-once on the first attempt. Re-running verify on unchanged
  bytes does not mint a phantom attempt. This is the data plane the rest of
  CR-097's feedback loop reads; it has standalone value even before the ledger
  and example bank land.
- **CR-097 Epic 2: 2-occurrence trigger is live (2026-08-21).**
  `scripts/scan_authoring_defects.py` writes a gitignored cross-submission ledger
  and opens a pending review when the same targeted category hits 2+ slugs.
  Stage 2 policy calls it advisory-only after COMPLETE (`[defect_scan, status:
  ok|warning]`); `--status` is also on the existing send-batch / every-3-submissions
  sweep. No submission is blocked on a process chore.
- **CR-097 Epic 3: retrieval bank injects into Stage 1 (2026-08-21).** Packets
  carry `learned_examples` (capped, one per category, containment-ranked) and
  `example_bank_version`. Over-budget packets drop examples before shrinking
  WE excerpts. A stale bank version warns; it does not hard-fail the way a
  stale digest does. The bank ships empty until Epic 4 seeds it.
- **CR-097 Epic 4-6 (partial): bank seeded, bleed WARN, report CLI (2026-08-21).**
  `--promote` writes a `few_shot_eligible: false` skeleton; `--decline` needs
  `--note`. Two human-seeded bank entries (gap confession + colon-as-elaboration)
  are eligible. `LW-032` WARNs when a different known company name appears in
  this folder's docs. `--report --last 10` prints the SR-05 split. Story 5.5
  (seed bleed) waits for two real ledger hits; Story 6.2 waits for 10 post-launch
  submissions.
- **CR-096: Stage 1-3 audit remediation, all 6 fixes (2026-08-21).** See
  `docs/spec/05-change-requests/CR-096-stage1-3-audit-remediation.md` for full detail.
  Stage 0 `evidence_scale.py` gains a 4th hard-gate category (`certification`, e.g. a
  required PMP with no honest bridge) and 0-to-1/founding-ownership language in
  `role_exclusion`'s examples. A `gate="HARD"` verdict whose reasoning doesn't share
  real vocabulary with the item it claims to classify gets one retry, then demotes to
  `NONE` with an explicit human-review marker instead of silently finalizing a rejection
  (confirmed real: a citizenship line wrongly Skipped on reasoning about an unrelated
  "regulated industry" line). `stage0_extract.py`'s boilerplate filter (the real default
  extraction path since 2026-08-17, not `build_stage0_fit_gate.py`'s older regex) now
  catches bare salary ranges, recruiter name+email lines, application deadlines, and
  GDPR/sign-off boilerplate that were reaching `required` as fake hire criteria.
  `submission_linter.py`'s LW-028 (attribution vs. ownership-verb) no longer flags a verb
  handed to a different subject via "who"/"that"/"which," and no longer flags an unrelated
  verb sharing a long comma-spliced sentence with an anchor phrase it doesn't describe.
  `build_authoring_packet.py`'s excerpt cap raised 500 → 900 chars with truncation moved
  from a hard character cutoff to the nearest sentence boundary (excerpts no longer end
  mid-word); real measured tradeoff: this cap increase alone re-blocks one real,
  unusually item-heavy JD's 8,000-token packet budget, accepted as a known outlier rather
  than shrinking the cap for every other JD. `authoring_rule_digest.md` gains a final
  self-check section for this round's recurring first-draft mistakes.
- **CR-094: WE-primary authoring (2026-08-20).** Packet excerpts come from
  `workExperience.md` (or `aiProjects.md` for ACC-401), not catalog `text`.
  `claim_constraints` carries OWNED / CONTRIBUTED / DO NOT CLAIM per claim.
  Attribution and DO NOT CLAIM ACC ids are not treated as accomplishments.
  Context pack strips contact/references sections.
- **Stage 0 requirement extraction (2026-08-20):** pinned to `qwen2.5:7b-instruct-q4_K_M`.
  If that model is missing, Ollama is down, or the call returns empty/unparseable output,
  Stage 0 stops and tells you — it no longer silently swaps in the regex extractor or
  another local model.
- **Stage 0 extract is id-only (2026-08-20):** Python cleans HTML and harvests candidate
  lines; Qwen returns integer ids, never JD wording. Copied strings and unknown ids drop.
  This is the extraction-quality fix CR-093 flagged as out of scope (Stripe paragraph-as-item,
  HTML-entity JDs). Regex extract still only runs when `STAGE0_SECTION_MODE=deterministic`.
- **Stage 0 header-hint default (2026-08-20):** unlabeled harvested ids under
  Requirements/Preferred keep that bucket. Qwen's label still wins when present.
  Header labels such as `Required Qualifications:` are skipped using the mature
  section-header list. Culture sentences in required no longer count as extracted
  qualifications for thin-JD / empty-required / Tier-1 cap.
- **Stage 0 score model (2026-08-20):** pinned to `gemma2:2b-instruct-q8_0` (21/21 on the
  golden set, ~3.7GB extra VRAM vs Qwen 7B's 5.6GB at the same accuracy). Stage 0 unloads
  resident models after Qwen extraction and before Gemma scoring so they never share VRAM.
- **Fit-score UI (2026-08-20):** Today / Sync / All Jobs read `skip_floor` / `tier1_floor`
  from `GET /api/fit-thresholds` (`data/fit_rubric_calibration.json`) instead of leftover
  72/80/60 literals. `jobs.score` is reconciled from each folder's `stage0_fit_gate.json`.
- **Empty-required Stage 0 cap (2026-08-20):** a preferred-only JD can no longer be promoted
  to Tier 1 just because preferred items scored at or above 65. Empty required stays Tier 2
  so under-extraction stays visible.
- **Fit floors locked (2026-08-20):** Skip below 40, Tier 1 at 65+. Jason closed CR-093
  Story 3.3. These are the production Stage 0 bands. They are not yet calibrated against
  Applyr interview outcomes. Do not change them without that data or another explicit call.

### Developer
- **CR-094 (2026-08-20):** `scripts/we_acc_index.py` classifies WE ACC ids; packet tests
  assert WE spans over catalog `text`; audit ignores Attribution/DNC brackets;
  context pack strips contact/references headings.
- **Stage 0 id-only extract (2026-08-20):** `scripts/test_stage0_extract.py` plus updated
  `TestSectionExtractionLLM` cover HTML cleanup, harvest ids, long-paragraph split,
  header-hint fill, and drop-unknown-ids. Offline suite stays mocked. Live Qwen re-ran
  on 10 archive JDs after the header-hint default.
- **CR-093 Story 2.7 (2026-08-20):** `test_build_stage0_fit_gate.py` mocks
  `evidence_scale.classify_requirement` so the suite is fast and offline again (~7s).
  Regex-era HARD-tool assertions were rewritten to the evidence-scale contract. Live
  accuracy stays on `data/fit_rubric_golden_set.json`.
- **`batch_pipeline.py` (2026-08-20):** removed leftover evaluate/draft helpers with no live
  callers (`_effective_jd_body`, `get_min_jd_chars_evaluate`, `_jd_meets_evaluate_threshold`,
  `_company_submission_dir`, `_has_required_pdfs`) plus `test_jd_completeness.py`. File keeps
  the keyword gate and backlog-summary helpers.

### Added
- **CR-093: Evidence-scale fit engine (2026-08-19).** Replaces every prior fit-scoring mechanism
  with one: a single LLM judgment per JD requirement line (`scripts/evidence_scale.py`), rating a
  0-4 behaviorally-anchored evidence scale (no evidence → strong direct evidence) against
  retrieval-scoped `workExperience.md` excerpts, gated first by research-grounded hard-gate rules
  (only degree/named-domain-with-years/role-exclusion disqualify — named tools never gate,
  fixing a real miss where a JD was rejected sight-unseen over one Tableau mention), then combined
  by a deterministic weighted formula (`compute_fit_score()`, no second LLM call). Wired into
  `build_stage0_fit_gate.py`'s Step 4/5.5, the sole live Stage 0 gate. Golden-set regression
  (`data/fit_rubric_golden_set.json` + `scripts/check_fit_rubric_golden_set.py`, rewritten for
  this engine) at 20/21, with 21/21 correct on the disqualification-critical dimension across
  every run. Full research, evidence ledger, and pressure-test log:
  `docs/spec/05-change-requests/CR-093-evidence-scale-fit-engine.md`.
- **CR-093: Cutoff-score calibration research (2026-08-19).** The old 70/80 Tier/Skip thresholds
  had no research behind them — confirmed a round number, never checked. Real primary-source
  research (Cascio/Alexander/Barrett 1988's seminal cutoff-score paper, a 2024 standard-setting
  methods comparison, OPM's own admission that job-fit-as-screen-out validity research is "still
  in its infancy," TalentWorks real-outcome data) produced calibrated, explicitly provisional
  bands now living in `data/fit_rubric_calibration.json` — tracked in git on purpose (a
  scoring-engine calibration constant, not a personal job-search preference, so it doesn't belong
  in gitignored `candidate_preferences.json`). `evidence_scale.load_score_bands()` is the sole
  reader.

### Removed
- **The entire old fit-scoring system (CR-093, 2026-08-19).** `scripts/structured_fit.py`,
  `scripts/fit_policy.py`, `scripts/fit_judgment_io.py` deleted outright. `batch_pipeline.py`'s
  `evaluate_job_fit()`/`_call_fit_llm()`/`_call_fit_scoring_only()`/`process_single()`/
  `process_batch()` and its `--mode single|batch` CLI entry point removed — the file is now a
  pure DB/JD helper library, no longer directly executable. The "Find New Jobs" page
  (`src/pages/FindNewJobsView.tsx`, `src/hooks/usePipeline.ts`, the "Add Job" sidebar tab) and its
  `POST /api/evaluate` SSE route (`server/routes/pipeline.ts`) removed — confirmed dead; the real
  authoring flow is `scripts/run_submission.py` from a Claude Code chat session, not this server.
  `candidate_preferences.json`'s `min_fit_score` field, `utils.get_min_fit_score()`/
  `MIN_FIT_SCORE`, and the TypeScript-side `readMinFitScore()`/`DEFAULT_MIN_FIT_SCORE` all removed
  — every remaining consumer was itself part of the deleted system. Associated dead maintenance
  scripts (`re_score_jobs.py`, `regenerate_backlog.py`, `cleanup_pending_backlog.py`) and their
  test-only counterparts (`test_structured_fit.py`, `test_structured_fit_claude_native.py`,
  `test_fit_policy.py`, `test_fit_judgment_io.py`, `test_audit_convergence.py`,
  `test_batch_gate.py`) also deleted — the real, valuable regression each protected (CR-054
  non-convergence transparency) has independent coverage in `test_audit_improve_native.py`,
  unaffected. Verified: `tsc --noEmit` clean, full vitest suite 292/292 passing,
  `run_all_tests.py --python-only` clean apart from one pre-existing, unrelated claims-catalog
  data-drift failure this session never touched (`test_audit_claims_coverage.py`).

### Added
- **Stage 0 numeric fit score (2026-08-18):** `build_stage0_fit_gate.py` now calls the existing CR-053 `structured_fit.evaluate_structured_fit()` scorer on every PASS decision and writes the result into a new `fit_score` field in `stage0_fit_gate.json`, gated on `STAGE0_SECTION_MODE != "deterministic"` so tests stay network-free. `server/submissionFolders.ts`'s `reconcileOrphanSubmissionFolders()` reads that real value via `readStage0FitScore()` instead of hardcoding `score: 80` for every orphan-linked folder — that hardcode is what made every Backlog job in the UI show an identical score. See "structured_fit equivalence schema" fix below for the related scoring-quality bug found while testing this.
- **Advanced-degree unbridgeable hard gap (2026-08-18, Jason-supplied):** A required line naming an advanced degree (PhD/Doctorate/Master's/MBA/JD/MD) with no Bachelor's-or-equivalent-experience alternative and no preferred/plus/bonus hedge is now a HARD gap (`_is_unbridgeable_advanced_degree()`), checked on the whole required-item line before CR-092's compound-clause splitting can break it into context-losing sub-clauses. Real miss: Dassault Systèmes' "PhD, MS, or equivalent in the natural sciences" previously landed as Tier 2 SOFT.
- **PO solo-backlog-ownership signal (2026-08-18, Jason-supplied):** Product Owner postings vary between collaborative-with-engineering (Jason's actual 4 years under the PO title at Cision) and solo backlog ownership with upfront requirements-writing. Stage 0 now surfaces a SOFT `flagged_gaps` entry (routes to Tier 2, never Skip) when a PO-titled JD hits a `po_solo_backlog_flags` phrase (BRD, waterfall, "sole owner of the backlog", etc.) with no collaborative mitigator phrase present ("partner with engineering", etc.). Both lists live in `data/candidate_preferences.json` and are user-editable there directly — added to `PRESERVE_PIPELINE_PREF_KEYS` in `server/domain/jobSearchPrefs.ts` so a Settings save never overwrites them (ADR-005's existing pipeline-tuning-key escape hatch, not a new mechanism). Detection: `_detect_po_solo_backlog_signal()` in `scripts/build_stage0_fit_gate.py`. Tests: `TestPoSoloBacklogSignal` in `scripts/test_build_stage0_fit_gate.py`.
- **CR-092: 9-bug batch fix from a real 9-job CSV run (2026-08-15):** JD-extraction Greenhouse-footer stripping; ground-truth coverage re-keyed by claim lens instead of project_id; robust directory-move fallback for Windows rename `PermissionError`; job-board-mirror company dedup via JD self-identification; tool-name allow-list (`data/skills_catalog.json`) layered on top of the existing deny-list; compound-requirement clause splitting (mechanizes the "Humana finding" prose rule); `claim_provenance.json` existence now gates Stage 1 exit; CSV-import report filename no longer hardcoded/overwriting; a real-corpus regression ratchet test (`test_stage0_extraction_corpus.py`). Full plan + implementation log: `docs/spec/05-change-requests/CR-092-2026-08-15-bug-batch-implementation-plan.md`.
- **CR-091: Stage 0 skip ledger (2026-08-14):** Incoming JDs land in `data/pending_review/`. A Skip is remembered in `stage0_skips` (URL, then company+title) and the folder moves to `data/archive/skipped/`. Only PASS folders are promoted into `data/submissions/`. Next CSV/Sync run does not recreate a skipped posting. Spec: `docs/spec/05-change-requests/CR-091-stage0-skip-ledger.md`. `FR-264`, `AC-326`–`AC-331`. Migration `016_add_stage0_skips.sql` is additive only (`CREATE TABLE IF NOT EXISTS`); it does not ALTER `jobs` or rewrite existing application rows.

### Fixed
- **structured_fit equivalence schema silently degrading every score (2026-08-18):** `_call_equivalence_llm()`'s `response_schema` declared `criteria` as a bare `{"type": "object"}` with no nested shape. Ollama enforces `response_schema` via constrained decoding, so a flat `{criterion: "yes"}` map satisfied it as well as the nested `{judgment, justification}` shape `_normalize_judgments()` expects — every real judgment was silently dropped and defaulted to `"partial"`, producing a uniform ~60/Low-confidence score for every job regardless of real fit. Fixed both layers: schema now declares each of the 5 `CRITERION_WEIGHTS` keys explicitly, and the normalizer also tolerates a flat string value as a defensive fallback. Verified live against 5 real archive JDs: scores went from a uniform 60 to a real 40-92 spread with populated justifications. Affects both the new Stage 0 `fit_score` wiring above and the still-live legacy `batch_pipeline.py` path behind the "Find New Jobs" UI button.
- **Ollama never auto-started for local LLM calls (2026-08-18):** `model_manager.ensure_ollama_running()` was supposed to land alongside the 2026-08-17 "Stage 0 defaults to a local LLM call" change but was missed — every local call silently fell back to the deterministic path on any machine where Ollama wasn't already running, with no attempt to start it. Now checks reachability first and, if unreachable, shells out to `ollama list` (auto-launches the installed background app) and polls until the API responds or a timeout elapses. `scripts/utils.py`'s `_call_local` calls it before selecting a model.
- **Ground-truth coverage / JD-term / linter false positives from a real 2026-08-18 6-company batch:** (1) `check_ground_truth_coverage.py` now checks `claim_provenance.json` first when present — authoritative record of which claim_ids the authoring pass actually cited — before falling back to literal metric/tag text matching, so a genuine paraphrase no longer manufactures a false "unused claim" flag. (2) `jd_term_extractor.py` adds a hand-rolled suffix stemmer for resume/cover-letter-side term matching (JD-side stays exact-literal) so a word-form variant ("Supported" for "Support") counts as covered. (3) `submission_linter.py`'s cross-employer audience-bleed check (`LW-021`) gets a much larger generic-word stopword list and raises its distinctiveness bar to `min_count=3`, after ~50 false positives on ordinary PM/business vocabulary in one session. (4) `import_csv_to_submissions.py` reconfigures stdout/stderr to UTF-8 so a non-ASCII character in a skip-reason string no longer crashes the whole batch on Windows's default console codec.
- **Disabled claims in a ready packet (2026-08-14):** Live `master_claims.json` had no `"disabled": true` on `ACC-114-COST` while packet tests injected that flag, so Nava selected a quarantined $800K / Canadian-ingest lens. Catalog now sets `disabled: true`; `load_claims()` always unions `_QUARANTINED_CLAIM_IDS`; live-catalog test fails if the flag drifts.
- **Playwright sandbox PDF compile (2026-08-14):** Cursor sets `PLAYWRIGHT_BROWSERS_PATH` to `%TEMP%\cursor-sandbox-cache\<hash>\playwright`, which often has no Chromium. `compile_single.py` / `audit_all_submissions.py` now prefer `%USERPROFILE%\AppData\Local\ms-playwright` when that install has a `chromium*` dir.

### Removed
- **`scripts/run_stage0_pending_batch.py`:** Called `build_stage0_fit_gate(..., write=True)` but that function has no `write` argument (08-11 batch report was all `stage0_error`). Unused. Canonical batch path remains `python scripts/build_stage0_fit_gate.py … --batch-table`.

### Added
- **CR-089 (proposed):** Stage 0 extraction precision — false Tier 1s, Ad Tech in JD body, people-mgmt phrasing, benefits scraped as requirements. Tracker only; no extractor rewrite in this send.

### Fixed
- **Recruiting-slogan job titles (2026-08-11):** Compugroup landed as `Create the future of e-health together with us by becoming a Product Manager`; Pinterest II Content Compliance as a qualifications bullet (`Proven ability to lead…`). `is_implausible_job_title` now rejects slogans / qual lines / >10-word titles; bare `lead` no longer counts as a role word; extractor pulls embedded `Product Manager` or a Workday/Greenhouse URL slug. Same rules mirrored in `server/submissionFolders.ts` `readJdMeta`.
- **DOCX bullets collapsed into paragraphs (2026-08-11):** `compile_single.py` already inserted a blank line before `* `/`- ` lists for the PDF path (Python-Markdown), but Pandoc DOCX still read the raw `.md`. Location lines glued to bullets became one Word paragraph with a literal asterisk. DOCX now compiles the same preprocessed markdown as the PDF.
- **LR-031 B2B SaaS summary HARD_BLOCK (2026-08-11):** Promoted former WARN `LW-013` to Mech HARD_BLOCK `LR-031`. Resume Professional Summary (subtitle or body) may not say "B2B SaaS" unless `Original_JD.txt` itself uses "SaaS". Stops the recurring default opener ("7 years of B2B SaaS platform experience") on non-SaaS roles. Authoring digest updated; experience bullets still allowed to describe Cision as B2B SaaS when true.
- **Identity chrome + closer hygiene (2026-08-11):** Post-finalize audit found SDSU education, Senior Cision titles, wrong employer date ranges, undersold "four years," and stacked "I would welcome" closers on COMPLETE packs. Mech now HARD_BLOCKs via LR-013 (widened), LR-028 (National University education), LR-029 (employer header chrome), LR-030 (duplicate welcome closers). CL-012 accepts "chance to"; batch repair merges thanks in-place instead of stacking a second template. Batch/force Stage 2 no longer auto-disposes HM findings. Swept 30 COMPLETE folders, recompiled PDFs, reminted receipts. Plan: `docs/superpowers/plans/2026-08-11-identity-chrome-and-closer-hygiene.md`.
- **Finalize title chrome (2026-08-11):** Stage 0 `extract_job_title_line` was taking the first short JD line, so LeafLink finalized as `The Role` and Camunda as `Register Here!`. Extraction now skips section headers/CTAs and falls back to the first embedded Product Manager/Owner span; `is_implausible_job_title` blocks Stage 3 / `finalize_submission_job` / `check_finalize_ready` from writing that chrome (not `--force`-bypassable). Same junk filter applied in `server/submissionFolders.ts` `readJdMeta`. Live rows corrected; regression tests in `test_extract_job_title_line.py`.
- **Workday false positive in LR-026 (2026-08-11):** `\bworkday\b` matched capacity phrasing (`workday-hours` / `workday hours`) and blocked PDF compile on neogen/precisepk/procede. `blocked_tools` now excludes the hours-compound form while still catching the Workday HCM product.
- **Workflow integrity hardening (2026-08-11):** Three Type A/B control-plane gaps closed without redesign. (1) Stage 2 dispositions are now bound to per-phase findings content hashes (`reviews/dispositions.json` → `bound_findings_hashes`); regenerating the same finding id with different payload clears the old disposition so Stage 2 cannot COMPLETE on a stale FALSE_POSITIVE. (2) `contracts.check_workflow_complete()` now verifies receipt_id digests, `prior_receipt_id` chain continuity, state↔receipt pointers, and on-disk `output_hashes` freshness (was existence-only despite "fresh hashes" docs). (3) `finalize_submission_job.py` refuses direct DB finalize for workflow-adopted folders lacking an orchestrator-issued Stage 2 COMPLETE receipt (legacy non-adopted folders unchanged; `--force` still overrides). Regression tests in `test_workflow_authority.py` / `test_stage_gate.py`.
- **Stage 0 skills-catalog false anchors (2026-08-11):** `skills_catalog.json` entries like `Microsoft Teams` / `Google Suite` were whitespace-split into bare vocab words (`microsoft`, `suite`), which falsely marked `Microsoft Office Suite` as grounded. Stage 1 then fail-closed with an unmapped required item (Central Bank). Skills catalog now contributes full phrases plus slash/colon/comma components only — no whitespace word-split. Claim-tag word-split unchanged. Central Bank packet rebuild → ready.
- **Stabilization corpus pass (2026-08-11):** 20-JD Stage 0+packet pressure test. Fixed: (1) shared `scripts/blocked_tools.py` for Stage 0 + LR-026 (Amplitude/Procore/Smartsheet drift closed); (2) `teams` added to Stage 0 generic anchor words; (3) Zoom Total Direct Compensation / apply-window + navigate-ambiguity boilerplate filtered; (4) familiarity intensifiers must modify the hedge prefix — trailing `strong plus` no longer HARD-Skips Familiarity-with-Amplitude (Seed Health); (5) preferred Stage-0 soft gaps get honesty bridges when claim scoring returns empty (LeafLink marketplace). Report: `data/reports/stabilization_corpus_2026-08-11.json`.
- **Stage 1 exit ↔ packet Rule 7 parity (2026-08-11):** `--verify-only` optimization_bar no longer fails soft gaps that have empty `claim_ids` but an explicit honesty/bridge note (same rule packet Rule 7 already used). Closes the central_bank / camunda / LeafLink packet-ready-but-Stage-1-fail loop. Also: workflow entry points refuse silent practice↔production mode drift unless `force=True`; Microsoft Office / Google Workspace lines force-empty with a non-claimable honesty bridge.
- **Quality pass on Stage 2 blockers (2026-08-11):** ncontracts Sterkly bullet now carries honest ACC-202 Agile scoping (U.S./Israel/India) with provenance aligned to live Resume.md; leaflink gained grounded `claim_provenance.json` + summary first-person fix; camunda got a fresh non-templated rubric (82/88), honest GTM/governance/workflow keyword adds, Visible still omitted (VOC). Practice Stage 2 COMPLETE: ncontracts, leaflink, camunda, central_bank.
- **Evidence map best-match guards (2026-08-10):** Pressure test on 10 live folders showed lexical Top-2 picking the wrong story: Smartsheet/Power BI → `ACC-120`/`ACC-401` via shared word `tools`; Procore → `ACC-101` platform proxies; Bachelor's and compensation boilerplate getting claim_ids. Fixes in `build_authoring_packet.py`: denylist `tool`/`tools`/`tooling`; force empty `claim_ids` + honesty bridge when the line names a Stage-0 hard-blocked tool, a satisfied Bachelor's/undergrad degree, or compensation/pay boilerplate (required row kept — never dropped); soft_gaps inherit that bridge so Rule 7 / `--verify-only` accept honest empties. Stage 0 hard-tool list gains `procore` / `smartsheet` / `monday.com`. Bachelor's detector also accepts `Bachelor's or Master's degree`. AI capability boost no longer substring-matches `ai` inside `training`/`email` (which, after the tools denylist, tied unrelated claims at +12000 ahead of ACC-120). Real AI lines still boost ACC-120.
- **Stage 0 monitor fixes (2026-08-10):** After re-batching 54 folders: (1) drop/culture-route Acushnet CTA/benefits + Realtime `WHAT SETS YOU APART?` / `WHAT IS IN IT FOR YOU?`; (2) `Undergraduate degree` admin-satisfied like Bachelor's; (3) soft-skill fluff denylist (`Dependable, accountable…`); (4) plain `Familiarity with` hard-blocked tools → SOFT Tier 2 (not Skip) so unconfirmed tool exposure stays draftable — intensified `deep/strong/hands-on` still HARD; (5) empty `required` cannot be Tier 1 (preferred-only → Tier 2). Camunda Docker/K8s familiarity returns to Tier 2.
- **Stage 0 mixed-bucket recovery (2026-08-10):** When a JD dumps duties and requirements into one list (no separate Required header), `required` stayed empty and Stage 0 looked falsely clean. Recovery now runs only when `required` is empty: duty-verb lines stay in responsibilities; years/degree/qual lead-ins move to required; leading `Bonus:` to preferred. Also added mid-JD quals headers (`WHAT DO YOU NEED?`, `Ideal Candidate Profile`, `Your Key Strengths`) and fixed culture header company-prefix under `re.I` (was matching "Strong opinions about AI" as a fake About-header). Eval on 54 live folders: empty-req-with-resp dropped to 1 (Elevance — real duties, quals already in preferred). SDL/Camunda/Paylocity/Realtime/Shazam/Acushnet/Neogen now split correctly.
- **Stage 0 extractor remediations from 54-submission batch (2026-08-10):** Measured failures on live `data/submissions/*` — (1) bare `Required:` never matched (`requirements?` ≠ `required`), so Deloitte-class JDs extracted empty; (2) missing headers (`Work you'll do`, `The Key Responsibilities`, `Roles and Responsibilities`, `Knowledge, Skills, and Abilities`, `Experience and Qualifications`, Ready-Net `About Your Role` / `A Bit About You`, RealTime all-caps `WHAT ARE WE LOOKING FOR?` / `WHAT WILL YOU BE DOING?`, `About {Company}`); (3) leading `Bonus: … Braze …` stayed in required and hard-Skipped Seed Health — now routes to preferred so preferred tool mentions cannot Skip; (4) boilerplate/orphan soft-gap noise (E-Verify, pay notes, hybrid-policy blurbs, `Your Qualifications`, benefits headers); (5) thin career-page stubs / empty JD files (Netradyne, Principal URL-only, `test_co`) now Skip as `thin_incomplete` instead of false Tier 1 or extraction_empty Tier 2. Tests added in `test_build_stage0_fit_gate.py`.
- **CR-088: master_claims catalog hygiene (2026-08-10):** Claim-construction standard (`data/CLAIMS_STANDARD.md`); `skills_catalog.json` gains Pendo/Productboard/Zoom/Airtable (ACC-119 stays skills-path, no claim lens); cleared stale `UNVERIFIED_PROJECT_IDS` for ACC-111/113/115; filled attribution/prohibited on ACC-204 + ACC-111-SCOPE; `scripts/audit_claims_coverage.py` (ERROR: mis-key/phantom/WE-unclaimed; WARN: high-risk field gaps; ACC-401 side corpus + ACC-119 allowlist). Spec: `CR-088-master-claims-catalog-hygiene.md`. Session-007 R18. ACC-101-RETENTION mis-key was fixed earlier by Claude Code (not duplicated).
- **CR-087: item-overlap precision (2026-08-10):** Camunda "equip team for epics" mapped to `ACC-120-AIRESEARCH` because overlap scored the generic token `team` at 1000pts (from tag "Cross-Team Learning"), and zero-overlap claims could still fill Top-2 via full-JD `jd_score` alone. `_score_claims_for_item` now ignores a denylist of generic tokens and forces `total=0` when distinctive overlap and capability_boost are both zero. Live Camunda rebuild: epics line → `[]` (not ACC-120); AI items still boost ACC-120. Packet eval **30/35 → 28/35** (accepted precision tradeoff — prior hits were often jd_score stuffing). Spec: `CR-087-item-overlap-precision.md`. Session-007.
- **CR-086: Stage0 extraction-noise filter (2026-08-10):** Mid-JD headers like `Job Responsibilities` / `Our Core Values` / `Work Environment / Physical Requirements` were captured as *required items* and scored into the authoring packet (AMN Healthcare: office/ADA/pay boilerplate pulled ACC-120/ACC-113/etc.). Expanded section-header + ignore-header patterns; denylisted physical/ADA/final-pay lines; orphan-header allowlist as belt-and-suspenders (not generic Title-Case — that false-positived on skill list items). Packet eval should-surface held at **30/35 (85.7%)**; AMN packet **4259→2072** tokens with header rows gone. Spec: `docs/spec/05-change-requests/CR-086-stage0-extraction-noise-filter.md`. Session-007. Camunda lexical FPs on *real* responsibility lines deferred (scoring signal).

### Added
- **CR-084: Stage 3 finalize under orchestrator (in progress, 2026-08-09):** Explicit `--finalize` wraps `finalize_submission_job.finalize`; mints `stage_receipts/stage3.json`; sets `COMPLETE` / `COMPLETE_WITH_OVERRIDE` / `PRACTICE_COMPLETE`. Practice skips DB. Tests: 27. Spec: `CR-084-stage3-finalize-orchestrator.md`. `FR-263`, `AC-321`–`AC-325`. Unblocks Claude CR-078 finalize/status cutover.
- **CR-081: HM + final mech + Stage 2 receipt (in progress, 2026-08-09):** 2C HM (lint + `hm.critical_read`), 2D compile+`verify_one`, 2E `check_stage2_ready` → `stage_receipts/stage2.json` COMPLETE + Stage 3 READY. Tests: 24. Spec: `CR-081-hm-mech-stage2-receipt.md`. `FR-262`, `AC-316`–`AC-320`.
- **CR-080: ATS / AI review Stage 2B (in progress, 2026-08-09):** After Truth COMPLETE, orchestrator runs `jd_term_extractor`, writes `reviews/ats_findings.json`, same disposition model; PASS → ats COMPLETE + hm READY. `--stop-after-truth` skips ATS. Tests: 22. Spec: `CR-080-ats-ai-review.md`. `FR-261`, `AC-312`–`AC-315`.
- **CR-079: Truth / Evidence review Stage 2A (in progress, 2026-08-09):** After Stage 1 COMPLETE, orchestrator runs claim_provenance + ground_truth_coverage, writes `reviews/truth_findings.json`, stubs `reviews/dispositions.json`, policy → `WAITING_FOR_HUMAN` or truth COMPLETE + ats READY. No `stage_receipts/stage2.json` yet (CR-081). `--stop-after-stage1` skips Truth. Tests: 20 in `test_workflow_authority.py`. Spec: `docs/spec/05-change-requests/CR-079-truth-evidence-review.md`. `FR-260`, `AC-307`–`AC-311`.
- **CR-077: Receipt chaining + hash invalidation (in progress, 2026-08-09):** After `WAITING_FOR_LLM`, when Resume.md + CoverLetter.md exist, orchestrator runs `author_from_packet.run_verify_only` + `check_stage1_ready`, writes Stage 1 `COMPLETE` receipt (prior_receipt_id chain), unlocks Stage 2 `READY` only. `reconcile_state_against_receipts` marks STALE + locks downstream on hash mismatch. CLI `--resume` / default continue past waiting when docs present; `--stop-at-waiting` preserves CR-076 stop. Tests expanded in `test_workflow_authority.py` (15). Spec: `docs/spec/05-change-requests/CR-077-receipt-chaining-hash-invalidation.md`. `FR-258`, `AC-294`–`AC-298`.
- **CR-076: Workflow authority foundation (in progress, 2026-08-09):** `scripts/run_submission.py` + `scripts/workflow/` (sole writer of `workflow_state.json` / `stage_receipts/`). Wraps existing Stage 0/packet/prompt workers; CR-075 gates stay live underneath. Vertical slice: Stage 0 → packet/prompt → `WAITING_FOR_LLM`. `contracts.check_workflow_complete()` is the DONE oracle (full COMPLETE in later CRs). Adopt path for existing folders. Tests: `scripts/test_workflow_authority.py`. Spec: `docs/spec/05-change-requests/CR-076-workflow-authority-foundation.md`. `FR-257`, `AC-289`–`AC-293`. Claude Code spot-check accepted (session-006 R6); no blockers.
- **Round 4 draft optimization bar (fail-closed, 2026-08-07):** Stage 1 done-criteria is strongest honest soft-gap bridge, not rubric 70/65. `authoring_rule_digest.md` §1b; Stage 0 soft-flags domain-qualified preferreds (e.g. banking+compliance) even when capability tags match; packet `soft_gaps[].claim_ids` + compliance-primary claim scoring; `author_from_packet.py --verify-only` fails when soft_gap/required claim_ids are unused in `claim_provenance.json`; empty-bucket Stage 0/packet fail-closed; `test_build_stage0_fit_gate` / `test_build_authoring_packet` / `test_author_from_packet` registered in `run_all_tests.py`. Central Bank rebuilt as proof (ACC-107 bridge, Stage 2 COMPLETE).
- **CR-075: Stage 0-2 completion gates & verification lineage — Implemented** (2026-08-07): Extends the Stage-3-only `check_finalize_ready` pattern to Stages 0-2 via `check_stage1_ready` / `check_stage2_ready` + `scripts/stage_gate.py` (`apply_stage2_verdict`, `--force` override log at `data/.force_override_log.json`; Stage 2 requires `--force-reason`). Verification receipts gain `content_hashes` (sha256); `check_freshness` is hash-aware with mtime fallback for legacy receipts. `claim_provenance.py` in Required Verification (WARN-tier). Batch workflow `authorPrompt()` on CR-074 packet path + company-count guard (≤3 without opt-in). `FR-256`, `AC-278`–`AC-288`. Tracker: `docs/spec/08-implementation/CR-075-stage-completion-gates-epics.md` (done).
- **CR-074: token-conscious authoring packet — Implemented** (2026-08-06): Deterministic Stage 0, lean `authoring_packet.json` (≤8k), ~1.6k-token rule digest, one cloud draft (~4k input vs ~100–150k old path), scripts-first Stage 2. Calibration: Limble + Camunda + Paylocity all `--verify-only` PASS + send-ready Y (Ncontracts skipped). `generate-submission` v2.1.0; AGENTS.md/CLAUDE.md cut over. Epic 8 (local assists) deferred. Report: `docs/reports/cr074-calibration-report.md`. `FR-252`–`FR-255`, `NFR-007`.

### Changed
- **Doc/skill cutover to `run_submission.py` (2026-08-09):** `CLAUDE.md`/`AGENTS.md` Required Verification + Processing-JDs paragraph, `.cursor/rules/generate-submission.mdc`, `generate-submission` SKILL Stage 2 ladder / Required Verification, batch workflow `whenToUse`+Finalize, README scripts map — all point at the orchestrator as the default completion path. CR-074 workers stay; direct CLI prints a stderr note via `workflow/entry_warning.py`. Historical CR-074/075 specs unchanged (history).
- **`conversion_rubric.md` threshold language:** “Stop improving” / “ready to send at CONVERT-READY” replaced with floor + strongest-GT done criteria (aligned with Round 4 optimization bar).
- **`build_authoring_packet.py` exit contract (CR-075):** missing/invalid `stage0_fit_gate.json` now exits non-zero unless `--force` (logged). Other non-gate error paths still exit 0 (CR-074 behavior preserved).
- **Required Verification (CLAUDE.md / AGENTS.md):** canonical path is `run_submission.py` / `--resume` / `--finalize`; workers (`verify_submission`, coverage, jd terms, claim_provenance) remain under Mech / debug only.

### Fixed
- **Gmail rejection sync (CR-072): dry-run had no off switch, and the classifier missed most real-world rejection phrasing (2026-08-10):** Two distinct problems. (1) `gmail_sync_dry_run` defaults to `true` on any missing/unreadable profiles row (by design — fail closed on a fresh install), but nothing ever called `setDryRunEnabled()` — no route, no Settings UI — so every real rejection detection since CR-072 shipped just logged a `[DRY RUN] would close job as Rejected` line and never wrote the job status. Flipped off via direct profile write; still no in-app toggle if it needs revisiting. (2) Even with real writes on, `emailClassifier.ts`'s keyword classifier missed most genuine rejections against a full mailbox sweep, for three separate reasons: HTML-only emails (no `text/plain` MIME part — common for Workday/iCIMS-style senders) fell back to Gmail's ~200-char `snippet`, which never reaches the actual decision sentence (`extractSubjectAndBody` now also extracts and tag-strips `text/html` when no plain-text part exists); real emails render curly apostrophes (`’`, U+2019) while `REJECTION_PHRASES` used straight ones (`'`), so phrases like `"we've decided not to move forward"` never matched real mail (added quote/whitespace normalization before matching, which also fixes phrases split across a hard-wrapped line's `\n`); and several common real templates ("position has now been filled," "focusing our search on other candidates," "will not move you forward in the hiring process," "have not been selected for the position," etc.) simply weren't in the phrase list at all. Verified against the full 221-message `Applyr/Incoming` label post-fix: 0 new false positives (checked against Gmail's own `Applyr/Rejected` label as ground truth), 19 previously-silent rejections backfilled to real job status through the normal `applyJobStatusUpdate` path. One unrelated job-matcher bug surfaced in the process and was **not** fixed: `matchJobForEmail`'s whole-word company match paired a RealPage rejection email (body text says "Product Manager (Remote)") with an unrelated job whose own `company` field is literally `"Remote"` (an upstream data-quality issue) — excluded from the backfill rather than reinforced.
- **`jobMatcher.ts`: ATS/job-board platform names treated as employer identities caused correct rejection classifications to still land on no match (2026-08-10):** A real Principal rejection classified correctly as `'rejection'` but `matchJobForEmail` still returned `null` — it found 3 candidate jobs, not 1, and (correctly, per its own ambiguity guard) refused to guess. Two of the three were never real employer matches: a `company: "LinkedIn"` row (a leftover "Auto Apply" placeholder, no JD text, never applied to) and a `company: "ICIMS"` row (Stage-0-rejected, never applied to, score 0 — the scraper had picked up the ATS *vendor* badge off a LinkedIn listing instead of the real employer). Both normalize to common words that show up as routine boilerplate in nearly any iCIMS-relayed ATS email (`tracking.icims.com` links, a "follow us on LinkedIn" footer icon) — so this wasn't Principal-specific, it silently blocked matching for any iCIMS-routed rejection with a LinkedIn footer icon. The real employer behind the "ICIMS" row is unknown and wasn't fabricated; instead added `NON_COMPANY_PLATFORM_NAMES`, a small denylist of known ATS/job-board vendor names (iCIMS, LinkedIn, Indeed, Greenhouse, Lever, Workday, Ashby, SmartRecruiters, Taleo, Workable, Breezy, BambooHR, Jobvite, SuccessFactors, Paylocity) excluded from every match stage — a platform name is never a legitimate employer signal, whether via domain, exact text, or fuzzy match. Verified against the full mailbox: 0 regressions on already-correct matches, and the same fix independently unblocked 5 other previously-silent rejections (Vector Solutions, IntegriChain, HealthEdge, Pluralsight, SentiLink) that had hit the identical collision. Principal + Pluralsight backfilled from `Applied` to `Closed`/`Rejected` through the normal sync path; the other 4 were already `Closed` and just gained real `outcome_notes`.
- **`finalize_submission_job.py` company-only UPDATE clobbered a different posting (2026-08-07):** Thermo Fisher Digital PM finalize matched the Closed Gas Analyzers row by company name, retitled it, and left the Builtin URL. Prefer URL match; only update a single company row when status is still `Backlog`/`Drafted` and URL is empty or equal; otherwise insert. UPDATE also writes `url`/`jd_text` when provided.
- **Stage 0 quals-bucket ATS boilerplate bleed (2026-08-07):** after `What we're looking for`, Pinterest-style `Relocation Statement` / Inclusion / salary / `#LI-` tails were ingested as required items → fake soft gaps. `_extract_sections` now ends on ignore-headers (end-anchored) + item denylist; eval on 408 archive/live JDs via `scripts/eval_stage0_boilerplate.py` (confidence_gate PASS).
 `.claude/workflows/generate-submission-batch.js` `authorPrompt()` now builds/uses `authoring_packet.json` + `authoring_rule_digest.md` instead of `agent_context_pack.md`/full `CLAUDE.md`; refuses >3 companies unless `allowLargeBatch` opt-in — the incident class that burned a 5-hour allocation on a 12-company unattended run.
- **Resume name rendered ALL CAPS by the PDF compiler regardless of source casing (2026-08-05):** `compile_single.py`'s CSS applied `text-transform: uppercase` to the `h1` selector (the candidate's name heading), so PDF text-extraction always read "JASON TAYLOR" no matter how the name was typed in `Resume.md` — a known ATS name-entity-recognition gotcha (an all-caps run reads as an acronym/header, not a proper name), and the recurring reason Jason had to manually correct his parsed name on submission portals. Removed the transform from `h1` only; `h2` (section headers like "PROFESSIONAL EXPERIENCE") keeps it, since that's expected/harmless there.
- **`spearheaded` simultaneously banned and trusted in `submission_linter.py` (2026-08-05):** `LW-006`'s AI-tell buzzword pattern banned it, while `_OWNERSHIP_VERBS_METRIC` (the attribution-fidelity check) treated its presence as high-confidence evidence a claim was genuinely owned — two rules giving opposite verdicts on the same word. Removed it from the banned pattern; kept it in the ownership-verb list, cross-referenced with a comment in both places so a future edit to one doesn't silently reintroduce the contradiction.
- **Silent Sync auto-draft disabled (2026-08-04):** Sync's EVALUATE stage no longer starts Ollama or runs `batch_pipeline.py --mode batch`, which had been silently generating Resume/CoverLetter PDFs outside `generate-submission`. Replaced with a deterministic export of gate-passed Drafted JDs to `data/pending_review/{slug}_{id8}/Original_JD.txt` (idempotent via new `jobs.exported_for_review_at` column, migration 013). Also removed the dead Sync "Draft Assets" button and `POST /api/jobs/:id/draft` route. **Still live (flagged, not changed):** `POST /api/evaluate` via Find New Jobs (`usePipeline`) still spawns `batch_pipeline.py --mode single`.
- **Years-experience gate wired at ingest with +2 buffer (2026-08-04):** `passesYearsExperienceGate` now runs in `scoutOrchestrator` alongside title/industry/geo. Rejects only when a clearly extractable required-years value exceeds `experience_range.max + 2` (currently 8 → ceiling 10). Ambiguous/unparseable years pass through for Stage 0. Extracted separately from `passesSeniorityGate` so title-blocklist is not double-applied.
### Added
- **`jobs.status_changed_at` (migration 015) + new vocabulary gap fixes in `submission_linter.py` (2026-08-05):** added `status_changed_at`, stamped in `jobStatusService.ts`'s `applyJobStatusUpdate()` only when status actually changes (not on every call), enabling a real elapsed-time-since-rejection calculation that didn't exist before (`created_at` alone only says when a row was first scouted, not when it was later rejected). Feeds the Stage 0 reapply cooldown described in the Changed section below. Also added `paramount`, `foster(ed)`, `showcas(e/es/ing)` to `LW-006`'s banned-buzzword pattern in `submission_linter.py` — confirmed missing via grep against current (2026) recruiter AI-detection research, not already covered by the existing list.
- **`LW-028`: claim-attribution vs. ownership-verb mismatch check in `submission_linter.py` (2026-08-04, prompted by reading an external "ATS/AI Resume Alignment Pass" template Jason was evaluating for adoption):** the template's "seniority signals" section (distinguish true ownership from participation) surfaced a real gap rather than something already covered — `master_claims.json` already tags 10 of 67 claims with `attribution: "contributed"`/`"influenced"`, and CLAUDE.md hand-writes the ACC-120 exception ("never say 'I built' or 'I designed'"), but nothing mechanically checked a drafted bullet's verb against any claim's actual tag except that one hand-remembered instance. New `check_attribution_verb_strength()` cross-references bullets/sentences against every tagged claim via metric co-occurrence (8 of 9 claims) or curated anchor phrases (ACC-120, which has no metric). Deliberately excludes "led"/"drove"/"owned"/"designed"/"established" from the general verb list — each produced a real false positive when tested against the live catalog (e.g. `ACC-101-ANCHOR`'s legitimately-owned "Owned and stabilized a $40M ARR platform..." shares its $40M/3,500 metrics with the `contributed`-tagged `ACC-101-RETENTION` churn claim). Metric matching also needed an alnum-boundary check, not substring containment — the bare-digit variant of `7%` ("7") was substring-matching inside "700" and cross-flagging an unrelated claim. WARN-tier, matching `LW-021`/`LW-026`'s tolerance for a heuristic requiring judgment on read. Verified zero false positives across every real folder in `data/submissions/`, and confirmed it fires correctly on synthetic true-positive text. Rest of the source template (parseability review, JD-term extraction, terminology alignment, evidence-strength/readability rubric) was found to duplicate existing mechanisms (`compile_single.py`'s fixed template, `jd_term_extractor.py`, `conversion_rubric.md`, `submission-no-ai-slop`) and wasn't adopted.
- **CR-073: `pdftotext` reading-order regression guard + `jd_literal_term_gaps` check in `verify_submission.py` (2026-08-04):** originated from a research pass on ATS/AI screening failure modes, cross-checked against the real pipeline before building anything — most proposed mitigations (native `.docx` output, font/column whitelisting, a general eligibility gate) turned out to already be solved by the Playwright HTML→PDF architecture or by `generate-submission` Stage 0. Two gaps survived the check: (1) added `_check_reading_order()` — confirms `##` section headings extract via `pdftotext -layout` in the same order as the source Markdown, a standing regression guard for a suspected CORE COMPETENCIES-as-`<table>` risk that direct testing found isn't actually live in current output (the real generator emits bold-label + comma text, not a Markdown table); (2) new `scripts/jd_term_extractor.py` diffs Jason's real skill/tool vocabulary (`data/skills_catalog.json` + `data/master_claims_tags_only.json`'s tags, minus a small hand-tuned soft-skill exclusion list) against each specific JD's text and the drafted documents — distinct from the existing `jd_keyword_coverage` field's static 14-word generic list, and from `check_ground_truth_coverage.py`'s unused-claims check (this flags unmatched literal JD terms instead). Both new receipt fields (`reading_order`, `jd_literal_term_gaps`) are WARN-level, excluded from `mechanically_verified`. Same-day follow-up (Jason-prompted, asking whether the keyword logic should also apply to cover letters): answer was no — cover letters aren't an ATS-parsed keyword-matching target and stuffing JD vocabulary into one risks `LW-011`/`LW-012` — but the question exposed a real bug: the check originally pooled resume + cover letter into one coverage pass, so a term mentioned only in the cover letter's prose was silently credited as "covered," masking a real resume-side gap. Fixed: `jd_literal_term_gaps` now reports `missing_from_resume` (the actionable signal) separately from `cover_letter_only_mentions` (informational, never counts as coverage). Verified against all 14 real folders in `data/submissions/` both before and after the fix — zero regressions. See [CR-073](docs/spec/05-change-requests/CR-073-ats-parseability-term-coverage.md).

### Fixed
- **`reconcileActiveSubmissionFolders()` deleted in-progress Stage 0 fit-gate folders on server startup (2026-08-03, found live):** `generate-submission/SKILL.md` Stage 0 step 5 has an agent persist `stage0_fit_gate.json` + `Original_JD.txt` in a submission folder ahead of drafting, as a deliberate hold point between triage and authoring. But `reconcileActiveSubmissionFolders()` (`server/submissionFolders.ts`, called on every `server/index.ts` startup) treated any folder with no PDFs and no `jobs` row as an orphan stub and `fs.rmSync`'d it — exactly the shape a Stage-0-only folder has. Five real Tier 2 fit-gate folders (Velosio, Bellese Technologies, TriVoca Health, TraceGains, Tata Consultancy Services) were deleted this way the first time the dev server restarted mid-batch. Nothing was unrecoverable (the JD text lives in the source CSV, the fit-gate content was still in a scratch file and the conversation), but it shouldn't have happened. Added `hasStage0FitGate()` and exempted folders carrying that file from the orphan-stub sweep. Verified live: recreated the five folders, restarted the dev server, confirmed all five survived (no `removed=` entries in the `[FR-030]` startup log this time).

### Changed
- **"No web research, any stage, any purpose" split into a scoped exception (2026-08-06, Jason-supplied, per the planning doc's Round 5):** Stage 0's fit decision (REJECT/PASS) still never touches research — that boundary is unchanged and for the same reason (a high-stakes call is exactly when the temptation to search is strongest). Stage 1 cover-letter drafting now may call one small, sourced fact via `research-engine.py --hook-fact` (new CLI mode) for Tier 1 fits and `Reach Out`-tagged Tier 2 fits only — never pasted verbatim, always bridged fresh, never for plain Tier 2. `research-engine.py`'s `fetch_company_intel()` (the older, fuller company-intel path) is now Gemini-primary rather than trying Perplexity first — a deliberate choice, not the previous implicit fallback-when-Perplexity-unconfigured behavior. Live-tested against a real company (Stripe): returns a dated, sourced fact correctly; one known limitation — the source URL can land on a generic page (e.g. a newsroom homepage) rather than a deep link, so treat a non-specific citation with more skepticism than a precise one. `generate-submission/SKILL.md` top-level rule + Stage 0.5 (defensive reading extended to research content) + Stage 1 step 5.
- **`Research_Packet_Contract.md` (the old six-module company dossier) un-retired, narrowly, for interview prep only (2026-08-06):** it was built assuming a ~25% response rate; at the real current rate it's only worth the token cost once an interview is actually scheduled, not at draft time. Restored from `archive/rules/` to live `.agent/rules/` with an updated banner scoping it to that one on-demand use, wired to run before `generate_cheat_sheet.py` (which already expected `Research_Packet.json` to exist and silently skipped a rich cheat sheet without it — the missing link was that nothing called the fetch). `.agent/DEPRECATED.md` updated to match.
- **Stage 0's DB reapply check refined from a blanket rule to a rejection-type + time-gated one (2026-08-05, Jason-supplied, per the 2026-08-05 planning doc's Round 4):** the original rule (2026-07-20) treated any prior `Rejected`/`Closed` row identically, regardless of whether the company actually evaluated the application or it was simply never reviewed. `jobs.rejection_type` (populated by the Gmail-sync classifier) already distinguishes these — `Ghosted`/`No Longer Available`/unset get a 30-day cooldown, `Rejected`/`Domain Mismatch`/`Title Ceiling`/`Unfit`/`Mismatch` get 120 days. Rows past cooldown route to Tier 2 (flagged as a re-apply, not silently redrafted) instead of staying auto-rejected forever. `Self-Rejected` is the one exception, and deliberately the strictest, not the most lenient: **permanently blocked, no cooldown clears it** (corrected same day — first draft of this rule had it backwards) — Jason rejecting it himself means he had a reason, unlike the other categories where the reason for no signal is ambiguous. See `.claude/skills/generate-submission/SKILL.md` Stage 0 step 0.
- **Stage 0 required-item gaps now classified hard vs. soft, not treated uniformly (2026-08-05, Jason-supplied):** a zero-anchor gap on a literal, named, ATS-string-matchable requirement (a specific tool/platform/certification) is now treated the same as a clear unhedged mismatch — REJECT by default, flagged distinctly so Jason can override toward outreach-only pursuit for a standout fit. A zero-anchor gap on a domain/industry descriptor or transferable methodology stays the existing flagged-gap/Tier-2/honest-bridge path. Reasoning: research found a cold application can't be rescued by a transferable-skill narrative against a literal keyword filter, but a human reader reached through warm outreach can still be persuaded. `.claude/skills/generate-submission/SKILL.md` Stage 0 step 2/3.
- **Resume subtitle title-mirroring boundary clarified (2026-08-05, Jason-supplied):** mirror the JD's base role title when honest (exact-title-match research shows a real callback-rate effect), but never adopt its domain/industry qualifier unless genuinely backed by real experience — same overclaim class as the existing "Data Enrichment" rule, just applied to titles specifically. `CLAUDE.md`/`AGENTS.md` Required Document Structure section.
- **`Reach Out` tagging extended to strong-bridge Tier 2 fits, not just clean Tier 1 (2026-08-05, Jason-supplied):** research indicates a cold, keyword-filtered application can't rescue a hard-requirement gap (an ATS filter never reads the transferable-skill bridge), but warm outreach can — making a convincing-bridge Tier 2 stretch fit the profile where outreach matters most, not least. `.claude/skills/generate-submission/SKILL.md` Stage 0/Stage 3.
- **"Junior" removed from the title blocklist (2026-08-03, Jason-prompted):** `data/candidate_preferences.json`'s `blocked_role_titles` (the list `scripts/seniority_gate.py`'s `title_blocked()` actually gates against — a preserved pipeline key, not overwritten by Settings-UI saves) and the legacy `blocked_titles` field both had "Junior" removed. Surfaced when a Stage 0 batch triage skipped HiredBuddy's "Junior Product Manager" posting on this exact term.
- **Color-consistency pass: semantic warning/success tokens added, remaining raw Tailwind colors swept to tokens, dead Tailwind v3 config removed (2026-08-02, Jason-prompted: "I saw some color in some areas that didn't look consistently applied"):** audited every component for color usage that bypassed the token system. Found two root causes rather than isolated typos: (1) `tailwind.config.mjs` still carried a full `theme.extend.colors` block from before the project moved to Tailwind v4's CSS-native `@theme` — with no `@config` directive linking it back in, it was silently dead (any edit there had zero effect) and also stale (missing `status-new`/`status-drafted`, added to `index.css` after the config file was last touched). Deleted it. (2) The token system had no semantic slot for "warning" or "success" — every component that needed a caution or good/connected signal reached for raw `amber-*`/`emerald-*` and picked its own shade by eye: 7 different amber combinations across `DocumentEditor.tsx`, `AllJobsView.tsx`, `SyncActivityView.tsx`, `TuningLogView.tsx`, `JobDetailPanel.tsx`, and `StatusChip.tsx`, plus emerald used for "success" in `SettingsView.tsx`'s 6 connection badges, `SyncActivityView.tsx`'s live log, and `TodayView.tsx`'s funnel bar — while `status-offer` already had a vetted, contrast-checked green sitting unused. Added `--color-warning`/`-dim`/`-container`/`-on-container` and the equivalent `--color-success` set to `index.css` for both themes: warning values match the amber already used most often (so the swap is visually a no-op, not a new look); success reuses `status-offer`'s exact already-vetted values rather than inventing a third green, so "success" now means one hue app-wide instead of two. Swapped every raw-color instance to the new tokens, including `JobDetailPanel.tsx`'s outcome-type selector (`Rejected`/`Ghosted`/`No Longer Available`/`Self-Rejected`), which had hand-coded `slate-100 dark:slate-800`/`amber-100 dark:amber-900` with manual `dark:` variants — the exact pattern the original "Rejected/Closed stay neutral" design rule (see the color-palette-rebuild entry further below) was supposed to prevent, just missed in a component that predated the token system reaching it; now uses `status-closed-*`/`warning-container` and drops the manual dark variants entirely since tokens already auto-switch via the `.dark` class. Also caught and fixed along the way: a self-inflicted PostCSS parse error (a comment containing the literal substring `amber-*/emerald-*` closed early on the embedded `*/`, silently invalidating everything after it in the file — reworded to `amber-* / emerald-*`), the WARN log-level color in both `SyncActivityView.tsx`'s and `JobDetailPanel.tsx`'s activity-log renderers (was `text-secondary-container`, a light blue nearly indistinguishable from the default/INFO color one branch below it — now `text-warning-container`, consistent with the amber semantics established everywhere else), and a native-scrollbar contrast bug Jason spotted live in a screenshot (the main browser window scrollbar isn't covered by the app's own `.applyr-scrollbar` class, which only themes a few inner panels — with no `color-scheme` hint, the browser fell back to the OS default, which follows the Windows accent color and rendered as a blue thumb against the coral/indigo dark palette; added `color-scheme: light` / `.dark { color-scheme: dark }` so the browser paints its native chrome, including that scrollbar, in the correct palette). Verified throughout via the running dev server: computed-style checks confirmed the new tokens resolve to the intended hex values in both themes on real rendered elements (Settings connection badges, Tuning Log notice box), and a final repo-wide grep confirmed zero remaining `bg|text|border-{tailwind-color}-{shade}` instances in `src/`.
- **Light mode repivoted a second and third time to an indigo/blue reference screenshot; sidebar rebuilt as a fixed dark-navy rail (2026-08-02, was sitting uncommitted in the working tree before this session — captured here from the reasoning already left in `index.css`'s own comments, not written from firsthand context):** per those comments, Jason pointed at a social-listening-dashboard screenshot (dark navy icon rail, light blue-gray canvas, white cards, indigo-blue accent, green/red/amber status signal) and asked light mode to move closer to it, superseding the Claude-coral identity documented in the "Primary accent" entry below; dark mode was explicitly kept out of scope and left as it was. Light `@theme` primary → indigo `#3B5FE0` (was coral `#D97757`), secondary → cyan `#0EA5E9` (was deep teal), canvas → light blue-gray `#EEF1F7` (was white), status chips retinted to match. A third same-day pass corrected several values against an exact hex-mapping table Jason supplied against the reference screenshot (`primary` refined from an initial `#3457D9` approximation, card border corrected to `#E4E8F1`, status-drafted amber corrected to a bolder `#F5B301` fill since the original pastel pairing was too light to read as text). New `--color-sidebar-*` token set (`bg`/`container`/`border`/`hover`/`active`/`text`/`text-active`) added at the top level of `index.css`, outside the `.dark` block, so the rail stays a fixed dark navy in both themes rather than following the page's own light/dark toggle — matching the reference screenshot's icon rail, which does the same. `Sidebar.tsx` rewired to consume it (brand mark replaced with an inline SVG using the new indigo, nav items and the account-menu footer switched from the general `surface`/`primary`/`outline` tokens to the sidebar-specific ones), superseding the still-general-token sidebar design documented in the "Sidebar restructured to match Linear" entry below. Also bundled in the same uncommitted state: `AllJobsView.tsx` gained a dismissible "N new roles from your last scout" banner (now using `status-drafted` tokens per this session's consistency pass above) and a left-border fit-score accent on each job row (`border-l-primary` ≥80, `border-l-secondary` ≥60, `border-l-outline-variant` below). Compiled and smoke-tested live via the dev server during this session's own verification pass; the design reasoning behind the indigo repivot and the new banner/accent features themselves predates this conversation and isn't independently verified here beyond "it builds and renders."
- **"Rejected" → "Archived" in every user-facing label (2026-08-02, Jason-prompted: "let's replace rejected with archived"):** display-only rename, deliberately not a data migration — `rejection_type: 'Rejected'` stays the actual stored value in `jobagent.sqlite` and the API payload (`JobDetailPanel.tsx`'s closure picker still POSTs `'Rejected'`), only the rendered text changed. Kept the app's own established pattern for this (`StatusChip.tsx` already decoupled internal value from display label for this exact status, e.g. `'Not a fit'`) rather than inventing a new one, and avoided a real-data migration risk on Jason's actual 287-application history. Four spots: the closure-outcome button label (`JobDetailPanel.tsx`, was `label: 'Rejected'`), `StatusChip`'s `long` mode (`status/StatusChip.tsx`) which previously rendered the *raw* status string when `job.status` itself was the legacy unnormalized `'Rejected'` value (server-side `crud.ts` normalizes `Rejected`+`rejection_type` to `Closed` on the common path, but the raw value can still reach the UI) — now intercepted so that path can never leak the word either — and two spots in `SettingsView.tsx`'s Analytics tab: the stat tile label and the "How they ended" breakdown, which was rendering `row.rejection_type` verbatim. Also dropped the "Archived" stat tile's leftover `text-error` (red) styling to the neutral `text-on-surface-variant` already used by the "Ghosted" tile next to it — same color-neutrality rule as the rest of the day's work, just a spot that had been missed. **Deliberately not touched:** `Self-Rejected` (a distinct concept — the candidate's own decision, not the company's, so it doesn't carry the same sting the rest of this session has been designing against) and `"Marked as 'Rejected'"` in `SyncActivityView.tsx` (a different "rejected" entirely — the automated scout/gate pipeline rejecting a job *posting* from the queue, unrelated to a company rejecting Jason's application). General descriptive prose containing the word ("Where rejections happened," "where rejections landed") was left as-is — scoped this to the status label itself, not a copy-editing pass; flag it if you want that softened too.
- **Light mode restructured around the real Google Store's card/canvas relationship (2026-08-02, Jason-prompted with two google.com/store screenshots):** the earlier light-mode pass made canvas the off-white tier (`#F8FAFC`) and cards pure white — Google's actual pattern is the opposite: white canvas, cards/containers tinted with Google's own literal gray scale. Inverted `src/index.css`'s light `@theme` block to match: `surface` (canvas) → `#FFFFFF` (was `#F8FAFC`), `surface-container-lowest` (cards) → `#F1F3F4` (was `#FFFFFF`), through `#F8F9FA`/`#E8EAED`/`#DADCE0` for the remaining tiers — all Google's own real values, not approximations. `on-surface-variant` → `#5F6368` and `outline`/`outline-variant` → `#9AA0A6`/`#BDC1C6`, also Google's actual text/border grays. Verified live: card-vs-border contrast improved to 1.63:1 (was 1.05:1 canvas-vs-card in the previous pass). `.btn-secondary` restyled to match the reference's "Learn more" button specifically: outlined rounded-full pill, neutral `text-on-surface` instead of colored `text-primary`, `bg-surface` instead of a filled tonal background — cascades to every existing `.btn-secondary` usage (Cheat sheet, Details, Mark as Applied variants, etc.) with no per-instance changes needed. `.glass-nav`'s light-mode backdrop color updated to match the new white canvas. Scoped to light mode only, and to card/button structure specifically — did not attempt to replicate the reference's marketing-hero pastel-tile treatment, since Applyr has no equivalent hero/marketing content type for it to apply to.
- **Sidebar restructured to match Linear's actual product UI, not just its marketing-site colors (2026-08-02, Jason-prompted with a screenshot of the real Linear app):** the earlier dark-mode research pulled colors from linear.app's marketing site; this pass looked at a screenshot of the real product instead, which is structurally flatter than what Applyr had. Two changes in `Sidebar.tsx`: (1) sidebar background changed from `bg-surface-container-low` to `bg-surface` — same tone as the main canvas, no tonal split, separated only by a real `border-r border-outline-variant` (verified live: `sidebarMatchesCanvas: true`). (2) Active nav item changed from a left-side `border-r-2` bar + flat `bg-surface-container` fill to a full rounded border ring (`border-primary/30 bg-primary/10`), closer to the contained-chip selection style shown in the reference; inactive items now use `border-transparent` that reveals `border-outline-variant` on hover rather than only a text-color change. Scoped to the sidebar only — the header's distinct `glass-nav` band, the empty-state illustration style, and the ghost-icon toolbar buttons visible in the same reference screenshot were noticed but not touched, since none were specifically called out and each is a larger, separable change.
- **Primary accent: Electric Cobalt → Claude Coral (2026-08-02, Jason-prompted: "that blue doesn't look right, stick closer to claude"):** swapped `--color-primary` and its dependent tokens (`primary-dim`, `primary-container`, `on-primary-container`, `surface-tint`, `inverse-primary`) from `#2563EB` to `#D97757` — Claude.ai's actual accent, confirmed live via `getComputedStyle` during the dark-mode research pass, reused unchanged across both Applyr themes since that's what Claude itself does (same value in their light and dark UI). Verified live: brand-icon-vs-canvas contrast 6.2:1 in dark mode, 3.0:1 in light; white text on the coral fill sits at 3.1:1, matching how Claude's own buttons use white text on this exact color. Deliberately scoped to the accent only — the cool-neutral surface base stays as-is rather than also adopting Claude's warm canvas, since that would re-touch the "not cozy, not home" reasoning behind the palette work earlier the same day; an accent pop reads differently than a warm background wash. Status chip hues (the per-pipeline-stage system: teal/blue/green/cyan/amber/neutral) were left alone — `status-core`'s blue was never tied to the primary/brand token, it's an independent categorical color, so it didn't need to move just because the brand accent did. `tailwind.config.mjs` resynced to match.

### Added
- **Dark mode (2026-08-02, Jason-prompted, modeled on Linear + Claude.ai's real dark UIs):** researched both live in-browser rather than guessing from memory — extracted actual computed colors via `getComputedStyle`. Linear: cool near-black canvas (`#08090A`), brand accent purple reused unchanged across light/dark, elevation via small lightness steps rather than shadow, borders mostly solid or low-alpha white. Claude.ai: warm `#201F1F` canvas, warm off-white text, coral `#D97757` accent. Took Linear's structural approach — cool near-black base, lightness-step elevation, real (not decorative) borders — and kept Applyr's own cobalt/teal identity rather than importing Claude's warm coral, since going warm would have partly undone the "not home, not cozy" decision from the palette work earlier the same day. Implementation: `@custom-variant dark (&:where(.dark, .dark *))` in `src/index.css`, a `.dark { }` block redefining every `--color-*` custom property Tailwind's utilities already reference (no component code changes needed for anything token-based — Dashboard, Opportunities, Settings, and Job Search all inherited correctly for free, verified live in-browser across all three), a FOUC-prevention inline script in `index.html` that reads `localStorage['applyr-theme']` (falling back to `prefers-color-scheme`) and sets the `dark` class before first paint, and a toggle switch in `Sidebar.tsx`'s account menu that flips the class and persists the choice. Same status-chip rules as light mode carried forward unchanged: Rejected/Closed stay neutral (not red), Offer stays a scarce accent, `error` stays reserved for real system errors. Two real passes, not one: the first dark token set measured out to the *same* low-contrast bug already fixed once in light mode that day (card-vs-canvas border at only 1.25:1) — re-verified numerically in-browser and widened the border to 1.57:1 (2.39:1 for the stronger/hover outline) before treating it as done; canvas-vs-card *background* contrast landing near 1.1-1.2:1 was left alone once confirmed that's what Linear's own real site measures too (WCAG contrast is a text-legibility metric, not a surface-separation one — near black, a real border does the separating work, not raw luminance delta). Also added `dark:` variants to the handful of spots still using Tailwind's static color scale instead of Applyr's tokens (the closure-outcome buttons in `JobDetailPanel.tsx`, the Offer bar's `bg-emerald-600` in `TodayView.tsx`), since those don't respond to CSS-variable overrides. **Known gap, not fixed here:** `DocumentEditor.tsx`'s Toast UI Editor only imports the light theme CSS (`toastui-editor.css`); a `toastui-editor-dark.css` already exists in `node_modules` but wiring a conditional/dynamic stylesheet swap for a third-party editor is a distinct follow-up, not part of this pass. Internal low-opacity section dividers (`border-outline-variant/10`-style, e.g. in `SettingsView.tsx`, `SyncActivityView.tsx`) were left as-is, consistent with the same scope boundary drawn during the light-mode contrast fix earlier that day — they were already faint by design in light mode, not a regression introduced here.

### Changed
- **Palette revised again same day — low-contrast tokens replaced with a higher-contrast "utility SaaS" base, plus real bugs the first pass didn't catch (2026-08-02, Jason-prompted after an external color-contrast critique he brought from Gemini):** the first neutral-palette pass (below) was itself too washed out — measured live: card-vs-page background contrast was only 1.1:1, and the funnel chart's non-zero bars rendered at `bg-primary-container/50` (50% opacity) or a `/20`-opacity gray for zero states, both nearly invisible against a white card. Root-caused two real bugs, not just muted color choices: (1) `.card-applyr` and the shared `.editorial-shadow` class (used for nearly every card across Dashboard/Opportunities/Job Search/Tuning Log) had **no actual border** — `.card-applyr:hover` set a `border-color` with no `border-width` anywhere, so it painted nothing even on hover; several job-row cards in `TodayView.tsx`, `AllJobsView.tsx`, and `TuningLogView.tsx` used `border-transparent hover:border-outline-variant/10`, i.e. genuinely zero separation until the pointer was already on the card. (2) The Application Progress bar chart in `TodayView.tsx` only ever gave one series (`i===2`, Screening) a solid fill; every other non-zero bar rendered at 50% opacity and zero-state bars at 20% opacity — with Jason's real data at 0 Screening/Interviews/Offers, nearly the entire chart was rendering in its faintest state. Fixed: added `border border-outline-variant` directly to the shared `.editorial-shadow`/`.card-applyr` classes and replaced every transparent-until-hover card border with a visible one; chart bars now render solid (`bg-primary` for active series, `bg-emerald-600` reserved for the Offers series specifically — kept separate from Applyr's own `secondary` teal so it stays the one true "you got an offer" signal — `bg-outline-variant` at full opacity for zero states), and the chart's dashed gridlines went from 10%- to full-opacity `border-outline-variant`. On top of the bug fixes, retuned the base tokens themselves to Gemini's "Deep Slate & Electric Cobalt" direction rather than its "Terminal Analytics" (emerald-primary) option — the latter would have made green the everyday action color and undone the "Offer stays a scarce accent" rule from the first pass. New tokens in `tailwind.config.mjs`/`src/index.css`: primary → Electric Cobalt (`#2563EB`, was `#45566E`), secondary → deep teal (`#0F766E`, was `#3E6B66`), canvas → `#F8FAFC` (was `#F5F6F8`), body text → near-black `#0F172A` (was `#2B2E33`), true-error red → `#DC2626` (was the deliberately desaturated `#A13A3A` — real system errors should look urgent; only job-rejection status stays de-alarmed, per the rule below). Status chip tints deepened to match (e.g. Applied `#CCFBF1`/`#115E59`, was `#D2E6E2`/`#1F3B37`) so pills read as distinct against the page instead of blending in. The "Rejected stays neutral, not red" and "green stays scarce" rules from the first pass both carried forward unchanged — this revision is a contrast/visibility fix layered on top, not a reversal of the emotional-design reasoning.
- **Color palette rebuilt around emotional neutrality, not comfort (2026-08-02, Jason-prompted):** Applyr's original tokens (sage green primary, terracotta secondary, warm stone tertiary, cream-paper surfaces, clay-red error) were a deliberately cozy, domestic palette — the actual problem, once named: a tool that delivers rejection emails shouldn't feel like home, because that lets rejection read as personal instead of just a status update. The fix isn't "make it cold" (true clinical/hospital white-and-gray was considered and rejected — it risks reading as unfeeling right when support matters most); it's "make it neutral," closer to a productivity tool (Linear, Notion) than either a spa or a hospital. Rebuilt `tailwind.config.mjs` and `src/index.css`'s design tokens onto the same Material-3 slot structure with new hue families: primary → slate blue (`#45566E`), secondary → muted teal (`#3E6B66`), tertiary → cool slate gray (`#5B6270`), surfaces → cool off-white (`#F5F6F8`). The load-bearing change is status semantics, not just hue: **`Rejected` moved out of the red/error color family entirely** and now shares the same flat neutral slate as `Closed` — `StatusChip.tsx` already did this for the read-only pipeline chip; extended the same logic to the closure-outcome buttons in `JobDetailPanel.tsx`, which still used `bg-error`/`bg-error-container` for both `Rejected` and `Ghosted`. A closed application is a status, not a system failure, so it gets no alarm color; `error`/`on-error` tokens stay reserved for genuine app errors. Green (`Offer`) stays a scarce, single accent so it still reads as a real signal instead of ambient decoration. Also fixed leftover hardcoded old-palette hex values the token swap alone wouldn't have caught: `.glass-nav` background and shadow `rgba()` values in `index.css`, the scrollbar-thumb color, and `index.html`'s hardcoded `bg-[#faf9f6] text-[#303330]` body classes.
- **Sidebar brand mark: meditation icon → briefcase (2026-08-02, Jason-prompted):** the Material Symbols `spa` icon (a lotus/flower glyph) next to the "Applyr" wordmark in `Sidebar.tsx` read as a wellness/meditation app rather than a tool for actively working a job search — flagged directly by Jason after seeing it rendered in the nav. Swapped to `work` (briefcase). Also reworded `index.html`'s meta description off "serene, editorial... mindful career pursuit" (the same cozy/passive instinct as the old palette) to plain language about running the search as a system.

### Removed
- **"Rerank Backlog" semantic search (TodayView):** removed the search input + button on the Ready to Apply pipeline list, along with the `/api/jobs/rerank` route and `scripts/rerank_backlog.py` it called. The feature never refreshed the job list after reranking, so it had no visible effect once triggered.

### Fixed
- **`mergeSubmissionFolder()` silent overwrite risk (2026-07-31, Jason-prompted):** `reconcileActiveSubmissionFolders()` archives any `data/submissions/{company}` folder whose linked DB job row isn't `Backlog`/`Drafted`, matching purely by company-name slug with no concept of "same posting" vs "different posting, same company." Found live: two same-day fresh drafts (Snapsheet, Tenna) got auto-archived mid-session because both companies already had a `Closed`/`Applied` row from a real prior cycle, merging into archive folders that already held genuine historical files (`Interview_Cheat_Sheet.md`, `Research_Packet.pdf`) — and `mergeSubmissionFolder`'s `fs.copyFileSync` overwrote any same-named file (`Resume.md`, `CoverLetter.md`) with zero warning. In this specific case the archived drafts turned out to be the same postings Jason had already applied to (confirmed via exact URL match for Tenna, same title/company/ATS for Snapsheet), so the archiving itself was correct — but the overwrite mechanism had no way to know that and would have silently destroyed genuinely different content just as easily. Fixed: before overwriting an existing destination file with different content, `mergeSubmissionFolder` now preserves the old version as `{name}.bak-{timestamp}`. Verified in an isolated scratch-directory test (not against real submission data). Does not fix the deeper one-folder-per-company architecture question — just guarantees nothing real disappears without a trace while that's still true.

### Added
- **`scripts/check_ground_truth_coverage.py` (2026-07-31, Jason-prompted):** cross-references every claim's tags in `master_claims_tags_only.json` against a target JD, flags claims whose metrics/tags never appear anywhere in `Resume.md`/`CoverLetter.md`, writes `ground_truth_coverage.json`. Built after the "ask whether ground truth exists unused" instruction in `generate-submission/SKILL.md` Stage 2 point 1 (already written down once, after the Bazaarvoice dry run) recurred as a real miss on a 10-submission real batch, caught by Jason, not by the prose — same failure class the self-repair protocol already names for `LR-016` (a written rule that didn't survive drafting pressure and had to become a mechanical check). It's a heuristic, not an oracle: freshly-authored bullets don't always contain a claim's literal tag words, so it produces real false positives (confirmed on this batch — 2 of 4 flagged misses on one company turned out to already be covered, just phrased differently) and needs each flag checked against the actual document, not blind-forced in. Wired into Stage 2 and the Required Verification section of `generate-submission/SKILL.md` and `CLAUDE.md`/`AGENTS.md` as a required command alongside `verify_submission.py`. Run retroactively against all 10 folders in the batch that prompted it, per the self-repair protocol's rule that a new mechanical check doesn't apply itself backward automatically.
- **`ACC-117-PENDO` and `ACC-121-SQLFOOTPRINT` added to `master_claims.json` (2026-07-31):** while building the coverage script above, found `ACC-117` (Pendo/product-analytics — documented in `workExperience.md`'s own Approved Accomplishments Inventory) had no entry in `master_claims.json` at all, meaning it was invisible to the tag-scan retrieval step `generate-submission` Stage 1 instructs authors to use. Also found `MET-09` (~200 SQL databases managed, `workExperience.md` Section 4) had never been elevated to a discoverable claim either, despite being real, verified, and directly relevant to most platform/API/data-heavy JDs — added as `ACC-121-SQLFOOTPRINT`, phrased as "queried and navigated," never "designed," per the existing DO-NOT-CLAIM on data modeling/schema authorship.

### Found, not yet resolved
- **`master_claims.json` contains project_ids with no backing narrative in `workExperience.md` (2026-07-31):** `ACC-111` (dual-platform ownership, ~38 enterprise accounts on a secondary legacy platform), `ACC-113` (PR-attribution-tool reverse-engineering rebuild), and `ACC-115` (migration-requirements design) all have specific, plausible-sounding accomplishment text in the claims catalog with zero corresponding entry in `workExperience.md`'s Approved Accomplishments Inventory — backwards from the documented architecture, where `workExperience.md` is supposed to be the source of truth and `master_claims.json` a tags-only index into it. `check_ground_truth_coverage.py` treats all three as `UNVERIFIED` and never surfaces them as usable evidence regardless of tag overlap. Needs Jason's call on whether these are real (an omission in `workExperience.md`, needs a proper write-up there) or stale/superseded (should be marked `disabled`) before anything gets built on them.

### Changed
- **`CLAUDE.md`/`AGENTS.md` slimmed (2026-07-30):** 428 lines / 6,585 words down to 368 lines / 5,658 words (~14% smaller), with zero rule, threshold, code table, or schema removed — verified by diffing every `MET-`/`ACC-`/`LR-`/`LW-`/`CR-`/`R-`/`CW-`/`H-`/`FR-` identifier before and after the edit. Root `CLAUDE.md` auto-loads on every touch of this repo regardless of which skill is active (confirmed live in-session: it loaded unprompted mid-networking-outreach-skill work), so its size is a fixed tax paid by every session, not just resume-batch ones — a per-skill `AGENTS.md` was considered and rejected for this reason, since it wouldn't reduce what auto-loads and would add a second place for rules to drift out of sync. Two moves: (1) "Active Engineering Work" (86 lines of engineering-only CR status, already excluded from `data/agent_context_pack.md`'s digest for the same reason) compressed into a table of current-state one-liners with pointers to the full tracker docs, which remain the source of truth. (2) Inline incident narrative trimmed throughout (dates, company names, "found on X after Y" backstory) to short pointers, keeping every operative rule, rule ID, hard-block/warn status, and example trigger phrase intact — narrative that duplicated `CHANGELOG.md` (confirmed exact duplication on the `no-ai-slop` integration entry) was cut hardest. `AGENTS.md` resynced byte-identical after.

### Added
- **`networking-outreach` skill (2026-07-30):** new `.claude/skills/networking-outreach/SKILL.md`, built after two drafts of a CivicPlus contact-outreach message missed the mark in the same session (first version too soft with no concrete ask, second overcorrected to a referral ask with zero relationship framing) — the pattern needed writing down instead of re-deriving each time. Covers two contact types with different message structures: a hiring-manager/role-relevant contact (existing "I saw the role and thought it might be a good fit" pattern) versus an unrelated-department warm connection like an alum or former coworker, who can't evaluate PM fit and needs a different ask (referral or a pointer to the right person, sequenced after a genuine relationship-anchoring line). Grounded in independent web research on referral effectiveness (referred candidates get ~5x more interviews, hired ~55% faster) and warm-vs-cold outreach reply-rate benchmarks, on top of an initial Perplexity pass Jason supplied — sources cited in the skill file, with a caveat that the specific benchmark percentages come from recruiting-tool marketing blogs and should be treated as directional, not precise.

### Added
- **`no-ai-slop` skill integration:** installed the [petergyang/no-ai-slop](https://github.com/petergyang/no-ai-slop) writing skill globally (`~/.claude/skills/no-ai-slop`) and diffed its AI-slop pattern catalog against `submission_linter.py`'s existing `LR`/`LW` rules for genuine gaps. Added six new `WARN` rules: `LW-015` (throat-clearing openers), `LW-016` (faux-insight/rhetorical setups), `LW-017` (importance puffery), `LW-018` (weasel attribution), `LW-019` (fake-strong hub-verb, e.g. "serves as a centralized hub"), `LW-020` (binary-contrast two-sentence shape, "It's not X. It's Y."). Widened `LW-007` to also catch "Ultimately,"/"Overall," as summary-recap sentence-starters. 9 new tests in `scripts/test_submission_linter.py`. See CLAUDE.md's "Forbidden Language" section for the full rationale and the patterns deliberately left un-mechanized.

### Added
- **`LW-021` cross-employer audience/domain vocabulary bleed (2026-07-30):** new mechanical WARN rule in `submission_linter.py`. Found via a hiring-manager-pass audit of a real Newsela submission (drafted by a parallel session, not this one): a Cision-attributed Pendo bullet in `CoverLetter.md` said "we prioritized fixes **teachers and users** would feel in the product" — Cision has no teachers as users; Newsela's own audience vocabulary had leaked into a different employer's paragraph. No existing rule caught it — it isn't forbidden language, a metric problem, or a JD-paraphrase in the hook, it's a distinct failure class. `check_cross_employer_audience_bleed()` extracts the target JD's own distinctive vocabulary (frequency-based, excluding a generic cross-JD stopword set and the target company's own name) and flags it appearing inside a resume bullet or cover-letter paragraph attributed to a past employer (Cision/Sterkly/Zero to Sixty). Resume bullets are checked per-bullet, attributed via their enclosing `### Title | Employer | dates` header (a bullet almost never repeats the employer name inline, so a first attempt at plain sentence-splitting missed the real bug entirely). Cover letter is checked per-paragraph, not per-sentence, so an anaphoric reference ("at the same company") still gets caught. WARN, not HARD_BLOCK — a shared word can be a legitimate different sense (e.g. "prompt design" vs instructional "design"), so this forces a human read rather than an automatic rewrite. Wired into `lint_folder()`/`verify_submission.py` for every future submission automatically.

### Added
- **`LW-022` "sits at the intersection of" cliche opener (2026-07-30, Jason-supplied):** found in 3 of 8 real cover letters in one batch (Newsela, CivicPlus, Empower Pharmacy) via a critical-hiring-manager-pass audit — a recurring drafting habit, not a one-off. Jason: "that is not my voice and we shouldn't have that in cover letters." New WARN rule in `submission_linter.py` catches `sits/lives/operates/stands at the/that/this intersection` (with or without a following "of ..." clause — the first regex attempt required "intersection of" and missed CivicPlus's "sits at *that* intersection" variant, which has no "of" at all). Scoped to cover letters only. All 3 real instances fixed to plain, specific language instead of the metaphor; docs recompiled and re-verified clean.

### Added
- **Perplexity-sourced cliché audit, 6 new rules (2026-07-30, Jason-supplied):** Jason brought a Perplexity-generated cover-letter rule set; most of it duplicated existing rules (opener/closer bans, buzzword list, em-dash ban, fact cross-checking) or conflicted with deliberate decisions already on record — see below. The genuine gaps: widened `LR-003` ("I am confident that") to also catch "I am confident **in my ability to**"; widened `LR-009`'s core buzzword list with `robust`/`unwavering`; new `LR-023` (HARD_BLOCK, "look forward to discussing how my/our skills align"); new `LW-023` (WARN, stacked self-descriptor clichés — "results-driven, highly motivated, and dedicated" — curated word list, not a generic adjective-stacking grammar rule, to avoid false-positiving on legitimate comma/and verb lists); new `LW-024` (WARN, the "whether doing X or Y, I have consistently..." template, sibling to the existing `LW-020` binary-contrast rule); new `LW-025` (WARN, generic mission-alignment phrasing, "[Company]'s mission to X aligns with my commitment to Y" — real risk even without outside company research, since a JD's own "About Company" text often states a mission Stage 1 could echo back); new `LW-026` (WARN, JD-specificity floor — flags a cover letter engaging with fewer than 2 of the JD's own distinctive terms, reusing `LW-021`'s word-extraction machinery). **Retracted before shipping:** an initial `LR-022` blanket-banning "welcome the opportunity to" false-positived on the linter's own "clean" test fixture — CLAUDE.md's Cover Letter Proof-Point Selection section already explicitly treats "I would welcome a conversation about how this maps to X" as fine and only the generic "speak with your team" variant as the actual problem; a blanket HARD_BLOCK fought a decision already on record, so it was removed rather than kept. **Explicitly declined, conflicts with existing design:** "require at least one non-round, specific number per paragraph" — several real metrics (MET-04 churn, MET-15 conversion) are genuine self-reported estimates per the Attribution Discipline table, and forcing false unrounded precision onto them would violate the anti-hallucination rule that exists specifically to prevent that. "Draft-first, AI-edit-second workflow" — doesn't map onto this pipeline's actual architecture (Claude authors fresh from Fact-ID ground truth directly, not by editing user-supplied seed bullets); the underlying goal (never invent) is already served, more rigorously, by the Fact-ID/`find_unapproved_metrics` system. Swept all 7 real submission folders against every new rule — zero real content needed fixing beyond the 3 "sits at the intersection" instances already logged above. Also added a standing process rule to `generate-submission/SKILL.md`: a full cross-batch critical-hiring-manager sweep (not just per-company Stage 2) now triggers before any real send-batch or every 3+ new submissions, specifically because Stage 2's per-company scope structurally cannot catch a habit repeating across companies drafted in different sessions — which is exactly how the "sits at the intersection" pattern went unnoticed across 3 companies until asked for directly.

### Fixed
- **Job posting URLs never reached the database:** a full 13-submission batch (2026-07-24) went into `jobs` with `url` left `NULL` on every row, and 5 of the 13 had no `jobs` row at all. Root cause: `server/submissionFolders.ts`'s `readJdMeta()` already parses a `URL: <url>` first line out of `Original_JD.txt` when linking a folder to a DB row via `reconcileOrphanSubmissionFolders()`, but nothing in the authoring process had ever written that line — the mechanism existed, it was just never fed. Backfilled the 13 real URLs (from the source CSV exports) directly into `data/jobagent.sqlite` and prepended the `URL:` line to each `Original_JD.txt`. Documented the required format in CLAUDE.md/AGENTS.md's Submission Folder Structure section and in `generate-submission/SKILL.md`'s Stage 3 so future submissions capture it from the start.
- **generate-submission Stage 1 restatement leak:** Stage 2 kept failing the same way across most of a 9-JD batch — cover letters reused resume bullet phrasing for shared accomplishments. Root cause: Stage 1 told authors not to reuse phrases but deferred the check to Stage 2, and `LW-008-PAIR` only caught contrast-frame density, not general phrase overlap. Added `LW-009-PAIR` (shared 6+ word sequences across the resume+letter pair, allowing metric/scope cores) and made Stage 1 require a clean `lint_folder` pair check before handoff.

### Changed
- **2026-07-30 scout title-scope widening (Jason-supplied):** diagnosed why the scout was surfacing few real matches — the two largest reject categories in a live run were `target_role_scope` (730) and `Title Blocklist` (708), dwarfing dedup (310). Extended the `generate-submission/SKILL.md` §1.5 principle ("title is never itself a reject reason") from manual Stage 0 triage to the automated connector gate: added `Product Owner` and `Program Manager` to `search_terms` via `additionalSearchTerms` (real Settings mechanism, `server/domain/jobSearchPrefs.ts`), and removed `/\bprogram manager\b/i` from `ADJACENT_ROLE_DENY_PATTERNS` (`shared/domain/gates.ts`) since it now conflicted with a deliberately-added search term. `Project Manager` stays denied — not requested. A small live sample (3 real Program Manager postings pulled pre-gate-change) showed 2/3 were clear domain mismatches (security-ops TPM, healthcare case management) and 1/3 had a real anchor (privacy/compliance) — small sample, but a reminder that Program Manager is a much less discriminating title than Product Manager and will pull in more cross-industry noise for the fit-score gate to catch. CR-053 Epic 2 (evidence-tiered scoring, still in progress) is what has to catch that noise now instead of the title gate — worth monitoring queue quality over the next few runs.
- **2026-07-18/19 architecture pivot:** the biggest change to how the product actually authors documents had zero changelog visibility until now. The deterministic drafting pipeline (`draft_compiler.py` and everything the CR-062→068 entries below improve) is retired as the *authoring* method — Claude now writes resumes/cover letters directly from job-description text and `data/workExperience.md`/`data/master_claims.json` ground truth, verified against `data/conversion_rubric.md` plus a fixed set of deterministic checks (`submission_linter.py`, `quality_checker.py`, `approved_metrics.py`). The pipeline scripts stay in the repo, unmodified, still live behind the web UI's own "Draft" button — this is an authoring-method change, not a deletion. Process: `.claude/skills/generate-submission/SKILL.md`. See `docs/spec/08-implementation/SESSION-HANDOFF-2026-07-18-authoring.md` and `C:\Users\Jason\.claude\plans\magical-booping-wilkes.md`.

### Added
- **CR-062:** `scripts/local_rewrite.py` — the first local-LLM-generation call site in the drafting pipeline that's actually wired live (per CR-059, the default pipeline previously called zero local LLMs for generation, only for embeddings). Implements the "Deterministic-Minimal-LLM" architecture (see `docs/reports/local-llm-builder-architecture-options.md`, ranked #1 of 10 candidate designs): a new `DRAFT_MODE=local_rewrite` value, additive to the existing `compose` default, that naturalizes an already-selected, already-fact-checked sentence at 3 call sites (resume bullets via `claim_composer.compose_bullet`; the summary proof clause via `local_draft_stages.build_summary_deterministic`; cover-letter paragraphs via `cover_letter_renderer._render_block_letter`) using a new `rewrite` stage (`qwen2.5:7b-instruct-q4_K_M`, escalating to `phi3.5:3.8b-mini-instruct-q8_0` on gate failure, hard local-only with no cloud fallback). Grounding is enforced twice: input is always already-verified source text, and output is re-validated against numeric-token-set *equality* (not just no-fabrication) plus a proper-noun/tool subset check, falling back to the verbatim source on any failure — logged to a per-batch audit file (`data/submissions/_batch_audit/{batch_id}/rewrite_fallbacks.log`) for an after-the-fact skim, never a blocking per-submission step. Claim selection, JD profiling, and structure are entirely untouched. 26 regression tests in `scripts/test_local_rewrite.py`; end-to-end calibration run against a real archived JD (tropic) confirmed identical rubric score to the `compose` baseline (76.2/100) with cleaner bullet/paragraph phrasing, 1-page output, and a clean lint pass. See `docs/spec/05-change-requests/CR-062-local-rewrite-harness.md`.
- **CR-062:** Fixed a real side-effect bug found while calibrating the above: `pipeline_env.jd_profile_mode()` and `cover_hook_mode()` treated *any* `DRAFT_MODE` value other than `"compose"` as an implicit switch to the free-form LLM path for JD profiling and cover-hook generation — meaning the new `local_rewrite` mode was silently also flipping unrelated pipeline behavior it was never designed to touch. Both functions now treat `local_rewrite` the same as `compose` for these decisions.
- **CR-063:** Ran the JD theme-extraction & claim-selection test-and-iterate loop against a new 16-JD human-verified eval set (`docs/reports/jd-theme-claim-eval-set.md`). Baseline: 14/45 should-surface claims hit, 0/16 companies with a full pass. Added 10 `THEME_KEYWORDS` entries to `scripts/jd_tailoring.py` (privacy/compliance/identity/access/governance/genai/agentic/llm/cursor/claude) across three rounds — net aggregate stayed flat (one fix + one tag-collision regression, one correctly-firing-but-too-weak fix, one candidate ruled out by hand-calculation before implementation). Piloted both of the CR's own proposed fallbacks with real local infra: semantic re-ranking via cached embeddings (`scripts/measure_semantic_rerank.py`, new) made the aggregate monotonically *worse* across 6 tested scale values (14/45 → 11/45); `jd_profile_mode="llm"` produced byte-identical selection accuracy to the deterministic path on the 3 worst JDs despite genuinely better theme extraction. Both ruled out with measured data. Root cause pinned to `score_claim_for_jd`'s scoring formula (three uncapped, non-deduped scoring loops let generic PM vocabulary out-accumulate rare precise matches) — handed off as CR-064. See `docs/spec/08-implementation/CR-063-jd-theme-claim-selection-loop-tracker.md` for the full round-by-round trail.
- **CR-064:** Reworked `score_claim_for_jd`'s scoring formula in `scripts/jd_tailoring.py` (dedup + rarity weight + DCG breadth dampener), keeping the existing 3-argument signature so all 8 call sites (6 production: `local_draft_stages.py`, `claim_composer.py` ×2, `draft_compiler.py` ×2, `cover_claim_picker.py`; plus `measure_semantic_rerank.py`, `smoke_draft_compiler.py`) need no changes. Fixed two real, verified defects: cross-loop/cross-line token double-counting (a single token like `platform` could score 3+ times) and rare precise matches being under-scored against generic PM vocabulary. **Closed partial (`closed_partial`), goal NOT achieved:** the CR's headline acceptance criterion — that `ACC-105-EXECUTION`'s cross-JD top-5 over-representation measurably drops — was not met. Three independently-implemented, security-cleared, QA-verified mechanisms (dedup, rarity, breadth dampener) each behaved exactly as designed on isolated hand-checks yet moved the metric ~0 on the fullest eval measurement (ACC-105 stayed 10/14 top-5 appearances before and after, 14 companies including archive-sourced sailpoint/group_1001). Two known cover-letter test regressions are deferred, not fixed (`test_cover_claim_picker.py::test_fintech_jd_prefers_dropoff_story`, `test_cover_word_padding.py::test_thin_jd_still_produces_proof_content` — `cover_claim_picker.py`'s flat proof-bonuses interacting with the CR's inflated score scale; a Jason-gated calibration follow-up, deliberately not retuned inside this CR). Recommended next direction is a separate investigation into JD-profile/keyword extraction (upstream of this function, flagged by CR-063), not a further round of scoring-arithmetic. See `docs/spec/05-change-requests/CR-064-claim-score-formula-rework.md` and the round-by-round trail in `docs/spec/08-implementation/CR-064-claim-score-formula-rework-tracker.md`.

### Fixed
- **CR-068:** `build_jd_profile_deterministic`'s `requirements` field (`scripts/jd_tailoring.py`) captured job-posting boilerplate (location, employment type, salary band, benefits copy, interview steps, bare section headings) instead of the JD's real requirement bullets in 4/13 measured companies — starving downstream claim scoring of the real requirement signal. Fixed in two measured rounds, one hypothesis each (CR-064 discipline). Round 1: added `who you are` and `required education and experience` to `_REQ_SECTION_RE`'s heading alternation, and rewired the `requirements` line-scan to source from `extract_req_section(jd_text)` instead of raw `jd_text` (previously the heading-scoping helper was never called on this field). Round 2: raised the line-length cap from 120 to 250 on both the upper-bound test and the store-slice, in lockstep (250 is the measured break point between the real single-bullet population, which tops out ~245-250 chars, and the multi-sentence paragraph-boilerplate class above it — the original cap was silently dropping every long "Trait: elaboration"-style real bullet). Second production code change in the CR-063→064→065→066→067→068 arc. All 4 originally-broken companies substantially improved: OneStream and Remote clean, Ontra and Covideo at 5/6 real bullets + 1 residual section-boundary/ordering artifact each (out of the length-cap-only scope, flagged for a possible Round 3). Full-archive regression check across 250 archived JDs found exactly one marginal regression (`visionaire_partners`, an already near-100%-boilerplate job-board scrape); zero regressions among the 8 previously-good companies. Pytest 28F/195P/1S → 28F/200P/1S (5 new tests in `scripts/test_jd_profile_requirements.py`, same 28 pre-existing failures). No change to `_NEXT_SECTION_RE`, `keywords`, `priority_themes`, `score_claim_for_jd`, `THEME_KEYWORDS`, or `data/master_claims.json`. See `docs/spec/05-change-requests/CR-068-requirements-section-extraction-fix.md` and `docs/spec/08-implementation/CR-068-requirements-section-extraction-fix-tracker.md`.
- **CR-066:** `build_jd_profile_deterministic`'s `keywords` field (`scripts/jd_tailoring.py`) selected the JD's top-12 length-≥5 words by **alphabetical order** (`sorted(set(...))[:12]`), which discarded frequency entirely and systematically surfaced whatever generic vocabulary sorts early over the JD's own defining nouns. Changed to descending in-JD-frequency with alphabetical tie-break (`Counter`-based), keeping the same `[a-z]{5,}` length filter, same 5-word stopword set, same `_jd_body_for_themes()` source text, and same `[:12]` cutoff — signature and all call sites unchanged. This is the first production code change in the CR-063→064→065→066 arc and its first measured win: CR-063 diagnosed the selection problem, CR-064 wrongly attributed it to downstream ranking arithmetic (null result, closed partial), CR-065 root-caused it to `keywords` extraction, CR-066 fixes it. Measured across the 12 available eval-set companies: `ACC-105-EXECUTION`'s cross-JD top-5 over-representation dropped 9/12 → 5/12 (every drop was a company where it was never should-surface), aggregate should-surface hit rate improved 10/34 → 11/34 with zero regressions, pytest 28F/190P/1S → 28F/195P/1S (5 new tests in `scripts/test_jd_profile_keywords.py`, same 28 pre-existing failures). The `requirements`/`extract_req_section()` boilerplate-capture defect (a distinct, still-undiagnosed root cause) is explicitly reserved for a future CR-067, and the under-scoring `ACC-401-AITOOLS`/`ACC-204` problem remains open with no measured evidence an extraction fix addresses it. See `docs/spec/05-change-requests/CR-066-jd-profile-keywords-frequency-fix.md` and `docs/spec/08-implementation/CR-066-jd-profile-keywords-frequency-fix-tracker.md`.
- **CR-061:** AI-Native trigger (batch2-jd-tailoring-findings.md P-005) confirmed failing on ~13 of ~20 manually-reviewed submissions. Root cause was two separate gaps, not one: (1) `draft_compiler.py` stripped the resume PROJECTS section (FR-208) on *any* over-budget render before trimming a single bullet, so it almost never survived — reordered pruning so bullets trim to floor first and PROJECTS is the last resort; also capped `build_projects_section` to the single highest-priority entry (`MAX_PROJECTS`, `local_draft_stages.py`) instead of 3, reducing its budget footprint. (2) The cover letter path had no mechanism at all — `projects_catalog.json` was resume-only and no equivalent claim existed in `master_claims.json` for `cover_claim_picker.py` to select. Added `ACC-401-AITOOLS` (grounded in `workExperience.md` line 44's existing Jason-confirmed AI-tooling note) with `employer: ""` so it can never be mis-selected as a resume experience-section bullet, plus a `has_ai_signal`-gated scoring bonus in `cover_claim_picker._proof_score`. Also found and fixed: the picker's metric-density guard was silently discarding this claim after selection because it has no digit (by design — it's a qualitative capability claim, not a fabricated metric); added a narrow protected-slot exception gated on the same AI signal. Verified against 15 real archived JDs: 12/12 with genuine AI/LLM language now select the claim, 0/3 without it do. Regression tests in `scripts/test_ai_signal_routing.py`.
- **CR-061:** All 8 entries in `data/projects_catalog.json` used a literal em-dash in the project name (`"JobAgent — AI-Powered..."`), which would have hard-blocked the linter (`LR-006`) the first time the PROJECTS section actually survived to a final resume — found while verifying the fix above. Replaced with colons.
- **CR-057:** Missing SQLite transaction boundaries in `jobRepository.ts`. Mutating `jobs` and syncing `jobs_fts` were sequential but non-transactional; a crash midway permanently desynced the full-text search index. Fixed by wrapping `insertJob`, `patchJob`, and `deleteJobRecord` in `db.transaction()`.
- **CR-057:** Type safety vulnerability in external ATS connectors (demonstrated in `theirstack`). `res.json()` was casted and sliced without runtime array validation, causing TypeErrors on malformed payloads. Fixed for TheirStack (returning empty array safely); globally deferred for Zod overhaul.
- **CR-057:** Silent data loss and logic failures caused by swallowed exceptions. `scoutOrchestrator.ts` swallowed `UNIQUE` constraint errors from concurrent inserts, and `openpostings` swallowed ATS sync fetch errors. Both now log errors correctly.
- **CR-056:** Ashby connector called a private/authenticated endpoint (`v1/publishing-posts`, always 401) instead of the public `posting-api/job-board` endpoint; also fixed response parsing (`{jobs:[...]}` wrapper, not a raw array) and the job-URL field name (`jobUrl`, not `jobPostingUrl`). Was returning 0 jobs on every run; now returns real results (verified live: 0 → 15 on the existing watchlist).
- **CR-056:** Workable connector called a deprecated endpoint (`www.workable.com/api/accounts/...`) that Cloudflare now blocks with a 302 redirect instead of JSON. Switched to the working `apply.workable.com/api/v1/widget/accounts/...` endpoint.
- **CR-056:** Working Nomads connector filtered on `category_name` for "product"/"management" — that category never appears in Working Nomads' real taxonomy (Marketing, Development, Design, Sales, etc.), so it always returned 0 regardless of what was actually posted. Switched to title-text matching, consistent with the other connectors; added configurable `searchTerms`.
- **CR-056:** OpenPostings connector pointed at a project-root path that never existed (`OpenPostings-extracted/OpenPostings-main`) and, even when pointed at the right path, parsed the wrong response shape (`{items:[...]}`, not a raw array) — both bugs meant it silently returned 0 jobs on every run, forever. Found the actual OpenPostings project already sitting in `data/archive/` from a prior cleanup, installed its 4 real server dependencies (skipping its unrelated Expo/React-Native app tree), repointed the connector, and fixed the parsing bug. Verified live through the full spawn → sync → search flow (0 → 3 jobs, including a company not on any existing watchlist).
- **CR-056:** Geographic gate (`passesGeographicGate`) auto-rejected any job with a thin/missing description if it wasn't from one of 7 pre-approved remote job boards — even when the job's *title* explicitly named the candidate's local area (e.g. "Product Manager – San Diego, CA"). The short-description branch never checked the title at all. Now checks title against `localAreaTerms` before falling back to the work-setting/source-allowlist check.
- **CR-056:** Settings page (`SettingsView.tsx`) used a single shared debounce timer across every settings field on the page. Editing the Adzuna API key fields, then touching any other field (e.g. the TheirStack key sitting right below it) within 1 second silently cancelled the pending Adzuna save with no error shown — the save badge still read "Saved" for whichever key won the race. Switched to per-key debounce timers. Confirmed via the live database: `adzunaAppId`/`adzunaAppKey` had been silently dropped twice while `theirstackApiKey`, saved through the identical mechanism, persisted correctly.
- **CR-054:** Post-drafting audit non-convergence no longer reports pipeline success. `audit_and_improve_company` returns an `AuditImproveResult` contract; `run_drafting_engine` raises on failure; pre-audit file snapshots restore on non-convergence so bad enhanced drafts cannot ship under normal filenames.
- **CR-055:** Years-gate false positives from incidental JD prose (Jackson Laboratory 90-year history, Civica founded-years) fixed via requirements anchoring and plausibility caps in `seniority_gate.py`.
- **CR-055:** Title blocklist uses role-designation vs focus-area split; `Product Manager, Growth` and NVIDIA developer-productivity titles no longer false-block.
- **CR-053:** Location gate rejects non-SD onsite/hybrid cities, Canada in-person, and EST/CST-only remote postings.
- **CR-053:** Structured evidence-tiered fit scoring (`structured_fit.py`) replaces holistic LLM 0-100 as default path; anchor floor no longer force-promotes scores.

### Removed
- **CR-056:** BuiltIn and Levels.fyi connectors — both used Playwright with a stealth plugin to impersonate a real browser against a live site. Levels.fyi had been silently returning 0 jobs for 10+ days with no visible errors; both were the same category of ban-risk the rest of the connector stack (pure JSON APIs) was built to avoid.
- **CR-056:** Per-company Greenhouse, Lever, Ashby, and Workable connectors — these only work by hand-curating a list of companies to watch, which no longer matches how job search is actually being run (broad PM search by location, not a fixed company list). OpenPostings already covers these same ATS platforms (plus Workday, iCIMS, and others) across ~7,700 companies via free-text search with no watchlist required, making the per-company connectors redundant. Also removed the now-orphaned `shared/domain/atsBoards.ts` loader.

### Changed
- **CR-056:** `experience_range.max` (years-of-experience ceiling used by both the ingestion-time years gate and `seniority_gate.py`) raised from 7 to 8 to match actual years of experience and stop silently rejecting "Senior Product Manager" roles requiring 8 years. Updated through the real `job_search` settings API so the change persists correctly rather than being overwritten on next Settings save.
- **CR-053:** `apply_anchor_floor` records anchor hits in `RiskFlags` only (no score overwrite).
- **CR-054:** `blocked_companies` list in `candidate_preferences.json` enforced at zero-token gate (Unity in example prefs).

### Developer
- **CR-054 Epic 1:** `scripts/test_audit_convergence.py` regression coverage.
- **CR-053/055:** New tests: `test_location_gate`, `test_title_blocklist`, `test_structured_fit`, `test_blocked_companies`, `test_template_lint_sources`; `calibration_harness.py`, `rescore_location_gates.py`.
- **Rollout:** `npm run gate-rollout` / `gate-rollout:apply` merges gate prefs from example and rescores Backlog/New location gates (`apply_gate_rollout.py`).
- **SDD closeout:** Formal `CR-053`/`CR-054`/`CR-055` specs; registry `FR-242`–`FR-248` + `AC-264`–`AC-271`; traceability matrix; `job_fit_engine.md` v5.0; `FR-248` preserve keys in `jobSearchPrefs.ts` + vitest.

---

## [7.1.0] — 2026-06-24

### Changed
- **Cross-device data portability** — All private data (`submissions/`, `archive/`, `jobagent.sqlite`) consolidated under `data/`. Google Drive sync of one folder (`data/`) is now sufficient to move the full application state between devices. No hosted database required.
- **Repo hygiene** — Removed root-level duplicate docs, stale `data/job_fit_engine.md`, accidental `=` file, and 18 files that should never have been tracked (`data/thinking/`, `_bmad-output/`). CI smoke tests now pass reliably after fixing step-ordering bug that caused `python: command not found` on ubuntu-latest.

### Fixed
- `server/routes/system.ts` — local-model streaming route no longer crashes; reads LLM settings from SQLite `profiles` table instead of missing `.agent/llm_settings.json`.
- `scripts/utils.py` — `ARCHIVE_DIR` constant aligned to `data/archive/submissions` (was `archive/`, now matches the active archive path used by all scripts).
- README doc links in root table pointed at deleted root copies of `AGENTS.md` and `SDD_PROCESS.md`; corrected to `docs/` canonical versions.
- Example files moved to live next to their real counterparts in `data/`: `ats_watchlist.example.json`, `cover_voice.example.md`.

### Developer
- 64-file path refactor updating every `submissions/`, `archive/`, and `jobagent.sqlite` reference across Python scripts, TypeScript scripts, server files, CI config, audit script, and `.gitignore`.
- `package.json` `dev:server` tsx watch exclusions simplified — single `--exclude "data/**"` replaces four separate patterns.
- `scripts/regeneration_log.txt` added to `.gitignore` (was untracked runtime output).

---

## [7.0.0] — 2026-06-12

### Added
- **Epic 1: Modular Connector Architecture & Crawl Governance** — Refactored all 12 existing connectors to a clean, isolated `JobConnector` contract; introduced a domain policy gate (`domain_policies`) to govern BuiltIn and Levels.fyi crawlers.
- **Epic 2: Expanded Source Coverage** — Added Greenhouse, Lever, Ashby, Workable, and TheirStack API connectors with credit usage checks (200 credits/month TheirStack cap).
- **Epic 3: Raw Ingest & Deduplication** — Storing raw job payloads in `job_ingest_raw` with post-sync job clustering (`clusterDedup`), showcasing multi-source attribution in the job details.
- **Epic 4: Scoring Transparency** — Persisted multi-dimensional scoring breakdowns in `job_scores` and rendered interactive score breakdowns ( seniorities, domain compatibility, salary, location gates) in the job detail panel.
- **Epic 5: Live Pipeline Observability** — Implemented Server-Sent Events (SSE) stream backend and real-time React EventSource hooks to update progress logs, active stage progress, and source health badges dynamically.
- Unified test runner (`npm test`) that runs both Python unit/regression test scripts and the Vitest TypeScript suite, providing a clean dashboard summary and non-zero exit code on failure (CR-046).
- Windows encoding robustness in the test runner, setting `PYTHONIOENCODING=utf-8` on child processes and using `errors="replace"` on `subprocess.run` decoders to prevent console crashes.


---

## [6.2.31] — 2026-06-01

### Added
- Deterministic cover letter voice engine — proof paragraphs use verified catalog text only, no LLM voice rewrite, word band enforced at 300–400 words
- Resume quality enforcement with strict conversion critique gate — blocks PDF export until human-mirror critique passes, with auto-retry loop

### Changed
- Cover letters no longer append boilerplate bridge phrases on every proof paragraph
- Job source count expanded to 12 active sources (added Jobicy, Working Nomads, JobsCollider)

---

## [6.0.0] — 2026-05-13

### Added
- Semantic anti-hallucination engine — mathematical verification that all percentages, dollar values, and user scales in generated text are valid subsets of ground truth
- Stateful orchestration with stage recovery — sync crashes no longer reset the full batch queue; re-triggering restores the precise failed sub-stage
- Early location gate embedded in the scout aggregator — filters out-of-bounds listings before database storage

### Fixed
- SQLite write-ahead logging configured globally — eliminates database locking deadlocks during high-concurrency execution

---

## [5.0.0] — 2026-04-16

### Added
- Deterministic claim-to-ID verification — LLM must anchor all resume and cover letter claims using bracketed proof codes (`ACC-NNN`, `MET-NNN`, `VOC-NNN`) from `workExperience.md`; codes stripped before final PDF output
- Automated verification retry loop — up to 3 attempts; hallucinated or invented IDs trigger a localized rewrite before failing
- Multi-LLM fallback chain — Gemini → Claude → Ollama with instant failover on 429 or provider error; no run lost to a single provider outage

---

## [4.0.0] — 2026-04-15

### Added
- Local web portal with dashboard metrics, active pipeline view, and per-job detail panels
- Settings UI for LLM provider keys, work experience, and search preferences — all stored in SQLite, no `.env` file required

### Changed
- Migrated from CLI-only execution to a full local single-page web app (React 19 + Vite frontend, Express backend)

---

## [3.0.0] — 2026-03-12

### Added
- Anti-hallucination guard — audits every generated document against `workExperience.md` to prevent AI seniority inflation or invented credentials
- Markdown-to-PDF compilation pipeline using headless Chromium

---

## [2.0.0] — 2026-02-18

### Added
- Multi-dimensional job-fit scoring engine evaluating roles across four vectors: leadership fit, seniority fit, technical depth, transition potential
- Deterministic fast gate — instantly rejects roles matching solo-PM traps, founding PM roles, low salary, or non-US location before spending any LLM tokens

---

## [1.0.0] — 2026-01-10

### Added
- Initial release: automated job discovery and crawling across LinkedIn and Built In
- Structured extraction of raw job description text for downstream processing
