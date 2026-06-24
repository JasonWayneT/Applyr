import html
import re

def clean_html_to_text(raw_html: str) -> str:
    """
    DOM Cleanup Pre-Processor for JDs.
    Removes garbage HTML code, invisible trackers, and formatting noise
    out of scraped job postings before the AI reads them.
    """
    if not raw_html:
        return ""

    # Decode HTML entities first so that entity-encoded HTML (e.g. &lt;p&gt;)
    # is converted to real tags before the tag-stripping regexes run.
    text = html.unescape(raw_html)

    # Remove script and style tags and their contents
    text = re.sub(r'<(script|style).*?>.*?</\1>', '', text, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove hidden elements (e.g., style="display:none")
    text = re.sub(r'<[^>]*style=["\'][^"\']*display:\s*none[^"\']*["\'][^>]*>.*?</[^>]+>', '', text, flags=re.IGNORECASE | re.DOTALL)
    
    # Replace common block elements with newlines for readability
    text = re.sub(r'<(div|p|br|li|h[1-6]).*?>', '\n', text, flags=re.IGNORECASE)
    
    # Remove all remaining HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # Normalize whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    return text.strip()

if __name__ == "__main__":
    pass
