#!/usr/bin/env python3
"""Import applyr_jobs CSVs into data/submissions/{slug}/Original_JD.txt (no DB finalize)."""
from __future__ import annotations

import csv
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUBMISSIONS = ROOT / "data" / "submissions"
DB = ROOT / "data" / "jobagent.sqlite"
SKIP_COMPLETE = {"ncontracts", "leaflink", "camunda", "central_bank"}


def sanitize(name: str) -> str:
    return re.sub(r"[\W_]+", "_", name).strip("_").lower()


def existing_urls() -> set[str]:
    return set(url_to_slug().keys())


def url_to_slug() -> dict[str, str]:
    """Map lowercase URL -> submission slug (folder wins over DB-only rows)."""
    mapping: dict[str, str] = {}
    if DB.exists():
        conn = sqlite3.connect(DB)
        for u, company in conn.execute(
            "SELECT url, company FROM jobs WHERE url IS NOT NULL"
        ):
            if u:
                mapping[u.strip().lower()] = sanitize(company or "")
        conn.close()
    for folder in SUBMISSIONS.iterdir():
        if not folder.is_dir():
            continue
        jd = folder / "Original_JD.txt"
        if not jd.exists():
            continue
        first = jd.read_text(encoding="utf-8", errors="ignore").splitlines()[:1]
        if first and first[0].lower().startswith("url:"):
            mapping[first[0].split(":", 1)[1].strip().lower()] = folder.name
    return mapping


def unique_slug(base: str) -> str:
    slug = base
    n = 2
    while (SUBMISSIONS / slug).exists():
        # If folder already has same company but we're importing a new URL, disambiguate
        slug = f"{base}_{n}"
        n += 1
    return slug


def write_jd(slug: str, url: str, position: str, jd: str) -> Path:
    folder = SUBMISSIONS / slug
    folder.mkdir(parents=True, exist_ok=True)
    parts = []
    if url:
        parts.append(f"URL: {url}")
        parts.append("")
    if position:
        parts.append(f"Title: {position}")
        parts.append("")
    parts.append(jd.strip())
    path = folder / "Original_JD.txt"
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return path


def import_csv(path: Path, known_urls: set[str], url_slugs: dict[str, str]) -> list[str]:
    created: list[str] = []
    with path.open(encoding="utf-8-sig", errors="ignore", newline="") as f:
        for row in csv.DictReader(f):
            company = (row.get("Company") or "").strip()
            position = (row.get("Position") or "").strip()
            url = (row.get("URL") or "").strip()
            jd = (row.get("Job Description") or "").strip()
            if not company or not jd:
                print(f"  skip empty: {company!r}")
                continue
            if url and url.lower() in known_urls:
                existing = url_slugs.get(url.lower())
                if existing and (SUBMISSIONS / existing / "Original_JD.txt").exists():
                    created.append(existing)
                    print(f"  reuse {existing} | {position}")
                else:
                    print(f"  skip dup URL: {company} | {url[:60]}")
                continue
            base = sanitize(company)
            if base in SKIP_COMPLETE:
                # Prefer role-disambiguated slug rather than overwriting COMPLETE
                base = sanitize(f"{company}_{position}") or base
            folder = SUBMISSIONS / base
            if folder.exists() and (folder / "workflow_state.json").exists():
                # Existing pending folder — overwrite JD only if no COMPLETE
                import json

                st = json.loads((folder / "workflow_state.json").read_text(encoding="utf-8"))
                if st.get("status") in ("COMPLETE", "COMPLETE_WITH_OVERRIDE"):
                    slug = unique_slug(sanitize(f"{company}_{position}"))
                else:
                    slug = base
            elif folder.exists() and (folder / "Original_JD.txt").exists():
                # Existing JD — if URL differs, disambiguate
                existing = (folder / "Original_JD.txt").read_text(encoding="utf-8", errors="ignore")
                m = re.match(r"^URL:\s*(\S+)", existing)
                existing_url = m.group(1).strip().lower() if m else ""
                if url and existing_url and existing_url != url.lower():
                    slug = unique_slug(sanitize(f"{company}_{position}"))
                else:
                    slug = base
            else:
                slug = base

            write_jd(slug, url, position, jd)
            if url:
                known_urls.add(url.lower())
                url_slugs[url.lower()] = slug
            created.append(slug)
            print(f"  wrote {slug} | {position}")
    return created


def main(argv: list[str]) -> int:
    paths = [Path(p) for p in argv] or [
        Path(r"c:\Users\Jason\Downloads\applyr_jobs.csv"),
        Path(r"c:\Users\Jason\Downloads\applyr_jobs (1).csv"),
        Path(r"c:\Users\Jason\Downloads\applyr_jobs (2).csv"),
        Path(r"c:\Users\Jason\Downloads\applyr_jobs (3).csv"),
    ]
    url_slugs = url_to_slug()
    known = set(url_slugs.keys())
    all_slugs: list[str] = []
    for p in paths:
        print(f"Importing {p}")
        all_slugs.extend(import_csv(p, known, url_slugs))
    # Preserve order, drop empty, keep first occurrence of each slug
    seen: set[str] = set()
    unique: list[str] = []
    for slug in all_slugs:
        if slug and slug not in seen:
            seen.add(slug)
            unique.append(slug)
    print(f"Imported {len(unique)} folders ({len(all_slugs)} CSV rows mapped)")
    out = ROOT / "data" / "reports" / "csv_import_slugs_2026-08-14.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(unique) + "\n", encoding="utf-8")
    print(f"slug list: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
