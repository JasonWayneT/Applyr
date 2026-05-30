"""Audit Backlog/Drafted jobs for apply-readiness (BUG-016 follow-up)."""
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "jobagent.sqlite"
SUB = ROOT / "submissions"
ARCH = ROOT / "archive" / "submissions"

UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.I,
)
LEGACY = re.compile(r"^[a-zA-Z0-9_-]+$")
ACTIVE = {"Backlog", "Drafted"}


def valid_id(jid: str) -> tuple[bool, str]:
    if not jid or len(jid) > 128:
        return False, "length"
    if ".." in jid or "/" in jid or "\\" in jid:
        return False, "traversal"
    if UUID.match(jid) or LEGACY.match(jid):
        return True, "ok"
    return False, "charset"


def company_slug(company: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", company.lower()).strip("_")


def find_folder_in(base: Path, label: str, company: str) -> tuple[str, Path] | None:
    if not base.exists():
        return None
    target = company_slug(company).replace("_", "")
    for d in base.iterdir():
        if d.is_dir() and d.name.replace("_", "") == target:
            return label, d
    standard = base / company_slug(company)
    if standard.exists():
        return label, standard
    return None


def find_folder(company: str) -> tuple[str, Path] | None:
    return find_folder_in(SUB, "submissions", company) or find_folder_in(ARCH, "archive", company)


def pdf_check(folder: Path) -> list[str]:
    issues = []
    pdfs = list(folder.glob("*.pdf"))
    has_resume = any("resume" in f.name.lower() for f in pdfs)
    has_cover = any("cover" in f.name.lower() for f in pdfs)
    if not has_resume:
        issues.append("missing_resume_pdf")
    if not has_cover:
        issues.append("missing_cover_pdf")
    return issues


def main() -> int:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, company, title, status, score, url FROM jobs ORDER BY company, title"
    ).fetchall()
    ready = [r for r in rows if r["status"] in ACTIVE]

    print("=== READY TO APPLY (Backlog + Drafted) ===")
    print(f"Total: {len(ready)}\n")

    issues_by_job: list[dict] = []
    company_counts: dict[str, int] = {}
    for r in ready:
        key = r["company"].lower()
        company_counts[key] = company_counts.get(key, 0) + 1

    for r in sorted(ready, key=lambda x: (x["company"].lower(), x["title"])):
        ok, _ = valid_id(r["id"])
        blocked = " [WOULD BLOCK BEFORE FIX]" if not ok else ""
        print(
            f"  {r['status']:8}  {r['company'][:28]:28}  {r['title'][:38]:38}  id={r['id']}{blocked}"
        )

        row_issues: list[str] = []
        ok_id, reason = valid_id(r["id"])
        if not ok_id:
            row_issues.append(f"invalid_job_id:{reason}")

        loc = find_folder_in(SUB, "submissions", r["company"])
        if not loc:
            arch = find_folder_in(ARCH, "archive", r["company"])
            if arch and list(arch[1].glob("*.pdf")):
                row_issues.append("assets_in_archive_only")
            else:
                row_issues.append("no_submission_folder")
        else:
            row_issues.extend(pdf_check(loc[1]))

        if company_counts.get(r["company"].lower(), 0) > 1:
            row_issues.append(f"duplicate_company:{company_counts[r['company'].lower()]}_rows")

        if row_issues:
            issues_by_job.append(
                {
                    "id": r["id"],
                    "company": r["company"],
                    "title": r["title"],
                    "status": r["status"],
                    "score": r["score"],
                    "issues": row_issues,
                }
            )

    print("\n=== ISSUES FOUND ===")
    if not issues_by_job:
        print("None — all ready jobs pass ID validation and have resume+cover PDFs in submissions/")
    else:
        for item in issues_by_job:
            print(f"\n{item['company']} — {item['title']} ({item['status']}, score={item['score']})")
            print(f"  id: {item['id']}")
            for iss in item["issues"]:
                print(f"  - {iss}")

    # Summary counts
    print("\n=== SUMMARY ===")
    uuid_only = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        re.I,
    )
    pre_fix_blocked = sum(1 for r in ready if not uuid_only.match(r["id"]))
    print(f"Jobs ready to apply: {len(ready)}")
    print(f"Would fail UUID-only id check (pre BUG-016 fix): {pre_fix_blocked}")
    print(f"Jobs with any issue after fix: {len(issues_by_job)}")

    backlog = [r for r in rows if r["status"] == "Backlog"]
    print("\n=== TODAY VIEW PIPELINE (Backlog + PDFs in submissions/) ===")
    ok_count = 0
    for r in sorted(backlog, key=lambda x: (-(x["score"] or 0), x["company"].lower())):
        loc = find_folder_in(SUB, "submissions", r["company"])
        sub_pdfs = loc[1] if loc else None
        has_assets = bool(sub_pdfs and list(sub_pdfs.glob("*.pdf")))
        if not has_assets:
            continue
        ok_count += 1
        legacy = "legacy_id" if not uuid_only.match(r["id"]) else "uuid"
        dupe = company_counts.get(r["company"].lower(), 0) > 1
        flags = []
        if legacy == "legacy_id":
            flags.append("needs BUG-016 server restart")
        if dupe:
            flags.append("duplicate company rows")
        flag_str = f"  [{', '.join(flags)}]" if flags else ""
        print(f"  score={r['score']}  {r['company'][:30]:30}  {r['title'][:35]:35}  id={r['id']}{flag_str}")
    print(f"\nPipeline count: {ok_count}")

    print("\n=== BACKLOG WITHOUT submissions/ PDFs (hidden from Today) ===")
    for r in sorted(backlog, key=lambda x: x["company"].lower()):
        loc = find_folder_in(SUB, "submissions", r["company"])
        sub_pdfs = loc[1] if loc else None
        has_assets = bool(sub_pdfs and list(sub_pdfs.glob("*.pdf")))
        if has_assets:
            continue
        arch = find_folder_in(ARCH, "archive", r["company"])
        arch_note = " (PDFs in archive only)" if arch and list(arch[1].glob("*.pdf")) else ""
        print(f"  {r['company']} — {r['title'][:40]} (id={r['id']}){arch_note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
