"""
Deterministic seniority gating (CR-019 / FR-109, CR-055).

- Title blocklist: role-designation terms vs focus-area modifiers (CR-055 Epic 2).
- Years gate: requirements-anchored parsing; ignores incidental numbers (CR-055 Epic 1).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
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

# Age and company-tenure are never a years-of-experience floor (CR-117 / FR-332).
_AGE_CONTEXT = re.compile(
    r"years?\s+of\s+age|years?\s+old|\bmust be\b.{0,24}\b(?:age|eighteen|older)",
    re.I,
)

MAX_PLAUSIBLE_YEARS = 25

# Word-number to digit mapping for spelled-out year counts (found 2026-09-03:
# hale_products_inc JD said "Twelve+ years" but regex \d+ only matches digits).
_WORD_NUMBERS: dict[str, int] = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
}
_WORD_NUMBER_RE = re.compile(
    r"\b(" + "|".join(_WORD_NUMBERS.keys()) + r")\s*\+?\s*years?",
    re.I,
)
_WORD_RANGE_RE = re.compile(
    r"\b(" + "|".join(_WORD_NUMBERS.keys()) + r")\s+to\s+("
    + "|".join(_WORD_NUMBERS.keys()) + r")\s*\+?\s*years?",
    re.I,
)
_YEAR_WORD_ALT = "|".join(_WORD_NUMBERS.keys())
_TENURE_CONTEXT = re.compile(
    r"\bwith\s+over\b"
    r"|\bcustomers\s+for\b"
    r"|\blong-term\s+client"
    r"|\bbeen\s+(?:delivering|serving|operating|providing)"
    r"|\bfor\s+(?:the\s+past\s+)?(?:\d+|" + _YEAR_WORD_ALT + r")\s+years?\b"
    r"(?!\s+(?:of\s+)?(?:product|professional|management|experience))",
    re.I,
)

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
# Fixed 2026-09-03: added ['\u2019']? after years? to handle "years' experience"
# (curly/straight apostrophe, found on sprezzatura JD). Added pattern for
# "N years in product management" (without "experience" keyword, hale JD).
_LOOSE_RANGE_PATTERNS = [
    re.compile(r"(\d+)\s*[-\u2013~]\s*(\d+)\s*\+?\s*years?", re.I),
    re.compile(r"(\d+)\s+to\s+(\d+)\s*\+?\s*years?", re.I),
]
_LOOSE_YEARS_PATTERNS = _LOOSE_RANGE_PATTERNS + [
    re.compile(r"(\d+)\s+years?['\u2019']?\s+(?:of\s+)?(?:product\s+)?(?:management\s+)?experience", re.I),
    re.compile(r"(\d+)\s+years?['\u2019']?\s+of\s+(?:professional\s+)?(?:product\s+)?experience", re.I),
    re.compile(r"(\d+)\s+years?['\u2019']?\s+(?:in\s+)?(?:product\s+)?management", re.I),
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
    """Return (role_designation_terms, focus_area_words) from prefs.

    Merges ``blocked_role_titles`` (pipeline-managed) with ``blocked_titles``
    (UI-sourced) so a term present in only one list is still enforced. Found
    2026-09-03: ``blocked_titles`` had "Junior" but ``blocked_role_titles``
    did not, and this function ignored ``blocked_titles`` entirely when
    ``blocked_role_titles`` existed, so "Junior Product Manager" passed the
    title gate. Same for "Associate" (absent from both lists, but present in
    ``_DEFAULT_BLOCKED_ROLE_TITLES`` which was never reached because
    ``blocked_role_titles`` was non-None).
    """
    prefs = prefs or {}
    role = prefs.get("blocked_role_titles")
    focus = prefs.get("blocked_focus_area_words")
    legacy = list(prefs.get("blocked_titles") or [])

    if role is None and focus is None and not legacy:
        return list(_DEFAULT_BLOCKED_ROLE_TITLES), list(_DEFAULT_BLOCKED_FOCUS_AREA_WORDS)

    # Merge: start from blocked_role_titles, add any blocked_titles entries
    # not already present (de-duplicated case-insensitively).
    role_terms: list[str] = list(role or [])
    focus_terms: list[str] = list(focus or [])
    existing_role_lower = {t.lower() for t in role_terms}
    existing_focus_lower = {t.lower() for t in focus_terms}
    focus_set = {w.lower() for w in _DEFAULT_BLOCKED_FOCUS_AREA_WORDS}
    for term in legacy:
        tl = term.lower()
        if tl in focus_set and tl not in existing_focus_lower:
            focus_terms.append(term)
            existing_focus_lower.add(tl)
        elif tl not in existing_role_lower and tl not in existing_focus_lower:
            role_terms.append(term)
            existing_role_lower.add(tl)
    return role_terms, focus_terms


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
    """True when a years figure is a candidate experience floor, not age or tenure."""
    if value > MAX_PLAUSIBLE_YEARS:
        return False
    if _AGE_CONTEXT.search(context):
        return False
    if _TENURE_CONTEXT.search(context):
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


def _snippet(text: str, start: int, end: int) -> str:
    """Compact context around a years match for audit output. Implements TEST-114D."""
    ctx = _context_window(text, start, end)
    return re.sub(r"\s+", " ", ctx).strip()[:160]


@dataclass(frozen=True)
class YearsHit:
    """One parsed years figure and how the parser found it. Implements TEST-114D."""

    value: int
    source: str
    snippet: str
    is_range: bool
    range_low: int | None = None
    range_high: int | None = None


def _hit_from_match(text: str, match: re.Match[str], source: str) -> Optional[YearsHit]:
    """Build a YearsHit from a numeric regex match, or None if implausible.

    A range gates on its low end, the minimum the posting will accept (CR-117 / FR-332).
    """
    groups = [g for g in match.groups() if g is not None]
    if not groups:
        return None
    nums = [int(g) for g in groups]
    is_range = len(nums) > 1
    value = min(nums) if is_range else nums[0]
    ctx = _context_window(text, match.start(), match.end())
    if not _plausible_years(value, ctx):
        return None
    return YearsHit(
        value=value,
        source=source,
        snippet=_snippet(text, match.start(), match.end()),
        is_range=is_range,
        range_low=min(nums) if is_range else None,
        range_high=max(nums) if is_range else None,
    )


def collect_years_hits(jd_text: str) -> list[YearsHit]:
    """Return every plausible years hit the gate would consider. Implements TEST-114D."""
    if not jd_text:
        return []
    jd_text = _normalize_quotes(jd_text)
    hits: list[YearsHit] = []
    global_range_spans: list[tuple[int, int]] = []
    for pat in _LOOSE_RANGE_PATTERNS:
        for match in pat.finditer(jd_text):
            global_range_spans.append((match.start(), match.end()))

    def _overlaps_range(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
        return any(start < span_end and end > span_start for span_start, span_end in spans)

    for pat in _ANCHORED_YEARS_PATTERNS:
        for match in pat.finditer(jd_text):
            if _overlaps_range(match.start(), match.end(), global_range_spans):
                continue
            hit = _hit_from_match(jd_text, match, source="anchored")
            if hit is not None:
                hits.append(hit)

    req_text = _extract_requirements_sections(jd_text)
    if req_text.strip():
        loose_source = "loose_requirements"
        scan_bodies = [req_text]
    else:
        loose_source = "loose_full_jd"
        scan_bodies = [jd_text]

    for body in scan_bodies:
        numeric_range_spans: list[tuple[int, int]] = []
        for pat in _LOOSE_RANGE_PATTERNS:
            for match in pat.finditer(body):
                hit = _hit_from_match(body, match, source=loose_source)
                numeric_range_spans.append((match.start(), match.end()))
                if hit is not None:
                    hits.append(hit)
        for pat in _LOOSE_YEARS_PATTERNS[len(_LOOSE_RANGE_PATTERNS):]:
            for match in pat.finditer(body):
                if any(
                    match.start() < span_end and match.end() > span_start
                    for span_start, span_end in numeric_range_spans
                ):
                    continue
                hit = _hit_from_match(body, match, source=loose_source)
                if hit is not None:
                    hits.append(hit)

    range_spans: list[tuple[int, int]] = []
    for match in _WORD_RANGE_RE.finditer(jd_text):
        low_word = match.group(1).lower()
        high_word = match.group(2).lower()
        low = _WORD_NUMBERS.get(low_word)
        high = _WORD_NUMBERS.get(high_word)
        if low is None or high is None:
            continue
        range_spans.append((match.start(), match.end()))
        floor, ceiling = min(low, high), max(low, high)
        ctx = _context_window(jd_text, match.start(), match.end())
        if not _plausible_years(floor, ctx):
            continue
        hits.append(
            YearsHit(
                value=floor,
                source="word_number",
                snippet=_snippet(jd_text, match.start(), match.end()),
                is_range=True,
                range_low=floor,
                range_high=ceiling,
            )
        )

    def _in_word_range(start: int, end: int) -> bool:
        return any(start < span_end and end > span_start for span_start, span_end in range_spans)

    seen_values = {hit.value for hit in hits}
    for match in _WORD_NUMBER_RE.finditer(jd_text):
        if _in_word_range(match.start(), match.end()):
            continue
        word = match.group(1).lower()
        val = _WORD_NUMBERS.get(word)
        if val is None or val in seen_values:
            continue
        ctx = _context_window(jd_text, match.start(), match.end())
        if _plausible_years(val, ctx):
            hits.append(
                YearsHit(
                    value=val,
                    source="word_number",
                    snippet=_snippet(jd_text, match.start(), match.end()),
                    is_range=False,
                )
            )
            seen_values.add(val)

    return hits


def wrong_number_flags(hit: YearsHit) -> list[str]:
    """Return range-top, age, or company-history flags for a winning figure.

    The audit asks whether this is the right number, not whether skip arithmetic
    matches the parser's own output. Implements FR-332 / TEST-114D.
    """
    flags: list[str] = []
    if (
        hit.is_range
        and hit.range_high is not None
        and hit.range_low is not None
        and hit.range_low != hit.range_high
        and hit.value == hit.range_high
    ):
        flags.append("range_top")
    if _AGE_CONTEXT.search(hit.snippet):
        flags.append("age")
    if _TENURE_CONTEXT.search(hit.snippet):
        flags.append("company_history")
    return flags


def explain_years_requirement(jd_text: str, prefs: dict | None) -> dict:
    """Explain the years figure used for the gate and whether it is the right number.

    A range contributes its low end. Age, company history, and tenure are not
    experience floors. Implements TEST-114D / FR-332.
    """
    exp = (prefs or {}).get("experience_range") or {}
    max_years_raw = exp.get("max")
    max_years = None if max_years_raw is None else int(max_years_raw)
    hits = collect_years_hits(jd_text)
    required = max((hit.value for hit in hits), default=None)
    gate_passes, reason = check_years_gate(jd_text, prefs or {})
    winning = [hit for hit in hits if hit.value == required] if required is not None else []
    winning_sources = sorted({hit.source for hit in winning})
    flags: list[str] = []
    for hit in winning:
        for flag in wrong_number_flags(hit):
            if flag not in flags:
                flags.append(flag)
    inferred_reasons: list[str] = []
    if required is not None:
        if not any(hit.source == "anchored" for hit in winning):
            inferred_reasons.append("winning_not_anchored")
        if any(hit.source == "loose_full_jd" for hit in winning):
            inferred_reasons.append("loose_full_jd")
        if any(hit.source == "word_number" for hit in winning) and not any(
            hit.source == "anchored" for hit in winning
        ):
            inferred_reasons.append("word_number")
    if max_years is None:
        arithmetic_ok = True
    elif required is None:
        arithmetic_ok = gate_passes
    elif not gate_passes:
        arithmetic_ok = required >= max_years
    else:
        arithmetic_ok = required < max_years
    return {
        "required": required,
        "candidate_max": max_years,
        "gate_passes": gate_passes,
        "reason": reason,
        "arithmetic_ok": arithmetic_ok,
        "wrong_number_flags": flags,
        "inferred": bool(inferred_reasons),
        "inferred_reasons": inferred_reasons,
        "winning_sources": winning_sources,
        "hits": [
            {
                "value": hit.value,
                "source": hit.source,
                "snippet": hit.snippet,
                "is_range": hit.is_range,
                "range_low": hit.range_low,
                "range_high": hit.range_high,
            }
            for hit in hits
        ],
    }


def _normalize_quotes(text: str) -> str:
    """Normalize curly/smart quotes to ASCII equivalents (OWASP UAX-15 guidance).

    Production NLP systems normalize text to a canonical encoding before
    applying regex patterns. Found 2026-09-03: sprezzatura JD had a curly
    apostrophe (U+2019) in "years' experience" that broke the years gate.
    """
    if not text:
        return text
    return (
        text.replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201a", "'")
        .replace("\u201b", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2013", "-")
        .replace("\u2014", "--")
    )


def parse_max_years_required(jd_text: str) -> Optional[int]:
    """Highest experience floor implied as required. A range contributes its low end."""
    hits = collect_years_hits(jd_text)
    return max((hit.value for hit in hits), default=None)


def check_years_gate(jd_text: str, prefs: dict) -> Tuple[bool, str]:
    """
    Returns (passes, reason). Fails closed when JD requires >= max years.

    CR-110 Round 5: Jason targets mid-level (below 7). Roles requiring 7 or
    more years are blocked; roles requiring fewer than 7 are candidates.
    """
    exp = (prefs or {}).get("experience_range") or {}
    max_years = exp.get("max")
    if max_years is None:
        return True, ""
    required = parse_max_years_required(jd_text)
    if required is None:
        return True, ""
    if required >= int(max_years):
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
