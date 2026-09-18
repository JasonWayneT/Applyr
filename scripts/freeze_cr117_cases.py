#!/usr/bin/env python3
"""Freeze privacy-safe metadata for CR-117 pilot authoring cases."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "data" / "eval" / "cr117" / "frozen_inputs"
INPUTS = ("Original_JD.txt", "stage0_fit_gate.json", "authoring_packet.json", "authoring_prompt.md")
MODEL_CONFIG = {"provider": "agy", "model": "gemini-3.8-flash-medium", "transport": "agy_headless_pilot"}


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inspect_cases(root: Path, digest_path: Path) -> dict:
    """Validate case inputs and return hashes, never source text."""
    if not root.is_dir():
        raise ValueError(f"Case root missing: {root}")
    digest = digest_path.read_bytes()
    rows = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        missing = [name for name in INPUTS if not (folder / name).is_file()]
        if missing:
            raise ValueError(f"{folder.name}: missing {', '.join(missing)}")
        gate = json.loads((folder / "stage0_fit_gate.json").read_text(encoding="utf-8"))
        packet = json.loads((folder / "authoring_packet.json").read_text(encoding="utf-8"))
        if gate.get("decision") != "PASS" or packet.get("packet_status") != "ready":
            raise ValueError(f"{folder.name}: Stage 0 PASS and ready packet required")
        if not packet.get("excerpts") or not packet.get("claim_constraints"):
            raise ValueError(f"{folder.name}: missing evidence excerpts or claim constraints")
        if packet.get("incomplete_reasons"):
            raise ValueError(f"{folder.name}: ready packet has incomplete reasons")
        hashes = {name: _hash_bytes((folder / name).read_bytes()) for name in INPUTS}
        rows.append({
            "slug": folder.name,
            "split": "holdout" if folder.name.startswith("holdout_") else "pilot",
            "hashes": hashes,
            "packet_estimated_tokens": packet.get("estimated_tokens"),
        })
    if not rows:
        raise ValueError("No cases found")
    config_bytes = json.dumps(MODEL_CONFIG, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "schema_version": "1.0",
        "status": "frozen",
        "digest_sha256": _hash_bytes(digest),
        "model_config": MODEL_CONFIG,
        "model_config_sha256": _hash_bytes(config_bytes),
        "cases": rows,
    }


def verify_existing(path: Path, current: dict, *, refresh: bool = False) -> bool:
    """Return True if a new snapshot should be written; reject quiet drift."""
    if not path.exists():
        return True
    frozen = json.loads(path.read_text(encoding="utf-8"))
    if frozen == current:
        return False
    if not refresh:
        raise ValueError("Frozen case inputs changed; inspect the diff before using --refresh")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--refresh", action="store_true", help="Replace a changed snapshot after review")
    args = parser.parse_args()
    cases = args.cases.resolve()
    eval_root = (ROOT / "data" / "eval").resolve()
    if not cases.is_relative_to(eval_root):
        parser.error("Case root must stay under gitignored data/eval")
    manifest = inspect_cases(cases, ROOT / "data" / "authoring_rule_digest.md")
    path = cases / "case_manifest.json"
    try:
        should_write = verify_existing(path, manifest, refresh=args.refresh)
    except ValueError as exc:
        parser.error(str(exc))
    if should_write:
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    splits = {name: sum(row["split"] == name for row in manifest["cases"]) for name in ("pilot", "holdout")}
    verb = "Frozen" if should_write else "Verified"
    print(f"{verb} {len(manifest['cases'])} cases ({splits['pilot']} pilot, {splits['holdout']} holdout): {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
