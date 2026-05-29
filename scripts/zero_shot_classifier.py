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
_US_SIGNALS = ("united states", "within the us", "us citizen", "usa")


def classify_onsite(jd_text: str) -> Tuple[bool, str]:
    """
    Returns (should_reject, reason).
    Rejects stealth on-site/hybrid roles that are not remote and not San Diego-local.
    Mirrors scout geographic gate (FR-070) for scraped JD text.
    """
    text = (jd_text or "").lower()
    if len(text.strip()) < 50:
        return False, ""

    has_local_sd = any(k in text for k in _LOCAL_SD)
    has_remote = any(k in text for k in _REMOTE_SIGNALS)

    is_explicit_foreign = any(k in text for k in _FOREIGN_SIGNALS) and not any(
        k in text for k in _US_SIGNALS
    )
    if is_explicit_foreign:
        return True, "Non-US location signals without US eligibility"

    if has_local_sd or has_remote:
        return False, ""

    onsite_markers = re.search(
        r"\b(on[- ]?site|onsite|in[- ]?office|in office|hybrid|"
        r"\d+\s*days?\s+(?:per\s+)?week\s+in[- ]?office)\b",
        text,
    )
    if onsite_markers:
        loc = classify_location(jd_text)
        return True, f"Location policy appears {loc or 'On-Site'} without remote or local SD"

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
