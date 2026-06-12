import re

def redact_pii(text: str) -> str:
    """
    Local PII Redaction Guard via Regex.
    Strips common Personal Identifiable Information (Phone, Email, SSN) 
    before sending data to external APIs if needed.
    """
    if not text:
        return text

    # Redact Emails
    text = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '[REDACTED_EMAIL]', text)
    
    # Redact Phone Numbers (US formats: 123-456-7890, (123) 456-7890, etc.)
    text = re.sub(r'(?:\+?1[-.●]?)?\(?([0-9]{3})\)?[-.●\s]?([0-9]{3})[-.●\s]?([0-9]{4})', '[REDACTED_PHONE]', text)
    
    # Redact SSN
    text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[REDACTED_SSN]', text)
    
    return text

if __name__ == "__main__":
    sample = "Contact me at user@example.com or call (555) 019-9238."
    print("Original:", sample)
    print("Redacted:", redact_pii(sample))
