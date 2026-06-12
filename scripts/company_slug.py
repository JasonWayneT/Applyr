"""Shared company folder slug sanitization (CR-025)."""
from __future__ import annotations

import os
import re


def sanitize_company_slug(company: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (company or "").lower()).strip("_")
    if not slug:
        import hashlib
        slug = "company_" + hashlib.md5(company.encode("utf-8")).hexdigest()[:12]
    if not slug or ".." in slug or slug.startswith("."):
        raise ValueError(f"Invalid company name for folder slug: {company!r}")
    return slug


def company_submission_dir(base_dir: str, company: str) -> str:
    slug = sanitize_company_slug(company)
    folder = os.path.join(base_dir, slug)
    base_real = os.path.realpath(base_dir)
    folder_real = os.path.realpath(folder)
    if folder_real != base_real and not folder_real.startswith(base_real + os.sep):
        raise ValueError(f"Path traversal blocked for company: {company!r}")
    return folder
