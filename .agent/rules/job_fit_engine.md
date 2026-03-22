---
trigger: always_on
---

# Jason Taylor – Job-Fit Decision Engine (v2.5, Batch & Transition Optimized)

This file defines a deterministic YES/NO decision system for evaluating multiple job descriptions in a batch pipeline. It is optimized for Jason's transition from Platform PM to Growth/General PM while maintaining a strict "Context Firewall."

---

## 0) Purpose & Batch Logic
Evaluate JDs at scale. For each JD in a batch:
1. **Initialize Sandbox:** Clear previous JD context; load only `workExperience.md`.
2. **Fast Gate:** Kill poor fits immediately to save processing tokens.
3. **Transition Analysis:** Score based on "Growth" potential vs. "Platform" debt.

---

## 1) Jason’s Ground Truth Profile (The Source of Truth)
*Refer to data/workExperience.md for all specific metrics.*
- **Core:** B2B SaaS Platform PM, roadmap ownership, technical integrations, data integrity.
- **Transition Target:** Growth/General PM (leveraging platform/infra for business outcomes).
- **Hard Constraints:** NO People Management (of PMs), NO direct ML model training, NO pure consumer "viral loop" marketing.

---

## 2) Stage A: The Fast Gate (Instant Kill)
If any trigger is met, return **Score: 0-30**, **Decision: NO**, and **Terminate Pipeline** for this JD.

### 2.1 Seniority & Management (Level Mismatch)
- Requires managing other PMs (Director, VP, Group PM, "Lead of PMs").
- Requires 10+ years of experience (Jason is mid-level/Senior IC).
- Explicitly entry-level/APM/Internship.

### 2.2 Technical & Domain "Hard Outs"
- **Pure ML Research:** Role is owning model architecture/training (vs. using AI tools).
- **Non-Software:** Hardware, firmware, medical devices, or heavy manufacturing.
- **Legacy ERP:** Deep expertise in SAP, Oracle, or Mainframe systems.
- **Niche Compliance:** Required deep PCI/Payments or HIPAA expertise (unless transferable).

### 2.3 Growth Misalignment
- **Pure Marketing Growth:** 90%+ focus on SEO, Paid Ads, or "Viral Loops" without product/infra technicality.

---

## 3) Stage B: Full Scoring (0–100)

### A) Seniority Match (0–25)
- **23–25:** Senior PM / PM II (IC Role), 4–8 years exp.
- **15–22:** "Lead PM" (IC) or Senior with high ambiguity.
- **0–14:** Director/VP signals or < 3 years exp.

### B) Product Model & Transition Fit (0–25)
- **22–25:** B2B SaaS, Platform-led Growth, or API-first products.
- **18–21:** General B2B SaaS with heavy workflow/data focus.
- **10–17:** B2B2C or Prosumer tools.
- **0–9:** Pure consumer-only (TikTok-style) or non-SaaS.

### C) Technical & Execution Depth (0–25)
- **22–25:** Integrations, data migrations, reliability, security, or "Internal Platforms."
- **15–21:** General feature PM-ing with strong engineering collaboration.
- **0–14:** Requires hands-on coding (Python/SQL) or "Scientific" ML research.

### D) "The Bridge" - Growth Potential (0–25)
*How well can Jason's Platform background solve their Growth problems?*
- **20–25:** High (e.g., "Scale our API to support 10x users").
- **15–19:** Medium (e.g., "Improve onboarding for enterprise customers").
- **0–14:** Low (e.g., "Optimize Facebook Ad spend").

---

## 4) Thresholds & Overlap Gate (Slightly Tighter)
**Total Score = (A+B+C+D) - Penalties.**

### 4.1 Penalties
- **Mobile-Only Focus:** -15 (Jason is Web/Platform focused).
- **Heavy Design/UX-Led:** -10 (Jason is Data/Infra focused).
- **On-site (Non-Local):** -25 (unless relocation is explicitly provided).

### 4.2 The "Two-Anchor" Rule
Even with a high score, a **YES** requires 2 explicit overlaps from:
1. Platform stability/reliability.
2. Complex data migrations/integrations.
3. Security/Risk prioritization (300+ item backlogs).
4. B2B Enterprise workflow scaling.

### 4.3 Final Decision
- **Score ≥ 80:** YES (Strong Fit).
- **Score 72–79:** YES (Conditional on "Two-Anchor" Rule).
- **Score < 72:** NO (Efficient Reject).

---

## 5) Output Requirements (Human + JSON)
*Constraints: No em-dashes, no chain-of-thought, max lengths as defined below.*

### Human-Readable Block
```text
Decision: YES/NO
Score: [0-100]
Confidence: High/Medium/Low
Summary: [Max 25 words. Direct reasoning for fit/reject.]

Top fit reasons:
- [Reason 1, Max 15 words]
- [Reason 2, Max 15 words]
- [Reason 3, Max 15 words]

Risk flags:
- [Risk 1, Max 15 words]
- [Risk 2, Max 15 words]