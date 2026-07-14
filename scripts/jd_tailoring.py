"""
JD profile extraction and claim scoring (CR-014 / FR-091).
"""
from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from utils import PROJECT_ROOT

BRIDGE_PHRASES_PATH = os.path.join(PROJECT_ROOT, "data", "bridge_phrases.json")

THEME_KEYWORDS = (
    ("platform", "platform reliability and scale"),
    ("data", "data integrity and ingestion"),
    ("ingest", "data integrity and ingestion"),
    ("migration", "customer migration and retention"),
    ("security", "security backlog and risk reduction"),
    ("roadmap", "roadmap prioritization and execution"),
    ("saas", "B2B SaaS product delivery"),
    ("stakeholder", "cross-functional stakeholder alignment"),
    ("onboarding", "onboarding and customer experience"),
    ("monetiz", "monetization and revenue-generating platform capabilities"),
    ("revenue", "revenue-generating product delivery"),
    ("ranking", "rankings and list franchise data platforms"),
    ("intelligence", "intelligence and analytics platform evolution"),
    ("media", "media and audience data products"),
    ("franchise", "scalable franchise and vertical expansion"),
    ("integration", "API integration and cross-system workflows"),
    ("restful", "API integration and cross-system workflows"),
    ("api", "API integration and cross-system workflows"),
    ("analytics", "analytics product delivery and adoption"),
    ("kpi", "KPI-driven product delivery"),
    ("adoption", "product adoption and measurable outcomes"),
    ("underwriting", "analytics for sales and underwriting workflows"),
    ("fintech", "fintech product delivery and marketplace infrastructure"),
    ("lender", "lender integrations and partner onboarding"),
    ("funnel", "consumer funnel optimization and conversion"),
    ("marketplace", "marketplace infrastructure and partner matching"),
    ("borrower", "borrower experience and offer optimization"),
    ("privacy", "privacy compliance and governance"),
    ("compliance", "compliance and legal alignment"),
    ("identity", "identity access governance"),
    ("access", "access control and platform governance"),
    ("governance", "platform governance and automated workflows"),
    ("genai", "AI tooling and agentic automation workflows"),
    ("agentic", "AI tooling and agentic automation workflows"),
    ("llm", "AI tooling and prompt engineering workflows"),
    ("cursor", "AI tooling and prompt engineering workflows"),
    ("claude", "AI tooling and prompt engineering workflows"),
)


@dataclass
class JdProfile:
    priority_themes: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    source: str = "deterministic"

    def to_dict(self):
        return asdict(self)


def load_bridge_phrases() -> Dict[str, str]:
    if os.path.exists(BRIDGE_PHRASES_PATH):
        with open(BRIDGE_PHRASES_PATH, encoding="utf-8-sig") as f:
            return json.load(f)
    return {}


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _substring_valid(phrase: str, jd_text: str) -> bool:
    return _normalize_ws(phrase) in _normalize_ws(jd_text)


_REQ_SECTION_RE = re.compile(
    r"^(requirements?|qualifications?|what\s+you.{0,8}bring|"
    r"what\s+we.{0,8}looking|what\s+you.{0,8}need|"
    r"preferred\s+qualifications?|basic\s+qualifications?|"
    r"required\s+qualifications?|key\s+requirements?|"
    r"minimum\s+qualifications?|must\s+have|you\s+bring|"
    r"what\s+you\s+offer)(?:[^\n]{0,20})?\s*:?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_NEXT_SECTION_RE = re.compile(
    r"\n\s*\n[A-Z][A-Z\s]{3,}\n|\n##\s",
    re.MULTILINE,
)


def extract_req_section(jd_text: str) -> str:
    """Return the requirements/qualifications subsection of a JD (FR-196).

    Searches for common requirement-section headings and returns the text
    that follows, up to the next major section break. Falls back to the
    full JD text when no heading is found, so callers can always use this
    safely without a None check.
    """
    m = _REQ_SECTION_RE.search(jd_text)
    if not m:
        return jd_text
    remainder = jd_text[m.end():]
    boundary = _NEXT_SECTION_RE.search(remainder)
    if boundary and boundary.start() > 100:
        return remainder[: boundary.start()].strip()
    trimmed = remainder[:2000].strip()
    return trimmed if trimmed else jd_text


def _jd_body_for_themes(jd_text: str) -> str:
    """Theme detection body — excludes trailing job-board category tag footers."""
    return jd_text[: max(1, int(len(jd_text) * 0.72))]


def build_jd_profile_deterministic(jd_text: str, fit_summary: str = "") -> JdProfile:
    theme_source = _jd_body_for_themes(jd_text)
    jd_lower = theme_source.lower()
    themes = []
    for kw, phrase in THEME_KEYWORDS:
        if kw in jd_lower and phrase not in themes:
            themes.append(phrase)

    requirements = []
    for line in jd_text.splitlines():
        line = line.strip().lstrip("-•*").strip()
        if 20 <= len(line) <= 120 and line[0].isalnum():
            requirements.append(line[:120])
    requirements = requirements[:6]

    words = set(re.findall(r"[a-z]{5,}", jd_lower))
    keywords = sorted(w for w in words if w not in {"about", "their", "would", "should", "other"})[:12]

    if fit_summary:
        fs = fit_summary.lower()
        for kw, phrase in THEME_KEYWORDS:
            if kw in fs and phrase not in themes:
                themes.append(phrase)

    return JdProfile(
        priority_themes=themes[:4],
        requirements=requirements[:6],
        keywords=keywords,
        source="deterministic",
    )


def build_jd_profile(jd_text: str, fit_summary: str = "") -> JdProfile:
    from pipeline_env import jd_profile_mode

    if jd_profile_mode() == "deterministic":
        return build_jd_profile_deterministic(jd_text, fit_summary)

    from llm_stages import call_llm_stage

    prompt = f"""Extract from this job description ONLY phrases that appear verbatim (substring).
Output JSON: {{"priority_themes": [], "requirements": [], "keywords": []}}
Max 4 themes, 6 requirements, 12 keywords.

JD:
{jd_text[:2500]}"""
    raw = call_llm_stage(
        "jd_profile",
        "Output only valid JSON. Do not invent requirements not in the JD.",
        prompt,
        temperature=0.0,
        response_mime_type="application/json",
    )
    if raw:
        try:
            cleaned = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            data = json.loads(cleaned)
            themes = [t for t in data.get("priority_themes", []) if _substring_valid(str(t), jd_text)]
            reqs = [r for r in data.get("requirements", []) if _substring_valid(str(r), jd_text)]
            kws = [k for k in data.get("keywords", []) if str(k).lower() in jd_text.lower()]
            if themes or reqs:
                prof = JdProfile(
                    priority_themes=themes[:4],
                    requirements=reqs[:6],
                    keywords=[str(k) for k in kws[:12]],
                    source="llm_validated",
                )
                save_cached_jd_profile(jd_text, prof)
                return prof
        except (json.JSONDecodeError, TypeError):
            pass
    return build_jd_profile_deterministic(jd_text, fit_summary)


def _jd_hash(jd_text: str) -> str:
    import hashlib

    return hashlib.sha256(jd_text.encode("utf-8")).hexdigest()[:16]


def save_cached_jd_profile(jd_text: str, profile: JdProfile, company_folder: Optional[str] = None) -> None:
    import os

    if not company_folder:
        return
    path = os.path.join(company_folder, "jd_profile_cache.json")
    payload = {"jd_hash": _jd_hash(jd_text), "profile": profile.to_dict()}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def load_cached_jd_profile_from_folder(company_folder: str, jd_text: str) -> Optional[JdProfile]:
    import os

    path = os.path.join(company_folder, "jd_profile_cache.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("jd_hash") != _jd_hash(jd_text):
            return None
        p = data.get("profile") or {}
        return JdProfile(
            priority_themes=p.get("priority_themes", []),
            requirements=p.get("requirements", []),
            keywords=p.get("keywords", []),
            source=p.get("source", "cached"),
        )
    except (json.JSONDecodeError, TypeError, OSError):
        return None


# --- CR-064 Round 3: rarity-weight cache ---------------------------------
_RARITY_DF: Optional[Dict[str, int]] = None   # token -> number of active claims containing it
_RARITY_N: Optional[int] = None               # number of active (non-disabled) claims


def _reset_rarity_cache() -> None:
    """Test hook: force `_get_rarity_table` to rebuild on next call."""
    global _RARITY_DF, _RARITY_N
    _RARITY_DF, _RARITY_N = None, None


def _set_rarity_table(df: Dict[str, int], n: int) -> None:
    """Test hook: inject a fixed synthetic df table so rarity-weight unit tests can
    pin exact arithmetic without coupling to production `master_claims.json`
    contents that drift.
    """
    global _RARITY_DF, _RARITY_N
    _RARITY_DF, _RARITY_N = dict(df), n


def _get_rarity_table() -> "tuple[Dict[str, int], int]":
    """Lazily build (and cache) token document-frequency over active (non-disabled)
    claims in `data/master_claims.json`. Self-loads the file directly via
    `json.load` rather than `claim_catalog.load_catalog()`, which triggers a
    dormant Ollama embeddings sync this CR must not couple into.
    """
    global _RARITY_DF, _RARITY_N
    if _RARITY_DF is not None and _RARITY_N is not None:
        return _RARITY_DF, _RARITY_N
    path = os.path.join(PROJECT_ROOT, "data", "master_claims.json")
    with open(path, encoding="utf-8") as fh:
        claims = json.load(fh)                              # dict keyed by claim id
    df: Dict[str, int] = {}
    n = 0
    for rec in claims.values():
        if not isinstance(rec, dict) or rec.get("disabled"):
            continue
        n += 1
        blob = ((rec.get("text") or "") + " " + " ".join(rec.get("tags") or [])).lower()
        for tok in set(re.findall(r"[a-z]{5,}", blob)):      # count each token once per claim
            df[tok] = df.get(tok, 0) + 1
    _RARITY_DF, _RARITY_N = df, n
    return df, n


def _rarity_weight(token: str) -> float:
    """Smoothed-IDF weight: `1 + ln(N/df)` for tokens seen in the catalog, floored
    to `1.0` (i.e. behaves like the old flat/unweighted contribution) for tokens
    absent from the table (typically substring-match artifacts, e.g. `ability`
    inside "stability").
    """
    df, n = _get_rarity_table()
    freq = df.get(token, 0)
    if freq <= 0:
        return 1.0
    return 1.0 + math.log(n / freq)


def score_claim_for_jd(claim_text: str, profile: JdProfile, jd_text: str) -> int:
    """CR-064 Round 2+3+5: dedup pass, rarity-weighted contributions, then a DCG
    rank-discount breadth dampener.

    A given matched token contributes at most once per claim-JD pair, at its
    highest tier across the four loops, instead of once per loop/line it happens
    to appear in (the pre-CR-064 cross-loop/cross-line compounding bug). Each
    unique matched token's tier is then scaled by how rare that token is across
    the active claim catalog, so a claim that wins on one rare, precise term can
    outscore a claim that wins on breadth of generic/common terms. Finally
    (Round 5), the per-token contributions are sorted descending and discounted
    by rank via `log2(rank+1)` (DCG position discount): the single strongest
    match (rank 1) is undiscounted, so a one-token precision claim is immune to
    this step, while each additional token pays a progressively steeper breadth
    tax -- countering the pure-additive sum's structural bias toward claims that
    match many moderately-relevant tokens over claims that match one killer one.
    """
    text_l = claim_text.lower()
    jd_l = jd_text.lower()

    matched: Dict[str, int] = {}

    def _bump(tok: str, tier: int) -> None:
        if matched.get(tok, 0) < tier:
            matched[tok] = tier

    for w in profile.keywords:                             # loop 1, tier 1
        if w in text_l and w in jd_l:
            _bump(w, 1)
    for req in profile.requirements:                       # loop 2, tier 2
        for token in re.findall(r"[a-z]{5,}", req.lower()):
            if token in text_l:
                _bump(token, 2)
    for theme in profile.priority_themes:                  # loop 3, tier 1
        for token in re.findall(r"[a-z]{5,}", theme.lower()):
            if token in text_l:
                _bump(token, 1)
    for kw, _phrase in THEME_KEYWORDS:                      # loop 4, tier 3
        if kw in jd_l and kw in text_l:
            _bump(kw, 3)

    contribs = sorted(
        (tier * _rarity_weight(tok) for tok, tier in matched.items()),
        reverse=True,
    )
    total = sum(v / math.log2(rank + 1) for rank, v in enumerate(contribs, start=1))
    return int(round(total))


def _metric_signature(text: str) -> frozenset:
    from verify_claims import extract_numeric_tokens

    return frozenset(extract_numeric_tokens(text.replace(",", "")))


def pick_cover_bullets(
    bullets: Dict[str, str],
    valid_ids: Dict[str, str],
    profile: JdProfile,
    jd_text: str,
    k: int = 2,
) -> List[str]:
    from local_draft_stages import employer_for_claim_id

    ranked = sorted(
        bullets.items(),
        key=lambda item: (
            score_claim_for_jd(valid_ids.get(item[0], item[1]), profile, jd_text),
            item[0],
        ),
        reverse=True,
    )
    jd_l = jd_text.lower()

    def _complement_score(cid: str, text: str) -> int:
        base = score_claim_for_jd(valid_ids.get(cid, text), profile, jd_text)
        tl = text.lower()
        bonus = 0
        if "media" in jd_l and "media" in tl:
            bonus += 6
        if "monetiz" in jd_l and ("revenue" in tl or "$" in text):
            bonus += 6
        if "migrat" in jd_l and "migrat" in tl:
            bonus += 5
        if ("ranking" in jd_l or "franchise" in jd_l) and "migrat" in tl:
            bonus += 8
        if ("ranking" in jd_l or "franchise" in jd_l) and "platform" in tl:
            bonus += 4
        if "data" in jd_l and ("data" in tl or "analytics" in tl):
            bonus += 3
        if "security" in jd_l and ("security" in tl or "vulnerab" in tl):
            bonus += 8
        if "compliance" in jd_l and ("compliance" in tl or "risk" in tl):
            bonus += 4
        return base + bonus

    picked: List[str] = []
    sigs_seen: set = set()
    if ranked:
        cid0, text0 = ranked[0]
        picked.append(text0)
        sig0 = _metric_signature(text0)
        if sig0:
            sigs_seen.add(sig0)

    if k >= 2 and len(picked) == 1:
        best_alt = None
        best_score = -1
        for cid, text in ranked[1:]:
            if text in picked:
                continue
            sig = _metric_signature(text)
            if sig and sig in sigs_seen:
                continue
            comp = _complement_score(cid, text)
            if comp > best_score:
                best_score = comp
                best_alt = text
        if best_alt:
            picked.append(best_alt)
            sig = _metric_signature(best_alt)
            if sig:
                sigs_seen.add(sig)

    for cid, text in ranked:
        if len(picked) >= k:
            break
        if text in picked:
            continue
        sig = _metric_signature(text)
        if sig and sig in sigs_seen:
            continue
        picked.append(text)
        if sig:
            sigs_seen.add(sig)

    return picked[:k]


_AI_SIGNAL_RE = re.compile(
    r"\b(ai|llm|large\s+language\s+model|genai|generative\s+ai|"
    r"agentic|agent[- ]based|chatgpt|gpt[-\s]?\d|openai|anthropic|gemini|"
    r"claude|langchain|rag|retrieval[- ]augmented|vector\s+search|"
    r"embedding|fine[- ]tun|prompt\s+engineer|machine\s+learning|ml\s+model|"
    r"copilot|ai[- ]powered|ai[- ]native|ai[- ]first|nlp|"
    r"natural\s+language\s+processing|transformer)\b",
    re.IGNORECASE,
)


def has_ai_signal(jd_text: str) -> bool:
    """Return True when the JD body contains AI/LLM role indicators (FR-209).

    Only scans the first 80% of the text to avoid triggering on industry
    category tag footers common on job board pages (e.g. BuiltIn's
    'Machine Learning  Generative AI' tag line).
    """
    from conversion_framing import _jd_body_for_signals

    return bool(_AI_SIGNAL_RE.search(_jd_body_for_signals(jd_text)))


_ROLE_DESC_SECTION_RE = re.compile(
    r"^(what\s+you.{0,10}do|responsibilities|the\s+role|your\s+impact|"
    r"what\s+you.{0,10}own|key\s+responsibilities|what\s+you.{0,10}build|"
    r"day[- ]to[- ]day|in\s+this\s+role)(?:[^\n]{0,20})?\s*:?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_PAIN_SIGNAL_PATTERNS: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bhelp\s+us\s+(\w+(?:\s+\w+){0,3})",
        r"\breduce\s+(\w+(?:\s+\w+){0,4})\b",
        r"\bimprove\s+(\w+(?:\s+\w+){0,4})\b",
        r"\bscale\s+(?:the\s+|our\s+)?(\w+(?:\s+\w+){0,4})\b",
        r"\bgrow\s+(?:the\s+|our\s+)?(\w+(?:\s+\w+){0,4})\b",
        r"\bdrive\s+(\w+(?:\s+\w+){0,4})\b",
        r"\bbuild\s+(?:a\s+|the\s+)?(\w+(?:\s+\w+){0,4})\b",
        r"\bincrease\s+(\w+(?:\s+\w+){0,4})\b",
        r"\bsolve\s+(?:complex\s+)?(\w+(?:\s+\w+){0,4})\b",
        r"\bown\s+(?:the\s+)?(\w+(?:\s+\w+){0,4})\b",
        r"\b(?:lender|borrower|consumer|funnel)\s+(\w+(?:\s+\w+){0,3})\b",
        r"\b(?:run|launch)\s+(\w+(?:\s+\w+){0,4})\b",
    ]
]

_PAIN_STOP_WORDS = frozenset({
    "a", "an", "the", "our", "your", "their", "this", "that", "these",
    "and", "or", "but", "with", "for", "on", "in", "at", "to", "of",
    "we", "you", "they", "us", "team", "role", "company",
})


def _extract_role_desc_section(jd_text: str) -> str:
    m = _ROLE_DESC_SECTION_RE.search(jd_text)
    if m:
        remainder = jd_text[m.end():]
        boundary = _NEXT_SECTION_RE.search(remainder)
        if boundary and boundary.start() > 80:
            return remainder[: boundary.start()].strip()
        return remainder[:2000].strip()
    return jd_text[:3000]


def extract_jd_pain_points(jd_text: str, max_results: int = 5) -> List[str]:
    """Extract short hiring-signal phrases from the JD role description (FR-211).

    Returns up to `max_results` short strings (3-7 words) like
    "reduce churn", "scale the platform", "help us grow" that are
    grounded as literal substrings of the JD. Used for cover story
    selection scoring and opener framing.
    """
    section = _extract_role_desc_section(jd_text)
    section_l = section.lower()
    seen: set = set()
    results: List[str] = []

    for pat in _PAIN_SIGNAL_PATTERNS:
        for m in pat.finditer(section_l):
            captured = m.group(1).strip()
            words = captured.split()
            if not words or words[0] in _PAIN_STOP_WORDS:
                continue
            while words and words[-1].lower() in _PAIN_STOP_WORDS:
                words.pop()
            if not words:
                continue
            verb_part = m.group(0).split(captured)[0].strip()
            full_phrase = f"{verb_part} {' '.join(words)}".strip()
            key = full_phrase[:50]
            if key in seen:
                continue
            seen.add(key)
            results.append(full_phrase)
            if len(results) >= max_results:
                return results

    return results


# ---------------------------------------------------------------------------
# Epic 3 — Proof Point Pre-Selection
# ---------------------------------------------------------------------------

def score_all_claims(
    jd_profile: "JdProfile",
    catalog,
    jd_text: str = "",
) -> List[tuple]:
    """Batch-score all active claims against the JD profile (Story 3.1).

    Returns sorted list of (ClaimRecord, score) tuples, descending by score.
    Disabled claims (catalog.claims with disabled=True or missing) are excluded.
    """
    scored = []
    for claim_id, rec in catalog.claims.items():
        # Skip disabled claims — master_claims.json marks them with "disabled": true.
        # load_catalog() already filters these at load time; this is a defense-in-depth
        # check for callers (including tests) that construct a ClaimCatalog directly.
        if getattr(rec, "disabled", False):
            continue
        raw_text = catalog.raw_truth_lines.get(claim_id, "")
        if not raw_text:
            continue
        # Also check the record body
        body = rec.body or raw_text
        score = score_claim_for_jd(body, jd_profile, jd_text)
        scored.append((rec, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def select_cl_claims(
    jd_profile: "JdProfile",
    catalog,
    resume_claim_ids: List[str],
    jd_text: str = "",
    n: int = 2,
) -> List[object]:
    """Pre-select top n claims for the CL, excluding resume-prominent claims (Story 3.2).

    Claims that appear as the lead bullet for a given employer in the resume
    are down-weighted so the CL introduces a different angle.

    Returns list of ClaimRecord objects (top n).
    """
    scored = score_all_claims(jd_profile, catalog, jd_text)

    # Identify claims to down-weight: those already used as lead resume bullets
    lead_ids = set(resume_claim_ids[:3]) if resume_claim_ids else set()

    results = []
    for rec, score in scored:
        if rec.claim_id in lead_ids:
            continue  # skip resume-prominent claims
        results.append(rec)
        if len(results) >= n:
            break

    # If we didn't get enough, fill from lead claims as a last resort
    if len(results) < n:
        for rec, score in scored:
            if rec in results:
                continue
            results.append(rec)
            if len(results) >= n:
                break

    return results[:n]


def bridge_hints_for_jd(jd_text: str) -> str:
    jd_l = jd_text.lower()
    phrases = load_bridge_phrases()
    lines = []
    for key, out in phrases.items():
        if key.replace("_", " ") in jd_l or key in jd_l:
            lines.append(f"- When source relates to {key.replace('_', ' ')}, prefer framing: {out}")
    return "\n".join(lines[:8])
