#!/usr/bin/env python3
"""Legacy CSV → pending_review one-shot. Prefer scripts/ingest_csv_queue.py (CR-119).

# Implements FR-264 / CR-091 — incoming JDs do not land in submissions/.
# Reduced to a wrapper over csv_ingest.py. Hardcoded Downloads paths removed.
"""
from __future__ import annotations

import csv
import re
import sys
from datetime import datetime
from pathlib import Path

from csv_ingest import (
    existing_urls as _existing_urls,
    sanitize,
    unique_slug as _unique_slug,
    url_to_slug as _url_to_slug,
    write_jd as _write_jd,
)
from stage0_skip_ledger import lookup_skip

# Added 2026-08-18: this script crashed outright on a real run with
# UnicodeEncodeError -- the Windows console's default cp1252 codec can't
# encode a skip-reason string containing a non-ASCII arrow character.
# PYTHONIOENCODING=utf-8 set by the caller works around it, but only if the
# caller remembers to set it; reconfiguring stdout/stderr here means the
# script self-heals regardless of who invokes it or how. errors="replace"
# (not "strict") so a still-unanticipated character degrades to a visible
# replacement glyph instead of crashing the whole import mid-batch.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
PENDING_REVIEW = ROOT / "data" / "pending_review"
SUBMISSIONS = ROOT / "data" / "submissions"
DB = ROOT / "data" / "jobagent.sqlite"
SKIP_COMPLETE = {"ncontracts", "leaflink", "camunda", "central_bank"}


def existing_urls() -> set[str]:
    return _existing_urls(DB, PENDING_REVIEW, SUBMISSIONS)


def url_to_slug() -> dict[str, str]:
    return _url_to_slug(DB, PENDING_REVIEW, SUBMISSIONS)


def unique_slug(base: str) -> str:
    return _unique_slug(base, PENDING_REVIEW, SUBMISSIONS)


def write_jd(slug: str, url: str, position: str, jd: str) -> Path:
    return _write_jd(slug, url, position, jd, dest_root=PENDING_REVIEW)


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
            prior = lookup_skip(url=url or None, company=company, title=position, db_path=DB)
            if prior:
                print(
                    f"  skip ledger: {company} | {prior.get('skip_reason', 'prior Skip')}"
                )
                continue
            if url and url.lower() in known_urls:
                existing = url_slugs.get(url.lower())
                pending_jd = PENDING_REVIEW / existing / "Original_JD.txt" if existing else None
                live_jd = SUBMISSIONS / existing / "Original_JD.txt" if existing else None
                if existing and (
                    (pending_jd and pending_jd.exists()) or (live_jd and live_jd.exists())
                ):
                    created.append(existing)
                    print(f"  reuse {existing} | {position}")
                else:
                    print(f"  skip dup URL: {company} | {url[:60]}")
                continue
            base = sanitize(company)
            if base in SKIP_COMPLETE:
                # Prefer role-disambiguated slug rather than overwriting COMPLETE
                base = sanitize(f"{company}_{position}") or base
            folder = PENDING_REVIEW / base
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
    if not argv:
        print(
            "Usage: python scripts/import_csv_to_submissions.py <csv> [csv...]\n"
            "Legacy one-shot. Prefer: python scripts/ingest_csv_queue.py",
            file=sys.stderr,
        )
        return 2
    paths = [Path(p) for p in argv]
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
    # Bug fix (2026-08-15): this used to be a hardcoded literal filename
    # ("csv_import_slugs_2026-08-14.txt") that every run, on any date,
    # silently overwrote -- destroyed a real 47-slug record from a prior
    # cleanup with zero warning. One-file-per-run, timestamped to the
    # second, matches this script's actual usage (an occasional batch
    # import, not a continuous logger) and needs no merge/append logic.
    out = ROOT / "data" / "reports" / f"csv_import_slugs_{datetime.now():%Y-%m-%dT%H%M%S}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(unique) + "\n", encoding="utf-8")
    print(f"slug list: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
