import os
import json
import time
import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

def fetch_company_intel_perplexity(company, role, prompt):
    if not PERPLEXITY_API_KEY:
        raise ValueError("Perplexity API Key not found.")

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
        "temperature": 0.2
    }
    
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }

    print(f"Fetching intelligence for {company} - {role} using Perplexity...")
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()

    raw_content = response.json()['choices'][0]['message']['content']
    clean_json = raw_content.replace('```json', '').replace('```', '').strip()
    json.loads(clean_json) # validate
    return clean_json

def fetch_company_intel_gemini(company, role, prompt):
    print(f"Fetching intelligence for {company} - {role} using Gemini Search...")
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = gemini_client.models.generate_content(
                model='gemini-2.5-pro',
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction="You are a corporate intelligence agent. Return output in VALID JSON format ONLY. Do not include markdown code blocks like ```json in your response. Ensure the output is strictly valid JSON.",
                    tools=[{"google_search": {}}],
                    temperature=0.2
                )
            )
            raw_content = response.text
            clean_json = raw_content.replace('```json', '').replace('```', '').strip()
            # Test JSON validity
            json.loads(clean_json)
            return clean_json
        except Exception as e:
            err_str = str(e)
            if "retryDelay" in err_str or "429" in err_str or "quota" in err_str.lower() or "exhausted" in err_str.lower():
                print(f"    -> LLM Rate limit hit. Waiting 45s before retry {attempt+1}/{max_retries}...")
                time.sleep(45)
            else:
                print(f"Error fetching intelligence: {e}")
                import traceback
                traceback.print_exc()
                if attempt == max_retries - 1:
                    return "{}"
                time.sleep(10)

def fetch_company_intel(company, role, contract_path):
    with open(contract_path, 'r', encoding='utf-8') as f:
        contract = f.read()

    prompt = f"""
    Using the following Research Packet Contract:
    {contract}
    
    Conduct a deep dive/web search into {company} for the {role} position.
    Provide a structured JSON response following the contract modules (A-F).
    Ensure all factual claims include a URL source.
    """

    try:
        return fetch_company_intel_perplexity(company, role, prompt)
    except Exception as e:
        print(f"Perplexity failed: {e}. Falling back to 'in-house' Gemini.")
        return fetch_company_intel_gemini(company, role, prompt)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python research_engine.py 'Company Name' 'Role Title'")
        sys.exit(1)

    company_name = sys.argv[1]
    role_title = sys.argv[2]
    contract = ".agent/rules/Research_Packet_Contract.md"
    
    try:
        result = fetch_company_intel(company_name, role_title, contract)
        
        folder = f"submissions/{company_name.lower().replace(' ', '_')}"
        os.makedirs(folder, exist_ok=True)
        out_path = f"{folder}/Research_Packet.json"
        
        print(f"Saving intelligence to {out_path}...")
        with open(out_path, "w", encoding='utf-8') as f:
            f.write(result)
        print("Done.")
        
    except Exception as e:
        print(f"An error occurred during research: {e}")