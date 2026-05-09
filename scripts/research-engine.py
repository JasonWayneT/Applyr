import os
import json
import requests
from utils import load_file, call_llm, load_llm_settings, _is_configured, SUBMISSIONS_DIR, RESEARCH_CONTRACT_FILE
from dotenv import load_dotenv

load_dotenv()


# Implements FR-061: Perplexity key read dynamically from llm_settings, not module-level env
def fetch_company_intel_perplexity(company, role, prompt, settings=None):
    if settings is None:
        settings = load_llm_settings()
    api_key = settings.get('perplexityApiKey') or os.getenv('PERPLEXITY_API_KEY')
    if not api_key:
        raise ValueError("Perplexity API Key not configured.")

    url = "https://api.perplexity.ai/chat/completions"
    payload = {
        "model": "sonar-pro",
        "messages": [
            {
                "role": "system",
                "content": "You are a corporate intelligence agent. Return output in VALID JSON format ONLY. Do not include markdown code blocks like ```json in your response."
            },
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    print(f"Fetching intelligence for {company} - {role} using Perplexity...")
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()

    raw_content = response.json()['choices'][0]['message']['content']
    clean_json = raw_content.replace('```json', '').replace('```', '').strip()
    json.loads(clean_json)  # validate
    return clean_json


def fetch_company_intel_gemini(company, role, prompt):
    print(f"Fetching intelligence for {company} - {role} using Gemini 2.5 Flash Search...")

    result = call_llm(
        system_prompt="You are a corporate intelligence agent. Return output in VALID JSON format ONLY. Do not include markdown code blocks like ```json in your response. Ensure the output is strictly valid JSON.",
        user_prompt=prompt,
        model="gemini-2.5-flash",
        temperature=0.2,
        tools=[{"google_search": {}}]
    )

    if not result:
        return "{}"

    clean_json = result.replace('```json', '').replace('```', '').strip()
    json.loads(clean_json)  # validate
    return clean_json


def fetch_company_intel(company, role, contract_path=None):
    if contract_path is None:
        contract_path = RESEARCH_CONTRACT_FILE

    contract = load_file(contract_path)
    prompt = f"""
    Using the following Research Packet Contract:
    {contract}

    Conduct a deep dive/web search into {company} for the {role} position.
    Provide a structured JSON response following the contract modules (A-F).
    Ensure all factual claims include a URL source.
    """

    # Implements FR-061: try Perplexity first (native web retrieval), fall back to primary LLM
    settings = load_llm_settings()
    if _is_configured('perplexity', settings):
        try:
            return fetch_company_intel_perplexity(company, role, prompt, settings)
        except Exception as e:
            print(f"Perplexity research failed ({e}), falling back to primary LLM...", file=sys.stderr)

    return fetch_company_intel_gemini(company, role, prompt)



if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python research-engine.py 'Company Name' 'Role Title'")
        sys.exit(1)

    company_name = sys.argv[1]
    role_title = sys.argv[2]

    try:
        result = fetch_company_intel(company_name, role_title)

        folder = os.path.join(SUBMISSIONS_DIR, company_name.lower().replace(' ', '_'))
        os.makedirs(folder, exist_ok=True)
        out_path = os.path.join(folder, "Research_Packet.json")

        print(f"Saving intelligence to {out_path}...")
        with open(out_path, "w", encoding='utf-8') as f:
            f.write(result)
        print("Done.")

    except Exception as e:
        print(f"An error occurred during research: {e}")