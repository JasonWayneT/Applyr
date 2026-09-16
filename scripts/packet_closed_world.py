#!/usr/bin/env python3
"""CR-112 Story 3.1 — extra-packet provenance IDs (exact match only).

A cited claim_id is extra when it is not literally present in packet
excerpts, evidence_map.claim_ids, or soft_gaps.claim_ids. Project-prefix
match (ACC-101-SAVINGS vs ACC-101-PM) does not clear the check.

Findings are BLOCK (`truth.provenance.extra.<id>`), a Stage 1 completion
block. This module detects. It does not rank, recommend, or recover.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent


def packet_allowed_claim_ids(packet: dict[str, Any]) -> set[str]:
    allowed: set[str] = set()
    excerpts = packet.get("excerpts") or {}
    if isinstance(excerpts, dict):
        allowed.update(
            cid.strip() for cid in excerpts if isinstance(cid, str) and cid.strip()
        )
    for row in packet.get("evidence_map") or []:
        if not isinstance(row, dict):
            continue
        for cid in row.get("claim_ids") or []:
            if isinstance(cid, str) and cid.strip():
                allowed.add(cid.strip())
    for sg in packet.get("soft_gaps") or []:
        if not isinstance(sg, dict):
            continue
        for cid in sg.get("claim_ids") or []:
            if isinstance(cid, str) and cid.strip():
                allowed.add(cid.strip())
    return allowed


def provenance_cited_ids(provenance: dict[str, Any]) -> list[str]:
    cited: list[str] = []
    seen: set[str] = set()
    for section in ("resume_claims", "cover_letter_claims"):
        for row in provenance.get(section) or []:
            if not isinstance(row, dict):
                continue
            for cid in row.get("claim_ids") or []:
                if not isinstance(cid, str) or not cid.strip():
                    continue
                value = cid.strip()
                if value not in seen:
                    seen.add(value)
                    cited.append(value)
    return cited


def extra_packet_claim_ids(
    packet: dict[str, Any], provenance: dict[str, Any]
) -> list[str]:
    """Return cited IDs that are not exact members of the packet closed world."""
    allowed = packet_allowed_claim_ids(packet)
    return [cid for cid in provenance_cited_ids(provenance) if cid not in allowed]


def extra_packet_findings(
    packet: dict[str, Any], provenance: dict[str, Any]
) -> list[dict[str, str]]:
    """Implements FR-312 / AC-409. Detection only: no rank, recover, or widen."""
    findings: list[dict[str, str]] = []
    for cid in extra_packet_claim_ids(packet, provenance):
        findings.append(
            {
                "id": f"truth.provenance.extra.{cid}",
                "claim_id": cid,
                "severity": "BLOCK",
                "recovery_state": "UNRESOLVED",
            }
        )
    return findings


def scan_extra_packet_folders(root: Path) -> list[dict[str, Any]]:
    """Read-only extra-packet scan. Never rewrites Resume.md, packets, or provenance."""
    rows: list[dict[str, Any]] = []
    if not root.is_dir():
        return rows
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        packet_path = folder / "authoring_packet.json"
        prov_path = folder / "claim_provenance.json"
        if not packet_path.is_file() or not prov_path.is_file():
            continue
        try:
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            provenance = json.loads(prov_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            rows.append(
                {
                    "slug": folder.name,
                    "readable": False,
                    "extra_ids": [],
                    "finding_ids": [],
                }
            )
            continue
        if not isinstance(packet, dict) or not isinstance(provenance, dict):
            rows.append(
                {
                    "slug": folder.name,
                    "readable": False,
                    "extra_ids": [],
                    "finding_ids": [],
                }
            )
            continue
        findings = extra_packet_findings(packet, provenance)
        rows.append(
            {
                "slug": folder.name,
                "readable": True,
                "extra_ids": [row["claim_id"] for row in findings],
                "finding_ids": [row["id"] for row in findings],
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only scan for provenance IDs outside the packet closed world."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=_REPO_ROOT / "data" / "submissions",
        help="Directory of submission folders (read-only).",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    rows = scan_extra_packet_folders(args.root)
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
    else:
        print("slug\textra_ids")
        for row in rows:
            extras = ",".join(row["extra_ids"]) if row["extra_ids"] else "(none)"
            print(f"{row['slug']}\t{extras}")
        print("Read-only. Did not rewrite any folder.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
