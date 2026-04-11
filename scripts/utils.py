"""
Shared utilities for the JobAgent pipeline.
Centralizes file I/O, LLM calls with retry logic, and path constants.
"""
import os
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
DB_FILE = os.path.join(DATA_DIR, "job_database.json")
FIT_ENGINE_FILE = os.path.join(RULES_DIR, "job_fit_engine.md")
CLAIM_VERIFIER_FILE = os.path.join(RULES_DIR, "claim_verifier.md")
RESEARCH_CONTRACT_FILE = os.path.join(RULES_DIR, "Research_Packet_Contract.md")
RESUME_MASTER_FILE = os.path.join(DATA_DIR, "Resume.md")
COVER_LETTER_REF_FILE = os.path.join(DATA_DIR, "Cover_Letter_Reference.md")
RESUME_STYLE_REF_FILE = os.path.join(DATA_DIR, "Resume_Style_Reference.md")
NAVIGATOR_FILE = os.path.join(PROJECT_ROOT, "Job_Navigator.html")

# Default LLM model for the pipeline
DEFAULT_MODEL = "gemini-2.5-flash"


def load_file(filepath):
    """Read a text file safely. Returns empty string on failure."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return ""


def call_llm(system_prompt, user_prompt, model=None, temperature=0.2,
             response_mime_type=None, tools=None, max_retries=3):
    """
    Centralized LLM call with rate-limit retry and exponential backoff.
    Returns the stripped text response or empty string on failure.
    """
    if model is None:
        model = DEFAULT_MODEL

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
            response = client.models.generate_content(
                model=model,
                contents=user_prompt,
                config=config
            )
            return response.text.strip()
        except Exception as e:
            err = str(e).lower()
            if any(k in err for k in ["retrydelay", "429", "quota", "exhausted"]):
                wait = 45 * (attempt + 1)
                print(f"  -> Rate limit hit. Waiting {wait}s (retry {attempt+1}/{max_retries})...")
                time.sleep(wait)
            else:
                print(f"LLM Error: {e}")
                return ""
    return ""
