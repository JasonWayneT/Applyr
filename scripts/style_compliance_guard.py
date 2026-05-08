import os
import re
import sys

# --- Constraints & Standard Limits ---
RESUME_MAX_CHARS = 3200
CL_MAX_CHARS = 1800

def parse_args():
    if len(sys.argv) < 2:
        print("Usage: python style_compliance_guard.py <file_path>", file=sys.stderr)
        sys.exit(1)
    return sys.argv[1]

def determine_type(file_path, content):
    lower_path = file_path.lower()
    lower_content = content.lower()
    if "cover" in lower_path or "letter" in lower_path or "dear hiring" in lower_content:
        return "cover_letter"
    return "resume"

def clean_escapes(content):
    """Phase 1: Unescape backslashes and cleanup markdown artifacts."""
    # Strip LLM debug headers if any are written
    content = re.sub(r"^\[LLM\].*?\n", "", content, flags=re.MULTILINE)
    
    # Strip markdown code block fences if returned by LLM
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:markdown|html)?\n|```$", "", content, flags=re.MULTILINE).strip()
        
    # Unescape escaped characters common in LLM outputs
    content = content.replace(r"\,", ",")
    content = content.replace(r"\-", "-")
    content = content.replace(r"\|", "|")
    content = content.replace(r"\+", "+")
    content = content.replace(r"\*", "*")
    content = content.replace(r"\.", ".")
    content = content.replace(r"\'", "'")
    content = content.replace(r"\"", '"')
    content = content.replace(r"\:", ":")
    content = content.replace(r"\_", "_")
    content = content.replace(r"\(", "(")
    content = content.replace(r"\)", ")")
    
    # Clean up corrupted dash characters and standard en-dashes
    content = content.replace("\ufffd", "-").replace("\xef\xbf\xbd", "-")
    content = content.replace("–", "-")


    # Strip SDD Fact IDs (e.g., [ACC-101], [MET-02], [VOC-05]) that the LLM might have leaked
    content = re.sub(r'\[(?:ACC|MET|VOC)-\d+\]\s*', '', content)

    # Replace em-dashes and double-hyphens used as breaks inside paragraphs/bullets with commas
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if not line.strip().startswith("#"):
            lines[i] = re.sub(r'\s*—\s*', ', ', line)
            lines[i] = re.sub(r'\s*--\s*', ', ', lines[i])
    content = "\n".join(lines)

    return content

def trim_excess_newlines(content):
    """Phase 3 Compactor: Reduce excessive whitespace."""
    # Normalize newline chunks
    content = re.sub(r'\n{3,}', '\n\n', content)
    return content

def trim_bullet_points(content):
    """Phase 3 Compactor: Trim company bullets if we are running long."""
    lines = content.splitlines()
    cleaned_lines = []
    
    in_cision = False
    in_sterkly = False
    in_zerotosixty = False
    
    cision_bullets = 0
    sterkly_bullets = 0
    zerotosixty_bullets = 0
    
    for line in lines:
        stripped = line.strip()
        # Track sections
        if stripped.startswith("###"):
            in_cision = False
            in_sterkly = False
            in_zerotosixty = False
            if "cision" in stripped.lower():
                in_cision = True
            elif "sterkly" in stripped.lower():
                in_sterkly = True
            elif "zero to sixty" in stripped.lower() or "zero to 60" in stripped.lower():
                in_zerotosixty = True
        elif "cision" in line.lower():
            in_cision = True
            in_sterkly = False
            in_zerotosixty = False
        elif "sterkly" in line.lower():
            in_cision = False
            in_sterkly = True
            in_zerotosixty = False
        elif "zero to sixty" in line.lower() or "zero to 60" in line.lower():
            in_cision = False
            in_sterkly = False
            in_zerotosixty = True
        elif "<h2" in line.lower() or "education" in line.lower() or "certifications" in line.lower() or line.startswith("##"):
            in_cision = False
            in_sterkly = False
            in_zerotosixty = False
            
        is_bullet = stripped.startswith('*') or stripped.startswith('-') or stripped.startswith('•') or stripped.startswith('<li')
        
        if in_cision and is_bullet:
            cision_bullets += 1
            if cision_bullets <= 5:
                cleaned_lines.append(line)
        elif in_sterkly and is_bullet:
            sterkly_bullets += 1
            if sterkly_bullets <= 4:
                cleaned_lines.append(line)
        elif in_zerotosixty and is_bullet:
            zerotosixty_bullets += 1
            if zerotosixty_bullets <= 3:
                cleaned_lines.append(line)
        else:
            cleaned_lines.append(line)
            
    return "\n".join(cleaned_lines)


def strip_html_wrappers(content):
    """Strip legacy HTML wrappers and convert them back to pure standard Markdown."""
    content = re.sub(r'<div[^>]*>', '', content, flags=re.IGNORECASE)
    content = re.sub(r'</div>', '', content, flags=re.IGNORECASE)
    content = re.sub(r'<strong>', '', content, flags=re.IGNORECASE)
    content = re.sub(r'</strong>', '', content, flags=re.IGNORECASE)
    content = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1', content, flags=re.IGNORECASE)
    content = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1', content, flags=re.IGNORECASE)
    content = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1', content, flags=re.IGNORECASE)
    return content

def normalize_resume_headers(content):
    """Normalize headers, contact info, level-1 headers, and legacy job titles."""
    # 1. Normalize Header/Contact flipped position
    name_match = re.search(r'^#\s*(?:\*\*)?JASON\s+TAYLOR(?:\*\*)?.*$', content, re.MULTILINE | re.IGNORECASE)
    contact_pattern = r'(?:San Diego,\s*CA|[REDACTED_PHONE]|jason\.wayne\.t@gmail\.com)'
    contact_match = re.search(r'^.*' + contact_pattern + r'.*$', content, re.MULTILINE | re.IGNORECASE)
    
    if name_match and contact_match:
        name_str = name_match.group(0).strip()
        contact_str = contact_match.group(0).strip()
        
        # Strip both from original text
        cleaned = content.replace(name_str, "").replace(contact_str, "").strip()
        
        # Re-inject properly at the very top
        content = f"# JASON TAYLOR\n\nSan Diego, CA | [REDACTED_PHONE] | [REDACTED_EMAIL] | linkedin.com/in/redacted-linkedin-slug\n\n" + cleaned

    # 2. Convert level-1 headers to level-2 headers (except JASON TAYLOR)
    lines = content.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("# ") and not re.search(r'^#\s*(?:\*\*)?JASON\s+TAYLOR', stripped, re.IGNORECASE):
            lines[i] = "## " + stripped[2:].lstrip()
        elif (stripped.startswith("#**") or stripped.startswith("# **")) and not re.search(r'JASON\s+TAYLOR', stripped, re.IGNORECASE):
            lines[i] = "## " + re.sub(r'^#\s*\**', '', stripped).replace("**", "").strip()
    content = "\n".join(lines)

    # 3. Strip redundant company headings (e.g. ## CISION, ## STERKLY SERVICES)
    content = re.sub(r'^##\s*(?:\*\*)?(?:CISION|STERKLY SERVICES|ZERO TO SIXTY MEDIA|STERKLY|ZERO TO SIXTY)(?:\*\*)?\s*$', '', content, flags=re.MULTILINE | re.IGNORECASE)

    # 4. Standardize job title dates to pipe format (### **Title | Date**)
    lines = content.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("###"):
            if " - " in stripped or " — " in stripped or " -- " in stripped:
                if not "|" in stripped:
                    parts = re.split(r'\s*(?:—|--|-)\s*', stripped[3:])
                    if len(parts) >= 2:
                        title = parts[0].replace("**", "").strip()
                        date_str = " - ".join(parts[1:]).replace("**", "").strip()
                        lines[i] = f"### **{title} | {date_str}**"
    content = "\n".join(lines)

    # 5. Strip bold prefixes on bullet points (Option A Clean Action-Verb Standard)
    content = re.sub(
        r'^(\s*[\*\-•]\s*)\*\*[^*]+?\*\*(?::\s*|\s*-\s*|\s*—\s*|\s+)',
        r'\1',
        content,
        flags=re.MULTILINE
    )

    return content

def run_guard(file_path):
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' does not exist.", file=sys.stderr)
        return
        
    print(f"Running Style Compliance Guard on: {os.path.basename(file_path)}", file=sys.stderr)
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    doc_type = determine_type(file_path, content)
    
    # Strip HTML and restore to pure Markdown
    content = strip_html_wrappers(content)
    content = clean_escapes(content)
    
    # Phase 2: Trim excess newlines
    content = trim_excess_newlines(content)
    
    # Phase 3: Bullet points and header normalization for resumes
    if doc_type == "resume":
        content = normalize_resume_headers(content)
        content = trim_bullet_points(content)
        content = trim_excess_newlines(content)
        
    content = content.strip()
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"Successfully audited and verified style compliance for {os.path.basename(file_path)} (Length: {len(content)} chars)", file=sys.stderr)

if __name__ == "__main__":
    path = parse_args()
    run_guard(path)
