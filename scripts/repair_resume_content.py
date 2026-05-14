"""
repair_resume_content.py

Repair script for existing submissions:
  1. Fix malformed education lines (* | National University → full degree line)
  2. Add missing Cision bullets (ACC-101, ACC-105) to resumes with < 6 Cision bullets
  3. Add missing Sterkly bullet (ACC-203) to resumes with < 4 Sterkly bullets
  4. Add missing Zero To Sixty bullet (ACC-303) to resumes with < 3 Zero To Sixty bullets

Run from the JobAgent project root:
    python scripts/repair_resume_content.py
"""

import os
import re
import sys

SUBMISSIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "submissions")

CANONICAL_BBA = (
    "* **Bachelor of Business Administration, Major in Management** "
    "| National University, San Diego, California, 2019"
)

BAD_EDU_RE = re.compile(r'^\*\s*(?:\|)?\s*National University.*$', re.MULTILINE)

# --- Cision bullets ---
ACC_101_BULLET = (
    "* Mitigated recurring indexing server crashes by implementing proactive storage capacity "
    "monitoring, alerting thresholds, and legal-approved cleanups of stale accounts, reducing "
    "service outages across the platform."
)
ACC_105_BULLET = (
    "* Implemented a rigorous, PTO-adjusted capacity model based on workday-hours per engineer, "
    "using T-shirt sizing with uncertainty bands to manage resource allocations across stability, "
    "compliance, and planned roadmap items."
)
ACC_101_KEYWORDS = ['indexing', 'storage capacity', 'server crash', 'stale account', 'service outage']
ACC_105_KEYWORDS = ['capacity model', 'workday-hour', 't-shirt', 'tshirt', 'headcount reduction', 'sprint planning']

# --- Sterkly bullet ---
ACC_203_BULLET = (
    "* Resolved a critical distribution bottleneck for a macOS security product by developing an "
    "in-house browser extension certificate procurement workflow, eliminating dependency on unreliable "
    "external vendors and saving approximately $100 per certificate."
)
ACC_203_KEYWORDS = ['certificate', 'safari extension', 'macos', 'browser extension', 'revenue bottleneck', 'procurement workflow']

# --- Zero To Sixty bullet ---
ACC_303_BULLET = (
    "* Built the company's first automated prospect onboarding funnel, combining a professional "
    "landing page with a Salesforce integration to eliminate manual account manager overhead and "
    "increase estimated conversion rates by approximately 40%."
)
ACC_303_KEYWORDS = ['landing page', 'conversion', 'funnel', 'educational funnel', '40%']


# --- Section detection helpers ---

CISION_HEADER_RE = re.compile(r'\| Cision \|', re.IGNORECASE)
STERKLY_HEADER_RE = re.compile(r'(?:\| Sterkly|\bSterkly\b)', re.IGNORECASE)
ZEROTOSIXTY_HEADER_RE = re.compile(r'(?:Zero To Sixty|Zero to 60)', re.IGNORECASE)

NEXT_SECTION_RE = re.compile(
    r'^(\*\*Product Manager\*\*|\*\*Product Owner\*\*|\*\*Account Manager\*\*|## )',
    re.MULTILINE,
)


def has_keyword(text, keywords):
    lower = text.lower()
    return any(kw in lower for kw in keywords)


def find_section(lines, header_re):
    """Return the line index of the section header, or -1."""
    for i, line in enumerate(lines):
        if header_re.search(line):
            return i
    return -1


def count_section_bullets(lines, section_start):
    """Count bullet lines (starting with '* ') in a section until the next company/## header."""
    count = 0
    for i in range(section_start + 1, len(lines)):
        line = lines[i].strip()
        if not line:
            continue
        if NEXT_SECTION_RE.match(line) or (line.startswith('##') and 'education' not in line.lower()):
            break
        if line.startswith('* '):
            count += 1
    return count


def find_section_end(lines, section_start):
    """Return the line index where the section's bullets end (exclusive)."""
    for i in range(section_start + 1, len(lines)):
        line = lines[i].strip()
        if not line:
            continue
        if NEXT_SECTION_RE.match(line) or (line.startswith('##') and 'education' not in line.lower() and 'experience' not in line.lower()):
            return i
    return len(lines)


def insert_bullet_after_last(lines, section_start, section_end, bullet):
    """Insert bullet after the last '* ' line in the section."""
    insert_at = section_end
    for i in range(section_end - 1, section_start, -1):
        if lines[i].strip().startswith('* '):
            insert_at = i + 1
            break
    lines.insert(insert_at, bullet)


def repair_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # 1. Fix malformed education line
    content = BAD_EDU_RE.sub(CANONICAL_BBA, content)

    lines = content.splitlines()
    bullets_added = 0

    # 2. Cision bullets (ACC-101, ACC-105)
    cision_start = find_section(lines, CISION_HEADER_RE)
    if cision_start != -1:
        cision_end = find_section_end(lines, cision_start)
        cision_text = '\n'.join(lines[cision_start:cision_end])
        bullet_count = count_section_bullets(lines, cision_start)

        to_add = []
        if not has_keyword(cision_text, ACC_101_KEYWORDS):
            to_add.append(ACC_101_BULLET)
        if not has_keyword(cision_text, ACC_105_KEYWORDS):
            to_add.append(ACC_105_BULLET)

        if to_add and bullet_count < 6:
            for bullet in reversed(to_add):
                insert_bullet_after_last(lines, cision_start, cision_end, bullet)
                cision_end += 1
            bullets_added += len(to_add)

    # Re-detect sections after potential insertions above
    lines_snapshot = list(lines)

    # 3. Sterkly bullet (ACC-203)
    sterkly_start = find_section(lines, STERKLY_HEADER_RE)
    if sterkly_start != -1:
        sterkly_end = find_section_end(lines, sterkly_start)
        sterkly_text = '\n'.join(lines[sterkly_start:sterkly_end])
        bullet_count = count_section_bullets(lines, sterkly_start)

        if not has_keyword(sterkly_text, ACC_203_KEYWORDS) and bullet_count < 4:
            insert_bullet_after_last(lines, sterkly_start, sterkly_end, ACC_203_BULLET)
            bullets_added += 1

    # 4. Zero To Sixty bullet (ACC-303)
    z2s_start = find_section(lines, ZEROTOSIXTY_HEADER_RE)
    if z2s_start != -1:
        z2s_end = find_section_end(lines, z2s_start)
        z2s_text = '\n'.join(lines[z2s_start:z2s_end])
        bullet_count = count_section_bullets(lines, z2s_start)

        if not has_keyword(z2s_text, ACC_303_KEYWORDS) and bullet_count < 3:
            insert_bullet_after_last(lines, z2s_start, z2s_end, ACC_303_BULLET)
            bullets_added += 1

    content = '\n'.join(lines)

    if content != original:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        folder = os.path.basename(os.path.dirname(path))
        print(f"  Repaired [{folder}]: {bullets_added} bullet(s) added")
    else:
        folder = os.path.basename(os.path.dirname(path))
        print(f"  OK (no changes): {folder}")


def main():
    if not os.path.isdir(SUBMISSIONS_DIR):
        print(f"Submissions directory not found: {SUBMISSIONS_DIR}", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning {SUBMISSIONS_DIR} ...\n")
    for folder in sorted(os.listdir(SUBMISSIONS_DIR)):
        resume_path = os.path.join(SUBMISSIONS_DIR, folder, "Resume.md")
        if os.path.isfile(resume_path):
            repair_file(resume_path)

    print("\nDone.")


if __name__ == "__main__":
    main()
