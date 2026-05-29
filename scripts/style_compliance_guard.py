import os
import re
import sys

# --- Constraints & Standard Limits ---
RESUME_MAX_CHARS = 3200
CL_MAX_CHARS = 1800

# Sections that must NEVER appear in a final resume output.
# The allowed set is: PROFESSIONAL SUMMARY, PROFESSIONAL EXPERIENCE, EDUCATION.
_FORBIDDEN_SECTION_RE = re.compile(
    r'^#{1,3}\s*(?:\*\*)?(?:'
    r'Core\s+Competencies|Technical\s+Skills?\s*(?:&|and)?\s*Tools?|Technical\s+Proficiencies?|'
    r'Key\s+Projects?(?:\s*(?:&|and)\s*Achievements?)?|Projects?\s*(?:&|and)\s*Achievements?|'
    r'Key\s+Achievements?\s+(?:&|and)\s+Impact(?:\s+Summary)?|Key\s+Achievements?|'
    r'Skills?\s*(?:&|and)\s*Tools?|Technical\s+Environment|Core\s+Expertise|'
    r'Additional\s+Information|Summary\s+of\s+Qualifications?|Highlights?'
    r')(?:\*\*)?\s*$',
    re.IGNORECASE,
)

# Any ## header resets the "skip" flag (so we re-evaluate each section)
_RESUME_SECTION_BOUNDARY_RE = re.compile(r'^##\s', re.IGNORECASE)


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

    # Clean up corrupted dash characters
    content = content.replace("�", "-").replace("\xef\xbf\xbd", "-")
    # Normalize en-dashes in non-header lines to hyphens
    content = content.replace("–", "-")

    # Strip SDD Fact IDs (e.g., [ACC-101], [MET-02], [VOC-05]) that the LLM might have leaked
    content = re.sub(r'\[(?:ACC|MET|VOC)-\d+\]\s*', '', content)

    # Replace em-dashes and double-hyphens used inside paragraphs/bullets with commas
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if not line.strip().startswith("#"):
            lines[i] = re.sub(r'\s*—\s*', ', ', line)
            lines[i] = re.sub(r'\s*--\s*', ', ', lines[i])
    content = "\n".join(lines)

    # Remove artifact-only lines: lines that contain nothing meaningful after unescaping
    # e.g. ", -" or "* -" or "---" that appear as LLM-generated dividers
    content = re.sub(r'(?m)^[\s,\-\*|•]+$', '', content)

    return content


def strip_forbidden_sections(content: str) -> str:  # Implements FR-074
    """
    Remove sections that are not allowed in a final resume.
    Allowed ## sections: PROFESSIONAL SUMMARY, PROFESSIONAL EXPERIENCE, EDUCATION.
    Everything else (Core Competencies, Technical Skills, Key Projects, etc.) is stripped
    along with all of its bullet content, up to the next ## section boundary.
    """
    lines = content.splitlines(keepends=True)
    result = []
    in_forbidden = False

    for line in lines:
        stripped = line.rstrip('\n\r')
        if _FORBIDDEN_SECTION_RE.match(stripped):
            in_forbidden = True
            continue
        if in_forbidden:
            # A ## header (but not ###) ends the forbidden block
            if _RESUME_SECTION_BOUNDARY_RE.match(stripped):
                in_forbidden = False
                result.append(line)
            # ### sub-headers and content lines inside the forbidden block are dropped
        else:
            result.append(line)

    return ''.join(result)


def trim_excess_newlines(content):
    """Phase 3 Compactor: Reduce excessive whitespace."""
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
        elif "<h2" in line.lower() or "education" in line.lower() or line.startswith("##"):
            in_cision = False
            in_sterkly = False
            in_zerotosixty = False

        is_bullet = (stripped.startswith('* ') or stripped.startswith('- ') or stripped.startswith('• ') or stripped.startswith('<li') or stripped == '*' or stripped == '-')

        if in_cision and is_bullet:
            cision_bullets += 1
            if cision_bullets <= 6:
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


_CANONICAL_BBA = (
    "* **Bachelor of Business Administration, Major in Management** "
    "| National University, San Diego, California, 2019"
)

_BAD_EDU_RE = re.compile(
    r'^\*\s*(?:\|)?\s*National University.*$',
    re.MULTILINE,
)


def normalize_education_section(content: str) -> str:
    """Ensure the education bullet always contains the full degree text.

    Fixes truncated lines like '* | National University...' left behind when
    the degree-text prefix was accidentally stripped by a prior sed pass.
    """
    return _BAD_EDU_RE.sub(_CANONICAL_BBA, content)


_AI_FINGERPRINT_TRANSITIONS = re.compile(
    r'\b(furthermore|moreover|additionally),?\s*',
    re.IGNORECASE,
)

_AI_FINGERPRINT_WORDS = {
    'synergy': 'collaboration',
    'synergies': 'collaboration',
    'leverage': 'use',
    'leveraging': 'using',
    'leveraged': 'used',
    'passionate': 'dedicated',
    'passionately': 'dedicatedly',
}


def remove_ai_fingerprints(content: str) -> str:
    """Strip transition filler words and replace AI-signature vocabulary."""
    content = _AI_FINGERPRINT_TRANSITIONS.sub('', content)
    for bad, good in _AI_FINGERPRINT_WORDS.items():
        content = re.sub(rf'\b{bad}\b', good, content, flags=re.IGNORECASE)
    return content


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
    # 1. Find the name line — accept #, ##, ### or bold-only variants
    name_match = re.search(
        r'^(?:#{1,3}\s*)?(?:\*\*)?JASON\s+TAYLOR(?:\*\*)?.*$',
        content,
        re.MULTILINE | re.IGNORECASE,
    )
    contact_pattern = r'(?:San Diego,\s*CA|[REDACTED_PHONE]|jason\.wayne\.t@gmail\.com)'
    contact_match = re.search(r'^.*' + contact_pattern + r'.*$', content, re.MULTILINE | re.IGNORECASE)

    if name_match and contact_match:
        name_str = name_match.group(0).strip()
        contact_str = contact_match.group(0).strip()

        # Strip both occurrences from original text (replace ALL to catch duplicates)
        cleaned = content.replace(name_str, "").replace(contact_str, "").strip()

        # Also strip any remaining orphaned contact-like lines (duplicates after placeholder healing)
        cleaned = re.sub(
            r'(?m)^(?:San Diego,\s*CA\s*\|?\s*)?[REDACTED_PHONE].*linkedin\.com.*$\n?', '', cleaned
        )

        # Re-inject correctly at the very top
        content = (
            "# JASON TAYLOR\n\n"
            "San Diego, CA | [REDACTED_PHONE] | [REDACTED_EMAIL] | linkedin.com/in/redacted-linkedin-slug\n\n"
            + cleaned
        )

    # 2. Convert any remaining ##+ headers to ## (except JASON TAYLOR which must stay #)
    lines = content.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("# ") and not re.search(r'^#\s*(?:\*\*)?JASON\s+TAYLOR', stripped, re.IGNORECASE):
            lines[i] = "## " + stripped[2:].lstrip()
        elif (stripped.startswith("#**") or stripped.startswith("# **")) and not re.search(r'JASON\s+TAYLOR', stripped, re.IGNORECASE):
            lines[i] = "## " + re.sub(r'^#\s*\**', '', stripped).replace("**", "").strip()
    content = "\n".join(lines)

    # 3. Strip redundant standalone company headings (e.g. ## CISION, ## STERKLY SERVICES)
    content = re.sub(
        r'^##\s*(?:\*\*)?(?:CISION|STERKLY SERVICES|ZERO TO SIXTY MEDIA|STERKLY|ZERO TO SIXTY)(?:\*\*)?\s*$',
        '',
        content,
        flags=re.MULTILINE | re.IGNORECASE,
    )

    # 4. Standardize job title dates to pipe format (### **Title | Date**)
    lines = content.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("###"):
            if " - " in stripped or " — " in stripped or " -- " in stripped:
                if "|" not in stripped:
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
        flags=re.MULTILINE,
    )

    return content


_PLACEHOLDER_RE = re.compile(r'\[(?:[A-Z][A-Za-z0-9\s/&,\-]{1,40})\]')


def strip_placeholders(content: str) -> str:
    """Remove unfilled template tokens like [Position Overview], [JD], [Your City, State]."""
    found = _PLACEHOLDER_RE.findall(content)
    if found:
        content = _PLACEHOLDER_RE.sub('', content)
        content = re.sub(r'  +', ' ', content)
        for token in found:
            print(f"  [GUARD] Stripped placeholder: {token}", file=sys.stderr)
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
    content = remove_ai_fingerprints(content)

    from tone_guard import sanitize_submission_tone

    content = sanitize_submission_tone(content)

    # Strip unfilled template placeholders (applies to all doc types)
    content = strip_placeholders(content)

    # Phase 2: Trim excess newlines
    content = trim_excess_newlines(content)

    # Phase 3: Resume-specific normalization
    if doc_type == "resume":
        content = strip_forbidden_sections(content)
        content = normalize_resume_headers(content)
        content = normalize_education_section(content)
        content = trim_bullet_points(content)
        content = trim_excess_newlines(content)

    # Strip education/certification sections from cover letters — they don't belong
    if doc_type == "cover_letter":
        content = re.sub(
            r'\n+##\s+EDUCATION.*$',
            '',
            content,
            flags=re.IGNORECASE | re.DOTALL,
        )

    content = content.strip()

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(
        f"Successfully audited and verified style compliance for "
        f"{os.path.basename(file_path)} (Length: {len(content)} chars)",
        file=sys.stderr,
    )


if __name__ == "__main__":
    path = parse_args()
    run_guard(path)
