#!/usr/bin/env python3
"""
Build the CR-074 authoring packet for a submission folder.
# Implements FR-253

Stories 3.1–3.5: evidence mapper → excerpt slicer → packet assembler
→ hook-fact slot → CLI + size guard.
Story 4.3: rule_digest_version stamped from data/authoring_rule_digest.version.

Usage:
    python scripts/build_authoring_packet.py data/submissions/{slug}
    python scripts/build_authoring_packet.py data/submissions/{slug} --no-hook
    python scripts/build_authoring_packet.py data/submissions/{slug} --with-stage0

Requires stage0_fit_gate.json to already exist (run build_stage0_fit_gate.py first)
unless --with-stage0 is passed, which runs Stage 0 automatically first.

Exit: always 0.
Writes: authoring_packet.json
Prints: ready|incomplete — {company} — {tokens} tokens — {reason}
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_SCRIPT_DIR = Path(__file__).parent
_REPO_ROOT = _SCRIPT_DIR.parent

_CLAIMS_TAGS_PATH = _REPO_ROOT / "data" / "master_claims_tags_only.json"
_CLAIMS_FULL_PATH = _REPO_ROOT / "data" / "master_claims.json"
_WE_PATH = _REPO_ROOT / "data" / "workExperience.md"
_AI_PROJECTS_PATH = _REPO_ROOT / "data" / "aiProjects.md"

_TOKEN_BUDGET = 8000
_EXCERPT_MAX_CHARS = 500

# Preferred claim_ids per canonical employer so closed-world authoring can always
# satisfy the three-role resume rule (Cision, Sterkly, Zero To Sixty) even when
# JD ranking alone leaves a role unselected. First present, non-disabled ids win
# until _MIN_EXCERPTS_PER_CANONICAL_EMPLOYER is met.
_CANONICAL_ROLE_CLAIMS: dict[str, list[str]] = {
    "cision": [
        "ACC-101-PM",
        "ACC-102-TECH",
        "ACC-103-SEC",
        "ACC-105-AGILE",
        "ACC-104-OPS",
        "ACC-117-PENDO",
    ],
    "sterkly": [
        "ACC-203-INDUSTRY",
        "ACC-201-PROCESS",
        "ACC-202-REQUIREMENTS",
        "ACC-204-QA",
        "ACC-203-TECH",
        "ACC-204-GLOBAL",
    ],
    "zero_to_sixty": [
        "ACC-301-AUTO",
        "ACC-302-SALESFORCE",
        "ACC-303-CONVERSION",
        "ACC-301-FINANCE",
        "ACC-302-OPS",
        "ACC-303-GTM",
    ],
}
_MIN_EXCERPTS_PER_CANONICAL_EMPLOYER = 2

# When the JD names these skills/tools, force-pull a matching claim excerpt so the
# closed-world author can place the literal term without inventing history.
_JD_SKILL_ANCHORS: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(r"\bAgile\b", re.I), ["ACC-105-AGILE", "ACC-105-PROCESS"]),
    (re.compile(r"\bJira\b", re.I), ["ACC-108-SUPPORT"]),
    (re.compile(r"\bQuality Assurance\b|\bQA\b", re.I), ["ACC-204-QA"]),
    (re.compile(r"\bPendo\b", re.I), ["ACC-117-PENDO"]),
    (re.compile(r"\bSLA\b", re.I), ["ACC-101-OPS"]),
    (
        re.compile(r"\bGo[\s-]?to[\s-]?Market\b|\bGTM\b", re.I),
        ["ACC-106-GTM", "ACC-303-GTM", "ACC-104-OPS"],
    ),
    (re.compile(r"\bCustomer Support\b", re.I), ["ACC-108-SUPPORT"]),
    (re.compile(r"\bOperations\b", re.I), ["ACC-108-OPS", "ACC-201-PROCESS"]),
    (
        re.compile(r"\bUsage Data\b|\bproduct usage\b", re.I),
        ["ACC-117-PENDO"],
    ),
    (
        re.compile(r"\bAI Tools?\b|\bChatGPT\b|\bClaude\b|\bGemini\b", re.I),
        ["ACC-401-AITOOLS", "ACC-120-AIRESEARCH"],
    ),
]

# Compact geo note injected into hard_constraints (from workExperience.md §2.1).
_GEO_COLLAB_CONSTRAINT = (
    "Geographic collaboration (use selectively when the JD emphasizes remote/global work): "
    "Cision was fully remote with engineering worldwide (U.S., Budapest, India); "
    "Sterkly engineering was worldwide (U.S., Israel, India). "
    "Prefer 'worldwide' plus one country per timezone band — never list every country."
)

_RULE_DIGEST_VERSION_PATH = _REPO_ROOT / "data" / "authoring_rule_digest.version"
_RULE_DIGEST_PATH = _REPO_ROOT / "data" / "authoring_rule_digest.md"


def _load_rule_digest_version() -> str:
    """Story 4.3 — Return rule_digest_version from disk, or 'pending-epic-4' with a warning.

    Priority:
    1. data/authoring_rule_digest.version  (written by generate_authoring_rule_digest.py)
    2. sha256[:16] of data/authoring_rule_digest.md  (digest present but version file missing)
    3. 'pending-epic-4' with a stderr warning  (neither file present)
    """
    import hashlib as _hashlib  # local import avoids polluting module-level namespace

    if _RULE_DIGEST_VERSION_PATH.exists():
        v = _RULE_DIGEST_VERSION_PATH.read_text(encoding="utf-8").strip()
        if v:
            return v

    if _RULE_DIGEST_PATH.exists():
        content = _RULE_DIGEST_PATH.read_text(encoding="utf-8")
        return _hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    print(
        "WARNING: authoring_rule_digest.version not found — rule_digest_version set to "
        "'pending-epic-4'. Run scripts/generate_authoring_rule_digest.py to generate it. "
        "(Epic 5 author must require a real version before cloud compose.)",
        file=sys.stderr,
    )
    return "pending-epic-4"


# Fixed hard constraints restated from AGENTS.md / RULES.md for cloud author.
_HARD_CONSTRAINTS: list[str] = [
    "Use only claim_ids listed in excerpts; never invent metrics, tools, companies, or facts.",
    "Resume structure: exact ## PROFESSIONAL SUMMARY / ## PROFESSIONAL EXPERIENCE / ## EDUCATION headings; exactly 3 summary sentences; all three canonical roles present (Cision, Sterkly, Zero To Sixty).",
    "Cover letter: argue fit only — no gap-confession language; no em dashes (—), semicolons, or double-hyphen (--); no bullet points; 250–400 words.",
    "No people-management claims, no titles above Senior IC PM, no AI/ML model ownership, no revenue/billing ownership.",
    "No internal codenames: use plain-English VOC translations (e.g. 'Airo' → 'a macOS security product', 'Platform Data Remediation' → 'centralized platform data remediation initiative').",
    "Do not copy excerpt sentences verbatim — author fresh prose from the facts.",
    "Forbidden words: 'leverage', 'passionate', 'driven', 'dynamic', 'innovative', 'seamless', 'transformative', 'proven track record', 'layoffs'.",
    _GEO_COLLAB_CONSTRAINT,
]


# ---------------------------------------------------------------------------
# Story 3.1 — Evidence Mapper helpers
# ---------------------------------------------------------------------------

def load_claims(
    claims_tags_path: Path | None = None,
    claims_full_path: Path | None = None,
) -> tuple[dict[str, dict], set[str]]:
    """Load claims from master_claims_tags_only.json; identify disabled IDs from master_claims.json.

    Returns (claims_by_id, disabled_ids_set).
    """
    tags_path = claims_tags_path or _CLAIMS_TAGS_PATH
    full_path = claims_full_path or _CLAIMS_FULL_PATH

    claims: dict[str, dict] = {}
    if tags_path.exists():
        try:
            claims = json.loads(tags_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    disabled: set[str] = set()
    if full_path.exists():
        try:
            full = json.loads(full_path.read_text(encoding="utf-8"))
            for cid, rec in full.items():
                if isinstance(rec, dict) and rec.get("disabled"):
                    disabled.add(cid)
        except Exception:
            pass
    else:
        # Fallback: check tags-only for disabled field (in case it was included)
        for cid, rec in claims.items():
            if isinstance(rec, dict) and rec.get("disabled"):
                disabled.add(cid)

    return claims, disabled


def _claim_text_for_scoring(cid: str, rec: dict) -> str:
    """Build a text string suitable for score_claim_for_jd from a claim record."""
    parts: list[str] = []
    # Include the claim ID words
    parts.extend(re.findall(r"[A-Za-z]+", cid))
    employer = rec.get("employer") or ""
    if employer:
        parts.append(employer)
    lens = rec.get("lens") or ""
    if lens:
        parts.extend(lens.replace("_", " ").split())
    for tag in rec.get("tags") or []:
        parts.append(str(tag))
    for m in rec.get("metrics") or []:
        parts.append(str(m))
    return " ".join(parts)


def _score_claims_for_item(
    item_text: str,
    claims: dict[str, dict],
    disabled: set[str],
    jd_profile: Any,
    jd_text: str,
) -> list[tuple[str, int]]:
    """Score all active claims for a single JD item, return (cid, score) sorted desc.

    Scoring strategy: item-specific tag overlap is the PRIMARY signal (most
    useful for pairing a specific requirement with the most relevant claim).
    The full-JD score from score_claim_for_jd is a SECONDARY tiebreaker.
    This prevents high-JD-relevance but low-item-relevance claims from winning
    every item uniformly.

    Uses score_claim_for_jd from jd_tailoring.py when available; falls back to
    pure overlap scoring so tests can inject a mocked scorer.
    """
    try:
        from jd_tailoring import score_claim_for_jd  # type: ignore
        use_jd_scorer = True
    except ImportError:
        use_jd_scorer = False

    # Item-specific word overlap — primary signal
    item_words = set(re.findall(r"[a-z]{4,}", item_text.lower()))

    scored: list[tuple[str, int]] = []
    for cid, rec in claims.items():
        if cid in disabled:
            continue
        ct = _claim_text_for_scoring(cid, rec)
        tag_words = set(re.findall(r"[a-z]{4,}", ct.lower()))

        # Primary: item-specific overlap (weighted heavily)
        overlap = len(item_words & tag_words)

        # Secondary: full-JD scorer as tiebreaker
        if use_jd_scorer and jd_profile is not None:
            jd_score = score_claim_for_jd(ct, jd_profile, jd_text)
        else:
            jd_score = overlap

        # Combined: overlap dominates; jd_score breaks ties
        total = overlap * 1000 + jd_score
        scored.append((cid, total))

    scored.sort(key=lambda x: (-x[1], x[0]))
    return scored


def _stage0_item_text(entry: Any) -> str:
    """Normalize Stage 0 list entries (legacy bare strings or CR-074 dicts)."""
    if isinstance(entry, str):
        return entry.strip()
    if isinstance(entry, dict):
        return str(entry.get("item") or entry.get("text") or "").strip()
    return ""


def build_evidence_map(
    stage0: dict,
    jd_text: str,
    claims: dict[str, dict],
    disabled: set[str],
    jd_profile: Any = None,
) -> list[dict]:
    """Story 3.1 — Map JD items to strongest claim IDs.

    Covers required, preferred, and responsibilities buckets.
    Soft-gap bridge notes from stage0 are attached to required rows.
    Accepts both CR-074 dict items (`{item, ...}`) and legacy bare strings.
    """
    # Build a soft-gap bridge lookup from flagged_gaps + required item bridges
    soft_gap_bridges: dict[str, str] = {}
    for gap in stage0.get("flagged_gaps", []):
        if not isinstance(gap, dict):
            continue
        item = gap.get("item", "")
        if not item:
            continue
        bridge = gap.get("bridge_used") or gap.get("bridge") or ""
        soft_gap_bridges[item] = bridge

    # Also collect bridge text from required items directly (human-curated format)
    for req in stage0.get("required", []):
        if not isinstance(req, dict):
            continue
        item = req.get("item", "")
        if item and not soft_gap_bridges.get(item):
            bridge = req.get("bridge") or ""
            if bridge:
                soft_gap_bridges[item] = bridge

    def _map_item(item_text: str, bucket: str, is_required: bool = False) -> dict:
        scored = _score_claims_for_item(item_text, claims, disabled, jd_profile, jd_text)
        # Pick top 2 with score > 0
        top = [cid for cid, score in scored[:2] if score > 0]

        bridge: str | None = None
        if is_required and item_text in soft_gap_bridges:
            raw_bridge = soft_gap_bridges[item_text]
            bridge = raw_bridge or "Soft gap — transferable-skill bridge; see soft_gaps for detail."

        return {
            "jd_item": item_text,
            "bucket": bucket,
            "claim_ids": top,
            "bridge": bridge,
        }

    evidence_map: list[dict] = []

    for req in stage0.get("required", []):
        item = _stage0_item_text(req)
        if not item:
            continue
        evidence_map.append(_map_item(item, "required", is_required=True))

    for pref in stage0.get("preferred", []):
        item = _stage0_item_text(pref)
        if not item:
            continue
        evidence_map.append(_map_item(item, "preferred"))

    for resp in stage0.get("responsibilities", []):
        item = _stage0_item_text(resp)
        if not item:
            continue
        evidence_map.append(_map_item(item, "responsibilities"))

    return evidence_map


# ---------------------------------------------------------------------------
# Story 3.2 — Excerpt Slicer
# ---------------------------------------------------------------------------

def _load_source_texts(
    we_path: Path | None = None,
    ai_path: Path | None = None,
) -> tuple[str, str]:
    """Load workExperience.md and aiProjects.md as strings."""
    we = (we_path or _WE_PATH)
    ai = (ai_path or _AI_PROJECTS_PATH)
    we_text = we.read_text(encoding="utf-8", errors="replace") if we.exists() else ""
    ai_text = ai.read_text(encoding="utf-8", errors="replace") if ai.exists() else ""
    return we_text, ai_text


def _strip_markdown_decoration(text: str) -> str:
    """Remove common Markdown syntax to produce readable plain text."""
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"`{1,3}", "", text)
    text = re.sub(r"\[([^\]]+)\]", r"\1", text)  # keep link text, drop []()
    text = re.sub(r"\([^)]*\)", "", text)          # drop (url) part
    text = re.sub(r"^\s*[-•*◦▪▸]\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _is_thin_synthetic_excerpt(excerpt: str) -> bool:
    """True for tag-pipe fallbacks like 'ACC-113 (cision) | Product Adoption · ...'."""
    return bool(re.match(r"^ACC-\d+\s*\([^)]+\)\s*\|", (excerpt or "").strip()))


def _extract_excerpt_for_project(
    project_id: str,
    we_text: str,
    ai_text: str,
    claim_rec: dict,
    max_chars: int = _EXCERPT_MAX_CHARS,
) -> str:
    """Extract a bounded ground-truth excerpt for project_id.

    ACC-401: uses aiProjects.md (no bracket marker in workExperience.md).
    All others: searches workExperience.md for [ACC-NNN] bracket pattern,
    falls back to bare ACC-NNN, then synthesizes from tags if still not found.
    Never dumps the full source file.
    """
    if project_id == "ACC-401":
        if ai_text:
            # Take from the first substantive heading onward
            m = re.search(r"^## ", ai_text, re.MULTILINE)
            start = m.start() if m else 0
            raw = ai_text[start: start + max_chars]
            return _strip_markdown_decoration(raw)[:max_chars]
        return _synthetic_excerpt(project_id, claim_rec)

    # Try [ACC-NNN] bracket pattern first
    bracket_pat = f"[{project_id}]"
    idx = we_text.find(bracket_pat)

    if idx < 0:
        # Try bare code without brackets
        bare_m = re.search(rf"\b{re.escape(project_id)}\b", we_text)
        idx = bare_m.start() if bare_m else -1

    if idx < 0:
        return _synthetic_excerpt(project_id, claim_rec)

    # Capture from the start of the bullet line
    line_start = we_text.rfind("\n", 0, idx)
    line_start = (line_start + 1) if line_start >= 0 else 0

    raw_chunk = we_text[line_start: line_start + max_chars + 200]

    # Clip at next [ACC-NNN] marker (skip current tag which is at position 0)
    next_m = re.search(r"\[ACC-\d+\]", raw_chunk[len(bracket_pat):])
    if next_m:
        raw_chunk = raw_chunk[: len(bracket_pat) + next_m.start()]

    # Clip at blank line (end of bullet block)
    blank_m = re.search(r"\n\s*\n", raw_chunk)
    if blank_m:
        raw_chunk = raw_chunk[: blank_m.start()]

    clean = _strip_markdown_decoration(raw_chunk)
    return clean[:max_chars]


def _synthetic_excerpt(project_id: str, claim_rec: dict) -> str:
    """Fallback excerpt built from claim metadata when source text is unavailable."""
    tags = claim_rec.get("tags") or []
    metrics = claim_rec.get("metrics") or []
    employer = claim_rec.get("employer") or ""
    parts = [project_id]
    if employer:
        parts.append(f"({employer})")
    if tags:
        parts.append("| " + " · ".join(str(t) for t in tags))
    if metrics:
        parts.append("| metrics: " + ", ".join(str(m) for m in metrics))
    return " ".join(parts)


def _employer_excerpt_counts(
    excerpts: dict[str, str], claims: dict[str, dict]
) -> dict[str, int]:
    """Count how many excerpt claim_ids belong to each employer."""
    counts: dict[str, int] = {}
    for cid in excerpts:
        emp = (claims.get(cid) or {}).get("employer") or ""
        if emp:
            counts[emp] = counts.get(emp, 0) + 1
    return counts


def _employers_covered(excerpts: dict[str, str], claims: dict[str, dict]) -> set[str]:
    """Return employer keys present among excerpt claim_ids."""
    return set(_employer_excerpt_counts(excerpts, claims))


def _ensure_canonical_role_excerpts(
    excerpts: dict[str, str],
    claims: dict[str, dict],
    we_text: str,
    ai_text: str,
    disabled: set[str] | None = None,
) -> dict[str, str]:
    """Guarantee enough excerpts per canonical career-history employer.

    JD-ranked evidence can omit Zero To Sixty (or another role) entirely; the
    author then cannot invent bullets under closed-world rules, and LR-020/021 fail.
    Also tops up thin roles to at least _MIN_EXCERPTS_PER_CANONICAL_EMPLOYER claims
    so earlier roles can support the required 2–3 bullets.
    """
    disabled = disabled or set()
    counts = _employer_excerpt_counts(excerpts, claims)
    for employer, preferred_ids in _CANONICAL_ROLE_CLAIMS.items():
        while counts.get(employer, 0) < _MIN_EXCERPTS_PER_CANONICAL_EMPLOYER:
            added = False
            for cid in preferred_ids:
                if cid in disabled or cid not in claims or cid in excerpts:
                    continue
                rec = claims[cid]
                project_id = rec.get("project_id") or cid
                excerpt = _extract_excerpt_for_project(project_id, we_text, ai_text, rec)
                if excerpt:
                    excerpts[cid] = excerpt
                    counts[employer] = counts.get(employer, 0) + 1
                    added = True
                    break
            if not added:
                break
    return excerpts


def _ensure_jd_skill_anchor_excerpts(
    excerpts: dict[str, str],
    claims: dict[str, dict],
    we_text: str,
    ai_text: str,
    jd_text: str,
    disabled: set[str] | None = None,
) -> dict[str, str]:
    """Pull claim excerpts for JD-named skills so literal terms stay closed-world."""
    if not jd_text:
        return excerpts
    disabled = disabled or set()
    for pattern, preferred_ids in _JD_SKILL_ANCHORS:
        if not pattern.search(jd_text):
            continue
        if any(cid in excerpts for cid in preferred_ids):
            continue
        for cid in preferred_ids:
            if cid in disabled or cid not in claims:
                continue
            rec = claims[cid]
            project_id = rec.get("project_id") or cid
            excerpt = _extract_excerpt_for_project(project_id, we_text, ai_text, rec)
            if excerpt:
                excerpts[cid] = excerpt
                break
    return excerpts


def build_excerpts(
    evidence_map: list[dict],
    claims: dict[str, dict],
    we_text: str,
    ai_text: str,
    disabled: set[str] | None = None,
    jd_text: str = "",
) -> dict[str, str]:
    """Story 3.2 — Pull bounded excerpts for evidence_map + role/skill floors."""
    excerpts: dict[str, str] = {}
    for row in evidence_map:
        for cid in row.get("claim_ids") or []:
            if cid in excerpts:
                continue
            rec = claims.get(cid, {})
            project_id = rec.get("project_id") or cid
            excerpt = _extract_excerpt_for_project(project_id, we_text, ai_text, rec)
            if excerpt and not _is_thin_synthetic_excerpt(excerpt):
                excerpts[cid] = excerpt
            elif excerpt and cid not in excerpts:
                excerpts[cid] = excerpt

    excerpts = _ensure_canonical_role_excerpts(
        excerpts, claims, we_text, ai_text, disabled=disabled
    )

    # Prefer narrative excerpts over tag-pipe synthetic fallbacks.
    narrative_projects = {
        (claims.get(cid) or {}).get("project_id") or cid
        for cid, ex in excerpts.items()
        if not _is_thin_synthetic_excerpt(ex)
    }
    for cid in list(excerpts):
        if not _is_thin_synthetic_excerpt(excerpts[cid]):
            continue
        project_id = (claims.get(cid) or {}).get("project_id") or cid
        if project_id not in narrative_projects:
            continue
        del excerpts[cid]
        for row in evidence_map:
            ids = row.get("claim_ids") or []
            if cid in ids:
                row["claim_ids"] = [x for x in ids if x != cid]

    return _ensure_jd_skill_anchor_excerpts(
        excerpts, claims, we_text, ai_text, jd_text, disabled=disabled
    )


# ---------------------------------------------------------------------------
# Story 3.3 — Packet Assembler + fail-closed checker
# ---------------------------------------------------------------------------

def _check_fail_closed(
    stage0: dict,
    evidence_map: list[dict],
    excerpts: dict[str, str],
    disabled: set[str],
    estimated_tokens: int,
) -> tuple[str, list[str]]:
    """Apply fail-closed rules from authoring_packet_RULES.md.

    Returns (packet_status, incomplete_reasons).
    """
    reasons: list[str] = []

    # Rule 1: Skip tier
    tier = stage0.get("tier", "")
    if tier == "Skip":
        reasons.append("Tier is Skip — no drafting allowed.")

    # Rule 2: Required item unmapped (empty claim_ids AND bridge null/empty)
    required_items = {
        item for item in (_stage0_item_text(r) for r in stage0.get("required", []))
        if item
    }
    mapped_required = {
        row["jd_item"]
        for row in evidence_map
        if row.get("bucket") == "required"
        and (row.get("claim_ids") or row.get("bridge"))
    }
    unmapped = required_items - mapped_required
    for item in sorted(unmapped):
        reasons.append(f"Required item unmapped (no claims, no bridge): {item[:80]}")

    # Rule 3: Disabled claim selected
    all_selected_ids: set[str] = set()
    for row in evidence_map:
        all_selected_ids.update(row.get("claim_ids") or [])
    all_selected_ids.update(excerpts.keys())
    for cid in sorted(all_selected_ids & disabled):
        reasons.append(f"Disabled claim selected: {cid}")

    # Rule 4: claim_id in evidence_map but no excerpt
    for row in evidence_map:
        for cid in row.get("claim_ids") or []:
            if cid not in disabled and not excerpts.get(cid):
                reasons.append(f"Missing excerpt for claim: {cid}")

    # Rule 5: Over budget
    if estimated_tokens > _TOKEN_BUDGET:
        reasons.append(f"Over token budget: {estimated_tokens} > {_TOKEN_BUDGET}")

    status = "incomplete" if reasons else "ready"
    return status, reasons


def _build_soft_gaps(stage0: dict) -> list[dict]:
    """Build soft_gaps list from stage0 flagged_gaps."""
    soft_gaps: list[dict] = []
    for gap in stage0.get("flagged_gaps", []):
        item = gap.get("item", "")
        if not item:
            continue
        gap_class = gap.get("gap_class", "SOFT")
        note = (
            gap.get("bridge_used")
            or gap.get("bridge")
            or "Soft gap flagged at Stage 0; argue as transferable-skill fit in cover letter."
        )
        soft_gaps.append({"item": item, "class": gap_class, "note": note})
    return soft_gaps


def _build_jd_buckets(stage0: dict) -> dict:
    """Extract jd_buckets from stage0 in the packet schema shape."""
    required = [
        item for item in (_stage0_item_text(r) for r in stage0.get("required", []))
        if item
    ]
    preferred = [
        item for item in (_stage0_item_text(p) for p in stage0.get("preferred", []))
        if item
    ]
    responsibilities = [
        item for item in (_stage0_item_text(r) for r in stage0.get("responsibilities", []))
        if item
    ]
    culture = [
        item for item in (_stage0_item_text(c) for c in stage0.get("culture", []))
        if item
    ]
    return {
        "required": required,
        "preferred": preferred,
        "responsibilities": responsibilities,
        "culture": culture,
    }


def assemble_packet(
    stage0: dict,
    evidence_map: list[dict],
    excerpts: dict[str, str],
    disabled: set[str],
    hook_fact: dict | None,
    company: str,
    role_title: str,
    slug: str,
    url: str | None,
) -> dict:
    """Story 3.3 — Assemble the full authoring_packet dict matching schema v1.0."""
    tier = stage0.get("tier", "Tier 1")
    reach_out = stage0.get("reach_out", False)
    stage_signal = stage0.get("stage_signal") or None
    thin_jd = bool(stage0.get("thin_jd", False))

    jd_buckets = _build_jd_buckets(stage0)
    soft_gaps = _build_soft_gaps(stage0)

    # Compute estimated_tokens before status check
    # Build a draft packet without status for size estimation
    draft = {
        "schema_version": "1.0",
        "company": company,
        "role_title": role_title,
        "slug": slug,
        "url": url,
        "tier": tier,
        "reach_out": reach_out,
        "jd_buckets": jd_buckets,
        "evidence_map": evidence_map,
        "excerpts": excerpts,
        "soft_gaps": soft_gaps,
        "hard_constraints": _HARD_CONSTRAINTS,
        "hook_fact": hook_fact,
        "rule_digest_version": _load_rule_digest_version(),  # Story 4.3
        "packet_status": "ready",
        "incomplete_reasons": [],
        "estimated_tokens": 0,
        "stage_signal": stage_signal,
        "thin_jd": thin_jd,
    }
    # estimated_tokens from utf-8 bytes / 4
    estimated_tokens = len(json.dumps(draft, ensure_ascii=False).encode("utf-8")) // 4

    # Run fail-closed checks
    status, reasons = _check_fail_closed(stage0, evidence_map, excerpts, disabled, estimated_tokens)

    draft["packet_status"] = status
    draft["incomplete_reasons"] = reasons
    draft["estimated_tokens"] = estimated_tokens

    return draft


# ---------------------------------------------------------------------------
# Story 3.4 — Hook-fact slot
# ---------------------------------------------------------------------------

def get_hook_fact(
    company: str,
    role_title: str,
    tier: str,
    reach_out: bool,
    no_hook: bool = False,
) -> dict | None:
    """Story 3.4 — Attempt to retrieve a hook fact from research-engine.py.

    Only runs for Tier 1 or (Tier 2 AND reach_out is True).
    On any failure or --no-hook: returns None.
    Never puts raw HTML in the packet.
    """
    if no_hook:
        return None
    if not (tier == "Tier 1" or (tier == "Tier 2" and reach_out)):
        return None

    research_script = _SCRIPT_DIR / "research-engine.py"
    if not research_script.exists():
        return None

    try:
        python = sys.executable
        result = subprocess.run(
            [python, str(research_script), "--hook-fact", company, role_title],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            raw = result.stdout.strip()
            # Strip any HTML tags that might have leaked through
            raw = re.sub(r"<[^>]+>", "", raw)
            raw = raw.strip()
            if raw:
                return {"text": raw[:500], "source_url": None, "fetched_at": None}
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Story 3.5 — Main builder + CLI
# ---------------------------------------------------------------------------

_SENTINEL = object()  # used as a "not provided" sentinel for hook_fact_override


def build_packet(
    folder_path: str | Path,
    no_hook: bool = False,
    claims_override: dict | None = None,
    disabled_override: set[str] | None = None,
    we_text_override: str | None = None,
    ai_text_override: str | None = None,
    jd_profile_override: Any = None,
    hook_fact_override: Any = _SENTINEL,
) -> dict:
    """Build the authoring packet for the given submission folder.

    # Implements FR-253

    Parameters
    ----------
    folder_path:
        Path to a submission folder containing stage0_fit_gate.json
        (and preferably Original_JD.txt for JD-profile scoring).
    no_hook:
        Skip the hook-fact research call entirely.
    *_override:
        Injection points used by tests to avoid real disk/network I/O.
    """
    folder = Path(folder_path)
    stage0_path = folder / "stage0_fit_gate.json"
    if not stage0_path.exists():
        raise FileNotFoundError(f"stage0_fit_gate.json not found in {folder}")

    stage0 = json.loads(stage0_path.read_text(encoding="utf-8"))

    # Load JD text for scoring (best-effort — gracefully skip if missing)
    jd_text = ""
    jd_file = folder / "Original_JD.txt"
    if jd_file.exists():
        raw = jd_file.read_text(encoding="utf-8", errors="replace")
        # Strip optional `URL: ...` first line
        lines = raw.splitlines()
        if lines and lines[0].strip().lower().startswith("url:"):
            jd_text = "\n".join(lines[1:]).lstrip()
        else:
            jd_text = raw

    # Build JD profile for scoring (deterministic, no LLM)
    jd_profile = jd_profile_override
    if jd_profile is None and jd_text:
        try:
            from jd_tailoring import build_jd_profile_deterministic  # type: ignore
            jd_profile = build_jd_profile_deterministic(jd_text)
        except Exception:
            jd_profile = None

    # Metadata
    company = stage0.get("company") or folder.name.replace("_", " ").replace("-", " ").title()
    role_title = (
        stage0.get("role")
        or stage0.get("role_title")
        or stage0.get("position")
        or "Product Manager"
    )
    slug = folder.name
    url = stage0.get("url") or None

    # Load claims and disabled set
    claims, disabled = (claims_override, disabled_override or set()) if claims_override is not None \
        else load_claims()

    # Load source texts
    we_text: str
    ai_text: str
    if we_text_override is not None:
        we_text, ai_text = we_text_override, (ai_text_override or "")
    else:
        we_text, ai_text = _load_source_texts()

    # Story 3.1 — Evidence map
    evidence_map = build_evidence_map(stage0, jd_text, claims, disabled, jd_profile)

    # Story 3.2 — Excerpts (evidence map + canonical-role floor + JD skill anchors)
    excerpts = build_excerpts(
        evidence_map, claims, we_text, ai_text, disabled=disabled, jd_text=jd_text
    )

    # Story 3.4 — Hook fact
    if hook_fact_override is not _SENTINEL:
        hook_fact = hook_fact_override
    else:
        tier = stage0.get("tier", "Tier 1")
        reach_out = bool(stage0.get("reach_out", False))
        hook_fact = get_hook_fact(company, role_title, tier, reach_out, no_hook=no_hook)

    # Story 3.3 — Assemble packet
    packet = assemble_packet(
        stage0=stage0,
        evidence_map=evidence_map,
        excerpts=excerpts,
        disabled=disabled,
        hook_fact=hook_fact,
        company=company,
        role_title=role_title,
        slug=slug,
        url=url,
    )

    return packet


def _one_line(packet: dict, folder: Path) -> str:
    """Format the CLI summary line."""
    status = packet.get("packet_status", "incomplete")
    company = packet.get("company", folder.name)
    tokens = packet.get("estimated_tokens", 0)
    reasons = packet.get("incomplete_reasons") or []
    reason_str = reasons[0] if reasons else "all checks passed"
    line = f"{status} — {company} — {tokens} tokens — {reason_str}"
    # Safe encode for Windows consoles
    enc = sys.stdout.encoding or "utf-8"
    return line.encode(enc, errors="replace").decode(enc, errors="replace")


def _resolve_folder(raw: str) -> Path:
    p = Path(raw)
    if p.is_dir():
        return p
    for base in (_REPO_ROOT / "data" / "submissions", _REPO_ROOT / "data" / "context_pack_validation"):
        cand = base / raw
        if cand.is_dir():
            return cand
    return p


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Build authoring_packet.json for a submission folder (CR-074 Epic 3).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/build_authoring_packet.py data/submissions/limble
  python scripts/build_authoring_packet.py data/submissions/limble --no-hook
  python scripts/build_authoring_packet.py data/submissions/limble --with-stage0
""",
    )
    parser.add_argument("folder", help="Path or slug to a submission folder.")
    parser.add_argument(
        "--no-hook",
        action="store_true",
        help="Skip the optional hook-fact research call.",
    )
    parser.add_argument(
        "--with-stage0",
        action="store_true",
        help="Run build_stage0_fit_gate.py automatically if stage0_fit_gate.json is missing.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print result without writing authoring_packet.json.",
    )
    args = parser.parse_args()

    folder = _resolve_folder(args.folder)
    if not folder.is_dir():
        print(f"ERROR: '{folder}' is not a directory.", file=sys.stderr)
        sys.exit(0)

    stage0_path = folder / "stage0_fit_gate.json"
    if not stage0_path.exists():
        if args.with_stage0:
            print("stage0_fit_gate.json missing — running build_stage0_fit_gate.py first...", file=sys.stderr)
            try:
                result = subprocess.run(
                    [sys.executable, str(_SCRIPT_DIR / "build_stage0_fit_gate.py"), str(folder)],
                    timeout=60,
                )
                if result.returncode != 0 or not stage0_path.exists():
                    print("ERROR: build_stage0_fit_gate.py failed.", file=sys.stderr)
                    sys.exit(0)
            except Exception as exc:
                print(f"ERROR running Stage 0: {exc}", file=sys.stderr)
                sys.exit(0)
        else:
            print(
                f"ERROR: stage0_fit_gate.json not found in {folder}. "
                "Run build_stage0_fit_gate.py first, or pass --with-stage0.",
                file=sys.stderr,
            )
            sys.exit(0)

    try:
        packet = build_packet(folder, no_hook=args.no_hook)
    except Exception as exc:
        print(f"ERROR building packet: {exc}", file=sys.stderr)
        sys.exit(0)

    if not args.no_write:
        out_path = folder / "authoring_packet.json"
        out_path.write_text(json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8")

    print(_one_line(packet, folder))
    sys.exit(0)


if __name__ == "__main__":
    _main()
