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
from authoring_examples import bank_version, select_examples  # noqa: E402
from build_stage0_fit_gate import (  # noqa: E402
    _BACHELORS_SATISFIED_RE,
    _HIGHER_DEGREE_MANDATORY_RE,
    _get_hard_tool_pattern,
    _is_administratively_satisfied,
)

_SCRIPT_DIR = Path(__file__).parent
_REPO_ROOT = _SCRIPT_DIR.parent

_CLAIMS_TAGS_PATH = _REPO_ROOT / "data" / "master_claims_tags_only.json"
_CLAIMS_FULL_PATH = _REPO_ROOT / "data" / "master_claims.json"
_WE_PATH = _REPO_ROOT / "data" / "workExperience.md"
_AI_PROJECTS_PATH = _REPO_ROOT / "data" / "aiProjects.md"

_TOKEN_BUDGET = 8000
# Fix 5 (2026-08-21 Stage 1-3 audit): 500 was below even the low end of
# researched RAG chunk-size floors for fact-retrieval use (~1,000 chars /
# ~250 tokens cited as a sensible floor) and confirmed real, repeatedly, as
# excerpts ending mid-word across several packets. Raised toward that floor;
# see _truncate_at_sentence for the other half of the fix (cut at a sentence
# boundary, not a fixed character count). Real tradeoff, not hidden: this
# eats into the same _TOKEN_BUDGET that blocked Schellman's packet entirely
# this round -- see the Schellman diagnosis for the boilerplate-item fix
# that offsets most of that cost, and _shrink_excerpts_to_budget() below for
# the adaptive fix that replaced a second, smaller hardcoded constant.
_EXCERPT_MAX_CHARS = 900

# Emergency floor for _shrink_excerpts_to_budget() -- below this an excerpt
# is too thin to trust regardless of budget pressure. Always sentence-bounded
# (never mid-word), so this is a much better failure mode than the pre-Fix-5
# bug even at the floor.
_EXCERPT_MIN_CHARS = 400

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
    "work independently and manage multiple priorities",
    "ability to work independently",
    "ability to multitask",
    "manage multiple priorities",
    "strong work ethic",
    "willingness to use our product",
    "ability and/or willingness to use our product",
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
    (
        re.compile(r"\bCross[\s-]?Functional Planning\b", re.I),
        ["ACC-178-SCOPING"],
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
    "Do not copy excerpt sentences verbatim — author fresh prose from the WE facts. "
    "Packet excerpts are retrieved workExperience.md (or aiProjects.md) spans plus "
    "hedge headers, not catalog `text`. Obey claim_constraints attribution and "
    "prohibited_claims. Never round CONTRIBUTED into OWNED.",
    _GEO_COLLAB_CONSTRAINT,
]


# ---------------------------------------------------------------------------
# Story 3.1 — Evidence Mapper helpers
# ---------------------------------------------------------------------------

# Catalog IDs that stay quarantined even if master_claims.json drops the flag.
# 2026-08-14 Nava: tests injected ACC-114-COST as disabled; the live catalog had
# no disabled:true, so a ready packet selected it.
_QUARANTINED_CLAIM_IDS = frozenset({"ACC-114-COST"})


def load_claims(
    claims_tags_path: Path | None = None,
    claims_full_path: Path | None = None,
) -> tuple[dict[str, dict], set[str]]:
    """Load claims from master_claims_tags_only.json; identify disabled IDs from master_claims.json.

    CR-094: merge hedge fields (attribution, prohibited_claims, allowed_claims, lens)
    from the full catalog. Do **not** merge `text` / `cover_story` — those are a second
    biography. Packet excerpts are WE spans (CR-085's lens-`text` path is reversed).

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

    disabled: set[str] = set(_QUARANTINED_CLAIM_IDS)
    full: dict = {}
    if full_path.exists():
        try:
            full = json.loads(full_path.read_text(encoding="utf-8"))
            for cid, rec in full.items():
                if isinstance(rec, dict) and rec.get("disabled"):
                    disabled.add(cid)
        except Exception:
            pass
    for cid, rec in claims.items():
        if isinstance(rec, dict) and rec.get("disabled"):
            disabled.add(cid)

    _HEDGE_KEYS = ("attribution", "prohibited_claims", "allowed_claims", "lens")
    for cid, rec in claims.items():
        full_rec = full.get(cid)
        if not isinstance(full_rec, dict):
            continue
        for key in _HEDGE_KEYS:
            if rec.get(key) in (None, "", []):
                val = full_rec.get(key)
                if val:
                    rec[key] = val

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
        # "tools"/"tooling" — ACC-120/401 "AI Tools" was winning Smartsheet/Power BI
        # lines on the shared word alone (evidence_map pressure test 2026-08-10).
        "tool",
        "tools",
        "tooling",
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

# Required lines that must never receive claim_ids (keep the row + bridge; do not drop —
# required-bucket drop is forbidden by session-007 R4).
_COMPENSATION_NOISE_RE = re.compile(
    r"\b(?:compensation\s+practices?|equitable\s+compensation|competitive(?:ly)?(?:,?\s*fair,?)?\s+"
    r"(?:and\s+)?(?:equitable\s+)?compensation|"
    r"final\s+offered\s+salary|offered\s+salary\s+will\s+be\s+based|"
    r"salary\s+will\s+be\s+based\s+on\s+several\s+factors|"
    r"total\s+compensation|total\s+direct\s+compensation|"
    r"base\s+salary\s+and/?\s*or\s+ote|\bote\s+listed\b|"
    r"base\s+salary\s+range|pay\s+range\s+is|"
    r"window\s+of\s+at\s+least\s+\d+\s+days?\s+for\s+you\s+to\s+apply)\b",
    re.I,
)

_HARD_TOOL_EVIDENCE_BRIDGE = (
    "Named tool not in verified history — do not claim ownership of this tool; "
    "transferable-skill bridge in prose only if Stage 0 marked SOFT."
)

_NON_CLAIMABLE_BRIDGE_DEGREE = (
    "Administratively satisfied (education / years-of-experience) -- "
    "not a skill claim, no evidence required."
)

_NON_CLAIMABLE_BRIDGE_COMP = (
    "Not a skill claim (compensation/benefits boilerplate) -- no evidence required."
)

_NON_CLAIMABLE_BRIDGE_PRODUCTIVITY = (
    "Not a skill claim (named productivity suite not in verified history) -- "
    "no evidence required; do not invent Office/Workspace proficiency."
)

_PRODUCTIVITY_SUITE_RE = re.compile(
    r"\b(?:microsoft\s+office(?:\s+suite)?|google\s+(?:workspace|suite)|ms\s+office)\b",
    re.I,
)


def _is_degree_non_claimable(item_text: str) -> bool:
    """Bachelor's/undergrad lines map to no ACC — force empty claim_ids."""
    item_l = (item_text or "").lower()
    if not _BACHELORS_SATISFIED_RE.search(item_l):
        return False
    if _HIGHER_DEGREE_MANDATORY_RE.search(item_l):
        return False
    return True


def _is_compensation_non_claimable(item_text: str) -> bool:
    return bool(_COMPENSATION_NOISE_RE.search(item_text or ""))


def _is_productivity_suite_non_claimable(item_text: str) -> bool:
    """Microsoft Office / Google Workspace lines are not Jason skill claims."""
    return bool(_PRODUCTIVITY_SUITE_RE.search(item_text or ""))


def _item_names_hard_blocked_tool(item_text: str) -> bool:
    """True when the JD line names a Stage-0 hard-blocked tool Jason must not claim."""
    if not (item_text or "").strip():
        return False
    return _get_hard_tool_pattern().search(item_text) is not None


def _force_empty_claim_scoring(item_text: str) -> str | None:
    """If this item must not receive claim_ids, return the bridge note to attach.

    Returns None when normal scoring should run.
    """
    if _is_degree_non_claimable(item_text):
        return _NON_CLAIMABLE_BRIDGE_DEGREE
    if _is_compensation_non_claimable(item_text):
        return _NON_CLAIMABLE_BRIDGE_COMP
    if _is_productivity_suite_non_claimable(item_text):
        return _NON_CLAIMABLE_BRIDGE_PRODUCTIVITY
    if _item_names_hard_blocked_tool(item_text):
        return _HARD_TOOL_EVIDENCE_BRIDGE
    return None


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
        # Claim-side match must be word-bounded: substring "ai" false-positives inside
        # "training"/"email"/"details" and, once tools was denylisted, tied every claim
        # at +12000 so ACC-105 sorted ahead of ACC-120 on real AI lines.
        item_l = item_text.lower()
        if re.search(r"\b(ai|ml|ai/ml|machine\s+learning|llm)\b", item_l):
            cid_l = cid.lower()
            tags_lower = [str(t).lower() for t in (rec.get("tags") or [])]
            claim_tag_blob = " ".join(tags_lower)
            if (
                "120" in cid_l
                or "airesearch" in cid_l
                or "401" in cid_l
                or "aitools" in cid_l
                or re.search(r"\b(ai|ml|prompt)\b", claim_tag_blob)
                or any("ai tool" in t or "prompt" in t for t in tags_lower)
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
        # Required and preferred Stage-0 soft gaps both need a bridge when claim
        # scoring finds nothing (LeafLink marketplace preferred, 2026-08-11).
        if item_text in soft_gap_bridges:
            raw_bridge = soft_gap_bridges[item_text]
            return raw_bridge or (
                "Soft gap — transferable-skill bridge; see soft_gaps for detail."
            )
        return None

    def _enqueue(item: str, bucket: str, *, is_required: bool) -> None:
        forced_bridge = _force_empty_claim_scoring(item)
        soft_raw = (soft_gap_bridges.get(item) or "").strip()
        if forced_bridge is not None:
            # No claim_ids: prefer a real Stage-0 soft-gap bridge, else the honesty note.
            # Do not use the generic "Soft gap — transferable…" filler here — that exists for
            # scored soft gaps; for hard-tools/degree/pay it would hide the real reason.
            scored: list[tuple[str, int]] = []
            bridge = soft_raw or forced_bridge
        else:
            scored = _score_claims_for_item(item, claims, disabled, jd_profile, jd_text)
            bridge = _bridge_for(item, is_required)
        pending.append({
            "jd_item": item,
            "bucket": bucket,
            "bridge": bridge,
            "scored": scored,
        })

    # Pass 1: score every item, don't pick claim_ids yet.
    pending: list[dict] = []

    for req in stage0.get("required", []):
        item = _stage0_item_text(req)
        if not item:
            continue
        _enqueue(item, "required", is_required=True)

    for pref in stage0.get("preferred", []):
        item = _stage0_item_text(pref)
        if not item:
            continue
        if _is_boilerplate_item(item):
            print(f"INFO: filtered boilerplate preferred item: {item[:80]!r}", file=sys.stderr)
            continue
        _enqueue(item, "preferred", is_required=False)

    for resp in stage0.get("responsibilities", []):
        item = _stage0_item_text(resp)
        if not item:
            continue
        if _is_boilerplate_item(item):
            print(f"INFO: filtered boilerplate responsibility item: {item[:80]!r}", file=sys.stderr)
            continue
        _enqueue(item, "responsibilities", is_required=False)

    # Required items Stage 0 did not mark as a gap. If scoring/slot-cap later
    # leaves them with no claim_ids, Rule 2 would hard-block a PASS JD
    # (found 2026-08-14: Nava "IT modernization" anchored on a tag, then unscored).
    stage0_anchored_required = {
        _stage0_item_text(r)
        for r in stage0.get("required", [])
        if isinstance(r, dict) and r.get("gap") is False
    }

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
            elif row["jd_item"] in stage0_anchored_required:
                bridge = (
                    "Stage 0 treated as anchored but no claim slot remained. "
                    "Use the nearest packet excerpt as a transferable bridge. "
                    "Do not claim the JD's literal domain as owned."
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


_SENTENCE_END_RE = re.compile(r"[.!?][\"')\]]*(?:\s|$)")


def _truncate_at_sentence(text: str, max_chars: int) -> str:
    """Truncate *text* to at most max_chars, preferring the nearest sentence
    boundary at or before the limit over a hard mid-word/mid-sentence cut.

    Fix 5 (2026-08-21 Stage 1-3 audit): the plain `[:max_chars]` slice this
    replaced produced excerpts ending mid-word, confirmed real across
    several packets this round -- true accomplishment facts sitting unused
    because the retrieved excerpt cut off before finishing the sentence that
    stated them. Falls back to the hard cut only when no sentence boundary
    exists anywhere inside the budget (e.g. one long run-on clause), so this
    never returns more text than max_chars allows.
    """
    if len(text) <= max_chars:
        return text
    window = text[:max_chars]
    best_end = -1
    for m in _SENTENCE_END_RE.finditer(window):
        best_end = m.end()
    if best_end > 0:
        return window[:best_end].rstrip()
    return window


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
            return _truncate_at_sentence(_strip_markdown_decoration(raw), max_chars)
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

    # CR-095: include substory / hedge lines until the next indexable story.
    from we_acc_index import story_span_end

    span_end = story_span_end(we_text, str(project_id), idx)
    raw_chunk = we_text[line_start:span_end]

    clean = _strip_markdown_decoration(raw_chunk)
    return _truncate_at_sentence(clean, max_chars)


def _format_excerpt_card(
    cid: str,
    rec: dict,
    span: str,
    we_text: str,
    *,
    pointer_to: str | None = None,
    max_chars: int = _EXCERPT_MAX_CHARS,
) -> str:
    """WE span plus hedge header, or a lens pointer for a later lens of the same story.

    Implements CR-094: author sees retrieved WE, not catalog `text`.
    """
    from we_acc_index import hedges_for_project

    project_id = str(rec.get("project_id") or cid)
    lens = str(rec.get("lens") or "").strip() or "story"
    hedges = hedges_for_project(we_text, project_id)
    attr = str(rec.get("attribution") or hedges.get("attribution") or "").strip()
    prohibited = rec.get("prohibited_claims") or hedges.get("prohibited_claims") or []
    if isinstance(prohibited, str):
        prohibited = [prohibited]
    attr_s = attr.upper() if attr else "unspecified"
    dnc = "; ".join(str(p) for p in prohibited) if prohibited else "none listed"
    header = f"Lens {lens} of {project_id}. Attribution: {attr_s}. Prohibited: {dnc}."
    if pointer_to:
        body = (
            f"{header} Same WE story as {pointer_to}. Write this JD item through the "
            f"{lens} lens. Do not copy excerpt sentences."
        )
        return _truncate_at_sentence(body, max_chars)
    return _truncate_at_sentence(f"{header}\n{span}", max_chars)


def _excerpt_for_claim(
    cid: str,
    rec: dict,
    we_text: str,
    ai_text: str,
    max_chars: int = _EXCERPT_MAX_CHARS,
    pointer_to: str | None = None,
) -> str:
    """CR-094: always slice WE / aiProjects. Never use claim `text`.

    pointer_to: claim_id that already holds this project's WE span. Later lenses
    of the same project get a short lens instruction instead of a duplicate dump
    (CR-085's byte-identical waste, without a second biography).
    """
    project_id = rec.get("project_id") or cid
    span = _extract_excerpt_for_project(
        project_id, we_text, ai_text, rec, max_chars=max_chars
    )
    return _format_excerpt_card(
        cid, rec, span, we_text, pointer_to=pointer_to, max_chars=max_chars
    )


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


def _add_excerpt(
    excerpts: dict[str, str],
    span_holders: dict[str, str],
    cid: str,
    rec: dict,
    we_text: str,
    ai_text: str,
) -> str:
    """Insert a WE card for cid, reusing a prior span for the same project_id."""
    if cid in excerpts:
        return excerpts[cid]
    project_id = str(rec.get("project_id") or cid)
    pointer_to = span_holders.get(project_id)
    excerpt = _excerpt_for_claim(cid, rec, we_text, ai_text, pointer_to=pointer_to)
    if excerpt:
        excerpts[cid] = excerpt
        if pointer_to is None and not _is_thin_synthetic_excerpt(excerpt):
            span_holders[project_id] = cid
    return excerpt


def _ensure_canonical_role_excerpts(
    excerpts: dict[str, str],
    claims: dict[str, dict],
    we_text: str,
    ai_text: str,
    disabled: set[str] | None = None,
    span_holders: dict[str, str] | None = None,
) -> dict[str, str]:
    """Guarantee enough excerpts per canonical career-history employer.

    JD-ranked evidence can omit Zero To Sixty (or another role) entirely; the
    author then cannot invent bullets under closed-world rules, and LR-020/021 fail.
    Also tops up thin roles to at least _MIN_EXCERPTS_PER_CANONICAL_EMPLOYER claims
    so earlier roles can support the required 2–3 bullets.
    """
    disabled = disabled or set()
    span_holders = span_holders if span_holders is not None else {}
    counts = _employer_excerpt_counts(excerpts, claims)
    for employer, preferred_ids in _CANONICAL_ROLE_CLAIMS.items():
        while counts.get(employer, 0) < _MIN_EXCERPTS_PER_CANONICAL_EMPLOYER:
            added = False
            for cid in preferred_ids:
                if cid in disabled or cid not in claims or cid in excerpts:
                    continue
                rec = claims[cid]
                excerpt = _add_excerpt(excerpts, span_holders, cid, rec, we_text, ai_text)
                if excerpt:
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
    span_holders: dict[str, str] | None = None,
) -> dict[str, str]:
    """Pull claim excerpts for JD-named skills so literal terms stay closed-world."""
    if not jd_text:
        return excerpts
    disabled = disabled or set()
    span_holders = span_holders if span_holders is not None else {}
    for pattern, preferred_ids in _JD_SKILL_ANCHORS:
        if not pattern.search(jd_text):
            continue
        if any(cid in excerpts for cid in preferred_ids):
            continue
        for cid in preferred_ids:
            if cid in disabled or cid not in claims:
                continue
            rec = claims[cid]
            excerpt = _add_excerpt(excerpts, span_holders, cid, rec, we_text, ai_text)
            if excerpt:
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
    """Story 3.2 — Pull bounded WE excerpts for evidence_map + role/skill floors."""
    excerpts: dict[str, str] = {}
    span_holders: dict[str, str] = {}
    for row in evidence_map:
        for cid in row.get("claim_ids") or []:
            rec = claims.get(cid, {})
            excerpt = _add_excerpt(excerpts, span_holders, cid, rec, we_text, ai_text)
            if excerpt and _is_thin_synthetic_excerpt(excerpt) and cid not in excerpts:
                excerpts[cid] = excerpt

    excerpts = _ensure_canonical_role_excerpts(
        excerpts, claims, we_text, ai_text, disabled=disabled, span_holders=span_holders
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
        excerpts, claims, we_text, ai_text, jd_text, disabled=disabled,
        span_holders=span_holders,
    )


def build_claim_constraints(
    excerpts: dict[str, str],
    claims: dict[str, dict],
    we_text: str,
) -> dict[str, dict]:
    """Per-claim hedge fields the closed-world author must obey (CR-094)."""
    from we_acc_index import hedges_for_project

    out: dict[str, dict] = {}
    for cid in excerpts:
        rec = claims.get(cid) or {}
        project_id = str(rec.get("project_id") or cid)
        hedges = hedges_for_project(we_text, project_id)
        attr = str(rec.get("attribution") or hedges.get("attribution") or "").strip()
        prohibited = rec.get("prohibited_claims") or hedges.get("prohibited_claims") or []
        if isinstance(prohibited, str):
            prohibited = [prohibited]
        allowed = rec.get("allowed_claims") or []
        if isinstance(allowed, str):
            allowed = [allowed]
        out[cid] = {
            "project_id": project_id,
            "lens": str(rec.get("lens") or "").strip() or "story",
            "attribution": attr.upper() if attr else "",
            "prohibited_claims": [str(p) for p in prohibited],
            "allowed_claims": [str(a) for a in allowed],
        }
    return out


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
            or ""
        )
        claim_ids = _claim_ids_for_soft_gap(gap, evidence_map)
        if not note.strip():
            # Prefer the evidence_map bridge (hard-tool / degree / compensation honesty)
            # so Rule 7 and verify-only can accept empty claim_ids when that is correct.
            item_norm = _normalize_gap_item_key(item)
            for row in evidence_map:
                if _normalize_gap_item_key(row.get("jd_item") or "") == item_norm:
                    em_bridge = (row.get("bridge") or "").strip()
                    if em_bridge:
                        note = em_bridge
                        break
        if not note.strip():
            note = (
                "Soft gap flagged at Stage 0; argue as transferable-skill fit in cover letter."
            )
        soft_gaps.append({
            "item": item,
            "class": gap_class,
            "note": note,
            "claim_ids": claim_ids,
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


def _shrink_excerpts_to_budget(excerpts: dict[str, str], overage_tokens: int) -> dict[str, str]:
    """Adaptive post-hoc shrink pass (2026-08-21, Schellman fix).

    Real measured tradeoff, not hidden: raising _EXCERPT_MAX_CHARS to 900
    (Fix 5) re-blocks one real, unusually evidence-heavy JD's token budget --
    17 required items (typical is 7-12), so a per-item cap applied uniformly
    costs proportionally more the more items a JD has. Rather than hand-
    picking one smaller global cap that shortchanges every normal-sized JD to
    accommodate the rare outlier, every excerpt is still built at the full
    researched cap first; only if the assembled packet actually comes in over
    budget does this shrink proportionally across every excerpt (largest
    excerpts give up the most, in proportion to their own size) until it
    fits, down to _EXCERPT_MIN_CHARS. A typical JD never hits this path at
    all. Same "score-weighted truncation, adapt to the retrieval set's real
    size instead of one fixed constant" pattern RAG token-budgeting research
    recommends over a single hardcoded per-item limit.

    Never truncates mid-word/mid-sentence: re-runs _truncate_at_sentence on
    the already-built excerpt text, so a shrink only ever removes whole
    trailing sentences, same as the original build.
    """
    if not excerpts or overage_tokens <= 0:
        return excerpts
    # utf-8 bytes / 4 approximation, matching assemble_packet()'s own estimator.
    overage_chars = overage_tokens * 4
    total_chars = sum(len(v) for v in excerpts.values())
    if total_chars <= 0:
        return excerpts
    shrunk: dict[str, str] = {}
    for cid, text in excerpts.items():
        share = len(text) / total_chars
        target = max(_EXCERPT_MIN_CHARS, len(text) - int(overage_chars * share))
        shrunk[cid] = _truncate_at_sentence(text, target) if target < len(text) else text
    return shrunk


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
    claim_constraints: dict | None = None,
    jd_text: str = "",
    ats_term_contract: list[dict] | None = None,
) -> dict:
    """Story 3.3 — Assemble the full authoring_packet dict matching schema v1.0."""
    tier = stage0.get("tier", "Tier 1")
    reach_out = stage0.get("reach_out", False)
    stage_signal = stage0.get("stage_signal") or None
    thin_jd = bool(stage0.get("thin_jd", False))

    jd_buckets = _build_jd_buckets(stage0)
    soft_gaps = _build_soft_gaps(stage0, evidence_map)
    from jd_term_extractor import build_packet_ats_term_contract
    if ats_term_contract is None:
        ats_term_contract = build_packet_ats_term_contract(jd_text, evidence_map)

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
        "claim_constraints": claim_constraints or {},
        "soft_gaps": soft_gaps,
        "ats_term_contract": ats_term_contract,
        # Implements FR-265: rebuilt packets require claims to map to the exact resume
        # bullet or factual cover-letter sentence they support. Legacy packets
        # without this contract retain their existing provenance behavior.
        "provenance_contract": {
            "version": 2,
            "resume_unit": "bullet",
            "cover_letter_unit": "factual_sentence",
        },
        "hard_constraints": _HARD_CONSTRAINTS,
        "hook_fact": hook_fact,
        "rule_digest_version": _load_rule_digest_version(),  # Story 4.3
        "packet_status": "ready",
        "incomplete_reasons": [],
        "estimated_tokens": 0,
        "stage_signal": stage_signal,
        "thin_jd": thin_jd,
        # Recency: render last in dumped JSON, same reason Fix 6 put the
        # self-check last in the digest (CR-097 Story 3.3).
        "learned_examples": select_examples(
            {"jd_buckets": jd_buckets, "soft_gaps": soft_gaps}
        ),
        "example_bank_version": bank_version(),
    }
    # estimated_tokens from utf-8 bytes / 4
    estimated_tokens = len(json.dumps(draft, ensure_ascii=False).encode("utf-8")) // 4

    # CR-097 Story 3.4 budget ordering — do not get this backwards.
    # learned_examples is counted inside estimated_tokens before the
    # _TOKEN_BUDGET check. If the packet is over budget, drop examples
    # first, one at a time, and only call _shrink_excerpts_to_budget()
    # if it is still over after the examples are gone. Evidence never
    # gets truncated to make room for a teaching example.
    if estimated_tokens > _TOKEN_BUDGET and draft["learned_examples"]:
        while estimated_tokens > _TOKEN_BUDGET and draft["learned_examples"]:
            draft["learned_examples"].pop()
            estimated_tokens = (
                len(json.dumps(draft, ensure_ascii=False).encode("utf-8")) // 4
            )

    # Adaptive shrink (2026-08-21, Schellman fix): only reached when the
    # packet built at the full excerpt cap actually comes in over budget --
    # see _shrink_excerpts_to_budget()'s own docstring.
    if estimated_tokens > _TOKEN_BUDGET:
        shrunk_excerpts = _shrink_excerpts_to_budget(excerpts, estimated_tokens - _TOKEN_BUDGET)
        if shrunk_excerpts != excerpts:
            excerpts = shrunk_excerpts
            draft["excerpts"] = excerpts
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
    claim_constraints = build_claim_constraints(excerpts, claims, we_text)
    from jd_term_extractor import build_packet_ats_term_contract
    ats_term_contract = build_packet_ats_term_contract(
        jd_text,
        evidence_map,
        claims=claims,
        excerpt_claim_ids=set(excerpts),
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
        claim_constraints=claim_constraints,
        jd_text=jd_text,
        ats_term_contract=ats_term_contract,
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
