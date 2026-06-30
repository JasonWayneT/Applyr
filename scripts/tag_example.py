"""
Golden Example Tagger — Epic 5, Part 2.

Tags a cover letter or resume as an approved example and adds it to
data/approved_examples.json for few-shot injection during generation.

Usage:
    python scripts/tag_example.py data/submissions/hubspot/CoverLetter.md
    python scripts/tag_example.py data/submissions/hubspot/Resume.md
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

EXAMPLES_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "approved_examples.json",
)

# Valid role types and company types for tagging
ROLE_TYPES = [
    "data_platform_pm",
    "platform_reliability_pm",
    "analytics_pm",
    "growth_pm",
    "enterprise_saas_pm",
    "consumer_pm",
    "marketplace_pm",
    "edtech_pm",
    "fintech_pm",
    "generic_pm",
]

COMPANY_TYPES = [
    "enterprise_saas",
    "mid_market_saas",
    "consumer_tech",
    "fintech",
    "marketplace",
    "edtech",
    "healthcare",
    "media_tech",
    "startup",
    "public_company",
]

HOOK_PATTERNS = [
    "company_observation",
    "role_problem",
    "industry_context",
    "need_first",
    "domain_first",
]


def _load_library() -> Dict:
    if os.path.exists(EXAMPLES_FILE):
        with open(EXAMPLES_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"version": "1.0", "examples": []}


def _save_library(library: Dict) -> None:
    with open(EXAMPLES_FILE, "w", encoding="utf-8") as f:
        json.dump(library, f, indent=2)


def _detect_doc_type(path: str, content: str) -> str:
    basename = os.path.basename(path).lower()
    if "cover" in basename:
        return "cover_letter"
    if "resume" in basename:
        return "resume"
    if "Dear Hiring Manager" in content:
        return "cover_letter"
    return "resume"


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _prompt_choice(prompt: str, choices: List[str]) -> str:
    print(f"\n{prompt}")
    for i, c in enumerate(choices, 1):
        print(f"  {i}. {c}")
    while True:
        raw = input("Enter number or custom value: ").strip()
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        if raw:
            return raw
        print("  (Enter a number or type a custom value)")


def _prompt_text(prompt: str, default: str = "") -> str:
    val = input(f"{prompt} [{default}]: ").strip() if default else input(f"{prompt}: ").strip()
    return val or default


def _prompt_bool(prompt: str, default: bool = False) -> bool:
    default_str = "Y/n" if default else "y/N"
    val = input(f"{prompt} [{default_str}]: ").strip().lower()
    if not val:
        return default
    return val in ("y", "yes", "1", "true")


def _prompt_claim_ids() -> List[str]:
    raw = input("Proof claim IDs used (comma-separated, e.g. ACC-102,ACC-103): ").strip()
    if not raw:
        return []
    return [c.strip() for c in raw.split(",") if c.strip()]


def tag_example(md_path: str) -> Optional[Dict]:
    """Interactive CLI to tag a single example (Story: Part 2 of Epic 5)."""
    if not os.path.exists(md_path):
        print(f"[ERROR] File not found: {md_path}", file=sys.stderr)
        return None

    with open(md_path, encoding="utf-8") as f:
        content = f.read()

    doc_type = _detect_doc_type(md_path, content)
    company_slug = Path(md_path).parent.name
    word_count = _word_count(content)

    print(f"\n{'='*60}")
    print(f"Tagging: {md_path}")
    print(f"  Detected doc type: {doc_type}")
    print(f"  Company slug:      {company_slug}")
    print(f"  Word count:        {word_count}")
    print(f"{'='*60}")

    # Generate a unique ID
    existing = _load_library()
    existing_ids = {e["id"] for e in existing.get("examples", [])}
    base_id = f"ex_{company_slug}_{doc_type[:2]}"
    counter = 1
    example_id = f"{base_id}_{counter:03d}"
    while example_id in existing_ids:
        counter += 1
        example_id = f"{base_id}_{counter:03d}"

    print(f"\n  Suggested ID: {example_id}")
    custom_id = input("  Use this ID? (Enter to confirm, or type a new one): ").strip()
    example_id = custom_id or example_id

    role_type = _prompt_choice("Role type:", ROLE_TYPES)
    company_type = _prompt_choice("Company type:", COMPANY_TYPES)

    proof_claims: List[str] = []
    hook_pattern: str = ""
    gap_acknowledged: bool = False

    if doc_type == "cover_letter":
        hook_pattern = _prompt_choice("Hook pattern:", HOOK_PATTERNS)
        proof_claims = _prompt_claim_ids()
        gap_acknowledged = _prompt_bool("Does this CL acknowledge a gap?", default=False)

    notes = _prompt_text("Notes (what makes this example strong)", default="")

    entry = {
        "id": example_id,
        "type": doc_type,
        "company": company_slug,
        "role_type": role_type,
        "company_type": company_type,
        "word_count": word_count,
        "approved": True,
        "notes": notes,
        "content_path": os.path.relpath(md_path, start=os.path.dirname(EXAMPLES_FILE)),
    }

    if doc_type == "cover_letter":
        entry["hook_pattern"] = hook_pattern
        entry["proof_claims"] = proof_claims
        entry["gap_acknowledged"] = gap_acknowledged

    print(f"\n{'='*60}")
    print("Entry to be saved:")
    print(json.dumps(entry, indent=2))
    print(f"{'='*60}")

    confirm = _prompt_bool("Save this entry?", default=True)
    if not confirm:
        print("Cancelled.")
        return None

    library = _load_library()
    examples = library.get("examples", [])
    # Replace if same ID already exists
    examples = [e for e in examples if e["id"] != example_id]
    examples.append(entry)
    library["examples"] = examples
    _save_library(library)

    print(f"\n[OK] Saved '{example_id}' to {EXAMPLES_FILE}")
    return entry


# ---------------------------------------------------------------------------
# Retrieval function (Story: Part 3 of Epic 5)
# ---------------------------------------------------------------------------

def retrieve_examples(
    jd_profile,
    doc_type: str = "cover_letter",
    n: int = 2,
) -> List[str]:
    """Retrieve best-matching approved examples for few-shot injection (Part 3).

    Matching priority:
    1. role_type exact match
    2. company_type exact match
    3. Fallback: highest-rated examples regardless of type

    Returns list of content strings (actual document text) for few-shot injection.
    """
    library = _load_library()
    examples = [e for e in library.get("examples", []) if e.get("approved") and e.get("type") == doc_type]

    if not examples:
        return []

    # Determine target role_type and company_type from jd_profile
    themes = getattr(jd_profile, "priority_themes", [])
    keywords = set(getattr(jd_profile, "keywords", []))
    all_text = " ".join(themes).lower() + " " + " ".join(keywords).lower()

    def _infer_role_type() -> str:
        if any(k in all_text for k in ("data", "ingest", "pipeline")):
            return "data_platform_pm"
        if any(k in all_text for k in ("platform", "reliability", "infrastructure")):
            return "platform_reliability_pm"
        if any(k in all_text for k in ("analytics", "reporting", "kpi")):
            return "analytics_pm"
        if any(k in all_text for k in ("growth", "acquisition", "funnel", "conversion")):
            return "growth_pm"
        if any(k in all_text for k in ("fintech", "payment", "lending")):
            return "fintech_pm"
        if any(k in all_text for k in ("marketplace", "lender", "borrower")):
            return "marketplace_pm"
        return "generic_pm"

    def _infer_company_type() -> str:
        if any(k in all_text for k in ("enterprise", "arr", "b2b")):
            return "enterprise_saas"
        if any(k in all_text for k in ("consumer", "b2c", "user", "dau")):
            return "consumer_tech"
        if any(k in all_text for k in ("fintech", "banking", "payment")):
            return "fintech"
        if any(k in all_text for k in ("marketplace", "platform")):
            return "marketplace"
        return "enterprise_saas"

    target_role = _infer_role_type()
    target_company_type = _infer_company_type()

    def _score(example: Dict) -> int:
        s = 0
        if example.get("role_type") == target_role:
            s += 2
        if example.get("company_type") == target_company_type:
            s += 1
        return s

    ranked = sorted(examples, key=_score, reverse=True)
    selected = ranked[:n]

    # Load actual content
    results: List[str] = []
    base_dir = os.path.dirname(EXAMPLES_FILE)
    for ex in selected:
        content_path = os.path.join(base_dir, ex.get("content_path", ""))
        if os.path.exists(content_path):
            try:
                with open(content_path, encoding="utf-8") as f:
                    results.append(f.read())
            except OSError:
                pass

    return results


# ---------------------------------------------------------------------------
# Embedding upgrade path — documented here, not built
# ---------------------------------------------------------------------------
#
# EMBEDDING UPGRADE PATH (when library reaches 50+ examples):
#
# The `retrieve_examples` function signature stays identical:
#     retrieve_examples(jd_profile, doc_type, n) -> List[str]
#
# The internals change:
#   1. Precompute embeddings for each example's content_path and store in
#      approved_examples.json under an "embedding" key (list of floats).
#   2. At retrieval time, embed the JD themes + keywords text.
#   3. Rank by cosine similarity instead of keyword matching.
#   4. Filter to approved=True and doc_type match before ranking.
#
# No callers need to change. The upgrade is non-breaking.


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tag_example.py <path/to/CoverLetter.md>", file=sys.stderr)
        sys.exit(1)
    result = tag_example(sys.argv[1])
    if result is None:
        sys.exit(1)
