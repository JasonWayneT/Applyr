# SESSION HANDOFF — 2026-07-23 — Tier 2 batch, handed to Antigravity

**Purpose of this doc:** this is a cross-harness handoff. Claude Code drafted and verified the Tier 1 batch (6 companies, all landed in `data/submissions/`) in the same session that produced this file. Jason is now testing whether Antigravity can pick up the Tier 2 batch below and run the same `generate-submission` process independently, without this chat history.

## Instructions for the agent picking this up (Antigravity or otherwise)

1. Read `AGENTS.md` at the repo root first — it is byte-identical to `CLAUDE.md` and is the ground-truth rules doc (anti-hallucination rules, forbidden language, exact document structure, Required Verification commands).
2. Read `data/workExperience.md` (ground truth for every claim) and `data/master_claims.json` (`tags` field only — never `text`/`cover_story`).
3. Read and follow `.claude/skills/generate-submission/SKILL.md` directly, in full, as plain instructions — there is no automatic skill-loading step in this harness, so this file will not surface on its own. It is the authoritative Stage 0/1/2/3 process. Note its 2026-07-23 addition: **title/role family (Program Manager, Technical Program Manager, etc.) is never itself a reject reason** — several companies below are titled Program Manager and that is expected, not a problem.
4. The 9 companies below already passed Stage 0 triage in the prior Claude Code session — don't re-litigate the PASS decision, go straight to `stage0_fit_gate.json` + Stage 1 authoring, using the flagged gap noted for each as the thing Stage 1 needs to honestly bridge.
5. **Do not generate `Interview_Cheat_Sheet.md`** — removed from Stage 3 as of 2026-07-23 (wastes tokens on submissions that may never reach interview stage; also implies web research this pipeline doesn't do). Build it later, on demand, only once a real interview is scheduled.
6. **Do not touch `data/jobagent.sqlite` directly** — no DB reads or writes. If drafting produces `data/submissions/{company}/` folders with both PDFs present, the Applyr app's own `reconcileOrphanSubmissionFolders()` will auto-create the `jobs` DB row on its own next poll (a bug in that function was fixed 2026-07-23, so this should now work cleanly — one row per company, correct title, no duplicates). Report each submission's status, don't try to insert or fix DB rows yourself.
7. Three companies below are marked **STOP — needs Jason's call** and must not be drafted without his explicit go-ahead. Report them back as open questions, don't guess.

---

## Tier 2 — clear to draft (6 companies)

### 1. SambaSafety — Senior Product Manager, Telematics
Company: SambaSafety, driver monitoring/risk-scoring software (fleet risk, InsurTech).
**Flagged gap:** InsurTech/telematics domain itself is unfamiliar to Jason — bridge via his data-platform/API-first product thinking and data-pipeline background (Cision's ~200 SQL databases, data remediation work), not via any InsurTech-specific claim.

Job posting (verbatim), URL: https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?cid=12b42754-ce4b-494b-8ac4-b514a41ae8bf&ccId=19000101_000001&lang=en_US&jobId=9200820048709_1&&source=EN

"Who we are: Hi, we're SambaSafety and we offer the industry's most comprehensive driver monitoring software. Our mission is promoting safer communities by reducing risk through data insights.

What You'll Do: We are looking for a Senior Telematics Product Manager to own the strategy, roadmap, and execution of our telematics data platform and driver risk scoring products. This is a high-impact, end-to-end product ownership role sitting at the intersection of connected vehicle technology, fleet risk management, and InsurTech — and you will be responsible for translating complex data capabilities into products that deliver measurable outcomes for fleet operators, insurance carriers, and their shared customers. You will define what we build, why we build it, and how it reaches the market. You will work closely with customers, engineering, data science, design, sales, and commercial partners.

Responsibilities: Define and maintain a 12-24 month product roadmap for the telematics data platform, grounded in customer insight, market intelligence, and business priorities. Set clear product OKRs and success metrics. Make and communicate prioritization decisions transparently, including trade-offs between new capability, platform reliability, and technical debt. Own the product vision for how telematics data is ingested, processed, normalized, scored, and surfaced. Drive API-first product thinking: define developer-facing APIs, webhooks, and data integrations. Collaborate with data science and engineering teams to shape driver risk scoring. Champion platform scalability, data quality, and reliability as product-level concerns. Conduct structured discovery with fleet risk managers, loss control professionals, insurance underwriters, brokers. Partner with sales, marketing, customer success on go-to-market strategy. Track product-level revenue contribution, adoption rates, retention metrics. Lead planning, backlog refinement, release management. Produce requirements, user stories, acceptance criteria, API specifications.

Essential: 5+ years of product management experience, with at least 2-3 years in a senior role. Excellent stakeholder management and customer communication — influence without authority across engineering, commercial, executive audiences. Demonstrable domain expertise in one or more of: vehicle telematics, fleet risk management, usage-based insurance, connected vehicle data. Strong technical fluency — able to engage credibly with engineering and data science on API architecture, data pipeline design, scoring model logic. Experience defining and launching API-first or data-as-a-product capabilities. Proven ability to translate ambiguous market opportunities into structured product strategies.

Benefits and Perks: Flexible PTO, 401k Employer Match, Healthcare Benefits, remote friendly."

---

### 2. Incisive — Senior Product Manager
Company: Incisive, dental integrations platform (~650 doctors, 95%+ retention).
**Flagged gap:** small, high-ownership team framing — watch that the resume/letter frame the integrations-ownership scope honestly as an established company's existing product domain, not as founding/0-to-1 work (Jason's Exclusion Zone: NOT a 0-to-1 greenfield PM).

Job posting (verbatim), URL: https://deep-end-talent-strategies.breezy.hr/p/139bc36df37c-senior-product-manager?state=published

"Incisive is building a better model for restorative dentistry. Independent practices are under pressure: lab consolidation is accelerating, digital dentistry has arrived, but most practices are only halfway there. We solve that through one partnership: curated labs matched to specific case types, no-cost digital equipment, a portal to track every case and manage every invoice in one place, and a clinical support team to help. More than 650 doctors nationwide trust us, we retain over 95% of them year over year, and we're growing fast.

We're hiring a Senior Product Manager to own integrations across the Incisive Portal and its supporting services — every place where our platform connects to another piece of software, inside or outside the company. Lab integrations are the most important: the systems that move a case from a doctor's chair to the right lab and back. Beyond labs, you'll own the connections that keep the rest of the business running — Salesforce, QuickBooks, scanner and digital-equipment software, and the internal services that tie them together. This role is intentionally broad. We're looking for someone who can flex beyond their core area to take on whatever is most important for moving Incisive forward.

What will you be doing? Own the integrations roadmap across the Incisive Portal and supporting services — internal and external dependencies alike — from vision through delivery and iteration. Design lab integrations that scale. Build patterns that work across partners at very different levels of technical sophistication — from real-time APIs to file-based and manual-assisted workflows. Own connections to the broader software stack (Salesforce, QuickBooks, scanner/digital-equipment software). Run discovery with doctors, lab partners, and internal stakeholders. Collaborate closely with engineering to define, sequence, and ship work. Define and instrument success metrics. Coordinate cross-functionally with Operations, RevOps, Partnerships, Clinical Support.

Who are you? 5+ years of product management experience, including ownership of complex products end to end. Experience building integrations, API, or platform/marketplace products, ideally connecting external partners and internal systems with varying technical capabilities. Comfort orchestrating across a real software stack — moving data reliably between systems like CRMs, financial tools, third-party software. Comfort working close to data — able to explore a relational schema, reason about data quality, write or read SQL. A track record of shipping in fast-moving, resource-constrained environments.

What you'll love: $140,000-$170,000 base salary, plus performance bonus and meaningful equity. Fully remote in the US."

---

### 3. AVIXA — Product Manager
Company: AVIXA, professional association for the AV industry (digital platforms: AVIXA.org, AVIXA TV, AVIXA Xchange).
**Flagged gap:** none required-item-level; general digital-platform/community fit. Salary band ($85-95K) is on the low side for Jason's target — flag it, don't let it change the drafting.

Job posting (verbatim), URL: https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?cid=314574b3-596c-4ea4-9e5f-5a543b5653cc&ccId=19000101_000001&type=JS&lang=en_US

"Summary of Position: We're looking for a Product Manager to own a portfolio of customer-facing digital experiences that help users discover, explore, and engage with AVIXA's products, content, and community. This role sits at the intersection of content, community, and professional development. This role will support key digital platforms including AVIXA.org, AVIXA TV, and AVIXA Xchange, helping create seamless experiences that connect users with industry knowledge, education, events, community discussions, certification programs, and membership offerings. This role is focused on the beginning of a user's journey with us, starting with acquisition and awareness, and driving to engagement. You'll work closely with Engineering, UX, Content, Marketing, and business stakeholders to define product strategy, prioritize opportunities, and deliver features.

What You'll Do: Own the product roadmap and feature development for AVIXA's core audience-facing digital experiences. Define product vision and priorities aligned with customer needs and business objectives. Identify opportunities for new features through customer research, behavioral analytics, stakeholder collaboration. Write epics, define acceptance criteria, maintain a prioritized product backlog. Lead product discovery, backlog refinement, sprint planning, agile ceremonies. Define and monitor product KPIs using analytics platforms such as Amplitude, Mixpanel, Google Analytics. Use data, experimentation, A/B testing to optimize digital experiences. Collaborate with Product Managers responsible for education, membership, webinars, certification. Partner with content teams to optimize experiences and build on a headless CMS, preferably Storyblok.

What We're Looking For: Minimum of 4 years of Product Management or Product Ownership experience delivering audience-facing digital products or web experiences. Experience owning product features from discovery through delivery. Strong understanding of Agile product development methodologies. Experience using analytics platforms such as Amplitude, Mixpanel. Experience optimizing digital experiences using customer insights, behavioral analytics, experimentation. Experience writing user stories, defining acceptance criteria, managing product backlogs. Experience with headless CMS platforms such as Storyblok, Contentful, or Sanity. Experience managing website, portal, SaaS, or other customer-facing digital products.

Location: Remote (United States or EMEA). Starting base pay range $85,000-$95,000."

---

### 4. Doppel — Digital Program Manager, Customer Success
Company: Doppel, AI-native social engineering/phishing defense platform, Series C.
**Flagged gap:** function is CS-ops/lifecycle-marketing, not core product ownership — real anchors are Jason's Pendo analytics experience (ACC-117) and data-driven prioritization work; don't overclaim product-strategy ownership this role doesn't actually have.

Job posting (verbatim), URL: https://grnh.se/4owk0qgh9us

"Doppel is building the future of social engineering defense. Our AI-native platform uses agentic AI to protect executives, employees, customers, and brands from phishing, impersonation, fraud, and other AI-powered threats. Backed by Andreessen Horowitz and Bessemer Venture Partners, Doppel is a rapidly growing Series C startup.

We are looking for a Digital Program Manager, Customer Success to build and scale the digital programs, reporting infrastructure, and operational processes that help Doppel customers realize value across the customer lifecycle. You will design and optimize digital customer journeys, develop customer reporting and insights, accelerate AI adoption, and partner cross-functionally to make Customer Success more data-driven, consistent, and scalable. This is a highly cross-functional role that partners closely with Customer Success leadership, Revenue Operations, Product, Marketing, Enablement, Support, Professional Services, and Engineering.

What You Will Do: Design, launch, and continuously improve digital customer success programs across the customer lifecycle (onboarding, adoption, customer education, AI feature adoption, renewal readiness, advocacy). Own Customer Success digital reporting by developing scalable dashboards and reporting views for customer health, onboarding, adoption, product usage, engagement, renewals, expansion. Partner with Revenue Operations and Business Systems to improve data quality, reporting automation, accessibility of customer insights. Identify customer trends, risks, friction points through data analysis. Partner with Product and Customer Success to accelerate adoption of Doppel's AI capabilities. Map, document, and continuously optimize the end-to-end digital customer journey.

What We Are Looking For: 3+ years of experience in Customer Success Operations, Program Management, Digital Customer Experience, Lifecycle Marketing, Revenue Operations, or a related SaaS function. Experience designing, launching, and scaling digital customer success programs for an existing customer base. Strong understanding of the SaaS customer lifecycle. Experience building customer reporting, dashboards, and insights using data from CRM systems, product analytics tools, customer success platforms. Experience with customer engagement, product analytics, or lifecycle tools such as HubSpot, Pendo, Docebo, Gainsight, Planhat, Vitally. Proven ability to manage complex, cross-functional programs with measurable business outcomes. Experience in B2B SaaS, cybersecurity, AI-driven products helpful but not required.

The base salary range for this role is $140,000-$160,000 with commissions, equity participation."

---

### 5. McGraw Hill — Program Manager
Company: McGraw Hill, education technology publisher.
**Flagged gap:** general PMO/delivery fit via Jason's PI-planning/roadmap background (ACC-109). 25% travel — disclose plainly per the 15% travel-ceiling rule in `workExperience.md` §1.4, don't stay silent on it.

Job posting (verbatim), URL: https://careers.mheducation.com/jobs/6850?lang=en-us&iis=Job+Board&iisn=LinkedIn

"McGraw Hill, the leading provider of digital and print educational resources, is looking for a Program Manager that leads a cross-functional team to effectively and efficiently deliver high-quality products across a portfolio. Ensuring transparency of project status from planning through development and delivery, the Program Manager oversees timelines, budgets and resources. This is a remote position open to applicants authorized to work for any employer within the United States.

What you will be doing: Partner with the Curriculum Strategy Lead on roadmap planning, managing scope, prioritization, scheduling, resource estimation, budget, risk identification. Lead and coach a cross-functional team to successfully deliver projects, facilitating meetings, removing roadblocks, fostering a collaborative, high-performance culture. Manage agile project plans and monitor milestones through data-driven dashboards, reporting progress and issues to stakeholders and leadership. Ensure consistent, transparent communication across project teams, stakeholders, and leadership. Leverage and champion AI-powered tools and workflows, staying current on emerging capabilities. Champion change initiatives by coaching and supporting team members through transitions. Contribute to the evolution of PMO standards and best practices.

We're looking for someone with: Bachelor's degree required, along with 5+ years of proven experience managing complex projects from initiation through delivery. Project Management certification required or in progress, with PMP expected within 1 year of hire. Excellent communication, leadership, and interpersonal skills. Strong problem-solving and analytical skills. Proven risk management capabilities. Willingness and ability to travel up to 25% of the time. Preferred: experience managing Agile projects using Scrum, proficiency with Jira and Smartsheet.

The pay range for this position is between $62,000-$110,000 annually."

---

### 6. Franklin Fitch — Senior Data Program Manager (Data & AI)
Recruiting firm posting for "a leading global professional services organisation" (client undisclosed in the posting).
**Flagged gap:** function is programme delivery, not product ownership — bridge via data-integrity work (ACC-102, ACC-105) and analytics-driven prioritization (ACC-117), framed honestly as delivery-execution strength, not strategic product ownership.

Job posting (verbatim), URL: https://www.linkedin.com/jobs/view/4444423002/

"Senior Data Program Manager (Data & AI) | Remote (U.S. locations) | $110,000-$210,000 + bonus + benefits.

The Opportunity: A leading global professional services organisation is seeking a Senior Data Program Manager to lead the delivery of enterprise-scale data and AI initiatives. This is a senior individual contributor role responsible for managing complex, cross-functional programmes across data, analytics, and engineering teams.

Key Responsibilities: Own and maintain the enterprise data programme roadmap, aligning with business priorities and overall data strategy. Lead end-to-end programme delivery, including scope definition, scheduling, risk management, dependency coordination. Manage programme budgets, forecasts, financial reporting. Define and track key performance indicators, translating delivery outcomes into clear business value for stakeholders. Maintain visibility of programme progress through delivery tools such as Azure DevOps. Proactively identify, escalate, and resolve risks, blockers, cross-team dependencies. Translate business requirements into structured programme plans, delivery milestones, executive-level updates. Establish and oversee testing and quality assurance frameworks. Leverage AI-assisted tools (e.g. Copilot) to improve delivery efficiency.

Experience and Skills Required: 4+ years' experience managing complex, cross-functional programmes. Demonstrated experience working with data, analytics, AI, or enterprise technology teams. Proven ownership of programme roadmaps, budgets, delivery timelines. Strong understanding of Agile, hybrid, or waterfall delivery methodologies. Experience using programme management tools such as Azure DevOps, Jira. Excellent stakeholder management skills across technical and non-technical audiences. Ability to operate independently as a senior individual contributor."

---

## Tier 2 — weaker case, use judgment (2 companies)

### 7. Campus4Tech — Program Manager (Agile)
Weakest case in this batch — the JD's "Who Should Apply" list skews toward coordinator-level titles (Scrum Masters, Agile Project Coordinators, Business Systems Analysts), not senior PM. Only draft if a genuinely honest, non-inflated case can be made; skip rather than stretch.

Job posting (verbatim), URL: https://candidateportal.ceipal.com/api/share/y5nEZmVBp3oopMqXIZzallf1eP-oNNSQisif-psrHLY

"Role: Program Manager (Agile). Location: United States (Remote). Employment Type: Full-Time. Pay Rate: $90,000-$130,000 per year. Travel: Not Required.

Who Should Apply: Scrum Masters, Agile Project Coordinators, Program Coordinators, Business Systems Analysts, Implementation Coordinators, Customer Success Associates, Customer Service Representatives, Sales Coordinators, Marketing Coordinators etc. Professionals returning to the workforce. Individuals from diverse backgrounds.

Job Description: We are seeking a motivated and organized Program Manager (Agile) to join our growing team. In this role, you will support the planning, coordination and successful delivery of multiple Agile projects while collaborating with cross-functional teams to ensure strategic business objectives are achieved.

Key Responsibilities: Assist in planning, coordinating and managing multiple Agile projects and programs. Collaborate with Product Owners, Scrum Masters, Business Analysts, and stakeholders to define program objectives. Develop and maintain program road maps, project schedules and delivery timelines. Track program progress, milestones, risks and dependencies. Facilitate Agile ceremonies, including program planning, sprint reviews, retrospectives and stakeholder meetings. Monitor program budgets, resources and overall performance. Prepare program status reports, dashboards and executive presentations. Identify and mitigate program risks. Coordinate cross-functional teams. Support Agile, Scrum, Kanban and SAFe methodologies. Drive continuous process improvements."

---

### 8. iSpot — Technical Program Manager
Flipped from Skip to Tier 2 under the 2026-07-23 title-family policy change — was previously rejected on title alone. 5-7 years fits (Jason has 7); PRD/requirements-translation work is a real anchor.

Job posting (verbatim), URL: https://job-boards.greenhouse.io/ispottv/jobs/4717331005?gh_src=1e1873425us

"iSpot.tv is changing how brands, agencies, and networks measure and assess the impact of TV advertising. Our Operations team provides mission-critical support to our sales, customer success, and marketing teams. The Technical Program Manager (TPM) will own and drive the execution of core business system initiatives, applying program management rigor — such as comprehensive requirements gathering, roadmap planning, timeline tracking, and stakeholder communication — to bridge the gap between complex business needs and technical systems architecture.

Responsibilities: Program Leadership: Partner closely with cross-functional business stakeholders (Sales, Marketing, Finance, Product, Engineering) to scope strategic initiatives and author technical requirements, including Product Requirement Documents (PRDs) and detailed user stories. Execution & Delivery: Lead the end-to-end execution of complex, technical projects by establishing project milestones, managing dependencies, proactively mitigating risks, clearing blockers. Stakeholder Alignment: Facilitate regular syncs, communication channels, status updates across technical and non-technical teams. System Optimization: Continuous evaluation of core systems to identify opportunities to maximize application capabilities.

Qualifications: 5-7 years of experience managing technical programs, complex software projects, or enterprise systems implementations. Proven track record of translating ambiguous business requests into structured, execution-ready technical documentation, such as system process maps and PRDs. Proficient in JIRA. Strong ability to multitask, prioritize competing high-impact initiatives.

Target cash compensation range: $104,700-$125,200 USD Annually."

---

## STOP — needs Jason's explicit call before drafting (3 companies)

Do not draft these without asking Jason first. Report them back as open questions.

### 9. Allstate — Digital Product Manager, Cybersecurity, Controls, and Compliance
Strong domain fit — Jason's real security-backlog-triage accomplishment (ACC-103, 90% of ~300 vulnerabilities resolved) maps directly to this role's "Security, Controls & Risk Management" responsibilities. **But**: `jobagent.sqlite` shows 9 prior rows for Allstate, including 3x Applied and 3x Rejected. This needs Jason's judgment on whether re-applying makes sense given that history — not a fit question, a "have I already burned this bridge" question only he can answer.

### 10. Venture Institute (Decile Group) — Product Manager (Remote)
VC-tooling SaaS platform, decent AI-fluency-signal fit. **But**: `jobagent.sqlite` shows an existing row for "Decile Group" with status Applied — likely the same company, possibly the same role re-posted. Confirm with Jason before drafting a second application.

### 11. Risepoint — "Product Manager, Enterprise Data"
**Data quality flag, not just a duplicate flag**: the CSV's Position field says "Product Manager, Enterprise Data," but the actual posting URL is `.../Principal-Business-Analyst--Data_JR101286` — if the real title is "Principal Business Analyst," that's a blocked title (Principal) and arguably not a Product Manager role at all. Confirm the real title from the live posting before doing anything else with this one. URL: https://risepoint.wd503.myworkdayjobs.com/Risepoint/job/US---Remote/Principal-Business-Analyst--Data_JR101286?source=LinkedIn

---

## What "done" looks like for this handoff

For each of the 8 clear-to-draft companies: `data/submissions/{company-slug}/` containing `Original_JD.txt`, `stage0_fit_gate.json`, `Resume.md`/`.pdf`, `CoverLetter.md`/`.pdf`, `draft_manifest.json` (verification_passed/rubric_score populated) — no `Interview_Cheat_Sheet.md`, no DB writes. Report back in plain language per company: fit decision, rubric score, any gap and how it was bridged, final page count, where files landed. Flag the 3 STOP companies as open questions rather than drafting them.
