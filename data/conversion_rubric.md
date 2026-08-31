# PM Resume & Cover Letter Conversion Rubric
# Optimized for LLM evaluation — B2B SaaS Product Manager roles

---

## HOW TO USE THIS RUBRIC

Attach to this prompt:
- The job description (required)
- The generated resume (required)
- The generated cover letter (required)
- Company research / recent news (optional — include if available)
- Company stage: Series B / Growth / Late-stage / Public (optional)
- Target customer segment, e.g. "mid-market, 200-2000 employees" (optional)
- Sales motion: PLG / sales-led / hybrid (optional)

Score each dimension. Return a VERDICT. Do not suggest additional improvements once the verdict is CONVERT-READY.

---

## CONVERSION THRESHOLD

**Resume:** 70+ = CONVERT-READY floor (not a stop signal).
**Cover Letter:** 65+ = CONVERT-READY floor (not a stop signal).

These are conversion floors, not done criteria. A score at or above floor means the document clears the mechanical conversion bar — it does **not** mean drafting is finished. **Done** means every engaged JD item (especially Stage 0 soft gaps / domain soft stretches) uses the single strongest honest bridge available in ground truth, and nothing genuinely usable for that item was left on the table. Do not chase points above floor with padding, stretch claims, or volume. Do not stop at "clears 70/65" while stronger real evidence for a soft gap sits unused.

---

## RESUME SCORING (100 points total)

### R1 — ATS Integrity (10 pts)
Does the resume survive automated parsing?

- 10 pts: Single-column layout, standard section headings (Experience, Education, Skills), no tables, no text boxes, no icons or graphics, no headers/footers with critical info, dates in consistent format
- 6 pts: Mostly clean but 1 structural issue present
- 3 pts: 2+ issues that could break parsing
- 0 pts: Multi-column, graphic-heavy, or non-standard structure

**Flag:** List any specific formatting issues found.

---

### R2 — JD Keyword Alignment (15 pts)
Are the right words in the right places?

- 15 pts: 60–80% of unique, meaningful JD keywords appear in the resume — naturally, where evidence supports them. Keywords appear in summary, skills, and bullets (not just one section).
- 10 pts: 40–59% coverage, or keywords only appear in one section
- 5 pts: Under 40% coverage, or keywords are forced/unsupported by evidence
- 0 pts: Resume reads generically with no JD language alignment

**Flag:** List the top 5 JD keywords missing from the resume that should be there if evidence exists.

---

### R3 — Top-Third Signal (15 pts)
Does the top third of the resume establish the right signals before the reader decides to continue?

Score 3–4 pts per signal present and credible:
- Target title matches or is clearly adjacent to the JD title
- Seniority is clear (years of PM experience, scope owned)
- Domain or product motion fit is visible (B2B SaaS, enterprise, mid-market, etc.)
- At least one business outcome metric appears above the fold

**Flag:** Which signals are absent or buried below the fold?

---

### R4 — Metric Quality (20 pts)
Are the metrics the right kind and framed correctly?

Hierarchy (higher = more points per bullet):
1. Business/customer-behavior outcomes: revenue, retention, churn, activation, conversion, adoption, expansion, time-to-value (3 pts each, max 12)
2. Efficiency outcomes tied to business impact: implementation time, support load, incident reduction (2 pts each)
3. Scale signals paired with an outcome: ARR segment, MAU, customer count (1 pt each)
4. Pure output metrics with no outcome: features shipped, tickets closed, sprints completed (0 pts, flag as weak)

- 20 pts: All recent-role bullets use Tier 1–2 metrics with baseline + delta + timeframe + affected segment where applicable
- 14 pts: Most bullets have strong metrics but some are vague or Tier 4
- 7 pts: Metrics present but mostly activity-based or unanchored
- 0 pts: No metrics, or metrics are ungrounded large numbers with no context

**Flag:** List specific bullets where the metric is weak and what tier it falls into.

---

### R5 — PM Craft Coverage (15 pts)
Does the resume prove PM capability across the full craft, not just delivery?

Award 3 pts each for evidence of:
- **Discovery:** User research, problem framing, opportunity sizing
- **Prioritization:** Tradeoffs navigated, frameworks applied, decisions owned
- **Experimentation:** A/B testing, hypothesis-driven iteration, post-launch learning
- **GTM Partnership:** Launch coordination with sales, CS, marketing, or compliance
- **Iteration:** Post-launch improvement based on data or customer feedback

- 15 pts: All five present
- 9 pts: Three present
- 3 pts: Only delivery mechanics visible (shipped X, built Y)
- 0 pts: Pure execution/coordination framing with no decision or outcome ownership

**Flag:** Which craft areas are absent? Suggest which existing bullets might be reframed to cover them — do not invent new claims.

---

### R6 — Seniority Altitude (10 pts)
Is the candidate pitched at the right level for this role?

- 10 pts: Bullets show scope owned, decisions made, tradeoffs navigated, and business metrics moved at the level the JD targets. Not too tactical, not too executive.
- 6 pts: Minor calibration needed — occasional junior framing ("supported," "assisted," "helped") or occasional over-claim without evidence
- 3 pts: Clearly under-calibrated (backlog hygiene, coordination) or over-calibrated (strategy claims without shipping evidence)
- 0 pts: Strong mismatch between candidate framing and target role level

**Flag:** Specific bullets that signal wrong altitude, with suggested reframes (using only existing evidence).

---

### R7 — Internal Consistency (10 pts)
Does the summary, skills section, and bullets all tell the same story?

- 10 pts: Summary claims are all backed by bullets. Skills listed are all evidenced in experience. No contradiction between sections.
- 6 pts: Minor inconsistency — one claim in summary or skills not clearly supported by bullets
- 3 pts: Summary or skills section makes claims the bullets don't support
- 0 pts: Clear contradiction — summary claims expertise the bullets don't demonstrate

**Flag:** Any specific inconsistencies between sections.

---

### R8 — B2B SaaS Legibility (5 pts)
Can a hiring team immediately infer the candidate understands their business?

If any of the following appear naturally in the resume, award points:
- Who the buyer is (enterprise, mid-market, SMB) — 1 pt
- Who the user is vs. the buyer — 1 pt
- Sales motion or product motion referenced (sales-led, PLG, CS-led growth) — 1 pt
- Internal cross-functional partners named (sales, CS, solutions engineering, compliance, security) — 1 pt
- Monetization or retention context (ARR, NRR, expansion, churn) — 1 pt

*If company stage is known:*
- Series B: bonus if ambiguity-handling, 0-to-1 work, or system-building is visible
- Growth/Public: bonus if scale, operating rigor, or experimentation discipline is visible

**Flag:** Which legibility signals are missing and could be added from existing experience.

---

## COVER LETTER SCORING (100 points total)

### C1 — Opening Hook (25 pts)
Does the first paragraph earn the reader's attention with something specific?

- 25 pts: Opens with a concrete reason for THIS company and THIS role — references the company's product, a recent move they made, a specific problem the role is solving, or a direct thread from the candidate's experience to the company's current context. Does not open with "I am excited to apply."
- 15 pts: Opening is specific to the role but generic about the company
- 8 pts: Opening is enthusiastic but could apply to any company
- 0 pts: Opens with "I am writing to express my interest" or equivalent

*If company research is provided:* use it to make the hook specific. Reference a product launch, strategy shift, funding round, or market move from the last 12 months if relevant and accurate.

**Flag:** What specific company detail could improve the hook if research is available?

---

### C2 — Proof Density (25 pts)
Does the cover letter prove fit rather than assert it?

- 25 pts: Includes 1–2 accomplishments that are directly relevant to the role's likely hiring thesis, with enough specificity to be credible. Does not restate the resume verbatim.
- 15 pts: One strong proof point, or two weak ones
- 8 pts: Claims fit without evidence, or restates resume bullets word-for-word
- 0 pts: All assertion, no proof

**Flag:** Which accomplishment from the resume would be the strongest single proof point for this role, and is it in the cover letter?

---

### C3 — Role Fit Logic (20 pts)
Does the cover letter explain WHY this candidate fits THIS product context now?

- 20 pts: Connects the candidate's specific background to the specific demands of this role at this company stage. Explains the thread from past work to this opportunity without generic PM language.
- 12 pts: Makes the connection but relies on generic PM framing ("I have a track record of...")
- 5 pts: Lists qualifications without connecting them to the role's context
- 0 pts: Could have been written for any PM role at any company

---

### C4 — Authenticity (20 pts)
Does this sound like a person wrote it, or does it sound AI-generated?

- 20 pts: Specific, grounded, natural voice. No boilerplate. No phrases like "leverage my expertise," "dynamic environment," "proven track record," "passionate about," or "I am confident that."
- 12 pts: Mostly authentic with 1–2 AI-sounding phrases
- 6 pts: Several generic phrases, reads like a template
- 0 pts: Dense with AI boilerplate, indistinguishable from a ChatGPT default

**Flag:** List any specific phrases that sound AI-generated and suggest plain-language replacements.

---

### C5 — Length & Structure (10 pts)

- 10 pts: 250–400 words. Three to four paragraphs. No bullet points. Ends with a clear, low-pressure close.
- 6 pts: 400–500 words or under 200 words
- 3 pts: Over 500 words or uses bullets
- 0 pts: Under 150 words or over 600 words

---

## OUTPUT FORMAT

Return your evaluation in this format:

```
RESUME SCORE: [total]/100
  R1 ATS Integrity:        [X]/10
  R2 JD Alignment:         [X]/15
  R3 Top-Third Signal:     [X]/15
  R4 Metric Quality:       [X]/20
  R5 PM Craft Coverage:    [X]/15
  R6 Seniority Altitude:   [X]/10
  R7 Internal Consistency: [X]/10
  R8 B2B SaaS Legibility:  [X]/5

COVER LETTER SCORE: [total]/100
  C1 Opening Hook:     [X]/25
  C2 Proof Density:    [X]/25
  C3 Role Fit Logic:   [X]/20
  C4 Authenticity:     [X]/20
  C5 Length/Structure: [X]/10

VERDICT:
  Resume: CONVERT-READY (70+) / NEEDS-ONE-PASS (50-69) / NEEDS-REWORK (<50)
  Cover Letter: CONVERT-READY (65+) / NEEDS-ONE-PASS (45-64) / NEEDS-REWORK (<45)

BLOCKING ISSUES (only list what is keeping the document below threshold):
  [numbered list, specific and actionable, no more than 5 items per document]

IF NEEDS-ONE-PASS: Apply the fixes listed above and return the revised document.
IF CONVERT-READY on the number alone: still check soft gaps / unused strongest ground truth before calling the document done. Clearing the floor is not permission to leave a stronger honest bridge unused. Only stop when the strongest available evidence for each engaged JD item is already in the document.
```

---

## OPTIONAL CONTEXT (include what you have, skip what you don't)

- Company stage: ___
- Company recent news / research: ___
- Target customer segment: ___
- Sales motion: ___
- Any specific role requirements that stand out: ___
