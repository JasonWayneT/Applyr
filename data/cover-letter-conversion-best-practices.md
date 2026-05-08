# Cover Letter Conversion Best Practices for AI Generation

```yaml
document_type: cover_letter_conversion_reference
primary_objective: create_a_targeted_cover_letter_that_converts
intended_reader: ai_cover_letter_generation_agent
human_readable: true
inputs:
  - master_work_history_or_cv
  - targeted_resume
  - target_job_description
  - company_context_if_available
output:
  - targeted_cover_letter
optimization_order:
  - truthfulness
  - employer_specific_relevance
  - proof_of_fit
  - concise_persuasive_story
  - complement_to_resume
  - voice_authenticity
forbidden_behaviors:
  - repeating_the_resume
  - writing_generic_ai_filler
  - inventing_company_research_or_motivation
  - inventing_metrics_or_claims
  - overexplaining_the_full_career
  - centering_what_the_company_can_do_for_the_candidate
  - apologizing_for_gaps_or_weaknesses_unless_needed
```

## Purpose

This reference defines the rules an AI should apply when generating a targeted cover letter from a master work-history source, a tailored resume, and a target job description. The goal is not to restate the resume. The goal is to make a short, credible, company-aware argument that the candidate understands the role, has relevant proof, and can create value for the employer.

Use this document as the cover-letter generation quality standard. Apply the rules in priority order. If rules conflict, prefer truthfulness, employer relevance, specific evidence, and authentic voice over polished generic prose.

## Operating Definition of a Cover Letter That Converts

A converting cover letter helps the reader answer: “Why this candidate, for this role, at this company, now?” Yale describes the cover letter as a document that introduces the candidate, outlines interest, shows qualification, makes a connection, and should be tailored to a specific job ([Yale Office of Career Strategy](https://ocs.yale.edu/channels/cover-letters-correspondence/)). MIT similarly frames an effective cover letter as a curated document for a specific company or position that demonstrates genuine interest and uses brief examples from past experience to highlight role-relevant skills ([MIT CAPD cover letter guide](https://capd.mit.edu/resources/career-toolkit-writing-a-cover-letter/)).

### Conversion Criteria

| Criterion | AI implementation rule | Pass condition |
| --- | --- | --- |
| Specific fit | Tie the letter to the exact role, company, and job-description needs. | The letter cannot be sent unchanged to another employer. |
| Evidence-backed persuasion | Use 2 to 3 concrete examples, stories, or results. | Claims are proven through examples, not adjectives. |
| Resume complement | Expand or connect selected resume proof instead of repeating bullets. | The letter adds context, motivation, fit, or story not obvious from the resume alone. |
| Employer value | Emphasize what the candidate can help the company accomplish. | The letter is framed around company problems, goals, and role outcomes. |
| Concision | Keep the letter focused and skimmable. | One page or less, usually 3 to 4 paragraphs. |
| Authentic voice | Sound like a credible human candidate, not a generic AI template. | The letter uses natural, specific, defensible language. |

## Source Signals the AI Must Extract Before Writing

Before drafting, extract and rank the following from the job description, company context, targeted resume, and master work history.

### From the Job Description

| Signal | Extraction instruction | Use in cover letter |
| --- | --- | --- |
| Role mission | Identify what the hire is expected to accomplish. | Anchor the opening and proof points around this mission. |
| Top 3 skills | Extract the three most important skills, capabilities, or strengths. | Build the letter around these themes. |
| Business outcomes | Extract goals such as growth, adoption, operational efficiency, quality, customer experience, analytics, platform scale, or launch velocity. | Choose examples that show similar outcomes. |
| Pain points | Infer problems the employer needs solved. | Position candidate evidence as relevant problem-solving proof. |
| Keywords | Capture terms that should appear naturally. | Use exact terminology only where truthful and readable. |
| Seniority signals | Detect expected ownership level. | Match tone and examples to the level of the role. |

### From Company Context

| Signal | Extraction instruction | Use in cover letter |
| --- | --- | --- |
| Mission or product | Identify what the company does and who it serves. | Explain specific interest without generic flattery. |
| Business model or market | Identify customers, users, industry, competitors, or growth stage if known. | Connect the candidate’s background to business context. |
| Values or culture | Extract only if credible and relevant. | Mention values only if connected to the candidate’s actual experience. |
| Recent initiatives | Use only verified or user-provided information. | Connect interest to current priorities when available. |
| Referral or connection | Include only if explicit and allowed. | Mention in the opening if it strengthens trust. |

### From the Targeted Resume and Master Work History

| Signal | Extraction instruction | Use in cover letter |
| --- | --- | --- |
| Strongest aligned proof | Identify 2 to 3 examples that map to the job’s top needs. | Use as body paragraph evidence. |
| Story-worthy moments | Find examples with problem, action, trade-off, and outcome. | Convert into concise narrative, not bullet repetition. |
| Differentiators | Extract unusual combinations of domain, skill, tool, leadership, or impact. | Use to make the candidate memorable. |
| Motivation evidence | Find real reasons the candidate is interested in this role or company. | Use in opening or closing. |
| Transition logic | If changing roles/domains, identify transferable skills and credible bridge evidence. | Explain fit without apologizing. |

## Priority Order for Cover Letter Content

Use this order when selecting what to include. Do not optimize for warmth alone. Optimize for a concise, persuasive fit argument.

1. **Employer’s most important need**: The role outcome, pain point, or capability the company is hiring for.
2. **Candidate’s strongest matching proof**: A concrete example that shows the candidate has solved a similar problem.
3. **Company-specific reason**: A truthful reason the candidate is interested in this company or role.
4. **Differentiator**: A rare combination, relevant domain, unusual project, or signature strength.
5. **Transferable bridge**: Only if needed to explain a pivot, nontraditional background, or adjacent experience.
6. **Call to conversation**: A brief, confident closing that invites next steps.
7. **Everything else**: Exclude if it repeats the resume, sounds generic, or does not support this specific application.

## Hard Rules

### CL-001: Tailor Every Cover Letter to One Role and Company

Do not generate a generic cover letter. MIT says an effective cover letter is directed toward a specific company or position, and Yale says each letter should be tailored to a specific job ([MIT CAPD cover letter guide](https://capd.mit.edu/resources/career-toolkit-writing-a-cover-letter/), [Yale Office of Career Strategy](https://ocs.yale.edu/channels/cover-letters-correspondence/)). The AI must make the letter specific enough that it would feel misaddressed if sent to a different employer.

### CL-002: Do Not Repeat the Resume

The cover letter must complement the resume rather than restate it. MIT explicitly warns that the biggest mistake is repeating resume content and advises using the letter to elaborate, tell stories, link experiences, and connect past experience to role responsibilities ([MIT CAPD cover letter guide](https://capd.mit.edu/resources/career-toolkit-writing-a-cover-letter/)). The AI must select a few resume proof points and add narrative context, motivation, or relevance.

### CL-003: Lead With Role Fit, Not Personal Need

Do not center why the candidate wants a job, career growth, or personal benefit unless it directly supports employer value. MIT’s cover letter packet advises demonstrating how the candidate can contribute to the company, not what the company can do for the candidate ([MIT Sloan cover letter packet](https://cdn.cdo.mit.edu/wp-content/uploads/sites/67/2019/07/Cover-Letter-Sample-Packet-Revised-2017-2018.pdf)). The AI must frame interest around contribution, role outcomes, and company needs.

### CL-004: Use Specific Examples Instead of Generic Ability Claims

Do not write “I am a strong communicator,” “I am a great fit,” or “I am passionate” without proof. Indeed advises avoiding generic references to abilities and instead using meaningful anecdotes that connect skills to concrete problem-solving or tangible business results ([Indeed cover letter guide](https://www.indeed.com/career-advice/resumes-cover-letters/how-to-write-a-cover-letter)). The AI must prove every major claim with an example or outcome.

### CL-005: Build Around 2 to 3 Proof Points

Do not summarize the candidate’s full career. Indeed recommends choosing one or two achievements and mapping them directly to desired experience or qualifications, while MIT’s packet recommends focusing body paragraphs on 3 to 4 skills, abilities, or experiences that help the company meet business goals ([Indeed cover letter guide](https://www.indeed.com/career-advice/resumes-cover-letters/how-to-write-a-cover-letter), [MIT Sloan cover letter packet](https://cdn.cdo.mit.edu/wp-content/uploads/sites/67/2019/07/Cover-Letter-Sample-Packet-Revised-2017-2018.pdf)). The AI should usually select 2 to 3 proof points, not every relevant experience.

### CL-006: Keep It One Page or Less

Cover letters should be concise. Yale advises limiting the letter to one page, and Indeed describes a cover letter as a one-page, three- to four-paragraph letter ([Yale Office of Career Strategy](https://ocs.yale.edu/channels/cover-letters-correspondence/), [Indeed cover letter guide](https://www.indeed.com/career-advice/resumes-cover-letters/how-to-write-a-cover-letter)). The AI must cut anything that does not directly strengthen fit.

### CL-007: Use Job-Description Keywords Naturally

Use relevant terms from the job description, but do not keyword-stuff. Yale advises using keywords from the position description, and Indeed recommends paying attention to job-description keywords and including ones that apply in the body of the letter ([Yale Office of Career Strategy](https://ocs.yale.edu/channels/cover-letters-correspondence/), [Indeed cover letter guide](https://www.indeed.com/career-advice/resumes-cover-letters/how-to-write-a-cover-letter)). The AI must integrate keywords into natural sentences that prove real experience.

### CL-008: Preserve Authentic Voice and Truth

Do not let AI-generated language become the candidate’s voice by default. Harvard says generative AI can be useful for editing and brainstorming, but should not be the primary author because output is likely generic, and the final document should authentically represent the candidate ([Harvard FAS AI resume and cover letter guide](https://careerservices.fas.harvard.edu/ai-resumes-and-cover-letters/)). The AI must maintain truthful, specific, defensible language that the candidate can say aloud.

### CL-009: Research the Employer Only When Reliable Context Exists

Do not invent company admiration, recent news, mission alignment, or product familiarity. MIT recommends researching the employer’s website, social media, mission, products, services, culture, and role context, but the AI must use only verified or user-provided company context ([MIT CAPD cover letter guide](https://capd.mit.edu/resources/career-toolkit-writing-a-cover-letter/)). If reliable company context is unavailable, keep company-specific language modest and role-specific.

### CL-010: Proofread as a Conversion Requirement

Errors reduce trust. Yale warns that proofreading matters and that errors can be deal-breakers ([Yale Office of Career Strategy](https://ocs.yale.edu/channels/cover-letters-correspondence/)). The AI must run a final grammar, accuracy, tone, and name/company check before output.

## Recommended Cover Letter Architecture

### Default Structure

| Section | Length | Job to be done | AI instruction |
| --- | --- | --- | --- |
| Header | Optional based on submission format | Make contact and application details clear. | Use the same clean header as the resume if submitting as an attachment; omit redundant address details if pasting into an application box. |
| Greeting | 1 line | Address the reader professionally. | Use the hiring manager’s name if known; otherwise use “Dear Hiring Manager” or “Dear Hiring Committee.” |
| Opening paragraph | 2 to 4 sentences | State role, company interest, and fit thesis. | Connect the candidate to the company’s need and preview 2 to 3 strengths. |
| Body paragraph 1 | 3 to 5 sentences | Prove the strongest match. | Use one concrete example that maps to a top job requirement. |
| Body paragraph 2 | 3 to 5 sentences | Prove second match or differentiator. | Use a second example, company-specific connection, or transferable bridge. |
| Closing paragraph | 2 to 4 sentences | Reaffirm contribution and invite conversation. | Summarize value, thank the reader, and express interest in discussing fit. |
| Signoff | 1 to 2 lines | Close professionally. | Use “Sincerely,” “Best regards,” or a similarly professional close. |

### Optional Short Structure

Use this structure for application portals, recruiter messages, or roles where a shorter note is better.

```text
Dear [Hiring Manager/Team],

[Role-specific opening: role + company + fit thesis.]

[One proof paragraph: concrete example mapped to top requirement.]

[Closing: contribution + interest in conversation.]

Best regards,
[Name]
```

## Paragraph-by-Paragraph Rules

### Header

| Rule ID | Rule | Implementation |
| --- | --- | --- |
| H-001 | Match the resume header when attached. | Use the same name, phone, email, LinkedIn, portfolio, city/state, and visual style as the resume. |
| H-002 | Avoid unnecessary address clutter. | For digital applications, include only useful contact details unless a formal business-letter format is expected. |
| H-003 | Use professional formatting. | Indeed recommends simple professional fonts, 10 to 12 point size, left alignment, single spacing, and standard margins ([Indeed cover letter formatting guide](https://www.indeed.com/career-advice/resumes-cover-letters/how-to-format-a-cover-letter-example)). |

### Greeting

| Rule ID | Rule | Implementation |
| --- | --- | --- |
| G-001 | Use a named recipient if known. | Use the full name when reliable. |
| G-002 | Use a safe fallback. | If the name is unknown, use “Dear Hiring Manager” or “Dear Hiring Committee.” |
| G-003 | Avoid outdated or impersonal greetings. | MIT and Indeed advise avoiding “To Whom It May Concern,” and Indeed advises avoiding “Dear Sir/Madam” ([MIT CAPD cover letter guide](https://capd.mit.edu/resources/career-toolkit-writing-a-cover-letter/), [Indeed cover letter formatting guide](https://www.indeed.com/career-advice/resumes-cover-letters/how-to-format-a-cover-letter-example)). |

### Opening Paragraph

The opening must make the letter feel specific immediately. It should answer: role, company, reason, and fit thesis.

| Rule ID | Rule | Implementation |
| --- | --- | --- |
| O-001 | Name the role and company. | Make it obvious what application this letter supports. |
| O-002 | State a specific reason for interest. | Use company mission, product, customers, domain, role problem, referral, or a credible user/customer connection. |
| O-003 | Preview the fit argument. | End with 2 to 3 strengths that map to the role. |
| O-004 | Avoid hollow enthusiasm. | Do not write “I am excited to apply” unless followed by specific evidence of why. |

#### Opening Formula

```text
I am applying for the [Role] at [Company] because [specific company/role reason].
The role’s focus on [job need/outcome] aligns with my experience in [proof theme 1], [proof theme 2], and [proof theme 3].
```

### Body Paragraphs

Each body paragraph should prove one fit theme. Yale recommends starting each middle paragraph with a topic sentence that highlights one related skill, then using the rest of the paragraph to show examples of that skill ([Yale Office of Career Strategy](https://ocs.yale.edu/channels/cover-letters-correspondence/)).

| Rule ID | Rule | Implementation |
| --- | --- | --- |
| B-001 | One paragraph equals one proof theme. | Do not mix too many unrelated skills in one paragraph. |
| B-002 | Use story logic. | Problem or context, action, method, result, and relevance to target role. |
| B-003 | Add meaning beyond resume bullets. | Explain decision-making, motivation, stakeholder context, constraints, or why the example matters. |
| B-004 | Use measurable outcomes when available. | Indeed recommends specific details and measurable impacts when describing success ([Indeed cover letter guide](https://www.indeed.com/career-advice/resumes-cover-letters/how-to-write-a-cover-letter)). |
| B-005 | Connect back to the employer. | End or imply how the example helps this company’s role outcomes. |

#### Body Paragraph Formula

```text
In [context], I [action] to address [problem/goal].
By [method, collaboration, tool, or decision], I [specific outcome or measurable result].
That experience maps directly to [Company]’s need for [job-description need] because [relevance bridge].
```

### Closing Paragraph

| Rule ID | Rule | Implementation |
| --- | --- | --- |
| C-001 | Reaffirm value, not desperation. | Summarize how the candidate can contribute. |
| C-002 | Invite next step. | Express interest in discussing how the background maps to the role. |
| C-003 | Keep it brief. | Do not add a new career story in the closing. |
| C-004 | Thank the reader professionally. | Use a concise thank-you and signoff. |

#### Closing Formula

```text
I would welcome the opportunity to discuss how my experience in [proof theme] and [proof theme] can help [Company] [role/company outcome].
Thank you for your time and consideration.
```

## Evidence Selection Heuristics

### Proof Point Scoring Matrix

Score each possible story or example before selecting cover-letter content.

| Factor | Score 0 | Score 1 | Score 2 | Score 3 |
| --- | --- | --- | --- | --- |
| Role relevance | Unrelated | Adjacent | Relevant | Direct match |
| Company relevance | Generic | Weakly related | Connected to company context | Directly tied to company/product/mission/problem |
| Outcome strength | No result | Qualitative result | Measured result | Measured business/customer/product impact |
| Story clarity | Confusing | Needs explanation | Clear | Memorable and concise |
| Differentiation | Common claim | Somewhat useful | Strong candidate signal | Rare or unusually compelling |
| Resume complement | Repeats resume | Lightly expands resume | Adds useful context | Adds insight not visible in resume |
| Truth support | Unsupported | Inferred | Supported by source | Explicitly supported with metric/context |

Select the 2 to 3 highest-scoring proof points. If two proof points tie, choose the one that better explains “why this role” or “why this company.”

### Proof Point Inclusion Threshold

| Letter area | Minimum evidence score | Rule |
| --- | --- | --- |
| Opening thesis | 14+ | Must preview the strongest fit themes. |
| Body paragraph 1 | 15+ | Must prove the top job requirement. |
| Body paragraph 2 | 12+ | Must prove a second requirement, differentiator, or company-specific fit. |
| Career pivot explanation | 11+ | Include only if it clarifies fit and reduces confusion. |
| Closing | No new proof | Summarize; do not introduce unrelated evidence. |

## Story Construction Rules

### Required Story Traits

Each body proof point should include at least four of the following:

| Trait | Definition | Example signal |
| --- | --- | --- |
| Context | Situation or problem. | “In a high-volume support workflow…” |
| Ownership | What the candidate owned or influenced. | “I led,” “I built,” “I partnered,” “I analyzed.” |
| Method | How the candidate worked. | Research, experimentation, prioritization, automation, stakeholder alignment. |
| Constraint | Difficulty, ambiguity, scale, or trade-off. | Limited resources, tight timeline, unclear requirements, cross-functional complexity. |
| Outcome | What changed. | Faster decisions, reduced manual work, improved adoption, clearer roadmap. |
| Relevance bridge | Why this matters to the employer. | “This is the same type of…” |
| Voice | Human specificity. | Natural wording that the candidate can say aloud. |

### Weak Story Patterns to Rewrite

| Weak pattern | Problem | Rewrite direction |
| --- | --- | --- |
| “I am excited about this role because it aligns with my skills.” | Generic and unsupported. | Name the role problem and the candidate’s matching proof. |
| “My resume shows I have experience in product management.” | Repeats resume. | Tell a brief story that proves product judgment. |
| “I am a strong communicator and team player.” | Generic soft-skill claim. | Show stakeholder alignment, decision clarity, executive communication, or conflict resolution. |
| “Your company is innovative and mission-driven.” | Generic company praise. | Name a specific product, customer, mission element, or business problem. |
| “Although I do not have X…” | Draws attention to weakness. | Lead with adjacent proof and transferable strengths unless the gap must be addressed. |
| “I believe I would be a great fit.” | Unsupported conclusion. | Prove fit, then invite conversation. |

## Keyword Strategy

### Keyword Extraction Process

1. Extract the top 5 to 10 job-description terms.
2. Select the 3 to 5 terms most relevant to the cover letter’s proof points.
3. Use exact terms only when supported by the candidate’s source material.
4. Place terms in the opening thesis and body proof paragraphs.
5. Avoid repeating the same term unnaturally.
6. Prefer proof over frequency.

### Keyword Placement Rules

| Keyword type | Best placement | Bad placement |
| --- | --- | --- |
| Role title | Opening paragraph. | Repeated throughout the letter. |
| Core skill | Opening thesis and one body paragraph. | Generic skill list inside prose. |
| Tool or method | Body paragraph showing usage. | Mentioned without evidence. |
| Domain term | Company-interest sentence or relevance bridge. | Added with no actual connection. |
| Soft skill | Story outcome or collaboration example. | Unsupported adjective. |

### Keyword Integrity Test

For every keyword added, the AI must answer:

```text
1. Is this keyword important to the target job?
2. Is it supported by the candidate’s work history or resume?
3. Does it appear in a natural sentence?
4. Does the surrounding sentence prove or contextualize the skill?
5. Would the candidate comfortably discuss this claim in an interview?
```

If any answer is “no,” remove or rewrite the keyword.

## Company-Specificity Rules

### Valid Company-Specific Hooks

| Hook type | Use when | Example pattern |
| --- | --- | --- |
| Product/user hook | Candidate understands or has relevant experience with the product, users, or market. | “Your focus on [product/user problem] stands out because…” |
| Mission hook | The company mission is specific and connects to candidate experience. | “The mission to [specific mission] connects with my work in…” |
| Role-problem hook | Job description clearly reveals the business problem. | “The opportunity to improve [role outcome] matches my experience…” |
| Referral hook | A real person referred or encouraged the candidate. | “After speaking with [Name] about [topic], I was drawn to…” |
| Domain hook | Candidate has relevant domain context. | “My background in [domain] would help me contribute to…” |

### Invalid Company-Specific Hooks

| Hook type | Why to avoid |
| --- | --- |
| “Your company is innovative.” | Too generic; could apply anywhere. |
| “I have always admired your company.” | Often unverifiable and overused. |
| “I am passionate about your mission.” | Weak without personal or professional evidence. |
| Recent news claim without source. | Risk of hallucination or outdated information. |
| Overly flattering language. | Sounds insincere and AI-generated. |

## Career Pivot and Gap Handling

Use a bridge only when the reader may otherwise be confused. Do not apologize. Do not overexplain. Do not lead with weakness.

### Pivot Formula

```text
My background in [source domain/function] has given me practical experience in [transferable capability 1] and [transferable capability 2].
That experience is directly relevant to [target role need], where success depends on [shared underlying skill/outcome].
```

### Gap Formula

```text
During [period/context if necessary], I focused on [truthful productive activity, learning, caregiving, consulting, project, or transition].
That period strengthened my ability to [target-relevant capability], which I am ready to apply to [role/company outcome].
```

Only include a gap explanation if the application context requires it or if leaving it unexplained creates more risk than mentioning it.

## Tone and Voice Rules

| Rule ID | Rule | Implementation |
| --- | --- | --- |
| T-001 | Use confident, active language. | Yale recommends confident language and active voice ([Yale Office of Career Strategy](https://ocs.yale.edu/channels/cover-letters-correspondence/)). |
| T-002 | Sound specific, not grandiose. | Replace “I am uniquely qualified” with concrete proof. |
| T-003 | Avoid excessive humility. | Do not overuse “I believe,” “I hope,” “I think,” or “I would be honored.” |
| T-004 | Avoid hype. | Do not use exaggerated claims, empty enthusiasm, or over-flattery. |
| T-005 | Match candidate voice. | Harvard recommends reading the letter aloud to ensure it is authentic and in the candidate’s voice ([Harvard FAS AI resume and cover letter guide](https://careerservices.fas.harvard.edu/ai-resumes-and-cover-letters/)). |

## Formatting Rules

| Rule ID | Rule | Rationale |
| --- | --- | --- |
| F-001 | Keep the letter to one page. | Yale and Indeed both recommend a one-page cover letter ([Yale Office of Career Strategy](https://ocs.yale.edu/channels/cover-letters-correspondence/), [Indeed cover letter guide](https://www.indeed.com/career-advice/resumes-cover-letters/how-to-write-a-cover-letter)). |
| F-002 | Use 3 to 4 paragraphs by default. | Yale and Indeed both describe cover letters as typically 3 to 4 paragraphs ([Yale Office of Career Strategy](https://ocs.yale.edu/channels/cover-letters-correspondence/), [Indeed cover letter guide](https://www.indeed.com/career-advice/resumes-cover-letters/how-to-write-a-cover-letter)). |
| F-003 | Use a simple professional font. | Indeed recommends professional fonts such as Arial, Helvetica, Calibri, or Verdana at 10 to 12 points ([Indeed cover letter formatting guide](https://www.indeed.com/career-advice/resumes-cover-letters/how-to-format-a-cover-letter-example)). |
| F-004 | Align formatting with the resume. | MIT recommends formatting the cover letter similarly to the resume for uniform application materials ([MIT CAPD cover letter guide](https://capd.mit.edu/resources/career-toolkit-writing-a-cover-letter/)). |
| F-005 | Use left alignment and readable spacing. | Indeed recommends left alignment, single spacing, and standard margins ([Indeed cover letter formatting guide](https://www.indeed.com/career-advice/resumes-cover-letters/how-to-format-a-cover-letter-example)). |
| F-006 | Use PDF or DOCX depending on employer instructions. | Indeed lists Word document or PDF as cover-letter file formats ([Indeed cover letter formatting guide](https://www.indeed.com/career-advice/resumes-cover-letters/how-to-format-a-cover-letter-example)). |

## Anti-Patterns and Rejection Triggers

The AI must stop and revise if any rejection trigger is present.

| Trigger | Why it fails | Required fix |
| --- | --- | --- |
| Generic opening | Sounds mass-produced. | Add role, company, specific reason, and fit thesis. |
| Resume repetition | Wastes the letter’s purpose. | Add story, context, motivation, or relevance bridge. |
| No company specificity | Could be sent anywhere. | Add verified company, product, mission, or role-problem connection. |
| No concrete example | Claims are unproven. | Add one specific story or measurable outcome. |
| Too many proof points | Dilutes the case. | Keep only the 2 to 3 strongest. |
| Candidate-centered framing | Focuses on personal benefit. | Reframe around employer needs and contribution. |
| Unsupported enthusiasm | Feels fake. | Tie interest to specific evidence. |
| Apologetic pivot language | Draws attention to weakness. | Use confident transferable bridge. |
| Excessive length | Reduces skim value. | Cut to one page or less. |
| Hallucinated company research | Creates credibility risk. | Remove or replace with verified context. |
| AI-polished clichés | Makes candidate sound interchangeable. | Replace with plain, specific, candidate-owned language. |

## Decision Trees

### Include or Exclude a Proof Point

```text
IF proof point maps directly to a top job requirement:
  INCLUDE as a body paragraph candidate.
ELSE IF proof point explains a differentiator or pivot:
  INCLUDE only if it improves the fit argument.
ELSE IF proof point is impressive but unrelated:
  EXCLUDE.
ELSE:
  EXCLUDE.
```

### Mention Company Research

```text
IF company context is verified and relevant:
  Include one specific sentence connecting it to candidate experience or motivation.
ELSE IF only generic company context is available:
  Use role-specific interest instead of company praise.
ELSE:
  Do not invent company details.
```

### Explain a Career Pivot

```text
IF the candidate’s background clearly differs from the target role:
  Add a concise transferable bridge.
ELSE IF the resume already makes the fit obvious:
  Do not spend space explaining the pivot.
ELSE:
  Lead with strongest related proof and avoid apology.
```

### Choose Between Two Openings

```text
Choose the opening that:
1. Names the target role and company.
2. Shows a specific reason for interest.
3. Introduces the strongest fit thesis.
4. Avoids clichés.
5. Could not be sent unchanged to a different employer.
```

## AI Prompt Blocks

### Cover Letter Generation Instruction Block

```text
You are generating a targeted cover letter from a master work-history source, targeted resume, job description, and available company context.
Do not repeat the resume.
Do not summarize the full career.
Write a concise, one-page-or-less letter that proves fit for this specific role and company.
Build the letter around 2 to 3 concrete proof points that map to the employer’s top needs.
Use company-specific context only if verified or provided.
Use job-description keywords naturally and only when supported by the candidate’s experience.
Never invent metrics, claims, company details, motivations, referrals, titles, tools, or credentials.
Before finalizing, run the quality gates in this reference and revise until the letter passes.
```

### Proof Point Selection Instruction Block

```text
Analyze the job description and identify:
1. The top 3 employer needs.
2. The likely business problem behind the role.
3. The most important skills or capabilities.

Then analyze the candidate source material and select 2 to 3 proof points that best match those needs.
Choose proof points with concrete examples, outcomes, constraints, or business relevance.
Reject proof points that are impressive but unrelated, unsupported, too old, too generic, or already fully obvious from the resume.
```

### Paragraph Drafting Instruction Block

```text
Draft the letter using this structure:
Opening: role + company + specific interest + fit thesis.
Body 1: strongest proof point mapped to top role requirement.
Body 2: second proof point, differentiator, company connection, or transferable bridge.
Closing: concise contribution statement + invitation to discuss fit + thanks.

Each body paragraph must include context, action, outcome, and relevance to the target role.
Use active voice, confident tone, and natural language.
Avoid clichés, generic enthusiasm, and resume repetition.
```

### Final Review Instruction Block

```text
Review the cover letter as a hiring manager.
Ask:
1. Is this clearly written for this exact role and company?
2. Does the opening create a specific fit thesis?
3. Does the letter prove 2 to 3 employer-relevant strengths?
4. Does it add context beyond the resume?
5. Is every company claim verified or user-provided?
6. Are keywords natural and supported?
7. Is the letter one page or less?
8. Does it sound like the candidate could say it aloud?
9. What should be cut because it is generic, repetitive, or candidate-centered?

Revise the letter until every answer is acceptable.
```

## Final Quality Gate

Before outputting the cover letter, score it using this rubric.

| Dimension | Fail | Pass | Strong |
| --- | --- | --- | --- |
| Specificity | Could be sent to any company. | Mentions target role and company. | Shows specific role, company, and business need alignment. |
| Proof | Mostly claims and adjectives. | Includes concrete examples. | Uses 2 to 3 sharp proof points with outcomes and relevance bridges. |
| Resume complement | Repeats resume bullets. | Expands on selected resume evidence. | Adds story, motivation, context, and contribution not obvious from the resume. |
| Employer value | Focuses on candidate wants. | Mentions contribution. | Clearly connects candidate evidence to employer goals. |
| Voice | Generic AI tone. | Professional and clear. | Authentic, confident, specific, and readable aloud. |
| Length | Too long or unfocused. | One page or less. | Tight, skimmable, and free of filler. |
| Truthfulness | Contains unsupported claims. | Claims are source-supported. | Every claim is precise, defensible, and interview-ready. |

### Minimum Passing Standard

The cover letter is not ready unless all conditions below are true:

- The opening names the role and company.
- The letter has a specific fit thesis.
- The letter includes 2 to 3 concrete proof points.
- Each proof point maps to a job-description need.
- The letter complements rather than repeats the resume.
- Any company-specific claim is verified or user-provided.
- The letter is one page or less.
- The tone is confident, active, and authentic.
- The candidate can defend every claim in an interview.
- No paragraph is generic enough to paste into another application unchanged.

## Implementation Checklist

Use this checklist every time the AI generates a cover letter.

```text
[ ] Extracted role mission, top 3 skills, business outcomes, pain points, keywords, and seniority signals from the job description.
[ ] Extracted company context only from verified or user-provided information.
[ ] Selected 2 to 3 strongest proof points from the targeted resume and master work history.
[ ] Built a specific opening with role, company, reason, and fit thesis.
[ ] Wrote body paragraphs that include context, action, outcome, and relevance bridge.
[ ] Avoided repeating resume bullets.
[ ] Used job-description keywords naturally.
[ ] Framed the letter around employer value and contribution.
[ ] Avoided unsupported company praise, clichés, and generic enthusiasm.
[ ] Kept the letter one page or less.
[ ] Preserved candidate voice and truthfulness.
[ ] Checked names, role title, company name, dates, metrics, and claims.
[ ] Performed read-aloud test for authenticity.
[ ] Performed hiring-manager test for relevance and persuasion.
```

## Core Principle

The AI’s job is not to write a polite letter that says the candidate is interested. The AI’s job is to write a short, specific, evidence-backed argument that this candidate can help this employer solve this role’s problems. Every sentence should either prove fit, explain motivation, connect evidence to the employer’s needs, or move the reader toward an interview. If a sentence does none of those, remove it.
