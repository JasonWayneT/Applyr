---
trigger: always_on
---

# Dynamic Job-Fit Decision Engine (v4.0)

This file defines a deterministic YES/NO decision system for evaluating job descriptions. It dynamically leverages the target specifications, experience ranges, blocklists, and anchors defined in the injected **Candidate Preferences JSON**.

---

## 0) Purpose & Batch Logic

**Pass threshold:** `candidate_preferences.json` → `min_fit_score` (default **72**). Python uses `get_min_fit_score()`; do not use legacy **78** from archived docs.

1. **Initialize Sandbox:** Clear previous JD context; load only `workExperience.md` (Ground Truth) and `Candidate Preferences` (Targets).
2. **Fast Gate:** Kill poor fits, seniority mismatches, blocked industries, or solo traps instantly using criteria from `Candidate Preferences`.
3. **Transition Analysis & Scoring:** Score based on alignment with the Candidate's profile, experiences, and anchors.

---

## 1) Ground Truth Profile & Preferences
Evaluate the candidate using:
- **Ground Truth (`workExperience.md`):** The candidate's actual metrics, roles, and historical timeline.
- **Candidate Preferences (Injected JSON):** The explicit parameters for the target role, experience limits, blocklists, and key focus anchors.

---

## 2) Stage A: The Fast Gate (Instant Kill)
If any of the following triggers are met, return **Score: 0**, **Decision: NO**, and **Terminate Pipeline** for this JD.

### 2.1 Title & Tier Blocklist
- **Blocked Titles:** Reject if the **job title** contains whole-word matches from `blocked_titles` (not substring hits in the JD body).
- **Senior titles allowed:** "Senior Product Manager" (and similar) is **allowed** when stated required years are within `experience_range.max`.
- **Organization Role:** Reject if the role is explicitly "Founding," "First," "0-to-1," or "Sole" product professional unless permitted by preferences.
- **Management Constraints:** Reject if the role requires hiring or managing other people in that same function when forbidden by `preferences.no_people_management`.
- **Entry-level:** Reject intern programs, 0–1 years required, or explicit greenfield 0-to-1 ownership when `no_zero_to_one` is true.

### 2.2 Experience & Constraints
- **Years Required:** Reject if required years of experience exceeds `experience_range.max` in Candidate Preferences.
- **Blocked Industries:** Reject if the company operates in any of the `blocked_industries` listed in Candidate Preferences. **Enforced deterministically** by `scripts/industry_gate.py` at scout ingest and batch zero-token gate (`FR-170` / CR-027) before this LLM stage runs.
- **Domain Gate:** Reject if the role requires domain expertise explicitly marked as a "Soft Blocker" in the candidate's history (e.g., hands-on ML model training, Developer Auth) unless allowed.
- **AI tools vs AI PM:** Do **not** reject because the JD mentions AI tools, Copilot, or workflow automation. Reject only when the role requires **owning ML model development** or being the primary AI/ML product owner.

### 2.3 Location & Setting Gate
- **Home Base:** The candidate is located in the **San Diego, CA** area.
- **Remote Criteria:** If the role is explicitly "Remote", it is **ALLOWED** (provided it supports US hiring).
- **On-Site/Hybrid Criteria:** If the role is On-Site or Hybrid, it MUST be located within **50 miles of San Diego, CA**.
- **Trigger:** Reject and Terminate if the role is On-Site or Hybrid in any city outside of greater San Diego (e.g., New York, Chicago, Plano, Atlanta, Seattle, Charlotte, Sunnyvale, Canada). Any non-San Diego, non-remote physical location requirement is an instant kill.

---

## 3) Stage B: Full Scoring (0–100)

### A) Organizational Maturity (0-25)
*Does the candidate have a function-specific leader/mentor and team structure?*
- **22-25:** Perfect alignment with `preferences.structured_team_required` (mentions direct manager and a team).
- **15-21:** Implicitly part of a larger functional org.
- **0-14:** Solo trap (e.g., reports directly to a non-functional executive in a tiny startup).

### B) Seniority & Tenure Fit (0–25)
- **23-25:** High overlap with `experience_range` (within min and max targets). Senior title + 3–7 years required scores here.
- **0-17:** Demands experience above `experience_range.max` or explicit people-management of PMs/engineers.

### C) Technical & Execution Depth (0–25)
- **22-25:** High technical overlap with the `required_anchors` listed in preferences.
- **0-14:** Requires deep daily coding or non-relevant daily activities.

### D) The "Bridge" Alignment (0–25)
- **20-25:** High alignment between the company's pain space and the candidate's core historical wins.
- **0-14:** Low-impact or unrelated daily focus.

---

## 4) Thresholds & The "Anchor" Gate
**Total Score = (A+B+C+D) - Penalties.**

### 4.1 Penalties
- **Small Startup:** Apply a -50 penalty if the company size is below `preferences.max_company_size_penalty_threshold` and has high risk of solo/founding trap.

### 4.2 The "Two-Anchor Room" (Mandatory)
A **YES** decision requires at least **2 explicit overlaps** between the job description responsibilities and the `required_anchors` list in the Candidate Preferences. When `ANCHOR_GATE_ENABLED=1`, batch zero-token gate enforces this before LLM fit (`FR-172` / CR-028); default is LLM-only enforcement.

### 4.3 Final Decision
- **Score ≥ 85:** YES (Strong Fit).
- **Score 75–84:** YES (Conditional on Anchors).
- **Score < 75:** NO (Reject).

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