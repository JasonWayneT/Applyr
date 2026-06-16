"""
Human-mirror resume conversion critique (FR-220–FR-222).

Detects the same failure modes external reviewers flag: incomplete summary
sentences, PDF experience-header layout inversion, and Sterkly narrative gaps.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

_INCOMPLETE_SUMMARY_PATTERNS: List[re.Pattern] = [
    re.compile(
        r"\b(?:enough|such)\s+that\s+[^.]{5,120}\b(?:teams|platforms?|groups?|stakeholders?)\s*\.\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:that|which)\s+[\w\s\-]{8,100}\b(?:teams|platforms?|groups?)\s*\.\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r",\s*(?:producing|building|delivering|creating|enabling)\s+[^.]{12,140}\s*\.\s*$",
        re.IGNORECASE,
    ),
    # Trailing participial phrase without an outcome verb (e.g. "…, managing resource allocations.")
    re.compile(
        r",\s*(?:managing|maintaining|overseeing|coordinating|supporting|handling|tracking)\s+"
        r"(?:\w+\s+){1,6}\w+\s*\.\s*$",
        re.IGNORECASE,
    ),
    # Sentence ends on a bare noun after "enough that" — adoption payoff was truncated
    re.compile(
        r"\benough\s+that\s+[^.]{5,100}\b(?:teams?|groups?|platforms?|partners?|customers?)\s*\.\s*$",
        re.IGNORECASE,
    ),
]

_COMPLETE_PROOF_VERB_RE = re.compile(
    r"\b(?:sought|adopted|delivered|reduced|eliminated|achieved|enabled|scaled|"
    r"resolved|generated|sustained|restored|increased|improved|launched|"
    r"secured|automated|migrated|rebuilt|implemented|closed|drove)\b",
    re.IGNORECASE,
)

_MACOS_JARGON_RE = re.compile(
    r"\b(?:macos|certificates?|vendor sources?|browser extension|competing products?)\b",
    re.IGNORECASE,
)

_STERKLY_CONTEXT_RE = re.compile(
    r"\b(?:developer|developers|engineering team|consumer|professional services|"
    r"partnered|cross-functional|workflow solutions?|dedicated team)\b",
    re.IGNORECASE,
)

_KNOWN_EMPLOYERS = ("Cision", "Sterkly", "Zero to Sixty")

# Summary template = sentences 1–2 (role opener + partnership framing). Sentence 3 = sole proof.
SUMMARY_TEMPLATE_SENTENCES = 2
SUMMARY_MAX_PROOF_SENTENCES = 1

_PARTICIPLE_FRAGMENT_RE = re.compile(
    r"^(?:Coordinating|Producing|Preserving|Building|Delivering|Enabling|Resolving|"
    r"Maintaining|Owning|Replacing|Implementing|Partnering|Managing|"
    r"Integrating|Automating|Scaling|Streamlining|Architecting|Synthesizing)\b",
    re.IGNORECASE,
)

_OUTCOME_OPENER_RE = re.compile(
    r"^(?:Rebuilt|Resolved|Reduced|Eliminated|Launched|Led|Drove|Built|"
    r"Delivered|Implemented|Stabilized|Sustained|Restored|Increased|"
    r"Maintained|Generated|Automated|Deployed|Migrated|Secured)\b",
    re.IGNORECASE,
)


def is_participle_proof_fragment(text: str) -> bool:
    """True when a summary sentence reads like a bullet clause pasted without a subject."""
    return bool(_PARTICIPLE_FRAGMENT_RE.match((text or "").strip()))


def is_incomplete_summary_sentence(text: str) -> bool:
    """True when a summary sentence ends mid-thought (credibility hit)."""
    t = (text or "").strip()
    if not t:
        return False
    if not t.endswith("."):
        return True
    if re.search(r"\bsought to adopt it\.?\s*$", t, re.IGNORECASE):
        return False
    if _COMPLETE_PROOF_VERB_RE.search(t):
        tail = t[-100:]
        if re.search(r"\b(?:sought|adopted|delivered|resolved|reduced|eliminated)\b", tail, re.I):
            return False
    for pat in _INCOMPLETE_SUMMARY_PATTERNS:
        if pat.search(t):
            return True
    # Trailing relative clause without completion verb
    if re.search(r"\b(?:that|which)\s+[^.]{10,120}\.\s*$", t, re.IGNORECASE):
        tail = t.rsplit(".", 1)[0]
        if not _COMPLETE_PROOF_VERB_RE.search(tail[-80:]):
            if re.search(r"\b(?:teams|platforms?|groups?|stakeholders?)\s*\.\s*$", t, re.IGNORECASE):
                return True
    return False


def _summary_text(resume_md: str) -> str:
    m = re.search(
        r"##\s*PROFESSIONAL\s+SUMMARY\s*\n+(.+?)"
        r"(?=\n##\s+[A-Z]|\nPROFESSIONAL\s+EXPERIENCE|\Z)",
        resume_md,
        re.DOTALL | re.IGNORECASE,
    )
    return m.group(1).strip() if m else ""


def _summary_sentences(summary: str) -> List[str]:
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+", summary.strip()) if p.strip()]


def _experience_blocks(resume_md: str) -> List[Dict[str, str]]:
    """Parse ### Title | Company | Dates blocks under PROFESSIONAL EXPERIENCE."""
    m = re.search(
        r"##\s*PROFESSIONAL\s+EXPERIENCE\s*\n+(.*?)(?=\n##\s+[A-Z]|\Z)",
        resume_md,
        re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return []
    blocks: List[Dict[str, str]] = []
    lines = m.group(1).splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        hdr = re.match(
            r"^###\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*$",
            line,
            re.IGNORECASE,
        )
        if not hdr:
            i += 1
            continue
        location = ""
        bullets: List[str] = []
        i += 1
        if i < len(lines) and lines[i].strip() and not lines[i].strip().startswith("*"):
            location = lines[i].strip()
            i += 1
        while i < len(lines):
            bl = lines[i].strip()
            if bl.startswith("###") or bl.startswith("##"):
                break
            if bl.startswith("*"):
                bullets.append(bl.lstrip("* ").strip())
            i += 1
        blocks.append(
            {
                "title": hdr.group(1).strip(),
                "company": hdr.group(2).strip(),
                "dates": hdr.group(3).strip(),
                "location": location,
                "bullets": bullets,
            }
        )
    return blocks


def _extract_pdf_text(pdf_path: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(pdf_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def check_pdf_experience_header_order(pdf_path: str, resume_md: str) -> List[str]:
    """CW-009: company/title must precede location and bullets in PDF text order."""
    warnings: List[str] = []
    try:
        pdf_text = _extract_pdf_text(pdf_path)
    except Exception as exc:
        return [f"[CW-009] PDF layout check failed (cannot read PDF): {exc}"]

    if "PROFESSIONAL EXPERIENCE" not in pdf_text.upper().replace("  ", " "):
        return [f"[CW-009] PDF missing PROFESSIONAL EXPERIENCE section text."]

    exp_start = re.search(r"PROFESSIONAL\s+EXPERIENCE", pdf_text, re.IGNORECASE)
    edu_start = re.search(r"\bEDUCATION\b", pdf_text, re.IGNORECASE)
    exp_text = pdf_text[exp_start.end() : edu_start.start() if edu_start else len(pdf_text)]

    blocks = _experience_blocks(resume_md)
    search_from = 0
    for block in blocks:
        company = block["company"]
        location = block["location"]
        title = block["title"]
        bullets = block["bullets"]
        if not company:
            continue

        company_pos = exp_text.find(company, search_from)
        title_pos = exp_text.find(title, search_from) if title else -1

        if company_pos < 0 and title_pos < 0:
            warnings.append(
                f"[CW-009] PDF layout: neither '{company}' nor '{title}' found in experience "
                "section — headers likely missing or reordered."
            )
            continue

        header_pos = company_pos if company_pos >= 0 else title_pos
        search_from = header_pos + len(company)

        if location:
            loc_pos = exp_text.find(location, header_pos)
            if loc_pos < 0:
                loc_pos = exp_text.find(location, search_from)
            if loc_pos >= 0 and loc_pos < header_pos:
                warnings.append(
                    f"[CW-009] PDF layout: location '{location}' appears before "
                    f"employer header '{company}' — recruiter sees location as section title."
                )

        bullet_anchor = -1
        if bullets:
            snippet = bullets[0][:48]
            bullet_anchor = exp_text.find(snippet, header_pos)
            if bullet_anchor < 0:
                for word in bullets[0].split()[:8]:
                    if len(word) > 5:
                        bullet_anchor = exp_text.find(word, header_pos)
                        if bullet_anchor >= 0:
                            break
            if bullet_anchor >= 0 and bullet_anchor < header_pos:
                warnings.append(
                    f"[CW-009] PDF layout: bullets for {company} appear before company/title header."
                )

    tail = exp_text[-400:]
    for company in _KNOWN_EMPLOYERS:
        if company in tail and company not in exp_text[: max(1, len(exp_text) - 400)]:
            warnings.append(
                f"[CW-009] PDF layout: '{company}' header rendered at bottom of experience "
                "section (print float/layout bug)."
            )
            break

    return warnings


def check_summary_completeness(resume_md: str) -> List[str]:
    """CW-011: summary must not end on incomplete or mid-thought sentences."""
    summary = _summary_text(resume_md)
    if not summary:
        return ["[CW-011] Professional summary section is missing."]
    issues: List[str] = []
    for sent in _summary_sentences(summary):
        if is_incomplete_summary_sentence(sent):
            issues.append(
                f"[CW-011] Incomplete summary sentence (credibility hit): \"{sent[:100]}...\""
                if len(sent) > 100
                else f"[CW-011] Incomplete summary sentence (credibility hit): \"{sent}\""
            )
    return issues


def check_summary_theme_grounding(
    resume_md: str, bullets_by_company: Optional[Dict] = None
) -> List[str]:
    """CW-014: summary 'focused on' phrase must be experience-backed, not JD-only mirroring."""
    summary = _summary_text(resume_md)
    if not summary:
        return []
    m = re.search(
        r"most recently focused on ([^.]+)\.",
        summary,
        re.IGNORECASE,
    )
    if not m:
        return []

    from experience_theme_guard import is_theme_experience_backed
    from cover_prose import _short_theme_label
    from jd_tailoring import THEME_KEYWORDS

    focus = m.group(1).strip()
    corpus = ""
    if bullets_by_company:
        corpus = " ".join(
            b for bl in bullets_by_company.values() for b in bl
        )
    if not corpus.strip():
        return []

    issues: List[str] = []
    for _kw, full_phrase in THEME_KEYWORDS:
        short = _short_theme_label(full_phrase)
        if not short or len(short) < 6:
            continue
        if short.lower() not in focus.lower():
            continue
        if not is_theme_experience_backed(full_phrase, corpus):
            issues.append(
                f"[CW-014] Summary claims focus on '{short}' but selected bullets "
                "do not support that theme — use transferable framing in cover letter instead."
            )
    return issues


def check_summary_proof_payoff(resume_md: str, bullets_by_company: Optional[Dict] = None) -> List[str]:
    """CW-015: attribution proof in summary should include adoption payoff when bullet has it."""
    if not bullets_by_company:
        return []
    summary = _summary_text(resume_md)
    if not summary or "revenue outcomes" not in summary.lower():
        return []
    if "sought to adopt" in summary.lower():
        return []
    corpus = " ".join(b for bl in bullets_by_company.values() for b in bl)
    if not re.search(
        r"producing a version reliable enough that[^.]+sought to adopt it",
        corpus,
        re.IGNORECASE,
    ):
        return []
    return [
        "[CW-015] Summary attribution proof stops before the adoption payoff "
        "(add '…sought to adopt it' when grounded in the Cision bullet)."
    ]


def check_summary_prose_quality(resume_md: str) -> List[str]:
    """CW-013: one grounded proof sentence; no participle fragments from bullets."""
    summary = _summary_text(resume_md)
    if not summary:
        return []
    sents = _summary_sentences(summary)
    issues: List[str] = []
    proof_sents = sents[SUMMARY_TEMPLATE_SENTENCES:]
    if len(proof_sents) > SUMMARY_MAX_PROOF_SENTENCES:
        issues.append(
            "[CW-013] Summary stacks multiple proof sentences — reads like pasted bullet "
            f"fragments ({len(proof_sents)} proof lines; max {SUMMARY_MAX_PROOF_SENTENCES})."
        )
    for sent in proof_sents:
        if is_participle_proof_fragment(sent):
            issues.append(
                f"[CW-013] Summary proof reads like a bullet fragment (participle opener): "
                f"\"{sent[:95]}...\""
                if len(sent) > 95
                else f"[CW-013] Summary proof reads like a bullet fragment (participle opener): \"{sent}\""
            )
    return issues


def score_summary_proof_candidate(
    proof: str,
    jd_text: str = "",
    body_bullets: Optional[List[str]] = None,
) -> int:
    """Rank proof clauses: outcome opener + metrics beat participle fragments and body dup."""
    p = (proof or "").strip()
    if not p or is_incomplete_summary_sentence(p):
        return -100
    if body_bullets and summary_proof_overlaps_body(p, body_bullets):
        return -50
    score = 0
    if re.search(r"[\$%]|\b\d{1,3}%|\b\d{4,}\b", p):
        score += 5
    elif re.search(r"\b\d", p):
        score += 2
    if _OUTCOME_OPENER_RE.match(p):
        score += 4
    if _COMPLETE_PROOF_VERB_RE.search(p):
        score += 2
    if is_participle_proof_fragment(p):
        score -= 6
    if jd_text:
        jd_words = set(re.findall(r"[a-z]{4,}", jd_text.lower()))
        score += min(4, sum(1 for w in jd_words if w in p.lower()))
    return score


def summary_proof_overlaps_body(proof: str, body_bullets: List[str], min_chars: int = 24) -> bool:
    """True when proof text is a contiguous substring of any experience bullet (FR-247)."""
    pn = (proof or "").strip().lower().rstrip(".")
    if len(pn) < min_chars:
        return False
    for bullet in body_bullets:
        bl = (bullet or "").strip().lower()
        if pn in bl:
            return True
    return False


def check_summary_bullet_overlap(resume_md: str) -> List[str]:
    """CW-016: summary proof must not verbatim-copy an experience bullet."""
    summary = _summary_text(resume_md)
    if not summary:
        return []
    sents = _summary_sentences(summary)
    proof_sents = sents[SUMMARY_TEMPLATE_SENTENCES:]
    if not proof_sents:
        return []
    body_bullets: List[str] = []
    for block in _experience_blocks(resume_md):
        body_bullets.extend(block.get("bullets") or [])
    issues: List[str] = []
    for sent in proof_sents[:SUMMARY_MAX_PROOF_SENTENCES]:
        if summary_proof_overlaps_body(sent, body_bullets):
            issues.append(
                f"[CW-016] Summary proof duplicates experience bullet text: "
                f"\"{sent[:90]}...\""
                if len(sent) > 90
                else f"[CW-016] Summary proof duplicates experience bullet text: \"{sent}\""
            )
    return issues


def check_sterkly_narrative_coherence(resume_md: str) -> List[str]:
    """CW-012: Mid-career employer must not read as unrelated domain jargon with no PM context."""
    from candidate_context import company_matches_employer_slug, employer_display_name, employer_tiers

    _, mid_slug, _ = employer_tiers()
    mid_label = employer_display_name(mid_slug)
    warnings: List[str] = []
    for block in _experience_blocks(resume_md):
        if not company_matches_employer_slug(block["company"], mid_slug):
            continue
        bullets = block["bullets"]
        if not bullets:
            return warnings
        jargon = sum(1 for b in bullets if _MACOS_JARGON_RE.search(b))
        has_context = any(_STERKLY_CONTEXT_RE.search(b) for b in bullets)
        if jargon >= 2 and not has_context:
            warnings.append(
                f"[CW-012] {mid_label} section is domain-jargon-heavy with no role-context "
                "bullet (engineering partnership, consumer software, or services framing)."
            )
        if len(bullets) >= 3 and jargon == len(bullets):
            warnings.append(
                f"[CW-012] All {mid_label} bullets are domain-jargon only — hiring manager may not "
                "recognize this as the same PM career."
            )
    return warnings


def check_cision_strengths(resume_md: str) -> List[str]:
    """Positive signals mirroring external reviewer praise."""
    from candidate_context import company_matches_employer_slug, employer_display_name, primary_employer_slug

    senior_slug = primary_employer_slug()
    senior_label = employer_display_name(senior_slug)
    strengths: List[str] = []
    for block in _experience_blocks(resume_md):
        if not company_matches_employer_slug(block["company"], senior_slug):
            continue
        joined = " ".join(block["bullets"]).lower()
        if re.search(r"\$|\b\d{1,3}%|\b\d{4,}\b", joined):
            strengths.append(f"{senior_label} section includes quantified scope or outcome metrics.")
        if "integration" in joined or "ingestion" in joined or "pipeline" in joined:
            strengths.append(f"{senior_label} data or platform integration bullet present.")
        if re.search(r"\bsecurity\b|\breliability\b|\bstability\b", joined) and re.search(r"\d", joined):
            strengths.append(f"{senior_label} risk or stability bullet includes concrete numbers.")
    return strengths


def evaluate_resume_conversion(
    resume_md: str,
    pdf_path: Optional[str] = None,
    bullets_by_company: Optional[Dict] = None,
    jd_text: str = "",
) -> Dict:
    """
    Run human-mirror conversion critique. Returns pass flag, issues, and strengths.
    bullets_by_company is accepted for API compatibility with check_conversion_signals.
    """
    issues: List[str] = []
    issues.extend(check_summary_completeness(resume_md))
    issues.extend(check_summary_prose_quality(resume_md))
    issues.extend(check_summary_bullet_overlap(resume_md))
    issues.extend(check_summary_theme_grounding(resume_md, bullets_by_company))
    issues.extend(check_summary_proof_payoff(resume_md, bullets_by_company))
    if pdf_path:
        issues.extend(check_pdf_experience_header_order(pdf_path, resume_md))
    issues.extend(check_sterkly_narrative_coherence(resume_md))

    from candidate_context import company_matches_employer_slug, employer_display_name, employer_tiers

    _, _, junior_slug = employer_tiers()
    junior_label = employer_display_name(junior_slug)
    strengths = check_cision_strengths(resume_md)
    for block in _experience_blocks(resume_md):
        if not company_matches_employer_slug(block["company"], junior_slug):
            continue
        joined = " ".join(block["bullets"])
        if re.search(r"\b\d{1,3}\s*(?:to|–|-)\s*\d{2,}\+?\b|\b\d{2,}\+\b", joined):
            strengths.append(f"{junior_label} section includes a scaling or volume metric.")

    blocking_codes = ("CW-009", "CW-011", "CW-012", "CW-013", "CW-014", "CW-015", "CW-016")
    hard_fail = [i for i in issues if any(i.startswith(f"[{c}]") for c in blocking_codes)]

    return {
        "pass": len(hard_fail) == 0,
        "issue_count": len(issues),
        "issues": issues,
        "strengths": strengths,
        "human_readable": _format_critique(issues, strengths),
    }


def _format_critique(issues: List[str], strengths: List[str]) -> str:
    lines: List[str] = []
    if strengths:
        lines.append("Strengths:")
        lines.extend(f"  + {s}" for s in strengths)
    if issues:
        lines.append("Issues:")
        lines.extend(f"  - {i}" for i in issues)
    if not issues:
        lines.append("No conversion critique issues detected.")
    return "\n".join(lines)
