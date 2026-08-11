"""Stage 2 review findings + dispositions (CR-079+).

Reviewers / mechanical collectors write findings under reviews/.
Only the orchestrator (via this module + receipts.write_state) updates
workflow_state subphase status. Reviewers never write stage_receipts.
"""
from __future__ import annotations

import json
import os
import tempfile
from typing import Any

from workflow.invalidate import sha256_hex_bytes
from workflow.state import utc_now

REVIEWS_DIR = "reviews"
TRUTH_FINDINGS = "truth_findings.json"
ATS_FINDINGS = "ats_findings.json"
HM_FINDINGS = "hm_findings.json"
DISPOSITIONS = "dispositions.json"

CLEAN_DISPOSITIONS = frozenset(
    {
        "RESOLVED_EDIT",
        "ACCEPTED_AS_CORRECT",
        "NOT_APPLICABLE",
        "FALSE_POSITIVE",
    }
)
OVERRIDE_DISPOSITIONS = frozenset({"HUMAN_ACCEPTED_RISK"})
ALL_DISPOSITIONS = CLEAN_DISPOSITIONS | OVERRIDE_DISPOSITIONS

BLOCKING_SEVERITIES = frozenset({"BLOCK"})


def reviews_dir(folder: str) -> str:
    return os.path.join(folder, REVIEWS_DIR)


def truth_findings_path(folder: str) -> str:
    return os.path.join(reviews_dir(folder), TRUTH_FINDINGS)


def ats_findings_path(folder: str) -> str:
    return os.path.join(reviews_dir(folder), ATS_FINDINGS)


def hm_findings_path(folder: str) -> str:
    return os.path.join(reviews_dir(folder), HM_FINDINGS)


def dispositions_path(folder: str) -> str:
    return os.path.join(reviews_dir(folder), DISPOSITIONS)


def _atomic_write_json(path: str, data: dict[str, Any]) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".rev_", suffix=".json", dir=parent or None)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_truth_findings(folder: str, payload: dict[str, Any]) -> str:
    """Orchestrator-owned write of aggregated Truth findings (not a stage receipt)."""
    path = truth_findings_path(folder)
    _atomic_write_json(path, payload)
    return path


def write_ats_findings(folder: str, payload: dict[str, Any]) -> str:
    """Orchestrator-owned write of aggregated ATS findings (not a stage receipt)."""
    path = ats_findings_path(folder)
    _atomic_write_json(path, payload)
    return path


def write_hm_findings(folder: str, payload: dict[str, Any]) -> str:
    """Orchestrator-owned write of aggregated HM findings (not a stage receipt)."""
    path = hm_findings_path(folder)
    _atomic_write_json(path, payload)
    return path


def load_truth_findings(folder: str) -> dict[str, Any] | None:
    path = truth_findings_path(folder)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{TRUTH_FINDINGS} is not a JSON object")
    return data


def load_ats_findings(folder: str) -> dict[str, Any] | None:
    path = ats_findings_path(folder)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{ATS_FINDINGS} is not a JSON object")
    return data


def load_dispositions(folder: str) -> dict[str, Any]:
    path = dispositions_path(folder)
    if not os.path.exists(path):
        return {
            "schema_version": 1,
            "by_finding_id": {},
            "bound_findings_hashes": {},
        }
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{DISPOSITIONS} is not a JSON object")
    by_id = data.get("by_finding_id")
    if not isinstance(by_id, dict):
        by_id = {}
    bound = data.get("bound_findings_hashes")
    if not isinstance(bound, dict):
        bound = {}
    return {
        "schema_version": data.get("schema_version", 1),
        "by_finding_id": by_id,
        "bound_findings_hashes": bound,
        "note": data.get("note"),
        "updated_at": data.get("updated_at"),
    }


def _write_dispositions(
    folder: str,
    by_id: dict[str, Any],
    bound_hashes: dict[str, Any],
) -> str:
    payload = {
        "schema_version": 1,
        "updated_at": utc_now(),
        "by_finding_id": by_id,
        "bound_findings_hashes": bound_hashes,
        "note": (
            "Set each finding_id to one of: RESOLVED_EDIT, ACCEPTED_AS_CORRECT, "
            "NOT_APPLICABLE, FALSE_POSITIVE, HUMAN_ACCEPTED_RISK. "
            "Dispositions are bound to the findings content hash for each review "
            "phase (truth/ats/hm/mech); a regenerated finding with the same id but "
            "different content clears that disposition automatically. "
            "Then re-run: python scripts/run_submission.py {slug} --resume"
        ),
    }
    path = dispositions_path(folder)
    _atomic_write_json(path, payload)
    return path


def ensure_dispositions_stub(folder: str, finding_ids: list[str]) -> str:
    """Create or extend dispositions.json with null slots for open findings (human fills)."""
    current = load_dispositions(folder)
    by_id = dict(current.get("by_finding_id") or {})
    bound = dict(current.get("bound_findings_hashes") or {})
    changed = False
    for fid in finding_ids:
        if fid not in by_id:
            by_id[fid] = None
            changed = True
    if changed or not os.path.exists(dispositions_path(folder)):
        return _write_dispositions(folder, by_id, bound)
    return dispositions_path(folder)


def sync_dispositions_for_phase(
    folder: str,
    phase: str,
    findings_doc: dict[str, Any],
) -> dict[str, Any]:
    """Ensure disposition slots exist and invalidate stale ones for this review phase.

    Invariant: a human disposition only applies to the findings payload it was made
    against. ``findings_content_hash`` is stored per phase under
    ``bound_findings_hashes``. If the current findings hash differs from the bound
    hash, every disposition for finding ids in the current payload is cleared to
    null so Stage 2 cannot COMPLETE on a review of different content.

    Same-hash re-runs keep dispositions (the normal --resume after Jason fills them).
    """
    if phase not in ("truth", "ats", "hm", "mech"):
        raise ValueError(f"sync_dispositions_for_phase: unknown phase {phase!r}")

    finding_ids = [
        str(f["id"]) for f in (findings_doc.get("findings") or []) if isinstance(f, dict) and f.get("id")
    ]
    fhash = findings_content_hash(findings_doc)
    current = load_dispositions(folder)
    by_id = dict(current.get("by_finding_id") or {})
    bound = dict(current.get("bound_findings_hashes") or {})
    prev = bound.get(phase)
    changed = False

    for fid in finding_ids:
        if fid not in by_id:
            by_id[fid] = None
            changed = True

    if prev is not None and prev != fhash:
        for fid in finding_ids:
            if by_id.get(fid) is not None:
                by_id[fid] = None
                changed = True

    if bound.get(phase) != fhash:
        bound[phase] = fhash
        changed = True

    if changed or not os.path.exists(dispositions_path(folder)):
        _write_dispositions(folder, by_id, bound)

    return load_dispositions(folder)


def findings_content_hash(findings: dict[str, Any]) -> str:
    canonical = json.dumps(
        findings.get("findings") or [],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return sha256_hex_bytes(canonical.encode("utf-8"))


def default_stage2_subphases() -> dict[str, Any]:
    return {
        "truth": {"status": "LOCKED"},
        "ats": {"status": "LOCKED"},
        "hm": {"status": "LOCKED"},
        "mech": {"status": "LOCKED"},
        "policy": {"status": "LOCKED"},
    }


def ensure_stage2_subphases(state: dict[str, Any]) -> dict[str, Any]:
    """Mutate-copy: ensure stage2.subphases exists."""
    from copy import deepcopy

    out = deepcopy(state)
    s2 = out.setdefault("stages", {}).setdefault(
        "stage2",
        {"status": "LOCKED", "receipt_id": None, "integrity": "CLEAN"},
    )
    if "subphases" not in s2 or not isinstance(s2.get("subphases"), dict):
        s2["subphases"] = default_stage2_subphases()
    else:
        for name, default in default_stage2_subphases().items():
            s2["subphases"].setdefault(name, dict(default))
    return out
