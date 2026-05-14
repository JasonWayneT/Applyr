# Master Career Context Spec (v3.1)

```yaml
document_type: master_career_context_spec
primary_objective: preserve_ground_truth_career_history_and_prevent_hallucinations
intended_reader: ai_resume_and_cover_letter_generation_agent
human_readable: true
inputs:
  - user_work_history_logs
  - platform_architectural_maps
  - corporate_metrics_records
output:
  - verified_source_of_truth_context
optimization_order:
  - absolute_truthfulness
  - factual_grounding
  - metric_integrity
  - precise_plain_language_positioning
forbidden_behaviors:
  - inventing_revenue_or_retention_metrics
  - claiming_people_management_or_direct_reports
  - claiming_model_training_or_ai_engineering
  - using_internal_company_codenames
  - fabricating_customer_satisfaction_data
```

## Section 1: Role Identity & Positioning

Jason Taylor is a **B2B SaaS Platform Product Manager** with 6+ years of experience in technically complex, revenue-bearing environments. He operates close to engineering, infrastructure, and system architecture, but his focus is always on business outcomes—stabilizing platforms under resource constraints, reducing major churn drivers, enabling voluntary migrations, and aligning cross-functional teams.

### 1.1 Core Specialization Areas
*   **Platform Stabilization & Reliability**: Managing legacy components, resolving systemic outage patterns, and mitigating infrastructure risk.
*   **Data Integrity & Ingestion Systems**: Redesigning data pathways, resolving ingest drop-offs, and consolidating content feeds.
*   **Migration Strategy & Sunset Planning**: Structuring voluntary, value-driven transition programs to protect revenue during platform sunsets.
*   **Disciplined Prioritization under Constraint**: Capacity modeling, scope control, and security backlog triage amid layoffs and organizational shifts.
*   **Cross-Functional Alignment**: Building trust with engineering managers, database administrators, DevOps, legal, customer experience, and sales.

### 1.2 Target Role Level & Positioning
*   **Target Role**: Mid-level Product Manager / PM II (IC Role) with 3–7 years of experience.
*   **Structured Mentorship Fit**: Optimized to grow under direct PM leadership (e.g., reporting to a Director of Product or Senior PM) within a larger structured product organization.
*   **Pragmatic Problem Solver**: Positioned as a hands-on, highly literate platform PM who thrives inside legacy complexity and imperfect data environments.

### 1.3 Exclusion Zones (What He is NOT)
*   **NOT a 0-to-1 Greenfield PM**: Does not specialize in initial consumer UX innovation or launching unproven products.
*   **NOT an AI/ML Product Lead**: Has not built, trained, or owned machine learning or predictive models.
*   **NOT a People Manager**: Has never hired, fired, or formally managed other Product Managers or engineers.
*   **NOT a Revenue/Billing Owner**: Has never owned billing, invoicing, payments, or direct revenue-generating pricing systems.

---

## Section 2: Career Chronology & Reporting

```mermaid
graph TD
    subgraph Zero to Sixty Media [2017 - 2019]
        Z[Account Manager / Product Owner]
    end
    subgraph Sterkly Services [2019 - 2021]
        S[Product Manager / Product Owner]
    end
    subgraph Cision [2021 - 2026]
        C[Product Manager]
    end
    Z --> S --> C
```

### 2.1 Employer Timeline Details
| Employer | Role | Start Date | End Date | Reporting Line | Team Footprint |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Cision** | Product Manager | September 2021 | January 2026 | Reported to Director of Product (first 3 months), then operated autonomously partnering with Engineering Managers. | Fluctuated between 6 and 15 engineers across up to 3 cross-functional teams (including Core, Next-Gen Core B2B SaaS Platform, and Migration Tooling). |
| **Sterkly Services** | Product Manager / Product Owner | February 2019 | August 2021 | Reported to Head of Product / Operations. | Partnered with 1 cross-functional team of 5-8 engineers and QA. |
| **Zero To Sixty Media** | Account Manager / Product Owner | June 2017 | January 2019 | Reported to Account & Operations Director. | Partnered with 2-3 developers and external vendor teams. |

### 2.2 Verified Cross-Functional Partners (Cision — DO NOT INVENT BEYOND THIS LIST)

This is the exhaustive list of teams and stakeholders Jason actually collaborated with at Cision. AI models MUST select cross-functional references only from this list. Do NOT name teams drawn from a job description if they are not on this list.

| Partner | Relationship Depth | Context |
| :--- | :--- | :--- |
| **Engineering** | Extremely close — primary daily partner | Owned the product roadmap; worked directly with Engineering Managers and engineers across 2-3 teams simultaneously. |
| **Database Administration (DBA)** | Very close | Coordinated on infrastructure improvements, index stability, and data pipeline work; had a primary DBA stakeholder for quarterly planning. |
| **DevOps** | Very close | Collaborated on server migrations, monitoring/alerting setup, cloud consolidation, and capacity planning; mid-quarter interrupts frequently required direct coordination. |
| **Customer Experience (CX)** | Close | Regular partner for ticket triage prioritization, high-risk account escalations, and understanding customer pain points. |
| **Customer Support** | Close | Supported and partially absorbed triage responsibilities as dedicated C3 support was wound down; built Jira scoring system with support workflow in mind. |
| **Sales** | Regular | Used Sales data (Salesforce, closed-lost analysis) to justify roadmap priorities; partnered on communicating platform stability to prospects. |
| **Account Management** | Regular | Coordinated on high-risk account retention, the critical save program, and voluntary migration timing at renewal. |
| **Legal** | Regular | Required sign-off for dead account data deletion (compliance with SLAs), premium content licensing rules, and regional data regulations. |
| **InfoSec** | Regular | Worked through penetration test vulnerability backlog; coordinated on security remediation prioritization and timelines. |
| **Product Marketing** | Regular | Collaborated during premium content integrations and go-to-market coordination for new capabilities. |
| **Executive / Presidential Leadership** | High visibility | Presented the quarterly roadmap to the full product and engineering organization (~200-300 people including CEOs and executive leadership); navigated three executive team transitions. |

**Roadmap ownership note:** Jason constructed the quarterly roadmap by gathering inputs from all of the above teams, synthesized competing priorities into a single plan, and presented it to the entire organization before each quarter. He then drove execution of that roadmap through each quarter, managing mid-quarter interrupts and trade-offs in real time.

---

## Section 3: Approved Plain-Language Vocabulary Translation Map

To eliminate technical obscurity and prevent ATS parsing failure, all company-specific internal codenames MUST be systematically translated into high-impact, plain-language business equivalents using this master map:

| Fact ID | Internal Codename | Plain-Language / Business Equivalent | Context & Purpose |
| :--- | :--- | :--- | :--- |
| **VOC-01** | **Platform Data Remediation** | Centralized platform data remediation initiative | Jason's signature architectural bypass project that directly linked Centralized Contact Database to Core B2B SaaS Platform, eliminating stale data complaints. |
| **VOC-02** | **Core B2B SaaS Platform** | Customer-facing B2B SaaS media monitoring & contact database platform | The primary revenue-bearing legacy platform Jason managed ($40M ARR, 25,000 active users). |
| **VOC-03** | **Core Platform Infrastructure** | Underlying core infrastructure and shared platform layer | The core technical foundation that supported Core B2B SaaS Platform and handled shared data services. |
| **VOC-04** | **Centralized Contact Database** | Centralized contact source-of-truth database | The upstream master database of journalists and outlets (not owned by Jason; consumed via Platform Data Remediation). |
| **VOC-05** | **Upstream Media Monitoring Platform (Upstream Media Monitoring Platform)** | Upstream enterprise content monitoring system | The corporate-wide master media monitoring ingest platform (not owned by Jason; consumed via Media Monitoring Ingestion Platform). |
| **VOC-06** | **Media Monitoring Ingestion Platform** | Core monitoring ingestion platform | The Core B2B SaaS Platform-specific content consumption platform owned and maintained by Jason to process data from Upstream Media Monitoring Platform. |
| **VOC-07** | **Nexus / EDP** | Unified enterprise shared data architecture | The new shared data initiative meant to unify data across products (not owned by Jason; integrated with directionally). |
| **VOC-08** | **Critical Save Program** | High-risk account retention program | The proactive retention effort focused on migrating vulnerable accounts likely to churn. |
| **VOC-09** | **White Glove Accounts** | Premium high-revenue enterprise clients | Enterprise accounts receiving prioritized, custom triage and escalation paths. |
| **VOC-10** | **Premium Content Initiative** | Compliance-gated third-party content integration | An executive-led effort to integrate premium sources (NYT, Bloomberg, Factiva) with strict retention workflows. |
| **VOC-11** | **DT Search** | Platform content indexing engine | The technical search component used to index customer news database tables. |

---

## Section 4: Rigorous Ground-Truth Metrics Matrix

These metrics are the **absolute bounds of truth**. They must never be extrapolated, inflated, or modified under any circumstances:

| Fact ID | Metric Category | Verified Value | Ground-Truth Scope & Meaning |
| :--- | :--- | :--- | :--- |
| **MET-01** | **core customer-facing B2B SaaS platform Revenue** | **$40,000,000 ARR** (approximate) | Total annual recurring revenue tied to the customer-facing legacy platform during Jason's tenure. |
| **MET-02** | **Customer Scale** | **~3,500 active accounts** | Total paying businesses and enterprise clients supported on the legacy platform. |
| **MET-03** | **User Scale** | **~25,000 active users** | Total daily/weekly active individual professional users accessing the platform. |
| **MET-04** | **Platform Churn Rate** | **7% annually** (approximate) | Extremely stable retention rate, including voluntary migrations to newer corporate systems. |
| **MET-05** | **Infrastructure Savings** | **$1,000,000 - $2,000,000** | Cumulative cost reduction achieved through resources optimization and dead account cleanups. |
| **MET-06** | **Contact Data Loss** | **40% loss** (pre-remediation) | Historical data drop-off rate between Centralized Contact Database and Core B2B SaaS Platform due to layered legacy ETL pipelines. |
| **MET-07** | **Data Drop-off Resolved** | **100% reduction** | Total elimination of stale-contact complaints tied to the data pipeline post-Platform Data Remediation launch. |
| **MET-08** | **Security Risk Backlog** | **90% resolved** (approximate) | Resolution of high-priority security vulnerabilities from an initial backlog of ~300 items. |
| **MET-09** | **Customer Databases** | **~200 SQL databases** | The physical database footprint managed and maintained under Core Platform Infrastructure. |
| **MET-10** | **Voluntary Migrations** | **~700 accounts** (approximate) | Total successful, non-disruptive migrations completed using the custom phased tooling. |
| **MET-11** | **Fulfillment Automation** | **$288,000 in contracts** | Total laptop vendor contract value managed, saving **$8,500 per quarter** ($34,000/yr) via automation. |
| **MET-12** | **Onboarding Automation** | **$22,100 saved annually** | Total cost savings from an internal automation project that streamlined user onboarding into Salesforce. |
| **MET-13** | **Sterkly Revenue Sustained** | **~$1M - $3M** (estimated) | Approximate revenue stream unlocked or sustained by resolving the Safari extension certificate bottleneck at Sterkly. |
| **MET-14** | **Certificate Cost Savings** | **~$100 per certificate** | Per-unit savings from building an in-house certificate procurement workflow vs. sourcing from external vendors. |
| **MET-15** | **Conversion Improvement** | **~40%** (estimated) | Approximate increase in prospect-to-customer conversion rate from the landing page and Salesforce onboarding automation at Zero To Sixty. |
| **MET-16** | **Fulfillment Scale** | **10 manual → 100+ units/day** | Laptop fulfillment program throughput improvement after replacing manual setup with automated script-based deployment. |

---

## Section 5: Role-by-Role Deep Dive Specifications

### 5.1 Cision (September 2021 - January 2026)
*   **Context & Constraints**: Legacy $40M ARR platform slated for sunset, operating under shrinking engineering headcount, repeated layoffs (3-4 cycles), executive turnover (3 management teams), and a complete lack of dedicated customer support resources.
*   **Owned Systems**: Customer-facing B2B SaaS media monitoring & contact database platform (Core B2B SaaS Platform) and underlying core infrastructure layer (Core Platform Infrastructure).
*   **Unowned Systems**: Centralized contact source-of-truth database (Centralized Contact Database), upstream enterprise content monitoring system (Upstream Media Monitoring Platform), and Cision One next-gen platforms.

#### Approved Accomplishments Inventory
*   **[ACC-101] Platform Stabilization**: Mitigated recurring indexing server crashes by implementing proactive storage capacity monitoring, alerting thresholds, and legal-approved cleanups of stale accounts, reducing overall service outages.
*   **[ACC-102] Data Remediation**: Conceived and drove a centralized platform data remediation initiative that bypassed failing legacy ETL paths to integrate directly with the upstream source-of-truth database, eliminating a 40% data drop-off rate and reducing stale-data complaints to zero.
*   **[ACC-103] Security Backlog Triage**: Prioritized a massive backlog of ~300 penetration test vulnerabilities using a balanced, risk-weighted severity scoring filter, resolving 90% of security risks over a one-year phased roll-out without stalling core roadmap development.
*   **[ACC-104] Controlled Migration Strategy**: Partnered with upgrades, engineering, and customer experience teams to build and deploy phased voluntary migration tooling, successfully transitioning ~700 high-risk accounts at renewal times without customer friction.
*   **[ACC-105] Prioritization & Capacity Discipline**: Replaced reactive planning with a rigorous, PTO-adjusted capacity model based on workday-hours per engineer, using T-shirt sizing with uncertainty bands to manage resource allocations across stability, compliance, and planned roadmap items.
*   **[ACC-106] Mobile UVPM Implementation**: Implemented mobile Unique Visitors Per Month (UVPM) support for the media outlet database, closing a critical competitive gap and reducing churn risk among core database customers who were actively evaluating alternatives due to the platform's desktop-only audience metrics.
*   **[ACC-107] Compliance & Privacy Workflows**: Built privacy and compliance workflows to handle contact data removal requests, enforce regional licensing constraints (including Australian and UK markets), and maintain adherence to third-party platform terms across Twitter, Google, and Yahoo data sources.
*   **[ACC-108] Customer Ticket Triage System**: Designed and maintained a structured Jira ticket prioritization system scoring inbound customer issues on revenue impact, frequency, and severity, with a dedicated escalation channel for high-risk accounts that automatically surfaced churn-risk tickets at the front of the queue.
*   **[ACC-109] Quarterly PI Planning & Roadmap Communication**: Led quarterly PI planning cycles, synthesizing inputs from CX, legal, DevOps, DBA, sales, and go-to-market teams into a single prioritized roadmap and presenting it to approximately 200-300 stakeholders — including executives — before each quarter.
*   **[ACC-110] Cross-Team Knowledge Transfer**: Established structured cross-training across engineering teams to eliminate single points of failure on critical platform components, maintaining operational continuity through three to four rounds of layoffs and voluntary attrition.

#### Factual Anti-Claims & Boundaries (DO NOT CLAIM)
*   *DO NOT claim Core B2B SaaS Platform returned to revenue growth (it was intentionally winding down).*
*   *DO NOT claim that any specific dollar amount of revenue was retained directly due to Platform Data Remediation.*
*   *DO NOT claim that the Kafka pipeline migration or CI/CD modernization was fully completed (they were scoped/initiated but not finalized).*
*   *DO NOT claim direct management or hiring of engineering team members.*
*   *DO NOT claim ownership of the company's premium content strategy or licensing contracts.*

---

### 5.2 Sterkly Services (February 2019 - August 2021)
*   **Context & Constraints**: Fast-paced professional services and digital workflow environment requiring rigorous requirements translation and stakeholder alignment to keep product delivery moving under tight timelines.
*   **Owned Systems**: Internal workflows, project requirements, and operational product delivery tools.

#### Approved Accomplishments Inventory
*   **[ACC-201] Operational Bottleneck Reduction**: Analyzed and optimized internal team workflows by standardizing requirements gathering, resolving resource conflicts, and facilitating regular cross-functional alignment sessions to maintain consistent delivery.
*   **[ACC-202] Technical-Business Translation**: Translated complex business constraints and operational requirements into granular, engineering-ready product specs, partnering with a team of 5-8 developers to ensure accurate, on-time delivery.
*   **[ACC-203] Critical Revenue Bottleneck Resolution**: Resolved a critical distribution bottleneck for a macOS security product by developing an in-house browser extension certificate procurement workflow — eliminating dependency on unreliable third-party vendors, saving approximately $100 per certificate, and sustaining an estimated $1M-$3M in product revenue that had been blocked.
*   **[ACC-204] QA Ownership & Global Team Coordination**: Owned backlog management and led QA processes for a macOS security product, coordinating with a globally distributed engineering team across three countries to maintain release cadence and product quality standards.

#### Factual Anti-Claims & Boundaries (DO NOT CLAIM)
*   *DO NOT claim people management, hiring, or direct leadership of PMs.*
*   *DO NOT claim ownership of any customer-facing SaaS core products.*
*   *DO NOT claim any specific revenue growth or funding round attribution.*
*   *DO NOT name the specific product ("Airo") — it is under NDA. Describe generically as "a macOS security product."*

---

### 5.3 Zero To Sixty Media (June 2017 - January 2019)
*   **Context & Constraints**: Operational agency and logistics environment managing vendor contracts, manual client onboarding, and delivery pipelines with limited engineering overhead.
*   **Owned Systems**: Internal fulfillment programs, client onboarding pipelines, and operational tools.

#### Approved Accomplishments Inventory
*   **[ACC-301] Laptop Fulfillment Automation**: Managed a laptop fulfillment program governing $288,000 in vendor contracts, replacing a manual setup process with a custom automated deployment script — scaling throughput from 10 manual setups per day to 100+ units processed unattended and saving $8,500 per quarter ($34,000 annually).
*   **[ACC-302] Onboarding Workflow Optimization**: Co-created and optimized an internal onboarding automation tool that streamlined new customer data mapping into Salesforce, reducing manual overhead and saving $22,100 annually.
*   **[ACC-303] Conversion Funnel & Lead Automation**: Built the company's first professional landing page and automated prospect onboarding funnel, integrating a website builder with Salesforce to eliminate manual account manager tasks, increasing estimated conversion rates by approximately 40%.

#### Factual Anti-Claims & Boundaries (DO NOT CLAIM)
*   *DO NOT claim ownership of the agency's primary client strategy or accounts.*
*   *DO NOT claim to have built the automation tools single-handedly (worked with 2-3 developers).*
*   *DO NOT claim direct budget ownership or P&L management beyond the specified vendor contracts.*
*   *DO NOT state the 40% conversion figure as verified — it is an estimate from memory.*

---

## Section 6: No-Inference Zones & Execution Guardrails

To prevent any form of hallucination, all AI models generating materials for Jason Taylor MUST run these strict validation checks before outputting any text:

### 6.1 Factual Validity & ID-Traceability Tests
1.  **Do NOT physically print Fact IDs inside generated Resumes or Cover Letters.** All IDs (`[ACC-101]`, `[MET-01]`, etc.) are internal validation keys only. They must never appear in final text or compiled PDFs.
2.  **Verify that every single fact, metric, and responsibility traces back to a Fact ID.** The specific wording, tone, and framing can be tailored to the job description, but the core underlying facts must match an active ID (`VOC-*`, `MET-*`, or `ACC-*`) in this spec.
3.  **Is this metric explicitly listed in Section 4?** If not, remove it immediately. (Do not guess or calculate percentages, NPS scores, or retained revenue).
4.  **Does this sentence use an internal company codename?** If yes, replace it with its plain-language equivalent from Section 3.
5.  **Is there any mention of "Platform & Ingestion Systems"?** If yes, replace it with "Platform & Ingestion Systems" or "Platform & Ingestion Infrastructure".
6.  **Are there any em-dashes (`—` or `--`) used parenthetically?** If yes, replace them with clean commas or subordinate clauses.
7.  **Does the text imply Jason was a "Senior" PM, "Director," or managed other PMs?** If yes, downgrade the title to "Product Manager" or "Product Owner" to preserve mid-level positioning.
8.  **Does the text claim involvement in AI, ML, or model training?** If yes, remove it completely. (Jason's domain is technical platform infrastructure and data integrity).

### 6.2 Truth-Seeking Fallback Protocol
If any required information or context is missing from this spec, the AI must never invent details. Instead, output:
*   `"Insufficient data provided."` OR
*   `"This was not specified in the master context."`

---

## Section 7: Education

*   **Bachelor of Business Administration, Major in Management** — National University, San Diego, California, 2019

