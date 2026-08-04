# SESSION HANDOFF — 2026-08-04 — Sync review queue (replaces the removed EVALUATE stage)

**Depends on:** `SESSION-HANDOFF-2026-08-04-URGENT-disable-silent-autodraft.md`. Do that removal first;
this doc fills the gap it leaves. Ideally land both in the same pass so EVALUATE isn't briefly a no-op.

## The design (Jason-supplied, 2026-08-04)

Sync should still be useful after the old auto-draft is gone — it just stops doing anything an LLM (local
or hosted) is needed for. New shape:

**Scrape (unchanged) → deterministic role filter (no LLM) → write qualifying JDs to a review folder →
stop.** Nothing further happens automatically. The next time Jason is in a Claude Code chat session, he
(or I, prompted) reads that folder and runs the real `generate-submission` Stage 0-3 process on what's
there — same as if he'd pasted the JD text directly, just sourced from a folder instead.

**No Anthropic API calls anywhere in this automated path.** That was an earlier design considered and
explicitly rejected in favor of this simpler one — deliberate, not an oversight. Fit judgment (Stage 0)
only ever happens live, with a human in the loop, in a chat session. Don't add any LLM call — local or
hosted — into the Sync flow.

## What to build

1. **Reuse the existing deterministic gates — don't build new filter logic.** `shared/domain/gates.ts`
   already has `passesTitleBlocklist`, `passesGeographicGate`, `passesIndustryGate`,
   `passesSeniorityGate`. **First, check whether these already run during the SCRAPE stage** (at
   connector ingestion, before a job lands in `jobs` at all — this appears to be the case per
   `scoutOrchestrator.ts`'s existing design). If so, any job that's newly present in the DB after this
   Sync run has *already* passed the role filter — the "filter" step here may just mean identifying which
   rows are new-this-run, not re-applying gate logic a second time. Confirm this before writing anything
   redundant.
2. **Export destination:** a new folder, kept separate from `data/submissions/` (that directory is
   reserved for actual authored drafts with the full PDF/verification-receipt structure — don't mix
   pending-review JDs into it). Propose `data/pending_review/{company}/Original_JD.txt`, but this is a
   naming call Cursor can make — just keep it a distinct top-level location.
3. **Follow the existing `Original_JD.txt` convention exactly** (CLAUDE.md's own documented format): if
   the job's URL is known, it must be the file's first line, formatted exactly as `URL: <the url>`,
   followed by a blank line, then the raw JD text. This isn't cosmetic — it's what `generate-submission`
   Stage 0 and other tooling already expect. Don't invent a different format.
4. **Idempotency — don't re-export the same job on every Sync.** Add a DB-level marker (e.g. a new
   nullable `exported_for_review_at` column, or reuse an existing status value if one already fits) so a
   job that's already been written to the review folder doesn't get rewritten (or re-flagged as "new")
   next time Sync runs. Check `server/migrations/` for the existing pattern before adding a column.
5. **This step fully replaces the old EVALUATE stage's role** — no scoring, no drafting, just: identify
   new qualifying jobs this run, write their JD text to the review folder. Keep the existing SCRAPE stage
   (job ingestion/scraping) exactly as-is; only the stage after it changes.

## Explicitly out of scope

- **No LLM calls of any kind** — this is the core design constraint, not a nice-to-have. If a future
  session wants to revisit automating Stage 0 itself (the CR-070 Epic 5 direction discussed earlier the
  same day), that's a distinct, separately-scoped decision — don't fold it into this pass.
- **Don't touch `data/submissions/`** or its existing structure/conventions.
- **Don't build any UI for the review folder** — Jason reads it via a Claude Code chat session, not a new
  app page. If a "N jobs waiting for review" indicator somewhere in the app turns out to be genuinely
  wanted later, that's a separate ask.

## Verification before calling this done

1. Run a real Sync from the app UI. Confirm new qualifying jobs produce `Original_JD.txt` files in the
   review folder, correctly formatted (URL line where known, matching the existing convention).
2. Run Sync a second time immediately after with no new postings — confirm nothing gets re-exported or
   duplicated.
3. Confirm the SCRAPE stage's existing behavior (job ingestion into `jobs` table) is unaffected.
4. Report back: the folder location chosen, the idempotency mechanism used, and the result of both Sync
   runs above.
