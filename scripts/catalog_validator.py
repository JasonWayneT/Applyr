"""
Catalog ↔ workExperience validation and anti-claim loading (CR-031 / FR-175).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from approved_metrics import APPROVED_METRICS
from utils import DATA_DIR, WORK_EXP_FILE
from voc_map import contains_voc_codename, find_voc_codenames

MASTER_CLAIMS_FILE = os.path.join(DATA_DIR, "master_claims.json")
MASTER_CLAIMS_EXAMPLE = os.path.join(DATA_DIR, "master_claims.example.json")
WORK_EXP_EXAMPLE = os.path.join(DATA_DIR, "workExperience.example.md")

ACC_RE = re.compile(r"ACC-\d+", re.I)
ANTI_LINE_RE = re.compile(
    r"(?:^|\b)(?:ANTI:|DO\s+NOT\s+claim|do\s+not\s+claim)\s*[:\-]?\s*(.+)$",
    re.I | re.M,
)

# Forbidden in catalog *text* — word-boundary phrases, not bare "manager".
FORBIDDEN_CATALOG_PHRASES = [
    r"\bmanaged a team\b",
    r"\bled a team\b",
    r"\bdirect reports\b",
    r"\bpeople management\b",
    r"\bvice president\b",
    r"\bhead of product\b",
]


@dataclass
class CatalogValidationResult:
    ok: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def resolve_master_claims_path(path: Optional[str] = None) -> str:
    if path and os.path.isfile(path):
        return path
    if os.path.isfile(MASTER_CLAIMS_FILE):
        return MASTER_CLAIMS_FILE
    return MASTER_CLAIMS_EXAMPLE


def resolve_work_experience_path(path: Optional[str] = None) -> str:
    if path and os.path.isfile(path):
        return path
    if os.path.isfile(WORK_EXP_FILE):
        return WORK_EXP_FILE
    return WORK_EXP_EXAMPLE


def load_anti_claim_hints(work_exp_path: Optional[str] = None) -> List[str]:
    path = resolve_work_experience_path(work_exp_path)
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    hints: List[str] = []
    for line in content.splitlines():
        m = ANTI_LINE_RE.search(line.strip())
        if m:
            hint = m.group(1).strip().strip('"').strip("'")
            if len(hint) >= 8:
                hints.append(hint)
    return hints


def _load_truth_map(work_exp_path: str) -> Dict[str, str]:
    from verify_claims import load_valid_ids

    return load_valid_ids(work_exp_path)


def _acc_prefix(claim_id: str) -> Optional[str]:
    m = ACC_RE.search(claim_id or "")
    return m.group(0).upper() if m else None


def validate_catalog(
    claims_path: Optional[str] = None,
    work_exp_path: Optional[str] = None,
) -> CatalogValidationResult:
    cpath = resolve_master_claims_path(claims_path)
    wpath = resolve_work_experience_path(work_exp_path)
    result = CatalogValidationResult(ok=True)

    if not os.path.isfile(cpath):
        result.ok = False
        result.errors.append(f"Missing claims file: {cpath}")
        return result

    with open(cpath, "r", encoding="utf-8") as f:
        claims = json.load(f)

    truth = _load_truth_map(wpath) if os.path.isfile(wpath) else {}
    approved_lower = {a.lower().replace(",", "") for a in APPROVED_METRICS}

    for cid, val in claims.items():
        text = (val.get("text") or "").strip()
        if not text:
            result.errors.append(f"{cid}: empty text")
            result.ok = False
            continue

        for pat in FORBIDDEN_CATALOG_PHRASES:
            if re.search(pat, text, re.I):
                result.errors.append(f"{cid}: forbidden phrase matched /{pat}/")
                result.ok = False

        if contains_voc_codename(text):
            hits = ", ".join(find_voc_codenames(text)[:3])
            result.errors.append(f"{cid}: internal VOC codename in claim text ({hits})")
            result.ok = False

        prefix = _acc_prefix(cid) or _acc_prefix(val.get("project_id", ""))
        acc_truth_keys = [k for k in truth if k.upper().startswith("ACC")]
        if acc_truth_keys and prefix:
            anchored = any(k.upper().startswith(prefix) for k in truth)
            if not anchored:
                result.errors.append(f"{cid}: no workExperience anchor for {prefix}")
                result.ok = False

        for metric in val.get("metrics") or []:
            mclean = str(metric).lower().replace("$", "").replace(",", "")
            if not any(mclean in al or al in mclean for al in approved_lower):
                result.errors.append(f"{cid}: metric '{metric}' not in approved list")
                result.ok = False

    return result


def validate_catalog_or_raise(
    claims_path: Optional[str] = None,
    work_exp_path: Optional[str] = None,
) -> CatalogValidationResult:
    result = validate_catalog(claims_path, work_exp_path)
    if not result.ok:
        raise ValueError("Catalog validation failed:\n" + "\n".join(result.errors[:20]))
    return result
