# Applyr System Invariants

This is the compact engineering reference for behavior that must not drift
during refactors. The detailed requirements and change requests remain
authoritative for implementation decisions.

## Truth and authoring

1. `data/workExperience.md` is the source of truth and runtime evidence.
2. `data/master_claims.json` is an index of IDs, tags, lenses, attribution,
   and prohibited claims. Its legacy `text` and `cover_story` fields are not
   authoring evidence.
3. Stage 1 is closed-world. The author may use only the packet's claim IDs,
   retrieved WorkExperience excerpts, constraints, and rule digest.
4. Every generated resume bullet and cover-letter proof point must have
   provenance tied to a real, non-disabled packet claim.
5. A missing, disabled, stale, or unverifiable evidence handoff blocks the
   relevant stage rather than being silently guessed around.

## Workflow authority

1. `scripts/run_submission.py` is the canonical submission entry point.
2. `workflow_state.json` and `stage_receipts/` are written by the workflow
   runner, not by agents or UI code.
3. Stage order is Stage 0 fit gate, Stage 1 authoring, Stage 2 Truth/ATS/HM/
   Mech/Policy review, then explicit Stage 3 finalization.
4. Stage 2 reviewers produce findings and dispositions. They do not rewrite
   application documents.
5. Content hashes make downstream receipts stale after document edits.
6. Production database writes happen only during explicit finalization.

## Safety and privacy

1. Private career data, credentials, submissions, and the local database stay
   under `data/` and are never committed.
2. Stage 0 requirement extraction and scoring use pinned local models and must
   not silently fall back to a paid cloud provider.
3. Hard gaps are not papered over with transferable-skill language.
4. Mechanical checks must run against both documents as a pair.
5. Human review remains required for qualitative conversion judgment.

## Derived artifacts

1. `master_claims_tags_only.json`, context packs, summaries, packets, receipts,
   and PDFs are derived artifacts, not independent sources of truth.
2. Derived artifacts must be regenerated through their project scripts.
3. A document is not complete because a manifest says it is complete. The
   verification receipt, freshness check, required fields, and workflow state
   must agree.

## Interview preparation boundary

1. Interview prep must reuse the same WorkExperience/claims truth model.
2. Interview debriefs are stored in `interview_debriefs`, not in a second
   parallel question store.
3. Draft interview answers are not confirmed facts until the user confirms
   them.
4. Any new fact discovered during prep needs an explicit path back into the
   canonical WorkExperience record before it can influence application
   documents.
