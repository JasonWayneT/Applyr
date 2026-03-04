# **Interview Cheat Sheet: EdVisorly - Product Manager, Partner Experience**

## **1. Prep Brief**
*   **Company Context:** EdVisorly is an early-stage edtech startup focused on helping universities and community colleges streamline the transfer student pipeline. 
*   **Team Priorities:** The Partner Experience PM is building the B2B SaaS side of the house. They need someone to standardize the messy, bespoke workflows of different universities (each with their own CRMs and Student Information Systems) into scalable platform features.
*   **The Hiring Manager's Headache:** Manual onboarding of college partnerships is blocking scale. Engineers are likely bogged down by custom data integrations for each new school. The product team needs rigorous agile hygiene (Jira, backlog management, sprint planning) to predictably ship integrations so Customer Success can onboard partners faster.
*   **Culture Sentiment:** Lean, mission-driven but "intense" (they literally said "we're intense and we like it that way" in previous JDs). They value execution, bias for action, and durable architectural choices over quick hacks.

---

## **2. STAR Mapping (Battle-Ready Stories)**

### **A. Core Problem Check: Workflow Discovery & Productization (Bellwether)**
*   **The JD Requirement:** "Productize manual or bespoke processes into scalable software."
*   **Context:** At Cision, we had a massive problem with stale data causing churn. The root cause was a brittle, internally patched legacy ETL process that had become a web of bespoke manual interventions.
*   **Action:** Conducted deep discovery on the ingestion workflow. Wrote the technical PRD to bypass the legacy architecture entirely and build a unified, automated integration to the central GPOD database.
*   **Result:** Eradicated the data drop-offs and removed the manual overhead required to support the old ingestion path.
*   **Bridge:** "Institutions often have decades of bespoke processes. My job is to map those out, identify the scalable denominators, and work with engineering to build an integration architecture that handles the variation without requiring a custom build every time."

### **B. Core Problem Check: Agile Delivery & Trade-offs (Security Backlog Framework)**
*   **The JD Requirement:** "Agile execution including backlog management, sprint planning, refinement... make thoughtful trade-offs."
*   **Context:** Constant tension between stability demands, a massive security backlog (~300 items), and sales integration requests.
*   **Action:** Implemented a rigorous capacity planning framework using T-shirt sizing and clear priority bands. Enforced strict Jira hygiene, ensuring every ticket attached to the roadmap was scoped and estimated before sprint planning.
*   **Result:** Resolved 90% of the security backlog over a year while still predictably shipping features. 
*   **Bridge:** "A roadmap is only as good as the sprint hygiene backing it. I believe in extreme clarity in the backlog so engineers never have to guess priority or requirements, which increases velocity natively."

### **C. Core Problem Check: APIs & Systems Integration (Premium Content)**
*   **The JD Requirement:** "Integrate thoughtfully with CRMs, Student Information Systems... APIs, data models."
*   **Context:** E-Staff wanted to commercialize premium content integrations (LexisNexis, Dow Jones).
*   **Action:** Worked with business stakeholders to map compliance limits. Translated these into technical requirements and collaborated directly with backend engineers on the data models required to handle expiration logic through the API layer.
*   **Result:** Successful integration with zero licensing compliance breaches.
*   **Bridge:** "When integrating with external systems like university CRMs, the data model decisions made early on dictate the scalability of the feature. I am highly comfortable living in that technical layer with engineers."

---

## **3. Strategic Questions for the Interviewer**
1. **Integration Architecture:** "Universities are notorious for having fragmented, localized systems (like various CRMs and SISs). How is the platform currently architecturalizing integrations? Are we building custom connectors per institution, or moving toward a unified API standard?"
2. **Prioritization Friction:** "When balancing the bespoke needs of a major new university partner against the scalability of the core platform, what frameworks does leadership currently use to make that trade-off?"
3. **Agile Maturity:** "The JD mentions 'continuous improvement to team processes.' Where is the engineering team's biggest friction point right now in the sprint cycle?"
4. **Partner Success:** "What is the primary bottleneck for the Implementation and CS teams today when bringing a new partner onto the platform?"
