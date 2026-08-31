#!/usr/bin/env python3
"""Per-opportunity observability report — Epic C of the observability design
(docs/spec/08-implementation/OBSERVABILITY-DESIGN-2026-08-30-stage0-3-replay-reporting.md §5.2).

Reads across the artifacts that already exist for one submission folder (stage receipts, the
Stage 0 fit gate, Stage 2 findings/dispositions, Stage 1's verify_history.json) plus the new
observability/run_events.jsonl (when present -- older or not-yet-replayed submissions have none,
and this must degrade to a receipt-only view rather than error) and renders one human-readable
Markdown report, overwritten each time it's regenerated (unlike run_events.jsonl, which is
append-only evidence; this report is a current-state view of that evidence).

Usage:
    .venv\\Scripts\\python.exe scripts\\observability_report.py <slug-or-path>

Writes {folder}/observability/report.md and also prints it to stdout.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import contracts  # noqa: E402
from workflow.runner import _resolve_folder, WorkflowError  # noqa: E402
from workflow.receipts import load_receipt  # noqa: E402
from workflow.observability import read_events  # noqa: E402


def _load_json_safe(path: str) -> Any | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _rel(folder: str, name: str) -> str:
    """Relative path used in the report's own links (report.md lives in observability/)."""
    return f"../{name}"


def gather(folder: str) -> dict[str, Any]:
    """Collects everything the report needs. Every lookup degrades to None/[] rather than
    raising — a submission from before this instrumentation existed should still get a report,
    just a thinner one."""
    slug = os.path.basename(folder.rstrip("/\\"))
    try:
        complete, complete_errors = contracts.check_workflow_complete(folder)
    except Exception as exc:  # noqa: BLE001 — a broken folder must still get a report, not a crash
        complete, complete_errors = False, [f"check_workflow_complete raised: {exc}"]
    return {
        "slug": slug,
        "folder": folder,
        "check_workflow_complete": complete,
        "check_workflow_complete_errors": complete_errors,
        "workflow_state": _load_json_safe(os.path.join(folder, "workflow_state.json")),
        "receipts": {
            stage: load_receipt(folder, stage) for stage in ("stage0", "stage1", "stage2", "stage3")
        },
        "stage0_fit_gate": _load_json_safe(os.path.join(folder, "stage0_fit_gate.json")),
        "findings": {
            phase: _load_json_safe(os.path.join(folder, "reviews", f"{phase}_findings.json"))
            for phase in ("truth", "ats", "hm", "mech", "policy")
        },
        "dispositions": _load_json_safe(os.path.join(folder, "reviews", "dispositions.json")),
        "verify_history": _load_json_safe(
            os.path.join(folder, "stage1_first_draft", "verify_history.json")
        )
        or [],
        "events": read_events(folder),
    }


def _fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.0f}m"
    return f"{minutes / 60:.1f}h"


def _stage_row(data: dict[str, Any], stage_key: str, label: str) -> str:
    """One markdown table row for a single top-level stage (0/1/2/3), reading from the receipt
    first (always present if the stage ran at all) and falling back to nothing extra when no
    observability event exists yet for it."""
    receipt = data["receipts"].get(stage_key)
    if not receipt:
        return f"| {label} | not reached | — | — | — |"
    status = receipt.get("status", "?")
    result = receipt.get("result") or {}
    duration = _fmt_duration(result.get("duration_seconds"))
    notes_parts = []
    if stage_key == "stage0":
        notes_parts.append(f"tier={result.get('tier')}")
        notes_parts.append(f"reasons={'; '.join(result.get('reasons') or []) or 'none'}")
    elif stage_key == "stage1":
        if result.get("verify_attempts") is not None:
            notes_parts.append(f"verify attempts={result['verify_attempts']}")
    elif stage_key == "stage2":
        subphases = (result.get("subphases") or {})
        notes_parts.append(
            ", ".join(f"{k}={v.get('status')}" for k, v in subphases.items()) or "—"
        )
    elif stage_key == "stage3":
        notes_parts.append(f"company={result.get('company')!r}")
        notes_parts.append(f"reach_out={result.get('reach_out')}")
    notes = "; ".join(notes_parts) or "—"
    integrity = receipt.get("integrity", "CLEAN")
    integrity_note = "" if integrity == "CLEAN" else f" ⚠ integrity={integrity}"
    return f"| {label} | {status}{integrity_note} | {duration} | {notes} |"


def _events_summary(events: list[dict[str, Any]]) -> list[str]:
    """M2.3-style summary: needs_disposition -> resolution latency, plus retries/fallbacks."""
    lines: list[str] = []
    open_at: dict[str, str] = {}
    for e in events:
        stage = e.get("stage", "")
        if e.get("event") == "needs_disposition":
            open_at[stage] = e.get("timestamp", "")
        elif e.get("event") == "complete" and stage in open_at:
            lines.append(f"- `{stage}` reached NEEDS_DISPOSITION, then resolved (see run_events.jsonl for exact timestamps).")
            del open_at[stage]
    for stage in open_at:
        lines.append(f"- ⚠ `{stage}` is still at NEEDS_DISPOSITION as of the last recorded event — unresolved.")
    for e in events:
        if e.get("event") == "verify_failed":
            lines.append(
                f"- Stage 1 verify attempt {e.get('attempt')} failed ({_fmt_duration(e.get('duration_seconds'))})."
            )
        if e.get("stage") == "stage0" and e.get("extraction_source") == "llm":
            lines.append("- Stage 0 fell back to the LLM extraction path (free NLP path missed).")
    return lines


def render(data: dict[str, Any]) -> str:
    slug = data["slug"]
    gate = data["stage0_fit_gate"] or {}
    company = gate.get("company", slug)
    role = gate.get("role") or gate.get("role_title") or ""
    ws = data["workflow_state"] or {}

    lines: list[str] = []
    lines.append(f"# Observability Report — {slug}")
    lines.append("")
    header_bits = [b for b in (company, role) if b]
    if header_bits:
        lines.append(" · ".join(header_bits))
    lines.append(f"Workflow status: **{ws.get('status', 'unknown')}**")
    if data["check_workflow_complete"]:
        lines.append("`check_workflow_complete`: **YES** — receipt chain verified end-to-end.")
    else:
        lines.append(
            "`check_workflow_complete`: **NO** — the authoritative predicate disagrees with "
            "the `status` field above. This is a real, not cosmetic, integrity finding:"
        )
        for err in data["check_workflow_complete_errors"]:
            lines.append(f"  - {err}")
    if not data["events"]:
        lines.append(
            "\n> No `observability/run_events.jsonl` found for this opportunity — it predates "
            "this instrumentation, or hasn't been replayed since. This report is built from "
            "stage receipts and review artifacts only."
        )
    lines.append("")

    lines.append("## Stage-by-stage outcome")
    lines.append("")
    lines.append("| Stage | Result | Duration | Notes |")
    lines.append("|---|---|---|---|")
    lines.append(_stage_row(data, "stage0", "0 Fit Gate"))
    lines.append(_stage_row(data, "stage1", "1 Authoring"))
    lines.append(_stage_row(data, "stage2", "2 Review"))
    lines.append(_stage_row(data, "stage3", "3 Finalize"))
    lines.append("")

    # M2.2 — every disposition enum broken out explicitly, plus a genuinely separate
    # "undisposed" count. Conflating NOT_APPLICABLE/FALSE_POSITIVE into a vague "other" bucket
    # made a real submission's clean, fully-disposed findings look like unresolved noise the
    # first time this report was tested against real data — worth naming precisely instead.
    lines.append("## Stage 2 findings by severity and disposition")
    lines.append("")
    lines.append("| Subphase | BLOCK | WARN | Resolved | Accepted | N/A | False+ | Risk-accepted | Undisposed |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    dispositions_doc = data["dispositions"] or {}
    by_id = dispositions_doc.get("by_finding_id") or {}
    lines_dupe_warning: dict[str, set[str]] = {}
    for phase in ("truth", "ats", "hm", "mech"):
        fdoc = data["findings"].get(phase)
        if not fdoc:
            lines.append(f"| {phase} | — | — | — | — | — | — | — | — |")
            continue
        findings = fdoc.get("findings") or []
        ids_raw = [f.get("id") for f in findings]
        ids = set(ids_raw)
        if len(ids_raw) != len(ids):
            dupes = {i for i in ids if ids_raw.count(i) > 1}
            lines_dupe_warning.setdefault(phase, dupes)
        # Counted per unique finding id, not raw list length — a duplicate id represents one
        # underlying issue reported twice (see the dupe warning below), not two real defects.
        severity_by_id = {f.get("id"): f.get("severity") for f in findings}
        block = sum(1 for v in severity_by_id.values() if v == "BLOCK")
        warn = sum(1 for v in severity_by_id.values() if v == "WARN")
        disp_values = [by_id.get(fid) for fid in ids]
        resolved = disp_values.count("RESOLVED_EDIT")
        accepted = disp_values.count("ACCEPTED_AS_CORRECT")
        not_applicable = disp_values.count("NOT_APPLICABLE")
        false_positive = disp_values.count("FALSE_POSITIVE")
        risk_accepted = disp_values.count("HUMAN_ACCEPTED_RISK")
        undisposed = sum(1 for v in disp_values if v is None)
        lines.append(
            f"| {phase} | {block} | {warn} | {resolved} | {accepted} | {not_applicable} | "
            f"{false_positive} | {risk_accepted} | {undisposed} |"
        )
    for phase, dupes in lines_dupe_warning.items():
        lines.append(
            f"- ⚠ Data-quality: `{phase}_findings.json` emitted the same finding id more than "
            f"once ({', '.join(sorted(dupes))}) — counted once per id above, not once per line."
        )
    lines.append("")

    lines.append("## Warnings, failures, retries, fallbacks, overrides")
    lines.append("")
    summary_lines = _events_summary(data["events"])
    if summary_lines:
        lines.extend(summary_lines)
    else:
        lines.append("- None recorded (or no run_events.jsonl to check — see note above).")
    if data["verify_history"]:
        n = len(data["verify_history"])
        if n > 1:
            lines.append(f"- Stage 1 needed {n - 1} fix round(s) before verify passed (see verify_history.json).")
    stage3_receipt = data["receipts"].get("stage3")
    if stage3_receipt and stage3_receipt.get("integrity") == "OVERRIDDEN":
        lines.append("- ⚠ Finalized with `COMPLETE_WITH_OVERRIDE` — a real quality signal, not a formality.")
    lines.append("")

    lines.append("## Manual inspection needed")
    lines.append("")
    needs_inspection = []
    for phase in ("truth", "ats", "hm", "mech", "policy"):
        subphase = ((ws.get("stages") or {}).get("stage2") or {}).get("subphases", {}).get(phase, {})
        if subphase.get("status") == "NEEDS_DISPOSITION":
            needs_inspection.append(f"- `{phase}` is currently at NEEDS_DISPOSITION.")
    if needs_inspection:
        lines.extend(needs_inspection)
    else:
        lines.append("- None flagged.")
    lines.append("")

    lines.append("## Artifacts")
    lines.append("")
    lines.append(f"- [stage0_fit_gate.json]({_rel(data['folder'], 'stage0_fit_gate.json')})")
    lines.append(f"- [workflow_state.json]({_rel(data['folder'], 'workflow_state.json')})")
    for phase in ("truth", "ats", "hm", "mech"):
        lines.append(f"- [{phase} findings]({_rel(data['folder'], f'reviews/{phase}_findings.json')})")
    lines.append(f"- [dispositions.json]({_rel(data['folder'], 'reviews/dispositions.json')})")
    if data["verify_history"]:
        lines.append(f"- [verify_history.json]({_rel(data['folder'], 'stage1_first_draft/verify_history.json')})")
    if data["events"]:
        lines.append(f"- [run_events.jsonl]({_rel(data['folder'], 'observability/run_events.jsonl')}) ({len(data['events'])} events)")
    lines.append("")

    return "\n".join(lines)


def generate(folder: str) -> str:
    folder = _resolve_folder(folder)
    data = gather(folder)
    report = render(data)
    out_dir = os.path.join(folder, "observability")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "report.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
        f.write("\n")
    return out_path


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: observability_report.py <slug-or-path>", file=sys.stderr)
        sys.exit(1)
    try:
        out_path = generate(sys.argv[1])
    except WorkflowError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    with open(out_path, encoding="utf-8") as f:
        report = f.read()
    # Windows consoles default to cp1252, which can't render em dashes/arrows — same defensive
    # encode/decode build_stage0_fit_gate.py's own _one_line() already uses for this reason.
    enc = sys.stdout.encoding or "utf-8"
    print(report.encode(enc, errors="replace").decode(enc, errors="replace"))
    print(f"\nWritten to: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
