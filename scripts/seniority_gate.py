"""
Deterministic seniority gating (CR-019 / FR-109, CR-055).

- Title blocklist: role-designation terms vs focus-area modifiers (CR-055 Epic 2).
- Years gate: requirements-anchored parsing; ignores incidental numbers (CR-055 Epic 1).
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

# Role-designation terms block anywhere in the title line.
_DEFAULT_BLOCKED_ROLE_TITLES = [
    "Staff", "VP", "Head", "Principal", "Lead", "Director", "Group Product Manager", "GPM",
    "Founding", "First", "Manager of", "Engineering Manager", "People Manager",
    "Assistant", "Coordinator", "Intern", "Associate", "Entry", "Junior",
    "Analyst", "Software Engineer",
]

# Focus-area words block only when they appear as the primary role, not "PM, Growth".
_DEFAULT_BLOCKED_FOCUS_AREA_WORDS = [
    "Growth", "Developer", "Designer", "Marketer",
]

_PM_ROLE_RE = re.compile(
    r"\b(?:senior\s+|staff\s+)?(?:technical\s+|platform\s+)?product\s+(?:manager|owner)\b",
    re.I,
)

_REQ_SECTION_HEADER = re.compile(
    r"^(?:#+\s*)?"
    r"(?:requirements?|qualifications?|what you(?:'|')ll need|minimum qualifications?|"
    r"what we(?:'|')re looking for|you have|you bring|experience required|about you|"
    r"who you are|must have|basic qualifications?)\b",
    re.I,
)

_NON_EXPERIENCE_CONTEXT = re.compile(
    r"\b(?:history|founded|since|anniversary|celebrating|legacy|years ago|"
    r"established|mission|nonprofit|research|science|institute|laboratory)\b",
    re.I,
)

MAX_PLAUSIBLE_YEARS = 25

# Always valid — explicit requirement language in match.
_ANCHORED_YEARS_PATTERNS = [
    re.compile(
        r"(?:minimum|min\.?|at least|requires?|requirement[s]?:?)\s*(\d+)\s*\+?\s*(?:years?|yrs?\.?)",
        re.I,
    ),
    re.compile(r"(\d+)\s*\+\s*years?", re.I),
    re.compile(r"(\d+)\s+or\s+more\s+years?", re.I),
]

# Requirements-section or experience-context only.
_LOOSE_YEARS_PATTERNS = [
    re.compile(r"(\d+)\s*[-–]\s*(\d+)\s*years?", re.I),
    re.compile(r"(\d+)\s+to\s+(\d+)\s+years?", re.I),
    re.compile(r"(\d+)\s+years?\s+(?:of\s+)?(?:product\s+)?(?:management\s+)?experience", re.I),
    re.compile(r"(\d+)\s+years?\s+of\s+(?:professional\s+)?(?:product\s+)?experience", re.I),
]


def _strip_html(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


_TITLE_BOILERPLATE_PREFIXES = (
    "reports to",
    "location",
    "first priority",
    "second priority",
    "about ",
    "responsibilities",
    "url:",
    "http",
)

# JD chrome that extract_job_title_line used to treat as the role (found live
# 2026-08-11: LeafLink "The Role", Camunda "Register Here!" finalized into jobs).
_TITLE_JUNK_EXACT = frozenset(
    {
        "the role",
        "the position",
        "the opportunity",
        "about the role",
        "about your role",
        "job summary",
        "job description",
        "job overview",
        "overview",
        "responsibilities",
        "requirements",
        "qualifications",
        "who we are",
        "about us",
        "register here",
        "register here!",
        "apply here",
        "apply here!",
        "apply now",
        "apply now!",
        "click here",
        "click here!",
        "please apply here",
        "join our team",
        "join us",
    }
)

_TITLE_JUNK_RE = re.compile(
    r"^(?:the\s+)?(?:role|position|opportunity)\s*!?\s*$|"
    r"^about\s+(?:the\s+|your\s+)?(?:role|position|company|us|you)\b|"
    r"^(?:register|apply|click|sign\s*up)\s+here\b|"
    r"^(?:please\s+)?apply\b|"
    r"^job\s+(?:summary|description|overview)\b|"
    r"^what\s+you(?:'|')?ll?\s+(?:do|be\s+doing|need|bring)\b|"
    r"^who\s+(?:we\s+are|you\s+are)\b|"
    r"^join\s+(?:our\s+)?(?:team|us)\b",
    re.I,
)

# Recruiting slogans that name the role inside a sentence (Compugroup 2026-08-11:
# "Create the future of e-health together with us by becoming a Product Manager").
_TITLE_SLOGAN_RE = re.compile(
    r"\b(?:"
    r"by\s+becoming|"
    r"join\s+(?:our\s+)?(?:team|us)\s+as|"
    r"we(?:'|')?re\s+(?:looking|seeking|hiring)|"
    r"(?:looking|seeking|hiring)\s+for\s+(?:a|an|our)|"
    r"create\s+the\s+future|"
    r"together\s+with\s+us|"
    r"opportunity\s+to\s+(?:join|become)|"
    r"come\s+join|"
    r"excited\s+to\s+(?:announce|share)"
    r")\b",
    re.I,
)

# Qualification / bullet lines that mention "lead" or "manager" but aren't titles
# (Pinterest: "Proven ability to lead teams and work in a highly collaborative environment").
_TITLE_QUAL_LINE_RE = re.compile(
    r"^(?:proven|strong|excellent|demonstrated|ability\s+to|"
    r"experience\s+(?:with|in|and)|minimum\s+of|bachelor|master|"
    r"years?\s+of\s+experience|\d+\+?\s+years?)\b",
    re.I,
)

# Real role titles are short; bare "lead" alone is too broad (matches "ability to lead").
_TITLE_ROLE_WORD_RE = re.compile(
    r"\b(?:manager|owner|director|pm)\b|"
    r"\b(?:product|technical|platform|team|group)\s+lead\b|"
    r"\blead\s+(?:product|technical|platform)\b",
    re.I,
)

_MAX_TITLE_WORDS = 10


def is_implausible_job_title(title: str) -> bool:
    """True when `title` is JD chrome (section header / CTA / slogan), not a real role name.

    Used by Stage 0 extraction cleanup and Stage 3 finalize so scrape junk cannot
    land in `jobs.title` again.
    """
    t = (title or "").strip()
    if not t or len(t) > 120:
        return True
    lower = t.lower().strip()
    if lower in _TITLE_JUNK_EXACT:
        return True
    if _TITLE_JUNK_RE.search(t):
        return True
    if _TITLE_SLOGAN_RE.search(t):
        return True
    if _TITLE_QUAL_LINE_RE.search(t):
        return True
    if len(t.split()) > _MAX_TITLE_WORDS:
        return True
    # Imperative CTA chrome almost always ends with !
    if t.rstrip().endswith("!") and not _TITLE_ROLE_WORD_RE.search(t):
        return True
    return False


def _embedded_pm_title(text: str) -> str:
    """Pull the first Product Manager/Owner span out of prose."""
    m = _PM_ROLE_RE.search(text or "")
    if not m:
        return ""
    return re.sub(r"\s+", " ", m.group(0)).strip()


def _title_from_url(jd_text: str) -> str:
    """Best-effort role from a Workday/Greenhouse-style URL slug."""
    url = ""
    for line in (jd_text or "").splitlines()[:5]:
        stripped = line.strip()
        if stripped.lower().startswith("url:"):
            url = stripped.split(":", 1)[1].strip()
            break
        if stripped.startswith("http"):
            url = stripped
            break
    if not url:
        return ""

    # Workday: .../Product-Manager_JR109379-1
    m = re.search(
        r"/((?:Senior-|Staff-|Sr-)?(?:Technical-)?Product-(?:Manager|Owner)"
        r"(?:-[A-Za-z0-9]+)?)(?:_|/|\?|$)",
        url,
        re.I,
    )
    if m:
        return m.group(1).replace("-", " ").strip()

    # Path slug: .../product-manager-ii-content-compliance/
    parts = [p for p in url.split("?", 1)[0].rstrip("/").split("/") if p]
    for part in reversed(parts):
        if part.isdigit():
            continue
        if not re.search(r"product[-_](?:manager|owner)", part, re.I):
            continue
        words = part.replace("_", "-").split("-")
        titled = " ".join(
            w.upper() if w.lower() in {"ii", "iii", "iv"} else w.capitalize()
            for w in words
            if w
        )
        return titled
    return ""


def extract_job_title_line(jd_text: str) -> str:
    """Best-effort job title from JD text (explicit header, short title line, or embedded PM).

    Prefers real role lines over section headers / apply CTAs / recruiting slogans.
    Falls back to the first Product Manager/Owner mention, then a URL slug.
    """
    if not jd_text:
        return ""

    short_candidates: list[str] = []
    for line in jd_text.splitlines()[:40]:
        stripped = _strip_html(line.strip())
        if not stripped:
            continue
        lower = stripped.lower()
        if lower.startswith("title:"):
            value = stripped.split(":", 1)[1].strip()
            if value and not is_implausible_job_title(value):
                return value
            continue
        if lower.startswith("position:"):
            value = stripped.split(":", 1)[1].strip()
            if value and not is_implausible_job_title(value):
                return value
            continue
        if len(stripped) >= 120:
            embedded = _embedded_pm_title(stripped)
            if embedded and not is_implausible_job_title(embedded):
                return embedded
            continue
        if any(lower.startswith(prefix) for prefix in _TITLE_BOILERPLATE_PREFIXES):
            continue
        if is_implausible_job_title(stripped):
            # Slogan / qual line may still embed the real title ("...by becoming a Product Manager")
            embedded = _embedded_pm_title(stripped)
            if embedded and not is_implausible_job_title(embedded):
                return embedded
            continue
        # Prefer a short non-sentence line that already looks like a role title
        if not stripped.endswith(".") and _TITLE_ROLE_WORD_RE.search(stripped):
            if len(stripped.split()) > 6:
                embedded = _embedded_pm_title(stripped)
                if embedded and not is_implausible_job_title(embedded):
                    return embedded
            return stripped
        if not stripped.endswith("."):
            short_candidates.append(stripped)

    embedded = _embedded_pm_title(jd_text)
    if embedded and not is_implausible_job_title(embedded):
        return embedded

    from_url = _title_from_url(jd_text)
    if from_url and not is_implausible_job_title(from_url):
        return from_url

    for candidate in short_candidates:
        if not is_implausible_job_title(candidate):
            return candidate
    return ""


def _lead_is_role_designation(title: str) -> bool:
    """Block Lead only as a role title, not verb uses like 'leaders lead with'."""
    patterns = (
        r"\blead\s+(?:product|technical|platform|senior|group|principal|pm)\b",
        r"\b(?:product|technical|platform|group|engineering)\s+lead\b",
        r"\bteam\s+lead\b",
        r"^lead\b",
    )
    return any(re.search(p, title, re.I) for p in patterns)


_HYPHEN_FIRST_RE = re.compile(r"[a-z]+-first\b", re.I)


def _first_is_role_designation(title: str) -> bool:
    """Block First only as a founding/first-hire signal ('First Product Manager',
    'PM, First'), not a hyphenated methodology modifier ('AI-First', 'Mobile-First',
    'Customer-First', 'Remote-First') and not a domain phrase ('First Value',
    'Onboarding & First Value'). False positive found 2026-08-13: "Senior
    Program Manager – AI-First". False positive found 2026-08-14: Dexcom
    "Product Manager, Patient Onboarding & First Value"."""
    stripped = _HYPHEN_FIRST_RE.sub("", title)
    patterns = (
        r"\bfirst\s+(?:product|technical|platform|senior|group|principal|pm|engineer|hire)\b",
        r"\b(?:product|technical|platform)\s+(?:manager|owner|pm),?\s+first\b",
        r"\bpm,?\s+first\b",
        r"^first\b",
    )
    return any(re.search(p, stripped, re.I) for p in patterns)


def blocked_title_lists(prefs: dict | None) -> Tuple[list[str], list[str]]:
    """Return (role_designation_terms, focus_area_words) from prefs with legacy fallback."""
    prefs = prefs or {}
    role = prefs.get("blocked_role_titles")
    focus = prefs.get("blocked_focus_area_words")
    if role is not None or focus is not None:
        return list(role or []), list(focus or [])

    legacy = list(prefs.get("blocked_titles") or [])
    if not legacy:
        return list(_DEFAULT_BLOCKED_ROLE_TITLES), list(_DEFAULT_BLOCKED_FOCUS_AREA_WORDS)

    focus_set = {w.lower() for w in _DEFAULT_BLOCKED_FOCUS_AREA_WORDS}
    role_out: list[str] = []
    focus_out: list[str] = []
    for term in legacy:
        if term.lower() in focus_set:
            focus_out.append(term)
        else:
            role_out.append(term)
    return role_out, focus_out


def title_matches_blocked(title: str, blocked: str) -> bool:
    phrase = blocked.strip()
    if not phrase or not title:
        return False
    pattern = r"\b" + re.escape(phrase) + r"\b"
    return bool(re.search(pattern, title, re.I))


def _focus_area_is_primary_role(title: str, term: str) -> bool:
    """True when a focus-area word is the role designation, not a PM specialty."""
    if not _PM_ROLE_RE.search(title):
        return True
    term_re = re.escape(term)
    primary_patterns = (
        rf"\bhead\s+of\s+{term_re}\b",
        rf"^{term_re}\s+(?:lead|director|head|manager)\b",
        rf"\b{term_re}\s+lead\b",
    )
    return any(re.search(p, title, re.I) for p in primary_patterns)


def title_blocked(title: str, prefs: dict | None) -> Optional[str]:
    """Return matched blocklist term or None — Implements CR-055 Epic 2."""
    if not title:
        return None
    role_terms, focus_terms = blocked_title_lists(prefs)
    for term in role_terms:
        if title_matches_blocked(title, term):
            if term.lower() == "assistant":
                pattern = r"\b(virtual|ai|intelligent|digital|voice|chat|smart)\s+assistant\b"
                all_matches = list(re.finditer(r"\bassistant\b", title, re.I))
                product_matches = list(re.finditer(pattern, title, re.I))
                if all_matches and len(all_matches) == len(product_matches):
                    continue
            if term.lower() == "lead" and not _lead_is_role_designation(title):
                continue
            if term.lower() == "first" and not _first_is_role_designation(title):
                continue
            return term
    for term in focus_terms:
        if title_matches_blocked(title, term) and _focus_area_is_primary_role(title, term):
            return term
    return None


def _extract_requirements_sections(jd_text: str) -> str:
    """Pull text under requirements/qualifications headers."""
    lines = jd_text.splitlines()
    chunks: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if _REQ_SECTION_HEADER.search(stripped):
            in_section = True
            continue
        if in_section:
            if re.match(r"^#+\s+\S", stripped) or re.match(r"^[A-Z][A-Z0-9\s/&-]{5,}$", stripped):
                in_section = False
            else:
                chunks.append(line)
    return "\n".join(chunks)


def _context_window(text: str, start: int, end: int, radius: int = 80) -> str:
    return text[max(0, start - radius): min(len(text), end + radius)]


def _plausible_years(value: int, context: str) -> bool:
    if value > MAX_PLAUSIBLE_YEARS:
        return False
    has_experience_signal = bool(
        re.search(
            r"\b(?:experience|experienced|pm|product management|professional)\b",
            context,
            re.I,
        )
    )
    if _NON_EXPERIENCE_CONTEXT.search(context) and not has_experience_signal:
        return False
    return True


def _collect_from_match(text: str, match: re.Match[str]) -> Optional[int]:
    groups = [g for g in match.groups() if g is not None]
    if not groups:
        return None
    nums = [int(g) for g in groups]
    value = max(nums)
    ctx = _context_window(text, match.start(), match.end())
    if not _plausible_years(value, ctx):
        return None
    return value


def parse_max_years_required(jd_text: str) -> Optional[int]:
    """Highest years figure implied as required in JD — requirements-anchored (CR-055)."""
    if not jd_text:
        return None
    found: list[int] = []

    for pat in _ANCHORED_YEARS_PATTERNS:
        for m in pat.finditer(jd_text):
            val = _collect_from_match(jd_text, m)
            if val is not None:
                found.append(val)

    req_text = _extract_requirements_sections(jd_text)
    scan_bodies = [req_text] if req_text.strip() else []
    if not scan_bodies:
        scan_bodies = [jd_text]

    for body in scan_bodies:
        for pat in _LOOSE_YEARS_PATTERNS:
            for m in pat.finditer(body):
                val = _collect_from_match(body, m)
                if val is not None:
                    found.append(val)

    return max(found) if found else None


def check_years_gate(jd_text: str, prefs: dict) -> Tuple[bool, str]:
    """
    Returns (passes, reason). Fails closed when JD requires more than max years.
    """
    exp = (prefs or {}).get("experience_range") or {}
    max_years = exp.get("max")
    if max_years is None:
        return True, ""
    required = parse_max_years_required(jd_text)
    if required is None:
        return True, ""
    if required > int(max_years):
        return False, f"required_years_{required}_exceeds_max_{max_years}"
    return True, ""


def passes_title_gate(jd_text: str, prefs: dict, fallback_title: str = "") -> Tuple[bool, str]:
    title = extract_job_title_line(jd_text) or (fallback_title or "").strip()
    if not title:
        return True, ""
    hit = title_blocked(title, prefs)
    if hit:
        return False, f"title_blocked:{hit}"
    return True, ""
