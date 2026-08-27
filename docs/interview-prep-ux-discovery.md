# Interview Prep UX Discovery Brief

**Status:** Discovery only. Do not implement schema or API work from this
document until the journeys and decisions are confirmed.

## Goal

Bring the existing manual interview-prep workflow into Applyr without creating
a second, drifting version of Jason's experience. The first design activity is
to map the user's actions, decisions, and confirmation points.

## Journeys to map

### 1. First run

- What does the user see when no stories exist?
- Can existing story-library material be imported?
- What must the user confirm before a story becomes reusable?
- How are missing or uncertain facts surfaced?

### 2. Prepare for a specific interview

- How is a job selected?
- What does Applyr show from the JD, resume, cover letter, and prior debriefs?
- Which questions are generated, imported, or manually added?
- How does the user distinguish likely questions from questions actually asked?

### 3. Log a debrief

- What is the fastest useful post-interview capture?
- When does free text become a discrete question?
- Is extraction automatic, manual, or reviewed before saving?
- How are unanswered or surprising questions flagged?

### 4. Find a preparation gap

- What does “gap” mean: no story, weak story, unconfirmed fact, or missing
  question coverage?
- What evidence does the user need to understand the gap?
- What action should close it?

### 5. Draft and confirm an answer

- What answer formats are useful: STAR, concise spoken answer, or both?
- Which parts are sourced facts versus delivery guidance?
- How are draft, user-edited, and confirmed states represented?
- What happens when the answer reveals a new fact?

## Decisions required before implementation

1. Import existing stories, guided creation, or both.
2. Free-text debrief only versus reviewed question extraction.
3. Local LLM default and explicit cloud-provider disclosure.
4. Story lifecycle: draft, confirmed, retired.
5. Fact-sync workflow back to `workExperience.md` and the claim index.
6. Dedicated Interview Prep screen versus job-detail-first experience.

## Existing constraints to preserve

- Reuse `interview_debriefs` as the source for post-interview notes.
- Reuse the existing LLM provider infrastructure rather than creating a
  second key-management path.
- Keep sensitive interview content local by default.
- Never treat an LLM-generated answer as verified experience automatically.
- Follow the onboarding pattern in `FEAT-010`.
