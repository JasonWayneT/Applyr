import re
from utils import call_llm

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
