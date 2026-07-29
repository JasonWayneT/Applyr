import json
import os

manifest_path = "data/submissions/ispot/draft_manifest.json"
with open(manifest_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

data["rubric_score"] = {
  "resume": {
    "overall": 94,
    "R1_ats_integrity": {"score": 10, "evidence": "Standard markdown formatting with standard headers like '## PROFESSIONAL EXPERIENCE' and no tables"},
    "R2_jd_alignment": {"score": 15, "evidence": "Summary highlights 'driving the release coordination, risk mapping, and technical delivery' which matches JD"},
    "R3_top_third_signal": {"score": 15, "evidence": "Core Competencies includes 'Backend Platform Execution' and 'SQL Database Discovery'"},
    "R4_metric_quality": {"score": 20, "evidence": "Bullet uses clear metrics: 'stabilized a $40M ARR legacy platform serving roughly 3,500 active accounts'"},
    "R5_pm_craft_coverage": {"score": 9, "evidence": "Heavy on delivery and stakeholder synthesis ('Synthesized requirements from Legal, DevOps, Sales') but lacks discovery/experimentation"},
    "R6_seniority_altitude": {"score": 10, "evidence": "Demonstrates scope ownership: 'presenting it to 200-300 stakeholders including executive leadership'"},
    "R7_internal_consistency": {"score": 10, "evidence": "Summary claims direct SQL discovery, supported by bullet: 'Queried and navigated roughly 200 SQL databases directly'"},
    "R8_b2b_saas_legibility": {"score": 5, "evidence": "Includes ARR, account numbers, and cross-functional partners ('Legal, DevOps, Sales, and Customer Experience')"},
    "verdict": "CONVERT-READY (70+ threshold)"
  },
  "cover_letter": {
    "overall": 82,
    "C1_opening_hook": {"score": 15, "evidence": "Specific to company function ('ISpot brings transparency to advertising...') but slightly generic"},
    "C2_proof_density": {"score": 25, "evidence": "Uses Sterkly and Cision accomplishments with specific details like 'resolved a 40 percent data drop-off rate'"},
    "C3_role_fit_logic": {"score": 20, "evidence": "Connects past data pipeline work to the 'large-scale calculations' required for the new role"},
    "C4_authenticity": {"score": 12, "evidence": "Mostly natural but has some standard phrasing like 'caught my eye' and 'I would welcome the opportunity'"},
    "C5_length_structure": {"score": 10, "evidence": "Four paragraphs, ~220 words, no bullets"},
    "verdict": "CONVERT-READY (65+ threshold)"
  }
}

with open(manifest_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)
