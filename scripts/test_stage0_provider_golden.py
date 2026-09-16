#!/usr/bin/env python3
"""Run the CR-093 golden set through the Stage 0 provider adapter (CR-108)."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import defaultdict
from pathlib import Path
from unittest.mock import patch

from cost_eligibility import set_test_zero_charge_providers
from stage0_evidence_cascade import BatchItem, classify_requirements_batch


_ROOT = Path(__file__).resolve().parents[1]
_GOLDEN = _ROOT / "data" / "fit_rubric_golden_set.json"
_DEFAULT_MODELS = {
    "groq": "openai/gpt-oss-120b",
    "gemini": "gemini-3.5-flash-lite",
    "local": "qwen2.5:7b-instruct-q4_K_M",
}


def _active_entries() -> list[dict]:
    """Load active CR-093 golden entries from the repository fixture."""
    payload = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    return [entry for entry in payload["entries"] if entry.get("status") == "active"]


def _items(entries: list[dict]) -> list[BatchItem]:
    """Convert golden entries into one bounded Stage 0 batch."""
    return [
        BatchItem(
            entry["id"],
            "preferred" if entry.get("requirement_type") == "Preferred/Bonus" else "required",
            entry["jd_line"],
            evidence_excerpt=entry.get("evidence_excerpt", ""),
        )
        for entry in entries
    ]


def _fixture_response(entries: list[dict]) -> str:
    """Build a deterministic provider response from expected golden semantics."""
    results = []
    for entry in entries:
        gate = entry["expected_gate"]
        source = entry.get("expected_gap_source") or ""
        requirement = entry["jd_line"]
        # Keep fixture reasoning grounded in the actual requirement vocabulary.
        first_term = next(iter(requirement.split()), "requirement")
        results.append(
            {
                "item_id": entry["id"],
                "gate": gate,
                "gap_source": source,
                "evidence_level": entry.get("expected_evidence_level", 0) or 0,
                "confidence": "high",
                "reasoning": f"The requirement explicitly addresses {first_term}.",
            }
        )
    return json.dumps({"results": results})


def _check_results(entries: list[dict], results: dict[str, dict]) -> tuple[int, int]:
    """Compare adapter results with gate, source, and evidence-level expectations."""
    passed = 0
    for entry in entries:
        result = results[entry["id"]]
        source_ok = (
            result.get("gap_source") == entry.get("expected_gap_source")
            if entry["expected_gate"] == "HARD"
            else result.get("gap_source") is None
        )
        expected_level = entry.get("expected_evidence_level")
        level_ok = (
            expected_level is None
            or abs(int(result["evidence_level"]) - int(expected_level)) <= 1
        )
        ok = result["gate"] == entry["expected_gate"] and source_ok and level_ok
        if ok:
            passed += 1
        else:
            exp_src = entry.get("expected_gap_source", "")
            act_src = result.get("gap_source", "")
            exp_lvl = expected_level if expected_level is not None else "?"
            act_lvl = result.get("evidence_level", "?")
            print(
                f"FAIL {entry['id']}: "
                f"gate exp={entry['expected_gate']} act={result['gate']}, "
                f"source exp={exp_src} act={act_src}, "
                f"level exp={exp_lvl} act={act_lvl}"
            )
    return passed, len(entries)


def _report_by_category(entries: list[dict], results: dict[str, dict]) -> None:
    """Print a per-category PASS/FAIL summary (CR-108 Epic 7.1).

    Same "don't hide a category collapse behind a healthy aggregate" principle
    check_fit_rubric_golden_set.py documents: an aggregate 21/21 can mask a
    whole category regressing. Category expectations come from the golden set
    entries themselves, so the four HARD-gate domain entries must all hold,
    the three false-positive domain entries must all stay NONE, and so on.
    """
    by_category: dict[str, list[tuple[str, bool]]] = defaultdict(list)
    for entry in entries:
        result = results[entry["id"]]
        source_ok = (
            result.get("gap_source") == entry.get("expected_gap_source")
            if entry["expected_gate"] == "HARD"
            else result.get("gap_source") is None
        )
        expected_level = entry.get("expected_evidence_level")
        level_ok = (
            expected_level is None
            or abs(int(result["evidence_level"]) - int(expected_level)) <= 1
        )
        ok = result["gate"] == entry["expected_gate"] and source_ok and level_ok
        by_category[entry["category"]].append((entry["id"], ok))
    for category in sorted(by_category):
        rows = by_category[category]
        passed = sum(1 for _, ok in rows if ok)
        status = "PASS" if passed == len(rows) else "FAIL"
        print(f"  [{status}] {category}: {passed}/{len(rows)}")
        for entry_id, ok in rows:
            if not ok:
                print(f"      FAIL {entry_id}")


def _run_fixture(
    entries: list[dict], provider: str
) -> tuple[int, int, int, dict[str, dict]]:
    """Run one provider adapter fixture without making a network request."""
    items = _items(entries)
    calls: list[dict] = []

    def fake_call(_system: str, _prompt: str, **kwargs: object) -> str:
        """Capture provider routing and return the deterministic golden response."""
        calls.append(kwargs)
        return _fixture_response(entries)

    settings = {
        "stage0_evidence_classification": {
            "provider_order": [provider],
            "models": {provider: f"{provider}-golden-test"},
        },
        "costClasses": {provider: "free_only"},
    }
    # Implements FR-316: mocked adapters need an explicit test-only zero-charge
    # assertion. Provider names alone must not bypass production cost eligibility.
    set_test_zero_charge_providers([provider])
    try:
        with patch("utils.call_llm", side_effect=fake_call):
            results = classify_requirements_batch(items, settings=settings)
    finally:
        set_test_zero_charge_providers(None)
    passed, total = _check_results(entries, results)
    routed = sum(
        1
        for call in calls
        if call.get("provider_override") == [provider]
        and call.get("model") == f"{provider}-golden-test"
    )
    return passed, total, routed, results


def _run_live(entries: list[dict], provider: str) -> tuple[int, int]:
    """Run one opt-in configured provider against the active golden batch."""
    from utils import load_llm_settings

    settings = copy.deepcopy(load_llm_settings())
    config = settings.get("stage0_evidence_classification")
    if not isinstance(config, dict):
        config = {}
    config["provider_order"] = [provider]
    config["local_only"] = provider == "local"
    settings["stage0_evidence_classification"] = config
    results = classify_requirements_batch(_items(entries), settings=settings)
    passed, total = _check_results(entries, results)
    print(f"  per-category ({provider} live):")
    _report_by_category(entries, results)
    return passed, total


def main() -> int:
    """Run offline provider fixtures or an explicitly requested live sample."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Use the configured provider and spend quota")
    parser.add_argument("--provider", choices=("groq", "gemini", "local"), default="groq")
    parser.add_argument("--category", default=None, help="Only check this golden category")
    args = parser.parse_args()
    entries = _active_entries()
    if args.category:
        entries = [e for e in entries if e["category"] == args.category]
    if args.live:
        passed, total = _run_live(entries, args.provider)
        print(f"Live {args.provider} golden result: {passed}/{total}")
        return 0 if passed == total else 1

    for provider in ("groq", "gemini"):
        passed, total, routed, results = _run_fixture(entries, provider)
        print(f"Fixture {provider} golden result: {passed}/{total}; routed calls: {routed}")
        print(f"  per-category ({provider}):")
        _report_by_category(entries, results)
        if passed != total or routed != 1:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
