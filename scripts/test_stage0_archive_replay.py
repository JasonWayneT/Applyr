#!/usr/bin/env python3
"""CR-108 Epic 7.3/7.4: archive replay harness for the Stage 0 evidence cascade.

Runs the cascade against real archived JDs (data/archive/submissions/) and
compares results to the legacy per-line classifier. Records call counts, batch
sizes, latency, and gate/source/evidence-level agreement.

Usage:
  python scripts/test_stage0_archive_replay.py                    # 5 JDs, cascade only
  python scripts/test_stage0_archive_replay.py --limit 10          # 10 JDs
  python scripts/test_stage0_archive_replay.py --compare           # also run old classifier
  python scripts/test_stage0_archive_replay.py --provider gemini   # use Gemini
  python scripts/test_stage0_archive_replay.py --jd axos_bank      # specific JD

This script makes real API calls using credentials stored in the SQLite
profiles table. It does not log credentials or personal contact data.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))

_ARCHIVE = _ROOT / "data" / "archive" / "submissions"
_WORK_EXP = _ROOT / "data" / "workExperience.md"


def _load_work_exp() -> str:
    """Load workExperience.md for evidence context."""
    if _WORK_EXP.exists():
        return _WORK_EXP.read_text(encoding="utf-8", errors="replace")
    return ""


def _extract_requirements(folder: Path) -> tuple[list[str], list[str], list[str], str]:
    """Extract requirement lines from an archived JD.

    Returns (required, preferred, responsibilities, company_name).
    Reuses the same extraction functions as build_stage0_fit_gate.py.
    """
    import re
    import html

    jd_file = folder / "Original_JD.txt"
    if not jd_file.exists():
        return [], [], [], folder.name

    raw_text = jd_file.read_text(encoding="utf-8", errors="replace")
    url, jd_text = _parse_url_and_jd(raw_text)
    for _ in range(3):
        unescaped = html.unescape(jd_text)
        if unescaped == jd_text:
            break
        jd_text = unescaped
    jd_text = re.sub(r"<[^>]+>", " ", jd_text)
    jd_text = re.sub(r"[ \t]{2,}", " ", jd_text)

    company = folder.name.replace("_", " ").replace("-", " ").title()

    # Use the same NLP extraction as the default pipeline path
    from build_stage0_fit_gate import _extract_sections_nlp, _extract_sections

    sections = _extract_sections_nlp(jd_text)
    if sections is None:
        sections = _extract_sections(jd_text)

    return (
        sections.get("required", []),
        sections.get("preferred", []),
        sections.get("responsibilities", []),
        company,
    )


def _parse_url_and_jd(raw_text: str) -> tuple[str, str]:
    """Extract URL from first line if present, return (url, jd_body)."""
    if raw_text.startswith("URL: "):
        lines = raw_text.split("\n", 2)
        url = lines[0][5:].strip()
        body = lines[2] if len(lines) > 2 else ""
        return url, body
    return "", raw_text


def _run_cascade(
    required: list[str],
    preferred: list[str],
    responsibilities: list[str],
    work_exp: str,
    company: str,
    provider: str,
) -> dict:
    """Run the cascade on extracted requirements. Returns metrics + results."""
    from stage0_evidence_cascade import BatchItem, classify_requirements_batch
    from evidence_scale import build_evidence_context
    from utils import load_llm_settings
    import copy

    items: list[BatchItem] = []
    for ordinal, line in enumerate(required):
        items.append(BatchItem(
            f"req-{ordinal}",
            "required",
            line,
            evidence_excerpt=build_evidence_context(line, work_exp, k=4, max_chars=3000),
        ))
    for ordinal, line in enumerate(preferred):
        items.append(BatchItem(
            f"pref-{ordinal}",
            "preferred",
            line,
            evidence_excerpt=build_evidence_context(line, work_exp, k=4, max_chars=3000),
        ))

    if not items:
        return {
            "items": 0,
            "cascade_calls": 0,
            "cascade_seconds": 0,
            "cascade_results": {},
            "hard_gates": [],
            "pending": [],
        }

    settings = copy.deepcopy(load_llm_settings())
    config = settings.get("stage0_evidence_classification", {})
    # Use the specified provider first, with the other as fallback
    fallback = "gemini" if provider == "groq" else "groq"
    config["provider_order"] = [provider, fallback]
    config["local_only"] = False
    settings["stage0_evidence_classification"] = config

    start = time.monotonic()
    results = classify_requirements_batch(items, settings=settings)
    elapsed = time.monotonic() - start

    hard_gates = []
    pending = []
    for item_id, result in results.items():
        if result.get("gate") == "HARD":
            hard_gates.append({
                "item_id": item_id,
                "gap_source": result.get("gap_source"),
                "evidence_level": result.get("evidence_level"),
            })
        if result.get("needs_user_confirmation"):
            pending.append({
                "item_id": item_id,
                "canonical_skill": result.get("canonical_skill"),
                "skill_kind": result.get("skill_kind"),
            })

    return {
        "items": len(items),
        "cascade_calls": 1,
        "cascade_seconds": round(elapsed, 2),
        "cascade_results": results,
        "hard_gates": hard_gates,
        "pending": pending,
    }


def _run_legacy(
    required: list[str],
    preferred: list[str],
    work_exp: str,
    company: str,
) -> dict:
    """Run the old per-line classifier for comparison. Returns metrics + results."""
    from evidence_scale import classify_requirement

    results: dict[str, dict] = {}
    total_seconds = 0.0
    calls = 0

    for ordinal, line in enumerate(required):
        item_id = f"required:{ordinal}:{line[:40]}"
        start = time.monotonic()
        try:
            judgment = classify_requirement(
                line, work_exp, is_required=True, company=company,
            )
            elapsed = time.monotonic() - start
            total_seconds += elapsed
            calls += 1
            results[item_id] = {
                "gate": judgment.gate,
                "gap_source": judgment.gap_source,
                "evidence_level": judgment.evidence_level,
                "confidence": judgment.confidence,
                "item": line,
            }
        except Exception as exc:
            elapsed = time.monotonic() - start
            total_seconds += elapsed
            calls += 1
            results[item_id] = {"error": str(exc), "item": line}

    for ordinal, line in enumerate(preferred):
        item_id = f"preferred:{ordinal}:{line[:40]}"
        start = time.monotonic()
        try:
            judgment = classify_requirement(
                line, work_exp, is_required=False, company=company,
            )
            elapsed = time.monotonic() - start
            total_seconds += elapsed
            calls += 1
            results[item_id] = {
                "gate": judgment.gate,
                "gap_source": judgment.gap_source,
                "evidence_level": judgment.evidence_level,
                "confidence": judgment.confidence,
                "item": line,
            }
        except Exception as exc:
            elapsed = time.monotonic() - start
            total_seconds += elapsed
            calls += 1
            results[item_id] = {"error": str(exc), "item": line}

    return {
        "legacy_calls": calls,
        "legacy_seconds": round(total_seconds, 2),
        "legacy_results": results,
    }


def _compare(cascade: dict, legacy: dict) -> dict:
    """Compare cascade vs legacy results by matching on requirement text."""
    cascade_items = {r["item"]: r for r in cascade.get("cascade_results", {}).values() if "item" in r}
    legacy_items = {r.get("item", ""): r for r in legacy.get("legacy_results", {}).values() if "item" in r}

    common = set(cascade_items.keys()) & set(legacy_items.keys())
    gate_matches = sum(
        1 for item_text in common
        if cascade_items[item_text].get("gate") == legacy_items[item_text].get("gate")
    )
    level_matches = sum(
        1 for item_text in common
        if abs(
            int(cascade_items[item_text].get("evidence_level", -1))
            - int(legacy_items[item_text].get("evidence_level", -1))
        ) <= 1
    )

    mismatches = []
    for item_text in common:
        c = cascade_items[item_text]
        l = legacy_items[item_text]
        if c.get("gate") != l.get("gate"):
            mismatches.append({
                "item": item_text[:80],
                "cascade_gate": c.get("gate"),
                "legacy_gate": l.get("gate"),
                "cascade_level": c.get("evidence_level"),
                "legacy_level": l.get("evidence_level"),
            })

    return {
        "common_items": len(common),
        "gate_matches": gate_matches,
        "gate_mismatches": len(common) - gate_matches,
        "level_matches_within_1": level_matches,
        "mismatches": mismatches,
    }


def _pick_jds(limit: int, jd_filter: str | None) -> list[Path]:
    """Pick a sample of archived JDs, excluding backups."""
    all_jds = sorted(
        d for d in _ARCHIVE.iterdir()
        if d.is_dir() and "backup" not in d.name
        and (d / "Original_JD.txt").exists()
    )
    if jd_filter:
        all_jds = [d for d in all_jds if jd_filter in d.name]
    return all_jds[:limit]


def main() -> int:
    os.environ["APPLYR_STAGE0_CLOUD_LLM"] = "1"
    parser = argparse.ArgumentParser(description="CR-108 archive replay harness")
    parser.add_argument("--limit", type=int, default=5, help="Number of JDs to replay")
    parser.add_argument("--compare", action="store_true", help="Also run legacy per-line classifier")
    parser.add_argument("--provider", choices=("groq", "gemini"), default="groq")
    parser.add_argument("--jd", default=None, help="Specific JD slug to replay")
    parser.add_argument("--delay", type=float, default=8.0, help="Seconds to wait between JDs (rate limit avoidance)")
    parser.add_argument("--verbose", action="store_true", help="Print per-item results")
    args = parser.parse_args()

    if not _ARCHIVE.exists():
        print(f"Archive not found: {_ARCHIVE}", file=sys.stderr)
        return 1

    work_exp = _load_work_exp()
    if not work_exp:
        print("Warning: workExperience.md not found — evidence excerpts will be empty.", file=sys.stderr)

    jd_folders = _pick_jds(args.limit, args.jd)
    if not jd_folders:
        print("No JDs found matching the filter.", file=sys.stderr)
        return 1

    print(f"Replaying {len(jd_folders)} JDs with provider={args.provider}")
    print(f"Compare with legacy: {args.compare}")
    print()

    aggregate = {
        "total_jds": len(jd_folders),
        "total_items": 0,
        "total_cascade_calls": 0,
        "total_cascade_seconds": 0,
        "total_legacy_calls": 0,
        "total_legacy_seconds": 0,
        "total_hard_gates": 0,
        "total_pending": 0,
        "gate_matches": 0,
        "gate_mismatches": 0,
        "level_matches_within_1": 0,
        "common_items": 0,
    }

    per_jd_results = []

    for folder in jd_folders:
        required, preferred, responsibilities, company = _extract_requirements(folder)
        n_items = len(required) + len(preferred)

        if n_items == 0:
            print(f"  {company}: no requirements extracted, skipping")
            continue

        print(f"  {company}: {len(required)} required, {len(preferred)} preferred, {len(responsibilities)} responsibilities")

        try:
            cascade = _run_cascade(required, preferred, responsibilities, work_exp, company, args.provider)
        except Exception as exc:
            print(f"    cascade FAILED: {exc}")
            per_jd_results.append({"company": company, "error": str(exc)})
            continue

        print(f"    cascade: {cascade['cascade_calls']} call, {cascade['cascade_seconds']}s, "
              f"{len(cascade['hard_gates'])} HARD gates, {len(cascade['pending'])} pending")

        aggregate["total_items"] += cascade["items"]
        aggregate["total_cascade_calls"] += cascade["cascade_calls"]
        aggregate["total_cascade_seconds"] += cascade["cascade_seconds"]
        aggregate["total_hard_gates"] += len(cascade["hard_gates"])
        aggregate["total_pending"] += len(cascade["pending"])

        legacy = {}
        if args.compare:
            legacy = _run_legacy(required, preferred, work_exp, company)
            print(f"    legacy: {legacy['legacy_calls']} calls, {legacy['legacy_seconds']}s")

            aggregate["total_legacy_calls"] += legacy["legacy_calls"]
            aggregate["total_legacy_seconds"] += legacy["legacy_seconds"]

            comparison = _compare(cascade, legacy)
            print(f"    comparison: {comparison['gate_matches']}/{comparison['common_items']} gate matches, "
                  f"{comparison['level_matches_within_1']}/{comparison['common_items']} level matches (±1)")

            aggregate["gate_matches"] += comparison["gate_matches"]
            aggregate["gate_mismatches"] += comparison["gate_mismatches"]
            aggregate["level_matches_within_1"] += comparison["level_matches_within_1"]
            aggregate["common_items"] += comparison["common_items"]

            if args.verbose and comparison["mismatches"]:
                for m in comparison["mismatches"]:
                    print(f"      MISMATCH: {m['item']}")
                    print(f"        cascade: gate={m['cascade_gate']} level={m['cascade_level']}")
                    print(f"        legacy:  gate={m['legacy_gate']} level={m['legacy_level']}")

        if args.verbose:
            for hg in cascade["hard_gates"]:
                print(f"      HARD: {hg['item_id']} source={hg['gap_source']} level={hg['evidence_level']}")
            for p in cascade["pending"]:
                print(f"      PENDING: {p['item_id']} skill={p['canonical_skill']} kind={p['skill_kind']}")

        per_jd_results.append({
            "company": company,
            "required": len(required),
            "preferred": len(preferred),
            "cascade": cascade,
            "legacy": legacy if args.compare else None,
        })

        # Rate limit avoidance: wait between JDs
        if folder != jd_folders[-1]:
            time.sleep(args.delay)

    print()
    print("=" * 60)
    print("AGGREGATE")
    print("=" * 60)
    print(f"  JDs replayed: {aggregate['total_jds']}")
    print(f"  Total items classified: {aggregate['total_items']}")
    print(f"  Cascade calls: {aggregate['total_cascade_calls']}")
    print(f"  Cascade total time: {aggregate['total_cascade_seconds']}s")
    print(f"  Cascade avg time per JD: {aggregate['total_cascade_seconds'] / max(aggregate['total_jds'], 1):.1f}s")
    print(f"  Hard gates found: {aggregate['total_hard_gates']}")
    print(f"  Pending confirmations: {aggregate['total_pending']}")

    if args.compare and aggregate["common_items"] > 0:
        print()
        print(f"  Legacy calls: {aggregate['total_legacy_calls']}")
        print(f"  Legacy total time: {aggregate['total_legacy_seconds']}s")
        print(f"  Call reduction: {aggregate['total_legacy_calls']} → {aggregate['total_cascade_calls']} "
              f"({1 - aggregate['total_cascade_calls'] / max(aggregate['total_legacy_calls'], 1):.0%})")
        print(f"  Time comparison: {aggregate['total_legacy_seconds']}s → {aggregate['total_cascade_seconds']}s")
        print(f"  Gate agreement: {aggregate['gate_matches']}/{aggregate['common_items']} "
              f"({aggregate['gate_matches'] / max(aggregate['common_items'], 1):.0%})")
        print(f"  Level agreement (±1): {aggregate['level_matches_within_1']}/{aggregate['common_items']} "
              f"({aggregate['level_matches_within_1'] / max(aggregate['common_items'], 1):.0%})")

    # Save detailed results
    output_path = _ROOT / "data" / "stage0_archive_replay_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"aggregate": aggregate, "per_jd": per_jd_results}, f, indent=2, default=str)
    print(f"\n  Detailed results saved to: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
