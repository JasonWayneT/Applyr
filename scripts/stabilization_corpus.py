#!/usr/bin/env python3
"""Temporary stabilization corpus runner — Stage 0 + packet rebuild across submissions.

Does not mint workflow receipts or touch the jobs DB. Writes a report under data/reports/.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_SCRIPT_DIR))

from build_stage0_fit_gate import build_stage0_fit_gate  # noqa: E402
from build_authoring_packet import build_packet  # noqa: E402

# Representative mix: clean, stretch, healthcare/domain, tooling, thin/stub, enterprise, AI-ish
CORPUS = [
    "camunda",
    "central_bank",
    "ncontracts",
    "paylocity",
    "amn_healthcare",
    "elevance_health",
    "deloitte",
    "relativity",
    "thermo_fisher_scientific",
    "seed_health",
    "acushnet_company",
    "netradyne_54a876",
    "test_co",
    "realtime_eclinical_solutions",
    "pinterest",
    "leaflink",
    "common_room",
    "sdl",
    "neogen",
    "amplify",
]


def main() -> int:
    sub_root = _ROOT / "data" / "submissions"
    report_rows = []
    novel = []

    for slug in CORPUS:
        folder = sub_root / slug
        row = {"slug": slug, "exists": folder.exists()}
        if not folder.exists():
            row["error"] = "missing folder"
            report_rows.append(row)
            continue
        jd = folder / "Original_JD.txt"
        if not jd.exists():
            row["error"] = "missing Original_JD.txt"
            report_rows.append(row)
            continue

        try:
            gate = build_stage0_fit_gate(str(folder))
            gate_path = folder / "stage0_fit_gate.json"
            # Honor extraction_override: keep hand-curated gate for packet build.
            if gate_path.exists():
                on_disk = json.loads(gate_path.read_text(encoding="utf-8"))
                if on_disk.get("extraction_override"):
                    gate = on_disk
                    row["extraction_override"] = True
                else:
                    gate_path.write_text(
                        json.dumps(gate, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8",
                    )
            else:
                gate_path.write_text(
                    json.dumps(gate, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
            row["tier"] = gate.get("tier")
            row["decision"] = gate.get("decision")
            row["thin_jd"] = gate.get("thin_jd")
            row["n_required"] = len(gate.get("required") or [])
            row["n_preferred"] = len(gate.get("preferred") or [])
            row["n_resp"] = len(gate.get("responsibilities") or [])
            row["n_gaps"] = len(gate.get("flagged_gaps") or [])
            row["hard_gaps"] = [
                g.get("item", "")[:80]
                for g in (gate.get("flagged_gaps") or [])
                if g.get("gap_class") == "HARD"
            ]
            row["skip_reason"] = gate.get("skip_reason") or gate.get("notes")
        except Exception as e:
            row["stage0_error"] = f"{type(e).__name__}: {e}"
            report_rows.append(row)
            novel.append({"slug": slug, "class": "CRITICAL", "msg": row["stage0_error"]})
            continue

        if gate.get("tier") == "Skip":
            row["packet"] = "skipped"
            report_rows.append(row)
            continue

        try:
            packet = build_packet(str(folder), no_hook=True)
            # Persist so disk artifacts match the in-memory verdict.
            (folder / "authoring_packet.json").write_text(
                json.dumps(packet, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            row["packet"] = packet.get("packet_status")
            row["tokens"] = packet.get("estimated_tokens")
            row["incomplete_reasons"] = packet.get("incomplete_reasons") or []
            if packet.get("packet_status") != "ready":
                novel.append(
                    {
                        "slug": slug,
                        "class": "MAJOR",
                        "msg": "packet incomplete: "
                        + "; ".join(row["incomplete_reasons"][:3]),
                    }
                )
            # Flag empty-required Tier 1 as Critical (should be impossible)
            if gate.get("tier") == "Tier 1" and row["n_required"] == 0 and not gate.get("thin_jd"):
                novel.append(
                    {
                        "slug": slug,
                        "class": "CRITICAL",
                        "msg": "Tier 1 with empty required",
                    }
                )
            # Flag required items that look falsely clean with zero claim_ids and no bridge
            em = packet.get("evidence_map") or []
            for erow in em:
                if erow.get("bucket") != "required":
                    continue
                if (erow.get("claim_ids") or erow.get("bridge")):
                    continue
                novel.append(
                    {
                        "slug": slug,
                        "class": "MAJOR",
                        "msg": f"required evidence row empty: {(erow.get('jd_item') or '')[:80]}",
                    }
                )
        except Exception as e:
            row["packet_error"] = f"{type(e).__name__}: {e}"
            novel.append(
                {
                    "slug": slug,
                    "class": "CRITICAL",
                    "msg": f"packet exception: {row['packet_error']}",
                }
            )
            traceback.print_exc()

        report_rows.append(row)

    out_dir = _ROOT / "data" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "stabilization_corpus_2026-08-11.json"
    payload = {
        "corpus_size": len(CORPUS),
        "ran": len(report_rows),
        "novel_or_failures": novel,
        "rows": report_rows,
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {out_path}")
    print(f"Rows: {len(report_rows)}")
    print(f"Novel/failure signals: {len(novel)}")
    for n in novel:
        print(f"  [{n['class']}] {n['slug']}: {n['msg']}")
    print("--- summary ---")
    for r in report_rows:
        print(
            f"{r['slug']:40} tier={str(r.get('tier')):8} "
            f"req={str(r.get('n_required')):3} gaps={str(r.get('n_gaps')):3} "
            f"pkt={r.get('packet') or r.get('packet_error') or r.get('error')}"
        )
    return 1 if any(n["class"] == "CRITICAL" for n in novel) else 0


if __name__ == "__main__":
    raise SystemExit(main())
