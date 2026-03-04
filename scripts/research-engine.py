import os
import json
import requests
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# Access the key securely from environment
API_KEY = os.getenv("PERPLEXITY_API_KEY")

def fetch_company_intel(company, role, contract_path):
    if not API_KEY:
        raise ValueError("API Key not found. Ensure it is set in your .env file.")

    url = "https://api.perplexity.ai/chat/completions"
    
    # Load your contract to ensure the prompt matches your requirements
    with open(contract_path, 'r') as f:
        contract = f.read()

    prompt = f"""
    Using the following Research Packet Contract:
    {contract}
    
    Conduct a deep dive into {company} for the {role} position.
    Provide a structured JSON response following the contract modules (A-F).
    Ensure all factual claims include a URL source.
    """

    payload = {
        "model": "sonar-pro", 
        "messages": [
            {
                "role": "system", 
                "content": "You are a corporate intelligence agent. Return output in VALID JSON format ONLY. Do not include markdown code blocks like ```json in your response."
            },
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2 # Lower temperature prevents "creative" hallucinations
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    print(f"Fetching intelligence for {company} - {role}...")
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code != 200:
        print(f"Error {response.status_code}: {response.text}")
        response.raise_for_status()

    # Get raw content and strip out any markdown code blocks the AI might add
    raw_content = response.json()['choices'][0]['message']['content']
    clean_json = raw_content.replace('```json', '').replace('```', '').strip()
    
    return clean_json

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
        
        # Save to the specific submission folder
        folder = f"submissions/{company_name.lower().replace(' ', '_')}"
        os.makedirs(folder, exist_ok=True)
        out_path = f"{folder}/Research_Packet.json"
        
        print(f"Saving intelligence to {out_path}...")
        with open(out_path, "w") as f:
            f.write(result)
        print("Done.")
        
    except Exception as e:
        print(f"An error occurred during research: {e}")