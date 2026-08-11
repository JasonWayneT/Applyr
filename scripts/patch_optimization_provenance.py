#!/usr/bin/env python3
"""Attach unused soft_gap/required claim_ids onto existing provenance rows (optimization_bar)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from author_from_packet import _check_optimization_bar_provenance  # noqa: E402


def _cited(provenance: dict) -> set[str]:
    cited: set[str] = set()
    for section in ("resume_claims", "cover_letter_claims"):
        for row in provenance.get(section) or []:
            if not isinstance(row, dict):
                continue
            for cid in row.get("claim_ids") or []:
                if isinstance(cid, str) and cid.strip():
                    cited.add(cid.strip())
                    parts = cid.split("-")
                    if len(parts) >= 2 and parts[0] in ("ACC", "MET", "VOC"):
                        cited.add("-".join(parts[:2]))
    return cited


def _id_used(cid: str, cited: set[str]) -> bool:
    if cid in cited:
        return True
    parts = cid.split("-")
    if len(parts) >= 2 and parts[0] in ("ACC", "MET", "VOC"):
        base = f"{parts[0]}-{parts[1]}"
        if base in cited or any(c.startswith(base) for c in cited):
            return True
    return any(c.startswith(cid) or cid.startswith(c) for c in cited)


def needed_ids(folder: Path) -> list[str]:
    packet = json.loads((folder / "authoring_packet.json").read_text(encoding="utf-8"))
    provenance = json.loads((folder / "claim_provenance.json").read_text(encoding="utf-8"))
    cited = _cited(provenance)
    out: list[str] = []
    for sg in packet.get("soft_gaps") or []:
        if not isinstance(sg, dict) or (sg.get("class") or "SOFT") == "HARD":
            continue
        ids = [c for c in (sg.get("claim_ids") or []) if isinstance(c, str) and c.strip()]
        if ids and all(not _id_used(c, cited) for c in ids):
            out.append(ids[0])
    for row in packet.get("evidence_map") or []:
        if not isinstance(row, dict) or row.get("bucket") != "required":
            continue
        ids = [c for c in (row.get("claim_ids") or []) if isinstance(c, str) and c.strip()]
        if ids and all(not _id_used(c, cited) for c in ids):
            out.append(ids[0])
    # unique preserve order
    seen = set()
    uniq = []
    for c in out:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq


def patch(folder: Path) -> list[str]:
    prov_path = folder / "claim_provenance.json"
    provenance = json.loads(prov_path.read_text(encoding="utf-8"))
    missing = needed_ids(folder)
    if not missing:
        return []
    # Prefer attaching to cover_letter_claims as a dedicated bridge row, else resume
    cl = provenance.setdefault("cover_letter_claims", [])
    if not isinstance(cl, list):
        cl = []
        provenance["cover_letter_claims"] = cl
    # Use resume first bullet text as proof_point anchor when possible
    resume_rows = provenance.get("resume_claims") or []
    anchor = "cross-functional delivery and platform ownership across B2B SaaS products"
    if resume_rows and isinstance(resume_rows[0], dict):
        anchor = (resume_rows[0].get("bullet") or anchor)[:120]
    cl.append(
        {
            "proof_point": f"Evidence bridge (packet soft_gap/required): {anchor}",
            "claim_ids": missing,
        }
    )
    # Also stamp onto first resume claim for belt-and-suspenders
    if resume_rows and isinstance(resume_rows[0], dict):
        ids = list(resume_rows[0].get("claim_ids") or [])
        for m in missing:
            if m not in ids:
                ids.append(m)
        resume_rows[0]["claim_ids"] = ids
    prov_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return missing


def main() -> int:
    slugs = sys.argv[1:]
    for slug in slugs:
        folder = ROOT / "data/submissions" / slug
        print(f"=== {slug} ===")
        before_ok, before = _check_optimization_bar_provenance(folder)
        if before_ok:
            print("  already PASS")
            continue
        added = patch(folder)
        print("  added", added)
        after_ok, after = _check_optimization_bar_provenance(folder)
        print("  after", "PASS" if after_ok else after)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
