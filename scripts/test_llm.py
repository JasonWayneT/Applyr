"""Quick Gemini connectivity check — reads key from jobagent.sqlite (Settings UI)."""
from utils import load_llm_settings

settings = load_llm_settings()
api_key = settings.get("geminiApiKey") or ""
print("Gemini key configured:", bool(api_key))
print("Gemini key length:", len(api_key))

if not api_key:
    raise SystemExit("No geminiApiKey in profiles/llm_settings — add one in Settings → API or Connections.")

from google import genai

client = genai.Client(api_key=api_key)
response = client.models.generate_content(
    model="gemini-2.5-flash-lite",
    contents="Reply with exactly: OK",
)
print("Response:", (response.text or "").strip())
