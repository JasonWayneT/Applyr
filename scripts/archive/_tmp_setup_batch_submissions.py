# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""Create submission folders, Original_JD.txt, and stage0_fit_gate.json for batch."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "submissions"

CSV_PATHS = [
    Path(r"C:\Users\Jason\Downloads\applyr_jobs (1).csv"),
    Path(r"C:\Users\Jason\Downloads\applyr_jobs (2).csv"),
]

# company exact name from CSV -> slug + stage0 payload
TARGETS: dict[str, dict] = {
    "Principal Financial Group": {
        "slug": "principal",
        "tier": 1,
        "decision": "PASS",
        "required": [
            "4+ years business, technology, or product management experience",
            "2+ years collaborative product environment with product or engineering teams",
            "Strategic thinking and confident decisions in a product-driven environment",
            "Integrate diverse perspectives; use customer/user/partner insights",
        ],
        "preferred": [
            "Platform/centralized enterprise experience unifying diverse stakeholders",
            "Comfort navigating evolving ownership and incomplete information",
        ],
        "flagged_gaps": [
            "Financial services domain (transferable: platform data trust + decision support under incomplete data)",
        ],
        "stage_signal": "enterprise mature",
        "thin_jd": False,
        "reason": "Portfolio & Application Intelligence decision product — strong platform/data fit",
    },
    "Relativity": {
        "slug": "relativity",
        "tier": 1,
        "decision": "PASS",
        "required": [
            "3+ years product management building custom software",
            "Bachelor's or comparable experience",
            "Own roadmap for document conversion and enrichment",
            "Cross-functional work with engineering, enablement, sales, customers",
        ],
        "preferred": [
            "Developer-facing platform products",
            "Data fluency for product health",
            "Agile SDLC",
        ],
        "flagged_gaps": [
            "e-discovery / document enrichment domain (transferable: data pipeline integrity + platform enrichment work)",
        ],
        "stage_signal": "enterprise mature",
        "thin_jd": False,
        "reason": "Software platform PM; enrichment domain transferable",
    },
    "Nelnet": {
        "slug": "nelnet",
        "tier": 1,
        "decision": "PASS",
        "required": [
            "5+ years PM leading SaaS, cloud-based, or enterprise software",
            "Product vision, strategy, roadmaps, feature prioritization",
            "Customer discovery into strategy/roadmap",
            "Concept through MVP, launch, continuous improvement",
            "Partner with engineering and UX via Agile",
            "Present strategy to senior leadership",
        ],
        "preferred": [
            "Advanced degree or PM certification",
            "AI/emerging tech to improve experiences",
        ],
        "flagged_gaps": [
            "Education / faith-org vertical (transferable: B2B SaaS platform lifecycle)",
        ],
        "stage_signal": "enterprise mature",
        "thin_jd": False,
        "reason": "Straight SaaS/enterprise Senior PM",
    },
    "Applause": {
        "slug": "applause",
        "tier": 1,
        "decision": "PASS",
        "required": [
            "5+ years Product Management",
            "End-to-end ownership ideation through iteration",
            "Customer research qualitative and quantitative",
            "Data-driven decisions with product analytics (e.g. Pendo)",
            "Cross-functional stakeholder communication",
        ],
        "preferred": [
            "Jobs to Be Done alignment",
        ],
        "flagged_gaps": [],
        "stage_signal": "early/growth startup (remote)",
        "thin_jd": False,
        "reason": "Clean remote Senior PM; no hard domain mismatch",
    },
    "Humana": {
        "slug": "humana",
        "tier": 2,
        "decision": "PASS",
        "required": [
            "Bachelor's or equivalent",
            "5+ years product management, analytics, or related technical discipline",
            "Product portfolios, intake, prioritization frameworks",
            "Tools such as Azure DevOps, MS Project, or similar",
            "Agile or hybrid delivery",
            "Complex initiatives across multiple stakeholders",
        ],
        "preferred": [
            "Stars Analytics / healthcare quality performance",
            "Data-driven product development frameworks",
        ],
        "flagged_gaps": [
            "Healthcare Stars domain preferred (disclose: no healthcare quality domain; transferable portfolio prioritization)",
            "ADO/MS Project specifically (transferable: Jira-based portfolio/backlog tooling)",
        ],
        "stage_signal": "enterprise mature",
        "thin_jd": False,
        "reason": "General PM requireds; healthcare preferred only",
    },
    "Leader Bank": {
        "slug": "leader_bank",
        "tier": 2,
        "decision": "PASS",
        "required": [
            "Technical fluency with engineers",
            "Ambiguous problem to well-defined plan",
            "Balance competing priorities and tradeoffs",
            "Analytical / data-supported decisions",
            "Stakeholder alignment across teams",
            "Shift between strategy and execution",
        ],
        "preferred": [
            "Software development / data / technology projects",
            "Agile",
            "Requirements, user stories, process docs, business cases",
            "APIs, databases, reporting, workflow automation, integrations",
            "Banking, financial services, fintech, or regulated industries",
        ],
        "flagged_gaps": [
            "Location unclear (MA bank; no remote stated) — disclose San Diego based; confirm arrangement",
            "Banking domain preferred (transferable: regulated/compliance partnership at Cision)",
        ],
        "stage_signal": "unknown",
        "thin_jd": False,
        "reason": "TPM fit; location + banking preferred are flags",
    },
    "Monks": {
        "slug": "monks",
        "tier": 2,
        "decision": "PASS",
        "required": [
            "5+ years technological projects related to digital products/software",
            "End-to-end software product lifecycle with dedicated team",
            "Web technologies, technical concepts, software development, APIs",
            "Lead discovery sessions",
        ],
        "preferred": [
            "Mentorship of associate/mid PMs",
            "Client consulting / trusted advisor",
        ],
        "flagged_gaps": [
            "Digital agency / client-services context (possible ad-tech adjacency) — Jason-approved to proceed",
            "Occasional travel (disclose within 15% ceiling)",
        ],
        "stage_signal": "agency/services",
        "thin_jd": False,
        "reason": "Lifecycle TPM; agency context flagged",
    },
    "Kintsugi AI, Inc.": {
        "slug": "kintsugi",
        "tier": 2,
        "decision": "PASS",
        "required": [
            "1-5 years B2B SaaS Product Management",
            "Prior experience in early-stage, fast-paced SaaS startups",
            "Stakeholder management",
        ],
        "preferred": [
            "Fintech Product Management",
            "Software Engineer/QA background",
        ],
        "flagged_gaps": [
            "Early-stage startup experience (transferable: ambiguity + resource-constrained delivery; not founding/0-to-1)",
            "Sales tax / fintech domain (transferable: compliance workflows + automation products)",
            "Thin JD — lower confidence on specificity",
        ],
        "stage_signal": "early-stage",
        "thin_jd": True,
        "reason": "B2B SaaS PM; thin JD + early-stage/fintech flags",
    },
    "Stripe": {
        "slug": "stripe",
        "tier": 2,
        "decision": "PASS",
        "required": [
            "7+ years product management",
            "Meaningful time owning platform, API, or developer-facing products end to end",
            "Own product area: strategy, execution, outcomes",
            "Analytical measurement framework before shipping",
            "Clear written communication; alignment across functions",
        ],
        "preferred": [
            "Payments, fintech, or financial infrastructure",
        ],
        "flagged_gaps": [
            "Payments / Connect domain (Exclusion Zone adjacency) — disclose: no payments/billing ownership; bridge via platform reliability, data integrity, compliance workflows",
        ],
        "stage_signal": "enterprise mature",
        "thin_jd": False,
        "reason": "Platform/API match; payments Exclusion Zone stretch — disclose honestly",
    },
}


def load_jobs() -> dict[str, dict]:
    by_company: dict[str, dict] = {}
    for p in CSV_PATHS:
        with p.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                company = (row.get("Company") or "").strip()
                if company in TARGETS and company not in by_company:
                    by_company[company] = row
    return by_company


def main() -> None:
    jobs = load_jobs()
    missing = [c for c in TARGETS if c not in jobs]
    if missing:
        raise SystemExit(f"Missing companies in CSVs: {missing}")

    for company, meta in TARGETS.items():
        row = jobs[company]
        folder = OUT / meta["slug"]
        folder.mkdir(parents=True, exist_ok=True)
        jd = row.get("Job Description") or ""
        (folder / "Original_JD.txt").write_text(
            f"Company: {company}\n"
            f"Position: {(row.get('Position') or '').strip()}\n"
            f"URL: {(row.get('URL') or '').strip()}\n\n"
            f"{jd}\n",
            encoding="utf-8",
        )
        stage0 = {
            "company": company,
            "company_slug": meta["slug"],
            "position": (row.get("Position") or "").strip(),
            "url": (row.get("URL") or "").strip(),
            "tier": meta["tier"],
            "decision": meta["decision"],
            "reason": meta["reason"],
            "required": meta["required"],
            "preferred": meta["preferred"],
            "flagged_gaps": meta["flagged_gaps"],
            "stage_signal": meta["stage_signal"],
            "thin_jd": meta["thin_jd"],
            "culture_mission_notes": "See Original_JD.txt; not used for gating.",
            "source_csvs": [p.name for p in CSV_PATHS],
        }
        (folder / "stage0_fit_gate.json").write_text(
            json.dumps(stage0, indent=2), encoding="utf-8"
        )
        print(f"OK {meta['slug']} ({company})")


if __name__ == "__main__":
    main()
