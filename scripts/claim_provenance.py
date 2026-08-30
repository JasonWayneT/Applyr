"""
Claim-provenance validation: does every drafted claim trace to a real Fact ID?

Why this exists (2026-08-06): workExperience.md Section 6.1 has said, since before this session,
that "AI models generating materials for Jason Taylor MUST... verify that every single fact,
metric, and responsibility traces back to a Fact ID" -- but nothing has ever mechanically checked
this. Every existing guard catches a specific WRONG thing (an unapproved number, a forbidden
tool, a mismatched attribution verb); none of them force the author to show its sourcing as it
writes. This is the difference between catching hallucination after the fact and making it
structurally harder to produce in the first place -- the author has to name a real ID for every
claim, and a fabricated or disabled ID fails mechanically, the same way a fabricated number
already does via approved_metrics.py.

This does NOT verify that a cited claim actually semantically supports what the bullet says --
that still needs a real read (same limitation check_ground_truth_coverage.py already has, and
for the same reason: a script can't verify judgment, only existence). What it DOES catch for
free: a citation to an ID that doesn't exist anywhere in ground truth (fabricated), and a
citation to an ID that exists but is explicitly disabled (e.g. ACC-114-COST) -- both currently
invisible to every other check in this pipeline.

Expected artifact shape -- claim_provenance.json in the submission folder:
    {
      "company": "...",
      "resume_claims": [
        {"bullet": "first several words or full text of the bullet", "claim_ids": ["ACC-104", "MET-10"]},
        ...
      ],
        "cover_letter_claims": [
            {"sentence": "...", "claim_ids": ["ACC-117"]}
        ]
    }
    Older artifacts may use ``proof_point`` instead of ``sentence``.  Both
    labels are accepted so Truth review remains compatible with the newer
    sentence-level contract.
Claim IDs may be either master_claims.json's own keys (e.g. "ACC-101-TECH") or the coarser
base IDs used in workExperience.md's bracket notation and CLAUDE.md's MET table (e.g. "ACC-101",
"MET-05") -- both forms are valid, matching how the two ground-truth docs actually cite things.

Usage:
    python scripts/claim_provenance.py data/submissions/{company} [...]
        Exits 1 if the file is missing, malformed, or cites any unknown/disabled claim ID.

Also importable:
    load_valid_claim_ids() -> (valid: set[str], disabled: set[str])
    check_claim_provenance(folder) -> (ok, errors)
"""
from __future__ import annotations

import json
import os
import re
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)
_MASTER_CLAIMS_PATH = os.path.join(_REPO_ROOT, "data", "master_claims.json")
_WORK_EXPERIENCE_PATH = os.path.join(_REPO_ROOT, "data", "workExperience.md")

# Not bracket-only: confirmed by direct inspection (2026-08-06) that ACC IDs appear bracketed
# ("[ACC-101]") but MET IDs appear as a bold markdown table cell ("**MET-01**") or bare in prose
# ("MET-01 $40M ARR") -- workExperience.md Section 6.1's own description of the format ("All IDs
# (`[ACC-101]`, `[MET-01]`, etc.)") turned out not to match how MET IDs are actually written.
# Matching the bare token everywhere covers both real forms without requiring brackets.
_ID_PATTERN = re.compile(r"\b((?:ACC|MET|VOC)-[0-9A-Za-z-]+)\b")


def _read_master_claims() -> dict:
    """Load master_claims.json or {} if missing."""
    if not os.path.exists(_MASTER_CLAIMS_PATH):
        return {}
    with open(_MASTER_CLAIMS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def _read_work_experience() -> str:
    """Load workExperience.md or empty string if missing. Caller must not log PII."""
    if not os.path.exists(_WORK_EXPERIENCE_PATH):
        return ""
    with open(_WORK_EXPERIENCE_PATH, encoding="utf-8") as f:
        return f.read()


def load_valid_claim_ids() -> tuple[set, set]:
    """Returns (valid_ids, disabled_ids). valid_ids is the union of master_claims.json's own
    keys, their project_id base forms, and every ACC-xxx/MET-xxx/VOC-xxx token found anywhere
    in workExperience.md -- both ID granularities real ground truth actually uses.

    CR-094: Attribution / DO NOT CLAIM / tools ACC tokens in WE are not citable
    accomplishments. Subtract them so a draft cannot "cover" a DNC line by citing it.
    """
    import we_acc_index as wai

    valid: set = set()
    disabled: set = set()

    claims = _read_master_claims()
    enabled_projects: set = set()
    disabled_only_projects: set = set()
    for key, entry in claims.items():
        if not isinstance(entry, dict):
            continue
        valid.add(key)
        project_id = entry.get("project_id")
        if project_id:
            valid.add(project_id)
        if entry.get("disabled"):
            disabled.add(key)
            if project_id:
                disabled_only_projects.add(project_id)
        elif project_id:
            enabled_projects.add(project_id)
    for pid in disabled_only_projects:
        if pid not in enabled_projects:
            disabled.add(pid)

    we_text = _read_work_experience()
    if we_text:
        valid |= set(_ID_PATTERN.findall(we_text))
        valid -= wai.non_story_acc_ids(we_text)

    return valid, disabled


def check_claim_provenance(folder: str) -> tuple[bool, list[str]]:
    path = os.path.join(folder, "claim_provenance.json")
    if not os.path.exists(path):
        return False, ["claim_provenance.json not found"]
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return False, [f"claim_provenance.json could not be read/parsed: {e}"]
    if not isinstance(data, dict):
        return False, ["claim_provenance.json is not a JSON object"]

    errors: list[str] = []
    if not data.get("company"):
        errors.append("claim_provenance.json: missing or empty 'company'")

    valid_ids, disabled_ids = load_valid_claim_ids()

    for section, item_label in (("resume_claims", "bullet"), ("cover_letter_claims", "sentence")):
        entries = data.get(section)
        if not isinstance(entries, list):
            errors.append(f"claim_provenance.json: '{section}' must be a list")
            continue
        if not entries:
            errors.append(f"claim_provenance.json: '{section}' is empty -- a real document has at least one claim")
            continue
        for i, entry in enumerate(entries):
            if not isinstance(entry, dict):
                errors.append(f"claim_provenance.json: {section}[{i}] is not an object")
                continue
            # CR-103/CR-075 compatibility: Stage 1 now records the complete
            # factual sentence, while older provenance artifacts called the
            # same field ``proof_point``.  Prefer the current contract but
            # accept the legacy label during Truth validation.
            label = entry.get(item_label)
            if section == "cover_letter_claims" and not label:
                label = entry.get("proof_point")
            claim_ids = entry.get("claim_ids")
            if not label:
                expected = "'sentence' (or legacy 'proof_point')" if section == "cover_letter_claims" else f"'{item_label}'"
                errors.append(f"claim_provenance.json: {section}[{i}] missing {expected}")
            if not isinstance(claim_ids, list) or not claim_ids:
                errors.append(f"claim_provenance.json: {section}[{i}] ('{label}') has no claim_ids -- every claim needs at least one real Fact ID")
                continue
            for cid in claim_ids:
                if cid in disabled_ids:
                    errors.append(f"claim_provenance.json: {section}[{i}] ('{label}') cites DISABLED claim '{cid}' -- this claim is quarantined, do not use it")
                elif cid not in valid_ids:
                    errors.append(f"claim_provenance.json: {section}[{i}] ('{label}') cites unknown claim ID '{cid}' -- does not exist in master_claims.json or workExperience.md. Fabricated citation.")

    return len(errors) == 0, errors


def main() -> None:
    folders = sys.argv[1:]
    if not folders:
        print(__doc__)
        sys.exit(1)

    any_failed = False
    for folder in folders:
        folder = folder.rstrip("/\\")
        company = os.path.basename(folder)
        ok, errors = check_claim_provenance(folder)
        if ok:
            print(f"{company}: PASS -- every cited claim ID is real and active")
        else:
            any_failed = True
            print(f"{company}: FAIL")
            for e in errors:
                print(f"  - {e}")

    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()
