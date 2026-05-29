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

    for req in prof.requirements:
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
        return need_to_goal_phrase(ranked_needs[0])
    if "ranking" in jd_l or "intelligence platform" in jd_l:
        return "scaling rankings and intelligence platform capabilities"
    if "monetiz" in jd_l:
        return "unlocking monetization through scalable platform delivery"
    return "delivering measurable platform outcomes"
