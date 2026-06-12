"""JD need extraction for independent cover pipeline (CR-024)."""
from __future__ import annotations

import re
from typing import List, Tuple

from jd_tailoring import JdProfile, _substring_valid, build_jd_profile_deterministic

_INCOMPLETE_ENDINGS = (
    " and",
    " or",
    " to",
    " for",
    " with",
    " the",
    " a",
    " an",
    " in",
    " on",
    " of",
    " that",
    " actionable",
    " scalable",
)


def _clause_valid(clause: str, jd_text: str) -> bool:
    c = clause.strip()
    if len(c) < 40 or len(c) > 160:
        return False
    if re.search(r"\d{5,}", c.replace(",", "")):
        return False
    if not _substring_valid(c, jd_text):
        return False
    low = c.lower().rstrip(".")
    for bad in _INCOMPLETE_ENDINGS:
        if low.endswith(bad):
            return False
    if len(c.split()) < 8:
        return False
    return True


_TENURE_RE = re.compile(r"\d+\+?\s*years?\s+of\b", re.I)

_ROLE_SECTION_MARKERS = (
    "what you'll do",
    "what you will do",
    "responsibilities",
    "the role",
    "position summary",
    "you will",
)


def is_tenure_requirement(need: str) -> bool:
    return bool(_TENURE_RE.search((need or "").strip()))


def _extract_role_action_paragraphs(jd_text: str) -> List[str]:
    """Pull responsibility prose from common Built In / corporate JD sections."""
    lines = jd_text.splitlines()
    blocks: List[str] = []
    i = 0
    while i < len(lines):
        low = lines[i].strip().lower()
        if any(low.startswith(m) for m in _ROLE_SECTION_MARKERS):
            i += 1
            chunk: List[str] = []
            while i < len(lines):
                raw = lines[i].strip()
                low_next = raw.lower()
                if not raw:
                    if chunk:
                        break
                    i += 1
                    continue
                if any(
                    low_next.startswith(h)
                    for h in (
                        "what you'll bring",
                        "what you will bring",
                        "qualification",
                        "requirements",
                        "preferred",
                        "education",
                        "about ",
                    )
                ):
                    break
                if raw.startswith(("-", "•", "*")) and len(raw) < 120:
                    cleaned = re.sub(r"^[-•*]\s*", "", raw).strip()
                    if cleaned:
                        blocks.append(cleaned[:160])
                    i += 1
                    continue
                chunk.append(raw)
                i += 1
            if chunk:
                para = " ".join(chunk).strip()
                if len(para) >= 40:
                    blocks.append(para[:200])
            continue
        i += 1
    return blocks


_OUTCOME_PATTERNS: tuple[tuple[str, str], ...] = (
    ("funded volume", "funded volume"),
    ("approval rate", "approval rates"),
    ("approval rates", "approval rates"),
    ("funnel conversion", "funnel conversion"),
    ("partner satisfaction", "partner satisfaction"),
    ("platform adoption", "platform adoption"),
    ("product adoption", "product adoption"),
    ("device reliability", "device reliability"),
    ("interoperability", "platform interoperability"),
    ("conversion", "conversion"),
)


_TARGET_PATTERNS: tuple[tuple[str, str], ...] = (
    ("vendor integration", "vendor integrations"),
    ("vendor integrations", "vendor integrations"),
    ("device lifecycle", "device lifecycle"),
    ("personal safety device", "personal safety device programs"),
    ("connected device", "connected device integrations"),
    ("lender integration", "lender integrations"),
    ("lender integrations", "lender integrations"),
    ("borrower offer experience", "the borrower offer experience"),
    ("borrower experience", "borrower experience"),
    ("borrower-lender match", "borrower-lender matching"),
    ("lender onboarding", "lender partner onboarding"),
    ("partner onboarding", "lender partner onboarding"),
    ("analytics products", "analytics product adoption"),
    ("analytics product", "analytics product adoption"),
    ("platform adoption", "platform adoption"),
    ("product adoption", "product adoption"),
    ("roadmap prioritization", "roadmap prioritization"),
)


_FINTECH_OUTCOME_ORDER: tuple[str, ...] = (
    "funnel conversion",
    "approval rates",
    "funded volume",
    "partner satisfaction",
)


def extract_role_outcomes(jd_text: str, max_n: int = 3) -> List[str]:
    """JD-grounded business outcomes for cover close (CR-047)."""
    jd_l = jd_text.lower()
    found: List[str] = []
    seen: set = set()
    for needle, label in _OUTCOME_PATTERNS:
        if needle in jd_l and label not in seen:
            seen.add(label)
            found.append(label)
    if (
        "funnel conversion" not in seen
        and "funnel" in jd_l
        and "conversion" in jd_l
    ):
        seen.add("funnel conversion")
        found.append("funnel conversion")
    if any(m in jd_l for m in ("lender", "borrower", "funded volume", "funnel conversion")):
        ordered = [o for o in _FINTECH_OUTCOME_ORDER if o in found]
        if ordered:
            found = ordered
    return found[:max_n]


def extract_role_targets(jd_text: str, max_n: int = 2) -> List[str]:
    """Role-specific JD targets for cover close — not candidate vocabulary (CR-047)."""
    jd_l = jd_text.lower()
    found: List[str] = []
    seen: set = set()
    for needle, label in _TARGET_PATTERNS:
        if needle in jd_l and label not in seen:
            seen.add(label)
            found.append(label)
        if len(found) >= max_n:
            break
    if (
        len(found) < max_n
        and "borrower" in jd_l
        and "offer experience" in jd_l
        and "the borrower offer experience" not in seen
    ):
        found.append("the borrower offer experience")
    return found[:max_n]


def extract_role_challenge(jd_text: str) -> str:
    """Short forward-looking business problem from the JD (for cover close)."""
    jd_l = jd_text.lower()
    if "personal safety" in jd_l or (
        "connected device" in jd_l and "integrat" in jd_l
    ):
        return "drive device vendor integrations and platform interoperability"
    if "lender" in jd_l and ("integration" in jd_l or "funnel" in jd_l):
        return "improve lender integrations and consumer funnel conversion"
    if "funnel" in jd_l and ("experiment" in jd_l or "conversion" in jd_l):
        return "run funnel experiments that improve conversion and funded volume"
    if "marketplace" in jd_l and ("borrower" in jd_l or "lender" in jd_l):
        return "match borrower demand to lender supply with a better offer experience"
    if "product domain" in jd_l and any(
        m in jd_l for m in ("financ", "dealer", "consumer", "point-of-sale", "point of sale")
    ):
        return (
            "improve roadmap clarity, cross-functional delivery, and "
            "customer-facing financing experiences"
        )
    if "adopted" in jd_l and "demo" in jd_l:
        return "ship analytics products that teams adopt, not just demo"
    if "analytics product" in jd_l or "analytics products" in jd_l:
        if "underwriting" in jd_l or "sales" in jd_l:
            return "deliver analytics products sales and underwriting teams actually use"
        return "deliver analytics products with measurable adoption"
    for block in _extract_role_action_paragraphs(jd_text):
        bl = block.lower()
        if "roadmap" in bl and "kpi" in bl:
            return "own roadmap delivery and KPIs without losing stakeholder trust"
        if "platform" in bl and "scale" in bl:
            return "scale platform capabilities without customer friction"
    if "ranking" in jd_l or "intelligence platform" in jd_l:
        return "expand rankings and intelligence platform capabilities"
    if "monetiz" in jd_l:
        return "unlock monetization across product lines"
    return ""


def _extract_responsibility_lines(jd_text: str) -> List[str]:
    lines: List[str] = []
    in_resp = False
    for raw in jd_text.splitlines():
        line = raw.strip()
        low = line.lower()
        if low.startswith("responsibilit"):
            in_resp = True
            continue
        if in_resp and low.startswith(
            ("the ideal", "ideal candidate", "qualification", "requirements", "about ")
        ):
            break
        if not in_resp:
            continue
        if not line:
            continue
        cleaned = re.sub(r"^[-•*]\s*", "", line).strip()
        low_clean = cleaned.lower()
        if any(x in low_clean for x in ("salary", "$", "compensation range", "per year")):
            continue
        if cleaned:
            lines.append(cleaned[:160])
    return lines


def _normalize_need_clause(line: str) -> str:
    c = line.strip()
    if c and c[0].islower():
        c = c[0].upper() + c[1:]
    return c


def _score_need_line(line: str, jd_text: str) -> int:
    jd_l = jd_text.lower()
    ll = line.lower()
    score = 0
    if is_tenure_requirement(line):
        score -= 25
    for kw in (
        "platform",
        "ranking",
        "monetiz",
        "revenue",
        "data",
        "roadmap",
        "scalable",
        "engineering",
        "kpi",
        "workflow",
        "franchise",
        "intelligence",
    ):
        if kw in jd_l and kw in ll:
            score += 4
    if "intelligence platform" in ll or "list franchise" in ll:
        score += 14
    if ll.startswith(("own ", "identify ", "ensure ", "establish ", "improve ")):
        score += 10
    if ll.startswith("collaborate "):
        score += 2
    score += min(len(line) // 20, 5)
    return score


def extract_ranked_needs(jd_text: str, profile: JdProfile | None = None, limit: int = 3) -> List[str]:
    prof = profile or build_jd_profile_deterministic(jd_text)
    candidates: List[Tuple[int, str]] = []

    for line in _extract_responsibility_lines(jd_text):
        if _clause_valid(line, jd_text):
            candidates.append((_score_need_line(line, jd_text), line))

    for para in _extract_role_action_paragraphs(jd_text):
        for sent in re.split(r"(?<=[.!?])\s+", para):
            clause = sent.strip()[:160]
            if _clause_valid(clause, jd_text):
                candidates.append((_score_need_line(clause, jd_text) + 12, clause))

    _SKIP_REQ_MARKERS = (
        "job posted",
        "summary generated",
        "fitness",
        "healthtech",
        "locations",
        "in-office",
    )
    for req in prof.requirements:
        if any(m in req.lower() for m in _SKIP_REQ_MARKERS):
            continue
        if _clause_valid(req, jd_text):
            candidates.append((_score_need_line(req, jd_text), req))

    if not candidates:
        for kw, phrase in (
            ("ranking", "expanding rankings and list franchise capabilities on a scalable platform"),
            ("monetiz", "unlocking monetization across subscription, enterprise, and data products"),
            ("platform", "scaling platform capabilities with structured data and cross-functional delivery"),
        ):
            if kw in jd_text.lower():
                candidates.append((10, phrase))

    seen: set = set()
    ranked: List[str] = []
    for _score, clause in sorted(candidates, key=lambda x: (-x[0], x[1])):
        key = clause.lower()[:80]
        if key in seen:
            continue
        seen.add(key)
        ranked.append(_normalize_need_clause(clause))
        if len(ranked) >= limit:
            break
    return ranked


def extract_role_title(jd_text: str) -> str:
    patterns = (
        r"seeking a\s+([^.\n]{8,80}?)(?:\s+to\s+|\s+who\s+|\s+that\s+|\.)",
        r"looking for a\s+([^.\n]{8,80}?)(?:\s+to\s+|\s+who\s+|\.)",
    )
    for pat in patterns:
        m = re.search(pat, jd_text, re.I)
        if m:
            title = re.sub(r"\s+", " ", m.group(1).strip())
            if "product manager" in title.lower():
                return "Product Manager"
            if 8 <= len(title) <= 48:
                return title
    if re.search(r"\bproduct manager\b", jd_text, re.I):
        return "Product Manager"
    return "Product Manager"


def need_to_goal_phrase(need: str) -> str:
    """Turn a responsibility line into a goal phrase for closes."""
    n = need.strip().rstrip(".")
    prefixes = (
        "Own ",
        "Own and prioritize ",
        "Identify and deliver ",
        "Ensure ",
        "Partner with ",
        "Collaborate closely with ",
        "Establish and track ",
        "Improve ",
        "Monitor ",
        "Evaluate ",
    )
    n_low = n.lower()
    for prefix in prefixes:
        if n_low.startswith(prefix.lower()):
            n = n[len(prefix) :]
            break
    n = n.strip().rstrip(",")
    if len(n) > 110:
        chunk = n[:110]
        if "," in chunk:
            n = chunk[: chunk.rfind(",")]
        else:
            n = chunk.rsplit(" ", 1)[0]
    if n[:4].upper() == "KPIS" or n[:3].upper() == "KPI":
        return n if n[0].isupper() else n[0].upper() + n[1:]
    return n[0].lower() + n[1:] if n and n[0].isupper() else n


def extract_jd_goal(jd_text: str, ranked_needs: List[str]) -> str:
    jd_l = jd_text.lower()
    if ranked_needs:
        for need in ranked_needs:
            if not is_tenure_requirement(need):
                return need_to_goal_phrase(need)
        return need_to_goal_phrase(ranked_needs[0])
    if "ranking" in jd_l or "intelligence platform" in jd_l:
        return "scaling rankings and intelligence platform capabilities"
    if "monetiz" in jd_l:
        return "unlocking monetization through scalable platform delivery"
    return "delivering measurable platform outcomes"
