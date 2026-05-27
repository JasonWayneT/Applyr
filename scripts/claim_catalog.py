"""
Parse workExperience.md Sections 3–5 into structured claims.

Implements FR-100 (CR-017).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from utils import WORK_EXP_FILE, load_file

ACC_LINE = re.compile(
    r"^\*\s+\*\*\[(ACC-\d+)\]\s*([^*]+)\*\*:\s*(.+?)\s*$",
    re.MULTILINE,
)
VOC_ROW = re.compile(
    r"\|\s*\*\*(VOC-\d+)\*\*\s*\|\s*\*\*([^*]+)\*\*\s*\|\s*([^|]+?)\s*\|",
)
ANTI_CLAIM = re.compile(r"DO NOT\s+(.+?)\*", re.IGNORECASE)

BOUNDARY_PHRASES = [
    "airo",
    "zenoti",
    "led a team of",
    "managed a team of",
    "direct reports",
    "people management",
    "trained model",
    "machine learning pipeline",
    "0-to-1 greenfield",
]


@dataclass
class ClaimRecord:
    claim_id: str
    title: str
    body: str
    employer: str


@dataclass
class ClaimCatalog:
    claims: Dict[str, ClaimRecord] = field(default_factory=dict)
    voc_map: Dict[str, str] = field(default_factory=dict)
    anti_claim_hints: List[str] = field(default_factory=list)
    raw_truth_lines: Dict[str, str] = field(default_factory=dict)

    def truth_map(self) -> Dict[str, str]:
        out = dict(self.raw_truth_lines)
        for cid, rec in self.claims.items():
            out[cid] = f"* **[{cid}] {rec.title}**: {rec.body}"
        return out


def _employer_for_acc(claim_id: str) -> str:
    if claim_id.startswith("ACC-2"):
        return "sterkly"
    if claim_id.startswith("ACC-3"):
        return "zero_to_sixty"
    return "cision"


def load_catalog(path: Optional[str] = None) -> ClaimCatalog:
    path = path or WORK_EXP_FILE
    content = load_file(path)
    catalog = ClaimCatalog()

    for m in ACC_LINE.finditer(content):
        cid, title, body = m.group(1), m.group(2).strip(), m.group(3).strip()
        catalog.claims[cid] = ClaimRecord(
            claim_id=cid,
            title=title,
            body=body,
            employer=_employer_for_acc(cid),
        )
        catalog.raw_truth_lines[cid] = m.group(0).strip()

    for m in VOC_ROW.finditer(content):
        _vid, internal, plain = m.group(1), m.group(2).strip(), m.group(3).strip()
        if internal and plain:
            catalog.voc_map[internal] = plain

    for m in ANTI_CLAIM.finditer(content):
        hint = m.group(1).strip()
        if len(hint) > 10:
            catalog.anti_claim_hints.append(hint)

    id_pat = re.compile(r"(ACC-\d+|MET-\d+|VOC-\d+)")
    for line in content.splitlines():
        for mid in id_pat.findall(line):
            if mid not in catalog.raw_truth_lines and mid.startswith("MET-"):
                catalog.raw_truth_lines[mid] = line.strip()

    return catalog


def apply_voc_map(text: str, catalog: ClaimCatalog) -> str:
    out = text
    for internal, plain in sorted(catalog.voc_map.items(), key=lambda x: -len(x[0])):
        if internal in out:
            out = out.replace(internal, plain)
        bold = f"**{internal}**"
        if bold in out:
            out = out.replace(bold, plain)
    return out


def sanitize_claim_text(text: str, catalog: ClaimCatalog) -> str:
    clean = re.sub(r"\[(ACC|MET|VOC)-\d+\]", "", text)
    clean = re.sub(r"\*+", "", clean).strip()
    clean = apply_voc_map(clean, catalog)
    for phrase in BOUNDARY_PHRASES:
        if phrase.lower() in clean.lower():
            clean = re.sub(re.escape(phrase), "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+", " ", clean).strip()
    if clean and not clean.endswith("."):
        clean += "."
    return clean
