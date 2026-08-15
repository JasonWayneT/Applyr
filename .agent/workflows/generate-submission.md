This repo has a mandatory, already-written process for drafting or reviewing a job application
(resume + cover letter). Do not invent your own structure from general resume-writing instinct
-- read the real files first, in this order:

1. Read `AGENTS.md` (repo root) in full. It owns the hard rules -- anti-hallucination, forbidden
   language, PII/exclusion zones, the required document structure and 1-page rule. Verified
   metrics and approved accomplishments (MET-*/ACC-*) live in `data/workExperience.md`, not here.
2. Read `.claude/skills/generate-submission/SKILL.md` in full. It owns the actual sequence:
   Stage 0 (fit screen, before any drafting) -> Stage 1 (author) -> Stage 2 (verify) ->
   Stage 3 (finalize). Follow it literally, in order, as written -- do not paraphrase from
   memory or reconstruct it from a prior session.
3. No web search or company research at any stage, for any reason -- this process is
   explicitly offline. Every claim traces to `data/workExperience.md`,
   `data/master_claims_tags_only.json` (tags only, never its `text`/`cover_story` fields),
   `data/conversion_rubric.md`, or `data/candidate_preferences.json`.
4. Before reporting any submission as done, run the commands in `SKILL.md`'s "Required
   Verification (before reporting any real submission done)" section and show the real output,
   not a summary. Every `ATTENTION` flag must be checked against the actual document and resolved
   before calling anything finished.
5. If anything is ambiguous -- a fit call you can't resolve from the JD text, a gap with no
   honest bridge, a blocked-industry judgment call -- stop and ask. Do not guess and do not
   search the web to resolve it.

Do not restate or duplicate the rules from `AGENTS.md`/`SKILL.md` into this file or into any
other file -- if a rule here ever needs to change, it changes there, not here. This file is a
pointer, nothing else.
