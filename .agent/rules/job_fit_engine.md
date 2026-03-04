Below is a **complete rewrite** of your Job-Fit Engine as a clean, deterministic, **slightly tighter** v2.1 that’s designed for agentic use.

Key upgrades baked in:

* **Two-stage logic** inside one file (Fast Gate + Full Scoring) to reduce wasted work
* **Explicit Overlap Gate** (prevents “YES because generic PM skills”)
* **JD completeness** to avoid false confidence
* **Tighter thresholds** so you get fewer borderline YES outcomes
* **Hard disqualifiers** remain immediate NO
* **Anti-hallucination** and **no inference** rules are explicit and enforceable
* Outputs match your template exactly and include JSON

Copy/paste this into:

✅ `.agent/rules/20_job_fit_engine.md`

---

````markdown
# Jason Taylor – Job-Fit Decision Engine (v2.1, Slightly Tighter)

This file defines a deterministic YES/NO decision system for evaluating job descriptions for Jason Taylor.

This engine is designed for agentic pipelines:
- slightly tighter (fewer borderline YES)
- efficient (fast gate first)
- anti-hallucination (no inference)
- deterministic (consistent scoring and outputs)

---

## 0) Purpose

Decide whether Jason Taylor should invest effort applying to a role.

Your output must be:

- **YES** = worth applying and tailoring (credible chance to convince a hiring manager).
- **NO** = likely rejection or inefficient due to seniority mismatch or experience gap too large.

This engine is **slightly tighter**. When in doubt, prefer **NO** unless defensibility is clear.

---

## 1) Jason’s Ground Truth Profile (Do Not Infer Beyond This)

Jason Taylor is a mid-level Product Manager in B2B SaaS with platform/revenue systems experience.

### Strong Areas (explicitly supported)
- Roadmap ownership, prioritization, requirements writing, backlog hygiene.
- B2B SaaS platforms, enterprise environments, global customers.
- Legacy platform ownership and stability/reliability improvements.
- Data integrity improvements and integrations with upstream sources of truth.
- Migration strategy and tooling (voluntary, phased). Do not claim migrated account count.
- Cross-functional alignment (Engineering, DevOps, DBA, CX, Support, Legal, Sales, AM, GTM).
- Security backlog prioritization (penetration test backlog ~300 items; ~90% addressed).
- Jira/Confluence daily usage.
- Capacity planning and quarterly / PI planning communication.

### Important nuance
- Customer interaction often via escalations and internal customer-facing stakeholders.

### Not Claimed (must not infer)
Do NOT claim Jason has:
- PM people management (managing PMs, hiring, performance management, org design).
- Direct P&L ownership.
- Consumer mobile app ownership.
- Large-scale experimentation/growth as primary charter.
- AI/ML product ownership (model roadmaps, evaluation frameworks, training).
- Deep domain regulatory specialization (unless explicitly shown in Jason files).

If the JD requires something not stated above or not present in the provided Jason files, treat it as missing.

---

## 2) Required Output (Non-Negotiable)

You must output:

### 2.1 Human-readable block (exact template)

```text
Decision: YES/NO
Score: [0–100]
Confidence: High/Medium/Low
Summary: [one sentence]

Top fit reasons:
[reason 1]
[reason 2]
[reason 3]

Risk flags:
[risk 1]
[risk 2]

Missing info (only if Confidence = Low):
[missing detail 1]
[missing detail 2]
[missing detail 3]
````

Constraints:

* Summary max 25 words.
* Each bullet max 15 words.
* No chain-of-thought.
* No extra commentary.
* No em dashes.

### 2.2 JSON object (mirrors block)

```json
{
  "decision": "YES or NO",
  "score": 0,
  "confidence": "High | Medium | Low",
  "summary": "string, max 25 words",
  "fit_reasons": [
    "reason 1, max 15 words",
    "reason 2, max 15 words",
    "reason 3, max 15 words"
  ],
  "risk_flags": [
    "risk 1, max 15 words",
    "risk 2, max 15 words"
  ],
  "missing_info": [
    "missing 1, max 15 words",
    "missing 2, max 15 words",
    "missing 3, max 15 words"
  ]
}
```

If Confidence is not Low, set `"missing_info": []`.

---

## 3) Stage A: Fast Gate (Efficiency Filter)

Before any scoring, run this fast gate.

If a hard disqualifier triggers, return:

* Decision = NO
* Confidence = High
* Score = 0–35 (choose based on severity, do not exceed 35)

### 3.1 Hard Disqualifiers (Immediate NO)

#### A) Seniority / leadership

Immediate NO if JD explicitly requires:

* Managing PMs (any people management of PMs).
* Director / Head / VP / Group Product Manager / Portfolio owner.
* Company-wide strategy across multiple product lines.
* Explicit 10+ years PM requirement.

#### B) AI/ML ownership

Immediate NO if JD explicitly requires:

* Owning ML/LLM roadmap, model training, evaluation, or data science leadership.
* “Must have shipped ML models” or “own ML evaluation pipeline.”

#### C) Non-transferable domain requirement

Immediate NO if JD explicitly requires prior domain expertise that is not quickly transferable:

* Hardware/embedded/robotics experience as a must-have.
* Explicit payments compliance depth (PCI, card networks) as a must-have.
* Clinical/medical device domain as a must-have.

#### D) Pure consumer growth

Immediate NO if role is explicitly centered on:

* paid acquisition funnels, viral loops, consumer growth experiments as primary output.
* daily A/B testing ownership as the core PM job.

If consumer product but not growth-centric, do not auto-reject.

### 3.2 Fast Gate Stop (Non-disqualifier STOP)

Return NO (Confidence Medium, Score 35–50) if:

* JD is clearly outside software product management (PMM-only, sales-only, pure research).
* Role requires hands-on engineering/coding as a core responsibility.

If ambiguous, proceed to scoring.

---

## 4) JD Completeness (Confidence Input)

Classify JD completeness:

* **High**: clear responsibilities + qualifications + success signals.
* **Medium**: partial clarity, some specifics missing.
* **Low**: vague, buzzwords, unclear expectations, mixes tracks with no weighting.

Rules:

* If completeness is Low, Confidence cannot be High.
* If completeness is Low AND score is borderline (60–74), default to NO unless explicit overlap is strong.

---

## 5) Stage B: Full Scoring (0–100)

Total Score = A + B + C + D + E

Each dimension must be an integer.
If a dimension is unclear, use the default bands below.

### A) Seniority Match (0–25)

* 23–25: PM / PM II, 3–7 yrs, no management.
* 19–22: Senior PM title but execution-heavy, no management.
* 10–18: Senior expectations ambiguous.
* 0–9: Director/VP/10+ yrs signals (would have disqualified if explicit).

Default if unclear but mid-level responsibilities: 20.

### B) Product Model Match (0–20)

* 18–20: B2B SaaS, enterprise workflows, platform/data products.
* 14–17: B2B2C/prosumer or regulated B2B with similar motion.
* 7–13: consumer but not growth-led.
* 0–6: consumer growth experimentation primary.

Default if implied B2B SaaS: 16.

### C) Scope & Problem Type Match (0–20)

* 18–20: reliability, migrations, integrations, data quality, legacy modernization.
* 14–17: enterprise workflows, security/compliance surfaces, complex internal systems.
* 7–13: mostly greenfield UX features with less systems focus.
* 0–6: unrelated to software/product.

Default if mixed new features + platform: 16.

### D) Skills & Execution Fit (0–20)

Look for overlap with:

* roadmap/prioritization

* requirements writing

* cross-functional delivery

* backlog hygiene

* incident/stability collaboration

* security/risk prioritization

* 18–20: very strong overlap

* 14–17: solid overlap

* 8–13: partial overlap

* 0–7: weak overlap

Default if standard PM responsibilities present: 15.

### E) Technical Depth Fit (0–15)

* 13–15: integrations/APIs/data systems, no coding required.
* 10–12: technical collaboration, specs, tradeoffs.
* 5–9: coding expected or deep system design ownership.
* 0–4: requires hands-on engineering or specialized ML depth.

Default if “work with engineers” but no coding: 11.

---

## 6) Soft Disqualifier Penalties (Slightly Tighter)

Apply these penalties after scoring.

* Role requires heavy mobile product ownership: -10
* Role requires primary growth experimentation: -10
* Role heavily design-led with strong UX org and Jason has limited design collaboration: -5
* Role requires deep domain expertise in a new regulated area (nice-to-have but strongly emphasized): -5
* Role expects frequent direct customer discovery as primary motion: -5

Do not apply penalties if requirement is merely “nice to have” and not emphasized.

---

## 7) Explicit Overlap Requirement (Prevents Generic YES)

Before outputting YES, verify:

Jason must have at least **2 explicit overlaps** with the JD that map to his documented experience, not generic PM traits.

Explicit overlaps include:

* platform stability/reliability work
* migrations and tooling
* data integrity/integration with source-of-truth systems
* enterprise B2B SaaS workflows
* security backlog prioritization
* Jira/PI planning and cross-functional roadmap communication

If fewer than 2 explicit overlaps exist:

* Decision must be NO (or MAYBE becomes NO in tighter mode).

---

## 8) Decision Thresholds (Slightly Tighter)

After penalties and overlap gate:

* **Score ≥ 78** → YES (Strong Fit)
* **Score 70–77** → YES only if Explicit Overlap Requirement passes clearly (2+ overlaps) and JD completeness is not Low.
* **Score 60–69** → NO (tighter efficiency, avoids borderline YES)
* **Score < 60** → NO

This is intentionally tighter than permissive triage.

---

## 9) Confidence Calibration

Set Confidence based on:

* clarity of JD
* presence of disqualifiers
* distance from thresholds
* missing critical info

### High

* Hard disqualifier triggered, or
* Score ≥ 85 with clear overlaps, or
* Score ≤ 50.

### Medium

* Score 70–84 with reasonable clarity, or
* Score is clearly NO but JD is somewhat ambiguous.

### Low

* JD completeness Low, or
* critical details missing (PM management ambiguity, role track unclear), or
* mixed responsibilities (platform + growth + ML) without weighting.

If Confidence = Low:

* still output YES or NO
* populate Missing Info with up to 3 items that could change the outcome.

---

## 10) Anti-Hallucination Rules (Must Follow)

* Do not infer experience.
* Do not invent metrics, tools, responsibilities, or domain exposure.
* If the JD mentions a requirement not present in Jason’s known profile, treat it as missing and flag it.
* Do not claim mobile platform work.
* Do not claim AI/ML ownership.
* Do not claim people management.

---

## 11) Output Construction Rules

Top fit reasons must be:

* specific and grounded
* no generic “strong communicator” phrasing
* each ≤ 15 words

Risk flags must be:

* concrete gaps or uncertainty
* each ≤ 15 words

Summary must be:

* 1 sentence
* ≤ 25 words
* capture why YES or why NO.

---

## 12) Required Output Template (Repeat)

You must output the human-readable block first, then the JSON object.
No other text.

```text
Decision: YES/NO
Score: [0–100]
Confidence: High/Medium/Low
Summary: [one sentence]

Top fit reasons:
[reason 1]
[reason 2]
[reason 3]

Risk flags:
[risk 1]
[risk 2]

Missing info (only if Confidence = Low):
[missing detail 1]
[missing detail 2]
[missing detail 3]
```

```

---

If you want, I can also rewrite your **wrapper** to match this v2.1 engine (small edits: new thresholds, overlap gate, completeness handling).
```
