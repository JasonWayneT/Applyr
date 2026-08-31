"""Hash helpers and cascade invalidation (CR-076/077)."""
from __future__ import annotations

import hashlib
import os
from copy import deepcopy
from typing import Any, Mapping


def sha256_file(path: str) -> str | None:
    """Return sha256 hex of file bytes, or None if missing."""
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def sha256_hex_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hashes_match(folder: str, expected: Mapping[str, str]) -> tuple[bool, list[str]]:
    """Compare relative paths under folder to expected sha256 hex digests."""
    errors: list[str] = []
    for rel, want in expected.items():
        path = os.path.join(folder, rel)
        got = sha256_file(path)
        if got is None:
            errors.append(f"{rel} missing (expected hash {want[:12]}...)")
        elif got != want:
            errors.append(f"{rel} hash mismatch (stale vs receipt)")
    return len(errors) == 0, errors


# Downstream stages that become invalid when an earlier stage goes STALE.
_CASCADE: dict[str, tuple[str, ...]] = {
    "stage0": ("stage1", "stage2", "stage3"),
    "stage1": ("stage2", "stage3"),
    "stage2": ("stage3",),
    "stage3": (),
}

_PREV_STAGE: dict[str, str] = {
    "stage1": "stage0",
    "stage2": "stage1",
    "stage3": "stage2",
}


def reconcile_state_against_receipts(
    folder: str,
    state: dict[str, Any],
    load_receipt_fn,
) -> tuple[dict[str, Any], list[str]]:
    """Mark stages STALE when receipt output_hashes no longer match disk.

    Returns (possibly updated state, list of human-readable reasons).
    Does not write — caller persists via receipts.write_state.
    """
    out = deepcopy(state)
    reasons: list[str] = []
    stages = out.setdefault("stages", {})

    for stage in ("stage0", "stage1", "stage2", "stage3"):
        info = stages.get(stage) or {}
        receipt_id = info.get("receipt_id")
        status = info.get("status")
        if not receipt_id or status in (None, "LOCKED", "READY", "RUNNING", "FAILED"):
            continue
        if status in ("STALE",):
            continue

        receipt = load_receipt_fn(folder, stage)
        if not receipt:
            reasons.append(f"{stage}: state points at receipt_id but file missing → STALE")
            stages[stage] = {
                "status": "STALE",
                "receipt_id": receipt_id,
                "integrity": info.get("integrity") or "CLEAN",
            }
            for down in _CASCADE.get(stage, ()):
                d = stages.get(down) or {}
                if d.get("status") not in ("LOCKED", None):
                    stages[down] = {
                        "status": "LOCKED" if down != "stage1" else "LOCKED",
                        "receipt_id": d.get("receipt_id"),
                        "integrity": d.get("integrity") or "CLEAN",
                    }
                    reasons.append(f"{down}: locked after {stage} receipt missing")
            continue

        expected = receipt.get("output_hashes") or {}
        if expected:
            ok, errs = hashes_match(folder, expected)
            if not ok:
                reasons.extend(f"{stage}: {e}" for e in errs)
                stages[stage] = {
                    "status": "STALE",
                    "receipt_id": receipt_id,
                    "integrity": info.get("integrity") or "CLEAN",
                }
                for down in _CASCADE.get(stage, ()):
                    d = stages.get(down) or {}
                    # Lock downstream even if they had COMPLETE/READY/WAITING
                    if d.get("status") and d.get("status") != "LOCKED":
                        stages[down] = {
                            "status": "LOCKED",
                            "receipt_id": None,
                            "integrity": d.get("integrity") or "CLEAN",
                        }
                        if down == "stage2":
                            # CR-079: restart Stage 2 from Truth after upstream STALE
                            from workflow.reviews import default_stage2_subphases

                            stages[down]["subphases"] = default_stage2_subphases()
                        reasons.append(f"{down}: LOCKED after {stage} became STALE")
                continue

        # Chain-integrity check: if this stage's prior_receipt_id doesn't match
        # the previous stage's current receipt_id, the chain is broken (an
        # earlier stage was re-run after this stage was already complete).
        # Mark this stage STALE so it gets re-validated against the new upstream.
        prior_id = receipt.get("prior_receipt_id")
        if prior_id and stage != "stage0":
            prev_stage = _PREV_STAGE.get(stage)
            if prev_stage:
                prev_info = stages.get(prev_stage) or {}
                prev_receipt_id = prev_info.get("receipt_id")
                if prev_receipt_id and prior_id != prev_receipt_id:
                    reasons.append(
                        f"{stage}: prior_receipt_id {prior_id[:20]}... "
                        f"does not match {prev_stage} receipt_id "
                        f"{prev_receipt_id[:20]}... (broken chain)"
                    )
                    stages[stage] = {
                        "status": "STALE",
                        "receipt_id": receipt_id,
                        "integrity": info.get("integrity") or "CLEAN",
                    }
                    for down in _CASCADE.get(stage, ()):
                        d = stages.get(down) or {}
                        if d.get("status") and d.get("status") != "LOCKED":
                            stages[down] = {
                                "status": "LOCKED",
                                "receipt_id": None,
                                "integrity": d.get("integrity") or "CLEAN",
                            }
                            if down == "stage2":
                                from workflow.reviews import default_stage2_subphases

                                stages[down]["subphases"] = default_stage2_subphases()
                            reasons.append(f"{down}: LOCKED after {stage} chain broken")

    if reasons:
        out["status"] = "STALE"
        # Point active stage at earliest stale
        for stage in ("stage0", "stage1", "stage2", "stage3"):
            if (stages.get(stage) or {}).get("status") == "STALE":
                out["active_stage"] = stage
                break

    return out, reasons
