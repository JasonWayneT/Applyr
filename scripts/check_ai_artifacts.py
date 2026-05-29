import json

def check_ai_artifacts():
    with open('data/master_claims.json', 'r', encoding='utf-8') as f:
        claims = json.load(f)

    # 1. Em-dashes
    em_dashes = ['—', '--', ' - ']
    
    # 2. Transition Fluff (starts of sentences or words)
    transitions = ['furthermore', 'moreover', 'in addition', 'additionally', 'in conclusion']
    
    # 3. Vibe Words
    vibe_words = ['passionate', 'driven', 'dynamic', 'innovative', 'leverage', 'synergy', 'transformative', 'testament']
    
    errors = []
    
    for cid, claim in claims.items():
        text = claim.get('text', '')
        text_lower = text.lower()
        
        # Check Em dashes
        for dash in em_dashes:
            if dash in text:
                errors.append(f"[{cid}] Em-dash found: {dash}")
                
        # Check transitions
        for trans in transitions:
            if text_lower.startswith(trans) or f" {trans}" in text_lower:
                errors.append(f"[{cid}] Transition fluff found: {trans}")
                
        # Check vibe words
        for vibe in vibe_words:
            # check as word boundary
            import re
            if re.search(r'\b' + vibe + r'\b', text_lower):
                errors.append(f"[{cid}] Vibe word found: {vibe}")
                
    if errors:
        print("Found AI Artifacts:")
        for e in errors:
            print(" - " + e)
    else:
        print("No AI artifacts found!")

if __name__ == "__main__":
    check_ai_artifacts()
