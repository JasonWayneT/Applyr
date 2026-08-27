# Stage 0 Speed Investigation, Plain-English Learning Note

## Why this document exists

This is a plain-English recap of an investigation into why Applyr's first job
screening step takes a long time, what we tried to speed it up, and what we
learned.

It is intentionally written for someone who does not work with software,
artificial intelligence, or local models every day.

## The short version

Applyr has a first screening step called **Stage 0**. It reads a job posting and
decides whether the role looks promising, questionable, or unsuitable before
time is spent writing a resume and cover letter.

Stage 0 is slow because it asks local AI models many small, careful questions
about each job posting. One real job took about **117 seconds**, or almost two
minutes. A batch of many jobs can therefore take well over an hour.

We found one safe small speed improvement and turned it on for batch work. We
also tested two larger shortcuts. Both larger shortcuts were rejected because
they could make incorrect decisions about Jason's job search.

The important outcome is:

> We chose accuracy over speed. The system will not pretend that a word match
> means Jason has the right experience.

## What is Stage 0?

Think of Stage 0 as a careful first reader of a job posting.

It does four main things:

1. **Reads the job posting.**
2. **Pulls out the important requirements.**
   For example: “five years of product management,” “strong SQL knowledge,”
   “healthcare experience,” or “people management.”
3. **Compares each requirement with Jason's verified work history.**
4. **Places the job into a bucket.**
   - **Tier 1:** strong fit
   - **Tier 2:** possible fit, but needs careful review
   - **Skip:** not a sensible role to pursue

Stage 0 is not allowed to invent qualifications. It uses
`workExperience.md`, Jason's private ground-truth record, as the source for
what can honestly be claimed.

## Why is it slow?

Applyr uses two local AI models. “Local” means they run on Jason's own computer
instead of sending job postings and work-history material to a paid cloud AI
service.

The models have different jobs:

- **Qwen** reads the job posting and sorts its text into sections such as
  required qualifications, preferred qualifications, and responsibilities.
- **Gemma** looks at one job requirement at a time and judges whether Jason's
  verified experience is direct, partial, adjacent, or absent.

For a typical job, the process looks like this:

```text
Read one job posting with Qwen
  ↓
Ask Gemma about requirement 1
Ask Gemma about requirement 2
Ask Gemma about requirement 3
...
Ask Gemma about requirement 14
```

The word **sequentially** matters here. The questions happen one after another,
not all at once. Running them all at once could overload the computer's video
memory and cause failures.

### What is video memory?

Video memory, also called **VRAM**, is fast memory on the graphics card.
AI models use it while they are thinking. It is limited, similar to a workbench
with limited space.

Qwen and Gemma cannot safely sit on that workbench at the same time on this
machine. Applyr must clear one model out before loading the other.

## What was the measured result?

We ran one complete, real Stage 0 evaluation for the Fragomen job posting.

Result:

```text
1 Qwen job-reading call
14 Gemma requirement-judgment calls
117.3 seconds total
```

This means the major time cost is not opening a file or moving a folder. The
major time cost is the repeated AI thinking for every requirement.

## Safe improvement we made

Before the improvement, each job did three video-memory cleanup steps:

```text
1. Clear space before Qwen reads the job
2. Clear space before Gemma judges requirements
3. Clear space again after the job is finished
```

For a large batch, step 3 was unnecessary. The next job immediately performs
step 1 anyway.

We added an explicit batch setting:

```text
STAGE0_BATCH_KEEP_ALIVE=1
```

With that setting, the final Gemma model remains loaded until the next job
starts. The next job still clears the model before loading Qwen, so the safety
boundary remains in place.

This is a real but modest improvement. It removes unnecessary cleanup work.
It does **not** remove the 14 careful Gemma judgments.

## Why not use simple word matching?

Earlier versions of the system relied more heavily on regular expressions,
often called **regex**. Regex is a way for software to look for literal words
or word patterns.

Example:

```text
Job posting says: “Strong Jira knowledge”
Work history contains: “Jira”
```

A simple word-matching system may say: “Match found. Good fit.”

That is unsafe. The word “Jira” alone does not tell us:

- how deeply Jason used it
- whether he owned the relevant workflows
- whether the job also requires Scrum, Kanban, Trello, or another tool
- whether the requirement is about a specific kind of delivery work

Literal matches miss context. That was the original problem that caused the
move toward AI judgment in the first place.

## Shortcut test 1: automatically trust exact verified word matches

We tested a conservative version of the idea, but only in **shadow mode**.

Shadow mode means:

- the experiment reads existing decisions
- it makes no changes to real job results
- it cannot move a job, change a tier, or create an application

The experiment looked for exact phrases that appeared both:

1. in a job requirement, and
2. in Jason's verified claim tags or skills list.

Then it asked: did Gemma also think that requirement was a strong, direct
match?

Results:

```text
Existing Stage 0 files examined:           107
Exact phrase-match candidates found:       111
Candidates with comparable Gemma results:   38
Gemma agreed they were direct matches:      16
Gemma did not agree:                        22
```

In plain English, exact matching was wrong too often. More than half of the
comparable cases would have treated a requirement as safely satisfied when the
careful model judged it as incomplete or only partially supported.

Conclusion:

> Exact word matches must not bypass the AI judgment.

## Shortcut test 2: ask Gemma about several requirements at once

Another idea was to ask Gemma about two job requirements in one response
instead of making two separate calls.

This would have been faster if it worked reliably.

The test was also run in shadow mode. It did not change any real job decision.

The result was unsafe: Gemma returned malformed structured data twice.

“Malformed structured data” means the answer was supposed to follow a strict
computer-readable format, but it came back incomplete or broken. A system
cannot safely make job-search decisions from an answer it cannot reliably read.

Conclusion:

> The current small local Gemma model is reliable enough for one carefully
> structured requirement at a time, but not reliable enough for multi-item
> structured answers in this workflow.

## What we did not do

We did not:

- switch to a weaker model
- use cloud AI as a silent fallback
- send private work-history information to a paid provider
- let keyword matching decide whether to skip a job
- run multiple AI judgments at once and risk a VRAM crash
- alter any real Stage 0 result during the experiments

## What is happening with the real job batch?

The real job batch was imported through the normal Applyr process.

At the time this note was written:

- 51 CSV rows mapped to job folders
- 17 folders had completed Stage 0 during the earlier run
- 34 folders remained to be processed
- the remaining 34 were launched with the safe batch VRAM improvement enabled

No manual filtering, manual tier assignment, or forced outcome is being used.
Each job continues through the same Stage 0 rules.

## What could make Stage 0 much faster later?

A major speed improvement is still possible, but it needs proof before it can
be trusted.

The most promising future path is:

1. Keep AI job-requirement extraction.
2. Use verified evidence only to retrieve the most relevant work-history
   passages.
3. Let the AI judge every ambiguous requirement one at a time.
4. Test whether a stronger local model can reliably judge several requirements
   at once in structured form.
5. Compare every test result against the current careful method before changing
   real decisions.

The key rule is simple:

> Faster is only better if it does not make Jason miss a good role or spend
> time on a bad one.

## Glossary

**AI model**  
Software trained to understand and generate language. In this process it reads
job postings and compares them with verified work history.

**Batch**  
A group of jobs processed together.

**Cloud model**  
An AI model running on another company's computers. It normally requires an
internet connection and may cost money or involve sending private data out.

**Direct evidence**  
Verified work experience that clearly satisfies a job requirement at a similar
level of responsibility and scope.

**Gemma**  
The local AI model that judges one job requirement against Jason's verified
experience.

**Ground truth**  
The source that defines what is true. Here, it is Jason's verified work-history
material, not a guess or an AI-generated statement.

**Qwen**  
The local AI model that organizes a job description into useful sections.

**Regex**  
Simple software pattern matching. It is good at finding literal text but poor
at understanding meaning, depth, and context.

**Shadow mode**  
An experiment that measures a possible change without allowing it to alter
real job decisions.

**Stage 0**  
Applyr's first job-screening step, before resume and cover-letter drafting.

**Structured output**  
An AI answer returned in a strict machine-readable format. This lets software
read the answer safely, if the model produces it correctly.

**Tier 1 / Tier 2 / Skip**  
Stage 0's outcome labels. Tier 1 is a strong fit, Tier 2 needs careful review,
and Skip is not a sensible role to pursue.

**VRAM**  
Video memory on the graphics card. Local AI models need this limited resource
while they run.
