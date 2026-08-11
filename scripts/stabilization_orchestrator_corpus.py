#!/usr/bin/env python3
"""Practice-mode orchestrator smoke across a small corpus.

For each slug:
  1. run_until_waiting_for_llm (or adopt + continue) in practice mode
  2. If Resume.md + CoverLetter.md already exist, attempt --resume through
     Stage 2 until WAITING_FOR_HUMAN or Stage 2 COMPLETE / stop.

Does not call finalize against the production DB (practice mode).
Writes data/reports/stabilization_orchestrator_2026-08-11.json
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from unittest import mock

_SCRIPT_DIR = Path(__file__).resolve().parent
_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_SCRIPT_DIR))

from workflow.runner import (  # noqa: E402
    WorkflowError,
    run_until_truth_settled,
    run_until_waiting_for_llm,
)
from workflow.state import load_state  # noqa: E402
import contracts  # noqa: E402

CORPUS = [
    "relativity",          # Tier 1 clean
    "central_bank",        # Tier 2 soft gaps
    "camunda",             # Tier 2 tooling soft
    "ncontracts",          # extraction_override
    "common_room",         # recently fixed Zoom noise
    "leaflink",            # recently fixed soft gap
    "amplify",             # expected Skip (Smartsheet)
    "test_co",             # expected Skip (thin)
]


def _has_docs(folder: Path) -> bool:
    return (folder / "Resume.md").exists() and (folder / "CoverLetter.md").exists()


def _auto_dispose_open_findings(folder: Path) -> int:
    """Fill null disposition slots from on-disk findings. Returns count filled."""
    disp_path = folder / "reviews" / "dispositions.json"
    if not disp_path.exists():
        return 0
    disp = json.loads(disp_path.read_text(encoding="utf-8"))
    by_id = disp.setdefault("by_finding_id", {})
    findings_by_id: dict = {}
    for name in (
        "truth_findings.json",
        "ats_findings.json",
        "hm_findings.json",
        "mech_findings.json",
    ):
        fp = folder / "reviews" / name
        if not fp.exists():
            continue
        doc = json.loads(fp.read_text(encoding="utf-8"))
        for f in doc.get("findings") or []:
            if f.get("id"):
                findings_by_id[f["id"]] = f
    for fid in findings_by_id:
        by_id.setdefault(fid, None)
    filled = 0
    for fid, cur in list(by_id.items()):
        if cur:
            continue
        sev = str((findings_by_id.get(fid) or {}).get("severity") or "WARN").upper()
        by_id[fid] = (
            "HUMAN_ACCEPTED_RISK" if sev == "BLOCK" else "ACCEPTED_AS_CORRECT"
        )
        filled += 1
    if filled:
        disp_path.write_text(json.dumps(disp, indent=2) + "\n", encoding="utf-8")
    return filled


def _status_snapshot(folder: Path) -> dict:
    out: dict = {"has_docs": _has_docs(folder)}
    state_path = folder / "workflow_state.json"
    if not state_path.exists():
        out["wf"] = None
        return out
    state = json.loads(state_path.read_text(encoding="utf-8"))
    out["wf"] = state.get("status")
    out["mode"] = state.get("mode")
    out["active"] = state.get("active_stage")
    s2 = (state.get("stages") or {}).get("stage2") or {}
    out["stage2"] = s2.get("status")
    subs = s2.get("subphases") or {}
    out["subphases"] = {k: (v or {}).get("status") for k, v in subs.items()}
    ok, errs = contracts.check_workflow_complete(str(folder))
    out["workflow_complete"] = ok
    out["workflow_complete_errors"] = errs[:5]
    return out


def main() -> int:
    rows = []
    novel = []
    sub_root = _ROOT / "data" / "submissions"

    for slug in CORPUS:
        folder = sub_root / slug
        row: dict = {"slug": slug}
        if not folder.exists():
            row["error"] = "missing"
            rows.append(row)
            continue

        try:
            # Stage 0 → packet → WAITING_FOR_LLM (practice)
            # force=True: practice corpus may rewrite an existing production mode
            # so finalize cannot silently hit the jobs DB mid-pressure-test.
            state = run_until_waiting_for_llm(
                str(folder),
                mode="practice",
                adopt=True,
                force=True,
                no_hook=True,
            )
            row["after_waiting"] = state.get("status")
            row["tier"] = ((state.get("stages") or {}).get("stage0") or {}).get("result_tier")
            # Prefer gate file for tier
            gate_path = folder / "stage0_fit_gate.json"
            if gate_path.exists():
                gate = json.loads(gate_path.read_text(encoding="utf-8"))
                row["tier"] = gate.get("tier")
                row["decision"] = gate.get("decision")
        except WorkflowError as e:
            row["waiting_error"] = str(e)[:300]
            # Skip is a valid terminal for Stage 0
            if "Skip" in str(e) or "SKIP" in str(e):
                row["after_waiting"] = "SKIPPED"
            else:
                novel.append({"slug": slug, "class": "CRITICAL", "msg": row["waiting_error"]})
            rows.append({**row, **_status_snapshot(folder)})
            continue
        except Exception as e:
            row["waiting_error"] = f"{type(e).__name__}: {e}"
            novel.append({"slug": slug, "class": "CRITICAL", "msg": row["waiting_error"]})
            traceback.print_exc()
            rows.append({**row, **_status_snapshot(folder)})
            continue

        if row.get("after_waiting") == "SKIPPED" or row.get("tier") == "Skip":
            rows.append({**row, **_status_snapshot(folder)})
            continue

        if not _has_docs(folder):
            row["stage2"] = "no_docs_stop_at_waiting"
            rows.append({**row, **_status_snapshot(folder)})
            continue

        # Ensure provenance stub exists so Truth can run
        prov = folder / "claim_provenance.json"
        if not prov.exists():
            row["stage2_note"] = "missing claim_provenance.json — Stage 1 validate may fail"
            # Don't invent provenance; record as Major process gap if docs exist without it
            novel.append(
                {
                    "slug": slug,
                    "class": "MAJOR",
                    "msg": "docs exist without claim_provenance.json",
                }
            )
            rows.append({**row, **_status_snapshot(folder)})
            continue

        try:
            # First resume observes natural WAITING_FOR_HUMAN (Truth/ATS/HM each may wait).
            state = run_until_truth_settled(
                str(folder),
                mode="practice",
                adopt=True,
                force=True,
                stop_at_waiting=True,
                no_hook=True,
                compile_pdfs=False,
            )
            row["after_resume"] = state.get("status")
            row["snapshot"] = _status_snapshot(folder)

            # Multi-cycle dispose: each Stage 2 phase can stop independently, so one
            # fill+resume is not enough to reach Stage 2 COMPLETE.
            dispose_cycles = 0
            while state.get("status") == "WAITING_FOR_HUMAN" and dispose_cycles < 6:
                filled = _auto_dispose_open_findings(folder)
                if not filled:
                    break
                dispose_cycles += 1
                state = run_until_truth_settled(
                    str(folder),
                    mode="practice",
                    adopt=True,
                    force=True,
                    stop_at_waiting=True,
                    no_hook=True,
                    compile_pdfs=False,
                )
            if dispose_cycles:
                row["dispose_cycles"] = dispose_cycles
                row["after_dispose_resume"] = state.get("status")
                row["snapshot"] = _status_snapshot(folder)
        except WorkflowError as e:
            row["stage2_error"] = str(e)[:400]
            # verify-only / stage1 failures are Major (validation), not always Critical
            novel.append({"slug": slug, "class": "MAJOR", "msg": row["stage2_error"]})
        except Exception as e:
            row["stage2_error"] = f"{type(e).__name__}: {e}"
            novel.append({"slug": slug, "class": "CRITICAL", "msg": row["stage2_error"]})
            traceback.print_exc()

        rows.append({**row, **_status_snapshot(folder)})

    out = {
        "corpus": CORPUS,
        "novel_or_failures": novel,
        "rows": rows,
    }
    out_path = _ROOT / "data" / "reports" / "stabilization_orchestrator_2026-08-11.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")
    print(f"Novel/failure signals: {len(novel)}")
    for n in novel:
        print(f"  [{n['class']}] {n['slug']}: {n['msg'][:200]}")
    print("---")
    for r in rows:
        print(
            f"{r['slug']:28} wait={str(r.get('after_waiting')):18} "
            f"resume={str(r.get('after_resume') or r.get('after_dispose_resume') or r.get('stage2') or '-'):22} "
            f"wf={r.get('wf')}"
        )
    return 1 if any(n["class"] == "CRITICAL" for n in novel) else 0


if __name__ == "__main__":
    raise SystemExit(main())
