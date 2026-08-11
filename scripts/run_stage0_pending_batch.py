#!/usr/bin/env python3
"""Stage 0 batch over pending submissions; write Tier1/Tier2/Skip report."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_stage0_fit_gate import build_stage0_fit_gate  # noqa: E402

SKIP_COMPLETE = {"ncontracts", "leaflink", "camunda", "central_bank"}
SUBMISSIONS = ROOT / "data" / "submissions"


def main() -> int:
    folders = []
    for folder in sorted(SUBMISSIONS.iterdir()):
        if not folder.is_dir():
            continue
        if folder.name in SKIP_COMPLETE:
            continue
        if not (folder / "Original_JD.txt").exists():
            continue
        st = folder / "workflow_state.json"
        if st.exists():
            status = json.loads(st.read_text(encoding="utf-8")).get("status")
            if status in ("COMPLETE", "COMPLETE_WITH_OVERRIDE"):
                continue
        folders.append(folder)

    print(f"Stage 0 on {len(folders)} folders")
    rows = []
    for folder in folders:
        try:
            result = build_stage0_fit_gate(str(folder), write=True)
            decision = result.get("decision") or result.get("tier") or "?"
            tier = result.get("tier")
            reach = result.get("reach_out")
            company = result.get("company") or folder.name
            role = result.get("role") or ""
            reason = (
                result.get("skip_reason")
                or result.get("reason")
                or result.get("decision_reason")
                or ""
            )
            if isinstance(reason, list):
                reason = "; ".join(str(x) for x in reason[:3])
            # Normalize tier bucket
            dlow = str(decision).lower()
            if dlow in ("skip", "reject", "rejected") or str(tier).lower() in (
                "skip",
                "reject",
            ):
                bucket = "Skip"
            elif str(tier) in ("1", "Tier 1", "T1") or dlow in ("pass", "tier1"):
                # check gaps
                gaps = result.get("flagged_gaps") or result.get("soft_gaps") or []
                hard = result.get("hard_gaps") or []
                if hard:
                    bucket = "Skip"
                elif gaps:
                    bucket = "Tier 2"
                else:
                    # Some gates use tier field explicitly
                    if str(tier) in ("2", "Tier 2", "T2"):
                        bucket = "Tier 2"
                    else:
                        bucket = "Tier 1"
            elif str(tier) in ("2", "Tier 2", "T2"):
                bucket = "Tier 2"
            else:
                bucket = str(tier or decision)
            tag = " — Reach Out" if reach else ""
            rows.append(
                {
                    "slug": folder.name,
                    "company": company,
                    "role": role,
                    "bucket": bucket,
                    "reach_out": bool(reach),
                    "reason": str(reason)[:200],
                    "raw_decision": decision,
                    "raw_tier": tier,
                }
            )
            print(f"  [{bucket}{tag}] {folder.name}: {role} | {str(reason)[:80]}")
        except Exception as exc:
            rows.append(
                {
                    "slug": folder.name,
                    "company": folder.name,
                    "role": "",
                    "bucket": "Skip",
                    "reach_out": False,
                    "reason": f"stage0_error: {exc}",
                    "raw_decision": "error",
                    "raw_tier": None,
                }
            )
            print(f"  [ERR] {folder.name}: {exc}")

    out = ROOT / "data" / "reports" / "stage0_batch_2026-08-11.json"
    out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")

    # Markdown table summary
    by = {"Tier 1": [], "Tier 2": [], "Skip": [], "Other": []}
    for r in rows:
        by.setdefault(r["bucket"] if r["bucket"] in by else "Other", []).append(r)

    md = ["# Stage 0 batch 2026-08-11", ""]
    for bucket in ("Tier 1", "Tier 2", "Skip", "Other"):
        items = by.get(bucket) or []
        md.append(f"## {bucket} ({len(items)})")
        md.append("")
        for r in items:
            ro = " — Reach Out" if r.get("reach_out") else ""
            md.append(
                f"- **{r['company']}** (`{r['slug']}`) — {r['role']}{ro}: {r['reason'] or r['raw_decision']}"
            )
        md.append("")
    md_path = ROOT / "data" / "reports" / "stage0_batch_2026-08-11.md"
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"report: {md_path}")
    print(
        "counts:",
        {k: len(v) for k, v in by.items()},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
