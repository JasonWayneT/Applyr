import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils import call_llm, load_llm_settings

def test_local_llm():
    print("Loading settings verify...")
    settings = load_llm_settings()
    print(f"Settings state: {settings}")
    
    print("\nTesting Local LLM availability via call_llm()...")
    system_prompt = "You are a helpful assistant. Respond in brief JSON."
    user_prompt = "Return {'status': 'ok'} as json."
    
    try:
        result = call_llm(
            system_prompt=system_prompt, 
            user_prompt=user_prompt,
            temperature=0.1
        )
        print("\n--- LLM Response ---")
        print(result)
        print("--------------------")
    except Exception as e:
        print(f"CRITICAL FAILURE calling local model: {e}")

if __name__ == "__main__":
    test_local_llm()
