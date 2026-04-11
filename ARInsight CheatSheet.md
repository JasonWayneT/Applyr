Here’s a structured, ARInsights-specific “script” you can rehearse. It’s written so you can speak it naturally, not read it word-for-word. Adapt phrases to your own voice.

***

## 1. “Tell me about yourself” (60–90 seconds)

“I’m a platform-focused product manager with a little over six years in B2B SaaS, and most of my career has been spent owning revenue-bearing, legacy systems where stability and data quality are the core value proposition rather than shiny new features.”

“Most recently at Cision, I owned Legacy C3 and the underlying CPRE platform, which together powered a media database and media monitoring product that carried about 40M in ARR across roughly 3,500 customers and 25,000 users. My job was to keep that platform reliable while the company was trying to migrate customers to newer products, which meant a lot of work on data integrity, ingestion pipelines, and migration tooling under declining investment and repeated layoffs.”

“A few of the things I’m proudest of are leading Bellwether, which bypassed brittle legacy ETL and restored trust in our contact data, driving a structured stability and security program that resolved about 90% of a 300-item security backlog, and building voluntary migration tooling so we could move high-risk accounts safely instead of repeating an earlier forced-migration disaster.”

“Before Cision I worked in smaller environments as a product owner and account manager, building internal tools and automation that reduced manual ops work and saved on the order of tens of thousands of dollars annually, which is where I learned to think in terms of systems and throughput, not just features.”

“At this point, I’m looking for roles like this ARInsights PM role where the challenge is: you have a trusted but aging data platform, you’re layering AI and insight loops on top, and you need someone who can stabilize the engine, improve data trust, and help modernize without breaking what’s already paying the bills.”

***

## 2. “Why ARInsights?” / “Why this role?” (60–90 seconds)

“The strategic alignment at ARInsights is compelling because you sit in a niche that looks a lot like the world I’ve been operating in: high-value, relationship-driven data about analysts and influencers, where your customers’ job is to make better strategic decisions, not just blast communications.”

“You’re also at a pivotal stage: long-standing product, profitable and PE-backed, but now going through a reinvention with AI, new leadership coming in with a CTO and CEO, and new offerings like AR Connect that try to turn interactions into measurable impact. That combination of ‘mature but reinventing’ is where I tend to add the most value.”

“The builder PM role you’ve outlined maps directly to what I’ve done: I’ve owned a legacy media data platform, I’ve untangled data quality and ingestion problems so that any AI or analytics on top actually had something trustworthy to work with, and I’ve done it on small teams where you can’t hide behind process. So this is a chance for me to bring very specific experience from Cision’s world into a more focused, analyst-relations-centric product that’s trying to modernize without losing the trust it’s built over decades.”

***

## 3. Handling “We’re reinventing the product; how do you deal with ambiguity?” (2–3 minutes)

“I’ve basically lived in product reinvention under imperfect conditions for the last few years, so ambiguity is familiar territory.”

“At Cision, I stepped into Legacy C3 right after a failed forced migration to a newer platform. Revenue was still meaningful, the architecture was old, and the company wanted to move customers without repeating the churn they’d just created. There was no neat blueprint; priorities shifted with leadership changes and layoffs.”

“The way I handle that is in layers: first I clarify what absolutely cannot break—the core contracts the platform has with customers. For C3 that was: reliable coverage, reasonably fresh contact data, and no embarrassing security or stability failures. Then I define a thin slice of ‘engine work’ that unlocks future bets.”

“Bellwether is a good example. We knew stale contact data was a top churn driver, and our ETL path was dropping 30–40% of records between GPOD and C3. Rather than trying to redesign everything, I proposed bypassing the whole legacy chain and listening directly to the upstream source of truth. We started with a hackathon proof of concept, validated the approach, and only then built the full pipeline that did a one-time repair sync plus ongoing deltas. That reduced stale-data complaints tied to that path and gave us a much simpler, observable foundation to build on.”

“So in a reinvention scenario like ARchitect, I’d apply the same pattern: make the core value non-negotiable (analyst and interaction data has to be reliable), build minimum viable data trust and observability first, and then layer on the more speculative AI/insight capabilities once we’re not guessing about the underlying data.”

***

## 4. “How do you balance stability vs new features on a small team?” (2–3 minutes)

“In a small-team environment, I don’t think of stability and features as separate lanes; they’re all competing claims on the same finite capacity.”

“At Cision we were often running with roughly one to two product-engineering pods covering a 40M ARR legacy platform plus migration work. Early on I made the mistake of saying yes to too many things and burning the team out. The way I corrected that was by getting very explicit about capacity and prioritization.”

“We built a quarterly capacity model: how many engineer-days we actually had after PTO, converted that into a rough hour budget, then sized initiatives with T-shirt sizes and low/high ranges. We reserved explicit slices of that capacity for security and stability, for customer-reported issues, and for planned reinvention projects like Bellwether or migration tooling.”

“For example, a pen test once dropped about 300 security issues on us. Sales wanted everything fixed immediately. Instead, we severity-ranked the issues, committed to clearing high-risk items quickly, slotted medium-risk issues across multiple quarters, and preserved enough room for roadmap work that actually moved the platform forward.”

“The benefit of this approach for a team like ARInsights is that it turns the conversation from ‘stability or features?’ into ‘given this finite capacity, which mix protects revenue and advances the strategy fastest?’ I’d expect to implement something similar here: make capacity visible, define a few clear initiative streams, and then hold the line so the team isn’t constantly whiplashed by the latest fire.”

***

## 5. “Tell me about a time you improved data quality in a way that changed customer outcomes” (Bellwether story, 2–3 minutes)

“Bellwether is the cleanest example of that.”

“When I took over C3, the biggest product-driven churn driver was stale contact data. Customers would tell us, ‘You have the biggest database, but too many contacts are out of date.’ Voice of Customer reports, closed-lost analysis, and support tickets all pointed to the same issue.”

“We traced the data path and found that contacts were traveling through multiple legacy databases and ETL jobs before they ever reached C3, and we were losing roughly 30–40% of records along the way. The people who built parts of that pipeline were gone, and the documentation was incomplete.”

“Instead of trying to patch an opaque system, I proposed a different approach: subscribe directly to GPOD, which was the upstream source of truth, and update C3 from there. We built a small proof of concept during a hackathon that listened to GPOD messages, transformed them into C3’s format, and updated the customer databases. Once we proved it worked, we built the production version: a one-time full sync to repair the existing data, then a streaming process to keep contacts current.”

“That effectively removed the loss points from the legacy chain and eliminated the primary mechanism that caused stale contacts. From the customer standpoint, complaints about stale contacts tied to that pipeline dropped away; we regarded it internally as one of the biggest wins for the platform.”

“In an environment like ARInsights, where AI-powered insight loops depend on the correctness and freshness of analyst and interaction data, I’d look for the equivalent of that Bellwether move: find where data is getting lost or delayed, simplify the path, and make the pipeline observable so we can trust what’s feeding the product.”

***

## 6. “Tell me about a time you managed migrations without blowing up customers” (2–3 minutes)

“When I arrived at Cision, the company had already tried a forced migration from one platform to another, and it created churn and a lot of distrust. So any future migration off Legacy C3 had to be voluntary and retention-first.”

“We started by aligning on two goals: protect revenue by moving customers who genuinely needed capabilities C3 couldn’t offer, and never repeat the pattern of pushing customers before the target platform could handle their workflows.”

“I worked with an Upgrades team, Cision One engineering, QA, and CX to define and build migration tooling instead of one-off scripts. Phase 1 focused on the simplest case—database-only customers where functionality was almost identical. Phase 2 layered in customers using monitoring, which required more careful validation. Phase 3 targeted more complex data-group accounts once the target platform could model them.”

“In parallel we ran a critical save program: accounts flagged as high churn risk if they stayed on C3 were prioritized for migration at renewal, with tighter coordination between Product, CX, and Account Management. We also dealt with vendor data-handling issues along the way, refactoring where quality wasn’t acceptable.”

“The result wasn’t a flashy big-bang launch, but it was a controlled path off a legacy platform that avoided systemic failures and let us move roughly 700 accounts, focusing first on those most at risk. I would take a similar philosophy here: migrations and big re-platform moves should be voluntary, aligned with clear customer value, and supported by tooling and feature parity, rather than viewed purely as an internal cost-reduction exercise.”

***

## 7. “How do you work with engineering and other partners?” (90–120 seconds)

“I operate very close to engineering, but my role is to be the connector and decision-maker, not the architect.”

“On C3 and CPRE I worked with roughly 6–15 engineers across multiple teams over time, plus dedicated partners in DevOps and DBAs. I was effectively the owner of the roadmap, cross-team prioritization, and alignment mechanism. We did quarterly planning grounded in capacity, and I maintained regular check-ins with upstream platform teams like GPOD and UCP, as well as CX and account management.”

“When layoffs and leadership churn hit, that connective tissue mattered even more. I set up recurring cross-functional sessions to keep people aligned on what we were doing and why, and over time that reduced mid-quarter thrash and helped us hold a year-long roadmap even while the org was changing around us.”

“In a small company like ARInsights, I’d expect to play a similar role: keep a tight feedback loop with engineering, be explicit about trade-offs, and make sure the roadmap reflects both customer reality and the constraints of the underlying platform.”

***

## 8. Reverse-interview questions you can ask

For the CTO:

- “From your perspective, what’s the architectural North Star for ARchitect over the next few years, especially around data model and ingestion? Where is it solid today, and where does it still feel fragile?”
- “When you say AI-powered market intelligence and insight loops, what has to be true in the data layer and in customer workflows for that to be real, not just a tagline?”

For Product / CEO:

- “If we’re talking 12 months from now and you’re thrilled you hired this PM, what specific problems will we have solved in ARchitect?”
- - “How do you currently decide between investing in stability and debt versus new capabilities like AR Connect or deeper analytics?”

***

If you’d like, I can next turn this into a one-page “run of show” for the actual interview (what to say in the first 5 minutes, which stories to prioritize for each interviewer, and a 30-second closing).