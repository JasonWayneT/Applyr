#!/usr/bin/env python3
"""CR-112 Story 1.4 — read-only detector for wiped claim_constraints packets.

Flags authoring_packet.json files that shipped ready with an empty
claim_constraints fence while still carrying evidence_map or soft_gaps.
Does not rewrite submissions.

Inspection outcomes (mutually reported, never collapsed into a clean scan):
  clean: every packet was readable and none were flagged (exit 0)
  flagged: inspection finished and at least one wiped packet was found (exit 1)
  incomplete: a packet or root could not be inspected (exit 2)

An existing empty root may report zero inspected. That is not evidence of
safety. A missing root is incomplete, not a successful empty scan.

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

EXIT_CLEAN = 0
EXIT_FLAGGED = 1
EXIT_INCOMPLETE = 2


def constraints_empty(constraints: Any) -> bool:
    return constraints is None or constraints == {}


def _constraint_count(constraints: Any) -> int:
    if constraints_empty(constraints):
        return 0
    if isinstance(constraints, dict):
        return len(constraints)
    raise TypeError("claim_constraints is not an object")


def _list_len(value: Any, field: str) -> int:
    if value is None:
        return 0
    if isinstance(value, list):
        return len(value)
    raise TypeError(f"{field} is not a list")


def is_wiped_constraints_packet(packet: dict[str, Any]) -> bool:
    """True when a ready packet dropped claim_constraints but still has evidence.

    Implements FR-298 / AC-395. Callers must pass a dict. Invalid nested
    field types raise TypeError so scan_packets can record an inspect error
    instead of aborting the rest of the root.
    """
    if packet.get("packet_status") != "ready":
        _list_len(packet.get("evidence_map"), "evidence_map")
        _list_len(packet.get("soft_gaps"), "soft_gaps")
        _constraint_count(packet.get("claim_constraints"))
        return False
    if not constraints_empty(packet.get("claim_constraints")):
        _constraint_count(packet.get("claim_constraints"))
        _list_len(packet.get("evidence_map"), "evidence_map")
        _list_len(packet.get("soft_gaps"), "soft_gaps")
        return False
    evidence_n = _list_len(packet.get("evidence_map"), "evidence_map")
    soft_n = _list_len(packet.get("soft_gaps"), "soft_gaps")
    return bool(evidence_n) or bool(soft_n)


def _error_row(slug: str | None, path: str, error: str) -> dict[str, Any]:
    return {
        "slug": slug,
        "path": path,
        "error": error,
        "flagged": False,
        "inspect_ok": False,
    }


def scan_packets(root: Path) -> list[dict[str, Any]]:
    """Scan one level of folders for authoring_packet.json. Read-only.

    A missing or non-directory root yields one inspect-error row, not an
    empty successful scan. One malformed packet does not stop the others.
    """
    findings: list[dict[str, Any]] = []
    if not root.is_dir():
        return [_error_row(None, str(root), "root is not a directory")]
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        packet_path = folder / "authoring_packet.json"
        if not packet_path.is_file():
            continue
        try:
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            findings.append(
                _error_row(folder.name, str(packet_path), f"unreadable packet: {exc}")
            )
            continue
        if not isinstance(packet, dict):
            findings.append(
                _error_row(folder.name, str(packet_path), "packet is not an object")
            )
            continue
        try:
            constraints = packet.get("claim_constraints")
            constraint_count = _constraint_count(constraints)
            evidence_map_rows = _list_len(packet.get("evidence_map"), "evidence_map")
            soft_gap_rows = _list_len(packet.get("soft_gaps"), "soft_gaps")
            flagged = is_wiped_constraints_packet(packet)
        except TypeError as exc:
            findings.append(_error_row(folder.name, str(packet_path), str(exc)))
            continue
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
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                disposition = {"error": "unreadable disposition sidecar"}
        findings.append(
            {
                "slug": folder.name,
                "path": str(packet_path),
                "packet_status": packet.get("packet_status"),
                "constraint_count": constraint_count,
                "estimated_tokens": packet.get("estimated_tokens"),
                "evidence_map_rows": evidence_map_rows,
                "soft_gap_rows": soft_gap_rows,
                "flagged": flagged,
                "inspect_ok": True,
                "disposition": disposition,
            }
        )
    return findings


def format_report(findings: list[dict[str, Any]]) -> str:
    inspected = [row for row in findings if row.get("inspect_ok")]
    errors = [row for row in findings if row.get("inspect_ok") is False]
    flagged = [row for row in inspected if row.get("flagged")]
    lines = [
        f"Inspected {len(inspected)} packet(s); flagged {len(flagged)}; "
        f"unable-to-inspect {len(errors)}.",
        "Flag: packet_status=ready and claim_constraints empty/missing "
        "while evidence_map or soft_gaps is non-empty.",
        "Read-only. Do not rebuild here. A packet_integrity_disposition.json "
        "sidecar is informational and is not authorization.",
        "",
    ]
    if not findings:
        lines.append("Inspected 0 packets. This is not evidence of safety.")
        return "\n".join(lines)
    if errors:
        lines.append("Unable to inspect:")
        for row in errors:
            label = row.get("slug") or row.get("path")
            lines.append(f"  - {label}: {row.get('error')}")
        lines.append("Incomplete inspection. This is not a clean scan.")
        lines.append("")
    if flagged:
        lines.append("Affected folders:")
        for row in flagged:
            lines.append(
                f"  - {row['slug']}: status={row.get('packet_status')} "
                f"constraints={row.get('constraint_count')} "
                f"estimated_tokens={row.get('estimated_tokens')} "
                f"evidence_map={row.get('evidence_map_rows')} "
                f"soft_gaps={row.get('soft_gap_rows')}"
                + (
                    (
                        f" sidecar_error={row['disposition'].get('error')}"
                        f" (informational; not authorization)"
                        if "error" in row["disposition"]
                        else (
                            f" sidecar_verdict={row['disposition'].get('verdict', 'recorded')}"
                            f" (informational; not authorization)"
                        )
                    )
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
    elif not errors:
        lines.append("No wiped-constraint ready packets found.")
    return "\n".join(lines)


def classify_findings(findings: list[dict[str, Any]]) -> int:
    if any(row.get("inspect_ok") is False for row in findings):
        return EXIT_INCOMPLETE
    if any(row.get("flagged") for row in findings):
        return EXIT_FLAGGED
    return EXIT_CLEAN


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
    return classify_findings(findings)


if __name__ == "__main__":
    sys.exit(main())
