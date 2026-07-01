"""
On-site / location classifiers (CR-020 / FR-132).

Implements on-site gate used by batch_pipeline (CR-020 / FR-124).
"""
import re
from typing import Tuple

from utils import call_llm

_LOCAL_SD = (
    "san diego",
    "carlsbad",
    "la jolla",
    "encinitas",
    "del mar",
    "solana beach",
)
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


def is_actually_remote(text: str) -> bool:
    """
    Checks if the job description indicates the role itself is remote,
    excluding mentions of "remote" in negative or team-only contexts.
    """
    # Explicit positive remote patterns
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
            
    # Check for isolated "remote" on its own line (common in headers)
    if "remote" in text:
        for line in text.splitlines():
            line_clean = line.strip().lower()
            if re.match(r"^(?:location|setting|workplace)?\s*:?\s*remote(?:\s*,\s*[a-z\s]+)?$", line_clean):
                return True
                
        # Exclude common negative context / team-only mentions
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


_NON_SD_MAJOR_CITIES = (
    "new york", "nyc", "manhattan", "brooklyn",
    "chicago", "san francisco", "sf,", "sunnyvale", "mountain view",
    "sacramento", "seattle", "boston", "austin", "denver", "atlanta",
    "los angeles", "portland", "philadelphia", "dallas", "houston",
    "toronto", "vancouver", "montreal", "ottawa", "calgary", "canada",
)
_TIMEZONE_RESTRICTED_REMOTE = re.compile(
    r"\b(?:must be|required to be|based in|located in|within)\b.{0,50}\b"
    r"(?:est|eastern|cst|central)(?:\s+time(?:zone)?)?\b",
    re.I | re.DOTALL,
)
_REMOTE_EST_CST_ONLY = re.compile(
    r"\bremote\b.{0,80}\b(?:est|eastern|cst|central)(?:\s+time(?:zone)?)?\b",
    re.I | re.DOTALL,
)
_PACIFIC_FLEX = re.compile(
    r"\b(?:pst|pacific|mst|mountain|flexible.{0,20}time(?:zone)?|any\s+us\s+time)\b",
    re.I,
)


def _mentions_non_sd_city(text: str) -> str | None:
    """Return first non-SD metro signal found in text, if any."""
    for city in _NON_SD_MAJOR_CITIES:
        if city in text:
            return city.strip()
    return None


def _timezone_remote_reject(text: str) -> str | None:
    """Reject remote postings limited to EST/CST when Pacific flexibility is absent."""
    if _PACIFIC_FLEX.search(text):
        return None
    if _TIMEZONE_RESTRICTED_REMOTE.search(text):
        return "Remote role restricted to EST/CST without Pacific-time flexibility"
    if _REMOTE_EST_CST_ONLY.search(text):
        return "Remote role restricted to EST/CST without Pacific-time flexibility"
    if re.search(r"\b(?:est|eastern|cst|central)\s+(?:time(?:zone)?|hours)\s+only\b", text, re.I):
        return "Remote role restricted to EST/CST without Pacific-time flexibility"
    return None


def resolve_location_verdict(jd_text: str) -> Tuple[str, str]:
    """
    Deterministic location eligibility for Remote + San Diego candidate.

    Returns (verdict, detail):
      REMOTE_OK   — explicit remote/WFH; multi-city + Remote listings qualify
      SD_LOCAL_OK — San Diego-area on-site/hybrid signals
      REJECT      — foreign-only or stealth on-site outside SD with no remote
      UNKNOWN     — insufficient signal (do not auto-pass or auto-fail)
    """
    text = (jd_text or "").lower()
    if len(text.strip()) < 50:
        return "UNKNOWN", "insufficient_jd_text"

    has_local_sd = any(k in text for k in _LOCAL_SD)
    has_remote = is_actually_remote(text)

    is_explicit_foreign = any(k in text for k in _FOREIGN_SIGNALS) and not any(
        k in text for k in _US_SIGNALS
    )
    if is_explicit_foreign:
        return "REJECT", "Non-US location signals without US eligibility"

    tz_reject = _timezone_remote_reject(text)
    if tz_reject:
        return "REJECT", tz_reject

    has_hybrid = bool(re.search(r"\bhybrid\b", text))
    has_onsite_explicit = bool(
        re.search(r"\b(on[- ]?site|onsite|in[- ]?office|in office|in[- ]?person)\b", text)
    )
    non_sd_city = _mentions_non_sd_city(text)

    if "canada" in text and (has_hybrid or has_onsite_explicit or "in person" in text or "in-person" in text):
        if not has_remote:
            return "REJECT", "Canada on-site/hybrid without remote eligibility"

    if (has_hybrid or has_onsite_explicit) and non_sd_city and not has_remote:
        return "REJECT", f"On-site/hybrid role in {non_sd_city} without remote option"

    # Remote anywhere in JD wins — even when other US cities are listed ("Dallas or Remote").
    if has_remote:
        return "REMOTE_OK", "Explicit remote / WFH signal in JD"

    if has_local_sd:
        return "SD_LOCAL_OK", "San Diego area location signal in JD"

    onsite_markers = re.search(
        r"\b(on[- ]?site|onsite|in[- ]?office|in office|hybrid|"
        r"\d+\s*days?\s+(?:per\s+)?week\s+in[- ]?office)\b",
        text,
    )
    if onsite_markers:
        loc = classify_location(jd_text)
        return "REJECT", (
            f"Location policy appears {loc or 'On-Site'} without remote or local SD"
        )

    return "UNKNOWN", "No remote, SD, or explicit onsite signal"


def location_lock_prompt_block(verdict: str, detail: str) -> str:
    """Inject into fit LLM prompt when location is pre-verified."""
    if verdict not in ("REMOTE_OK", "SD_LOCAL_OK"):
        return ""
    multi_city_note = (
        "Listings that offer Remote alongside other US cities "
        '(e.g. "Dallas, TX, Atlanta, GA, or Remote") are REMOTE-ELIGIBLE; '
        "do not instant-kill for non-SD city names when Remote is offered."
    )
    return f"""
PRE-VERIFIED LOCATION POLICY: {verdict}
Detail: {detail}
IMPORTANT: Location eligibility was verified deterministically before this evaluation.
Do NOT apply Stage A section 2.3 location instant-kill.
{multi_city_note}
Score location as satisfied; evaluate role fit on title, seniority, domain, and anchors only.
"""


def classify_onsite(jd_text: str) -> Tuple[bool, str]:
    """
    Returns (should_reject, reason).
    Rejects stealth on-site/hybrid roles that are not remote and not San Diego-local.
    Mirrors scout geographic gate (FR-070) for scraped JD text.
    """
    verdict, detail = resolve_location_verdict(jd_text)
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
    
    # Send only the first 2000 chars as location is usually at the top or bottom
    text_sample = jd_text[:1000] + "\n...\n" + jd_text[-1000:]
    try:
        ans = call_llm(system_prompt, text_sample, temperature=0.1)
        if ans:
            ans = ans.strip().lower()
            if 'remote' in ans: return 'Remote'
            if 'hybrid' in ans: return 'Hybrid'
            if 'on-site' in ans or 'onsite' in ans: return 'On-Site'
    except Exception:
        pass
        
    # Regex fallback
    text_lower = jd_text.lower()
    if re.search(r'\b(remote|work from home|wfh)\b', text_lower):
        return 'Remote'
    if re.search(r'\b(hybrid|partial remote)\b', text_lower):
        return 'Hybrid'
    if re.search(r'\b(on-site|onsite|in office|in-office)\b', text_lower):
        return 'On-Site'
        
    return 'Unknown'
