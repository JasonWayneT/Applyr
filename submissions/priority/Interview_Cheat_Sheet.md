# Interview Cheat Sheet: Priority (v1.0)
## Role: Product Manager (ERP/Cloud Solutions / Payment Orchestration)
## Context: Enterprise Resource Planning / FinTech Infrastructure

### 📋 1. The Strategy: "The Financial Source of Truth"
- **The "Pain":** Enterprise payments are fragmented, slow, and risky. Managing multiple rails (RTP, FedNow, push-to-card) within an ERP requires a unified, intelligent orchestration layer that developers can easily integrate.
- **The Solution:** You are the PM who understands how to build reliable "Orchestration and Routing" logic. You've done this at Cision by simplifying the **CPRE** infrastructure and routing data via the **Bellwether** bypass.

### 🔗 2. Tactical "Jason Bridges"
- **Bridge 1: API-Driven Product Experience.**
  - *Context:* Managing CPRE and technical integrations at Cision.
  - *Value:* Priority is moving toward modern API orchestration. You understand technical concepts like idempotency, latency, and routing tradeoffs. You know how to make a technical service "Productized" for enterprise users.
- **Bridge 2: Risk-Weighted Prioritization.**
  - *Context:* Resolving 90% of a 300+ item security and pen-test backlog.
  - *Value:* FinTech and ERP systems are high-value targets. Your experience remediating technical debt while protecting a $40M ARR system proves you prioritize the "Safety and Trust" of the platform.
- **Bridge 3: Pragmatic Decision Making.**
  - *Context:* Using T-shirt sizing and capacity modeling for 15 engineers.
  - *Value:* Priority values "navigating ambiguity" and "making well-reasoned decisions." You use data-driven evidence (like the 40% loss data at Cision) to justify architectural changes.

### 🎯 3. Anticipated Technical Questions
- **"How do you define requirements for an API that needs to support multiple payment rails?"**
  - *Focus:* Modularity and Generalization. Explain how you'd look for common patterns (like unique identifiers, which used at Cision) to ensure the API can handle diverse inputs (RTP, FedNow, etc.) without breaking.
- **"Tell me about a time you had to investigate and resolve a top customer pain point."**
  - *Focus:* Bellwether. Detail the investigation into "Stale Data" (Customer Pain Point #1), the data extraction showing the ETL failure, and the successful resolution through a direct-source bypass.
- **"What does 'Success' look like for a Payment Orchestration product?"**
  - *Focus:* Settlement Speed, Cost Efficiency, and Reliability. Connect this to your experience looking backwards from "financial outcomes" (like churn reduction at Cision).

### 🕵️ 4. Reverse-Interview Questions (Strategic)
1. "As Priority expands its orchestration capabilities to include rails like FedNow and RTP, how are we helping our customers manage the inherent 'Risk vs. Speed' tradeoffs for their own treasury operations?"
2. "How do we define success for the US-based product team—is it about 'API Adoption,' 'Transaction Volume,' or 'Feature Parity' with legacy providers?"
3. "Priority has a global background. How is the US product team influencing the global roadmap to accommodate US-specific payment regulations and customer expectations?"

### ⚠️ 5. Red Flags to Avoid
- *Do NOT* claim you are a CPA or accounting expert; emphasize your **Platform Integrity, API Management, and Orchestration** expertise.
- *Do NOT* use "vibe" words like 'passionate' or 'innovative'. Stick to **Reliability, Security, and Tradeoffs**.
- *Do NOT* mention the "Context Firewall" (hallucination). Stick to **Bellwether** and **CPRE**.
