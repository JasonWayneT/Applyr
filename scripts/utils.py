"""
Shared utilities for the JobAgent pipeline.
Centralizes file I/O, LLM calls with retry logic, and path constants.
"""
import os
import sys
import time
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

# --- Path Constants ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS_DIR = os.path.join(PROJECT_ROOT, "jobs")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
AGENT_DIR = os.path.join(PROJECT_ROOT, ".agent")
RULES_DIR = os.path.join(AGENT_DIR, "rules")
SUBMISSIONS_DIR = os.path.join(PROJECT_ROOT, "data", "submissions")
ARCHIVE_DIR = os.path.join(PROJECT_ROOT, "data", "archive", "submissions")
DB_PATH = os.path.join(PROJECT_ROOT, "data", "jobagent.sqlite")

WORK_EXP_FILE = os.path.join(DATA_DIR, "workExperience.md")
WORK_EXP_SUMMARY_FILE = os.path.join(DATA_DIR, "workExperience_summary.md")
# Legacy JSON job store â€” superseded by jobagent.sqlite (see docs/ACTIVE_WORKFLOW.md). Used only by scripts/archive/*.
DB_FILE = os.path.join(DATA_DIR, "job_database.json")
FIT_ENGINE_FILE = os.path.join(RULES_DIR, "job_fit_engine.md")
CLAIM_VERIFIER_FILE = os.path.join(RULES_DIR, "claim_verifier.md")
RESEARCH_CONTRACT_FILE = os.path.join(RULES_DIR, "Research_Packet_Contract.md")
RESUME_MASTER_FILE = os.path.join(DATA_DIR, "Resume.md")
COVER_LETTER_REF_FILE = os.path.join(DATA_DIR, "Cover_Letter_Reference.md")
RESUME_STYLE_REF_FILE = os.path.join(DATA_DIR, "Resume_Style_Reference.md")
RESUME_BEST_PRACTICES = os.path.join(DATA_DIR, "resume-conversion-best-practices.md")
CL_BEST_PRACTICES = os.path.join(DATA_DIR, "cover-letter-conversion-best-practices.md")
CANDIDATE_PREFERENCES_FILE = os.path.join(DATA_DIR, "candidate_preferences.json")

# Default cloud model â€” must have non-zero free-tier quota on the user's AI Studio project.
# gemini-2.0-flash often returns limit:0 on free tier (see BUG-009); 2.5-flash-lite works.
DEFAULT_MODEL = "gemini-2.5-flash-lite"

# Max JD characters to send to LLM for scoring (token budget gate)
SCORING_JD_MAX_CHARS = 1500

_DEFAULT_JD_KEYWORDS = [
    'saas', 'b2b', 'b2c', 'consumer', 'platform', 'integration', 'enterprise', 'api',
    'product', 'software', 'agile', 'roadmap', 'stakeholder', 'mobile', 'app',
]

def _bootstrap_from_prefs():
    """Read pipeline config from candidate_preferences.json at import time."""
    try:
        prefs_path = os.path.join(DATA_DIR, 'candidate_preferences.json')
        if os.path.exists(prefs_path):
            import json as _json
            with open(prefs_path, 'r', encoding='utf-8') as f:
                p = _json.load(f)
            return (
                p.get('jd_required_keywords', _DEFAULT_JD_KEYWORDS),
                p.get('min_fit_score', 72),
            )
    except Exception:
        pass
    return _DEFAULT_JD_KEYWORDS, 72

def get_min_fit_score(default: int = 72) -> int:
    prefs = load_candidate_preferences()
    try:
        return int(prefs.get("min_fit_score", default))
    except (TypeError, ValueError):
        return default


def get_scoring_jd_max_chars(default: int = 4000) -> int:
    """Max JD characters sent to fit-scoring LLM (from candidate_preferences.json)."""
    prefs = load_candidate_preferences()
    try:
        raw = int(prefs.get("scoring_jd_max_chars", default))
        return max(500, min(raw, 15000))
    except (TypeError, ValueError):
        return default


def get_jd_required_keywords(default: list | None = None) -> list:
    """Legacy OR-list; prefers signal_keywords when set (FR-171)."""
    prefs = load_candidate_preferences()
    signal = prefs.get("signal_keywords")
    if isinstance(signal, list) and signal:
        return signal
    keywords = prefs.get("jd_required_keywords")
    if isinstance(keywords, list) and keywords:
        return keywords
    return default if default is not None else list(_DEFAULT_JD_KEYWORDS)


def get_must_have_keywords() -> list:
    """Implements FR-171 â€” all must match (AND) when non-empty."""
    prefs = load_candidate_preferences()
    raw = prefs.get("must_have_keywords")
    if isinstance(raw, list) and raw:
        return [str(k).strip().lower() for k in raw if str(k).strip()]
    return []


def get_signal_keywords() -> list:
    """Implements FR-171 â€” at least one must match when must_have is empty."""
    return [k.lower() for k in get_jd_required_keywords()]


def passes_keyword_gate(jd_text: str, prefs: dict | None = None) -> tuple[bool, str]:
    """Implements FR-171 / FR-006 â€” AND must-haves, else OR signals."""
    prefs = prefs or load_candidate_preferences()
    lower = (jd_text or "").lower()
    if not lower.strip():
        return False, "empty_jd"

    must = [
        str(k).strip().lower()
        for k in (prefs.get("must_have_keywords") or [])
        if str(k).strip()
    ]
    if must:
        for kw in must:
            if kw not in lower:
                return False, f"missing_must_have:{kw}"
        return True, ""

    signal = prefs.get("signal_keywords") or prefs.get("jd_required_keywords")
    if not isinstance(signal, list) or not signal:
        signal = list(_DEFAULT_JD_KEYWORDS)
    signal = [str(k).strip().lower() for k in signal if str(k).strip()]
    if any(kw in lower for kw in signal):
        return True, ""
    return False, "no_signal_keywords"


# Module-level compat vars â€” call init_pipeline_prefs() at CLI/smoke entry (CR-ARCH-003).
JD_REQUIRED_KEYWORDS: list = list(_DEFAULT_JD_KEYWORDS)
MIN_FIT_SCORE: int = 72


def init_pipeline_prefs() -> None:
    """Load jd_required_keywords and min_fit_score from candidate_preferences.json."""
    global JD_REQUIRED_KEYWORDS, MIN_FIT_SCORE
    JD_REQUIRED_KEYWORDS, MIN_FIT_SCORE = _bootstrap_from_prefs()


def load_candidate_preferences():
    """Reads data/candidate_preferences.json dynamically. Returns dict or empty dict on failure."""
    import json
    try:
        if os.path.exists(CANDIDATE_PREFERENCES_FILE):
            with open(CANDIDATE_PREFERENCES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading candidate preferences: {e}", file=sys.stderr)
    return {}


# --- Rate Limit & Validation Helpers ---
def check_rate_limits(provider: str) -> bool:
    """
    Checks rate limits for a provider via activity_log.
    Returns True if allowed to proceed, False if provider should be skipped/disabled.
    Sleeps if approaching RPM limit.
    """
    if provider != 'gemini':
        return True
        
    import sqlite3
    db_path = DB_PATH
    try:
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path, timeout=10.0)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM activity_log WHERE source = 'LLM_Call' AND message LIKE '%[gemini]%' AND timestamp >= datetime('now', '-24 hours')")
            daily_calls = cursor.fetchone()[0]
            if daily_calls >= 1400:
                print(f"    [Circuit Breaker] Gemini daily quota exceeded ({daily_calls}/1500). Disabling Gemini for 24h.", file=sys.stderr)
                conn.close()
                return False
                
            cursor.execute("SELECT COUNT(*) FROM activity_log WHERE source = 'LLM_Call' AND message LIKE '%[gemini]%' AND timestamp >= datetime('now', '-1 minute')")
            minute_calls = cursor.fetchone()[0]
            
            cursor.execute("INSERT INTO activity_log (level, source, message) VALUES ('INFO', 'LLM_Call', '[gemini] API request initiated')")
            conn.commit()
            conn.close()
            
            if minute_calls >= 14:
                print(f"    [Circuit Breaker] Gemini RPM approaching limit ({minute_calls}/15). Sleeping 60s...", file=sys.stderr)
                time.sleep(60)
                
    except Exception as e:
        print(f"    [Circuit Breaker Error] {e}", file=sys.stderr)
        
    return True


def extract_json_from_text(text: str) -> str:
    """
    Robustly extracts a JSON object from text, stripping markdown codeblocks
    and conversational fluff.
    """
    import re
    if not text:
        return ""
        
    text = text.strip()
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group(0).strip()
        
    if text.startswith("```json"):
        text = text[7:-3].strip()
    elif text.startswith("```"):
        text = text[3:-3].strip()
        
    return text.strip()


def load_file(filepath):
    """Read a text file safely. Returns empty string on failure."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}", file=sys.stderr)
        return ""


def clean_jd_text(text: str) -> str:
    """Removes HTML tags, boilerplate, navbars, and excess whitespace to save tokens."""
    import re
    if not text:
        return ""
    # Strip HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Remove extra spaces and newlines
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


def load_api_connections():
    """Reads api_connections from SQLite profiles table. Returns dict or empty dict on failure."""
    import sqlite3
    import json
    db_path = DB_PATH
    try:
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM profiles WHERE key = 'api_connections'")
            row = cursor.fetchone()
            conn.close()
            if row:
                return json.loads(row[0])
    except Exception as e:
        print(f"Error loading API connections from DB: {e}", file=sys.stderr)
    return {}


def load_llm_settings():
    """Reads llm_settings from SQLite profiles table dynamically. Returns dict or empty dict on failure."""
    import sqlite3
    import json
    db_path = DB_PATH
    try:
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM profiles WHERE key = 'llm_settings'")
            row = cursor.fetchone()
            conn.close()
            if row:
                return json.loads(row[0])
    except Exception as e:
        print(f"Error loading LLM settings from DB: {e}", file=sys.stderr)
    return {}


_DEFAULT_IDENTITY = {
    "name": "John Doe",
    "email": "email@example.com",
    "phone": "555-019-9238",
    "location": "City, State",
    "linkedin": "linkedin.com/in/johndoe",
    "portfolio": "johndoe.com",
    "github": "",
}


def load_identity_profile() -> dict:
    """Reads identity contact fields from SQLite profiles table."""
    import sqlite3
    import json

    profile = dict(_DEFAULT_IDENTITY)
    db_path = DB_PATH
    try:
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM profiles WHERE key = 'identity'")
            row = cursor.fetchone()
            conn.close()
            if row:
                data = json.loads(row[0])
                for key, value in data.items():
                    if value:
                        profile[key] = value
    except Exception as e:
        print(f"Error loading identity profile from DB: {e}", file=sys.stderr)
    return profile


def format_contact_line(profile: dict | None = None) -> str:
    """Single-line contact string for resume/cover letter headers."""
    profile = profile or load_identity_profile()
    parts = [
        profile.get("location"),
        profile.get("phone"),
        profile.get("email"),
        profile.get("linkedin"),
        profile.get("portfolio"),
    ]
    return " | ".join(p for p in parts if p)


def format_contact_header_block(profile: dict | None = None) -> str:
    """Markdown header block: # Name + contact line.

    2026-08-09: was `# {name.upper()}` with a blank line before the contact line -- a different,
    older convention than the CR-074 packet path (apply_resume_header.py), which preserves
    workExperience.md's real casing ("Jason Taylor", not "JASON TAYLOR"). The inconsistency was
    latent until a real, already-CR-074-authored submission (camunda) went through this function
    for the first time via the editor-save route and got its header silently rewritten to the
    wrong case. Jason's call: real casing wins everywhere, and the spacing matches CLAUDE.md's
    documented Required Document Structure (`# [Name]` then the contact line on the very next
    line, no blank line between them) -- this function was also violating that.
    """
    profile = profile or load_identity_profile()
    name = (profile.get("name") or _DEFAULT_IDENTITY["name"]).strip()
    return f"# {name}\n{format_contact_line(profile)}\n\n"


def contact_placeholder_map(profile: dict | None = None, target_company: str | None = None) -> dict:
    """Template placeholder â†’ profile values for draft post-processing."""
    profile = profile or load_identity_profile()
    name = (profile.get("name") or _DEFAULT_IDENTITY["name"]).strip()
    placeholders = {
        "[Your Name]": name,
        "*[Your Name]*": name,
        "[Full Name]": name,
        "[Your Phone Number]": profile.get("phone", ""),
        "[Phone Number]": profile.get("phone", ""),
        "[Your Email Address]": profile.get("email", ""),
        "[Your Email]": profile.get("email", ""),
        "[Email Address]": profile.get("email", ""),
        "[Your LinkedIn Profile URL]": profile.get("linkedin", ""),
        "[LinkedIn Profile URL]": profile.get("linkedin", ""),
        "[LinkedIn URL]": profile.get("linkedin", ""),
        "[LinkedIn]": profile.get("linkedin", ""),
        "## [Your Name]": f"# {name}",
        "[Your City, State]": profile.get("location", ""),
        "[City, State]": profile.get("location", ""),
        "[Hiring Manager Name]": "Hiring Team",
        "[Hiring Manager]": "Hiring Team",
        "[Dates]": "",
        "*[Dates]*": "",
    }
    if target_company:
        placeholders["[Company Name]"] = target_company
        placeholders["*[Company Name]*"] = target_company
        placeholders["[Target Company]"] = target_company
    return placeholders


# --- Implements FR-059: Provider configuration guard ---
def _is_configured(provider: str, settings: dict) -> bool:
    """Returns True only if the given provider has a usable key or URL configured."""
    if provider == 'gemini':
        return bool(settings.get('geminiApiKey') or os.getenv('GEMINI_API_KEY'))
    if provider == 'claude':
        return bool(settings.get('claudeApiKey') or os.getenv('ANTHROPIC_API_KEY'))
    if provider == 'local':
        return bool(settings.get('localUrl') or os.getenv('OLLAMA_HOST'))
    if provider == 'perplexity':
        return bool(settings.get('perplexityApiKey') or os.getenv('PERPLEXITY_API_KEY'))
    return False


# --- Implements FR-060, FR-063: Multi-provider fallback chain with primaryProvider ---
def _get_configured_providers(settings: dict) -> list:
    """Returns providers in call order: primary first, then remaining configured ones."""
    primary = settings.get('primaryProvider') or settings.get('provider', 'gemini')
    fixed_order = ['gemini', 'claude', 'local', 'perplexity']
    ordered = [primary] + [p for p in fixed_order if p != primary]
    return [p for p in ordered if _is_configured(p, settings)]


def _call_gemini(settings, system_prompt, user_prompt, model, temperature,
                 response_mime_type, tools, max_retries):
    """Returns result string on success, None to signal try-next-provider."""
    from google import genai
    from google.genai import types
    api_key = settings.get('geminiApiKey') or os.getenv('GEMINI_API_KEY')
    try:
        local_client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"    [LLM Error] Failed to initialize Gemini client: {e}", file=sys.stderr)
        return None
    target_model = model or DEFAULT_MODEL
    print(f"    [LLM] Calling Gemini: {target_model}...", file=sys.stderr)
    for attempt in range(max_retries):
        try:
            config_kwargs = {"system_instruction": system_prompt, "temperature": temperature}
            if response_mime_type:
                config_kwargs["response_mime_type"] = response_mime_type
            if tools:
                config_kwargs["tools"] = tools
            config = types.GenerateContentConfig(**config_kwargs)
            response = local_client.models.generate_content(
                model=target_model, contents=user_prompt, config=config
            )
            return (response.text or "").strip()
        except Exception as e:
            err = str(e).lower()
            if any(k in err for k in ["retrydelay", "429", "quota", "exhausted", "503", "unavailable"]):
                print(f"    [LLM Notice] Gemini is busy/rate-limited ({err[:100]}). Falling back to local model tier...", file=sys.stderr)
                return None
            else:
                print(f"    [LLM Error] Gemini: {e}", file=sys.stderr)
                return None
    return None


def _call_claude(settings, system_prompt, user_prompt, model, temperature, max_retries):
    """Returns result string on success, None to signal try-next-provider."""
    import requests
    api_key = settings.get('claudeApiKey') or os.getenv('ANTHROPIC_API_KEY')
    target_model = model or "claude-3-5-sonnet-20241022"
    print(f"    [LLM] Calling Claude: {target_model}...", file=sys.stderr)
    for attempt in range(max_retries):
        try:
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            payload = {
                "model": target_model,
                "max_tokens": 4000,
                "temperature": temperature,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            }
            res = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
            if res.status_code == 200:
                return res.json()["content"][0]["text"].strip()
            elif res.status_code == 429:
                wait = 60 * (attempt + 1)
                print(f"  -> Claude rate limit. Waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
            else:
                print(f"    [LLM Error] Claude status {res.status_code}: {res.text}", file=sys.stderr)
                return None
        except Exception as e:
            print(f"    [LLM Error] Claude: {e}", file=sys.stderr)
            return None
    return None


def _call_local(settings, system_prompt, user_prompt, model, temperature, response_mime_type=None, options_override=None, response_schema=None, request_timeout=120):
    """
    Returns result string on success, None to signal try-next-provider.
    Implements intra-local model fallback chain (e.g. fallback to smaller model if large one hits OOM).
    """
    import requests
    import model_manager
    
    base_url = settings.get('localUrl') or os.getenv('OLLAMA_HOST') or 'http://localhost:11434'

    # If caller explicitly pins a model, honour it directly.
    # Otherwise select dynamically based on available VRAM.
    # Default fallback is the primary model — never silently degrade to phi.
    primary = settings.get('localModel') or 'llama3.1:8b-instruct-q5_K_M'
    fallback = settings.get('localFallbackModel') or primary
    if model:
        target_model = model
        models_to_try = [model]
    else:
        target_model = model_manager.select_model(settings)
        models_to_try = [target_model]
        if target_model != fallback:
            models_to_try.append(fallback)

    # ANTI-HALLUCINATION CONSTRAINT PREFIX
    LOCAL_CONSTRAINT_PREFIX = (
        "STRICT RULES YOU MUST FOLLOW WITHOUT EXCEPTION:\n"
        "1. ONLY use facts, company names, job titles, tools, and metrics explicitly provided in the user prompt.\n"
        "2. NEVER invent, assume, or extrapolate any information not directly stated.\n"
        "3. NEVER mention tools such as Snowflake, Tableau, Docker, Kubernetes, AWS, GCP, Azure, FHIR, HL7, "
        "TensorFlow, or any technology not explicitly listed in the provided ground truth.\n"
        "4. NEVER inflate seniority. Do not write 'Led a team', 'Managed a team', 'Director', 'VP', or 'Head of'.\n"
        "5. NEVER invent percentage or dollar metrics. Only use numbers explicitly given to you.\n"
        "6. Output ONLY what was asked. No preamble, no explanations, no footnotes.\n\n"
    )
    enhanced_system = LOCAL_CONSTRAINT_PREFIX + system_prompt
    
    anchored_user_original = user_prompt + "\n\n[SYSTEM REMINDER: You must strictly follow the constraints defined in your system prompt, especially regarding factual accuracy and output formatting.]"

    def _truncate_prompt(prompt: str, fraction: float = 0.5) -> str:
        length = len(prompt)
        if length < 2000:
            return prompt
        keep_start = int(length * fraction / 2)
        keep_end = int(length * fraction / 2)
        return prompt[:keep_start] + "\n\n...[TRUNCATED BY LOCAL GUARD]...\n\n" + prompt[-keep_end:]

    for target_model in models_to_try:
        anchored_user = anchored_user_original
        for attempt in range(2):
            print(f"    [LLM] Calling Local LLM ({base_url}) Model: {target_model} (Attempt {attempt+1})...", file=sys.stderr)
            endpoint = base_url.rstrip('/')
            if not endpoint.endswith('/v1') and not endpoint.endswith('/v1/chat/completions'):
                endpoint = f"{endpoint}/v1/chat/completions"
            elif endpoint.endswith('/v1'):
                endpoint = f"{endpoint}/chat/completions"

            try:
                ollama_endpoint = base_url.rstrip('/') + '/api/chat'
                payload_ollama = {
                    "model": target_model,
                    "messages": [
                        {"role": "system", "content": enhanced_system},
                        {"role": "user", "content": anchored_user},
                    ],
                    "options": {
                        "temperature": temperature,
                        "num_ctx": 16384,
                        "num_predict": 4000,
                        "top_k": 40,
                        "top_p": 0.9,
                        "repeat_penalty": 1.1,
                    },
                    "stream": False,
                }
                
                if options_override:
                    payload_ollama["options"].update(options_override)

                if response_schema:
                    payload_ollama["format"] = response_schema
                elif response_mime_type == 'application/json':
                    payload_ollama["format"] = "json"
                    
                res_ollama = requests.post(ollama_endpoint, json=payload_ollama, timeout=request_timeout)
                if res_ollama.status_code == 200:
                    res_json = res_ollama.json()
                    result = res_json.get("message", {}).get("content", "")
                    if result.strip():
                        return result.strip()
                else:
                    print(f"    [LLM Local Error] HTTP {res_ollama.status_code}: {res_ollama.text}", file=sys.stderr)

                # Fallback to OpenAI compatibility API
                payload = {
                    "model": target_model,
                    "temperature": temperature,
                    "messages": [
                        {"role": "system", "content": enhanced_system},
                        {"role": "user", "content": anchored_user},
                    ],
                }
                if response_mime_type == 'application/json':
                    payload["response_format"] = {"type": "json_object"}
                res = requests.post(endpoint, json=payload, timeout=request_timeout)
                if res.status_code == 200:
                    result = res.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                    if result.strip():
                        return result.strip()

            except Exception as e:
                print(f"    [LLM Local Warning] Connection failed for model '{target_model}': {e}", file=sys.stderr)

            # If we reach here, the attempt failed
            if attempt == 0:
                print(f"    [LLM] Local call failed (OOM/Timeout). Truncating context by 50% for fast-retry...", file=sys.stderr)
                anchored_user = _truncate_prompt(anchored_user_original, 0.5)
            else:
                print(f"    [LLM] Model '{target_model}' failed both full and truncated attempts.", file=sys.stderr)

        if target_model != models_to_try[-1]:
            print(f"    [LLM] Attempting next local fallback model...", file=sys.stderr)

    # Exhausted all local models
    return None


# --- Implements FR-061: Perplexity as LLM provider ---
def _call_perplexity(settings, system_prompt, user_prompt, temperature, max_retries):
    """Returns result string on success, None to signal try-next-provider."""
    import requests
    api_key = settings.get('perplexityApiKey') or os.getenv('PERPLEXITY_API_KEY')
    print("    [LLM] Calling Perplexity sonar-pro...", file=sys.stderr)
    for attempt in range(max_retries):
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "sonar-pro",
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
            res = requests.post("https://api.perplexity.ai/chat/completions", headers=headers, json=payload)
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"].strip()
            elif res.status_code == 429:
                wait = 60 * (attempt + 1)
                print(f"  -> Perplexity rate limit. Waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
            else:
                print(f"    [LLM Error] Perplexity status {res.status_code}: {res.text}", file=sys.stderr)
                return None
        except Exception as e:
            print(f"    [LLM Error] Perplexity: {e}", file=sys.stderr)
            return None
    return None


def call_llm(system_prompt, user_prompt, model=None, temperature=0.2,
             response_mime_type=None, tools=None, max_retries=8, provider_override=None,
             options_override=None, response_schema=None, request_timeout=120):
    """
    Centralized LLM call with automatic provider fallback chain.
    Implements FR-059 (provider guard), FR-060 (fallback), FR-061 (Perplexity), FR-063 (primaryProvider).
    Only calls providers that have a configured key. On non-rate-limit error, falls through to next provider.
    
    Use provider_override (str or list) to lock specific high-fidelity operations (like drafting)
    to cloud models, bypassing the local core.
    """
    settings = load_llm_settings()
    all_providers = _get_configured_providers(settings)
    
    try:
        from pii_guard import redact_pii
        user_prompt = redact_pii(user_prompt)
        system_prompt = redact_pii(system_prompt)
    except ImportError:
        pass
    except Exception as e:
        print(f"    [Warning] Failed to run PII redaction: {e}", file=sys.stderr)
        
    try:
        from pipeline_env import local_only_mode as _local_only_env
    except ImportError:
        _local_only_env = lambda: False

    if provider_override:
        requested = [provider_override] if isinstance(provider_override, str) else provider_override
        # Filter list to only configured providers that match request
        providers = [p for p in requested if p in all_providers]
    else:
        providers = all_providers

    if _local_only_env():
        providers = [p for p in providers if p == "local"]
        if not providers and "local" in all_providers:
            providers = ["local"]

    if not providers:
        print(
            "    [LLM Error] No configured LLM providers. Add an API key via Settings > API or Connections.",
            file=sys.stderr,
        )
        return ""

    for i, provider in enumerate(providers):
        if not check_rate_limits(provider):
            continue
            
        result = None
        if provider == 'gemini':
            result = _call_gemini(
                settings, system_prompt, user_prompt, model, temperature,
                response_mime_type, tools, max_retries
            )
        elif provider == 'claude':
            # Claude does not support google_search tools â€” tools param intentionally omitted
            result = _call_claude(settings, system_prompt, user_prompt, model, temperature, max_retries)
        elif provider == 'local':
            result = _call_local(
                settings, system_prompt, user_prompt, model, temperature,
                response_mime_type, options_override, response_schema, request_timeout,
            )
        elif provider == 'perplexity':
            result = _call_perplexity(settings, system_prompt, user_prompt, temperature, max_retries)

        if result is not None:
            return result
        if _local_only_env():
            print("    [LLM] Local-only mode: no cloud fallback.", file=sys.stderr)
            break
        if i + 1 < len(providers):
            print(f"    [LLM] Falling back from {provider} to {providers[i + 1]}...", file=sys.stderr)

    return ""


def get_verifier_model() -> str:
    """Returns the configured local verifier model, defaulting to phi3.5."""
    settings = load_llm_settings()
    return settings.get('localVerifierModel') or 'phi3.5:3.8b-mini-instruct-q8_0'


def unload_local_models():
    """
    Forces local Ollama instance to unload any active models immediately, 
    restoring GPU VRAM back to system/desktop.
    """
    import model_manager
    settings = load_llm_settings()
    if not _is_configured('local', settings):
        return
    
    base_url = settings.get('localUrl', 'http://localhost:11434')
    model_manager.unload_all_models(base_url)

def send_notification(message: str, topic: str = "jobagent_alerts"):
    """
    Sends a push notification via ntfy.sh.
    Implements local-first notification webhooks for pipeline events.
    """
    import requests
    try:
        requests.post(f"https://ntfy.sh/{topic}", data=message.encode('utf-8'), timeout=5)
    except Exception as e:
        import sys
        print(f"    [Warning] Failed to send notification: {e}", file=sys.stderr)

