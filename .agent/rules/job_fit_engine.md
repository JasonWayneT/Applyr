---
trigger: always_on
---

# Dynamic Job-Fit Decision Engine (v4.0)

This file defines a deterministic YES/NO decision system for evaluating job descriptions. It dynamically leverages the target specifications, experience ranges, blocklists, and anchors defined in the injected **Candidate Preferences JSON**.

---

## 0) Purpose & Batch Logic
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
- **Blocked Titles:** Reject if the JD title contains any terms found in `blocked_titles` from the Candidate Preferences.
- **Organization Role:** Reject if the role is explicitly "Founding," "First," "0-to-1," or "Sole" product professional unless permitted by preferences.
- **Management Constraints:** Reject if the role requires hiring or managing other people in that same function when forbidden by `preferences.no_people_management`.

### 2.2 Experience & Constraints
- **Years Required:** Reject if required years of experience exceeds `experience_range.max` in Candidate Preferences.
- **Blocked Industries:** Reject if the company operates in any of the `blocked_industries` listed in Candidate Preferences.
- **Domain Gate:** Reject if the role requires domain expertise explicitly marked as a "Soft Blocker" in the candidate's history (e.g., hands-on ML model training, Developer Auth) unless allowed.

---

## 3) Stage B: Full Scoring (0–100)

### A) Organizational Maturity (0-25)
*Does the candidate have a function-specific leader/mentor and team structure?*
- **22-25:** Perfect alignment with `preferences.structured_team_required` (mentions direct manager and a team).
- **15-21:** Implicitly part of a larger functional org.
- **0-14:** Solo trap (e.g., reports directly to a non-functional executive in a tiny startup).

### B) Seniority & Tenure Fit (0–25)
- **23-25:** High overlap with `experience_range` (within min and max targets).
- **0-17:** Demands experience outside the target bounds or requires senior-level traits.

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
A **YES** decision requires at least **2 explicit overlaps** between the job description responsibilities and the `required_anchors` list in the Candidate Preferences.

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