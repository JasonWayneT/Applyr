import os
from dotenv import load_dotenv
from google import genai
load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
print("Gemini key length:", len(os.getenv("GEMINI_API_KEY") or ""))

try:
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="Hello! Say 'Yes, the API key works' if you receive this."
    )
    print("Response gemini-2.0-flash:", response.text)
except Exception as e:
    print("Error during test call gemini-2.0-flash:", e)

try:
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents="Hello! Say 'Yes, the API key works' if you receive this."
    )
    print("Response gemini-1.5-flash:", response.text)
except Exception as e:
    print("Error during test call gemini-1.5-flash:", e)
