---
status: decided
date: 2026-09-22
decision: E
related: CR-108, CR-109, CR-119, CR-121, CR-122, CR-123, CR-124
---

Decision (2026-09-22): ship **E**. Employer names, section-header fragments, and methodology nouns are chrome. They do not withhold. Implemented as CR-124.

Superseded in part (CR-125, 2026-09-23): a missing required product no longer withholds. The name can stay in the reason list. Authoring continues and does not claim it. A card exists only when that tool is why a job never went out.

# Decision brief: conversion_risk after CR-122

As of 2026-09-22. Decided the same day: option E, CR-124.

## The question

Should a Stage 0 PASS still withhold authoring when a **required** JD line is scored as a named tool with evidence 0, if that "tool" is often extractor junk (company name, section header, methodology) rather than a real product gap (Dynamics, UEM, Delta Lake)?

## Short answer

CR-122 did what you asked. Unknown tools no longer quiz you and no longer hold the CSV queue. Unsupervised flow is still blocked, because CR-121 conversion_risk now parks the same jobs one step later. Tomorrow's choice is whether conversion_risk means "this posting needs a product I do not have" or "Stage 0 found a noun." Those are different bars. The first is why velosio burned Agy for a 63. The second is why Employers paused on "And Experience."

Do not `apply_anyway` the junk parks as a habit. That teaches the pipeline that withhold is optional. Do not Skip them either. That writes the skip ledger and hides a job you might still want.

## How the pipeline actually runs now

CSV jobs go through `ingest_csv_queue.py` then `run_queue_worker.py`. The worker claims a pack, locks the slug, and is the only thing that should call `run_submission.py` on a queued folder.

Stage 0 (Agy, `APPLYR_STAGE0_SUBSCRIPTION_ADAPTER=1`):

1. Deterministic hard gates (people-management, 0-to-1, revenue, and the rest of the exclusion zone). These can Skip.
2. Extract and classify JD lines (required / preferred / culture / exclude).
3. Named-tool scan. Tools not in `workExperience.md` or the skills catalog are undocumented for this JD. Evidence 0, no `claim_ids`. A Review Center card is still created, grouped by tool, as a later WE correction.
4. Fit score. Skip floor is still 40. PASS can be Tier 1 or Tier 2.
5. **After PASS only:** `evaluate_conversion_feasibility`. If `risk`, Stage 0 receipt is COMPLETE, workflow stays `WAITING_FOR_INPUT` with `pause_kind=conversion_risk`, no authoring prompt. Queue `paused_reason=conversion_risk`. Skip ledger is not written. Worker releases the lease and takes the next slug.

Stage 1 only runs when conversion_feasibility is `ok` (or you later `requeue --reason apply_anyway`). Then packet, Agy author, Stage 2 Truth/ATS/HM/Mech/Policy. Resume floor 70, cover letter 65. Honest below-floor parks (`mech.rubric_floor`). `--finalize` is explicit and writes the jobs DB. Do not finalize until you have read the PDFs.

Groq/Gemini Settings keys are leftover cascade. They are not the production LLM. Agy is.

## What each CR is for

**CR-108** (superseded in part): unknown named tool paused Stage 0 and asked Review Center. `No` wrote `skill_memory.NOT_PRESENT` as a forever career fact.

**CR-122** (implemented 2026-09-22): default to WE. Do not pause Stage 0 on `skill_presence`. Do not write forever-No. Open skill cards do not hold the queue. Hard-gate review and requirement-extraction review still pause. Required unknown tools still go to CR-121.

**CR-121** (withhold on, Agy rubric hook off): after PASS, withhold authoring when a required item names a `not_present` tool, or a required item is evidence 0 and `looks_like_named_tool` hits a multi-word name. Designed for velosio Dynamics and omnissa Workspace ONE / Android: Stage 0 said PM-eligible (fit 40+), then the resume could not look native (honest 63 to 67). Raising the skip floor would not have caught velosio (fit 71, resume 63).

**CR-109**: stop treating methodology phrases, scientific fields, and category acronyms as tools. Live miss: certara/velosio. `Microsoft Dynamics 365` still counts. This did not catch "And Experience" or the company name inside a governance sentence.

## Live evidence tonight

| Slug | Fit | CR-122 | Then CR-121 | Why |
|---|---|---|---|---|
| `businessolver` | 76, Tier 1 PASS | No Review Center wait | `conversion_risk` | Required line about using AI tools "while following Businessolver data handling." Extractor treated **Businessolver** as a named tool. |
| `employers` | 44, Tier 2 PASS | No Review Center wait | `conversion_risk` | Reasons: **And Experience** (header fragment "Background And Experience/Expertise"), **OKRs**, **Delta Lake**. |

Both folders are in `data/submissions/` with Stage 0 COMPLETE and no `authoring_prompt.md`. Promote path is only:

```
python scripts/queue_claim.py requeue --slug SLUG --reason apply_anyway
```

then the worker. That writes `conversion_risk_apply_anyway.json`. It does not fix the next JD.

`ss_c_technologies` is still a skill-only `review_center` pause with zero open hard-gates. It is promotable under CR-122. Do not fill its IBM Cloud / Google Cloud cards to unstick it.

`amplify` and `eso` are requirement-extraction review. Different pause. Do not fill those templates.

Honest 70-floor parks (velosio, certara, omnissa, outschool, goodrx) stay parked. Do not rebuild. Do not auto-requeue.

Stage 3 READY (clarion, confidential, sourcegraph, velera): read PDFs, then `--finalize` if you want them in the jobs DB.

## The problem

You now have two different "this job cannot convert" machines.

1. **Fit Skip (floor 40).** "You are not a PM-eligible match." Folder goes to `archive/skipped/`. Ledger remembers the URL / company+title.
2. **conversion_risk (after PASS).** "You are eligible, but a required named tool is undocumented, so authoring will likely fail R2/R3 identity." Folder stays, no Skip, no draft.

Machine 2 is only as good as "required named tool." Tonight that phrase included:

- A real product Jason does not have (Delta Lake on a Data Product Manager JD). Same class as Dynamics.
- A methodology (OKRs). CR-109 already tried to stop this class and missed.
- A company name in a data-handling clause (Businessolver).
- A chopped section header (And Experience).

CR-122 removed the human quiz. It did not stop the extractor from minting those nouns, and it did not stop CR-121 from treating every one of them as an identity gap.

The unsupervised goal ("worker runs, Jason reads PDFs at the end") only holds for JDs whose **required** lines do not contain a multi-word `looks_like_named_tool` hit at evidence 0. Preferred unknown tools (IBM Cloud in an OR-list) now flow. Required unknown tools, real or fake, still stop the slug.

Helper: `evaluate_conversion_feasibility` in `scripts/build_stage0_fit_gate.py`. Single-token tool names do not fire unless they already sit in `not_present_named_tools`. Multi-word hits on an evidence-0 required line always fire. That is why "And Experience" and "Delta Lake" both count, and "Jira" on its own would not unless it was already marked not present.

## What not to undo

- Do not raise skip floor 40 to catch conversion identity. Velosio was 71 then 63.
- Do not Skip conversion_risk. Skip hides the job and writes the ledger.
- Do not fill Review Center skill cards to unstick the queue.
- Do not `--finalize` READY packs unread.
- Do not turn on `APPLYR_STAGE2_AGY_RUBRIC` until AC-464 (Agy must not CONVERT-READY the five parked-below-70 resumes).
- Do not hand-run `run_submission.py` on a queued slug.

## Options for tomorrow

### A. Leave the rule. Batch `apply_anyway` only when you still want a draft

**What:** conversion_risk stays. Worker keeps moving. You periodically read the conversion_risk list and requeue the ones that are real stretch-but-honest PM jobs, or real tools you actually have in WE and the extractor missed.

**Consequence:** Supervision is a batch, not 30 Review Center taps. Junk parks accumulate until you look. Agy is not spent on Dynamics-class jobs unless you say so. Employers-class junk sits next to Delta Lake-class real gaps, so the list is noisy. `apply_anyway` on junk still authors; Mech may still park below 70.

**Use when:** you would rather miss a few drafts than spend Agy on another velosio.

### B. Tighten what counts as a named tool (extractor hygiene)

**What:** extend CR-109. Do not treat company names, section headers, hire-site chrome, or methodology (OKRs, Agile, MVP) as named tools for conversion_risk. Keep withhold for product lines (Dynamics, Workspace ONE, Delta Lake, Snowflake).

**Consequence:** Businessolver and "And Experience" would author. Employers might still park on Delta Lake alone, which is the honest remaining gap. Future junk nouns stop landing in the same bucket as real products. This is the smallest change that matches "if it is not in WE, do not speak to it, and keep moving" **except** for real required products.

**Risk:** a real required product that looks like a methodology or a company-branded platform gets through. Packet caps still say "do not write the JD tool name," so the draft should stay honest. Rubric can still park below 70.

### C. Fire conversion_risk only on a closed product list

**What:** withhold only if the required tool is in `HARD_BLOCKED_TOOLS` / skills catalog / an explicit identity list (Dynamics, NetSuite, SAP, UEM, Android Enterprise, maybe Delta Lake). Unknown multi-word hits do not withhold.

**Consequence:** "And Experience" never parks. A brand-new required platform that is not on the list authors, then likely fails 70 the way certara/goodrx were allowed to (`ok` then honest 64). CR-121 v1 already accepted that miss rather than a domain gazetteer. This is that miss, applied to tools.

**Risk:** the next velosio-shaped product that is not in the list spends Agy again.

### D. Treat required unknown tools like preferred ones (no withhold)

**What:** CR-122 for required too. Auto-absent, card in Review Center, author anyway.

**Consequence:** Unsupervised flow looks like 2026-07 again: if it is not in WE, do not claim it, keep moving. You will spend Agy on Dynamics/UEM/Delta Lake jobs and honest-floor park after Stage 2, which is exactly the bill CR-121 was written to avoid.

**Use only if:** you would rather pay Agy than maintain a withhold rule, and you accept another week of 63 to 67 resumes.

### E. Split junk vs real inside conversion_risk, still withhold the real ones

**What:** same withhold, but Stage 0 must not put header fragments or the employer name into `not_present_named_tools` or `looks_like_named_tool` on required lines. Delta Lake still `risk`. Businessolver the company does not. This is B with an explicit "employer-name-in-JD is chrome" rule.

**Consequence:** the conversion_risk list becomes a short list of actual product gaps. `apply_anyway` on that list is a real product decision (stretch into a lakehouse PM role without Delta Lake in WE), not a parser apology.

## Suggested default if you do not want to design in the morning

Ship **E** (hygiene plus keep withhold for real required products). Do not `apply_anyway` Employers or Businessolver until that ships, unless you specifically want those drafts anyway. Delta Lake on a Data Product Manager posting is the one line in tonight's parks that looks like velosio, not like a parser bug.

`ss_c_technologies` can take a size-1 worker without a product decision. It is the leftover CR-122 live proof (preferred cloud OR-list). Expect either authoring or a cleaner conversion_risk if a required line names Google Cloud / IBM Cloud.

## Related, not this decision

Tonight's first `employers` claim returned empty because leftover `archive/skipped/employers` from an earlier skip made CR-123 treat a live `pending_review` folder as already handled and mark the queue row `done`. That close now ignores archive ghosts when a live pending_review or submissions folder exists. Archive-only rows still close. Do not mix that bug into the conversion_risk decision.

## What "done" looks like after you pick

- A: a written rule for when you `apply_anyway` vs leave parked. No code.
- B / E: a CR, tests with Businessolver-shaped and "And Experience"-shaped fixtures that stay `ok`, and a Dynamics-shaped fixture that stays `risk`. Delta Lake: you decide in that CR whether it is identity or transferable data-PM.
- C: a closed list in spec, not a growing regex.
- D: a CR that retracts FR-355 for unknown tools. Say that out loud. It undoes the velosio spend control.

Until you pick, the worker will keep parking PASS jobs whose required lines contain a multi-word tool-shaped noun that is not in WE. That is working as coded. It is not working as "run the queue and I will read PDFs."
