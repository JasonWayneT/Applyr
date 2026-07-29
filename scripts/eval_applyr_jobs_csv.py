#!/usr/bin/env python3
"""Evaluate applyr_jobs CSV exports: quality + human fit read."""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from seniority_gate import passes_title_gate, title_blocked, extract_job_title_line

FILES = [
    Path(r"C:\Users\Jason\Downloads\applyr_jobs.csv"),
    Path(r"C:\Users\Jason\Downloads\applyr_jobs (3).csv"),
]
OUT = PROJECT_ROOT / "docs" / "reports" / "applyr-jobs-csv-eval.md"
PREFS_PATH = PROJECT_ROOT / "data" / "candidate_preferences.json"

WEAK_URL_PATTERNS = (
    "linkedin.com/jobs/search",
    "search-results",
    "currentjobid=",
)


def parse_title(jd: str) -> str:
    m = re.search(r"^Title:\s*(.+)$", jd, re.M)
    if m:
        return m.group(1).strip()
    return jd.split("\n", 1)[0].strip()[:120]


def quality_row(company: str, url: str, jd: str) -> dict:
    issues = []
    if not url.strip():
        issues.append("missing_url")
    elif any(p in url.lower() for p in WEAK_URL_PATTERNS):
        issues.append("weak_search_url")
    if len(jd) < 800:
        issues.append("short_jd")
    if len(jd) < 2000:
        issues.append("thin_jd")
    if "Title:" not in jd[:200]:
        issues.append("no_title_line")
    if not re.search(r"(responsibilit|what you|role|about the job|job details)", jd, re.I):
        issues.append("maybe_truncated")
    if not re.search(r"(salary|compensation|\$\d)", jd, re.I):
        issues.append("no_salary")
    if not re.search(r"(remote|hybrid|onsite|location)", jd, re.I):
        issues.append("no_location")
    if not re.search(r"(\d+\+?\s*years?|\d+-\d+\s*years?)", jd, re.I):
        issues.append("no_yoe")
    return {
        "company": company,
        "title": parse_title(jd),
        "url": url,
        "jd_len": len(jd),
        "issues": issues,
    }


def human_fit(company: str, title: str, jd: str, prefs: dict) -> tuple[str, int, str]:
    """Returns tier, score-ish, one-line reason."""
    title_line = title or extract_job_title_line(jd)
    t = f"{title_line} {jd}".lower()

    blocked = title_blocked(title_line, prefs)
    if blocked:
        return "skip", 35, f"Title blocked: {blocked}"

    if re.search(r"\b(?:founding|first)\s+product\s+manager\b", title_line, re.I):
        return "skip", 35, "Founding / first PM trap"

    if any(x in t for x in ("machine learning engineer", "data scientist", "ai/ml product lead", "train models", "model training")):
        return "skip", 30, "AI/ML lead — exclusion zone"
    if any(x in t for x in ("robotics", "autonomous mobile robot", "hardware product", "semiconductor fab")):
        return "skip", 40, "Hardware/robotics domain"
    if re.search(r"\bproduct\s+owner\b", title_line, re.I) and not re.search(
        r"\bproduct\s+manager\b", title_line, re.I
    ):
        return "skip", 50, "PO role, not PM"
    if re.search(r"\bgrowth\s+product\s+manager\b", title_line, re.I) or title_line.lower().startswith("growth"):
        return "skip", 45, "Growth PM blocklist"
    if "operations product manager" in title_line.lower() and "salesforce" in company.lower():
        return "skip", 48, "Internal ops/BT config — not product PM"
    if "insurance" in t and re.search(r"\bproduct\s+manager\s+ii\b", title_line, re.I):
        return "tier2", 68, "Insurance B2B PM II — backlog/roadmap heavy; insurance domain stretch"

    # Positives
    score = 60
    reasons = []

    if any(x in t for x in ("b2b saas", "saas platform", "enterprise saas", "b2b software")):
        score += 8
        reasons.append("B2B SaaS")
    if any(x in t for x in ("platform", "integration", "api", "workflow")):
        score += 6
        reasons.append("platform/integration")
    if any(x in t for x in ("healthcare", "health ", "patient", "clinical", "medical")):
        score += 5
        reasons.append("healthcare")
    if any(x in t for x in ("education", "edtech", "learner", "k-12", "school")):
        score += 5
        reasons.append("ed-tech")
    if any(x in t for x in ("cross-functional", "roadmap", "discovery", "stakeholder")):
        score += 4
        reasons.append("core PM craft")
    if re.search(r"\bsenior\s+product\s+manager\b", title_line, re.I):
        score += 3
        reasons.append("senior PM in scope")
    if re.search(r"san diego|carlsbad", t):
        score += 3
        reasons.append("local SD")

    # Penalties
    if any(x in t for x in ("0 to 1", "0-to-1", "greenfield", "first pm hire", "solo pm")):
        score -= 12
        reasons.append("0-to-1 risk")
    if any(x in t for x in ("payments", "billing system", "revenue platform", "pricing engine owner")):
        score -= 10
        reasons.append("payments/revenue")
    if any(x in t for x in ("logistics", "freight", "supply chain", "fleet manager")):
        score -= 3
        reasons.append("logistics stretch")
    if any(x in t for x in ("people manager", "direct reports", "hire and fire")):
        score -= 15
        reasons.append("people mgmt")

    score = max(25, min(92, score))
    reason = ", ".join(reasons[:4]) if reasons else "generic PM"

    if score >= 72:
        tier = "apply"
    elif score >= 62:
        tier = "tier2"
    else:
        tier = "skip"

    return tier, score, reason


def load_csv(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8-sig", errors="ignore") as f:
        for row in csv.DictReader(f):
            company = (row.get("Company") or "").strip()
            jd = (row.get("Job Description") or "").strip()
            url = (row.get("URL") or row.get("Url") or "").strip()
            position = (row.get("Position") or "").strip()
            if not company or not jd:
                continue
            if not position:
                position = parse_title(jd)
            rows.append({"company": company, "position": position, "url": url, "jd": jd, "source": path.name})
    return rows


def main() -> None:
    import json

    prefs = json.loads(PREFS_PATH.read_text(encoding="utf-8")) if PREFS_PATH.exists() else {}

    all_rows: list[dict] = []
    for fp in FILES:
        if fp.exists():
            all_rows.extend(load_csv(fp))

    # dedupe by url or company+title
    seen: set[str] = set()
    unique: list[dict] = []
    dupes = 0
    for r in all_rows:
        key = r["url"] if r["url"] else f"{r['company']}|{r['position'][:60]}"
        if key in seen:
            dupes += 1
            continue
        seen.add(key)
        unique.append(r)

    evaluated = []
    for r in unique:
        q = quality_row(r["company"], r["url"], r["jd"])
        tier, score, reason = human_fit(r["company"], r["position"], r["jd"], prefs)
        evaluated.append({**r, **q, "tier": tier, "score": score, "fit_reason": reason})

    evaluated.sort(key=lambda x: (-x["score"], x["company"]))

    issue_counts: dict[str, int] = {}
    for e in evaluated:
        for i in e["issues"]:
            issue_counts[i] = issue_counts.get(i, 0) + 1

    lines = [
        "# applyr_jobs CSV Evaluation",
        "",
        f"Sources: `{FILES[0].name}` ({sum(1 for r in all_rows if r['source']==FILES[0].name)} rows), "
        f"`{FILES[1].name}` ({sum(1 for r in all_rows if r['source']==FILES[1].name)} rows)",
        f"**Unique jobs:** {len(unique)} | **Duplicates dropped:** {dupes}",
        "",
        "## Extraction quality (automation vs manual)",
        "",
        "| Issue | Count | Why it matters |",
        "|-------|------:|----------------|",
    ]
    issue_help = {
        "missing_url": "Import creates `local://` stub; harder to dedupe and re-open posting",
        "weak_search_url": "LinkedIn search URL, not job permalink — breaks re-fetch",
        "short_jd": "Under 800 chars — fit scoring unreliable",
        "thin_jd": "Under 2000 chars — may miss requirements/salary",
        "no_title_line": "No `Title:` prefix — import_csv_jobs won't get Position column",
        "maybe_truncated": "Missing responsibilities section — partial scrape",
        "no_salary": "Can't sanity-check comp without opening posting",
        "no_location": "Remote/hybrid filter harder",
        "no_yoe": "Experience gate may misfire",
    }
    for k, v in sorted(issue_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| `{k}` | {v} | {issue_help.get(k, '')} |")

    lines += [
        "",
        "**Missing column vs `import_csv_jobs.py`:** exporter has `Company, Job Description, URL` but importer also accepts **`Position`** as separate column. Title is embedded in JD as `Title:` — works, but a dedicated Position column is safer.",
        "",
        "**Recommend adding to automation export:**",
        "- `Position` (separate from JD body)",
        "- `Location` / `Work setting`",
        "- `Salary` or `Salary range`",
        "- `Posted date`",
        "- `Job ID` (LinkedIn/ATS id for dedupe)",
        "- `Source` (LinkedIn, greenhouse, etc.)",
        "",
        "## Fit summary",
        "",
    ]
    for tier_name in ("apply", "tier2", "skip"):
        bucket = [e for e in evaluated if e["tier"] == tier_name]
        lines.append(f"### {tier_name.upper()} ({len(bucket)})")
        lines.append("")
        for e in bucket:
            flags = f" ⚠ `{','.join(e['issues'])}`" if e["issues"] else ""
            lines.append(
                f"- **{e['company']}** — {e['title']} (score ~{e['score']}) — {e['fit_reason']}{flags}"
            )
        lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT)
    print(f"unique={len(unique)} apply={sum(1 for e in evaluated if e['tier']=='apply')} tier2={sum(1 for e in evaluated if e['tier']=='tier2')} skip={sum(1 for e in evaluated if e['tier']=='skip')}")
    for e in evaluated:
        if e["tier"] in ("apply", "tier2"):
            print(f"  [{e['tier']}] {e['score']} {e['company']} | {e['title'][:50]}")


if __name__ == "__main__":
    main()
