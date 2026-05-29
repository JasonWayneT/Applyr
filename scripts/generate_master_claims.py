import json
import os

claims = {
    "ACC-101-TECH": {
        "employer": "cision",
        "project_id": "ACC-101",
        "lens": "technical",
        "tags": ["Platform Stabilization", "Infrastructure", "Monitoring", "Alerting"],
        "metrics": [],
        "text": "Mitigated recurring legacy server crashes by implementing proactive storage capacity monitoring and alerting thresholds."
    },
    "ACC-101-OPS": {
        "employer": "cision",
        "project_id": "ACC-101",
        "lens": "operations",
        "tags": ["Risk Mitigation", "Compliance", "SLA"],
        "metrics": [],
        "text": "Stabilized core platform reliability by partnering with Legal to execute compliant data cleanups of stale accounts, drastically reducing service outages."
    },
    "ACC-101-PM": {
        "employer": "cision",
        "project_id": "ACC-101",
        "lens": "product",
        "tags": ["Reliability", "Legacy Systems", "Product Stability"],
        "metrics": [],
        "text": "Reduced overall service outages and stabilized a legacy platform by driving infrastructure capacity monitoring and proactive account cleanup initiatives."
    },

    "ACC-102-TECH": {
        "employer": "cision",
        "project_id": "ACC-102",
        "lens": "technical",
        "tags": ["Data Integrity", "ETL", "Platform Architecture", "Technical Problem Solving"],
        "metrics": ["40%"],
        "text": "Engineered a structural bypass of failing legacy ETL pipelines, integrating the core B2B SaaS platform directly with the upstream source-of-truth database to eliminate a 40% data drop-off rate."
    },
    "ACC-102-BUS": {
        "employer": "cision",
        "project_id": "ACC-102",
        "lens": "business",
        "tags": ["Customer Retention", "Revenue Protection", "Product Quality"],
        "metrics": ["40%", "0"],
        "text": "Protected retention across an enterprise platform by resolving a catastrophic 40% data drop-off issue, completely eliminating stale-contact complaints that were driving customer churn."
    },
    "ACC-102-LEAD": {
        "employer": "cision",
        "project_id": "ACC-102",
        "lens": "leadership",
        "tags": ["Cross-functional Alignment", "Initiative", "Problem Identification"],
        "metrics": ["40%"],
        "text": "Identified and drove a critical cross-functional data remediation initiative, aligning engineering and database administration to permanently resolve a 40% data ingestion failure."
    },

    "ACC-103-SEC": {
        "employer": "cision",
        "project_id": "ACC-103",
        "lens": "security",
        "tags": ["Security", "Compliance", "Vulnerability Management"],
        "metrics": ["300", "90%"],
        "text": "Prioritized and drove the remediation of ~300 penetration test vulnerabilities, successfully resolving 90% of security risks through a risk-weighted severity scoring filter."
    },
    "ACC-103-ROADMAP": {
        "employer": "cision",
        "project_id": "ACC-103",
        "lens": "roadmap",
        "tags": ["Roadmap Prioritization", "Capacity Planning", "Security"],
        "metrics": ["90%", "300"],
        "text": "Resolved 90% of a massive ~300-item security vulnerability backlog over a one-year phased roll-out without stalling core roadmap delivery."
    },
    "ACC-103-PM": {
        "employer": "cision",
        "project_id": "ACC-103",
        "lens": "product",
        "tags": ["Risk Mitigation", "Backlog Grooming", "Technical Debt"],
        "metrics": ["300", "90%"],
        "text": "Implemented a risk-weighted severity scoring framework to triage ~300 penetration test items, successfully resolving 90% of security risks while balancing new feature development."
    },

    "ACC-104-OPS": {
        "employer": "cision",
        "project_id": "ACC-104",
        "lens": "operations",
        "tags": ["Go-to-Market", "Phased Rollout", "Operational Delivery"],
        "metrics": ["700"],
        "text": "Built and deployed phased voluntary migration tooling, successfully transitioning ~700 high-risk legacy accounts at their time of renewal without generating customer friction."
    },
    "ACC-104-CS": {
        "employer": "cision",
        "project_id": "ACC-104",
        "lens": "customer_success",
        "tags": ["Customer Experience", "Stakeholder Management", "CS Alignment", "Migrations"],
        "metrics": ["700"],
        "text": "Partnered closely with Customer Experience and Upgrade teams to execute a frictionless migration strategy, safely transitioning ~700 vulnerable accounts to a new corporate platform."
    },
    "ACC-104-LIFECYCLE": {
        "employer": "cision",
        "project_id": "ACC-104",
        "lens": "lifecycle",
        "tags": ["Product Lifecycle", "Sunsetting", "Risk Mitigation"],
        "metrics": ["700"],
        "text": "Managed the end-of-life migration strategy for a legacy platform, delivering custom tooling that successfully moved ~700 accounts off the deprecating infrastructure."
    },

    "ACC-105-PROCESS": {
        "employer": "cision",
        "project_id": "ACC-105",
        "lens": "process",
        "tags": ["Agile Planning", "Capacity Modeling", "Process Improvement"],
        "metrics": [],
        "text": "Replaced reactive sprint planning with a rigorous, PTO-adjusted capacity model using T-shirt sizing and uncertainty bands to accurately manage resource allocations."
    },
    "ACC-105-EXECUTION": {
        "employer": "cision",
        "project_id": "ACC-105",
        "lens": "execution",
        "tags": ["Prioritization", "Delivery", "Engineering Alignment"],
        "metrics": [],
        "text": "Enforced strict prioritization and capacity discipline across engineering teams to balance platform stability, compliance mandates, and core roadmap delivery."
    },
    "ACC-105-AGILE": {
        "employer": "cision",
        "project_id": "ACC-105",
        "lens": "agile",
        "tags": ["Velocity", "Agile Ceremonies", "Resource Allocation"],
        "metrics": [],
        "text": "Optimized engineering velocity under resource constraints by deploying a workday-hour capacity model, ensuring predictable delivery of roadmap items."
    },

    "ACC-106-GTM": {
        "employer": "cision",
        "project_id": "ACC-106",
        "lens": "gtm",
        "tags": ["Competitive Analysis", "Go-to-Market", "Feature Launch"],
        "metrics": [],
        "text": "Closed a critical competitive gap by implementing mobile Unique Visitors Per Month (UVPM) metrics for the core media outlet database."
    },
    "ACC-106-RETENTION": {
        "employer": "cision",
        "project_id": "ACC-106",
        "lens": "retention",
        "tags": ["Churn Reduction", "Customer Retention", "Analytics"],
        "metrics": [],
        "text": "Reduced churn risk among high-value customers by delivering highly requested mobile audience metrics, mitigating the threat of customers migrating to evaluating alternatives."
    },
    "ACC-106-DATA": {
        "employer": "cision",
        "project_id": "ACC-106",
        "lens": "data",
        "tags": ["Data Integration", "Analytics", "Audience Metrics"],
        "metrics": [],
        "text": "Expanded platform analytics capabilities by integrating mobile Unique Visitors Per Month (UVPM) data feeds into the legacy customer-facing application."
    },

    "ACC-107-COMPLIANCE": {
        "employer": "cision",
        "project_id": "ACC-107",
        "lens": "compliance",
        "tags": ["Compliance", "Privacy", "GDPR/CCPA"],
        "metrics": [],
        "text": "Built robust privacy and compliance workflows to handle contact data removal requests and enforce strict regional data licensing constraints for Australian and UK markets."
    },
    "ACC-107-LEGAL": {
        "employer": "cision",
        "project_id": "ACC-107",
        "lens": "legal",
        "tags": ["Legal Alignment", "Third-Party Integration", "Vendor Terms"],
        "metrics": [],
        "text": "Partnered with Legal to enforce compliance with third-party platform terms of service across major data sources including Twitter, Google, and Yahoo."
    },
    "ACC-107-PLATFORM": {
        "employer": "cision",
        "project_id": "ACC-107",
        "lens": "platform",
        "tags": ["Platform Architecture", "Automated Workflows", "Governance"],
        "metrics": [],
        "text": "Architected platform-level compliance safeguards to automatically process data removal requests and handle complex regional content licensing rules."
    },

    "ACC-108-SUPPORT": {
        "employer": "cision",
        "project_id": "ACC-108",
        "lens": "support",
        "tags": ["Customer Support", "Jira", "Issue Triage"],
        "metrics": [],
        "text": "Designed a structured Jira ticket triage system that dynamically scored inbound customer issues based on revenue impact, frequency, and severity."
    },
    "ACC-108-RETENTION": {
        "employer": "cision",
        "project_id": "ACC-108",
        "lens": "retention",
        "tags": ["Retention", "Escalation Management", "Enterprise Clients"],
        "metrics": [],
        "text": "Created a dedicated escalation workflow for high-risk enterprise accounts that automatically surfaced churn-risk tickets to the front of the engineering queue."
    },
    "ACC-108-OPS": {
        "employer": "cision",
        "project_id": "ACC-108",
        "lens": "operations",
        "tags": ["Operations", "Workflow Optimization", "Engineering Support"],
        "metrics": [],
        "text": "Streamlined engineering support operations by implementing a priority-scoring matrix, significantly improving response times for critical platform issues."
    },

    "ACC-109-EXEC": {
        "employer": "cision",
        "project_id": "ACC-109",
        "lens": "executive",
        "tags": ["Executive Presentation", "Communication", "Organization-wide Alignment"],
        "metrics": ["200"],
        "text": "Presented the consolidated quarterly roadmap to a 200+ person organization, including the executive leadership team, ensuring total alignment prior to execution."
    },
    "ACC-109-SYNTHESIS": {
        "employer": "cision",
        "project_id": "ACC-109",
        "lens": "synthesis",
        "tags": ["Requirements Gathering", "Backlog Prioritization", "Synthesis"],
        "metrics": [],
        "text": "Synthesized competing requirements from Legal, DevOps, Sales, and Customer Experience into a single, highly-prioritized roadmap during quarterly PI planning."
    },
    "ACC-109-PROCESS": {
        "employer": "cision",
        "project_id": "ACC-109",
        "lens": "process",
        "tags": ["Agile Planning", "PI Planning", "Process Improvement"],
        "metrics": [],
        "text": "Led rigorous quarterly PI planning cycles, establishing a structured framework to align cross-functional engineering teams and go-to-market stakeholders."
    },

    "ACC-110-RESILIENCE": {
        "employer": "cision",
        "project_id": "ACC-110",
        "lens": "resilience",
        "tags": ["Technical Resilience", "Knowledge Transfer", "Engineering Operations"],
        "metrics": [],
        "text": "Established structured cross-training initiatives across engineering teams to eliminate single points of failure on critical legacy platform components."
    },
    "ACC-110-LEADERSHIP": {
        "employer": "cision",
        "project_id": "ACC-110",
        "lens": "leadership",
        "tags": ["Leadership", "Continuity", "Change Management"],
        "metrics": [],
        "text": "Maintained operational continuity and platform stability through increasing organizational and resource constraints by driving proactive cross-functional knowledge sharing."
    },
    "ACC-110-OPS": {
        "employer": "cision",
        "project_id": "ACC-110",
        "lens": "operations",
        "tags": ["Resource Management", "Operations", "Risk Mitigation"],
        "metrics": [],
        "text": "De-risked critical infrastructure by implementing engineering cross-training programs, ensuring uninterrupted support during severe organizational resource constraints."
    },

    "ACC-201-PROCESS": {
        "employer": "sterkly",
        "project_id": "ACC-201",
        "lens": "process",
        "tags": ["Process Optimization", "Requirements Gathering", "Operations"],
        "metrics": [],
        "text": "Analyzed and optimized internal team workflows by standardizing requirements gathering and resolving critical resource conflicts."
    },
    "ACC-201-ALIGNMENT": {
        "employer": "sterkly",
        "project_id": "ACC-201",
        "lens": "alignment",
        "tags": ["Alignment", "Delivery", "Cross-functional"],
        "metrics": [],
        "text": "Facilitated regular cross-functional alignment sessions to maintain consistent delivery cadences in a fast-paced professional services environment."
    },

    "ACC-202-REQUIREMENTS": {
        "employer": "sterkly",
        "project_id": "ACC-202",
        "lens": "requirements",
        "tags": ["Product Specs", "Business Translation", "Agile"],
        "metrics": [],
        "text": "Translated complex business constraints and operational requirements into granular, engineering-ready product specs for rapid execution."
    },
    "ACC-202-DELIVERY": {
        "employer": "sterkly",
        "project_id": "ACC-202",
        "lens": "delivery",
        "tags": ["Engineering Alignment", "Delivery", "Collaboration"],
        "metrics": ["5"],
        "text": "Partnered closely with a dedicated team of 5-8 developers to ensure accurate, on-time delivery of technical workflow solutions."
    },

    "ACC-203-TECH": {
        "employer": "sterkly",
        "project_id": "ACC-203",
        "lens": "technical",
        "tags": ["Technical Solutions", "Tooling", "macOS"],
        "metrics": [],
        "text": "Resolved a critical distribution bottleneck for a macOS security product by architecting an in-house browser extension certificate procurement workflow."
    },
    "ACC-203-BUS": {
        "employer": "sterkly",
        "project_id": "ACC-203",
        "lens": "business",
        "tags": ["Revenue Protection", "Vendor Management", "ROI"],
        "metrics": ["$1M", "$3M"],
        "text": "Sustained an estimated $1M-$3M in at-risk product revenue by eliminating dependency on unreliable third-party vendors for software certificates."
    },
    "ACC-203-OPS": {
        "employer": "sterkly",
        "project_id": "ACC-203",
        "lens": "operations",
        "tags": ["Operations", "Cost Reduction", "Process Automation"],
        "metrics": ["$100"],
        "text": "Streamlined operational delivery by internalizing certificate procurement, reducing lead times and saving approximately $100 per certificate."
    },

    "ACC-204-QA": {
        "employer": "sterkly",
        "project_id": "ACC-204",
        "lens": "qa",
        "tags": ["QA", "Quality Assurance", "Backlog Management"],
        "metrics": [],
        "text": "Owned backlog management and led rigorous QA processes for a macOS security product to ensure high product quality standards."
    },
    "ACC-204-GLOBAL": {
        "employer": "sterkly",
        "project_id": "ACC-204",
        "lens": "global",
        "tags": ["Distributed Teams", "Global Coordination", "Release Management"],
        "metrics": [],
        "text": "Coordinated with a globally distributed engineering team across three countries to maintain a consistent release cadence."
    },

    "ACC-301-AUTO": {
        "employer": "zero_to_sixty",
        "project_id": "ACC-301",
        "lens": "automation",
        "tags": ["Automation", "Scaling", "Scripting"],
        "metrics": ["10", "100+"],
        "text": "Replaced a manual setup process with a custom automated deployment script, scaling fulfillment throughput from 10 manual setups per day to 100+ units processed unattended."
    },
    "ACC-301-FINANCE": {
        "employer": "zero_to_sixty",
        "project_id": "ACC-301",
        "lens": "finance",
        "tags": ["Vendor Management", "Cost Savings", "ROI"],
        "metrics": ["$288,000", "$8,500", "$34,000"],
        "text": "Managed a fulfillment program governing $288,000 in vendor contracts, generating $8,500 per quarter ($34,000 annually) in pure operational savings through automation."
    },

    "ACC-302-SALESFORCE": {
        "employer": "zero_to_sixty",
        "project_id": "ACC-302",
        "lens": "salesforce",
        "tags": ["Salesforce", "CRM", "Onboarding"],
        "metrics": [],
        "text": "Co-created and optimized an internal onboarding automation tool that streamlined new customer data mapping directly into Salesforce."
    },
    "ACC-302-OPS": {
        "employer": "zero_to_sixty",
        "project_id": "ACC-302",
        "lens": "operations",
        "tags": ["Workflow Optimization", "Operations", "Cost Reduction"],
        "metrics": ["$22,100"],
        "text": "Reduced manual overhead across the account management team by automating data entry workflows, saving $22,100 annually in operational costs."
    },

    "ACC-303-GTM": {
        "employer": "zero_to_sixty",
        "project_id": "ACC-303",
        "lens": "gtm",
        "tags": ["Go-to-Market", "Lead Generation", "Funnel Optimization"],
        "metrics": [],
        "text": "Built the company's first automated prospect onboarding funnel, integrating a website builder directly with Salesforce to capture leads."
    },
    "ACC-303-CONVERSION": {
        "employer": "zero_to_sixty",
        "project_id": "ACC-303",
        "lens": "conversion",
        "tags": ["Conversion Rate", "Sales Automation", "CRM Integration"],
        "metrics": ["40%"],
        "text": "Eliminated manual account management tasks by automating the sales pipeline, increasing estimated prospect-to-customer conversion rates by approximately 40%."
    }
}

with open("data/master_claims.json", "w", encoding="utf-8") as f:
    json.dump(claims, f, indent=2, ensure_ascii=False)
print("master_claims.json generated successfully!")
