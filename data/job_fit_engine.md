# Job-Fit Decision Engine (Generic v1.0)

This file defines a deterministic YES/NO decision system for evaluating job descriptions. It leverages variables defined in `data/candidate_preferences.json`.

---

## 0) Instruction for AI
Before running this engine, you **MUST** read:
1. `data/candidate_preferences.json` (The "Target")
2. `data/workExperience.md` (The "Source of Truth")

---

## 1) Level 1: The Fast Gate (Instant Kill)
If any trigger is met, return **Score: 0**, **Decision: NO**, and Terminate.

### 1.1 Seniority & Title Blocklist
- **Industry Blocklist:** Gambling, Sports Betting, Ad Tech, Crypto, Web3, Autonomous Vehicles, Automotive, Autonomy, Robotics.
- **Rule:** If the **job title** (first line or `Title:` header) contains any term from `blocked_titles` using whole-word match. Do **not** scan the full JD body for title blocklist terms.
- **Rule:** **"Senior" in the title alone is NOT a disqualifier** when stated required years are within `experience_range` (e.g. "Senior Product Manager" with 3–6 years required is allowed).
- **Rule:** Reject titles containing Lead, Director, Head, VP, Staff, Principal, Group Product Manager, or "Manager of" people.
- **Rule:** If the role is explicitly "Founding," "First," or "Solo" (unless allowed in preferences).
- **Rule:** If the role requires management of other people in that same function (unless allowed).
- **Rule:** Reject entry-level signals: intern programs, 0–1 years required, or explicit greenfield 0-to-1 ownership when `no_zero_to_one` is true.

### 1.2 Experience & Constraints
- **Rule:** If required years of experience exceeds `experience_range.max` (deterministic years gate may already reject).
- **Rule:** Do **not** reject solely because the JD mentions AI tools, Copilot, or "AI-native" workflow unless the role requires **owning ML model development**, training models, or being the primary AI/ML product owner.
- **Rule:** If the company is in `blocked_industries`.
- **Rule:** If the role requires domain expertise explicitly marked as a "Soft Blocker" in the candidate's history (e.g., ML modeling, Developer Auth).

---

## 2) Level 2: Weighted Scoring (0–100)

### A) Organizational Maturity (0-25)
*Does the candidate report to a function-specific leader?*
- **25:** Mentions a direct manager (e.g., Director of Product) and a team of peers.
- **15:** Implicitly part of a larger org.
- **0:** Reports to a non-functional Exec (e.g., CEO) in a small company (Solo trap).

### B) Seniority & Tenure Fit (0–25)
- **25:** Perfect overlap with `experience_range` (e.g., 3-6 years). "Senior" title with 3–7 years stated requirement scores here.
- **15:** Slightly high or low but within acceptable deviation.
- **0-10:** Only when JD requires more than `experience_range.max` years or explicit people-management of PMs/engineers.

### C) Technical & Execution Depth (0–25)
- **25:** High overlap with the `required_anchors` list in preferences.
- **10:** General functionality with no specific anchor match.

### D) Growth & Interest (0–25)
- **25:** Explicit mention of scaling or optimization projects that match the candidate's history.

---

## 3) Level 3: The "Anchor" Gate (Mandatory)
A **YES** requires at least **2 explicit overlaps** from the `required_anchors` list found in `candidate_preferences.json`.

---

## 4) Final Thresholds
- **Score ≥ 85:** YES (Strong Fit).
- **Score 75–84:** YES (Conditional).
- **Score < 75:** NO (Reject).
