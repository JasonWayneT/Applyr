# Interview Run of Show: Jason Taylor x Carefull

## 1. "Tell me about yourself" (60-90 seconds)

I am a Platform Product Manager who specializes in high-stakes, data-heavy B2B environments. Most of my career has been spent managing the "plumbing" of complex systems where data integrity and platform uptime are the actual product.

For the last four years at Cision, I owned a legacy platform called C3 that carried 40 million dollars in ARR. When I stepped in, the platform was struggling with stale data and aging infrastructure. I did not have the luxury of a greenfield rebuild, so I focused on surgical modernization. I led an initiative called Bellwether that bypassed broken legacy pipelines to pull data directly from the source of truth, which eliminated our biggest churn driver.

I thrive in the middle of engineering, DevOps, and legal teams. I am not a 0-to-1 growth hacker. I am the person you hire to stabilize a platform, secure the data, and ensure that when the business scales, the infrastructure does not collapse under the weight of its own technical debt.

## 2. "Why Carefull?"

Carefull is fundamentally a trust company. You are monitoring the financial health of seniors, which means your data ingestion must be flawless and your platform must be beyond reproach from a security standpoint. If a transaction is missed or a connection to a financial institution drops, the user loses confidence immediately.

My experience at Cision was a four-year masterclass in maintaining that kind of trust under constraint. I managed a platform with 25,000 active users and 200 SQL databases. I have seen how fragmented data and legacy ETL processes can degrade a product, and I know how to fix those issues without disrupting the customer experience. I want to apply that discipline to a mission where the stakes are higher than just media monitoring. At Carefull, platform reliability directly impacts the financial safety of a vulnerable population.

## 3. Key Experience Bridge

**The Data Integrity Challenge (Bellwether)**
*   **Carefull Context:** You likely deal with multiple upstream data aggregators or direct bank integrations. If that data is delayed or dropped, your fraud detection fails.
*   **Jason’s Bridge:** At Cision, we were losing 30 to 40 percent of our contact data through layered legacy pipelines. I led the Bellwether project to bypass those layers and integrate directly with the source of truth. This restored data trust for 3,500 accounts. I can bring that same "source-of-truth" obsession to your ingestion engine.

**Infrastructure and Security (CPRE)**
*   **Carefull Context:** Handling sensitive financial data requires a rigorous security posture and a stable infrastructure.
*   **Jason’s Bridge:** I managed the CPRE infrastructure layer, where I cleared 90 percent of a 300-item security backlog while maintaining a roadmap. I also implemented storage monitoring for our indexing engines to prevent outages. I understand how to balance the need for new features with the non-negotiable requirements of security and stability.

**Migration and Transition**
*   **Carefull Context:** As Carefull evolves, you will inevitably need to move users from older data models or features to newer, more robust versions.
*   **Jason’s Bridge:** I managed voluntary, phased migrations for high-value accounts. I learned that forced migrations kill retention. I focus on feature parity and operational safety to ensure that transitions protect revenue rather than risking it.

## 4. Handling Ambiguity and Stability

In a lean environment like Carefull, you cannot do everything. My approach to ambiguity is rooted in disciplined capacity modeling. At Cision, I moved the team away from reactive "firefighting" by implementing a structured planning system.

I use a three-stream filter for prioritization:
1.  **Stability and Security:** Non-negotiable work to keep the platform alive and compliant.
2.  **Retention-Critical Improvements:** Fixing the specific pain points that cause churn (like the Bellwether project).
3.  **Strategic Initiatives:** New work handed down from leadership.

If a request does not fit into these streams, I say no. I factor in PTO, technical uncertainty, and "unplanned work" buffers to ensure my estimates are realistic. This prevents engineer burnout and ensures that when we commit to a release, we actually ship it. I don't need perfect data to make a decision, but I will build the systems to ensure we have better data for the next one.

## 5. Custom Reverse-Interview Questions

**For the CTO:**
*   Carefull relies on external financial data. When an upstream provider changes their API or has a data quality issue, how much of that burden currently falls on the PM versus the engineering team to triage?
*   You are operating in a high-compliance space. How do you currently balance the engineering velocity needed for a startup with the "slow down and verify" requirements of financial security?
*   What is the biggest "single point of failure" in the current ingestion pipeline that keeps you up at night?

**For the CEO:**
*   The business model relies on being a "quiet protector" for families. As you scale, how do you measure the success of the platform beyond just user growth? Is it a reduction in fraud events or a specific retention metric?
*   C3 was a legacy platform that we had to keep viable while the company moved elsewhere. Is Carefull currently in a "build and expand" phase, or are you reaching a point where you need to harden the existing core to support the next 100,000 users?
*   What is the one piece of the platform that, if it went down for 24 hours, would be existentially threatening to the brand?