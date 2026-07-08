"""
Deterministic cover-letter voice phrasing (CR-043 / FR-233).

No LLM rewrite — templates and banned-phrase rules only.
See docs/spec/03-feature-specs/cover_voice.example.md.
"""
from __future__ import annotations

import re
from typing import List

WORD_MIN = 300
WORD_MIN_NEED_FIRST = 250
WORD_MAX = 400
CHAR_MAX = 2800


def word_min_for_variant(opening_variant: str) -> int:
    if opening_variant == "need_first":
        return WORD_MIN_NEED_FIRST
    return WORD_MIN

# Casual / dictation openers — never in submission covers
BANNED_CASUAL_PATTERNS: List[re.Pattern] = [
    re.compile(r"^\s*okay\s+so\b", re.I),
    re.compile(r"\bright\?\b", re.I),
    re.compile(r"\byou know\?\b", re.I),
    re.compile(r"\bpush back\b", re.I),
]

# Corporate / AI filler — prefer plain PM language from cover_voice spec
BANNED_ROBOT_PHRASES: tuple[str, ...] = (
    "That experience is directly relevant to",
    "That experience is relevant to",
    "Together, these examples reflect",
    "translate platform requirements into shipped, measurable outcomes",
    "aligned with the Engineering and Data partnership model",
    "with the same discipline on metrics, stakeholder alignment, and platform delivery described above",
)

# Cover grammar defects the pipeline must never ship (CLW-005).
_COVER_GRAMMAR_DEFECTS: tuple[re.Pattern, ...] = (
    re.compile(r"\bhad no documentation remained\b", re.I),
    re.compile(r"\bno documentation remained and\b", re.I),
)

# Formal words Jason does not use in covers (replace with plain alternatives)
_COVER_PHRASE_POLISH: tuple[tuple[str, str], ...] = (
    ("unreliable ETL processes", "failing ETL processes"),
    ("actively breaking mid-project", "becoming unstable during the migration"),
    # Longer phrase first — avoids "had no surviving documentation" → ungrammatical seam.
    ("had no surviving documentation", "had no documentation left"),
    ("no surviving documentation", "no documentation left"),
    ("job-to-be-done failure", "product trust problem"),
    # JTBD jargon → plain language
    ("a JTBD failure", "a product trust problem"),
    ("JTBD failure", "product trust problem"),
    # Comma-splice pattern from ACC-102 cover_story:
    # "Customers told us X was wrong, that was a problem" → "When customers said X was wrong, I treated it as a problem"
    (
        "Customers told us the contact data in the product was wrong, that was a product trust problem, not a minor bug.",
        "When customers said the contact data in the product was wrong, I treated it as a product trust problem, not a minor data bug.",
    ),
    (
        "Customers told us the contact data in the product was wrong,",
        "When customers said the contact data in the product was wrong,",
    ),
    (
        "Business and customer wins moved together",
        "Customer trust and the business outcome improved together",
    ),
    ("credible successor path", "realistic migration path"),
    ("was costing us", "was hurting"),
    ("that kind of problem was central to the role", "the kind of problem I was responsible for solving"),
    ("managed in parallel", "balanced at the same time"),
    ("entirely from system behavior", "by studying system behavior"),
    (
        "subsequently requested the rebuild as the reference model",
        "later used it as their reference model",
    ),
    (
        "structural bypass of failing ETL paths",
        "more reliable data path around failing ETL processes",
    ),
)

_CRISIS_TO_CALM: tuple[tuple[str, str], ...] = (
    ("catastrophic", "significant"),
    ("actively breaking", "becoming unstable"),
)

_FORMAL_TO_PLAIN: tuple[tuple[str, str], ...] = (
    (r"\butilize\b", "use"),
    (r"\bleverage\b", "use"),
    (r"\bfurthermore\b", ""),
    (r"\bmoreover\b", ""),
    (r"\bit is worth noting that\b", ""),
)


def _first_clause(need: str, max_len: int = 50) -> str:
    raw = (need or "").strip().rstrip(".")
    if not raw:
        return ""
    first = raw.split(",")[0].strip()
    if len(first) >= 20:
        return first if len(first) <= max_len else first[:max_len].rsplit(" ", 1)[0]
    from cover_jd_needs import need_to_goal_phrase

    goal = need_to_goal_phrase(need)
    if goal:
        clause = goal.split(",")[0].strip()
        if len(clause) >= 20:
            return clause if len(clause) <= max_len else clause[:max_len].rsplit(" ", 1)[0]
    return raw[:max_len].rsplit(" ", 1)[0] if len(raw) > max_len else raw


def audit_need_fragment(need: str) -> str:
    """Substring auditors check for (goal[:50] or need[:35])."""
    return _first_clause(need, 50)


def short_goal_for_close(need: str) -> str:
    return _first_clause(need, 95)


IDENTITY_CLAUSE = (
    "I am an outcome-driven implementer: voice-of-customer and churn signals "
    "drive what I prioritize with engineering."
)

_OPENING_DEDUP_PHRASES = (
    "track record",
    "platform reliability",
    "data integrity",
    "structured data",
    "cross-functional",
    "analytics product",
    "your posting emphasizes",
    "transfers directly",
    "aligns with my",
)


def jd_presence_clause(need: str) -> str:
    """Deprecated for opener — tenure and JD mirroring belong in stories, not claims."""
    from cover_jd_needs import is_tenure_requirement

    if is_tenure_requirement(need):
        return ""
    return ""


def render_trust_hook(story: str) -> str:
    """Trust-principle hook from primary cover_story (CR-047).

    Returns the first sentence of the story with JTBD jargon converted to plain language.
    Does NOT unconditionally append 'product trust problem' — that framing only belongs
    when the story is about data quality / trust (ACC-102 pattern).  Appending it to
    unrelated stories (cost-savings, platform deprecation) creates semantic mismatch and
    duplicate phrases when ACC-102 appears as a proof paragraph in the same letter.
    """
    lead = value_lead_from_story(story)
    if not lead:
        return ""
    out = re.sub(r"\s*(?:—|--)\s*", ", ", lead)
    out = re.sub(r"\bCustomers told us\b", "When customers said", out, flags=re.I)
    # Convert inline JTBD jargon when present in the lead sentence
    out = re.sub(
        r",?\s*that was a job-to-be-done failure, not a minor bug\.?",
        ", I treated it as a product trust problem, not a minor data bug.",
        out,
        flags=re.I,
    )
    if not out.endswith("."):
        out += "."
    return out


def value_lead_from_story(story: str) -> str:
    """Extractive opener hook: first sentence only; metrics stay in proof paragraphs."""
    text = (story or "").strip()
    if not text:
        return ""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sentences:
        return ""
    lead = sentences[0]
    return lead if lead.endswith((".", "!", "?")) else f"{lead}."


def _normalize_hook_punct(text: str) -> str:
    return re.sub(r"\s*(?:—|--)\s*", ", ", text).strip()


def _hook_sentence_variants(hook: str) -> List[str]:
    """Alternate phrasings of the same trust hook for dedupe."""
    variants = [hook]
    core = hook.rstrip(".").strip()
    if core:
        variants.append(core)
    swapped = re.sub(
        r"\bCustomers told us\b",
        "When customers said",
        core,
        flags=re.I,
    )
    if swapped != core:
        variants.extend((swapped, f"{swapped}."))
    swapped2 = re.sub(
        r"\bWhen customers said\b",
        "Customers told us",
        core,
        flags=re.I,
    )
    if swapped2 != core:
        variants.extend((swapped2, f"{swapped2}."))
    return variants


def strip_opener_hook_from_body(body_para: str, hook: str) -> str:
    """Remove duplicated first sentence when proof paragraph repeats the opener hook."""
    para = _normalize_hook_punct((body_para or "").strip())
    hook = _normalize_hook_punct((hook or "").strip())
    if not para or not hook:
        return (body_para or "").strip()
    for variant in _hook_sentence_variants(hook):
        variant = _normalize_hook_punct(variant)
        if para.startswith(variant):
            rest = para[len(variant) :].lstrip().lstrip(".")
            return rest if rest else para
        core = variant.rstrip(".").strip()
        if para.startswith(core):
            rest = para[len(core) :].lstrip().lstrip(".")
            return rest if rest else para
    return (body_para or "").strip()


def dedupe_opening_paragraph(text: str) -> str:
    """Drop sentences that repeat the same fit phrase already stated."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    seen: set[str] = set()
    kept: list[str] = []
    for sent in sentences:
        sent_l = sent.lower()
        redundant = False
        for phrase in _OPENING_DEDUP_PHRASES:
            if phrase in sent_l and phrase in seen:
                redundant = True
                break
            if phrase in sent_l:
                seen.add(phrase)
        if not redundant:
            kept.append(sent if sent.endswith((".", "!", "?")) else f"{sent}.")
    return " ".join(kept)


def apply_cover_phrase_polish(text: str) -> str:
    """Cover-letter phrase map from Splash iteration (CR-047)."""
    if not text:
        return text
    out = text
    for old, new in _COVER_PHRASE_POLISH + _CRISIS_TO_CALM:
        out = out.replace(old, new)
    out = re.sub(
        r"\bbalancing\b([^,.]*)\bat the same time\b",
        r"balancing\1",
        out,
        flags=re.I,
    )
    return out


def _format_outcome_chain(outcomes: list[str]) -> str:
    if not outcomes:
        return "measurable product outcomes"
    if len(outcomes) == 1:
        return outcomes[0]
    if len(outcomes) == 2:
        return f"{outcomes[0]} and {outcomes[1]}"
    return f"{', '.join(outcomes[:-1])}, and {outcomes[-1]}"


def _dedupe_overlapping_targets(targets: list[str]) -> list[str]:
    """Drop redundant JD targets (e.g. 'product adoption' inside 'analytics product adoption')."""
    if len(targets) < 2:
        return targets
    kept: list[str] = []
    for t in sorted(targets, key=len, reverse=True):
        tl = t.lower()
        if any(tl in k.lower() or k.lower() in tl for k in kept if k.lower() != tl):
            continue
        kept.append(t)
    order = {t: i for i, t in enumerate(targets)}
    kept.sort(key=lambda x: order.get(x, 99))
    return kept


def check_cover_grammar_defects(text: str) -> list[str]:
    """Return CLW-005 issues for cover grammar seams introduced by phrase polish."""
    issues: list[str] = []
    for pat in _COVER_GRAMMAR_DEFECTS:
        m = pat.search(text or "")
        if m:
            issues.append(
                "[CLW-005] Cover grammar defect (phrase-polish seam): "
                f"\"{m.group(0)}\""
            )
            break
    return issues


def render_structured_close(
    company: str, jd_text: str, archetype_id: str = ""
) -> str:
    """JD-grounded close with verb variety and outcome chain (CR-047, all archetypes)."""
    from cover_jd_needs import extract_role_outcomes, extract_role_targets

    jd_l = jd_text.lower()
    if archetype_id == "product_domain":
        if any(m in jd_l for m in ("financ", "dealer", "consumer", "point-of-sale", "point of sale")):
            experience_phrase = (
                "financing experiences for dealers and customers"
                if "dealer" in jd_l
                else "customer-facing financing experiences"
            )
            return (
                f"I would welcome the opportunity to discuss how this background could help "
                f"{company} improve roadmap clarity, cross-functional delivery, and "
                f"{experience_phrase} where trust, speed, and reliable execution matter."
            )
        return (
            f"I would welcome the opportunity to discuss how this background could help "
            f"{company} improve roadmap clarity, cross-functional delivery, and "
            f"measurable product outcomes that depend on trust and reliable execution."
        )

    targets = _dedupe_overlapping_targets(extract_role_targets(jd_text, max_n=2))
    outcomes = extract_role_outcomes(jd_text, max_n=3)

    # Remove outcomes that duplicate or overlap a target — prevents circular closes.
    def _overlaps_target(phrase: str) -> bool:
        pl = phrase.lower()
        return any(
            pl == t.lower() or pl in t.lower() or t.lower() in pl for t in targets
        )

    outcomes = [o for o in outcomes if not _overlaps_target(o)]

    outcome_chain = _format_outcome_chain(outcomes)
    jd_l = jd_text.lower()

    # When no JD-specific outcomes were found the fallback "measurable product outcomes"
    # would produce "the product outcomes that drive measurable product outcomes" — circular.
    # Use a non-circular alternative that still closes forward.
    _GENERIC_FALLBACK = "measurable product outcomes"

    if len(targets) >= 2:
        t1, t2 = targets[0], targets[1]
        if archetype_id == "marketplace_fintech" and "borrower" in jd_l and "offer experience" in jd_l:
            if "borrower offer" not in t2.lower():
                t2 = "the borrower offer experience"
        if outcome_chain == _GENERIC_FALLBACK:
            return (
                f"I would welcome the opportunity to discuss how this background could help "
                f"{company} improve {t1}, strengthen {t2}, and deliver measurable outcomes "
                f"across the priorities in your posting."
            )
        return (
            f"I would welcome the opportunity to discuss how this background could help "
            f"{company} improve {t1}, strengthen {t2}, and improve "
            f"the product outcomes that drive {outcome_chain}."
        )
    if targets:
        if outcome_chain == _GENERIC_FALLBACK:
            return (
                f"I would welcome the opportunity to discuss how this background could help "
                f"{company} improve {targets[0]} and deliver measurable outcomes "
                f"across the priorities in your posting."
            )
        return (
            f"I would welcome the opportunity to discuss how this background could help "
            f"{company} improve {targets[0]} and the product outcomes that drive "
            f"{outcome_chain}."
        )
    return render_forward_close(company, jd_text)


# Backward-compatible alias
render_need_first_close = render_structured_close


def render_forward_close(company: str, jd_text: str) -> str:
    """Forward-looking close tied to a specific JD business problem."""
    from cover_jd_needs import extract_role_challenge

    challenge = extract_role_challenge(jd_text)
    if challenge:
        return (
            f"I would welcome a conversation about how this background could help "
            f"{company} {challenge}."
        )
    return render_close(company, "")


def render_close(company: str, jd_goal: str) -> str:
    goal = short_goal_for_close(jd_goal or "")
    if goal and goal[0].isdigit():
        return (
            f"I would welcome a conversation about how this background can help {company} "
            f"deliver on the analytics and platform priorities in your posting, "
            f"including the metrics and cross-functional delivery patterns above."
        )
    if goal:
        return (
            f"I would welcome a conversation about how this background can help {company} "
            f"on {goal}, including the metrics and cross-functional delivery patterns above."
        )
    return (
        f"I would welcome the opportunity to discuss how this background could help "
        f"{company} deliver on the priorities in your posting."
    )


def apply_voice_polish(text: str) -> str:
    """Light deterministic de-robotizing; preserves metrics and cover_story prose."""
    if not text:
        return text
    out = text
    for phrase in BANNED_ROBOT_PHRASES:
        out = out.replace(phrase, "")
    for pat, repl in _FORMAL_TO_PLAIN:
        out = re.sub(pat, repl, out, flags=re.I)
    out = apply_cover_phrase_polish(out)
    out = re.sub(r"\s*(?:—|--)\s*", ", ", out)
    out = re.sub(r"  +", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def strip_banned_casual(text: str) -> str:
    out = text
    for pat in BANNED_CASUAL_PATTERNS:
        out = pat.sub("", out)
    return re.sub(r"  +", " ", out).strip()
