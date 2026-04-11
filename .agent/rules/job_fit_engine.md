---
trigger: always_on
---

# Jason Taylor – Job-Fit Decision Engine (v3.2, Team-BPM / IC Optimized)

This file defines a deterministic YES/NO decision system for evaluating multiple job descriptions in a batch pipeline. It is optimized for Jason's preference for **mid-level Product Manager roles (3-7 years)** within a **structured team environment** where direct PM leadership (Director/Senior PM) is present.

---

## 0) Purpose & Batch Logic
1. **Initialize Sandbox:** Clear previous JD context; load only `workExperience.md`.
2. **Fast Gate:** Kill poor fits, seniority mismatches, or "Solo PM" traps immediately.
3. **Transition Analysis:** Score based on mid-level PM fit with a strong "Direct Leadership" anchor.

---

## 1) Jason’s Ground Truth Profile (The Source of Truth)
*Refer to data/workExperience.md for all specific metrics.*
- **Core:** B2B SaaS Platform PM, roadmap ownership, technical integrations, data integrity.
- **Experience Level:** ~6 years (Product Manager / Product Owner). 
- **Transition Target:** Mid-level PM in a structured SaaS or Professional Services organization.
- **Hard Constraints:** NO People Management (of PMs), NO direct ML model training, NO "First/Solo PM" roles.

---

## 2) Stage A: The Fast Gate (Instant Kill)
If any trigger is met, return **Score: 0**, **Decision: NO**, and **Terminate Pipeline** for this JD.

### 2.1 Title & Tier Blocklist (Seniority Mismatch)
- **Title Blocklist:** JD contains: [Senior, Staff, VP, Head, Principal, Lead, Director, Growth].
- **Organization Role:** Role is "Founding PM," "First PM," or "Sole Product Professional."
- **Leading PMs:** Role requires hiring/managing other Product Managers.

### 2.2 Experience & Reporting
- **Years Required:** Role requires **8+ years** of experience (Jason has 6; 8+ implies seniority level he's avoiding).
- **Structure:** JD implies a solo contributor reporting directly to a non-product CEO in a small company (< 50 employees).

### 2.3 Technical & Domain "Hard Outs"
- **Pure ML/AI Research:** Owns model architecture/training (vs. using AI tools).
- **Non-Software:** Hardware, medical devices, or heavy manufacturing.
- **Pure Consumer:** 90%+ focus on TikTok-style "Viral Loops" without B2B infra.
- **Industry Blocklist:** Gambling, Sports Betting, Gaming, Ad Tech, Crypto, Web3.

---

## 3) Stage B: Full Scoring (0–100)

### A) The "Direct Leadership" Match (0-25)
*Does the candidate have space to grow under a mentor?*
- **22-25:** Mentions a direct manager (Director of Product, Senior PM) and a team of 3+ PMs.
- **15-21:** Implicitly part of a larger product org.
- **0-14:** High autonomy expected; reports to "Head of Product" who is a solo exec.

### B) Seniority Fit (0–25)
- **23–25:** Product Manager / PM II (IC Role), 3–6 years exp.
- **18–22:** Product Manager, 6-7 years exp.
- **0–17:** Requires 7+ years or "Senior" traits.

### C) Technical & Execution Depth (0–25)
- **22–25:** Integrations, data pipelines, reliability, security, or "Internal Platforms."
- **15–21:** General B2B feature work with engineering collaboration.
- **0-14:** Requires hands-on coding (Python/SQL) for daily output.

### D) "The Bridge" - Growth Potential (0–25)
- **20–25:** High (e.g., "Scale our API to support new integrations").
- **15–19:** Medium (e.g., "Workflow optimization for enterprise users").
- **0–14:** Low (e.g., "Manage Paid Ad budgets").

---

## 4) Thresholds & The "Anchor" Gate
**Total Score = (A+B+C+D) - Penalties.**

### 4.1 Penalties
- **Startup < 25 people:** -50 (High probability of "Solo PM" trap).
- **On-site (Non-Local):** -25 (unless relocation is explicitly provided).

### 4.2 The "Two-Anchor Room" (Mandatory)
A **YES** requires at least 2 explicit overlaps from:
1. Platform stability/reliability.
2. Complex data migrations/integrations.
3. Security/Risk prioritization.
4. B2B Enterprise workflow scaling.

### 4.3 Final Decision
- **Score ≥ 85:** YES (Strong Fit - Ideal Mid-level Team Role).
- **Score 78–84:** YES (Conditional on Anchors).
- **Score < 78:** NO (Reject).

---

## 5) Output Requirements (Human + JSON)
*Constraints: No em-dashes, no transition fluff, max lengths as defined below.*

### Human-Readable Block
```text
Decision: YES/NO
Score: [0-100]
Confidence: High/Medium/Low
Summary: [Max 25 words. Direct reasoning for fit/reject.]

Top fit reasons:
- [Reason 1, Max 15 words]
- [Reason 2, Max 15 words]

Risk flags:
- [Risk 1, Max 15 words]
- [Risk 2, Max 15 words]
```