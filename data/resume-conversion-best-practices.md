# Resume Conversion Best Practices for AI Resume Generation

```yaml
document_type: resume_conversion_reference
primary_objective: create_a_targeted_resume_that_converts
intended_reader: ai_resume_generation_agent
human_readable: true
inputs:
  - master_work_history_or_cv
  - target_job_description
output:
  - targeted_resume
optimization_order:
  - truthfulness
  - target_job_relevance
  - recruiter_skim_value
  - ats_parseability
  - evidence_density
  - concise_readability
forbidden_behaviors:
  - inventing_metrics_or_claims
  - copying_the_full_master_cv
  - keyword_stuffing
  - using_generic_ai_resume_language
  - prioritizing_format_creativity_over_parseability
  - including_content_that_does_not_support_target_fit
```

## Purpose

This reference defines the rules an AI should apply when converting a master CV, work-history archive, or long-form career document into a targeted resume for a specific job description. The goal is not to summarize the candidate’s full career. The goal is to produce a resume that quickly proves fit to recruiters, hiring managers, ATS systems, and AI-assisted screening workflows.

Use this document as the resume-generation quality standard. Apply the rules in priority order. If rules conflict, prefer truthfulness, target-job relevance, fast skim value, and evidence-backed accomplishments over completeness.

## Operating Definition of a Resume That Converts

A converting resume earns the next step because the reader or screening system can quickly answer: “Does this candidate appear qualified, relevant, and worth interviewing?” Recruiters make initial fit judgments quickly, and the Ladders eye-tracking study found that recruiters spent about 6 seconds on initial resume review and concentrated most review time on name, current title, current company, previous title, previous company, and education ([TheLadders eye-tracking study hosted by Boston University](https://www.bu.edu/com/files/2018/10/TheLadders-EyeTracking-StudyC2.pdf)). ATS systems also categorize and rank resumes using employer-specified keywords, so the resume must be both parseable by software and persuasive to humans ([Indeed ATS resume guide](https://www.indeed.com/career-advice/resumes-cover-letters/ats-resume)).

### Conversion Criteria

| Criterion | AI implementation rule | Pass condition |
| --- | --- | --- |
| Fast relevance | Put the strongest target-match evidence in the top third of the resume. | A recruiter can infer target-role fit in 6 to 10 seconds. |
| ATS parseability | Use standard sections, simple formatting, and exact job-description terminology where truthful. | The resume can be copied into plain text without losing meaning or reading order. |
| Evidence density | Prefer accomplishments, outcomes, metrics, scope, tools, and business impact over responsibility summaries. | Most bullets prove what changed because of the candidate. |
| Role specificity | Tailor content to the target job rather than dumping all experience into one document. | Every included section supports the target role or explains a required qualification. |
| Human readability | Remove filler, generic adjectives, long narratives, and dense blocks. | The resume is easy to skim and has clear hierarchy. |
| Truthfulness | Never invent employers, titles, dates, tools, metrics, credentials, or outcomes. | Every claim can be traced to the master work history or explicitly marked as inferred only if allowed by the user. |

## Source Signals the AI Must Extract Before Writing

Before drafting, extract and rank the following from the job description and master work history.

### From the Job Description

| Signal | Extraction instruction | Use in resume |
| --- | --- | --- |
| Target title | Capture the exact role title and close variants. | Align summary headline, title framing, and experience emphasis. |
| Must-have skills | Identify repeated hard skills, required tools, methodologies, certifications, domains, and years of experience. | Include only skills the candidate actually has; place highest-value matches in summary, skills, and experience bullets. |
| Job outcomes | Extract what the hire is expected to improve, build, manage, reduce, increase, launch, automate, analyze, or own. | Rewrite bullets around similar outcomes from the candidate’s history. |
| Seniority signals | Detect verbs such as lead, own, manage, define, execute, support, collaborate, architect, scale, or optimize. | Match bullet language to the expected level of ownership. |
| Domain vocabulary | Capture product category, industry terms, customer type, GTM model, technical ecosystem, and business model. | Use truthful matching terms to improve pattern recognition for ATS and human readers. |
| Evaluation themes | Infer what the employer likely values most: revenue, efficiency, quality, speed, customer impact, compliance, strategy, analytics, leadership, or technical execution. | Prioritize evidence that proves those themes. |

### From the Master Work History

| Signal | Extraction instruction | Use in resume |
| --- | --- | --- |
| Closest-fit roles | Rank previous roles by similarity to the target job. | Allocate the most space and strongest bullets to the highest-fit roles. |
| Achievements | Extract outcomes with metrics, scope, stakeholders, tools, and before-after contrast. | Convert into achievement bullets. |
| Transferable evidence | Identify adjacent work that maps to target outcomes even if job titles differ. | Reframe using target-role language while preserving truth. |
| Tool and skill proof | Find where skills were actually used, not merely listed. | Include skills in bullets when possible, not only in the skills section. |
| Recency | Rank recent evidence above older evidence unless older evidence is dramatically more relevant. | Keep older content short unless it is a direct target-role proof point. |
| Differentiators | Identify rare combinations, domain expertise, scale, leadership, speed, or business impact. | Surface in summary and top bullets. |

## Priority Order for Resume Content

Use this order when selecting what to include. Do not optimize for completeness. Optimize for fit signal density.

1. **Direct match evidence**: Experiences that closely match the target job’s core responsibilities, required skills, domain, and outcomes.
2. **Measured impact**: Bullets with quantified results, business outcomes, scope, volume, velocity, cost, revenue, efficiency, quality, or adoption.
3. **Recent senior evidence**: Recent roles, ownership level, leadership, strategy, launches, stakeholder management, or technical execution that maps to the target level.
4. **Keyword-backed proof**: Skills and tools from the job description demonstrated in context.
5. **Transferable proof**: Adjacent accomplishments that support the job’s problems even if the exact industry or title differs.
6. **Credential support**: Education, certifications, training, or portfolio links only where they increase confidence.
7. **Everything else**: Exclude unless it prevents a gap or provides a clear conversion benefit.

## Hard Rules

### R-001: Tailor Every Resume to One Job Description

Do not produce a generic resume from the master CV. Harvard advises tailoring the resume to the type of position sought so it reflects the skills the employer values, and NACE highlights that candidates must connect experiences to skills and communicate that value to employers ([Harvard FAS resume guide](https://careerservices.fas.harvard.edu/resources/create-a-strong-resume/), [NACE best practices](https://www.naceweb.org/career-readiness/best-practices/)). The AI must create one resume per target job description.

### R-002: Reject the “Everything I Have Done” Resume

Do not include all experience simply because it exists in the master work history. NACE identifies one of the biggest resume mistakes as dumping everything into one document and using that same document for all jobs ([NACE best practices](https://www.naceweb.org/career-readiness/best-practices/)). The AI must treat the master CV as a source database, not as the resume outline.

### R-003: Optimize the First Screen, Not the Full Career Story

Place the highest-value evidence where skim readers will see it first. The Ladders study found that recruiters spent nearly 80% of review time on name, current title, current company, previous title, previous company, and education, with initial decisions happening in about 6 seconds ([TheLadders eye-tracking study hosted by Boston University](https://www.bu.edu/com/files/2018/10/TheLadders-EyeTracking-StudyC2.pdf)). The AI must make title alignment, current role relevance, company context, and top achievements immediately visible.

### R-004: Write for Both ATS and Human Readers

The resume must be machine-parseable and human-persuasive. Indeed explains that ATS systems scan resumes for targeted employer keywords, categorize content, and rank resumes by match, but recruiters still review selected resumes after the ATS stage ([Indeed ATS resume guide](https://www.indeed.com/career-advice/resumes-cover-letters/ats-resume)). The AI must integrate keywords naturally into credible context rather than creating a keyword list that fails human review.

### R-005: Use Standard Section Headings

Use standard headings such as “Professional Summary,” “Skills,” “Professional Experience,” “Education,” “Certifications,” and “Projects.” ATS guidance warns that nonstandard headings can cause sections to disappear or be miscategorized, while standard headings help parsers identify experience, education, and skills ([Jobscan ATS formatting mistakes](https://www.jobscan.co/blog/ats-formatting-mistakes/), [Indeed ATS resume guide](https://www.indeed.com/career-advice/resumes-cover-letters/ats-resume)). The AI must avoid creative headings such as “My Journey,” “Superpowers,” “Where I’ve Been,” or “Toolkit.”

### R-006: Use Simple Single-Column Formatting

Assume the final resume must survive ATS parsing. Jobscan warns that columns, tables, graphics, text boxes, headers, and footers can scramble reading order or make text invisible to ATS parsers ([Jobscan ATS formatting mistakes](https://www.jobscan.co/blog/ats-formatting-mistakes/)). The AI must output a simple one-column structure with contact details and skills in the main body.

### R-007: Replace Responsibility Bullets With Outcome Bullets

Do not write bullets that only describe assigned duties. Harvard lists “not demonstrating results” as a top resume mistake and recommends specific, fact-based language that quantifies and qualifies experience ([Harvard FAS resume guide](https://careerservices.fas.harvard.edu/resources/create-a-strong-resume/)). The AI must convert duties into achievements whenever the source evidence supports an outcome.

### R-008: Use Action Verbs Without Inflating Claims

Start most bullets with strong action verbs and avoid passive language. Harvard recommends active language, action words, and concise expression rather than passive or flowery writing ([Harvard FAS resume guide](https://careerservices.fas.harvard.edu/resources/create-a-strong-resume/)). The AI must choose verbs that match the actual level of ownership, such as led, built, launched, analyzed, automated, reduced, increased, partnered, redesigned, prioritized, implemented, or synthesized.

### R-009: Integrate Keywords in Context

Do not stuff keywords. Jobscan distinguishes useful keyword optimization from keyword stuffing, warning against dishonest skills, hidden text, and unnatural repetition ([Jobscan keyword stuffing guide](https://www.jobscan.co/blog/resume-keyword-stuffing/)). The AI must place critical keywords in the summary, skills, and experience bullets only when the candidate has real evidence for them.

### R-010: Preserve Truth Over Match Score

Never add a keyword, metric, tool, certification, title, or responsibility that is not supported by the master work history. Indeed advises only adding qualifications and experience the candidate actually has because recruiters verify information ([Indeed ATS resume guide](https://www.indeed.com/career-advice/resumes-cover-letters/ats-resume)). The AI must prefer a lower match score over a false or inflated claim.

## Section-by-Section Construction Rules

### Contact Header

| Rule ID | Rule | Implementation |
| --- | --- | --- |
| H-001 | Include only useful contact data. | Name, target location or remote availability if relevant, phone, email, LinkedIn, portfolio or GitHub if conversion-positive. |
| H-002 | Keep contact info in the main body. | Do not place contact information in headers, footers, tables, text boxes, icons, or images because ATS parsers may ignore those layers ([Jobscan ATS formatting mistakes](https://www.jobscan.co/blog/ats-formatting-mistakes/)). |
| H-003 | Remove distracting personal data. | Do not include photo, age, gender, marital status, or references; Harvard explicitly advises against pictures, age or gender, and references ([Harvard FAS resume guide](https://careerservices.fas.harvard.edu/resources/create-a-strong-resume/)). |

### Professional Summary

The summary must be 2 to 4 lines. It must answer: target role fit, domain relevance, strongest capabilities, and quantified credibility if available.

| Rule ID | Rule | Implementation |
| --- | --- | --- |
| S-001 | Make the first phrase target-aligned. | Use a truthful target identity such as “AI Product Manager,” “Technical Product Manager,” or “Product Manager specializing in AI automation.” |
| S-002 | Include 3 to 5 job-description-aligned capability themes. | Example themes: AI agents, workflow automation, product strategy, roadmap ownership, user research, analytics, GTM, SaaS, platform products. |
| S-003 | Include proof, not adjectives. | Replace “results-oriented strategic leader” with evidence such as “launched X,” “reduced Y,” “scaled Z,” or “owned roadmap for A.” |
| S-004 | Avoid generic summaries. | Harvard notes that generative AI should help revise and improve existing materials, but should not be the primary author because output is likely generic ([Harvard FAS resume guide](https://careerservices.fas.harvard.edu/resources/create-a-strong-resume/)). |

#### Summary Formula

```text
[Target-aligned professional identity] with [years or scope if useful] in [domain/function].
Proven strengths in [capability 1], [capability 2], and [capability 3], with evidence across [relevant environments].
Known for [differentiator] and [business/user outcome], supported by [metric, launch, portfolio, or scope].
```

### Skills Section

| Rule ID | Rule | Implementation |
| --- | --- | --- |
| SK-001 | Build the skills section from the job description and proof source. | Extract job-description keywords, then include only skills the master work history supports. |
| SK-002 | Prioritize hard skills and tools. | ATS systems often search for targeted skills and employer-specified keywords, so hard skills, tools, methods, and certifications should be easy to find ([Indeed ATS resume guide](https://www.indeed.com/career-advice/resumes-cover-letters/ats-resume)). |
| SK-003 | Group skills by useful categories. | Use categories such as Product, AI/Technical, Analytics, Research, GTM, Leadership, and Tools. |
| SK-004 | Avoid skill dumping. | Jobscan warns that giant skill blocks without demonstrated usage can look dishonest or out of context to recruiters ([Jobscan keyword stuffing guide](https://www.jobscan.co/blog/resume-keyword-stuffing/)). |
| SK-005 | Mirror exact terminology when truthful. | If the job description says “roadmap prioritization,” use “roadmap prioritization” instead of only “planning.” |

### Professional Experience

| Rule ID | Rule | Implementation |
| --- | --- | --- |
| E-001 | Allocate space by relevance, not chronology alone. | Keep reverse chronological order, but give more bullets to the most relevant recent roles. |
| E-002 | Make every bullet earn its space. | Each bullet must prove target-job fit, measurable impact, scope, tool proficiency, leadership, or domain expertise. |
| E-003 | Put the strongest bullet first under each role. | Recruiters skim quickly, so first bullets must carry the strongest conversion signal. |
| E-004 | Use context plus action plus result. | A bullet should show what the candidate did, how they did it, and why it mattered. |
| E-005 | Avoid first-person and narrative style. | Harvard advises against personal pronouns and narrative style in resumes ([Harvard FAS resume guide](https://careerservices.fas.harvard.edu/resources/create-a-strong-resume/)). |
| E-006 | Explain skill usage in bullets. | Jobscan recommends showing how skills were actually used rather than listing skills without context ([Jobscan keyword stuffing guide](https://www.jobscan.co/blog/resume-keyword-stuffing/)). |

#### Bullet Formula

Use this default bullet structure:

```text
[Action verb] [what was owned/built/improved] by [method, tool, collaboration, or decision] to [measured or observable result].
```

Use this when the result is not quantified:

```text
[Action verb] [scope or problem] by [method] resulting in [qualitative business, customer, operational, or product outcome].
```

Use this when rewriting a duty:

```text
Original duty: Responsible for [activity].
Converted bullet: [Action verb] [activity/object] for [audience/system/process], improving/enabling/supporting [target-job-relevant outcome].
```

### Projects

Include projects only when they strengthen target-role conversion. For AI, product, technical, or portfolio-driven roles, projects can provide proof of current capability when formal work history does not fully capture it.

| Rule ID | Rule | Implementation |
| --- | --- | --- |
| P-001 | Include projects that map directly to the target job. | Prioritize projects using the same domain, tools, users, workflows, or outcomes as the job description. |
| P-002 | Write project bullets like work-experience bullets. | Show product problem, user, technical approach, decision, trade-off, and outcome. |
| P-003 | Do not over-explain side projects. | Keep project descriptions concise and conversion-focused. |
| P-004 | Link only if the link helps the evaluator. | Include portfolio, GitHub, demo, case study, or live product links only when they are polished and relevant. |

### Education and Credentials

| Rule ID | Rule | Implementation |
| --- | --- | --- |
| ED-001 | Keep education parseable and concise. | Use standard institution, degree, field, location if needed, and graduation date if beneficial. |
| ED-002 | Prioritize required credentials. | If the job requires a degree, certification, security clearance, or license, make that credential easy to find. |
| ED-003 | Do not let education crowd out experience. | For experienced candidates, education usually supports the case rather than leading it unless the target job specifically values it. |

## Keyword Strategy

### Keyword Extraction Process

1. Extract exact repeated terms from the job description.
2. Separate hard requirements from nice-to-have terms.
3. Identify synonyms and equivalent terms from the candidate’s work history.
4. Keep exact terms when truthful and natural.
5. Place terms in three layers: summary, skills, and experience bullets.
6. Remove repeated terms that sound unnatural or unsupported.

Indeed recommends analyzing the job description for duties, skills, characteristics, patterns, and repeated terms before creating an ATS-focused resume ([Indeed ATS resume guide](https://www.indeed.com/career-advice/resumes-cover-letters/ats-resume)). Jobscan recommends keyword optimization that helps the resume pass ATS review and catch hiring-manager attention, but warns against hidden text, dishonest skills, and excessive repetition ([Jobscan keyword stuffing guide](https://www.jobscan.co/blog/resume-keyword-stuffing/)).

### Keyword Placement Rules

| Keyword type | Best placement | Bad placement |
| --- | --- | --- |
| Required tools | Skills section and a bullet showing usage. | Long tool list with no evidence. |
| Core responsibilities | Summary and top experience bullets. | Repeated unnaturally in every bullet. |
| Domain terms | Summary, role bullets, project bullets. | Added if the candidate has no domain connection. |
| Certifications | Education or certifications section. | Hidden in unrelated bullets. |
| Soft skills | Demonstrated through outcomes and collaboration bullets. | Generic lists such as “team player, communicator, leader.” |

### Keyword Integrity Test

For every keyword added, the AI must answer:

```text
1. Is this keyword explicitly in the job description?
2. Is this keyword supported by the master work history?
3. Is it placed where both ATS and humans can see it?
4. Is it used in a sentence that proves actual usage?
5. Would a recruiter believe this claim if asked in an interview?
```

If any answer is “no,” remove or rewrite the keyword.

## Evidence Selection Heuristics

### Scoring Matrix

Score each candidate achievement from the master work history before selecting bullets.

| Factor | Score 0 | Score 1 | Score 2 | Score 3 |
| --- | --- | --- | --- | --- |
| Job-description match | Unrelated | Adjacent | Relevant | Direct match |
| Outcome strength | Task only | Qualitative outcome | Measured outcome | Measured business/customer impact |
| Recency | Older than 10 years | 6 to 10 years | 3 to 5 years | 0 to 2 years |
| Scope | Individual task | Team/process | Cross-functional | Company, platform, revenue, customer, or strategic scope |
| Keyword support | No target terms | 1 minor term | 2 to 3 target terms | Multiple core target terms used truthfully |
| Differentiation | Common | Somewhat useful | Strong | Rare or highly relevant differentiator |

Include the highest-scoring achievements first. If two achievements tie, choose the one that is easier to understand in a 6-second skim.

### Bullet Inclusion Threshold

| Resume area | Minimum evidence score | Rule |
| --- | --- | --- |
| Summary | 14+ | Use only the strongest themes and differentiators. |
| First role, first 3 bullets | 13+ | Must strongly match the target job. |
| Other role bullets | 9+ | Include only if they support the target story. |
| Projects | 10+ | Include if they compensate for missing formal experience or prove target capability. |
| Skills | Supported evidence required | Include only if the candidate can defend the skill in an interview. |

## Bullet Quality Standard

### Required Bullet Traits

Each strong bullet should contain at least three of the following:

| Trait | Definition | Example signal |
| --- | --- | --- |
| Action | What the candidate did. | Built, led, launched, analyzed, automated, redesigned. |
| Object | What was affected. | Product roadmap, onboarding flow, bug triage process, AI agent, customer research program. |
| Method | How the work was done. | Using SQL, LLM evaluation, user interviews, prioritization framework, API integration. |
| Scope | Size or complexity. | Cross-functional team, enterprise customers, 10K users, multi-market rollout. |
| Outcome | What changed. | Increased adoption, reduced time, improved quality, accelerated release, clarified strategy. |
| Metric | Quantified proof. | 30%, 2x, $500K, 4 weeks, 12 stakeholders, 1M records. |
| Relevance | Connection to target job. | Uses target job terminology naturally. |

### Weak Bullet Patterns to Rewrite

| Weak pattern | Problem | Rewrite direction |
| --- | --- | --- |
| “Responsible for managing product roadmap.” | Duty, no outcome. | “Prioritized product roadmap across X stakeholders to deliver Y outcome.” |
| “Worked with engineering and design.” | Generic collaboration. | “Partnered with engineering and design to launch X, improving Y.” |
| “Used AI tools for automation.” | Vague and unproven. | “Built LLM-assisted workflow that reduced manual triage time by X.” |
| “Helped improve customer experience.” | Weak ownership and no evidence. | “Analyzed customer feedback and redesigned X flow, reducing Y friction.” |
| “Excellent communication and leadership skills.” | Unsupported soft-skill claim. | Show stakeholder alignment, executive briefings, conflict resolution, or team outcomes. |

### Bullet Compression Rules

| Rule ID | Rule |
| --- | --- |
| B-001 | Keep bullets to 1 to 2 lines where possible. |
| B-002 | Put the outcome before secondary detail when space is limited. |
| B-003 | Remove internal jargon unless the target employer uses it. |
| B-004 | Replace vague modifiers with evidence. |
| B-005 | Cut bullets that require a long explanation to matter. |
| B-006 | Prefer one strong quantified bullet over two weak descriptive bullets. |

## Resume Length and Density Rules

| Candidate situation | Recommended approach |
| --- | --- |
| Early career or highly focused application | One page unless critical evidence would be lost. |
| Mid-career with multiple relevant roles | One to two pages, with the first page carrying the conversion case. |
| Senior, technical, academic, federal, or complex domain roles | Two pages may be appropriate if every section has high relevance. |
| Long master CV | Never copy the whole source. Select and compress. |

Harvard defines a resume as a concise, informative summary of abilities, education, and experience, and it should highlight the strongest assets and differentiate the candidate from others seeking similar roles ([Harvard FAS resume guide](https://careerservices.fas.harvard.edu/resources/create-a-strong-resume/)). Jobscan also emphasizes limited resume real estate and warns against adding unimportant skills or broad lists that do not show useful proficiency ([Jobscan keyword stuffing guide](https://www.jobscan.co/blog/resume-keyword-stuffing/)).

## Formatting Rules for ATS and Skim Readability

| Rule ID | Rule | Rationale |
| --- | --- | --- |
| F-001 | Use a single-column layout. | Columns can scramble ATS reading order ([Jobscan ATS formatting mistakes](https://www.jobscan.co/blog/ats-formatting-mistakes/)). |
| F-002 | Avoid tables, graphics, charts, icons, and photos. | ATS systems may fail to parse visual elements, and Harvard advises against including pictures ([Jobscan ATS formatting mistakes](https://www.jobscan.co/blog/ats-formatting-mistakes/), [Harvard FAS resume guide](https://careerservices.fas.harvard.edu/resources/create-a-strong-resume/)). |
| F-003 | Use standard fonts. | Jobscan recommends web-safe fonts such as Arial, Calibri, Georgia, Helvetica, Tahoma, Verdana, Cambria, Garamond, Palatino, or similar readable fonts ([Jobscan ATS formatting mistakes](https://www.jobscan.co/blog/ats-formatting-mistakes/)). |
| F-004 | Keep dates consistent. | Jobscan warns that missing months, apostrophes, and inconsistent date formats can confuse ATS parsing ([Jobscan ATS formatting mistakes](https://www.jobscan.co/blog/ats-formatting-mistakes/)). |
| F-005 | Use main-body text only. | Headers, footers, and text boxes can be ignored by ATS parsers ([Jobscan ATS formatting mistakes](https://www.jobscan.co/blog/ats-formatting-mistakes/)). |
| F-006 | Save as PDF unless the employer requests DOCX. | Jobscan recommends PDF as safest when formatting rules are followed, unless another file type is requested ([Jobscan ATS formatting mistakes](https://www.jobscan.co/blog/ats-formatting-mistakes/)). |
| F-007 | Test plain-text readability. | Jobscan recommends copying the resume into plain text to detect icons, odd spacing, unreadable characters, or broken reading order ([Jobscan ATS formatting mistakes](https://www.jobscan.co/blog/ats-formatting-mistakes/)). |

## Anti-Patterns and Rejection Triggers

The AI must stop and revise if any rejection trigger is present.

| Trigger | Why it fails | Required fix |
| --- | --- | --- |
| Generic summary | Sounds AI-generated and does not prove fit. | Add target-role identity, strongest evidence, and relevant domain terms. |
| Keyword stuffing | Can appear dishonest or unreadable. | Keep keywords only where supported and natural. |
| Unsupported skills | Creates interview risk and trust loss. | Remove or downgrade to truthful adjacent wording. |
| Duty-only bullets | Does not prove results. | Add outcome, scope, metric, method, or impact. |
| Dense paragraphs | Hard to skim. | Convert to bullets and compress. |
| Creative headings | ATS may miscategorize sections. | Replace with standard headings. |
| Tables or columns | ATS may scramble reading order. | Convert to single-column text. |
| Unexplained career pivot | Reader cannot infer relevance. | Add summary framing and transferable proof. |
| Too much old experience | Dilutes relevance. | Compress older roles or move to brief “Additional Experience.” |
| Missing contact info | Basic application failure. | Add phone and email in main-body header. |
| Inflated metrics | Creates credibility risk. | Use verified metrics or qualitative outcomes. |

## Decision Trees

### Include or Exclude an Achievement

```text
IF achievement directly proves a core requirement:
  INCLUDE and place high.
ELSE IF achievement proves a transferable outcome the role values:
  INCLUDE if space allows and rewrite with target-role language.
ELSE IF achievement is impressive but unrelated:
  EXCLUDE unless it is a major differentiator.
ELSE:
  EXCLUDE.
```

### Use an Exact Job-Description Keyword

```text
IF keyword appears in the job description AND candidate has used it:
  Use exact keyword in skills or experience.
ELSE IF candidate has adjacent experience:
  Use truthful adjacent language and avoid false exact-match claims.
ELSE:
  Do not include keyword.
```

### Quantify a Bullet

```text
IF exact metric exists in source:
  Use exact metric.
ELSE IF source supports a safe range:
  Use range only if user permits estimates.
ELSE IF qualitative outcome is clear:
  Use observable outcome without numbers.
ELSE:
  Rewrite as scope/method bullet or exclude.
```

### Choose Between Two Bullets

```text
Choose the bullet that has:
1. Higher target-job relevance.
2. Clearer outcome.
3. Stronger metric or scope.
4. More recent evidence.
5. Easier 6-second comprehension.
```

## AI Prompt Blocks

### Resume Generation Instruction Block

```text
You are generating a targeted resume from a master work-history source and a job description.
Do not summarize the entire career.
Select only the evidence that best proves fit for this specific job.
Optimize for recruiter skim value, ATS parseability, truthful keyword alignment, and measurable impact.
Use standard resume sections, simple formatting, concise bullets, and exact job-description terminology only when supported by the source.
Never invent metrics, tools, titles, credentials, employers, dates, or outcomes.
Before finalizing, run the quality gates in this reference and revise until the resume passes.
```

### Bullet Rewrite Instruction Block

```text
Rewrite each bullet to follow this standard:
[Action verb] [object/scope] by [method/tool/collaboration] to [outcome/impact].

Prioritize:
1. Target-job relevance.
2. Measured or observable outcome.
3. Clear ownership.
4. Job-description keywords used naturally.
5. Concision.

Reject bullets that are only duties, generic collaboration statements, unsupported claims, or keyword-stuffed sentences.
```

### Keyword Alignment Instruction Block

```text
Extract the job description’s core keywords and rank them by importance.
For each keyword, find matching proof in the master work history.
Use exact terminology when truthful.
If exact proof does not exist, use adjacent truthful wording.
Do not add unsupported keywords.
Distribute valid keywords across summary, skills, and experience bullets.
Avoid hidden keywords, repeated keyword strings, and unnatural repetition.
```

### Final Review Instruction Block

```text
Review the resume as a recruiter, ATS parser, and hiring manager.
Ask:
1. Can fit be understood in 6 to 10 seconds?
2. Are the strongest target-role signals in the top third?
3. Does each major keyword have proof?
4. Are bullets outcome-focused rather than duty-focused?
5. Is the formatting single-column, standard, and ATS-safe?
6. Are all claims truthful and supported by the source?
7. What should be cut because it dilutes conversion?

Revise the resume until every answer is acceptable.
```

## Final Quality Gate

Before outputting the resume, score it using this rubric.

| Dimension | Fail | Pass | Strong |
| --- | --- | --- | --- |
| Target fit | Generic resume could be sent anywhere. | Most content maps to the job description. | Top third makes target fit obvious immediately. |
| ATS alignment | Nonstandard headings, columns, missing keywords, or unsupported terms. | Standard headings and truthful keywords included. | Keywords are distributed naturally and backed by experience bullets. |
| Evidence quality | Bullets describe duties. | Bullets include actions and outcomes. | Bullets include action, scope, method, and measurable or observable impact. |
| Relevance density | Resume includes too much unrelated history. | Most sections support the target role. | Nearly every line increases confidence for this specific job. |
| Skimmability | Dense, long, inconsistent, or visually confusing. | Clean and readable. | Fast hierarchy, strong first bullets, concise wording, no clutter. |
| Truthfulness | Unsupported claims or inflated language. | Claims are source-supported. | Claims are precise, defensible, and interview-ready. |
| Differentiation | Candidate sounds interchangeable. | Candidate appears qualified. | Candidate has clear edge through specific outcomes, domain fit, or rare skill combination. |

### Minimum Passing Standard

The resume is not ready unless all conditions below are true:

- The first third of the resume clearly matches the target job.
- The summary is specific, evidence-backed, and not generic.
- The skills section contains only supported skills.
- The strongest bullets appear first under each role.
- Most bullets include outcome, scope, method, or metric.
- The resume uses standard headings and single-column formatting.
- No claim depends on hidden context that the recruiter cannot see.
- No keyword appears only because the job description used it.
- No unsupported metric, title, tool, certification, or responsibility has been added.
- The final resume reads naturally to a human and parses cleanly as plain text.

## Implementation Checklist

Use this checklist every time the AI generates a resume.

```text
[ ] Extracted target title, must-have skills, outcomes, seniority, and domain terms from the job description.
[ ] Ranked master work-history evidence by relevance, outcome strength, recency, scope, keyword support, and differentiation.
[ ] Selected content by conversion value, not by completeness.
[ ] Built a specific target-aligned summary.
[ ] Created a skills section from truthful job-description matches.
[ ] Rewrote experience bullets using action, scope, method, and outcome.
[ ] Put strongest bullets first.
[ ] Removed generic, duty-only, outdated, or unrelated content.
[ ] Used standard section headings.
[ ] Avoided tables, columns, icons, graphics, headers, footers, and text boxes.
[ ] Used consistent date formatting.
[ ] Preserved truthfulness and did not invent claims.
[ ] Performed a recruiter skim test.
[ ] Performed an ATS plain-text test.
[ ] Performed a hiring-manager relevance test.
```

## Core Principle

The AI’s job is not to make the candidate look broadly impressive. The AI’s job is to make the candidate look specifically qualified for the target job using truthful, parseable, evidence-dense resume content. Every line should either prove fit, clarify relevance, support ATS matching, or increase trust. If a line does none of those, remove it.
