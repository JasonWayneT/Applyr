"""
On-site / location classifiers (CR-020 / FR-132).

Implements on-site gate used by batch_pipeline (CR-020 / FR-124).
Location signals are driven by candidate_preferences.json — no hardcoded metros.
"""
import re
from typing import Tuple

from utils import call_llm, load_candidate_preferences

_REMOTE_SIGNALS = (
    "remote",
    "work from home",
    "wfh",
    "telecommute",
    "anywhere in",
    "distributed",
)
_FOREIGN_SIGNALS = (
    "canada",
    "united kingdom",
    "london,",
    "europe",
    "germany",
    "india",
    "apac",
)
_US_SIGNALS = ("united states", "within the us", "us citizen", "usa", "remote---usa")


def _geo_terms(prefs: dict | None, key: str) -> list[str]:
    prefs = prefs or load_candidate_preferences()
    raw = prefs.get(key) or []
    if not isinstance(raw, list):
        return []
    return [str(t).strip().lower() for t in raw if str(t).strip()]


def _local_area_terms(prefs: dict | None = None) -> list[str]:
    return _geo_terms(prefs, "local_area_terms")


def _timezone_flex_terms(prefs: dict | None = None) -> list[str]:
    return _geo_terms(prefs, "timezone_flexibility_terms")


def _location_preference(prefs: dict | None = None) -> str:
    prefs = prefs or load_candidate_preferences()
    return str(prefs.get("location_preference") or "United States").strip()


def is_actually_remote(text: str) -> bool:
    """
    Checks if the job description indicates the role itself is remote,
    excluding mentions of "remote" in negative or team-only contexts.
    """
    positive_patterns = [
        r"\bwork\s+(?:remotely|from\s+home)\b",
        r"\b(?:wfh|telecommute|telecommuting)\b",
        r"\bremote[- ](?:first|eligible|friendly|only|based)\b",
        r"\b(?:fully|100%|completely|mostly)\s+remote\b",
        r"\b(?:position|role|job)\s+is\s+remote\b",
        r"\b(?:open|option|opportunity)\s+to\s+work\s+remote\b",
        r"\boption\s+for\s+remote\b",
        r"\bopen\s+to\s+remote\b",
        r"\bremote\s+(?:position|role|job|opportunity|work|status)\b",
        r"\bremote\s*-\s*(?:usa?|united\s+states|us|canada)\b",
    ]
    for pat in positive_patterns:
        if re.search(pat, text, re.I):
            return True

    if "remote" in text:
        for line in text.splitlines():
            line_clean = line.strip().lower()
            if re.match(r"^(?:location|setting|workplace)?\s*:?\s*remote(?:\s*,\s*[a-z\s]+)?$", line_clean):
                return True

        neg_patterns = [
            r"\b(?:not|no|non|never)\s+remote\b",
            r"\bnot\s+(?:eligible\s+for\s+|open\s+to\s+)?remote\b",
            r"\bno\s+remote\b",
            r"\bnot\s+open\s+to\s+remote\b",
            r"\bcollaborate\s+(?:with|across)\s+remote\b",
            r"\b(?:manage|lead|working\s+with|support|interaction\s+with)\s+remote\b",
            r"\bremote\s+(?:teams?|workers?|colleagues?|counterparts?|locations?|offices?|support|access)\b",
        ]

        all_remotes = list(re.finditer(r"\bremote\b", text, re.I))
        negated_count = 0
        for pat in neg_patterns:
            for m in re.finditer(pat, text, re.I):
                negated_count += m.group(0).lower().count("remote")

        if len(all_remotes) > 0 and negated_count < len(all_remotes):
            return True

    return False


_TIMEZONE_RESTRICTED_REMOTE = re.compile(
    r"\b(?:must be|required to be|based in|located in|within)\b.{0,50}\b"
    r"(?:est|eastern|cst|central)(?:\s+time(?:zone)?)?\b",
    re.I | re.DOTALL,
)
_REMOTE_EST_CST_ONLY = re.compile(
    r"\bremote\b.{0,80}\b(?:est|eastern|cst|central)(?:\s+time(?:zone)?)?\b",
    re.I | re.DOTALL,
)


def _timezone_restrict_enabled(prefs: dict | None) -> bool:
    """Only filter EST/CST remote when user opts in (default: accept any US remote timezone)."""
    prefs = prefs or {}
    return (prefs.get("preferences") or {}).get("reject_est_cst_remote") is True


def _timezone_remote_reject(text: str, prefs: dict | None = None) -> str | None:
    """Reject EST/CST-only remote when preferences.reject_est_cst_remote is true."""
    if not _timezone_restrict_enabled(prefs):
        return None
    flex_terms = _timezone_flex_terms(prefs)
    if flex_terms and any(term in text for term in flex_terms):
        return None
    if _TIMEZONE_RESTRICTED_REMOTE.search(text):
        return "Remote role restricted to EST/CST without configured timezone flexibility"
    if _REMOTE_EST_CST_ONLY.search(text):
        return "Remote role restricted to EST/CST without configured timezone flexibility"
    if re.search(r"\b(?:est|eastern|cst|central)\s+(?:time(?:zone)?|hours)\s+only\b", text, re.I):
        return "Remote role restricted to EST/CST without configured timezone flexibility"
    return None


def resolve_location_verdict(jd_text: str, prefs: dict | None = None) -> Tuple[str, str]:
    """
    Deterministic location eligibility from user geo prefs.

    Returns (verdict, detail):
      REMOTE_OK   — explicit remote/WFH
      LOCAL_OK    — matches local_area_terms in prefs
      REJECT      — foreign-only or stealth on-site/hybrid outside configured local areas
      UNKNOWN     — insufficient signal
    """
    prefs = prefs or load_candidate_preferences()
    text = (jd_text or "").lower()
    if len(text.strip()) < 50:
        return "UNKNOWN", "insufficient_jd_text"

    local_terms = _local_area_terms(prefs)
    has_local = any(term in text for term in local_terms) if local_terms else False
    has_remote = is_actually_remote(text)

    loc_pref = _location_preference(prefs).lower()
    is_explicit_foreign = any(k in text for k in _FOREIGN_SIGNALS) and not any(
        k in text for k in _US_SIGNALS
    )
    if is_explicit_foreign and ("united states" in loc_pref or "usa" in loc_pref or loc_pref == "us"):
        return "REJECT", "Non-US location signals without US eligibility"

    tz_reject = _timezone_remote_reject(text, prefs)
    if tz_reject:
        return "REJECT", tz_reject

    has_hybrid = bool(re.search(r"\bhybrid\b", text))
    has_onsite_explicit = bool(
        re.search(r"\b(on[- ]?site|onsite|in[- ]?office|in office|in[- ]?person)\b", text)
    )

    if "canada" in text and (has_hybrid or has_onsite_explicit or "in person" in text or "in-person" in text):
        if not has_remote:
            return "REJECT", "Canada on-site/hybrid without remote eligibility"

    if has_remote:
        return "REMOTE_OK", "Explicit remote / WFH signal in JD"

    if has_local:
        return "LOCAL_OK", "Configured local area signal in JD"

    onsite_markers = re.search(
        r"\b(on[- ]?site|onsite|in[- ]?office|in office|hybrid|"
        r"\d+\s*days?\s+(?:per\s+)?week\s+in[- ]?office)\b",
        text,
    )
    if onsite_markers and not has_remote and not has_local:
        return "REJECT", "On-site/hybrid role without remote or configured local area"

    return "UNKNOWN", "No remote, local area, or explicit onsite signal"


def location_lock_prompt_block(verdict: str, detail: str) -> str:
    """Inject into fit LLM prompt when location is pre-verified."""
    if verdict not in ("REMOTE_OK", "LOCAL_OK"):
        return ""
    multi_city_note = (
        "Listings that offer Remote alongside other US cities "
        '(e.g. "Dallas, TX, Atlanta, GA, or Remote") are REMOTE-ELIGIBLE; '
        "do not instant-kill for city names outside local_area_terms when Remote is offered."
    )
    return f"""
PRE-VERIFIED LOCATION POLICY: {verdict}
Detail: {detail}
IMPORTANT: Location eligibility was verified deterministically before this evaluation.
Do NOT apply Stage A section 2.3 location instant-kill.
{multi_city_note}
Score location as satisfied; evaluate role fit on title, seniority, domain, and anchors only.
"""


def classify_onsite(jd_text: str, prefs: dict | None = None) -> Tuple[bool, str]:
    """
    Returns (should_reject, reason).
    Rejects stealth on-site/hybrid roles that are not remote and not in configured local areas.
    """
    verdict, detail = resolve_location_verdict(jd_text, prefs)
    if verdict == "REJECT":
        return True, detail
    return False, ""


def classify_location(jd_text: str) -> str:
    """
    Zero-Shot classifier for job location (Remote, Hybrid, or On-Site).
    Falls back to regex heuristics if local model fails.
    """
    system_prompt = (
        "You are an expert HR text analyzer. "
        "Read the job description and determine the location policy. "
        "Output ONLY ONE WORD: 'Remote', 'Hybrid', or 'On-Site'."
    )

    text_sample = jd_text[:1000] + "\n...\n" + jd_text[-1000:]
    try:
        ans = call_llm(system_prompt, text_sample, temperature=0.1)
        if ans:
            ans = ans.strip().lower()
            if 'remote' in ans:
                return 'Remote'
            if 'hybrid' in ans:
                return 'Hybrid'
            if 'on-site' in ans or 'onsite' in ans:
                return 'On-Site'
    except Exception:
        pass

    text_lower = jd_text.lower()
    if re.search(r'\b(remote|work from home|wfh)\b', text_lower):
        return 'Remote'
    if re.search(r'\b(hybrid|partial remote)\b', text_lower):
        return 'Hybrid'
    if re.search(r'\b(on-site|onsite|in office|in-office)\b', text_lower):
        return 'On-Site'

    return 'Unknown'
