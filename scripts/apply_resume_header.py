"""
Deterministic header substitution for freshly-authored Resume.md/CoverLetter.md.

Why this exists (2026-08-07): the CR-074 closed-world authoring packet has no field for
name/contact/location -- confirmed by inspecting authoring_packet.json's schema directly, it simply
isn't there. data/authoring_rule_digest.md's own "Required Document Structure" example shows the
header as a literal placeholder ("# [Name]" / "[contact line]"), not real data. A closed-world
compose agent given only packet+digest has no way to know Jason's real contact info, and correctly
should not invent it -- but a real submission needs the real header. The header is identical,
non-JD-specific text every single time (name, phone, email, LinkedIn, location never change), which
makes it exactly the kind of thing that should be a deterministic substitution, not something asked
of a cloud LLM: it removes the reliability gap (a placeholder-only draft) AND avoids sending Jason's
real contact PII into a cloud authoring call for no benefit, since the value there is zero -- the
header carries no reasoning content an LLM needs to produce.

Source of truth: data/workExperience.md Section 1.0 (gitignored, real PII, never committed).
Location and the degree line are read from the same file's Education line (Section 2.x) since 1.0
has no explicit location field today -- see NOTE below if that ever changes.

Same reasoning extends to the resume's ## EDUCATION line (found 2026-08-07, same authoring pass
that found the header gap): it's identical, non-JD-specific text every time -- a closed-world agent
correctly left it as "[Degree] -- [Institution]" rather than invent it, which then trips the
forbidden-em-dash linter rule on a placeholder that was never real content to begin with.

Usage:
    python scripts/apply_resume_header.py data/submissions/{company} [...]
        Replaces a placeholder header (first two lines matching the known bracket patterns) and a
        placeholder ## EDUCATION line with the real ones in Resume.md (CoverLetter.md gets the header
        patch only -- it has no education section). Idempotent: content that already looks real (no
        bracket placeholder) is left untouched -- this script only ever replaces a confirmed
        placeholder, never guesses whether existing content is "wrong."
"""
from __future__ import annotations

import os
import re
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)
_WORK_EXPERIENCE_PATH = os.path.join(_REPO_ROOT, "data", "workExperience.md")

# Matches the placeholder shapes seen in practice: "[Full Name]" / "[Name]" on line 1,
# and a contact line built from some combination of [Email]/[Phone]/[Location]/[LinkedIn]
# brackets on line 2, in any order/separator -- both lines are only ever fully bracketed
# placeholders in this failure mode, never partially real.
_PLACEHOLDER_LINE1 = re.compile(r"^#\s*\[(Full Name|Name)\]\s*$")
_PLACEHOLDER_LINE2 = re.compile(r"^(\[[A-Za-z ]+\]\s*(\|\s*)?)+$")
_EDUCATION_HEADING = re.compile(r"^##\s*EDUCATION\s*$")
_PLACEHOLDER_EDU_LINE = re.compile(r"\[")  # any bracket on the line right after the heading
# ### [Title] | {Company} | [Start Date] - [End Date]
# CORRECTED 2026-08-07 (Jason-supplied): titles here are NOT a per-JD judgment call. That was a
# real conflation on the first pass -- CLAUDE.md's title-mirroring rule governs the resume
# SUMMARY's *optional bolded subtitle* (e.g. camunda's "**Senior Product Manager | Technical
# Platform Products**"), not the Professional Experience section's actual job-title history. An
# LLM must never invent or vary Jason's real historical titles -- they're exactly as static as the
# company names and dates, so all three get mechanized here. Never "B2B SaaS Product Manager" in
# either place: as a Professional Experience title it was simply never real, and as the summary
# subtitle it's a bad signal when the JD isn't actually B2B-SaaS-framed (e.g. a Data PM role) --
# that second failure mode is the compose agent's job to avoid, not this script's (see the summary
# subtitle check during rubric review).
_ROLE_TITLES = {
    "Cision": "Product Manager",
    "Sterkly": "Product Manager / Product Owner",
    "Zero To Sixty": "Account Manager / Product Owner",
}
_ROLE_DATES = {
    "Cision": "September 2021 - January 2026",
    "Sterkly": "February 2019 - August 2021",
    "Zero To Sixty": "June 2017 - January 2019",
}
_PLACEHOLDER_TITLE = re.compile(r"^###\s*\[Title\]\s*\|")
_PLACEHOLDER_COMPANY = re.compile(r"\[Company\]")
# CLAUDE.md's Required Document Structure fixes this order always: Cision, then Sterkly, then
# Zero To Sixty -- used as a positional fallback when a run also left [Company] as a placeholder
# (found 2026-08-07, caylent's run: the packet apparently never surfaces the company name as a
# literal string for every packet, so the compose agent had nothing to NOT-invent from and
# bracketed the company too, same closed-world discipline as the other fields).
_ROLE_ORDER = ["Cision", "Sterkly", "Zero To Sixty"]
# Different closed-world runs phrase this placeholder differently ("[Start Date] - [End Date]"
# vs "[Start] - [End]", found 2026-08-07 comparing amplify's run to camunda's) -- match any
# bracketed "start"/"end"-ish span rather than one exact literal wording.
_PLACEHOLDER_DATE_SPAN = re.compile(r"\[Start[^\]]*\]\s*-\s*\[End[^\]]*\]")
_PLACEHOLDER_SIGNOFF = re.compile(r"^\[(Full Name|Name)\]\s*$")
# authoring_rule_digest.md's own Required Document Structure template shows a per-role
# "[Location]" line (faithfully copied from CLAUDE.md's example) that no real resume checked
# (e.g. camunda) actually contains, and verify_submission.py's corrupted-placeholder check does
# not even detect it -- a real discrepancy between the documented template and actual convention,
# flagged for Jason, not resolved here. Pragmatic fix: strip the line, matching real precedent,
# rather than invent a per-role location value that was never part of the real structure.
_PLACEHOLDER_ROLE_LOCATION = re.compile(r"^\[Location\]\s*$")


def load_real_header() -> dict:
    """Parse Name/Email/Phone/LinkedIn from workExperience.md Section 1.0, and location from
    its Education line. Raises RuntimeError if workExperience.md is missing (never fall back to
    a placeholder or guessed value for real PII)."""
    if not os.path.exists(_WORK_EXPERIENCE_PATH):
        raise RuntimeError(
            "data/workExperience.md not found -- this is the only source of truth for the real "
            "header; refusing to guess or fall back to a placeholder."
        )
    text = open(_WORK_EXPERIENCE_PATH, encoding="utf-8").read()

    def _field(label: str) -> str:
        m = re.search(rf"^- {re.escape(label)}:\s*(.+)$", text, re.MULTILINE)
        if not m:
            raise RuntimeError(f"workExperience.md Section 1.0: '{label}' field not found")
        return m.group(1).strip()

    name = _field("Name")
    email = _field("Email")
    phone = _field("Phone")
    linkedin_raw = _field("LinkedIn")
    # Strip protocol/trailing slash to match the short form real resumes already use
    # (e.g. "linkedin.com/in/username", not "https://www.linkedin.com/in/username/")
    linkedin = re.sub(r"^https?://(www\.)?", "", linkedin_raw).rstrip("/")

    edu_match = re.search(
        r"\*\*([^*]+)\*\*\s*—\s*([^,]+,\s*San Diego,\s*California,\s*\d{4})", text
    )
    if not edu_match:
        raise RuntimeError(
            "Could not derive the education line from workExperience.md -- "
            "check the file hasn't changed shape before hardcoding a fallback."
        )
    location = "San Diego, CA"
    # Real resumes use a comma, not the source doc's em dash (LR-006 forbids em dashes).
    education_line = f"{edu_match.group(1).strip()}, {edu_match.group(2).strip()}"

    return {
        "name": name, "email": email, "phone": phone, "linkedin": linkedin,
        "location": location, "education_line": education_line,
    }


def real_header_lines(h: dict) -> tuple[str, str]:
    return (
        f"# {h['name']}",
        f"{h['location']} | {h['phone']} | {h['email']} | {h['linkedin']}",
    )


def patch_file(path: str, h: dict) -> str:
    """Returns a comma-joined summary of what was patched, or 'skipped (...)' reasons."""
    if not os.path.exists(path):
        return "skipped (file not found)"
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    actions = []

    if len(lines) >= 2:
        l1, l2 = lines[0].rstrip("\n"), lines[1].rstrip("\n")
        if _PLACEHOLDER_LINE1.match(l1) and _PLACEHOLDER_LINE2.match(l2):
            new1, new2 = real_header_lines(h)
            lines[0] = new1 + "\n"
            lines[1] = new2 + "\n"
            actions.append("header")

    for i, line in enumerate(lines):
        if _EDUCATION_HEADING.match(line.rstrip("\n")):
            # Real line is usually right after the heading, possibly with one blank line between.
            for j in (i + 1, i + 2):
                if j < len(lines) and _PLACEHOLDER_EDU_LINE.search(lines[j]):
                    lines[j] = h["education_line"] + "\n"
                    actions.append("education")
                    break
            break

    titles_patched = 0
    companies_patched = 0
    dates_patched = 0
    role_line_idx = 0
    for i, line in enumerate(lines):
        if not line.startswith("### "):
            continue
        company = None
        for c in _ROLE_TITLES:
            if c in line:
                company = c
                break
        if company is None and _PLACEHOLDER_COMPANY.search(line) and role_line_idx < len(_ROLE_ORDER):
            # Positional fallback: this is the Nth role header and no company name is present
            # as text, so trust CLAUDE.md's fixed Cision/Sterkly/Zero-To-Sixty ordering.
            company = _ROLE_ORDER[role_line_idx]
            lines[i] = _PLACEHOLDER_COMPANY.sub(company, lines[i])
            companies_patched += 1
        role_line_idx += 1
        if company is None:
            continue
        if _PLACEHOLDER_TITLE.match(lines[i]):
            lines[i] = _PLACEHOLDER_TITLE.sub(f"### {_ROLE_TITLES[company]} |", lines[i])
            titles_patched += 1
        if _PLACEHOLDER_DATE_SPAN.search(lines[i]):
            lines[i] = _PLACEHOLDER_DATE_SPAN.sub(_ROLE_DATES[company], lines[i])
            dates_patched += 1
    if titles_patched:
        actions.append(f"titles x{titles_patched}")
    if companies_patched:
        actions.append(f"companies x{companies_patched}")
    if dates_patched:
        actions.append(f"dates x{dates_patched}")

    loc_removed = sum(1 for l in lines if _PLACEHOLDER_ROLE_LOCATION.match(l.rstrip("\n")))
    if loc_removed:
        lines = [l for l in lines if not _PLACEHOLDER_ROLE_LOCATION.match(l.rstrip("\n"))]
        actions.append(f"stripped [Location] x{loc_removed}")

    # Cover-letter sign-off: last non-blank line, if it's still a bare name placeholder.
    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].rstrip("\n").strip()
        if not stripped:
            continue
        if _PLACEHOLDER_SIGNOFF.match(stripped):
            lines[i] = h["name"] + "\n"
            actions.append("signoff")
        break

    if not actions:
        return "skipped (no placeholder found)"
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return "patched (" + ", ".join(actions) + ")"


def main() -> None:
    folders = sys.argv[1:]
    if not folders:
        print(__doc__)
        sys.exit(1)

    h = load_real_header()
    any_patched = False
    for folder in folders:
        folder = folder.rstrip("/\\")
        company = os.path.basename(folder)
        for fname in ("Resume.md", "CoverLetter.md"):
            result = patch_file(os.path.join(folder, fname), h)
            print(f"{company}/{fname}: {result}")
            if result == "patched":
                any_patched = True

    sys.exit(0 if any_patched or len(folders) == 0 else 0)


if __name__ == "__main__":
    main()
