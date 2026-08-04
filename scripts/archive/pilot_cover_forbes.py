#!/usr/bin/env python3
# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""Pilot CR-024 cover engine on Forbes submission (FR-097)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cover_letter_compiler import compile_cover_letter, write_cover_bundle
from utils import PROJECT_ROOT

FORBES_DIR = os.path.join(PROJECT_ROOT, "data", "submissions", "forbes")


def main() -> int:
    jd_path = os.path.join(FORBES_DIR, "Original_JD.txt")
    if not os.path.exists(jd_path):
        print(f"Missing {jd_path}")
        return 1

    with open(jd_path, encoding="utf-8") as f:
        jd_text = f.read()

    research = os.path.join(FORBES_DIR, "Research_Packet.json")
    result = compile_cover_letter(
        jd_text,
        company_display="Forbes",
        research_packet_path=research if os.path.exists(research) else None,
    )

    write_cover_bundle(FORBES_DIR, result)

    print(f"Wrote {FORBES_DIR}/CoverLetter.md")
    print(f"Plan: {FORBES_DIR}/cover_letter_plan.json")
    print(f"Audit: {result.audit_grade} (score={result.audit_score}) words={result.word_count}")
    if result.audit_issues:
        print("Issues:", "; ".join(result.audit_issues))
    print("\n--- Preview (first 1200 chars) ---\n")
    print(result.markdown[:1200])
    if result.audit_grade != "Pass":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
