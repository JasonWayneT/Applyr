"""
Resume conversion framing guards (FR-216–FR-219).

Detects and enforces outcome-oriented framing vs. activity/defensive language.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

# Tier A: outcome verbs — signal achievement even without a metric
OUTCOME_VERB_RE = re.compile(
    r"^(Stabilized|Drove|Built|Designed|Delivered|Implemented|Reduced|"
    r"Eliminated|Launched|Led|Resolved|Closed|Identified|Prioritized|Replaced|"
    r"Generated|Sustained|Restored|Enabled|Accelerated|Increased|Improved|"
    r"Developed|Established|Executed|Negotiated|Streamlined|Automated|"
    r"Deployed|Migrated|Rebuilt|Architected|Created|Secured|Synthesized|"
    r"Presented|Reverse-engineered|Enforced|Expanded|Owned|Co-created|"
    r"Spearheaded|Introduced|Restructured|Consolidated|Optimized|Scaled|"
    r"Tracked|Formalized|Championed|Refined|Sustained)\b",
    re.IGNORECASE,
)

# Tier B: process/collaboration verbs — activity unless paired with outcome metric
PROCESS_VERB_RE = re.compile(
    r"^(Partnered|Coordinated|Translated|Managed|Facilitated|Navigated|"
    r"Maintained|Scoped|Collaborated|Supported|Assisted|Facilitated)\b",
    re.IGNORECASE,
)

_OUTCOME_METRIC_RE = re.compile(
    r"[\$%]|~\d|\b\d{1,3}%|\b\d{4,}\b|\b\d{1,3}[KkMm]\b",
)

_DEFENSIVE_SUMMARY_PATTERNS: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"security backlog",
        r"security vulnerability",
        r"vulnerability backlog",
        r"complex legacy",
        r"legacy b2b saas",
        r"focused on security",
        r"stabiliz(?:ing|ed)\s+(?:a\s+)?legacy",
        r"maintenance\s+pm",
        r"aging systems",
    ]
]

_SECURITY_JD_RE = re.compile(
    r"\b(security\s+backlog|security\s+engineer|security\s+product|"
    r"vulnerability|penetration\s+test|threat\s+detection|cybersecurity|"
    r"compliance\s+backlog|cve)\b",
    re.IGNORECASE,
)

# Claim IDs that are activity-only for Sterkly (prefer outcome alternatives)
_STERKLY_ACTIVITY_CLAIMS = frozenset({
    "ACC-202-DELIVERY",
    "ACC-202-REQUIREMENTS",
    "ACC-204-GLOBAL",
    "ACC-201-ALIGNMENT",
    "ACC-201-PROCESS",
})

_STERKLY_CONTEXT_CLAIMS = frozenset({
    "ACC-202-DELIVERY",
    "ACC-201-ALIGNMENT",
})

_STERKLY_DOMAIN_JARGON_RE = re.compile(
    r"\b(?:macos|certificates?|vendor sources?|browser extension|competing products?)\b",
    re.IGNORECASE,
)

_STERKLY_CONTEXT_SIGNAL_RE = re.compile(
    r"\b(?:developer|developers|engineering team|consumer|professional services|"
    r"partnered|cross-functional|workflow solutions?|dedicated team)\b",
    re.IGNORECASE,
)

_STERKLY_METRIC_ANCHORS = (
    "ACC-203-BUS",
    "ACC-203-OPS",
    "ACC-203-TECH",
    "ACC-203-INDUSTRY",
)

_STERKLY_WEAK_CLAIMS = frozenset({"ACC-204-QA"})

_STERKLY_QA_REPLACEMENTS = (
    "ACC-203-OPS",
    "ACC-204-GLOBAL",
    "ACC-203-TECH",
)


def has_outcome_metric(text: str) -> bool:
    """True when bullet contains a business outcome metric, not just team-size digits."""
    if not text:
        return False
    if _OUTCOME_METRIC_RE.search(text):
        return True
    # Reject lone small counts like "5-8 developers" as outcome metrics
    if re.search(r"\b\d{1,2}\s*[-–]\s*\d{1,2}\b", text):
        return False
    return bool(re.search(r"\b\d{2,}\b", text))


def is_activity_bullet(text: str) -> bool:
    """Activity-only: process verb opener with no outcome metric."""
    t = (text or "").strip()
    if not t:
        return False
    if has_outcome_metric(t):
        return False
    if OUTCOME_VERB_RE.match(t):
        return False
    return bool(PROCESS_VERB_RE.match(t))


def is_outcome_bullet(text: str) -> bool:
    return not is_activity_bullet(text) and (
        bool(OUTCOME_VERB_RE.match(text)) or has_outcome_metric(text)
    )


def _jd_body_for_signals(jd_text: str, ratio: float = 0.72) -> str:
    """Scan only the JD body, excluding job-board footer category tags."""
    text = jd_text or ""
    return text[: max(1, int(len(text) * ratio))]


def has_security_jd_signal(jd_text: str) -> bool:
    return bool(_SECURITY_JD_RE.search(_jd_body_for_signals(jd_text)))


def defensive_summary_violations(summary: str, jd_text: str = "") -> List[str]:
    if has_security_jd_signal(jd_text):
        return []
    hits: List[str] = []
    for pat in _DEFENSIVE_SUMMARY_PATTERNS:
        m = pat.search(summary or "")
        if m:
            hits.append(m.group(0))
    return hits


def metric_count_for_bullets(bullets: Dict[str, str]) -> Dict[str, int]:
    from candidate_context import employer_tiers, load_employers_ordered
    from local_draft_stages import employer_for_claim_id

    ordered = load_employers_ordered()
    counts: Dict[str, int] = {slug: 0 for slug in ordered}
    for cid, text in bullets.items():
        emp = employer_for_claim_id(cid)
        if emp in counts and has_outcome_metric(text):
            counts[emp] += 1
    return counts


def impact_pyramid_inverted(bullets: Dict[str, str]) -> bool:
    """Junior role has more outcome metrics than a senior role."""
    from candidate_context import employer_tiers

    senior, mid, junior = employer_tiers()
    c = metric_count_for_bullets(bullets)
    if c.get(junior, 0) > c.get(senior, 0):
        return True
    if c.get(junior, 0) > c.get(mid, 0) and c.get(mid, 0) > 0:
        return True
    return False


def _jd_keyword_score(jd_lower: str, text: str) -> int:
    words = set(re.findall(r"[a-z]{4,}", jd_lower))
    text_l = text.lower()
    return sum(1 for w in words if w in text_l)


def enforce_sterkly_metric_anchor(
    bullets: Dict[str, str],
    valid_ids: Dict[str, str],
    jd_text: str,
    fallback_bullet_fn,
) -> Dict[str, str]:
    """Ensure mid-career employer has at least one outcome-metric bullet (FR-217)."""
    from candidate_context import employer_tiers
    from local_draft_stages import employer_for_claim_id

    _, mid_slug, _ = employer_tiers()
    mid_claims = [c for c in bullets if employer_for_claim_id(c) == mid_slug]
    if any(has_outcome_metric(bullets[c]) for c in mid_claims):
        return bullets

    jd_lower = jd_text.lower()
    for anchor in _STERKLY_METRIC_ANCHORS:
        if anchor not in valid_ids or anchor in bullets:
            continue
        victims = sorted(
            [c for c in mid_claims if c in _STERKLY_ACTIVITY_CLAIMS or is_activity_bullet(bullets[c])],
            key=lambda c: _jd_keyword_score(jd_lower, bullets.get(c, "")),
        )
        if not victims:
            victims = sorted(mid_claims, key=lambda c: _jd_keyword_score(jd_lower, bullets.get(c, "")))
        if not victims:
            break
        victim = victims[0]
        del bullets[victim]
        bullets[anchor] = fallback_bullet_fn(valid_ids[anchor])
        break
    return bullets


def enforce_activity_cap(
    bullets: Dict[str, str],
    valid_ids: Dict[str, str],
    jd_text: str,
    fallback_bullet_fn,
    max_activity: int = 1,
) -> Dict[str, str]:
    """Max `max_activity` activity-only bullets per employer (FR-218)."""
    from local_draft_stages import employer_for_claim_id, EMPLOYERS

    jd_lower = jd_text.lower()
    for employer in EMPLOYERS:
        emp_cids = [c for c in bullets if employer_for_claim_id(c) == employer]
        from candidate_context import employer_tiers

        _, mid_slug, _ = employer_tiers()
        cap = max_activity
        if employer == mid_slug and any(has_outcome_metric(bullets[c]) for c in emp_cids):
            # Keep one context-bridge bullet (e.g. ACC-202-DELIVERY) alongside metric anchors.
            cap = 1 if any(c in _STERKLY_CONTEXT_CLAIMS for c in emp_cids) else 0
        activity = [
            c
            for c in emp_cids
            if is_activity_bullet(bullets[c]) and c not in _STERKLY_CONTEXT_CLAIMS
        ]
        while len(activity) > cap:
            victim = min(activity, key=lambda c: _jd_keyword_score(jd_lower, bullets[c]))
            del bullets[victim]
            activity.remove(victim)
            pool = [
                cid
                for cid, body in valid_ids.items()
                if employer_for_claim_id(cid) == employer
                and cid not in bullets
                and cid not in _STERKLY_WEAK_CLAIMS
                and (
                    is_outcome_bullet(body)
                    or (
                        employer == mid_slug
                        and (
                            cid in _STERKLY_CONTEXT_CLAIMS
                            or _STERKLY_CONTEXT_SIGNAL_RE.search(body)
                        )
                    )
                )
            ]
            if not pool:
                break

            def _swap_score(cid: str) -> tuple:
                jd_s = _jd_keyword_score(jd_lower, valid_ids[cid])
                prefer = (
                    2
                    if employer == mid_slug and cid in _STERKLY_QA_REPLACEMENTS
                    else 0
                )
                metric = 1 if has_outcome_metric(valid_ids[cid]) else 0
                return (prefer, metric, jd_s)

            pool.sort(key=_swap_score, reverse=True)
            swap = pool[0]
            bullets[swap] = fallback_bullet_fn(valid_ids[swap])
    return bullets


def enforce_impact_pyramid(
    bullets: Dict[str, str],
    valid_ids: Dict[str, str],
    jd_text: str,
    fallback_bullet_fn,
) -> Dict[str, str]:
    """Swap senior-role activity bullets for metric outcome claims when pyramid is inverted (FR-219)."""
    from local_draft_stages import employer_for_claim_id

    jd_lower = jd_text.lower()
    for _ in range(4):
        if not impact_pyramid_inverted(bullets):
            break
        from candidate_context import employer_tiers

        senior, _, junior = employer_tiers()
        c = metric_count_for_bullets(bullets)
        if c.get(junior, 0) <= c.get(senior, 0):
            break
        senior_cids = [c for c in bullets if employer_for_claim_id(c) == senior]
        victims = sorted(
            [c for c in senior_cids if is_activity_bullet(bullets[c]) or not has_outcome_metric(bullets[c])],
            key=lambda c: _jd_keyword_score(jd_lower, bullets[c]),
        )
        pool = [
            cid
            for cid, body in valid_ids.items()
            if employer_for_claim_id(cid) == senior
            and cid not in bullets
            and has_outcome_metric(body)
        ]
        pool.sort(key=lambda cid: _jd_keyword_score(jd_lower, valid_ids[cid]), reverse=True)
        if not victims or not pool:
            break
        del bullets[victims[0]]
        swap = pool[0]
        bullets[swap] = fallback_bullet_fn(valid_ids[swap])
    return bullets


def _sterkly_texts_fail_cw012(texts: List[str]) -> bool:
    jargon = sum(1 for t in texts if _STERKLY_DOMAIN_JARGON_RE.search(t))
    has_context = any(_STERKLY_CONTEXT_SIGNAL_RE.search(t) for t in texts)
    return jargon >= 2 and not has_context


def _best_sterkly_context_claim(
    valid_ids: Dict[str, str],
    mid_slug: str,
    jd_lower: str,
) -> Optional[str]:
    from local_draft_stages import employer_for_claim_id

    ranked: List[tuple] = []
    for cid, body in valid_ids.items():
        if employer_for_claim_id(cid) != mid_slug:
            continue
        if cid in _STERKLY_CONTEXT_CLAIMS or _STERKLY_CONTEXT_SIGNAL_RE.search(body):
            ranked.append((_jd_keyword_score(jd_lower, body), cid))
    if not ranked:
        return None
    ranked.sort(reverse=True)
    return ranked[0][1]


def enforce_sterkly_context(
    bullets: Dict[str, str],
    valid_ids: Dict[str, str],
    jd_text: str,
    fallback_bullet_fn,
) -> Dict[str, str]:
    """Ensure mid-career employer has a PM-context bullet when domain jargon dominates (FR-222 / FR-248)."""
    from candidate_context import employer_tiers
    from local_draft_stages import employer_for_claim_id

    _, mid_slug, _ = employer_tiers()
    mid_claims = [c for c in bullets if employer_for_claim_id(c) == mid_slug]
    if not mid_claims:
        return bullets

    texts = [bullets[c] for c in mid_claims]
    if not _sterkly_texts_fail_cw012(texts):
        return bullets

    jd_lower = jd_text.lower()
    context_id = _best_sterkly_context_claim(valid_ids, mid_slug, jd_lower)
    if not context_id:
        return bullets

    if context_id in bullets:
        return bullets

    victims = sorted(
        [
            c
            for c in mid_claims
            if _STERKLY_DOMAIN_JARGON_RE.search(bullets[c])
            or is_activity_bullet(bullets[c])
        ],
        key=lambda c: (
            1 if c in _STERKLY_METRIC_ANCHORS and has_outcome_metric(bullets[c]) and "$" in bullets[c] else 0,
            0 if _STERKLY_DOMAIN_JARGON_RE.search(bullets[c]) else 1,
            _jd_keyword_score(jd_lower, bullets[c]),
        ),
    )
    if not victims:
        victims = sorted(
            [c for c in mid_claims if c not in ("ACC-203-BUS",)],
            key=lambda c: _jd_keyword_score(jd_lower, bullets[c]),
        )
    if not victims:
        return bullets

    del bullets[victims[0]]
    bullets[context_id] = fallback_bullet_fn(valid_ids[context_id])
    return bullets


def enforce_sterkly_weak_claim_swap(
    bullets: Dict[str, str],
    valid_ids: Dict[str, str],
    jd_text: str,
    fallback_bullet_fn,
) -> Dict[str, str]:
    """Replace task-only Sterkly QA claim with metric/scope alternatives (FR-225)."""
    victims = [c for c in _STERKLY_WEAK_CLAIMS if c in bullets]
    if not victims:
        return bullets
    jd_lower = jd_text.lower()
    for victim in victims:
        pool = [
            cid
            for cid in _STERKLY_QA_REPLACEMENTS
            if cid in valid_ids and cid not in bullets
        ]
        pool.sort(key=lambda cid: _jd_keyword_score(jd_lower, valid_ids[cid]), reverse=True)
        if not pool:
            continue
        del bullets[victim]
        swap = pool[0]
        bullets[swap] = fallback_bullet_fn(valid_ids[swap])
    return bullets


def ensure_sterkly_narrative_pass(
    bullets: Dict[str, str],
    valid_ids: Dict[str, str],
    jd_text: str,
    fallback_bullet_fn,
    max_passes: int = 3,
) -> Dict[str, str]:
    """Repeat Sterkly context swap until CW-012 would pass (FR-248)."""
    for _ in range(max_passes):
        from candidate_context import employer_tiers
        from local_draft_stages import employer_for_claim_id

        _, mid_slug, _ = employer_tiers()
        mid_claims = [c for c in bullets if employer_for_claim_id(c) == mid_slug]
        if not mid_claims:
            break
        texts = [bullets[c] for c in mid_claims]
        if not _sterkly_texts_fail_cw012(texts):
            break
        before = dict(bullets)
        bullets = enforce_sterkly_context(bullets, valid_ids, jd_text, fallback_bullet_fn)
        if bullets == before:
            break
    return bullets


def enforce_activity_metric_swap(
    bullets: Dict[str, str],
    valid_ids: Dict[str, str],
    jd_text: str,
    fallback_bullet_fn,
) -> Dict[str, str]:
    """Swap one activity-only bullet per employer when a metric claim is available (FR-249)."""
    from local_draft_stages import employer_for_claim_id, EMPLOYERS

    jd_lower = jd_text.lower()
    for employer in EMPLOYERS:
        emp_cids = [c for c in bullets if employer_for_claim_id(c) == employer]
        activity = [
            c
            for c in emp_cids
            if is_activity_bullet(bullets[c]) and c not in _STERKLY_CONTEXT_CLAIMS
        ]
        if not activity:
            continue
        pool = [
            cid
            for cid, body in valid_ids.items()
            if employer_for_claim_id(cid) == employer
            and cid not in bullets
            and has_outcome_metric(body)
            and is_outcome_bullet(body)
        ]
        if not pool:
            continue
        victim = min(activity, key=lambda c: _jd_keyword_score(jd_lower, bullets[c]))
        pool.sort(key=lambda cid: _jd_keyword_score(jd_lower, valid_ids[cid]), reverse=True)
        del bullets[victim]
        swap = pool[0]
        bullets[swap] = fallback_bullet_fn(valid_ids[swap])
    return bullets


def enforce_conversion_framing(
    bullets: Dict[str, str],
    valid_ids: Dict[str, str],
    jd_text: str,
    fallback_bullet_fn,
) -> Dict[str, str]:
    """Run all conversion framing enforcers in dependency order."""
    bullets = enforce_sterkly_metric_anchor(bullets, valid_ids, jd_text, fallback_bullet_fn)
    bullets = enforce_impact_pyramid(bullets, valid_ids, jd_text, fallback_bullet_fn)
    bullets = enforce_activity_cap(bullets, valid_ids, jd_text, fallback_bullet_fn)
    bullets = enforce_activity_metric_swap(bullets, valid_ids, jd_text, fallback_bullet_fn)
    bullets = enforce_sterkly_weak_claim_swap(bullets, valid_ids, jd_text, fallback_bullet_fn)
    bullets = ensure_sterkly_narrative_pass(bullets, valid_ids, jd_text, fallback_bullet_fn)
    return bullets
