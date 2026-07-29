# Interview Prep Module — Thinking Doc (Working)

**Status:** Exploration — not ready to build. This captures decisions and open questions across multiple sessions so any future session (Claude, Cursor, or Jason) can pick this up cold.
**Last updated:** 2026-07-02

---

## Why this exists

`docs/IDEAS.md` already has "Granular Interview Tracking" open. Two related-but-distinct features came out of thinking about it:

1. **Interview Debrief** — small, scoped, already handed to Cursor to build (see below).
2. **Interview Prep Module** — much bigger: bring the manual prep workflow currently living in `Projects/Job Hunt/*.md` (a story library + gap tracking + LLM-assisted answer scripting, driven by a reusable prompt fed to fresh Claude sessions) into Applyr itself, as both structured data and in-app LLM drafting.

This doc is about #2. It is **not ready to build** — see Sequencing Decision below.

---

## Feature 1 (separate, smaller, already scoped): Interview Debrief

Decided 2026-07-02, handed to Cursor. Included here so this doc is self-contained.

- **Storage:** new `interview_debriefs` SQLite table (`job_id`, `date`, free-text `notes`, `outcome`) + CRUD API. Not a per-job JSON file, not a JSON-mirror hybrid — the table is the source of truth so later cross-job features can query it.
- **Capture UI:** one free-text dump box in `JobDetailPanel`, below Interview Schedule, separate from `Interview_Cheat_Sheet.md` (pre-interview prep vs. this, which is post-interview). No structured round-type/question-row fields in v1 — the bet is that Jason will write *something* right after a call only if it's frictionless.
- **v1 also includes:** debrief list on the job, activity log entry on save (mirrors the `RubricLog` pattern).
- **Deferred:** round types, cross-job question bank UI, TodayView "debrief this call" nudge, LLM-suggested cheat sheet additions.
- **Standing constraint:** any future interview-prep feature (including the module below) reads from `interview_debriefs` — no second/parallel storage for interview feedback.
- **Real test case:** the Hudu interview debrief (7 expected questions plus one unprepped one — "how do you stay current with the industry" — that wasn't on the cheat sheet).

---

## Feature 2: Interview Prep Module

### The existing manual workflow it would replace

Built 2026-07-01 in `Projects/Job Hunt/` (see `session-handoff.md` there for full detail):

- `star-story-library.md` — 14 STAR stories, voice-calibrated, coverage table
- `real-interview-questions.md` — living log of real questions mapped against the library, already flagging gaps (2 flagged after Hudu: vision-setting, early-stage/fast-moving)
- `pm-interview-prep-prompt.md` — the reusable prep prompt fed to a fresh Claude session to script answers, customize for a JD (Step 6), etc.
- Ground truth shared with Applyr already: `Applyr/data/workExperience.md` and `Applyr/data/master_claims.json` — the resume/cover-letter pipeline and this prep workflow are supposed to share one source of truth.

### Decisions made so far (directional, not final — see Sequencing Decision)

1. **LLM routing — reuse, don't rebuild.** Applyr already has a full multi-provider LLM system from the resume pipeline (`CR-006`, `FEAT-007`): `scripts/utils.py:call_llm()` with a Gemini → Claude → Local(Ollama) → Perplexity fallback chain, keys in the SQLite `llm_settings` record, a 4-card provider UI in Settings with "Connected" badges and a configuration guard (no key = no call, no silent token waste). The interview prep module should call into this, not build new key management.
2. **New requirement layered on top:** interview content (real employer names, personal narrative, career history) is more sensitive than resume text. Add a per-feature override — `interviewPrepProvider` (nullable) in `llm_settings`. Null = local (Ollama) by default, regardless of the app's app-wide `primaryProvider`. Non-null = explicit opt-in to a cloud provider for this feature only. This needs to be a visible, explicit disclosure in the UI (e.g. a banner naming the active provider), not just a buried settings toggle.
3. **Data model direction:** a `stories` table (STAR fields + competency tags + `source_claim_ids` pointing into `master_claims.json`/`workExperience.md`), seeded once from the 14 existing stories in `star-story-library.md`. A `question_story_links` join for gap tracking (question ↔ story ↔ coverage status).
4. **Storage constraint carried over from Feature 1:** this module reads from `interview_debriefs`, it does not become a second place where "what was asked" lives.

### Open gaps identified (2026-07-02 review, unresolved)

1. **Debriefs are free text; gap-tracking needs discrete questions.** `interview_debriefs` is intentionally an unstructured dump box. Nothing yet defines how individual questions get pulled out of that text into linkable rows — manual extraction step, or LLM-assisted parsing.
2. **Local-model quality risk.** The July 1 rebuild was explicitly about rejecting scripts that "read corporate/LLM." Local models via Ollama are generally weaker at that kind of voice-matching than Claude/Gemini. Defaulting to local for privacy is still likely right, but expect local drafts to need heavier manual editing — set that expectation rather than assume parity.
3. **Ground-truth sync rule has no home yet.** The old workflow's standing rule: new facts surfaced during prep fold into `workExperience.md` AND `master_claims.json`, keeping prep and the resume pipeline on one truth. Nothing in the new plan currently preserves that loop — a fact surfaced while drafting an answer could get stuck in the story library and never reach the resume pipeline.
4. **Fate of the old markdown files undecided.** Once stories live in the database, are `Projects/Job Hunt/*.md` frozen as historical record, or still touchable? If still touchable, they'll drift from the DB.
5. **No draft-vs-confirmed state on scripted answers.** The old workflow tracked verification explicitly (`[VERIFY]` tags, a full verification log before anything was "done"). An LLM-drafted answer — especially from a weaker local model — probably shouldn't be treated as finished the moment it's generated.

### Onboarding (raised 2026-07-02, unresolved)

Jason wants a first-run onboarding experience for this module, and it connects directly to gap #3 above: as new information is found (during onboarding or later use), it should fold into both `workExperience.md`/`master_claims.json` (existing system) and this module's stories/gaps (new).

**Precedent already in Applyr — reuse this pattern, don't invent a new one.** `FEAT-010` (Master Career Experience Onboarding, implemented) solved a structurally similar problem for the Experience tab: an empty-state onboarding card (explains the VOC/MET/ACC system before the user pastes anything) vs. an active-state status bar (live code counts) once content exists, gated on a simple content-length heuristic, plus a collapsible "how to edit safely" guide. Interview Prep's onboarding should likely follow the same empty-state/active-state shape rather than a new pattern.

**Open questions for the UX session:**
- Does onboarding include an automatic import/seed step (bring in the 14 existing stories), a from-scratch guided flow, or both?
- When new information surfaces (onboarding or later), does it save once and propagate to both `workExperience.md`/`master_claims.json` and the stories/gaps system, or are these two distinct save actions the user takes separately?

### Sequencing decision (2026-07-02)

This is a bigger build than first scoped. Before further technical design: **run a UX-first session** — map the actual user journeys (onboarding, logging a debrief, seeing a gap, drafting an answer, confirming a script) — before locking the data model or API shape further. Everything under "Decisions made so far" above is directional, not final; expect it to flex once the journeys are mapped.

### Next session should

1. Start with user journeys / UX, not schema or API design.
2. Revisit the 5 open gaps once journeys are mapped — several may resolve naturally once a flow is concrete (e.g. question extraction might just fall out of the "log a debrief" journey design).
3. Re-confirm the LLM routing decision (local default + per-feature override, disclosed in-UI) still holds once onboarding is designed — onboarding may be the first place this needs to surface to the user.
4. Only after journeys + open questions are resolved: write the formal `FEAT-XXX` spec and hand off to Cursor, the way Interview Debrief already was.

---

## Related files

- `docs/IDEAS.md` — original "Granular Interview Tracking" idea entry
- `docs/spec/03-feature-specs/FEAT-010-experience-onboarding.md` — onboarding pattern to reuse
- `docs/spec/05-change-requests/CR-006-llm-provider-architecture.md`, `FEAT-007-multi-llm.md` — LLM provider system to reuse
- `Projects/Job Hunt/session-handoff.md` — the manual workflow this module would eventually replace
- `data/workExperience.md`, `data/master_claims.json` — shared ground truth this module must stay in sync with
