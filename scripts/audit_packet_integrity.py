#!/usr/bin/env python3
"""CR-112 Story 1.4 — read-only detector for wiped claim_constraints packets.

Flags authoring_packet.json files that shipped ready with an empty
claim_constraints fence while still carrying evidence_map or soft_gaps.
Does not rewrite submissions.

Usage:
  python scripts/audit_packet_integrity.py
  python scripts/audit_packet_integrity.py --root data/submissions
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
_DEFAULT_ROOT = _REPO_ROOT / "data" / "submissions"


def constraints_empty(constraints: Any) -> bool:
    return constraints is None or constraints == {}


def is_wiped_constraints_packet(packet: dict[str, Any]) -> bool:
    """True when a ready packet dropped claim_constraints but still has evidence.

    Implements FR-298 / AC-395.
    """
    if packet.get("packet_status") != "ready":
        return False
    if not constraints_empty(packet.get("claim_constraints")):
        return False
    evidence = packet.get("evidence_map") or []
    soft_gaps = packet.get("soft_gaps") or []
    return bool(evidence) or bool(soft_gaps)


def scan_packets(root: Path) -> list[dict[str, Any]]:
    """Scan one level of folders for authoring_packet.json. Read-only."""
    findings: list[dict[str, Any]] = []
    if not root.is_dir():
        return findings
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        packet_path = folder / "authoring_packet.json"
        if not packet_path.is_file():
            continue
        try:
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            findings.append(
                {
                    "slug": folder.name,
                    "path": str(packet_path),
                    "error": f"unreadable packet: {exc}",
                    "flagged": False,
                }
            )
            continue
        if not isinstance(packet, dict):
            findings.append(
                {
                    "slug": folder.name,
                    "path": str(packet_path),
                    "error": "packet is not an object",
                    "flagged": False,
                }
            )
            continue
        constraints = packet.get("claim_constraints")
        constraint_count = 0 if constraints_empty(constraints) else len(constraints)
        # Display-only. This sidecar is never authorization: it does not
        # clear flagged, does not satisfy Stage 2, and is not read by
        # run_submission.py. Stage 2 HUMAN_ACCEPTED_RISK lives in
        # reviews/dispositions.json, a different file.
        disposition_path = folder / "packet_integrity_disposition.json"
        disposition = None
        if disposition_path.is_file():
            try:
                loaded = json.loads(disposition_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    disposition = loaded
            except (OSError, json.JSONDecodeError):
                disposition = {"error": "unreadable disposition sidecar"}
        row = {
            "slug": folder.name,
            "path": str(packet_path),
            "packet_status": packet.get("packet_status"),
            "constraint_count": constraint_count,
            "estimated_tokens": packet.get("estimated_tokens"),
            "evidence_map_rows": len(packet.get("evidence_map") or []),
            "soft_gap_rows": len(packet.get("soft_gaps") or []),
            "flagged": is_wiped_constraints_packet(packet),
            "disposition": disposition,
        }
        findings.append(row)
    return findings


def format_report(findings: list[dict[str, Any]]) -> str:
    flagged = [row for row in findings if row.get("flagged")]
    lines = [
        f"Scanned {len(findings)} packet(s); flagged {len(flagged)}.",
        "Flag: packet_status=ready and claim_constraints empty/missing "
        "while evidence_map or soft_gaps is non-empty.",
        "Read-only. Do not rebuild here. A packet_integrity_disposition.json "
        "sidecar is informational and is not authorization.",
        "",
    ]
    if not flagged:
        lines.append("No wiped-constraint ready packets found.")
        return "\n".join(lines)
    lines.append("Affected folders:")
    for row in flagged:
        lines.append(
            f"  - {row['slug']}: status={row.get('packet_status')} "
            f"constraints={row.get('constraint_count')} "
            f"estimated_tokens={row.get('estimated_tokens')} "
            f"evidence_map={row.get('evidence_map_rows')} "
            f"soft_gaps={row.get('soft_gap_rows')}"
            + (
                f" sidecar_verdict={row['disposition'].get('verdict', 'recorded')}"
                f" (informational; not authorization)"
                if isinstance(row.get("disposition"), dict)
                else ""
            )
        )
    lines.append("")
    lines.append(
        "A flagged packet stays flagged until the generator is fixed and the "
        "packet is rebuilt by an explicit request. Do not treat a sidecar "
        "as human authorization. Do not solicit risk acceptance here."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Detect ready authoring packets with empty claim_constraints."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=_DEFAULT_ROOT,
        help="Directory of submission folders (default: data/submissions)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable findings instead of the text report.",
    )
    args = parser.parse_args(argv)
    findings = scan_packets(args.root)
    if args.json:
        print(json.dumps(findings, indent=2))
    else:
        print(format_report(findings))
    flagged = sum(1 for row in findings if row.get("flagged"))
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
