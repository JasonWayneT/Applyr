"""
Experience-backed JD themes (FR-224).

Resume summary may only claim themes supported by selected bullet text.
JD-only themes belong in cover-letter transferable framing, not the career headline.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence

from jd_tailoring import THEME_KEYWORDS

_THEME_KEY_FROM_PHRASE = {phrase: kw for kw, phrase in THEME_KEYWORDS}

# Strict corpus signals — theme phrase is resume-safe only when pattern matches bullets.
_THEME_EXPERIENCE_PATTERNS: Dict[str, re.Pattern] = {
    "analytics product delivery and adoption": re.compile(
        r"\banalytics\b|business intelligence|\bBI\b|\bKPIs?\b|\bdashboards?\b",
        re.IGNORECASE,
    ),
    "KPI-driven product delivery": re.compile(
        r"\bKPIs?\b|key performance",
        re.IGNORECASE,
    ),
    "product adoption and measurable outcomes": re.compile(
        r"\badoption\b|\bactive users?\b|\bengagement\b",
        re.IGNORECASE,
    ),
    "analytics for sales and underwriting workflows": re.compile(
        r"\bunderwriting\b|\bsales analytics\b",
        re.IGNORECASE,
    ),
    "API integration and cross-system workflows": re.compile(
        r"\bAPIs?\b|\bRESTful\b|\bREST\b",
        re.IGNORECASE,
    ),
    "data integrity and ingestion": re.compile(
        r"\bingestion\b|upstream|data (?:pipeline|failure|drop|integrity)|"
        r"schema change|(?:\betl\b)|data provider",
        re.IGNORECASE,
    ),
    "platform reliability and scale": re.compile(
        r"\bplatform\b|churn|stability|reliability|\bARR\b|enterprise accounts",
        re.IGNORECASE,
    ),
    "security backlog and risk reduction": re.compile(
        r"security (?:backlog|vulnerability)|vulnerability backlog",
        re.IGNORECASE,
    ),
    "customer migration and retention": re.compile(
        r"\bmigration\b|retention|churn",
        re.IGNORECASE,
    ),
    "media and audience data products": re.compile(
        r"\bmedia\b|audience|monitoring",
        re.IGNORECASE,
    ),
    "intelligence and analytics platform evolution": re.compile(
        r"\bintelligence\b|\banalytics platform\b",
        re.IGNORECASE,
    ),
}

_STOP = frozenset({"through", "across", "delivery", "product", "platform", "scale"})


def _corpus_normalize(corpus: str) -> str:
    return re.sub(r"\s+", " ", (corpus or "")).strip().lower()


def is_theme_experience_backed(theme_phrase: str, corpus: str) -> bool:
    """True when selected resume bullets substantiate this JD theme phrase."""
    c = _corpus_normalize(corpus)
    if not c or not theme_phrase:
        return False

    pat = _THEME_EXPERIENCE_PATTERNS.get(theme_phrase.strip())
    if pat:
        return bool(pat.search(c))

    # Generic fallback: substantive tokens from theme label appear in corpus.
    label = theme_phrase.split(" and ", 1)[0].strip().lower()
    tokens = [
        w
        for w in re.findall(r"[a-z]{5,}", label)
        if w not in _STOP
    ]
    if not tokens:
        return False
    hits = sum(1 for t in tokens if t in c)
    return hits >= max(1, len(tokens) // 2)


def filter_experience_backed_themes(
    themes: Sequence[str],
    corpus: str,
) -> List[str]:
    """Preserve JD theme order; drop phrases not supported by bullet corpus."""
    return [t for t in themes if t and is_theme_experience_backed(t, corpus)]


def jd_only_themes(
    themes: Sequence[str],
    corpus: str,
    jd_text: str = "",
) -> List[str]:
    """Themes in the JD profile that are transferable but not resume-headline safe."""
    backed = set(filter_experience_backed_themes(themes, corpus))
    out = [t for t in themes if t and t not in backed]
    if not jd_text or not out:
        return out

    jd_l = jd_text.lower()

    def _salience(theme: str) -> tuple:
        key = _THEME_KEY_FROM_PHRASE.get(theme, "")
        label = theme.lower()
        in_jd = 0 if key and key in jd_l else 1
        if "analytics" in label or "kpi" in label:
            bucket = 0
        elif "api" in label or "restful" in label:
            bucket = 3
        else:
            bucket = 1
        return (in_jd, bucket)

    out.sort(key=_salience)
    return out


def build_transferable_bridge(
    experience_themes: Sequence[str],
    all_themes: Sequence[str],
    corpus: str,
    jd_text: str = "",
) -> str:
    """Cover-letter bridge: name JD emphasis + grounded experience (not a resume claim)."""
    jd_only = jd_only_themes(all_themes, corpus, jd_text=jd_text)
    if not jd_only or not experience_themes:
        return ""
    from cover_prose import format_themes_for_prose, _short_theme_label

    exp = format_themes_for_prose(list(experience_themes), max_items=2)
    target = _short_theme_label(jd_only[0])
    return (
        f"This role emphasizes {target}; my track record in {exp} "
        f"transfers directly to that scope."
    )


def summary_focus_phrase(
    themes: Sequence[str],
    corpus: str,
    max_items: int = 2,
    theme_skip: int = 0,
) -> Optional[str]:
    """Experience-backed phrase for 'most recently focused on …' summary opener."""
    backed = filter_experience_backed_themes(themes, corpus)
    if theme_skip:
        backed = backed[theme_skip:]
    if not backed:
        return None
    from cover_prose import format_themes_for_prose

    return format_themes_for_prose(backed, max_items=max_items)
