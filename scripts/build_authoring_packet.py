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

Exit: 0 on success (and on most non-gate errors, preserved from CR-074).
Exit: non-zero when the Stage 0 readiness gate fails (missing or structurally invalid
stage0_fit_gate.json) unless --force is passed (CR-075 AC2). --force is logged to
data/.force_override_log.json.
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

from stage_gate import StageGateNotReadyError, add_force_args, require_stage_ready  # noqa: E402
from build_stage0_fit_gate import _is_administratively_satisfied  # noqa: E402

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

# CR-085: cap how many evidence_map rows a single underlying project can win, so one
# strong story can't monopolize unrelated requirements. Real measured cases before this
# cap: ACC-104-CS in 14/18 rows (Thermo Fisher), ACC-113-ADOPTION in 5/10 and 5/8 rows
# (Limble, Paylocity) across genuinely unrelated requirements. Applied globally across
# the whole evidence_map, not per-item — each row still picks from its own ranked
# candidate list, so a capped-out claim is replaced by that row's own next-best match,
# never an unrelated claim forced in just to fill a slot.
_MAX_SLOTS_PER_PROJECT = 3

# CR-085: short, explicit, conservative boilerplate phrase list. Generic JD lines that
# carry no evidence-worthy signal still consumed a full 67-claim scoring pass and an
# evidence_map row before this. Deliberately narrow (substring match, not a classifier)
# to keep false-positive risk low, and NEVER applied to the `required` bucket — the
# fail-closed gate's unmapped-required-item rule must stay authoritative.
_BOILERPLATE_PHRASES: tuple[str, ...] = (
    "excellent communication skills",
    "strong communication skills",
    "excellent written and verbal communication",
    "team player",
    "self-starter",
    "self starter",
    "fast-paced environment",
    "fast paced environment",
    "wear multiple hats",
    "detail-oriented",
    "detail oriented",
    "positive attitude",
    "work independently and collaboratively",
    "ability to multitask",
    "strong work ethic",
)


def _is_boilerplate_item(item_text: str) -> bool:
    """True for generic, non-differentiating JD lines (Part 10's 'don't spend equal
    evidence budget on communicate effectively and lead migration of a mission-critical
    platform' idea). Never call this on a `required` item.
    """
    text_l = (item_text or "").strip().lower()
    if not text_l:
        return False
    return any(phrase in text_l for phrase in _BOILERPLATE_PHRASES)

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


# CR-085 Phase 1: trimmed from 8 items to 2. The other 6 (resume/cover-letter structure,
# exclusion zones, VOC translations, forbidden words) are verified line-for-line redundant
# with authoring_rule_digest.md sections 2/3/4/5/8/9, which is loaded into every author
# session alongside this packet — repeating them here cost ~245 tokens (~9% of a real
# packet) for content the author already has. Only the verbatim-copy rule and the geo note
# are genuinely packet-specific / not already in the digest.
_HARD_CONSTRAINTS: list[str] = [
    "Do not copy excerpt sentences verbatim — author fresh prose from the facts. This applies "
    "even when an excerpt is a short, clean claim description (master_claims.json's `text` "
    "field) — it is grounding evidence, not draftable prose.",
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

    CR-085: also merges each claim's lens-specific `text` field from the full catalog into
    the returned record (e.g. ACC-101-TECH's own text, distinct from ACC-101-PM's). This lets
    excerpt retrieval use the claim's own clean, bounded description instead of regex-slicing
    workExperience.md by project_id — which is also what was producing byte-identical excerpts
    across a project's different lenses (only one [ACC-NNN] marker per project in WE, so every
    lens fell back to the same slice). `text` is grounding evidence for the closed-world author,
    not draftable prose — the "do not copy verbatim" hard constraint already covers that.

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
    full: dict = {}
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

    for cid, rec in claims.items():
        full_rec = full.get(cid)
        if isinstance(full_rec, dict):
            text = full_rec.get("text")
            if isinstance(text, str) and text.strip():
                rec["text"] = text.strip()

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


# CR-087: tokens that must not drive item↔claim overlap. One shared generic word
# (e.g. "team" from "Cross-Team Learning") was enough to score ACC-120 at 1015 against
# an unrelated Camunda epics-staffing line via overlap*1000. Keep this list short and
# boring — distinctive domain tokens (agile, migration, privacy, epics, …) still count.
_GENERIC_OVERLAP_TOKENS: frozenset[str] = frozenset(
    {
        "able",
        "about",
        "across",
        "after",
        "also",
        "appropriate",
        "based",
        "been",
        "before",
        "between",
        "during",
        "equipped",
        "excellent",
        "experience",
        "from",
        "good",
        "have",
        "help",
        "helping",
        "high",
        "include",
        "including",
        "into",
        "keep",
        "kept",
        "make",
        "made",
        "managed",
        "more",
        "most",
        "only",
        "other",
        "others",
        "over",
        "product",
        "products",
        "related",
        "role",
        "roles",
        "same",
        "self",
        "skills",
        "some",
        "strong",
        "such",
        "team",
        "teams",
        "than",
        "that",
        "their",
        "them",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "under",
        "used",
        "using",
        "well",
        "what",
        "when",
        "where",
        "which",
        "while",
        "will",
        "with",
        "within",
        "work",
        "working",
        "years",
    }
)


def _distinctive_overlap(item_words: set[str], claim_words: set[str]) -> set[str]:
    """CR-087 — item↔claim token intersection after dropping generic fillers."""
    return {w for w in (item_words & claim_words) if w not in _GENERIC_OVERLAP_TOKENS}


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

    CR-087: overlap ignores generic tokens; jd_score alone (no distinctive overlap
    and no capability_boost) cannot nominate a claim into Top-2.

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

        # Primary: distinctive item-specific overlap (weighted heavily)
        overlap_words = _distinctive_overlap(item_words, tag_words)
        overlap = len(overlap_words)

        # Soft-gap capability boost: when the JD item names compliance/privacy/
        # regulatory work, prefer claims whose *primary* theme is that capability
        # (ACC-107/112-class) over security/ops claims that merely list Compliance
        # as a secondary tag.
        capability_boost = 0
        capability_tokens = {"compliance", "privacy", "regulatory", "gdpr", "ccpa"}
        if item_words & capability_tokens:
            tags_lower = [str(t).lower() for t in (rec.get("tags") or [])]
            claim_tag_blob = " ".join(tags_lower)
            cid_l = cid.lower()
            if any(tok in claim_tag_blob for tok in capability_tokens):
                capability_boost = 5000
            # Primary compliance/privacy claims outrank secondary-tag matches
            if any(
                t in {"compliance", "privacy", "gdpr/ccpa", "gdpr", "ccpa"}
                for t in tags_lower
            ) and (
                "privacy" in claim_tag_blob
                or "gdpr" in claim_tag_blob
                or "107" in cid_l
                or "112" in cid_l
                or "compliance" in cid_l
            ):
                capability_boost += 8000

        # AI/ML product experience soft gaps → ACC-120 (CONTRIBUTED joint research),
        # never invent model-ownership claims. Match short tokens in raw item text
        # (item_words only keeps length>=4, so "AI"/"ML" would otherwise miss).
        item_l = item_text.lower()
        if re.search(r"\b(ai|ml|ai/ml|machine\s+learning|llm)\b", item_l):
            cid_l = cid.lower()
            tags_lower = [str(t).lower() for t in (rec.get("tags") or [])]
            claim_tag_blob = " ".join(tags_lower)
            if (
                "120" in cid_l
                or "airesearch" in cid_l
                or "ai" in claim_tag_blob
                or "prompt" in claim_tag_blob
            ):
                capability_boost += 12000

        # Secondary: full-JD scorer as tiebreaker
        if use_jd_scorer and jd_profile is not None:
            jd_score = score_claim_for_jd(ct, jd_profile, jd_text)
        else:
            jd_score = overlap

        # Combined: capability boost + overlap dominate; jd_score breaks ties
        total = capability_boost + overlap * 1000 + jd_score
        # CR-087: full-JD score alone must not put a claim into Top-2 when the item
        # shares no distinctive tokens and no soft-gap capability boost fired.
        if overlap == 0 and capability_boost == 0:
            total = 0
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

    CR-085: two passes instead of one. Pass 1 scores every non-filtered item against the
    full claim catalog (unchanged scoring logic). Pass 2 does a single global left-to-right
    assignment with a running per-project_id counter capped at _MAX_SLOTS_PER_PROJECT, so
    one dominant claim can't win every requirement — each row still picks from its own
    ranked list, so a capped-out claim is replaced by that row's own next-best match. Also
    filters generic boilerplate lines out of preferred/responsibilities (never required)
    before they consume a scoring pass at all.
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

    def _bridge_for(item_text: str, is_required: bool) -> str | None:
        if is_required and item_text in soft_gap_bridges:
            raw_bridge = soft_gap_bridges[item_text]
            return raw_bridge or "Soft gap — transferable-skill bridge; see soft_gaps for detail."
        return None

    # Pass 1: score every item, don't pick claim_ids yet.
    pending: list[dict] = []

    for req in stage0.get("required", []):
        item = _stage0_item_text(req)
        if not item:
            continue
        scored = _score_claims_for_item(item, claims, disabled, jd_profile, jd_text)
        pending.append({
            "jd_item": item,
            "bucket": "required",
            "bridge": _bridge_for(item, True),
            "scored": scored,
        })

    for pref in stage0.get("preferred", []):
        item = _stage0_item_text(pref)
        if not item:
            continue
        if _is_boilerplate_item(item):
            print(f"INFO: filtered boilerplate preferred item: {item[:80]!r}", file=sys.stderr)
            continue
        scored = _score_claims_for_item(item, claims, disabled, jd_profile, jd_text)
        pending.append({"jd_item": item, "bucket": "preferred", "bridge": None, "scored": scored})

    for resp in stage0.get("responsibilities", []):
        item = _stage0_item_text(resp)
        if not item:
            continue
        if _is_boilerplate_item(item):
            print(f"INFO: filtered boilerplate responsibility item: {item[:80]!r}", file=sys.stderr)
            continue
        scored = _score_claims_for_item(item, claims, disabled, jd_profile, jd_text)
        pending.append({"jd_item": item, "bucket": "responsibilities", "bridge": None, "scored": scored})

    # Pass 2: global assignment with per-project_id cap.
    def _project_of(cid: str) -> str:
        return (claims.get(cid) or {}).get("project_id") or cid

    project_counts: dict[str, int] = {}
    evidence_map: list[dict] = []
    for row in pending:
        picked: list[str] = []
        for cid, score in row["scored"]:
            if score <= 0 or len(picked) >= 2:
                break
            proj = _project_of(cid)
            if project_counts.get(proj, 0) >= _MAX_SLOTS_PER_PROJECT:
                continue
            picked.append(cid)
            project_counts[proj] = project_counts.get(proj, 0) + 1
        bridge = row["bridge"]
        # CR-090 follow-up: an administratively-satisfied required item (Bachelor's
        # degree, years-of-experience already gated by seniority_gate.py) correctly
        # has no claim_ids -- there's no claim about "having a degree" -- but with
        # no bridge either, Rule 2 (unmapped required item) hard-blocks the packet
        # anyway. Same root cause as the soft-gap fix in build_stage0_fit_gate.py,
        # different fail-closed rule. Auto-supply a bridge note for this narrow,
        # already-vetted category instead of leaving it to trip a second rule.
        if row["bucket"] == "required" and not picked and not bridge:
            if _is_administratively_satisfied(row["jd_item"].lower()):
                bridge = (
                    "Administratively satisfied (education / years-of-experience) -- "
                    "not a skill claim, no evidence required."
                )
        evidence_map.append({
            "jd_item": row["jd_item"],
            "bucket": row["bucket"],
            "claim_ids": picked,
            "bridge": bridge,
        })

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


def _excerpt_for_claim(
    cid: str,
    rec: dict,
    we_text: str,
    ai_text: str,
    max_chars: int = _EXCERPT_MAX_CHARS,
) -> str:
    """CR-085: prefer the claim's own lens-specific `text` (merged in by load_claims from
    master_claims.json) over regex-slicing workExperience.md by project_id. Falls back to
    the existing project-level extraction when a claim has no `text` — legacy/test fixtures,
    or any future claim added without one. This is what actually fixes the duplicate-excerpt
    problem for real data: each lens gets genuinely distinct text instead of every lens of a
    project collapsing to the same WE bracket-marker slice.
    """
    text = (rec.get("text") or "").strip()
    if text:
        return text[:max_chars]
    project_id = rec.get("project_id") or cid
    return _extract_excerpt_for_project(project_id, we_text, ai_text, rec, max_chars=max_chars)


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
                excerpt = _excerpt_for_claim(cid, rec, we_text, ai_text)
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
            excerpt = _excerpt_for_claim(cid, rec, we_text, ai_text)
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
            excerpt = _excerpt_for_claim(cid, rec, we_text, ai_text)
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

    # Rule 6: Empty JD buckets on a non-thin JD (extraction_empty fail-closed)
    req = stage0.get("required") or []
    pref = stage0.get("preferred") or []
    resp = stage0.get("responsibilities") or []
    thin = bool(stage0.get("thin_jd", False))
    if not req and not pref and not resp and not thin:
        reasons.append(
            "Empty JD buckets on a non-thin JD (extraction_empty) — rebuild Stage 0 "
            "or fix section-header extraction before drafting."
        )

    # Rule 7: Soft gaps must carry claim_ids (or an explicit bridge note already present)
    soft_gaps = _build_soft_gaps(stage0, evidence_map)
    for sg in soft_gaps:
        if sg.get("class") == "HARD":
            continue
        if sg.get("claim_ids"):
            continue
        note = (sg.get("note") or "").strip()
        if note and "extraction_empty" in note:
            # synthetic extraction gap — incomplete already via Rule 6
            continue
        if not note or note.startswith("Soft gap flagged"):
            reasons.append(
                f"Soft gap has no claim_ids to bridge: {(sg.get('item') or '')[:80]}"
            )

    status = "incomplete" if reasons else "ready"
    return status, reasons


def _normalize_gap_item_key(text: str) -> str:
    """Collapse case/whitespace so soft_gaps can match evidence_map jd_item text."""
    return re.sub(r"\s+", " ", (text or "").casefold()).strip()


def _claim_ids_for_soft_gap(gap: dict, evidence_map: list[dict]) -> list[str]:
    """Resolve claim_ids for a Stage 0 flagged gap.

    Preference order (2026-08-08 Cluster C item 9):
    1. Hand-supplied ``claim_ids`` on the flagged_gaps row (extraction_override path).
    2. Exact ``jd_item`` match against evidence_map.
    3. Normalized (casefold + whitespace) match.
    4. Containment match either direction (short gap label vs full required line).
    """
    hand = gap.get("claim_ids")
    if isinstance(hand, list) and any(isinstance(x, str) and x.strip() for x in hand):
        return [str(x).strip() for x in hand if isinstance(x, str) and x.strip()]

    item = gap.get("item") or ""
    if not item:
        return []

    by_exact: dict[str, list[str]] = {}
    by_norm: dict[str, list[str]] = {}
    for row in evidence_map:
        jd_item = row.get("jd_item") or ""
        ids = list(row.get("claim_ids") or [])
        if not jd_item or not ids:
            continue
        by_exact[jd_item] = ids
        by_norm[_normalize_gap_item_key(jd_item)] = ids

    if item in by_exact:
        return list(by_exact[item])

    norm = _normalize_gap_item_key(item)
    if norm in by_norm:
        return list(by_norm[norm])

    # Containment: prefer the longest evidence_map jd_item that overlaps.
    best_ids: list[str] = []
    best_len = -1
    for jd_item, ids in by_exact.items():
        jd_norm = _normalize_gap_item_key(jd_item)
        if not jd_norm:
            continue
        if norm in jd_norm or jd_norm in norm:
            if len(jd_norm) > best_len:
                best_len = len(jd_norm)
                best_ids = list(ids)
    return best_ids


def _build_soft_gaps(stage0: dict, evidence_map: list[dict] | None = None) -> list[dict]:
    """Build soft_gaps list from stage0 flagged_gaps, with packet claim_ids attached."""
    evidence_map = evidence_map or []

    soft_gaps: list[dict] = []
    for gap in stage0.get("flagged_gaps", []):
        if not isinstance(gap, dict):
            continue
        item = gap.get("item", "")
        if not item:
            continue
        gap_class = gap.get("gap_class", "SOFT")
        note = (
            gap.get("bridge_used")
            or gap.get("bridge")
            or "Soft gap flagged at Stage 0; argue as transferable-skill fit in cover letter."
        )
        soft_gaps.append({
            "item": item,
            "class": gap_class,
            "note": note,
            "claim_ids": _claim_ids_for_soft_gap(gap, evidence_map),
        })
    return soft_gaps


def _build_jd_buckets(stage0: dict) -> dict:
    """Extract jd_buckets from stage0 in the packet schema shape.

    CR-085: required/preferred/responsibilities are deliberately left empty here.
    build_evidence_map emits exactly one row per Stage-0 item in each of those three
    buckets (unconditionally, same order), so their text is always fully reconstructable
    from evidence_map — populating both duplicated the same JD requirement text twice in
    the serialized prompt (author_from_packet.py dumps the whole packet as JSON), measured
    at ~8% of a real packet. Only `culture` has no evidence_map counterpart (culture items
    are never scored/mapped), so it's the only bucket still populated. Keys are kept for
    all four so authoring_packet_schema.json's required-keys check still passes.
    """
    culture = [
        item for item in (_stage0_item_text(c) for c in stage0.get("culture", []))
        if item
    ]
    return {
        "required": [],
        "preferred": [],
        "responsibilities": [],
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
    soft_gaps = _build_soft_gaps(stage0, evidence_map)

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
    add_force_args(parser, "stage0")
    args = parser.parse_args()

    folder = _resolve_folder(args.folder)
    if not folder.is_dir():
        print(f"ERROR: '{folder}' is not a directory.", file=sys.stderr)
        sys.exit(0)

    stage0_path = folder / "stage0_fit_gate.json"
    if not stage0_path.exists() and args.with_stage0:
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

    # CR-075 Story 4.2 / AC2: Stage 0 exit gate. Missing or structurally invalid
    # stage0_fit_gate.json exits non-zero unless --force (logged). Replaces the old
    # "missing file => exit 0" path; other exit-0 error paths above/below stay as-is.
    try:
        require_stage_ready(
            "stage0",
            str(folder),
            force=bool(args.force),
            argv=sys.argv,
        )
    except StageGateNotReadyError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

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
