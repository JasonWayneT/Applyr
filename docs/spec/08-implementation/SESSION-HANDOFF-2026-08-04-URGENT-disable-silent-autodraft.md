# SESSION HANDOFF — 2026-08-04 — URGENT: disable silent auto-draft in the Sync pipeline

**Priority: above the legacy-pipeline archiving work in the other 2026-08-04 handoff docs.** That task is
code hygiene. This one is live behavior Jason didn't know was still happening.

## What was found

While investigating your own prior finding (`batch_pipeline.py`/`draft_compiler.py` still wired to three
server call sites: `server/routes/jobs/draft.ts`, `server/routes/pipeline.ts`, `server/scout.ts`), a
Claude Code session traced all three instead of assuming they were equivalent. They are not:

- **`draft.ts`** (the UI "Draft" button on Sync Activity) — confirmed dead by Jason. Fine to remove
  whenever the rest of this lands.
- **`scout.ts`** — this is the one that matters. `SyncActivityView.tsx`'s **"Sync"** button
  (`POST /api/sync`, `SyncActivityView.tsx:343`) — a routine, everyday action, not an admin/rare one —
  triggers a full SCRAPE → EVALUATE pipeline. The EVALUATE stage (`server/scout.ts` ~line 176-225):
  1. Explicitly **starts local Ollama** ("Ensuring Ollama is running before evaluate/draft stage")
  2. Runs `batch_pipeline.py --mode batch`, logged as "Evaluating fit and generating PDF assets"

  This means every routine Sync may be **silently generating draft Resume/CoverLetter PDF assets** via the
  old Ollama-based deterministic pipeline, entirely outside the `generate-submission` Claude Code process
  (Stage 0 fit-gating, Stage 1 truth-grounded authoring, Stage 2 rubric scoring + no-ai-slop pass) that is
  the actual current standard for this codebase. This directly contradicts CLAUDE.md's own stated
  assumption that "the default drafting pipeline calls zero local LLMs by design (since CR-017)" — that's
  true of `generate-submission`, apparently not true of this separate automated path.

**Jason confirmed live, in chat: he did not know this was still happening.** Treat this as a real
correctness issue, not a hygiene item.

## Update (same day, resolved): fit-scoring does NOT need to be preserved

Originally this doc asked whether `jobs.score` (Ollama-based fit-scoring, bundled into the same
`batch_pipeline.py --mode batch` call as drafting) needed to survive separately from the drafting call.
**Resolved — no investigation needed.** A follow-up design decision (see the companion handoff,
`SESSION-HANDOFF-2026-08-04-sync-review-queue.md`) replaces this whole stage with a deterministic,
non-LLM role filter + JD export step. Stage 0 fit judgment now happens exclusively later, live, in a
Claude Code chat session — not automatically during Sync at all. **You can remove the entire
`batch_pipeline.py --mode batch` call outright**, including whatever Ollama-based scoring it did. Don't
spend time trying to decouple or preserve it.

## What to do

1. **Remove the `batch_pipeline.py --mode batch` call entirely** from `scout.ts`'s EVALUATE stage —
   including whatever Ollama-startup/scoring it did (see the resolved update above; nothing here needs
   preserving). This can land in the same pass as the companion handoff's replacement step
   (`SESSION-HANDOFF-2026-08-04-sync-review-queue.md`) — do them together, EVALUATE shouldn't be left
   doing nothing in between. Confirm with a real Sync run afterward (via the actual UI, not just a code
   read) that no new `Resume.pdf`/`CoverLetter.pdf` appear in `data/submissions/` from a Sync alone.
2. **Then remove `draft.ts`'s dead UI button/route** (confirmed dead by Jason) as part of the same pass or
   the next one — low risk, already confirmed safe.
3. **Do not touch `server/routes/pipeline.ts`'s `/api/evaluate` call yet** — traced to
   `src/hooks/usePipeline.ts:44`, not yet investigated for what triggers it or whether it's live. Flag it
   back rather than guessing.

## Explicitly out of scope for this handoff

- Archiving `batch_pipeline.py`/`draft_compiler.py` themselves — they're still Tier 2 (LIVE) via this
  exact wire. Don't move them yet; that's the separate, lower-priority isolation task once (and if) this
  wire is fully and deliberately cut.
- Auditing what's already been produced by this path historically (`data/submissions/`,
  `jobagent.sqlite`) — Jason was asked directly and chose to address it going forward rather than do a
  historical forensic pass right now. Don't add that scope unprompted.

## Verification before calling this done

1. Run a real Sync from the actual running app UI. Confirm via `logActivity`/console output that EVALUATE
   no longer starts Ollama or spawns `batch_pipeline.py` at all.
2. Confirm no new files appear in any `data/submissions/*/` folder as a result of that Sync run.
3. Confirm the companion handoff's replacement step (JD export to a review folder) ran in EVALUATE's
   place — see `SESSION-HANDOFF-2026-08-04-sync-review-queue.md` for what "done" looks like there.
4. Report back: confirm removal, and the real Sync-run verification result.
