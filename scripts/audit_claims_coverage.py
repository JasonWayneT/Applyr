"""
CR-088: mechanical WE <-> master_claims coverage audit.
CR-094: only story-class ACC ids must have a claims project_id. Attribution
and DO NOT CLAIM brackets are fields on the preceding story, not accomplishments.

ERROR tier (fails --strict / unit test):
  - claim id ACC prefix != project_id
  - project_id not in workExperience.md ACC inventory and not in SIDE_CORPUS
  - story-class WE ACC missing from claims (except ALLOW_NO_CLAIM)

WARN tier (printed; does not fail default exit):
  - high-risk project missing attribution or prohibited_claims on a lens

Usage:
  python scripts/audit_claims_coverage.py
  python scripts/audit_claims_coverage.py --strict
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any

import we_acc_index as wai

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)

# ACC-401 lives in data/aiProjects.md, not WE Approved Accomplishments.
SIDE_CORPUS_PROJECT_IDS = frozenset({"ACC-401"})

# Tools inventory — skills_catalog.json path (CLAIMS_STANDARD.md).
ALLOW_NO_CLAIM = frozenset({"ACC-119"})

# Claude R16 / CR-088 P4 priority set (plus siblings often needing hedges).
HIGH_RISK_PROJECT_IDS = frozenset(
    {
        "ACC-111",
        "ACC-113",
        "ACC-114",
        "ACC-115",
        "ACC-120",
        "ACC-121",
        "ACC-169",
        "ACC-172",
        "ACC-204",
        "ACC-211",
        "ACC-401",
    }
)

_ACC_RE = re.compile(r"ACC-\d+")
_BRACKET_ACC_RE = re.compile(r"\[(ACC-\d+)\]")


def _load_we_acc_ids(we_path: str) -> set[str]:
    with open(we_path, encoding="utf-8") as f:
        text = f.read()
    return set(_BRACKET_ACC_RE.findall(text))


def _claim_prefix(claim_id: str) -> str | None:
    m = re.match(r"(ACC-\d+)", claim_id)
    return m.group(1) if m else None


def audit(
    claims: dict[str, Any],
    we_acc: set[str],
    *,
    we_text: str = "",
    side_corpus: frozenset[str] = SIDE_CORPUS_PROJECT_IDS,
    allow_no_claim: frozenset[str] = ALLOW_NO_CLAIM,
    high_risk: frozenset[str] = HIGH_RISK_PROJECT_IDS,
) -> dict[str, list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    warns: list[dict[str, str]] = []
    claimed_projects: set[str] = set()

    for claim_id, entry in claims.items():
        if entry.get("disabled"):
            continue
        pid = str(entry.get("project_id") or "")
        prefix = _claim_prefix(claim_id)
        if not pid:
            errors.append({"code": "missing_project_id", "claim_id": claim_id, "detail": "no project_id"})
            continue
        if not _ACC_RE.fullmatch(pid):
            errors.append(
                {"code": "bad_project_id", "claim_id": claim_id, "detail": f"project_id={pid!r}"}
            )
            continue
        claimed_projects.add(pid)
        if prefix and prefix != pid:
            errors.append(
                {
                    "code": "miskey",
                    "claim_id": claim_id,
                    "detail": f"prefix {prefix} != project_id {pid}",
                }
            )
        if pid not in we_acc and pid not in side_corpus:
            errors.append(
                {
                    "code": "phantom_project",
                    "claim_id": claim_id,
                    "detail": f"{pid} not in WE and not in side corpus",
                }
            )

        if pid in high_risk:
            if not entry.get("attribution"):
                warns.append(
                    {
                        "code": "missing_attribution",
                        "claim_id": claim_id,
                        "detail": f"high-risk {pid} has no attribution",
                    }
                )
            if not entry.get("prohibited_claims"):
                warns.append(
                    {
                        "code": "missing_prohibited",
                        "claim_id": claim_id,
                        "detail": f"high-risk {pid} has no prohibited_claims",
                    }
                )

    story_ids = wai.indexable_project_ids(we_text) if we_text else set(we_acc)
    for acc in sorted(story_ids):
        if acc in allow_no_claim:
            continue
        if acc not in claimed_projects:
            errors.append(
                {
                    "code": "we_unclaimed",
                    "claim_id": "",
                    "detail": f"{acc} in WE has no master_claims project_id",
                }
            )

    return {"errors": errors, "warns": warns}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 when ERROR-tier findings exist (default: print and exit 0).",
    )
    args = parser.parse_args(argv)

    claims_path = os.path.join(_REPO_ROOT, "data", "master_claims.json")
    we_path = os.path.join(_REPO_ROOT, "data", "workExperience.md")
    with open(claims_path, encoding="utf-8") as f:
        claims = json.load(f)
    with open(we_path, encoding="utf-8") as f:
        we_text = f.read()
    we_acc = _load_we_acc_ids(we_path)
    result = audit(claims, we_acc, we_text=we_text)

    for e in result["errors"]:
        print(f"ERROR {e['code']}: {e.get('claim_id') or '-'} — {e['detail']}")
    for w in result["warns"]:
        print(f"WARN  {w['code']}: {w.get('claim_id') or '-'} — {w['detail']}")

    print(
        f"summary: {len(result['errors'])} error(s), {len(result['warns'])} warn(s); "
        f"WE ACC={len(we_acc)}, claims={len(claims)}"
    )

    if args.strict and result["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
