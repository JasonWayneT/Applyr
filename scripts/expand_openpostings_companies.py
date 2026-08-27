"""Grow OpenPostings' `companies` table from a real, external company-slug list instead of
hand-guessing board tokens from memory (the mistake made on 2026-08-26 before this script
existed — see CHANGELOG.md).

Source lists: data/archive/ats_company_seed_lists/{greenhouse,lever,ashby}_companies.json —
flat arrays of board tokens harvested from Common Crawl by
https://github.com/Feashliaa/job-board-aggregator (its data/ folder, MIT-licensed data,
refreshed periodically). Re-download them to pick up newly-added companies:

    curl -sL -o data/archive/ats_company_seed_lists/greenhouse_companies.json \
        https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data/greenhouse_companies.json
    (same for lever_companies.json, ashby_companies.json)

For each candidate token not already in OpenPostings' companies table, this hits the real
public Greenhouse/Lever/Ashby job board API (no auth, no cost) and only inserts the company
if it currently has at least one live posting matching the product-manager title family
(same regex as shared/domain/gates.ts's PRODUCT_MANAGER_FAMILY_TITLE) that survives Jason's
own blocked_titles/blocked_role_titles/blocked_focus_area_words from
data/candidate_preferences.json.

This is a live-relevance filter, not a bulk import: OpenPostings' own sync already takes
longer than its 2-minute per-run timeout across ~7,800 companies (see README.md), so adding
thousands of irrelevant companies would dilute how often the ones that matter get re-crawled.
A company with no qualifying posting today is simply not added this run — re-run periodically
(e.g. monthly, after refreshing the source lists) to catch newly-relevant companies; this does
not retry a token that was already checked and rejected within the same static candidate list.

Progress is checkpointed (data/archive/ats_company_seed_lists/scan_progress.json) so a run can
be interrupted and resumed with --limit without re-checking tokens already decided.

Usage:
    python scripts/expand_openpostings_companies.py --limit 500
    python scripts/expand_openpostings_companies.py --limit 500 --ats greenhouse
    python scripts/expand_openpostings_companies.py --status
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = REPO_ROOT / "data" / "archive" / "ats_company_seed_lists"
PROGRESS_PATH = SEED_DIR / "scan_progress.json"
OPENPOSTINGS_DB = (
    REPO_ROOT / "data" / "archive" / "OpenPostings-extracted" / "OpenPostings-main" / "jobs.db"
)
CANDIDATE_PREFS_PATH = REPO_ROOT / "data" / "candidate_preferences.json"

REQUEST_DELAY_SECONDS = 0.2
RATE_LIMIT_BACKOFF_SECONDS = 5
USER_AGENT = "Mozilla/5.0"

PRODUCT_MANAGER_FAMILY_TITLE = re.compile(
    r"\b(?:(?:technical|platform|data|enterprise|api|integration|infrastructure|senior|group)\s+)?"
    r"product\s+manager\b",
    re.I,
)
OTHER_TERMS = ("product owner",)
# "program manager" deliberately excluded as a standalone qualifier (2026-08-26): it's a
# generic title that collides with defense/construction/nonprofit/HR/manufacturing postings
# just as often as with a real product role — a first 900-candidate batch added 22 companies
# (of 80) whose only qualifying hit was bare "program manager" (aerospace, government
# contracting, foster-care nonprofits, marketing events). It stays a valid title Jason will
# accept for an actual job match elsewhere in the app; it's just too noisy a signal for
# deciding whether a *company* is worth tracking at all.

ATS_CONFIG = {
    "greenhouse": {
        "seed_file": "greenhouse_companies.json",
        "ats_name": "GreenHouse",
        "url": lambda token: f"https://job-boards.greenhouse.io/{token}",
        "api": lambda token: f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
        "extract_titles": lambda data: [j["title"] for j in data.get("jobs", [])],
    },
    "lever": {
        "seed_file": "lever_companies.json",
        "ats_name": "LeverCO",
        "url": lambda token: f"https://jobs.lever.co/{token}",
        "api": lambda token: f"https://api.lever.co/v0/postings/{token}?mode=json",
        "extract_titles": lambda data: [j["text"] for j in data] if isinstance(data, list) else [],
    },
    "ashby": {
        "seed_file": "ashby_companies.json",
        "ats_name": "AshbyHQ",
        "url": lambda token: f"https://jobs.ashbyhq.com/{token}",
        "api": lambda token: f"https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true",
        "extract_titles": lambda data: [j["title"] for j in data.get("jobs", [])],
    },
}


MIN_POSTINGS_ON_BOARD = 3  # filters out demo/trial/abandoned ATS accounts, not real employers


def load_blocklist_terms() -> tuple[list[str], list[str]]:
    """Returns (title_blocklist, industry_blocklist) from Jason's real preferences file."""
    if not CANDIDATE_PREFS_PATH.exists():
        return [], []
    with open(CANDIDATE_PREFS_PATH, encoding="utf-8") as f:
        prefs = json.load(f)
    title_terms: set[str] = set()
    for key in ("blocked_titles", "blocked_role_titles", "blocked_focus_area_words"):
        for term in prefs.get(key, []) or []:
            title_terms.add(str(term).strip().lower())
    industry_terms = {str(t).strip().lower() for t in prefs.get("blocked_industries", []) or []}
    return sorted(title_terms), sorted(industry_terms)


def title_is_relevant(title: str, title_blocklist: list[str]) -> bool:
    lower = title.lower()
    if any(b in lower for b in title_blocklist):
        return False
    return bool(PRODUCT_MANAGER_FAMILY_TITLE.search(title)) or any(t in lower for t in OTHER_TERMS)


def is_plausible_company_token(token: str) -> bool:
    """Common Crawl harvesting picks up throwaway/demo ATS accounts alongside real employers —
    a token that's all digits is almost always an auto-generated trial account, not a company."""
    return not token.isdigit()


def company_looks_blocked(token: str, titles: list[str], industry_blocklist: list[str]) -> bool:
    haystack = f"{token} {' '.join(titles)}".lower()
    return any(term in haystack for term in industry_blocklist)


def load_progress() -> dict:
    if PROGRESS_PATH.exists():
        with open(PROGRESS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"greenhouse": 0, "lever": 0, "ashby": 0}


def save_progress(progress: dict) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)


def fetch_json(url: str) -> object | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            time.sleep(RATE_LIMIT_BACKOFF_SECONDS)
        return None
    except Exception:
        return None


def existing_url_strings(conn: sqlite3.Connection) -> set[str]:
    cur = conn.execute("SELECT url_string FROM companies")
    return {row[0] for row in cur.fetchall()}


def scan_ats(
    ats: str,
    limit: int,
    title_blocklist: list[str],
    industry_blocklist: list[str],
    conn: sqlite3.Connection,
    progress: dict,
) -> dict:
    config = ATS_CONFIG[ats]
    seed_path = SEED_DIR / config["seed_file"]
    if not seed_path.exists():
        print(f"[{ats}] seed file missing: {seed_path} — skipping. See script docstring to download it.")
        return {"checked": 0, "added": 0}

    with open(seed_path, encoding="utf-8") as f:
        candidates = json.load(f)

    start = progress.get(ats, 0)
    known_urls = existing_url_strings(conn)
    checked = 0
    added = 0
    idx = start

    while idx < len(candidates) and checked < limit:
        token = candidates[idx]
        idx += 1
        checked += 1
        url = config["url"](token)
        if url in known_urls or not is_plausible_company_token(token):
            continue

        data = fetch_json(config["api"](token))
        time.sleep(REQUEST_DELAY_SECONDS)
        if data is None:
            continue

        try:
            titles = config["extract_titles"](data)
        except Exception:
            continue

        if len(titles) < MIN_POSTINGS_ON_BOARD:
            continue
        if company_looks_blocked(token, titles, industry_blocklist):
            continue

        relevant = [t for t in titles if title_is_relevant(t, title_blocklist)]
        if relevant:
            conn.execute(
                "INSERT INTO companies (company_name, url_string, ATS_name) VALUES (?, ?, ?)",
                (token, url, config["ats_name"]),
            )
            conn.commit()
            added += 1
            print(f"[{ats}] + {token} ({len(relevant)} matching posting(s), e.g. {relevant[0]!r})")

        if checked % 100 == 0:
            print(f"[{ats}] checked {checked}/{limit} this run (candidate {idx}/{len(candidates)} overall)")

    progress[ats] = idx
    return {"checked": checked, "added": added}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=300, help="Max candidates to check PER ATS this run")
    parser.add_argument("--ats", choices=list(ATS_CONFIG), help="Only scan this ATS (default: all three)")
    parser.add_argument("--status", action="store_true", help="Print progress and exit without scanning")
    args = parser.parse_args()

    progress = load_progress()

    if args.status:
        for ats, config in ATS_CONFIG.items():
            seed_path = SEED_DIR / config["seed_file"]
            total = len(json.load(open(seed_path, encoding="utf-8"))) if seed_path.exists() else 0
            print(f"{ats}: {progress.get(ats, 0)}/{total} candidates scanned")
        return

    if not OPENPOSTINGS_DB.exists():
        print(f"OpenPostings db not found at {OPENPOSTINGS_DB} — nothing to do.")
        sys.exit(1)

    title_blocklist, industry_blocklist = load_blocklist_terms()
    ats_list = [args.ats] if args.ats else list(ATS_CONFIG)

    conn = sqlite3.connect(OPENPOSTINGS_DB)
    totals = {"checked": 0, "added": 0}
    try:
        for ats in ats_list:
            result = scan_ats(ats, args.limit, title_blocklist, industry_blocklist, conn, progress)
            totals["checked"] += result["checked"]
            totals["added"] += result["added"]
    finally:
        save_progress(progress)
        conn.close()

    print(f"\nTotal this run: checked {totals['checked']}, added {totals['added']} new companies.")
    print("Progress saved — re-run the same command to continue from where this left off.")


if __name__ == "__main__":
    main()
