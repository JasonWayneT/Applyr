"""One-off audit of jobs DB + submissions folders (CR-017/018)."""
import json
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bullet_fit import is_incomplete_bullet
from jd_tailoring import load_bridge_phrases

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(PROJECT_ROOT, "data", "jobagent.sqlite")
SUBMISSIONS = os.path.join(PROJECT_ROOT, "data", "submissions")

ID_TOKEN = re.compile(r"\b(ACC|MET|VOC)-\d+\b|\|\s*(ACC|MET|VOC)-\d+\s*\|", re.I)
SLUG = re.compile(r"\b[A-Z][a-z]+(?:_[A-Z][a-z0-9]+)+_?(?:Inc|LLC)?\b")


def audit_folder(name, path):
    issues = []
    manifest = {}
    mp = os.path.join(path, "draft_manifest.json")
    if os.path.exists(mp):
        with open(mp, encoding="utf-8") as f:
            manifest = json.load(f)
    for doc in ("Resume.md", "CoverLetter.md"):
        fp = os.path.join(path, doc)
        if not os.path.exists(fp):
            issues.append(f"missing {doc}")
            continue
        with open(fp, encoding="utf-8") as f:
            t = f.read()
        if ID_TOKEN.search(t):
            issues.append(f"{doc}: ID token leak")
        if doc == "CoverLetter.md" and SLUG.search(t):
            issues.append(f"{doc}: possible slug company")
        if "& CERTIFICATIONS" in t and doc == "Resume.md":
            issues.append(f"{doc}: ghost education header")
        if doc == "Resume.md":
            for line in t.splitlines():
                if line.strip().startswith("*") and is_incomplete_bullet(line.lstrip("* ").strip()):
                    issues.append(f"{doc}: incomplete bullet ending")
                    break
            bridged = 0
            phrases = load_bridge_phrases()
            for line in t.splitlines():
                if not line.strip().startswith("*"):
                    continue
                for phrase in phrases.values():
                    p = phrase.strip()
                    if p and line.lower().startswith("* " + (p[0].upper() + p[1:] + ": ").lower()):
                        bridged += 1
                        break
            if bridged > 1:
                issues.append(f"{doc}: duplicate bridge prefixes ({bridged})")
        if doc == "CoverLetter.md":
            cover_l = t.lower()
            for phrase in load_bridge_phrases().values():
                p = phrase.strip()
                if p and (p[0].upper() + p[1:] + ": ").lower() in cover_l:
                    issues.append(f"{doc}: bridge prefix in cover")
                    break
    for pdf in ("Resume.pdf", "CoverLetter.pdf"):
        if not os.path.exists(os.path.join(path, pdf)):
            issues.append(f"missing {pdf}")
    return manifest, issues


def main():
    if not os.path.exists(DB):
        print("No jobagent.sqlite found")
        return
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    print("=== STATUS COUNTS ===")
    for status, n in cur.execute(
        "SELECT status, COUNT(*) FROM jobs GROUP BY status ORDER BY COUNT(*) DESC"
    ):
        print(f"  {status}: {n}")

    print("\n=== BACKLOG ===")
    backlog = cur.execute(
        """SELECT company, score, retry_count,
           substr(COALESCE(summary,''),1,90) FROM jobs
           WHERE status IN ('Backlog', 'Needs Retry') AND score >= 72
           ORDER BY score DESC"""
    ).fetchall()
    if not backlog:
        print("  (none)")
    for row in backlog:
        stale = (
            "Asset drafting failed" in (row[3] or "")
            or "numeric audit" in (row[3] or "")
        )
        flag = " STALE_SUMMARY" if stale else ""
        print(f"  {row[0]} | score={row[1]} | retry={row[2]} | {row[3]}{flag}")

    print("\n=== NEEDS RETRY ===")
    retry = cur.execute(
        """SELECT company, score, retry_count,
           substr(COALESCE(summary,''),1,100) FROM jobs
           WHERE status='Needs Retry' ORDER BY company LIMIT 25"""
    ).fetchall()
    if not retry:
        print("  (none)")
    for row in retry:
        print(f"  {row[0]} | score={row[1]} | retry={row[2]} | {row[3]}")

    print("\n=== PASSED SCORE BUT NOT BACKLOG (sample) ===")
    for row in cur.execute(
        """SELECT company, status, score FROM jobs
           WHERE score >= 72 AND status NOT IN ('Backlog','Applied','Interview')
           ORDER BY score DESC LIMIT 15"""
    ):
        print(f"  {row[0]} | {row[1]} | {row[2]}")

    conn.close()

    print("\n=== SUBMISSIONS FOLDERS ===")
    if not os.path.isdir(SUBMISSIONS):
        print(f"  No submissions dir at {SUBMISSIONS}")
        return
    dirs = sorted(
        d for d in os.listdir(SUBMISSIONS)
        if os.path.isdir(os.path.join(SUBMISSIONS, d)) and d != "archive"
    )
    print(f"  {len(dirs)} company folders (excl. archive)")

    backlog_names = {r[0].lower().replace(" ", "_") for r in backlog}
    targets = {
        "acxiom", "art_of_problem_solving", "athennian", "jobgether",
        "kohls", "ovme", "premier_inc", "the_data_group_inc",
    }
    print("\n=== QUALITY AUDIT (8 opportunity folders) ===")
    for d in dirs:
        if d.lower() not in targets:
            continue
        path = os.path.join(SUBMISSIONS, d)
        manifest, issues = audit_folder(d, path)
        ver = manifest.get("pipeline_version", "?")
        mode = manifest.get("draft_mode", "?")
        passed = manifest.get("verification_passed", "?")
        cs = manifest.get("cheat_sheet_source", "?")
        cheat_path = os.path.join(path, "Interview_Cheat_Sheet.md")
        if os.path.exists(os.path.join(path, "Research_Packet.json")) or os.path.exists(
            os.path.join(path, "Research_Packet.md")
        ):
            if not os.path.exists(cheat_path) or os.path.getsize(cheat_path) < 50:
                issues.append("missing or empty Interview_Cheat_Sheet.md")
        flag = "OK" if not issues else "ISSUES"
        print(f"  [{flag}] {d} | pipeline={ver} mode={mode} verified={passed} cheat={cs}")
        for i in issues:
            print(f"       - {i}")

    print("\n=== ALL FOLDERS WITH PDFs (quick) ===")
    for d in dirs[:40]:
        path = os.path.join(SUBMISSIONS, d)
        has_r = os.path.exists(os.path.join(path, "Resume.pdf"))
        has_c = os.path.exists(os.path.join(path, "CoverLetter.pdf"))
        if has_r and has_c:
            manifest, issues = audit_folder(d, path)
            if issues:
                print(f"  {d}: {', '.join(issues[:3])}")


if __name__ == "__main__":
    main()
