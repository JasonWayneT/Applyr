"""
Shared utilities for the JobAgent pipeline.
Centralizes file I/O, LLM calls with retry logic, and path constants.
"""
import os
import sys
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# --- Path Constants ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS_DIR = os.path.join(PROJECT_ROOT, "jobs")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
AGENT_DIR = os.path.join(PROJECT_ROOT, ".agent")
RULES_DIR = os.path.join(AGENT_DIR, "rules")
SUBMISSIONS_DIR = os.path.join(PROJECT_ROOT, "submissions")
ARCHIVE_DIR = os.path.join(PROJECT_ROOT, "archive")

WORK_EXP_FILE = os.path.join(DATA_DIR, "workExperience.md")
WORK_EXP_SUMMARY_FILE = os.path.join(DATA_DIR, "workExperience_summary.md")
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

# Default LLM model for the pipeline
DEFAULT_MODEL = "gemini-2.5-flash"

# Max JD characters to send to LLM for scoring (token budget gate)
SCORING_JD_MAX_CHARS = 1500

_DEFAULT_JD_KEYWORDS = [
    'saas', 'b2b', 'platform', 'integration', 'enterprise', 'api',
    'product', 'software', 'agile', 'roadmap', 'stakeholder',
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


def load_file(filepath):
    """Read a text file safely. Returns empty string on failure."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}", file=sys.stderr)
        return ""


def load_llm_settings():
    """Reads llm_settings from SQLite profiles table dynamically. Returns dict or empty dict on failure."""
    import sqlite3
    import json
    db_path = os.path.join(PROJECT_ROOT, "jobagent.sqlite")
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


def call_llm(system_prompt, user_prompt, model=None, temperature=0.2,
             response_mime_type=None, tools=None, max_retries=5):
    """
    Centralized LLM call supporting Google Gemini, Anthropic Claude,
    and Local OpenAI-compatible models (Ollama / LM Studio) dynamically routed from DB settings.
    """
    settings = load_llm_settings()
    provider = settings.get("provider", "gemini")

    if provider == "gemini":
        api_key = settings.get("geminiApiKey") or os.getenv("GEMINI_API_KEY")
        local_client = client
        if api_key and api_key != os.getenv("GEMINI_API_KEY"):
            try:
                local_client = genai.Client(api_key=api_key)
            except Exception as e:
                print(f"    [LLM Error] Failed to initialize Gemini Client with settings key: {e}", file=sys.stderr)

        if model is None:
            model = DEFAULT_MODEL
            
        print(f"    [LLM] Calling Gemini: {model}...", file=sys.stderr)
        for attempt in range(max_retries):
            try:
                config_kwargs = {
                    "system_instruction": system_prompt,
                    "temperature": temperature
                }
                if response_mime_type:
                    config_kwargs["response_mime_type"] = response_mime_type
                if tools:
                    config_kwargs["tools"] = tools

                config = types.GenerateContentConfig(**config_kwargs)
                response = local_client.models.generate_content(
                    model=model,
                    contents=user_prompt,
                    config=config
                )
                return (response.text or "").strip()
            except Exception as e:
                err = str(e).lower()
                if any(k in err for k in ["retrydelay", "429", "quota", "exhausted", "503", "unavailable"]):
                    wait = 60 * (attempt + 1)
                    print(f"  -> Rate limit hit. Waiting {wait}s...", file=sys.stderr)
                    time.sleep(wait)
                else:
                    print(f"    [LLM Error] {e}", file=sys.stderr)
                    break
        return ""

    elif provider == "claude":
        import requests
        import json
        api_key = settings.get("claudeApiKey") or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("    [LLM Error] Anthropic API Key not set.", file=sys.stderr)
            return ""
        
        target_model = model or "claude-3-5-sonnet-20241022"
        print(f"    [LLM] Calling Claude: {target_model}...", file=sys.stderr)
        
        for attempt in range(max_retries):
            try:
                headers = {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                }
                payload = {
                    "model": target_model,
                    "max_tokens": 4000,
                    "temperature": temperature,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}]
                }
                res = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return data["content"][0]["text"].strip()
                elif res.status_code == 429:
                    wait = 60 * (attempt + 1)
                    print(f"  -> Claude rate limit hit. Waiting {wait}s...", file=sys.stderr)
                    time.sleep(wait)
                else:
                    print(f"    [LLM Error] Claude returned status {res.status_code}: {res.text}", file=sys.stderr)
                    break
            except Exception as e:
                print(f"    [LLM Error] {e}", file=sys.stderr)
                break
        return ""

    elif provider == "local":
        import requests
        import json
        base_url = settings.get("localUrl", "http://localhost:11434")
        target_model = settings.get("localModel") or model or "llama3"
        print(f"    [LLM] Calling Local LLM ({base_url}) Model: {target_model}...", file=sys.stderr)
        
        endpoint = base_url.rstrip("/")
        if not endpoint.endswith("/v1") and not endpoint.endswith("/v1/chat/completions"):
            endpoint = f"{endpoint}/v1/chat/completions"
        elif endpoint.endswith("/v1"):
            endpoint = f"{endpoint}/chat/completions"
            
        try:
            payload = {
                "model": target_model,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            }
            res = requests.post(endpoint, json=payload, timeout=120)
            if res.status_code == 200:
                data = res.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                ollama_endpoint = base_url.rstrip("/") + "/api/chat"
                payload_ollama = {
                    "model": target_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "options": {"temperature": temperature},
                    "stream": False
                }
                res_ollama = requests.post(ollama_endpoint, json=payload_ollama, timeout=120)
                if res_ollama.status_code == 200:
                    return res_ollama.json()["message"]["content"].strip()
                print(f"    [LLM Error] Local LLM failed: OpenAI v1 status {res.status_code}, Ollama status {res_ollama.status_code}", file=sys.stderr)
        except Exception as e:
            print(f"    [LLM Error] Failed to connect to local LLM: {e}", file=sys.stderr)
        return ""
