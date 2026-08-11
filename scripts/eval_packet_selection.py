#!/usr/bin/env python3
"""
Packet-level selection-quality eval (session-007 R7/R8, pre-CR-086 measurement).

Answers a different question than the raw CR-063 scorer eval: not "does score_claim_for_jd
rank the right claim highest for one JD line" but "after Stage 0 extraction + CR-085's
domination-capped assignment, does the FINAL authoring_packet.json evidence_map actually
contain the projects a human verified should surface for that JD." CR-085 never touched the
scorer, so the raw CR-063 top-5 number is expected to read flat — this is the metric that can
actually move.

Ground truth: docs/reports/jd-theme-claim-eval-set.md's 16-row "claims that should surface"
column (human-verified against each Original_JD.txt + workExperience.md), hardcoded below as
project_id base codes (lens suffixes stripped — matches on ACC-NNN, per session-007 R8).

Corpus reality (verified against the live filesystem, not assumed): of 16 eval companies,
13 have an Original_JD.txt somewhere in the repo (mostly under data/archive/submissions/,
one live under data/submissions/). sailpoint, tilt, and parkingpass_com have no JD folder
anywhere and are marked UNAVAILABLE rather than guessed at.

Writes measurement artifacts to data/reports/cr086-packet-eval/ ONLY — never touches
data/archive/submissions/ or adopts anything into data/submissions/ as a side effect
(session-007 R8 requirement 2). Builds a throwaway Stage 0 + packet per company in a scratch
subfolder; does not run the real orchestrator (scripts/run_submission.py) since this is
measurement, not a real submission.

Usage:
    python scripts/eval_packet_selection.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_SCRIPT_DIR))

from build_authoring_packet import build_packet, load_claims  # noqa: E402
from build_stage0_fit_gate import build_stage0_fit_gate  # noqa: E402

_SUBMISSIONS_ROOT = _REPO_ROOT / "data" / "submissions"
_ARCHIVE_ROOT = _REPO_ROOT / "data" / "archive" / "submissions"
_SCRATCH_ROOT = _REPO_ROOT / "data" / "reports" / "cr086-packet-eval"

# docs/reports/jd-theme-claim-eval-set.md, "claims that should surface" column, project_id
# base codes only (ACC-NNN, lens suffix stripped). Company -> resolved data/ slug.
# sailpoint / tilt / parkingpass_com omitted: no Original_JD.txt found anywhere in the repo.
_EVAL_SET: dict[str, dict] = {
    "cresta":               {"should_surface": ["ACC-107", "ACC-103", "ACC-101"]},
    "group_1001":           {"should_surface": ["ACC-101", "ACC-103", "ACC-105", "ACC-107", "ACC-113"]},
    "onestream_software":   {"should_surface": ["ACC-107"]},  # marketplace theme has no claim (real gap)
    "buyers_edge_platform": {"should_surface": ["ACC-109"]},
    "ontra":                {"should_surface": ["ACC-401", "ACC-103"]},
    "remote":               {"should_surface": ["ACC-401", "ACC-106"]},
    "covideo":               {"should_surface": ["ACC-401", "ACC-105"]},
    "datagrail":            {"should_surface": ["ACC-107", "ACC-401", "ACC-103"]},
    "mytime":               {"should_surface": ["ACC-401", "ACC-104", "ACC-105"]},
    "par_technology":       {"should_surface": ["ACC-105", "ACC-109"]},  # ACC-204-style dev-coord, no exact code
    "pointclickcare":       {"should_surface": ["ACC-101", "ACC-102", "ACC-109", "ACC-401"]},
    "redox":                {"should_surface": ["ACC-101", "ACC-103", "ACC-109"]},
    "lumos":                {"should_surface": ["ACC-102", "ACC-107", "ACC-103", "ACC-101"]},
}

_MISSING_SLUGS = ["sailpoint", "tilt", "parkingpass_com"]

# Supplemental live packets for the unsupported-promotion signal only — NOT part of the
# should_surface hit/miss table (they're not in the 16-row eval set). Real, current
# submissions already known to Jason/Cursor from prior rounds of this session.
_SUPPLEMENTAL_SLUGS = ["camunda", "thermo_fisher_scientific", "amn_healthcare"]


def _resolve_jd_root(slug: str) -> Path | None:
    for root in (_SUBMISSIONS_ROOT / slug, _ARCHIVE_ROOT / slug):
        if (root / "Original_JD.txt").exists():
            return root
    return None


def _build_scratch_packet(slug: str, jd_root: Path) -> dict | None:
    """Copy the JD into an isolated scratch folder, build Stage 0 + the packet there.
    Never writes into jd_root itself.

    db_gate_result is forced to "clear" — these are real historical companies already
    in jobagent.sqlite from Jason's actual application history, so the normal 120-day
    reapplication cooldown gate (stage0_db_gate.py) rejects them outright before Stage 0
    even reaches requirement extraction (confirmed: this is what produced the first,
    wrong version of this eval's results — 7 of 13 "misses" were cooldown rejects, not
    real evidence_map defects). This is pure retrieval-quality measurement, not a real
    application decision, so the cooldown gate doesn't apply here.
    """
    scratch = _SCRATCH_ROOT / slug
    scratch.mkdir(parents=True, exist_ok=True)
    jd_text = (jd_root / "Original_JD.txt").read_text(encoding="utf-8", errors="replace")
    (scratch / "Original_JD.txt").write_text(jd_text, encoding="utf-8")

    try:
        stage0 = build_stage0_fit_gate(
            scratch,
            db_gate_result={"action": "clear", "reason_code": "eval_harness_override",
                             "reason": "CR-086 packet-selection eval — cooldown gate bypassed, measurement only"},
        )
    except Exception as exc:
        print(f"  SKIP {slug}: Stage 0 build raised {exc!r}", file=sys.stderr)
        return None
    (scratch / "stage0_fit_gate.json").write_text(
        json.dumps(stage0, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    try:
        packet = build_packet(scratch, no_hook=True)
    except Exception as exc:
        print(f"  SKIP {slug}: packet build raised {exc!r}", file=sys.stderr)
        return None

    (scratch / "authoring_packet.json").write_text(
        json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return packet


def _actual_projects(packet: dict, claims: dict[str, dict]) -> set[str]:
    projects: set[str] = set()
    for row in packet.get("evidence_map", []):
        for cid in row.get("claim_ids") or []:
            proj = (claims.get(cid) or {}).get("project_id") or cid
            projects.add(proj)
    return projects


def main() -> None:
    claims, _disabled = load_claims()

    rows = []
    for slug, spec in _EVAL_SET.items():
        jd_root = _resolve_jd_root(slug)
        if jd_root is None:
            rows.append({"slug": slug, "status": "UNAVAILABLE"})
            continue
        packet = _build_scratch_packet(slug, jd_root)
        if packet is None:
            rows.append({"slug": slug, "status": "BUILD_FAILED"})
            continue
        should = set(spec["should_surface"])
        actual = _actual_projects(packet, claims)
        hit = should & actual
        miss = should - actual
        extra = actual - should
        rows.append({
            "slug": slug,
            "status": "ok",
            "packet_status": packet.get("packet_status"),
            "should_surface": sorted(should),
            "actual": sorted(actual),
            "hit": sorted(hit),
            "miss": sorted(miss),
            "surfaced_not_expected": sorted(extra),
        })

    print("\n=== Packet-level selection eval (13 of 16 eval-set companies resolvable) ===\n")
    print(f"{'slug':<24}{'status':<10}{'hit':<6}{'miss':<6}{'extra':<6}")
    total_should = 0
    total_hit = 0
    for r in rows:
        if r["status"] != "ok":
            print(f"{r['slug']:<24}{r['status']}")
            continue
        n_should = len(r["should_surface"])
        n_hit = len(r["hit"])
        total_should += n_should
        total_hit += n_hit
        print(f"{r['slug']:<24}{r['packet_status']:<10}{n_hit}/{n_should:<4}{len(r['miss']):<6}{len(r['surfaced_not_expected']):<6}")

    print(f"\nAggregate: {total_hit}/{total_should} should-surface projects present in final evidence_map "
          f"({100*total_hit/total_should:.0f}%)" if total_should else "no data")

    print("\n--- Per-company detail (misses only, the real defect class) ---")
    for r in rows:
        if r["status"] == "ok" and r["miss"]:
            print(f"{r['slug']}: MISSING {r['miss']} (should={r['should_surface']}, got={r['actual']})")

    print(f"\nUnavailable (no JD found anywhere): {_MISSING_SLUGS}")

    # Supplemental: unsupported-promotion signal only, not scored against should_surface.
    print("\n=== Supplemental live packets (unsupported-promotion review, not should_surface-scored) ===\n")
    supplemental_rows = []
    for slug in _SUPPLEMENTAL_SLUGS:
        jd_root = _SUBMISSIONS_ROOT / slug
        if not (jd_root / "stage0_fit_gate.json").exists():
            print(f"{slug}: no live stage0_fit_gate.json, skipping")
            continue
        try:
            packet = build_packet(jd_root, no_hook=True)
        except Exception as exc:
            print(f"{slug}: packet build raised {exc!r}")
            continue
        print(f"--- {slug} (packet_status={packet.get('packet_status')}) ---")
        for row in packet.get("evidence_map", []):
            if row.get("claim_ids"):
                print(f"  [{row['bucket']}] {row['jd_item'][:70]!r} -> {row['claim_ids']}")
        supplemental_rows.append({"slug": slug, "evidence_map": packet.get("evidence_map")})

    out_path = _SCRATCH_ROOT / "results.json"
    out_path.write_text(
        json.dumps({"eval_rows": rows, "missing_slugs": _MISSING_SLUGS,
                     "supplemental": supplemental_rows}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nFull results written to {out_path}")


if __name__ == "__main__":
    main()
