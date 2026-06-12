"""Candidate-specific context from profile, workExperience.md, and master_claims."""
from __future__ import annotations

import os
import re
from typing import Dict, List, Tuple

from utils import WORK_EXP_FILE, format_contact_header_block, load_identity_profile

DEFAULT_EMPLOYER_SLUGS: Tuple[str, ...] = ("acme_corp", "example_inc", "startup_co")

DEFAULT_EMPLOYER_HEADERS: Dict[str, str] = {
    "acme_corp": "### Product Manager | Acme Corp | September 2021 - January 2026\nRemote\n",
    "example_inc": "### Product Manager | Example Inc | February 2019 - August 2021\nCity, State\n",
    "startup_co": "### Product Owner | Startup Co | June 2017 - January 2019\nCity, State\n",
}

DEFAULT_EDUCATION_BLOCK = (
    "## EDUCATION\n\n"
    "* **Bachelor of Business Administration** — Example University, City, State, 2019\n"
)


def employer_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_") or "employer"


def load_work_experience_text() -> str:
    if os.path.exists(WORK_EXP_FILE):
        with open(WORK_EXP_FILE, encoding="utf-8") as f:
            return f.read()
    return ""


def parse_company_names(text: str) -> List[str]:
    pattern = re.compile(r"^## \*\*(.+?)\*\*", re.MULTILINE)
    return [m.group(1).strip() for m in pattern.finditer(text or "")]


def parse_experience_headers(text: str) -> Dict[str, str]:
    """Map employer slug -> first ### experience header block line(s)."""
    headers: Dict[str, str] = {}
    current_slug: str | None = None
    for line in (text or "").splitlines():
        company = re.match(r"^## \*\*(.+?)\*\*", line)
        if company:
            current_slug = employer_slug(company.group(1))
            headers.setdefault(current_slug, "")
            continue
        if current_slug and line.startswith("### ") and not headers[current_slug]:
            headers[current_slug] = line + "\n"
    return {k: v for k, v in headers.items() if v}


def load_employer_headers() -> Dict[str, str]:
    from claim_catalog import load_catalog

    catalog = load_catalog()
    catalog_slugs = sorted({rec.employer for rec in catalog.claims.values() if rec.employer})
    parsed = parse_experience_headers(load_work_experience_text())
    merged = dict(DEFAULT_EMPLOYER_HEADERS)
    merged.update(parsed)
    for slug in catalog_slugs:
        if slug not in merged:
            label = slug.replace("_", " ").title()
            merged[slug] = f"### Product Manager | {label}\n"
    if catalog_slugs:
        return {slug: merged[slug] for slug in catalog_slugs if slug in merged}
    if parsed:
        return merged
    return dict(DEFAULT_EMPLOYER_HEADERS)


def load_employers() -> Tuple[str, ...]:
    from claim_catalog import load_catalog

    catalog = load_catalog()
    slugs = sorted({rec.employer for rec in catalog.claims.values() if rec.employer})
    if slugs:
        return tuple(slugs)
    parsed = tuple(parse_experience_headers(load_work_experience_text()).keys())
    if parsed:
        return parsed
    return DEFAULT_EMPLOYER_SLUGS


def primary_employer_slug() -> str:
    ordered = load_employers_ordered()
    return ordered[0] if ordered else "acme_corp"


def employer_tiers() -> Tuple[str, str, str]:
    """Most-recent, mid-career, and earliest employer slugs (senior → junior)."""
    ordered = load_employers_ordered()
    senior = ordered[0] if ordered else "acme_corp"
    mid = ordered[1] if len(ordered) > 1 else "example_inc"
    junior = ordered[2] if len(ordered) > 2 else "startup_co"
    return senior, mid, junior


def company_matches_employer_slug(company: str, slug: str) -> bool:
    """True when a resume header company label matches an employer slug."""
    if not company or not slug:
        return False
    labels = {
        employer_display_name(slug).lower(),
        slug.replace("_", " ").lower(),
        slug.lower(),
    }
    return company.strip().lower() in labels or employer_slug(company) == slug


def load_employers_ordered() -> Tuple[str, ...]:
    """Most recent employer first (ACC-1xx before ACC-2xx before ACC-3xx convention)."""
    employers = list(load_employers())

    def sort_key(slug: str) -> tuple:
        if slug.startswith("acme") or "cision" in slug:
            return (0, slug)
        if slug.startswith("example") or "sterkly" in slug:
            return (1, slug)
        if slug.startswith("startup") or "zero" in slug:
            return (2, slug)
        return (3, slug)

    return tuple(sorted(employers, key=sort_key))


def employer_for_claim_id(claim_id: str) -> str:
    from claim_catalog import load_catalog

    catalog = load_catalog()
    rec = catalog.claims.get(claim_id)
    if rec and rec.employer:
        return rec.employer
    if claim_id.startswith("ACC-2"):
        return "example_inc"
    if claim_id.startswith("ACC-3"):
        return "startup_co"
    if claim_id.startswith("ACC-1"):
        return "acme_corp"
    ordered = load_employers_ordered()
    return ordered[0] if ordered else "acme_corp"


def default_resume_bullet_quotas() -> Dict[str, int]:
    ordered = load_employers_ordered()
    if not ordered:
        return {"acme_corp": 5, "example_inc": 3, "startup_co": 3}
    quotas: Dict[str, int] = {}
    for i, slug in enumerate(ordered):
        quotas[slug] = 5 if i == 0 else 3
    return quotas


def parse_education_block(text: str) -> str:
    lines: List[str] = []
    in_education = False
    for line in (text or "").splitlines():
        if re.match(r"^##\s+education\b", line, re.I):
            in_education = True
            lines.append("## EDUCATION")
            continue
        if in_education and re.match(r"^##\s+", line):
            break
        if in_education and line.strip():
            lines.append(line)
    if lines:
        return "\n".join(lines).strip() + "\n"
    return DEFAULT_EDUCATION_BLOCK.strip() + "\n"


def employer_display_name(slug: str, headers: Dict[str, str] | None = None) -> str:
    headers = headers or load_employer_headers()
    header = headers.get(slug, "")
    m = re.search(r"\|\s*([^|]+?)\s*\|", header)
    if m:
        return m.group(1).strip()
    return slug.replace("_", " ").title()


def employer_names_in_text(text: str) -> List[str]:
    names = []
    headers = load_employer_headers()
    for slug in load_employers():
        names.append(employer_display_name(slug, headers).lower())
        names.append(slug.replace("_", " "))
    return [n for n in names if n]


def build_contact_header(profile: dict | None = None) -> str:
    return format_contact_header_block(profile or load_identity_profile())
