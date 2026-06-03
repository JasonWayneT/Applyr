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
    has_remote = any(k in text for k in _REMOTE_SIGNALS)

    is_explicit_foreign = any(k in text for k in _FOREIGN_SIGNALS) and not any(
        k in text for k in _US_SIGNALS
    )
    if is_explicit_foreign:
        return "REJECT", "Non-US location signals without US eligibility"

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
