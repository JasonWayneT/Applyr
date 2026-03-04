# **Interview Cheat Sheet: Better Collective - Product Manager**

## **1. Prep Brief**
*   **Company Context:** Better Collective functions as the parent company to major sports betting assets like Action Network, OddsChecker, and HLTV.org. They dominate the affiliate model (referring users to sportsbooks for CPA/Revenue Share). They are scaling heavily in the US post-PASPA and have active M&A strategies.
*   **Team Priorities:** They need to unify tech stacks, run aggressive A/B testing to optimize conversion funnels (content to bet), and manage real-time odds data with zero latency. 
*   **The Hiring Manager's Headache:** Navigating technical debt from acquisitions. Managing complex, multi-state regulations. Delivering high-uptime data streams during major events (Super Bowl). Running growth experiments on top of fragile architecture.
*   **Culture Sentiment:** Very data-driven, aggressive growth targets, requiring PMs who are technical enough to understand API latency but commercial enough to focus on Lifetime Value (LTV) and Average Revenue Per User (ARPU).

---

## **2. STAR Mapping (Battle-Ready Stories)**

### **A. Core Problem Check: Reliable Data & Architecture (The Bellwether Initiative)**
*   **The JD Requirement:** "Real-time data & live betting UX."
*   **Context:** Our $40M ARR platform at Cision relied on a legacy ETL pipeline that dropped 30-40% of critical media contact data. High churn risk.
*   **Action:** Conducted SQL analysis to prove the drop-off. Authored the technical PRD to bypass the legacy system and connect directly to the upstream GPOD database.
*   **Result:** Reduced stale-data complaints to zero. 
*   **Bridge:** "You need real-time odds to power the Action Network app. If the data pipelines are unreliable, the bettor loses trust and the affiliate funnel breaks. I bring the discipline to secure the pipeline."

### **B. Core Problem Check: Cross-Functional Alignment (Security vs. Features)**
*   **The JD Requirement:** "Lead sprint planning and cross-functional coordination."
*   **Context:** Deep technical debt, 300+ item security backlog, and conflicting demands from Sales and Engineering.
*   **Action:** Established a rigid capacity planning model utilizing T-shirt sizing and clear priority bands. Enforced strict stakeholder gatekeeping to prevent roadmap derailment.
*   **Result:** Resolved 90% of the security backlog over a year while still predictably shipping features. 
*   **Bridge:** "Growth experiments are only possible if engineering capacity is managed effectively. I know how to organize chaos and protect the team so they can ship."

### **C. Core Problem Check: Regulated/Complex Integrations (Premium Content)**
*   **The JD Requirement:** "Odds comparison & sportsbook integrations."
*   **Context:** E-Staff wanted to commercialize premium content integrations (LexisNexis, Dow Jones) that had massive legal and compliance rules on data expiration.
*   **Action:** Worked with business stakeholders to map compliance limits. Translated these into technical requirements for cross-platform implementation.
*   **Result:** Successful integration with zero licensing compliance breaches.
*   **Bridge:** "Given the variation in US state-by-state gambling regulations, integrating sportsbooks requires airtight technical compliance. I have experience mapping rigid legal constraints into engineering stories."

---

## **3. Strategic Questions for the Interviewer**
1. **M&A Tech Debt:** "With the steady stream of acquisitions like Action Network and OddsChecker, how is the product team balancing the need to unify legacy tech stacks versus shipping net-new conversion experiments?"
2. **Experimentation Velocity:** "Can you walk me through the current experimentation culture? How quickly can the team spin up A/B tests to optimize the affiliate conversion funnels?"
3. **Data Infrastructure:** "The JD mentions real-time data and live betting. What are the biggest architectural bottlenecks right now preventing the team from lowering latency or launching new insights faster?"
4. **Metrics Ownership:** "How are KPIs like ARPU and LTV attributed back to specific product changes, especially given the affiliate tracking models?"
