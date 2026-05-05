# **Interview Run of Show: Jason Taylor**
## **Role: Platform Product Manager**

This cheat sheet maps your experience at Cision and Sterkly to the specific demands of a Platform PM role. It prioritizes technical reliability and revenue protection over marketing fluff.

---

### **1. "Tell me about yourself" (60-90 Seconds)**

**The Pitch:**
I am a Product Manager who specializes in the unglamorous but critical side of B2B SaaS: platform stability, data integrity, and legacy migrations. Most of my career has been spent operating inside technically complex ecosystems where the goal isn't just to build new features, but to ensure the underlying infrastructure can actually support the business.

At Cision, I owned the legacy C3 platform and its underlying infrastructure, CPRE. This was a $40M ARR business line that was officially in a sunset phase but still carried 3,500 enterprise accounts. My job was to keep that revenue safe while the company transitioned to newer architecture. I led the Bellwether initiative, which bypassed broken legacy ETL pipelines to fix a 40% data loss issue that was our primary churn driver. 

I am at my best when I am working closely with engineering to solve architectural bottlenecks that block the roadmap. I do not need perfect conditions to ship. I have managed products through four rounds of layoffs and three CEO changes by staying focused on capacity modeling and disciplined prioritization.

---

### **2. Why This Company / Role?**

*Note: Since specific company research was not provided, use this framework to bridge your "Ground Truth" to their current state.*

**The Logic:**
"I am interested in this role because you are currently at a pivot point between [Scaling / Managing Technical Debt / Migrating to a New Core]. My experience at Cision was a four year masterclass in exactly that. You have a platform that [Generates Revenue / Serves Enterprise Clients], and you need a PM who understands that you cannot just 'move fast and break things' when $40M is on the line. I am looking to apply my framework for platform stabilization and migration tooling to help [Company Name] modernize without losing the trust of your existing customer base."

**The Bridge:**
*   If they are scaling: "I understand how to move from fragmented data sources to a unified source of truth, similar to how I integrated C3 with the Unified Content Platform."
*   If they are struggling with debt: "I have a proven track record of clearing 90% of a security backlog while still delivering architectural wins like Bellwether."

---

### **3. Key Experience Bridge**

**The "Bellwether" Story (Data Integrity & Trust):**
*   **The Challenge:** Cision had the largest database but the stalest data. We were losing 30 to 40% of our contact updates in a black box of legacy ETL pipelines.
*   **The Action:** I proposed a bypass. Instead of fixing twenty years of bad code, we built a direct integration to the upstream source of truth (GPOD). 
*   **The Result:** We eliminated the data drop off entirely. It proved that platform PMs should look for architectural shortcuts rather than just patching symptoms.

**The "CPRE" Story (Infrastructure & Cost):**
*   **The Challenge:** High infrastructure costs and frequent outages due to DT Search storage exhaustion.
*   **The Action:** I partnered with Legal and Engineering to identify and purge dead accounts that were bloating our indexes. I also implemented proactive monitoring and alerting.
*   **The Result:** We saved $1M to $2M in infrastructure costs and significantly reduced platform downtime.

---

### **4. Handling Ambiguity & Stability**

**On Balancing Legacy vs. Innovation:**
Innovation on a platform team often looks like a migration. At Cision, I did not have the luxury of a greenfield build. I had to build migration tooling that allowed for a voluntary, phased transition. We categorized customers by complexity (Database only vs. Monitoring) to ensure no one lost a critical workflow. I prioritize by asking: "Does this protect the current revenue, or does it enable the future platform?" If it does neither, it is a distraction.

**On Operating Under Constraint:**
I have worked with teams that shrank from 15 engineers down to six. In those environments, you cannot rely on gut feel. I implemented a capacity model based on actual workdays, PTO, and uncertainty buffers. This allowed me to give the business a realistic roadmap even when morale was low and resources were disappearing. I am comfortable being the person who says "no" so that the team can actually finish the "yes."

---

### **5. Custom Reverse-Interview Questions**

**For the CTO / Head of Engineering:**
1.  What is the current ratio of "keep the lights on" work versus strategic architectural modernization? 
2.  When we hit a bottleneck in the ingestion pipeline or database performance, how is the trade off between a quick patch and a long term fix decided?
3.  How do you currently handle subject matter expertise? If a core platform engineer leaves, is that knowledge documented or is it a single point of failure?

**For the CEO / CPO:**
1.  The platform is the foundation for the product, but it is often invisible to the customer until it breaks. How do you communicate the value of infrastructure investment to the board or investors?
2.  What is the three year vision for the legacy components of the stack? Are we in a "harvest and sunset" phase or a "modernize and grow" phase?
3.  What is the biggest churn driver that cannot be fixed by a UI change? (This tests their understanding of platform health).