# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""Pull targeted excerpts for ambiguous Stage 0 calls."""
import json
import re
from pathlib import Path

jobs = json.loads(Path("data/_tmp_stage0_batch.json").read_text(encoding="utf-8"))
by_name = {j["company"]: j for j in jobs}

needles = {
    "Leader Bank": [r"qualification", r"you have", r"experience", r"years", r"remote", r"hybrid", r"onsite", r"travel"],
    "Relativity": [r"minimum", r"qualification", r"years", r"required", r"hybrid", r"remote"],
    "Highmark Health": [r"minimum", r"qualification", r"years", r"required", r"travel", r"essential"],
    "Fluidstack": [r"0.?to.?1", r"0.?1", r"looking for", r"about the role", r"what you"],
    "Itron": [r"required skills", r"years", r"travel", r"hybrid", r"engineering"],
    "Kintsugi AI, Inc.": [r"."],  # short
    "Monks": [r"must have", r"years", r"travel", r"qualification"],
    "Pinterest": [r"looking for", r"years", r"qualification", r"experience", r"about the role"],
    "Dexcom": [r"responsibilities", r"what you", r"people", r"manage", r"travel", r"years"],
    "Cove": [r"you have", r"requirements", r"experience", r"CRE", r"looking for"],
    "Stripe": [r"minimum", r"qualification", r"years", r"you have", r"looking for"],
    "Farmers Insurance": [r"direct report", r"qualification", r"years", r"AI/ML"],
    "depthfirst": [r"relocate", r"founding", r"qualification"],
    "SONIFI Solutions, Inc.": [r"years", r"healthcare", r"you.?ll need", r"requirement"],
    "TE Connectivity": [r"years", r"level", r"qualification", r"remote", r"travel"],
    "Experis": [r"years", r"required", r"qualification", r"healthcare"],
    "Collective Health": [r"hybrid", r"office", r"years"],
    "Applause": [r"remote", r"senior"],
    "Nelnet": [r"MVP", r"0", r"required"],
    "Signal Advisors": [r"0-to-1", r"you have"],
    "CompuGroup Medical SE & Co. KGaA": [r"qualification", r"healthcare"],
    "Humana": [r"required", r"preferred", r"travel"],
    "Principal Financial Group": [r"who you are", r"hybrid", r"remote"],
    "SHAZAM Network - ITS, Inc.": [r"what you need", r"pricing", r"payment"],
    "Toptal": [r"required", r"experience"],
    "Granicus": [r"direct report", r"manage"],
    "Dow Jones": [r"you have", r"growth"],
    "Nominal": [r"0", r"looking for"],
}

out = []
for company, pats in needles.items():
    j = by_name.get(company)
    if not j:
        # fuzzy
        j = next((x for x in jobs if company.split()[0].lower() in x["company"].lower()), None)
    if not j:
        out.append(f"MISSING {company}")
        continue
    jd = j["jd"]
    out.append("=" * 80)
    out.append(f"{j['company']} — {j['position']} ({len(jd)} chars)")
    # For short JDs print all
    if len(jd) < 2500:
        out.append(jd)
        continue
    # Extract windows around key phrases
    lower = jd.lower()
    for pat in pats:
        for m in re.finditer(pat, lower, re.I):
            start = max(0, m.start() - 80)
            end = min(len(jd), m.end() + 500)
            snippet = " ".join(jd[start:end].split())
            out.append(f"\n[{pat}] ...{snippet}...")
            break  # one per pat

Path("data/_tmp_stage0_detail.txt").write_text("\n".join(out), encoding="utf-8")
print("wrote", len(out), "lines")
