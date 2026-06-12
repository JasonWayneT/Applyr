"""Generate detailed rejection report for CSV-imported jobs."""
import csv
import os
import re
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

from batch_pipeline import load_candidate_preferences
from seniority_gate import check_years_gate, passes_title_gate
from industry_gate import check_industry_gate
from anchor_gate import check_anchor_gate
from utils import passes_keyword_gate

CSV_PATH = r"C:\Users\Jason\Downloads\Job Evaluation 1 - Sheet1 (1).csv"
DB_PATH = os.path.join(PROJECT_ROOT, "jobagent.sqlite")
LOG_PATH = os.path.join(
    os.path.expanduser("~"),
    ".cursor",
    "projects",
    "c-Users-Jason-Desktop-Jason-Resource-CodeProjects-JobAgent",
    "terminals",
    "386646.txt",
)


def sanitize_filename(name):
    return re.sub(r"[\W_]+", "_", name).strip("_")


def diagnose_zero_token_gate(jd_text: str, company: str, prefs: dict) -> str | None:
    ok, reason = passes_title_gate(jd_text, prefs)
    if not ok:
        return reason
    ok, reason = check_years_gate(jd_text, prefs)
    if not ok:
        return reason
    ok, reason = check_industry_gate(company, jd_text, prefs=prefs)
    if not ok:
        return reason
    ok, reason = passes_keyword_gate(jd_text, prefs)
    if not ok:
        return reason
    ok, reason = check_anchor_gate(jd_text, prefs)
    if not ok:
        return reason
    return None


def parse_batch_log(log_text: str) -> dict[str, dict]:
    """Parse company -> {phase, score, summary, pre_score} from batch terminal log."""
    by_company: dict[str, dict] = {}
    current = None
    for line in log_text.splitlines():
        m = re.search(r"Processing: (\S+)", line)
        if m:
            current = m.group(1)
            by_company[current] = by_company.get(current, {})
            continue
        if not current:
            continue
        if "Pre-score:" in line:
            by_company[current]["pre_score"] = line.split("Pre-score:")[1].strip()
        if "Result: NO" in line or "Result: YES" in line:
            by_company[current]["fit_result"] = line.strip()
        if line.strip().startswith("-> Summary:"):
            by_company[current]["fit_summary"] = line.replace("-> Summary:", "").strip()
        if "phase=" in line and "BATCH_PROGRESS" in line:
            pm = re.search(r"current=(\S+) phase=(\w+)", line)
            if pm and pm.group(1) == current:
                by_company[current]["phase"] = pm.group(2)
        if "Duplicate/Repost" in line:
            by_company[current]["phase"] = "duplicate"
            by_company[current]["detail"] = "JD vector similarity >95% with prior job"
        if "keyword/title gate" in line:
            by_company[current]["phase"] = "keyword_reject"
        if "On-site gate" in line:
            by_company[current]["phase"] = "onsite_reject"
        if "low fit score" in line:
            by_company[current]["phase"] = "fit_reject"
    return by_company


def load_csv_rows(path: str) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
        for row in csv.DictReader(f):
            position = (row.get("Position") or "").strip()
            url = (row.get("URL") or "").strip()
            jd = (row.get("Job Description") or "").strip()
            staging = ""
            if position or url or jd:
                parts = []
                if position:
                    parts.append(f"Title: {position}")
                if url:
                    parts.append(f"URL: {url}")
                if parts:
                    parts.append("")
                parts.append(jd)
                staging = "\n".join(parts)
            rows.append({
                "company": (row.get("Company") or "").strip(),
                "position": position,
                "url": url,
                "jd": jd,
                "jd_len": len(jd),
                "staging_jd": staging,
            })
    return rows


def find_job(conn, company: str, url: str) -> dict | None:
    if url:
        row = conn.execute(
            "SELECT id, company, title, url, status, score, summary, pre_score, "
            "rejection_stage, rejection_type, outcome_notes, jd_text "
            "FROM jobs WHERE url = ? ORDER BY created_at DESC LIMIT 1",
            (url,),
        ).fetchone()
        if row:
            cols = [
                "id", "company", "title", "url", "status", "score", "summary",
                "pre_score", "rejection_stage", "rejection_type", "outcome_notes", "jd_text",
            ]
            return dict(zip(cols, row))
    row = conn.execute(
        "SELECT id, company, title, url, status, score, summary, pre_score, "
        "rejection_stage, rejection_type, outcome_notes, jd_text "
        "FROM jobs WHERE LOWER(company) = LOWER(?) ORDER BY created_at DESC LIMIT 1",
        (company,),
    ).fetchone()
    if not row:
        return None
    cols = [
        "id", "company", "title", "url", "status", "score", "summary",
        "pre_score", "rejection_stage", "rejection_type", "outcome_notes", "jd_text",
    ]
    return dict(zip(cols, row))


def info_will_be_keyword(job: dict | None, log_entry: dict) -> bool:
    phase = (log_entry or {}).get("phase", "")
    summary = (job or {}).get("summary") or ""
    return phase == "keyword_reject" or "keyword or title gate" in summary


def classify_rejection(job: dict, log_entry: dict, gate_reason: str | None) -> dict:
    phase = (log_entry or {}).get("phase", "")
    summary = (job or {}).get("summary") or ""
    score = (job or {}).get("score")

    if phase == "duplicate":
        category = "Duplicate JD"
        primary = log_entry.get("detail", "Vector duplicate of existing posting")
        gate = "duplicate_vector_check"
    elif phase == "onsite_reject":
        category = "Location / on-site"
        primary = summary or "Stealth on-site/hybrid outside San Diego"
        gate = "classify_onsite"
    elif phase == "keyword_reject" or "keyword or title gate" in summary:
        category = "Zero-token gate (no LLM fit)"
        primary = gate_reason or summary or "Keyword/title/industry/years/anchor gate"
        gate = "passes_jd_keyword_gate"
    elif phase in ("rejected", "fit_reject") or (score is not None and score < 72):
        category = "LLM fit score below threshold"
        primary = (log_entry or {}).get("fit_summary") or summary
        gate = "evaluate_job_fit (min_fit_score=72)"
    elif not job:
        category = "Not imported"
        primary = "URL already in database at import time"
        gate = "import_csv_jobs dedup"
    else:
        category = "Other"
        primary = summary or phase or "Unknown"
        gate = "unknown"

    return {
        "category": category,
        "primary_reason": primary,
        "gate": gate,
        "phase": phase,
        "fit_result": (log_entry or {}).get("fit_result"),
        "pre_score_log": (log_entry or {}).get("pre_score"),
    }


def main():
    prefs = load_candidate_preferences()
    min_fit = prefs.get("min_fit_score", 72)
    max_years = (prefs.get("experience_range") or {}).get("max", 7)

    csv_rows = load_csv_rows(CSV_PATH)
    log_by_slug = {}
    if os.path.exists(LOG_PATH):
        log_by_slug = parse_batch_log(open(LOG_PATH, encoding="utf-8", errors="ignore").read())

    conn = sqlite3.connect(DB_PATH)

    lines = []
    lines.append("# CSV Import Rejection Report")
    lines.append("")
    lines.append(f"**Source CSV:** `{CSV_PATH}`")
    lines.append(f"**Rows in sheet:** {len(csv_rows)}")
    lines.append(f"**Active gates:** min_fit_score={min_fit}, max_experience_years={max_years}")
    blocked = prefs.get("blocked_titles") or []
    lines.append(f"**Title blocklist (sample):** {', '.join(blocked[:8])}…")
    lines.append(f"**Signal keywords (need >=1):** {', '.join((prefs.get('signal_keywords') or [])[:6])}…")
    lines.append("")
    lines.append("## Import note")
    lines.append("")
    lines.append("- **27** rows imported as new jobs and evaluated in batch.")
    lines.append("- **3** rows skipped at import (URL already in database — not re-evaluated in this run).")
    lines.append("")
    lines.append("## Summary by rejection category")
    lines.append("")

    reports = []
    for i, cr in enumerate(csv_rows, 1):
        company = cr["company"]
        slug = sanitize_filename(company)
        job = find_job(conn, company, cr["url"])
        log_entry = log_by_slug.get(slug, {})
        info = classify_rejection(job, log_entry, None)

        gate_reason = None
        jd_for_gate = (job or {}).get("jd_text") or cr.get("staging_jd") or ""
        if jd_for_gate:
            gate_reason = diagnose_zero_token_gate(jd_for_gate, company, prefs)
        if gate_reason and info["category"].startswith("Zero-token"):
            info["primary_reason"] = gate_reason
        elif gate_reason and info["category"].startswith("LLM") and not (log_entry or {}).get("fit_summary"):
            # LLM never ran; zero-token would have blocked — log mismatch
            info["category"] = "Zero-token gate (no LLM fit)"
            info["primary_reason"] = gate_reason
            info["gate"] = "passes_jd_keyword_gate"
        reports.append({
            "num": i,
            "csv": cr,
            "job": job,
            "info": info,
            "gate_reason": gate_reason,
        })

    from collections import Counter
    cats = Counter(r["info"]["category"] for r in reports)
    for cat, n in cats.most_common():
        lines.append(f"- **{cat}:** {n}")
    lines.append("")
    lines.append("## Quick lookup — specific zero-token rule (recomputed from CSV JD)")
    lines.append("")
    lines.append("| Company | Rule that fails first |")
    lines.append("|---------|----------------------|")
    for r in reports:
        gr = r.get("gate_reason")
        if gr:
            lines.append(f"| {r['csv']['company']} | `{gr}` |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Per-opportunity detail")
    lines.append("")

    for r in reports:
        cr = r["csv"]
        job = r["job"] or {}
        info = r["info"]
        lines.append(f"### {r['num']}. {cr['company']}")
        lines.append("")
        lines.append(f"| Field | Value |")
        lines.append(f"|-------|-------|")
        lines.append(f"| **CSV position** | {cr['position'][:120]} |")
        lines.append(f"| **DB title** | {(job.get('title') or '—')[:120]} |")
        lines.append(f"| **Status** | {job.get('status') or 'NOT IMPORTED (duplicate URL)'} |")
        lines.append(f"| **Rejection category** | {info['category']} |")
        lines.append(f"| **Gate / stage** | `{info['gate']}` |")
        if info.get("phase"):
            lines.append(f"| **Batch phase** | `{info['phase']}` |")
        if job.get("pre_score") is not None or info.get("pre_score_log"):
            lines.append(f"| **Pre-score** | {job.get('pre_score') or info.get('pre_score_log')} |")
        if job.get("score") is not None:
            lines.append(f"| **Fit score** | {job.get('score')} (threshold >= {min_fit}) |")
        lines.append(f"| **Primary reason** | {info['primary_reason']} |")
        if r.get("gate_reason"):
            lines.append(f"| **Specific zero-token rule** | `{r['gate_reason']}` |")
        if info.get("fit_result"):
            lines.append(f"| **LLM result line** | {info['fit_result']} |")
        if cr["url"]:
            u = cr["url"][:100] + ("…" if len(cr["url"]) > 100 else "")
            lines.append(f"| **URL** | {u} |")
        lines.append(f"| **JD chars (CSV)** | {cr['jd_len']} |")
        if job.get("id"):
            lines.append(f"| **Job ID** | `{job['id']}` |")
        db_summary = (job.get("summary") or "").strip()
        if db_summary and db_summary != info["primary_reason"]:
            lines.append("")
            lines.append(f"**DB summary:** {db_summary}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Gate reference (why each category exists)")
    lines.append("")
    lines.append("1. **Zero-token gate** — Runs before LLM fit. Checks, in order: title blocklist, years required vs max, industry blocklist, must_have/signal keywords, optional anchor gate.")
    lines.append("2. **Location / on-site** — `classify_onsite()` when work_setting is Remote but JD lacks remote/SD signals.")
    lines.append("3. **Duplicate JD** — Embedding similarity >95% vs a job already processed.")
    lines.append("4. **LLM fit score** — qwen fit rubric; hard reject if score < min_fit_score (default 72). Many rows scored 28 with rubric summaries.")
    lines.append("5. **Not imported** — `import_csv_jobs.py` skipped row because URL already existed in SQLite.")
    lines.append("")

    out_path = os.path.join(PROJECT_ROOT, "docs", "reports", "csv-job-evaluation-1-rejection-report.md")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    text = "\n".join(lines)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[Wrote] {out_path} ({len(reports)} opportunities)")


if __name__ == "__main__":
    main()
