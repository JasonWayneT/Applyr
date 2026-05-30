"""Light verification for Document Editor saves (CR-031 / FR-177).

Full verify_content requires claim-ID tags; editor markdown is stripped.
This path uses corpus numeric audit + hard-fact warnings + tone guard.
"""
from __future__ import annotations

import json
import os
from typing import Tuple

from claim_catalog import load_catalog
from drafting_engine import validate_hard_facts
from local_draft_stages import audit_text_against_bullet_corpus
from quality_checker import HEADER_BLOCK
from tone_guard import tone_violations
from utils import RESUME_MASTER_FILE, load_file
from verification_chain import _enforce_strict_warnings


def verify_editor_save(
    text: str,
    filename: str,
    folder: str,
) -> Tuple[bool, str]:
    if not text or not text.strip():
        return False, "Empty document"

    catalog = load_catalog()
    corpus = "\n".join(catalog.raw_truth_lines.values()) if catalog.claims else ""
    manifest_path = os.path.join(folder, "draft_manifest.json")
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            sources = manifest.get("claim_sources") or {}
            if sources:
                corpus = corpus + "\n" + "\n".join(sources.values())
        except Exception:
            pass

    if not corpus.strip():
        return False, "No claim corpus available for verification"

    ok, err = audit_text_against_bullet_corpus(text, f"{corpus}\n{HEADER_BLOCK}")
    if not ok:
        return False, err or "Numeric audit failed"

    master = load_file(RESUME_MASTER_FILE)
    doc_type = "cover_letter" if "cover" in filename.lower() else "resume"
    _, warnings = validate_hard_facts(text, master, doc_type=doc_type)
    try:
        _enforce_strict_warnings(warnings)
    except ValueError as exc:
        return False, str(exc)

    hits = tone_violations(text)
    if hits:
        return False, f"Forbidden tone (FR-096): {', '.join(sorted(set(hits)))}"

    return True, ""


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 4:
        print("Usage: verify_editor_save.py <folder> <filename> (reads stdin)")
        raise SystemExit(2)
    folder, filename = sys.argv[1], sys.argv[2]
    body = sys.stdin.read()
    ok, msg = verify_editor_save(body, filename, folder)
    if ok:
        print("OK")
        raise SystemExit(0)
    print(msg)
    raise SystemExit(1)
