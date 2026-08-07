#!/usr/bin/env python3
"""
Deterministic Stage 0 fit-gate builder.
# Implements FR-252

Reads Original_JD.txt from a submission folder (or a bare folder path), runs
all zero-token gates (DB cooldown, prefs/exclusions, gap classification), and
writes stage0_fit_gate.json in a shape compatible with the live files at
data/context_pack_validation/*/stage0_fit_gate.json.

Usage:
    python scripts/build_stage0_fit_gate.py data/submissions/{slug}
    python scripts/build_stage0_fit_gate.py data/context_pack_validation/limble

Exit: always 0; read "tier" and "decision" in the JSON to branch.

No LLM / no Ollama required.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_SCRIPT_DIR = Path(__file__).parent
_REPO_ROOT = _SCRIPT_DIR.parent
_CLAIMS_PATH = _REPO_ROOT / "data" / "master_claims_tags_only.json"
_SKILLS_PATH = _REPO_ROOT / "data" / "skills_catalog.json"
_PREFS_PATH = _REPO_ROOT / "data" / "candidate_preferences.json"
_DEFAULT_DB = _REPO_ROOT / "data" / "jobagent.sqlite"

# ---------------------------------------------------------------------------
# Vocabulary loader (Story 2.4 anchor corpus)
# ---------------------------------------------------------------------------

def _load_anchor_vocab() -> set[str]:
    """
    Build the set of all known-true anchor terms (lowercase).

    Sources:
      - All tags from master_claims_tags_only.json
      - All tool names from skills_catalog.json

    Individual words within multi-word tags are also added so partial-phrase
    matching still fires (e.g. tag "Roadmap Prioritization" gives "roadmap"
    and "prioritization").
    """
    vocab: set[str] = set()

    if _CLAIMS_PATH.exists():
        try:
            claims = json.loads(_CLAIMS_PATH.read_text(encoding="utf-8"))
            for claim in claims.values():
                for tag in claim.get("tags") or []:
                    term = tag.strip().lower()
                    vocab.add(term)
                    for word in re.findall(r"[a-z]{3,}", term):
                        vocab.add(word)
        except Exception:
            pass

    if _SKILLS_PATH.exists():
        try:
            catalog = json.loads(_SKILLS_PATH.read_text(encoding="utf-8"))
            for terms in catalog.values():
                for t in terms:
                    term = t.strip().lower()
                    vocab.add(term)
                    # Split "Technical Literacy: HTML/CSS/JavaScript" at delimiters
                    for word in re.findall(r"[a-z]{3,}", term):
                        vocab.add(word)
        except Exception:
            pass

    return vocab


# ---------------------------------------------------------------------------
# Hard-blocked tool list (Story 2.4)
# ---------------------------------------------------------------------------

# Tools that Jason definitively does not have experience with.
# Drawn from AGENTS.md hard anti-hallucination rules and common industry tools.
# NOT a comprehensive list — add to it; err on SOFT when uncertain.
_HARD_BLOCKED_TOOLS: frozenset[str] = frozenset({
    # Healthcare data standards
    "fhir", "hl7", "epic", "cerner", "meditech", "athenahealth",
    "redox", "mirth", "smartonfhir", "dicom",
    # Data warehouse / analytics infrastructure
    "snowflake", "databricks", "dbt", "fivetran", "airbyte",
    "tableau", "looker", "power bi", "powerbi", "qlik", "sisense",
    # Infrastructure / cloud infra
    "docker", "kubernetes", "k8s", "terraform", "helm",
    "ansible", "puppet", "chef",
    # Cloud platforms (PM roles that require cloud certification / ownership)
    # Note: general cloud-aware is NOT a gap; only direct ownership
    # ML / AI frameworks (engineering, not tooling)
    "tensorflow", "pytorch", "keras", "scikit-learn", "huggingface",
    "mlflow", "kubeflow", "sagemaker",
    # Specific tools from blocked list
    "mixpanel",         # analytics (Pendo is in catalog; mixpanel is not)
    "braze",            # marketing automation
    "zendesk", "freshdesk",  # support tooling (not in resume)
    "intercom",         # support/chat
    # Finance/payments/billing tools
    "stripe", "braintree", "adyen", "recurly", "chargebee",
    "netsuite", "workday", "sap",
    # Legal/contract
    "ironclad", "docusign",
    # Domain-specific
    "coupa",            # procurement
    "veeva",            # pharma CRM
})

# Regex pattern to detect hard-blocked tool names in a requirement string.
# Compiled lazily.
_HARD_TOOL_RE: re.Pattern | None = None


def _get_hard_tool_pattern() -> re.Pattern:
    global _HARD_TOOL_RE
    if _HARD_TOOL_RE is None:
        escaped = sorted(_HARD_BLOCKED_TOOLS, key=len, reverse=True)
        pattern = r"\b(?:" + "|".join(re.escape(t) for t in escaped) + r")\b"
        _HARD_TOOL_RE = re.compile(pattern, re.I)
    return _HARD_TOOL_RE


# ---------------------------------------------------------------------------
# JD section extraction (Story 2.3)
# ---------------------------------------------------------------------------

# Section heading patterns → (bucket, priority)
# Earlier matches win; we stop scanning a section when the next header appears.
_SECTION_HEADERS: list[tuple[str, re.Pattern]] = [
    ("required", re.compile(
        r"^(?:#+\s*)?"
        r"(?:requirements?|qualifications?|what\s+you(?:'|')ll?\s+(?:need|bring|have)|"
        r"what\s+we(?:'|')re?\s+looking\s+for|who\s+you\s+are|must\s+have|"
        r"minimum\s+qualifications?|required\s+(?:skills?|qualifications?|experience)|"
        r"key\s+requirements?|basic\s+qualifications?|you\s+bring|about\s+you|"
        r"experience\s+(?:required|needed)|"
        r"what\s+you\s+offer)\b",
        re.I,
    )),
    ("preferred", re.compile(
        r"^(?:#+\s*)?"
        r"(?:preferred\s+(?:qualifications?|skills?|experience|requirements?)|"
        r"nice\s+to\s+have|bonus\s+(?:points?|if|qualifications?)|"
        r"additional\s+qualifications?|plus(?:es?)?|"
        r"preferred|ideally\s+you|you\s+may\s+also\s+have)\b",
        re.I,
    )),
    ("responsibilities", re.compile(
        r"^(?:#+\s*)?"
        r"(?:responsibilities?|what\s+you(?:'|')ll?\s+do|"
        r"the\s+role|in\s+this\s+role|what\s+you(?:'|')ll?\s+(?:be\s+doing|own)|"
        r"key\s+responsibilities?|your\s+responsibilities?|"
        r"day.to.day|primary\s+responsibilities?|core\s+responsibilities?|"
        r"what\s+success\s+looks?\s+like|"
        r"you\s+will)\b",
        re.I,
    )),
    ("culture", re.compile(
        r"^(?:#+\s*)?"
        r"(?:about\s+us|our\s+(?:culture|values?|team|mission|company)|"
        r"why\s+(?:us|join|we)|company\s+overview|who\s+we\s+are|"
        r"benefits?|perks?|compensation)\b",
        re.I,
    )),
]

_NEXT_MAJOR_SECTION_RE = re.compile(
    r"^(?:#+\s*)?[A-Z][A-Za-z\s/&,']{3,60}(?::|$)",
    re.MULTILINE,
)


def _extract_sections(jd_text: str) -> dict[str, list[str]]:
    """
    Extract text buckets by section heading.

    Returns dict with keys: required, preferred, responsibilities, culture.
    Each value is a list of bullet-like strings extracted from that section.
    """
    buckets: dict[str, list[str]] = {
        "required": [],
        "preferred": [],
        "responsibilities": [],
        "culture": [],
    }

    lines = jd_text.splitlines()
    current_bucket: str | None = None

    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue

        # Check if this line is a section header
        matched_bucket: str | None = None
        for bucket_name, header_re in _SECTION_HEADERS:
            if header_re.match(line):
                matched_bucket = bucket_name
                break

        if matched_bucket is not None:
            current_bucket = matched_bucket
            continue

        if current_bucket is None:
            continue

        # Extract meaningful bullet items (20–300 chars, starts with letter or digit)
        clean = line.lstrip("-•*◦▪▸→").strip()
        if 15 <= len(clean) <= 300 and (clean[0].isalnum() or clean[0] in '"\''):
            buckets[current_bucket].append(clean)

    return buckets


def _detect_thin_jd(jd_text: str, required_items: list) -> bool:
    """True when the JD is sparse (very short AND has almost no structured requirements).

    A JD with ≥2 extracted required items is never thin regardless of raw word count.
    Only mark thin when the JD is very short (< 80 words) OR has fewer than 2 extractable items.
    """
    if len(required_items) >= 2:
        return False
    word_count = len(re.findall(r"\w+", jd_text or ""))
    return word_count < 80


_STAGE_SIGNALS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bseries\s+[abcde]\b", re.I), "VC-backed (Series found)"),
    (re.compile(r"\bseed\s+(?:stage|funded|round)\b", re.I), "seed-stage startup"),
    (re.compile(r"\bpre.ipo\b", re.I), "pre-IPO"),
    (re.compile(r"\b(?:ipo|publicly\s+traded|nasdaq|nyse)\b", re.I), "public company"),
    (re.compile(r"\b(?:fortune\s+\d{3}|enterprise\s+saas|global\s+enterprise)\b", re.I), "enterprise/large company"),
    (re.compile(r"\b(?:startup|early.stage|growth.stage)\b", re.I), "startup / growth-stage"),
    (re.compile(r"\b(?:private\s+equity|pe.backed)\b", re.I), "PE-backed"),
]


def _detect_stage_signal(jd_text: str) -> str:
    """Return a human-readable stage signal or the standard unknown string."""
    for pat, label in _STAGE_SIGNALS:
        if pat.search(jd_text):
            return label
    return "not stated in JD text -- unknown, not inferred"


def _parse_url_and_jd(raw_text: str) -> tuple[str, str]:
    """
    Parse optional `URL: <url>` first line convention.

    Returns (url_or_empty, jd_body).
    """
    lines = raw_text.splitlines()
    if not lines:
        return "", raw_text
    first = lines[0].strip()
    if first.lower().startswith("url:"):
        url = first[4:].strip()
        body = "\n".join(lines[1:]).lstrip("\n")
        return url, body
    return "", raw_text


# ---------------------------------------------------------------------------
# Gap classification (Story 2.4)
# ---------------------------------------------------------------------------

# Generic terms that should never count as an "anchor" for a hard-skill requirement.
# Without this guard, broad tags like "compliance" could mask a gap for e.g. "HIPAA/HL7".
_GENERIC_TAG_WORDS: frozenset[str] = frozenset({
    "experience", "management", "work", "ability", "skills",
    "knowledge", "understanding", "background", "team", "product",
    "cross", "functional", "strong", "proven", "excellent",
    "ability", "deliver", "drive", "build", "lead", "grow",
})


def _item_has_anchor(item_lower: str, vocab: set[str]) -> list[str]:
    """
    Return list of matched anchor terms for *item_lower*.
    Empty list means no anchor found.
    """
    matched: list[str] = []
    for term in vocab:
        if len(term) < 4:
            continue
        if term in _GENERIC_TAG_WORDS:
            continue
        # Word-boundary match: term must appear as a complete word sequence
        pattern = r"\b" + re.escape(term) + r"\b"
        if re.search(pattern, item_lower, re.I):
            matched.append(term)
    return matched


def _classify_one_item(
    item: str,
    vocab: set[str],
) -> dict:
    """
    Classify a single required item string.

    Returns::
        {
            "item": str,
            "anchor": str,    # matched tag names or "none"
            "gap": bool,
            "gap_class": "HARD" | "SOFT" | None,
        }
    """
    item_lower = item.lower()

    # Check for hard-blocked tools first
    hard_match = _get_hard_tool_pattern().search(item_lower)
    if hard_match:
        return {
            "item": item,
            "anchor": "none",
            "gap": True,
            "gap_class": "HARD",
        }

    # Check anchor vocabulary
    anchors = _item_has_anchor(item_lower, vocab)
    if anchors:
        # Cap display to 3 most relevant tags
        display = ", ".join(sorted(set(anchors))[:3])
        return {
            "item": item,
            "anchor": f"tags: {display}",
            "gap": False,
            "gap_class": None,
        }

    # No hard tool, no anchor → soft gap (domain/methodology bridgeable)
    return {
        "item": item,
        "anchor": "none",
        "gap": True,
        "gap_class": "SOFT",
    }


def classify_gaps(
    required_items: list[str],
    preferred_items: list[str],
    vocab: set[str] | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Classify required and preferred items for gaps.

    Returns (classified_required, classified_preferred, flagged_gaps).
    flagged_gaps contains items where gap=True (HARD or SOFT).
    """
    if vocab is None:
        vocab = _load_anchor_vocab()

    classified_required: list[dict] = []
    for item in required_items:
        classified_required.append(_classify_one_item(item, vocab))

    classified_preferred: list[dict] = []
    for item in preferred_items:
        result = _classify_one_item(item, vocab)
        classified_preferred.append({
            "item": result["item"],
            "anchor": result["anchor"],
            "handling": (
                "not claimed -- not in ground truth" if result["gap"]
                else "addressed -- see resume/cover letter"
            ),
        })

    flagged_gaps: list[dict] = [
        {"item": r["item"], "gap_class": r["gap_class"]}
        for r in classified_required
        if r.get("gap")
    ]

    return classified_required, classified_preferred, flagged_gaps


# ---------------------------------------------------------------------------
# Tier determination
# ---------------------------------------------------------------------------

def _determine_tier(
    prefs_result: dict,
    flagged_gaps: list[dict],
    db_action: str,
) -> tuple[str, str]:
    """
    Return (tier, decision) based on gate results.

    tier: "Tier 1" | "Tier 2" | "Skip"
    decision: "PASS" | "SKIP"
    """
    # DB gate forces Skip
    if db_action == "reject":
        return "Skip", "SKIP"

    # Prefs gate hard reject forces Skip
    if not prefs_result.get("passed", True):
        return "Skip", "SKIP"

    # Any HARD gap forces Skip
    if any(g.get("gap_class") == "HARD" for g in flagged_gaps):
        return "Skip", "SKIP"

    # DB reapply flag or any SOFT gap → Tier 2
    if db_action == "reapply_flag" or any(g.get("gap_class") == "SOFT" for g in flagged_gaps):
        return "Tier 2", "PASS"

    return "Tier 1", "PASS"


def _build_exclusion_zone_summary(prefs_result: dict) -> str:
    """Compose a human-readable exclusion zone summary line."""
    exclusion_codes = {
        "exclusion_zone_people_management",
        "exclusion_zone_zero_to_one",
        "exclusion_zone_revenue_billing",
        "exclusion_zone_ai_ml_ownership",
        "solo_pm_trap",
    }
    hits = [r for r in prefs_result.get("rejects", []) if r["code"] in exclusion_codes]
    if not hits:
        return "clear -- no Exclusion Zone patterns detected"
    parts = [r["reason"] for r in hits]
    return "; ".join(parts)


# ---------------------------------------------------------------------------
# Main builder (Story 2.5)
# ---------------------------------------------------------------------------

def build_stage0_fit_gate(
    folder_path: str | Path,
    db_gate_result: dict | None = None,
    prefs: dict | None = None,
    vocab: set[str] | None = None,
) -> dict:
    """
    Full Stage 0 fit-gate for the submission folder at *folder_path*.

    # Implements FR-252

    Parameters
    ----------
    folder_path:
        Path to a submission folder containing Original_JD.txt.
    db_gate_result:
        Inject a pre-built DB gate result dict (used in tests to skip real DB).
        When None, calls evaluate_db_gate() from stage0_db_gate.py.
    prefs:
        Loaded candidate_preferences.json dict.  When None, loads from disk.
    vocab:
        Pre-built anchor vocabulary set.  When None, builds from disk files.

    Returns
    -------
    dict matching the live stage0_fit_gate.json shape.
    """
    folder = Path(folder_path)
    jd_file = folder / "Original_JD.txt"

    if not jd_file.exists():
        raise FileNotFoundError(f"Original_JD.txt not found in {folder}")

    raw_text = jd_file.read_text(encoding="utf-8", errors="replace")
    url, jd_text = _parse_url_and_jd(raw_text)

    # Company slug → display name
    company_slug = folder.name
    company_display = company_slug.replace("_", " ").replace("-", " ").title()

    # Role title: first substantive non-URL line of JD body
    from seniority_gate import extract_job_title_line
    role = extract_job_title_line(jd_text) or "Product Manager"

    # Load prefs
    if prefs is None:
        from utils import load_candidate_preferences
        prefs = load_candidate_preferences()

    # Load vocab
    if vocab is None:
        vocab = _load_anchor_vocab()

    # --- Step 1: DB gate ---
    if db_gate_result is None:
        from stage0_db_gate import evaluate_db_gate
        db_gate_result = evaluate_db_gate(company_display, db_path=_DEFAULT_DB)

    db_action = db_gate_result.get("action", "clear")

    # If DB says reject → write a Skip gate early, no further extraction needed
    if db_action == "reject":
        output = {
            "company": company_display,
            "role": role,
            "url": url or None,
            "decision": "SKIP",
            "tier": "Skip",
            "reach_out": False,
            "skip_reason": db_gate_result.get("reason", "DB gate reject"),
            "skip_reason_code": db_gate_result.get("reason_code", "db_reject"),
            "stage_signal": _detect_stage_signal(jd_text),
            "thin_jd": _detect_thin_jd(jd_text, []),
            "required": [],
            "preferred": [],
            "responsibilities": [],
            "culture": [],
            "flagged_gaps": [],
            "exclusion_zone_check": "n/a (skipped at DB gate)",
            "notes": db_gate_result.get("reason", "DB gate reject"),
        }
        return output

    # --- Step 2: Prefs / exclusion gate ---
    prefs_result = run_prefs_gate_safe(company_display, jd_text, prefs)

    # --- Step 3: Extract JD buckets ---
    sections = _extract_sections(jd_text)
    required_raw = sections["required"]
    preferred_raw = sections["preferred"]
    responsibilities = sections["responsibilities"]
    culture = sections["culture"]

    thin_jd = _detect_thin_jd(jd_text, required_raw)
    stage_signal = _detect_stage_signal(jd_text)

    # --- Step 4: Gap classification ---
    classified_required, classified_preferred, flagged_gaps = classify_gaps(
        required_raw, preferred_raw, vocab=vocab
    )

    # --- Step 5: Determine tier ---
    tier, decision = _determine_tier(prefs_result, flagged_gaps, db_action)

    # --- Step 6: Build skip_reason if needed ---
    skip_reason: str | None = None
    skip_reason_code: str | None = None
    if tier == "Skip":
        if not prefs_result.get("passed"):
            first_reject = prefs_result["rejects"][0]
            skip_reason = first_reject["reason"]
            skip_reason_code = first_reject["code"]
        elif any(g.get("gap_class") == "HARD" for g in flagged_gaps):
            hard_gaps = [g["item"] for g in flagged_gaps if g.get("gap_class") == "HARD"]
            skip_reason = f"Hard gap(s): {'; '.join(hard_gaps[:3])}"
            skip_reason_code = "hard_gap"

    # --- Build output ---
    exclusion_check = _build_exclusion_zone_summary(prefs_result)

    notes_parts: list[str] = []
    if db_action == "reapply_flag":
        notes_parts.append("Reapply flag from DB (prior rejections, all cooldowns expired).")
    if tier == "Tier 1":
        notes_parts.append("Clean Tier 1 pass. No flagged gaps.")
    elif tier == "Tier 2":
        soft_items = [g["item"][:60] for g in flagged_gaps if g.get("gap_class") == "SOFT"]
        if soft_items:
            notes_parts.append(f"Tier 2: soft gap(s) — {'; '.join(soft_items[:2])}.")
    elif tier == "Skip":
        if skip_reason:
            notes_parts.append(f"Skip: {skip_reason}.")

    output: dict = {
        "company": company_display,
        "role": role,
        "url": url or None,
        "decision": decision,
        "tier": tier,
        "reach_out": False,
        "stage_signal": stage_signal,
        "thin_jd": thin_jd,
        "required": classified_required,
        "preferred": classified_preferred,
        "responsibilities": responsibilities[:8],
        "culture": culture[:4],
        "flagged_gaps": flagged_gaps,
        "exclusion_zone_check": exclusion_check,
        "notes": " ".join(notes_parts) or tier,
    }

    if skip_reason:
        output["skip_reason"] = skip_reason
        output["skip_reason_code"] = skip_reason_code

    # Reapply flag annotation
    if db_action == "reapply_flag":
        output["db_reapply_flag"] = True
        output["db_reapply_note"] = db_gate_result.get("reason", "")

    return output


def run_prefs_gate_safe(company: str, jd_text: str, prefs: dict) -> dict:
    """Thin wrapper that catches import errors during tests."""
    try:
        from stage0_prefs_gate import run_prefs_gate
        return run_prefs_gate(company, jd_text, prefs)
    except Exception as exc:
        return {
            "passed": True,
            "rejects": [],
            "flags": [{"code": "prefs_gate_error", "note": str(exc)}],
        }


# ---------------------------------------------------------------------------
# CLI (Story 2.5)
# ---------------------------------------------------------------------------

def _one_line(result: dict, folder: Path) -> str:
    """Format the Tier one-liner for a single Stage 0 result."""
    tier = result.get("tier", "?")
    company = result.get("company", folder.name)
    skip_reason = result.get("skip_reason", "")
    notes = result.get("notes", "")
    gap_count = len(result.get("flagged_gaps", []))
    if skip_reason:
        line = f"{tier} — {company}: {skip_reason}"
    elif gap_count:
        line = f"{tier} — {company}: {gap_count} gap(s) — {notes}"
    else:
        line = f"{tier} — {company}: {notes}"
    return line.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
        sys.stdout.encoding or "utf-8", errors="replace"
    )


def _resolve_folder(raw: str) -> Path:
    """Resolve a slug or path to a submission-like folder with Original_JD.txt."""
    p = Path(raw)
    if p.is_dir() and (p / "Original_JD.txt").exists():
        return p
    for base in (_REPO_ROOT / "data" / "submissions", _REPO_ROOT / "data" / "pending_review"):
        cand = base / raw
        if cand.is_dir() and (cand / "Original_JD.txt").exists():
            return cand
    return p


def batch_report(folders: list[Path], write: bool = True) -> str:
    """Story 2.6 — run Stage 0 on many folders; return Markdown Tier 1/2/Skip table.

    # Implements FR-252 (batch triage without a cloud agent)
    """
    buckets: dict[str, list[str]] = {"Tier 1": [], "Tier 2": [], "Skip": []}
    for folder in folders:
        try:
            result = build_stage0_fit_gate(folder)
        except FileNotFoundError as e:
            buckets["Skip"].append(f"| {folder.name} | ERROR: {e} |")
            continue
        if write:
            out_path = folder / "stage0_fit_gate.json"
            out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        tier = result.get("tier", "Skip")
        if tier not in buckets:
            tier = "Skip"
        reason = result.get("skip_reason") or result.get("notes") or ""
        # Avoid Windows cp1252 crashes on arrows/dashes in reason strings
        reason = reason.replace("\u2192", "->").replace("\u2014", "-").replace("\u2013", "-")
        company = result.get("company", folder.name)
        buckets[tier].append(f"| {company} | {reason} |")

    parts: list[str] = []
    for header in ("Tier 1", "Tier 2", "Skip"):
        parts.append(f"### {header}")
        parts.append("")
        parts.append("| Company | Reason |")
        parts.append("|---|---|")
        if buckets[header]:
            parts.extend(buckets[header])
        else:
            parts.append("| - | none |")
        parts.append("")
    text = "\n".join(parts)
    enc = sys.stdout.encoding or "utf-8"
    return text.encode(enc, errors="replace").decode(enc, errors="replace")


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Build stage0_fit_gate.json for a submission folder (no LLM)."
    )
    parser.add_argument(
        "folder",
        nargs="*",
        help="Path(s) or slug(s) to folders containing Original_JD.txt",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print results without writing stage0_fit_gate.json",
    )
    parser.add_argument(
        "--batch-table",
        action="store_true",
        help="Print a Markdown Tier 1 / Tier 2 / Skip table for all folders (Story 2.6)",
    )
    args = parser.parse_args()

    if not args.folder:
        parser.error("at least one folder or slug is required")

    folders = [_resolve_folder(f) for f in args.folder]
    write = not args.no_write

    if args.batch_table or len(folders) > 1:
        print(batch_report(folders, write=write))
        sys.exit(0)

    folder = folders[0]
    if not folder.is_dir():
        print(f"ERROR: '{folder}' is not a directory.", file=sys.stderr)
        sys.exit(0)

    try:
        result = build_stage0_fit_gate(folder)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(0)

    if write:
        out_path = folder / "stage0_fit_gate.json"
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(_one_line(result, folder))
    sys.exit(0)


if __name__ == "__main__":
    _main()
