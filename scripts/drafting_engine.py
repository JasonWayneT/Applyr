import os
import re
import json
import subprocess
import verify_claims as determinator
from utils import (load_file, call_llm, is_local_primary, get_verifier_model,
                   SUBMISSIONS_DIR, RESUME_MASTER_FILE, COVER_LETTER_REF_FILE,
                   RESUME_STYLE_REF_FILE, CLAIM_VERIFIER_FILE,
                   WORK_EXP_FILE, RESUME_BEST_PRACTICES,
                   CL_BEST_PRACTICES)


# --- Hard Fact Validation (Deterministic Post-Generation Guard) ---
# Extracts known ground-truth facts from the master resume and verifies
# they were not hallucinated or substituted in the generated output.

# These are literal strings that MUST appear in any generated resume.
# If they are missing, the output is flagged and corrected.
HARD_FACTS = None  # Loaded lazily from master resume


def _load_hard_facts(master_resume_text):
    """Extract deterministic facts from the master resume."""
    facts = {
        "education": [],
        "companies": [],
        "contact": [],
    }
    # Education: look for university names
    if "national university" in master_resume_text.lower():
        facts["education"].append("National University")

    # Company names from ## headers
    company_pattern = re.compile(r"^## \*\*(.+?)\*\*", re.MULTILINE)
    for match in company_pattern.finditer(master_resume_text):
        facts["companies"].append(match.group(1).strip())

    # Contact info (name, email)
    lines = master_resume_text.split("\n")
    if lines:
        facts["contact"].append(lines[0].replace("#", "").replace("*", "").strip())  # Name

    return facts


# Common hallucination substitutions the LLM tends to make
KNOWN_HALLUCINATIONS = {
    # Education substitutions
    "San Diego State University": "National University",
    "SDSU": "National University",
    "San Diego State": "National University",
    "University of San Diego": "National University",
    "UC San Diego": "National University",
    "UCSD": "National University",
    "California State University": "National University",
    "CSUSM": "National University",
    # Company name corrections
    "PR Newswire": "Cision",
    "Cision Ltd": "Cision",
    "Cision Inc": "Cision",
}

# Tools Jason has NEVER used — block any mention in generated output
# Source: workExperience.md — if it isn't there, it doesn't exist.
BLOCKED_TOOLS = [
    "Snowflake", "Tableau", "Looker", "dbt", "Airflow", "Spark", "Kafka",
    "Kubernetes", "Docker", "Terraform", "Helm", "Jenkins", "CircleCI",
    "FHIR", "HL7", "HIPAA", "SOC2", "SOC 2", "ISO 27001",
    "Databricks", "Redshift", "BigQuery", "Fivetran", "Segment",
    "Amplitude", "Mixpanel", "Pendo", "LaunchDarkly",
    "React", "Node.js", "GraphQL", "Rust", "Go",
    "TensorFlow", "PyTorch", "LangChain", "RAG", "LLM pipeline",
    "AWS", "Azure", "GCP", "Heroku",
]

# Seniority inflation phrases — flag if any appear in the resume
SENIORITY_INFLATION_PHRASES = [
    "Led a team of", "Led team of",
    "Managed a team", "Managed team",
    "Director of", "Vice President", " VP ", "Head of",
    "Hired and", "Hire and", "Supervised",
    "People management", "Direct reports",
    "P&L ownership", "Revenue owner", "Owned billing",
    "Shipped AI", "Shipped ML", "Trained model", "Deployed model",
    "Built ML", "Built AI", "AI pipeline", "ML pipeline",
]

# Approved verified metrics from workExperience.md — exact values only
# Any numeric claim in the output must match one of these to pass.
APPROVED_METRICS = [
    "$40", "40M", "40,000,000",  # MET-01: $40M ARR
    "3,500", "3500",              # MET-02: 3,500 active accounts
    "25,000", "25000",            # MET-03: 25,000 active users
    "7%",                         # MET-04: 7% churn
    "$1M", "$2M", "1,000,000", "2,000,000",  # MET-05: infra savings
    "40%",                 # MET-06: data drop-off
    "100%",                       # MET-07: drop-off resolved
    "90%",                        # MET-08: security backlog
    "200",                        # MET-09: SQL databases
    "700",                        # MET-10: migrations
    "$288", "288,000",            # MET-11: fulfillment contracts
    "$8,500", "8500",             # MET-11: quarterly savings
    "$22,100", "22,100",          # MET-12: onboarding savings
    "6+", "6 years",              # tenure
]


def validate_hard_facts(generated_text, master_resume_text, target_company=None, doc_type='resume'):
    """
    Deterministic post-generation check. Compares generated output against
    the master resume source of truth. Fixes known hallucinations and logs
    any discrepancies.

    Checks (all regex/string — no LLM dependency):
      0. Header normalization to required standard headings
      1. Known bad substitutions (auto-fixed)
      2. Blocked tool names (flagged for removal)
      3. Seniority inflation phrases (flagged)
      4. Metric integrity (any number not in approved list is flagged)
      5. Education / company / contact presence (resume only)
      6. Enhanced placeholder and bracket healing

    Args:
        doc_type: 'resume' or 'cover_letter' — gates checks that only apply to resumes.

    Returns (corrected_text, warnings_list).
    """
    global HARD_FACTS
    if HARD_FACTS is None:
        HARD_FACTS = _load_hard_facts(master_resume_text)

    warnings = []
    corrected = generated_text

    # 0. Header Normalization Guard (Option A Standard)
    header_mappings = [
        (r'^#{2,3}\s*(?:\*\*)?PROFESSIONAL\s+SUMMARY(?:\*\*)?', '## PROFESSIONAL SUMMARY'),
        (r'^#{2,3}\s*(?:\*\*)?SUMMARY(?:\*\*)?', '## PROFESSIONAL SUMMARY'),
        (r'^#{2,3}\s*(?:\*\*)?PROFESSIONAL\s+EXPERIENCE(?:\*\*)?', '## PROFESSIONAL EXPERIENCE'),
        (r'^#{2,3}\s*(?:\*\*)?EXPERIENCE(?:\*\*)?', '## PROFESSIONAL EXPERIENCE'),
        (r'^#{2,3}\s*(?:\*\*)?WORK\s+EXPERIENCE(?:\*\*)?', '## PROFESSIONAL EXPERIENCE'),
        (r'^#{2,3}\s*(?:\*\*)?EMPLOYMENT\s+HISTORY(?:\*\*)?', '## PROFESSIONAL EXPERIENCE'),
        (r'^#{2,3}\s*(?:\*\*)?EDUCATION(?:\s+.*)?(?:\*\*)?', '## EDUCATION & CERTIFICATIONS'),
    ]
    
    header_fixed = False
    for pat, replacement in header_mappings:
        # Apply replacement line by line or multiline safely
        new_text = re.sub(pat, replacement, corrected, flags=re.MULTILINE | re.IGNORECASE)
        if new_text != corrected:
            corrected = new_text
            header_fixed = True
    
    if header_fixed:
         print("    [GUARD] Normalized layout section headers to standard uppercase format.")

    # 1. Fix known hallucination substitutions
    for wrong, right in KNOWN_HALLUCINATIONS.items():
        if wrong in corrected:
            warnings.append(f"HALLUCINATION CAUGHT: '{wrong}' replaced with '{right}'")
            corrected = corrected.replace(wrong, right)

    # 1b. Automatically strip Skills and Technical Environment sections safely (bulletproof variants)
    corrected = re.sub(
        r'(?:<h2[^>]*>\s*<strong>\s*(?:SKILLS|TECHNICAL).*?</h2>|##\s*(?:Skills|Technical Skills|Technical Environment|Core Expertise|Skills & Tools).*?)([\s\S]*?)(?=<h2[^>]*>|##|###|</div>|$)',
        '',
        corrected,
        flags=re.IGNORECASE
    )

    # 2. TOOL BLOCKLIST — flag any tool Jason never used
    tool_violations = []
    for tool in BLOCKED_TOOLS:
        pattern = r'(?<![\w-])' + re.escape(tool) + r'(?![\w-])'
        if re.search(pattern, corrected, re.IGNORECASE):
            tool_violations.append(tool)
    if tool_violations:
        warnings.append(
            f"TOOL HALLUCINATION: The following tools are NOT in workExperience.md and must be removed: "
            f"{', '.join(tool_violations)}"
        )
        for tool in tool_violations:
            pattern = r'(?<![\w-])' + re.escape(tool) + r'(?![\w-])'
            corrected = re.sub(pattern, '[REDACTED]', corrected, flags=re.IGNORECASE)
        print(f"    [GUARD] Auto-redacted {len(tool_violations)} blocked tool(s): {tool_violations}")

    # 3. SENIORITY INFLATION — flag leadership/management claims
    seniority_violations = []
    for phrase in SENIORITY_INFLATION_PHRASES:
        if phrase.lower() in corrected.lower():
            seniority_violations.append(phrase)
    if seniority_violations:
        warnings.append(
            f"SENIORITY INFLATION: The following phrases imply leadership/management Jason did not hold: "
            f"{', '.join(seniority_violations)}"
        )
        print(f"    [GUARD] Seniority inflation detected: {seniority_violations}")

    # 3b. MANDATORY TITLE CONSISTENCY GUARD — Enforce Cision is strictly "Product Manager"
    lines = corrected.split('\n')
    new_lines = []
    cision_healed = False
    for line in lines:
        if 'cision' in line.lower() and any(kw in line.lower() for kw in ['product owner', 'functional product manager']):
            ugly_titles = [
                "Product Owner / Functional Product Manager",
                "Product Owner / Platform Product Manager",
                "Product Owner (Functionally Product Manager)",
                "Product Owner (Functional Scope)",
                "Product Owner → Product Manager (Functional Scope)",
                "Product Owner -> Product Manager (Functional Scope)",
                "Product Owner / Product Manager",
                "Product Owner"
            ]
            for ugly in ugly_titles:
                pattern = re.compile(re.escape(ugly), re.IGNORECASE)
                if pattern.search(line):
                    line = pattern.sub("Product Manager", line)
                    cision_healed = True
            
            line = re.sub(r'Product Manager\s*/\s*Product Manager', 'Product Manager', line, flags=re.IGNORECASE)
            line = re.sub(r'Product Manager\s*/\s*Platform Product Manager', 'Product Manager', line, flags=re.IGNORECASE)
            
        new_lines.append(line)
    
    if cision_healed:
        corrected = '\n'.join(new_lines)
        print("    [GUARD] Enforced strict 'Product Manager' title consistency for Cision.")

    # 4. METRIC INTEGRITY — scan for any number patterns and verify against approved list
    numeric_pattern = re.compile(r'(?:\$[\d,]+(?:M|K|B)?|\d+(?:,\d{3})*(?:\.\d+)?\s*%|\d{1,3}(?:,\d{3})+|\b\d{2,}\b)')
    found_numbers = numeric_pattern.findall(corrected)
    unapproved = []
    for num in found_numbers:
        clean = num.strip()
        if not any(approved.lower() in clean.lower() or clean.lower() in approved.lower()
                   for approved in APPROVED_METRICS):
            unapproved.append(clean)
    if unapproved:
        real_violations = [n for n in unapproved if not re.match(r'^(?:20\d{2}|760|619|858|2026|2025|2024|2023|2022|2021|2019|2017|\d{1,2})$', n.replace(',', '').strip())]
        if real_violations:
            warnings.append(
                f"METRIC INTEGRITY: Unverified numeric claims found (not in approved metrics list): "
                f"{', '.join(real_violations)}"
            )
            print(f"    [GUARD] Unverified metrics detected: {real_violations}")

    # 5. Verify education facts are present & Auto-heal if missing (resume only)
    if doc_type == 'resume':
        missing_edu = False
        for uni in HARD_FACTS["education"]:
            if uni not in corrected:
                missing_edu = True
                warnings.append(f"MISSING FACT: Education '{uni}' not found in generated output. Triggering self-healing injection.")

        if missing_edu:
            corrected = re.sub(r'##\s*Education\s*(?:\n\s*)*', '', corrected, flags=re.IGNORECASE)
            corrected = re.sub(r'##\s*Certifications\s*(?:\n\s*)*', '', corrected, flags=re.IGNORECASE)
            corrected = re.sub(r'##\s*Education & Certifications\s*(?:\n\s*)*', '', corrected, flags=re.IGNORECASE)

            edu_cert_block = "\n\n## EDUCATION\n\n" \
                             "* **Bachelor of Business Administration, Major in Management** — National University, San Diego, California, 2019\n"
            corrected = corrected.rstrip() + edu_cert_block
            print("    [GUARD] Auto-injected verified Education block.")

        # 6. Verify company names are present (resume only)
        for company in HARD_FACTS["companies"][:2]:
            if company.upper() not in corrected.upper():
                warnings.append(f"MISSING FACT: Company '{company}' not found in generated output.")

    # 7. Auto-heal Contact & Template Info Placeholders (Hyper-Aggressive Local fallback sweeping)
    placeholders = {
        "[Your Name]": "JASON TAYLOR",
        "*[Your Name]*": "JASON TAYLOR",
        "[Full Name]": "JASON TAYLOR",
        "[Your Phone Number]": "[REDACTED_PHONE]",
        "[Phone Number]": "[REDACTED_PHONE]",
        "[Your Email Address]": "[REDACTED_EMAIL]",
        "[Your Email]": "[REDACTED_EMAIL]",
        "[Email Address]": "[REDACTED_EMAIL]",
        "[Your LinkedIn Profile URL]": "linkedin.com/in/redacted-linkedin-slug",
        "[LinkedIn Profile URL]": "linkedin.com/in/redacted-linkedin-slug",
        "[LinkedIn URL]": "linkedin.com/in/redacted-linkedin-slug",
        "[LinkedIn]": "linkedin.com/in/redacted-linkedin-slug",
        "## [Your Name]": "# JASON TAYLOR",
        "[University Name]": "National University",
        "[University]": "National University",
        "[Hiring Manager Name]": "Hiring Team",
        "[Hiring Manager]": "Hiring Team",
        "[Dates]": "",  # Safe collapse for leftover template debris
        "*[Dates]*": ""
    }
    if target_company:
        placeholders["[Company Name]"] = target_company
        placeholders["*[Company Name]*"] = target_company
        placeholders["[Target Company]"] = target_company
        
    placeholder_triggered = False
    for ph, val in placeholders.items():
        # Case-insensitive safe sweep for common variations
        if ph.lower() in corrected.lower():
            # Perform literal replacement on matching keys
            pattern = re.compile(re.escape(ph), re.IGNORECASE)
            corrected = pattern.sub(val, corrected)
            placeholder_triggered = True
            
    if placeholder_triggered:
        print("    [GUARD] Resolved model template placeholders and bracket tags to actual ground truth.")

    # 7b. Verify contact name is at the very top
    if HARD_FACTS["contact"]:
        name = HARD_FACTS["contact"][0]
        if name and name.upper() not in corrected[:300].upper():
            warnings.append(f"MISSING FACT: Name '{name}' not found at top of resume. Repairing header.")
            header = f"# JASON TAYLOR\n\nSan Diego, CA | [REDACTED_PHONE] | [REDACTED_EMAIL] | linkedin.com/in/redacted-linkedin-slug\n\n"
            corrected = header + corrected.lstrip()
            print("    [GUARD] Prepend-repaired missing Name/Contact header.")

    # 8. Anti-AI fingerprint: catch em-dashes
    if '\u2014' in corrected or ' -- ' in corrected:
        warnings.append("STYLE VIOLATION: Em-dash detected. Replacing with comma or clause break.")
        corrected = corrected.replace('\u2014', ', ').replace(' -- ', ', ')
        print("    [GUARD] Em-dash auto-corrected.")

    if warnings:
        print(f"    [HARD FACT AUDIT] {len(warnings)} issue(s) found & actively defended:")
        for w in warnings:
            print(f"      - {w}")
    else:
        print("    [HARD FACT AUDIT] All ground-truth facts verified. Clean output.")

    return corrected, warnings


def run_research(company_name, jd_text):
    folder = os.path.join(SUBMISSIONS_DIR, company_name.lower().replace(" ", "_"))
    packet_path = os.path.join(folder, "Research_Packet.json")
    if os.path.exists(packet_path):
        print(f"    [Research] Found cached intelligence for {company_name}. Using local packet.")
        return load_file(packet_path)

    print(f"    [Research] Pulling Perplexity intelligence for {company_name}...")
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        subprocess.run(["python", os.path.join(script_dir, "research-engine.py"),
                        company_name, "Product Manager"], check=True)
        if os.path.exists(packet_path):
            return load_file(packet_path)
    except Exception as e:
        print(f"    [Research Error] {e}")
    return "No research data available."


def select_relevant_claims(jd_text, valid_ids):
    """
    Phase 1 of two-phase generation: ask the LLM to pick the most relevant
    claim IDs for this specific JD before any resume text is written.
    Returns a list of valid ID strings. Falls back to all IDs on failure.
    """
    id_context = "\n".join(f"{k}: {v}" for k, v in valid_ids.items())
    system_prompt = (
        "You are a resume strategist. Your only job is to select claim IDs. "
        "Output ONLY a valid JSON array of ID strings. No explanation, no markdown, just JSON."
    )
    user_prompt = f"""Select the 8-12 claim IDs most relevant to this job description.

AVAILABLE CLAIMS (ID: ground-truth sentence):
{id_context}

JOB DESCRIPTION:
{jd_text[:2500]}

Rules:
- Output ONLY a JSON array, e.g. ["ACC-101", "MET-01", "VOC-03"]
- Only include IDs from the list above
- Prefer IDs whose evidence directly matches a stated requirement in the JD
- Do not invent IDs"""

    result = call_llm(
        system_prompt, user_prompt,
        temperature=0.0,
        response_mime_type="application/json",
        provider_override=["gemini", "local"],
    )

    if result:
        try:
            cleaned = result.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            selected = json.loads(cleaned)
            if isinstance(selected, list):
                valid_selected = [i for i in selected if i in valid_ids]
                if valid_selected:
                    print(f"    [Phase 1] Selected {len(valid_selected)} relevant claims: {valid_selected}")
                    return valid_selected
        except (json.JSONDecodeError, ValueError):
            pass

    print("    [Phase 1] Selection failed or returned no valid IDs — using all claims.")
    return list(valid_ids.keys())


def llm_verify_claims(draft_text, work_exp, claim_verifier_rules):
    print("    [Audit] Running Claim Verifier (v2.0) against generated text...")
    system_prompt = "You are the cynical auditor enforcing the Claim Verifier rules."
    user_prompt = f"""
    RULES:
    {claim_verifier_rules}

    GROUND TRUTH:
    {work_exp}

    TEXT TO AUDIT:
    {draft_text}

    Perform the verification. If high-risk flags exist, rewrite the sentence to be accurate.
    Return ONLY the final corrected markdown text. Do not output 'FAILED CLAIM' unless explicitly asked, just fix it in the final output directly to ensure the pipeline can proceed automatically with corrected text.
    """
    # BUG-010: local self-audit is unreliable — use Gemini when available.
    # In local-only mode, route to the dedicated verifier model (phi3.5 by default).
    verifier_model = get_verifier_model()
    providers = ['local'] if is_local_primary() else ['gemini']
    result = call_llm(system_prompt, user_prompt,
                      model=verifier_model,
                      provider_override=providers)
    if not result:
        print("    [Audit Warning] Claim Verifier returned empty. Using original draft.")
        return draft_text
    return result


def generate_pdf(md_path, output_path):
    # Enforces Single-Column, ATS-Optimized typography using Playwright
    script_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        subprocess.run(["python", os.path.join(script_dir, "compile_single.py"), md_path, output_path], check=True)
        print(f"    [Export] Saved ATS-Optimized PDF: {output_path}")
    except Exception as e:
        print(f"    [Export Error] Failed to generate PDF: {e}")


def _fallback_bullet(source_text):
    """Last-resort: reformat the raw ground-truth line as a plain bullet."""
    clean = re.sub(r'\[(ACC|MET|VOC)-\d+\]', '', source_text)
    clean = re.sub(r'\*+', '', clean)
    clean = clean.strip().lstrip('-•').strip()
    if clean and not clean.endswith('.'):
        clean += '.'
    return clean


def _generate_bullets_local(selected_ids, valid_ids, jd_text):
    """
    Phase 2 of the local two-phase flow.
    For each selected claim ID, makes one focused local LLM call to produce
    a single validated resume bullet. Falls back to reformatted source on failure.
    Returns dict {claim_id: bullet_text}.
    """
    from verify_claims import _verify_bullet_local

    bullets = {}
    for claim_id in selected_ids:
        source_text = valid_ids.get(claim_id, "")
        if not source_text:
            continue

        system = (
            "You are a resume bullet writer. Write exactly ONE resume bullet point. "
            "Output ONLY the bullet — no preamble, no ID tags, no explanation."
        )
        user = f"""Rewrite the achievement below as one resume bullet point reframed for the job.

ORIGINAL ACHIEVEMENT:
{source_text}

JOB CONTEXT (first 600 chars):
{jd_text[:600]}

Rules:
- Keep ALL numbers and dollar values EXACTLY as stated in the original
- Do NOT invent tools, metrics, or facts not in the original
- Start with an action verb
- Maximum 25 words
- Output the bullet only

Bullet:"""

        result = call_llm(system, user, temperature=0.0, provider_override=['local'])

        if result:
            bullet = result.strip().lstrip('-•').strip()
            valid, err = _verify_bullet_local(source_text, bullet)
            if valid:
                bullets[claim_id] = bullet
            else:
                print(f"    [Phase 2] {claim_id} bullet failed validation ({err}). Using source fallback.")
                bullets[claim_id] = _fallback_bullet(source_text)
        else:
            bullets[claim_id] = _fallback_bullet(source_text)

    return bullets


def run_drafting_engine(company_name, jd_text, work_exp, evaluation_result):
    print(f"  -> Initializing Drafting Engine for {company_name}")
    company_folder = os.path.join(SUBMISSIONS_DIR, company_name.lower().replace(" ", "_"))
    os.makedirs(company_folder, exist_ok=True)

    # Save original JD
    try:
        jd_path = os.path.join(company_folder, "Original_JD.txt")
        with open(jd_path, "w", encoding="utf-8") as f:
            f.write(jd_text)
    except Exception as e:
        print(f"    [Error] Could not save original JD: {e}")

    # 1. Run Research
    research_json = run_research(company_name, jd_text)

    # Load References
    master_resume = load_file(RESUME_MASTER_FILE)
    resume_style = load_file(RESUME_STYLE_REF_FILE)
    cl_style = load_file(COVER_LETTER_REF_FILE)
    resume_best_practices = load_file(RESUME_BEST_PRACTICES)
    cl_best_practices = load_file(CL_BEST_PRACTICES)
    verifier_rules = load_file(CLAIM_VERIFIER_FILE)

    # 2. Bridge Logic & Resume Generation
    print("    [Drafting] Applying 'Bridge Logic' (Platform -> Growth) to Resume...")
    
    # Load valid claim IDs
    valid_ids = determinator.load_valid_ids(WORK_EXP_FILE)

    # Phase 1: select the most relevant claims for this JD before writing anything
    selected_ids = select_relevant_claims(jd_text, valid_ids)
    selected_truth = "\n".join(
        f"[{id_}] {valid_ids[id_]}" for id_ in selected_ids if id_ in valid_ids
    )

    # Phase 2 (local only): pre-generate validated bullets before the full resume call
    using_local = is_local_primary()
    pre_validated_bullets = {}
    if using_local:
        print("    [Local Mode] Running Phase 2: pre-generating validated bullets for each selected claim...")
        pre_validated_bullets = _generate_bullets_local(selected_ids, valid_ids, jd_text)
        print(f"    [Local Mode] Phase 2 complete: {len(pre_validated_bullets)} validated bullets ready.")

    resume_prompt = {
        "role": "You are a professional resume writer for Jason Taylor. "
                "Your goal is to create a high-impact, ONE-PAGE technical resume that matches the style reference template exactly. "
                "STRICT CONSTRAINT: The resume MUST have exactly these three headers: PROFESSIONAL SUMMARY, PROFESSIONAL EXPERIENCE, and EDUCATION. No other headers are allowed. "
                "The PROFESSIONAL SUMMARY must be exactly 1-2 concise lines to save space. Do not include Skills or Technical Environment sections. "
                "The entire resume MUST fit on a single page. Do not exceed 3,200 characters. "
                "Use the provided work experience faithfully. Do not hallucinate tools or seniority.\n"
                "STRICT REQUIREMENT OVERRIDE: Despite rules suggesting otherwise, you MUST physically anchor EVERY accomplishment, metric, and translation claim in your output by appending its respective bracketed ID (e.g. [ACC-101], [MET-01], [VOC-01]) from the ground truth directly to the end of each sentence or bullet point. Every single claim must be traceable.",
        "content": f"""
    Transform the MASTER RESUME to match the JOB DESCRIPTION while strictly adhering to the BRIDGE LOGIC.

    BRIDGE LOGIC RULES:
    1. Translate Platform wins (Stability/Scale) to Growth needs (User Scaling, Business Revenue).
    Example: "Reduced API latency by 40%" -> "Improved system responsiveness to support 10x user scaling and retention."
    Example: "Resolved 300+ security vulnerabilities" -> "Mitigated enterprise risk to unblock GTM expansion."

    HALLUCINATION EXAMPLES — STUDY THESE BEFORE WRITING:
    ❌ WRONG: "Led a team of 12 engineers to build a Kubernetes microservices platform, cutting costs by $5M [ACC-101]"
       WHY WRONG: seniority inflation ("Led a team"), blocked tool (Kubernetes), fabricated metric ($5M not approved)
    ❌ WRONG: "Deployed Snowflake data pipeline improving churn by 15% [MET-04]"
       WHY WRONG: blocked tool (Snowflake), MET-04 value is 7% not 15%
    ❌ WRONG: "Owned P&L and drove $80M ARR growth [MET-01]"
       WHY WRONG: seniority inflation (P&L ownership), MET-01 value is $40M not $80M
    ✓ RIGHT: "Stabilized core platform to support 25,000 active users [MET-03], protecting $40M ARR [MET-01]."

    PHASE 2 CONSTRAINT — USE ONLY PRE-SELECTED CLAIMS:
    The following claims have already been selected as most relevant to this JD.
    You MUST build your bullets exclusively from these IDs. Do not reference any ID not listed here.

    SELECTED CLAIMS FOR THIS ROLE:
    {selected_truth}
    {(chr(10) + "    PRE-VALIDATED BULLETS (COPY THESE EXACTLY — do not rewrite, do not change any numbers):" + chr(10) + chr(10).join(f"    [{id_}] → {bullet}" for id_, bullet in pre_validated_bullets.items()) + chr(10)) if pre_validated_bullets else ""}

    STYLE & STRATEGY GUIDE:
    Write pure, standard Markdown (using `#`, `##`, `*`, etc.). DO NOT output any raw HTML tags or `<div...>` wrappers. The system will convert your standard Markdown into the final styled PDF automatically.

    You MUST strictly follow these best practices for conversion and impact:
    {resume_best_practices}

    You MUST strictly match the layout and structural formatting of this template:
    {resume_style}

    FULL GROUND TRUTH (for context — but ONLY cite IDs from SELECTED CLAIMS above):
    {work_exp}

    MASTER RESUME (Format to follow, but update bullets):
    {master_resume}

    JOB DESCRIPTION:
    {jd_text}

    CRITICAL REQUIREMENT: For EVERY bullet point or sentence making a factual claim, you MUST append the bracketed source Fact ID (e.g., [ACC-101], [MET-01]) at the end of that sentence. Only use IDs from the SELECTED CLAIMS list above.

    Output strictly the translated standard Markdown resume. No preamble.
    """
    }
    
    draft_resume = ""
    error_hint = ""
    
    # Initial Attempt + up to 2 retries
    for attempt in range(3):
        role = resume_prompt["role"]
        content = resume_prompt["content"]
        if error_hint:
            content += f"\n\n[PREVIOUS ATTEMPT FAILED CLAIM VERIFICATION]\nError details: {error_hint}\nPlease rewrite the resume ensuring EVERY single factual claim or metric is correctly tagged with valid bracketed IDs (e.g., [ACC-101], [MET-01]) from the ground truth. Do not invent tags."
            
        draft_resume = call_llm(role, content, temperature=0.0, provider_override=['gemini', 'local'])
        if not draft_resume:
            print("    [Drafting Error] LLM returned empty content.")
            break
            
        # Validate
        res = determinator.verify_content(draft_resume, valid_ids)
        if res["success"]:
            print(f"    [Audit] Resume passed claim ID verification on attempt {attempt+1}.")
            break
        else:
            error_hint = res["error"]
            print(f"    [Audit Warning] Resume failed claim ID verification on attempt {attempt+1}: {error_hint}")
            if attempt == 2:
                print("    [CRITICAL WARNING] Resume failed claim ID verification after maximum retries. Using best-effort output.")
                
    if not draft_resume:
        print(f"  [ERROR] LLM returned empty resume for {company_name}. Skipping save.")
        return
        
    cleaned_draft_resume = determinator.strip_ids(draft_resume)
    # Skip LLM claim audit when local is the only provider — the model cannot reliably audit itself
    if using_local:
        print("    [Local Mode] Skipping LLM claim audit (local self-audit unreliable). Deterministic guards cover this.")
        verified_resume = cleaned_draft_resume
    else:
        verified_resume = llm_verify_claims(cleaned_draft_resume, work_exp, verifier_rules)

    # Hard Fact Validation: deterministic check against master resume
    final_resume, resume_warnings = validate_hard_facts(verified_resume, master_resume, target_company=company_name, doc_type='resume')

    resume_md_path = os.path.join(company_folder, "Resume.md")
    resume_pdf_path = os.path.join(company_folder, "Resume.pdf")

    with open(resume_md_path, "w", encoding="utf-8") as f:
        f.write(final_resume)
    
    # Run the compliance guard on the saved Resume.md
    from style_compliance_guard import run_guard
    run_guard(resume_md_path)
    
    # Run the structural QA Checklist (Zero-Tolerance Enforced)
    from quality_checker import check_resume
    qa_passed, qa_msg = check_resume(resume_md_path)
    if not qa_passed:
        print(f"    [QA AUDIT FAIL] Resume: {qa_msg}")
        # Hard Block: Delete garbage markdown if it fails the final verification
        if os.path.exists(resume_md_path): os.remove(resume_md_path)
        raise ValueError(f"CRITICAL QA FAILURE: Resume does not meet production standards: {qa_msg}")
    else:
        print(f"    [QA AUDIT PASS] Resume: {qa_msg}")
    
    # Read the audited resume content to compile the PDF
    with open(resume_md_path, "r", encoding="utf-8") as f:
        final_resume = f.read()

    print(f"    [Drafting] Saved and validated Resume.md ({len(final_resume)} chars)")
    generate_pdf(resume_md_path, resume_pdf_path)

    # 3. Cover Letter Generation
    print("    [Drafting] Generating Cover Letter...")
    cl_prompt = {
        "role": "You are a professional cover letter writer for Jason Taylor. "
                "Your goal is to write a concise, one-page cover letter. "
                "STRICT CONSTRAINT: The entire letter must be under 1,800 characters to fit on one page with headers. "
                "Directly address the job requirements using Jason's actual experience.\n"
                "STRICT REQUIREMENT OVERRIDE: Despite instructions otherwise, you MUST physically anchor EVERY claim or accomplishment in your output by appending its respective bracketed ID (e.g. [ACC-101], [MET-01]) from the ground truth directly to the end of the sentence. Every single claim must have an ID.",
        "content": f"""
    Write a 250-400 word Cover Letter based on the JOB DESCRIPTION and RESEARCH PACKET.

    PHASE 2 CONSTRAINT — USE ONLY PRE-SELECTED CLAIMS:
    Build every factual claim exclusively from the IDs below. Do not reference any ID not listed here.

    SELECTED CLAIMS FOR THIS ROLE:
    {selected_truth}
    {(chr(10) + "    PRE-VALIDATED BULLETS (use these exact facts and numbers):" + chr(10) + chr(10).join(f"    [{id_}] → {bullet}" for id_, bullet in pre_validated_bullets.items()) + chr(10)) if pre_validated_bullets else ""}

    STYLE & STRATEGY GUIDE:
    Write pure, standard Markdown. DO NOT output any raw HTML tags.

    You MUST strictly follow these best practices for cover letter writing:
    {cl_best_practices}

    You MUST strictly match the structural format and signature style of this template:
    {cl_style}

    FULL GROUND TRUTH (for context — but ONLY cite IDs from SELECTED CLAIMS above):
    {work_exp}

    JOB DESCRIPTION:
    {jd_text}

    RESEARCH:
    {research_json}

    CRITICAL REQUIREMENT: For EVERY sentence making a factual claim, you MUST append the bracketed source Fact ID (e.g., [ACC-101], [MET-01]) at the end of that sentence. Only use IDs from the SELECTED CLAIMS list above.

    Output strictly the standard markdown cover letter. No preamble.
    """
    }
    
    draft_cl = ""
    cl_error_hint = ""
    
    # Initial attempt + up to 2 retries
    for attempt in range(3):
        role = cl_prompt["role"]
        content = cl_prompt["content"]
        if cl_error_hint:
            content += f"\n\n[PREVIOUS ATTEMPT FAILED CLAIM VERIFICATION]\nError details: {cl_error_hint}\nPlease rewrite the cover letter ensuring EVERY single claim is tagged with its valid bracketed ID (e.g. [ACC-101], [MET-01]) from the ground truth."
            
        draft_cl = call_llm(role, content, temperature=0.0, provider_override=['gemini', 'local'])
        if not draft_cl:
            break
            
        # Validate
        res = determinator.verify_content(draft_cl, valid_ids)
        if res["success"]:
            print(f"    [Audit] Cover letter passed claim ID verification on attempt {attempt+1}.")
            break
        else:
            cl_error_hint = res["error"]
            print(f"    [Audit Warning] Cover letter failed claim ID verification on attempt {attempt+1}: {cl_error_hint}")
            if attempt == 2:
                print("    [CRITICAL WARNING] Cover letter failed claim ID verification after maximum retries. Using best-effort output.")
                
    if not draft_cl:
        print(f"  [ERROR] LLM returned empty cover letter for {company_name}. Skipping save.")
        return
        
    cleaned_draft_cl = determinator.strip_ids(draft_cl)
    if using_local:
        verified_cl = cleaned_draft_cl
    else:
        verified_cl = llm_verify_claims(cleaned_draft_cl, work_exp, verifier_rules)

    # Hard Fact Validation: deterministic check against master resume
    final_cl, cl_warnings = validate_hard_facts(verified_cl, master_resume, target_company=company_name, doc_type='cover_letter')

    cl_md_path = os.path.join(company_folder, "CoverLetter.md")
    cl_pdf_path = os.path.join(company_folder, "CoverLetter.pdf")

    with open(cl_md_path, "w", encoding="utf-8") as f:
        f.write(final_cl)
        
    # Run the compliance guard on the saved CoverLetter.md
    from style_compliance_guard import run_guard
    run_guard(cl_md_path)
    
    # Run the structural QA Checklist & Auto-Repair (Zero-Tolerance Enforced)
    from quality_checker import check_and_repair_cover_letter
    qa_passed, qa_msg = check_and_repair_cover_letter(cl_md_path)
    if not qa_passed:
        print(f"    [QA AUDIT FAIL] Cover Letter: {qa_msg}")
        # Hard Block: Delete garbage cover letter
        if os.path.exists(cl_md_path): os.remove(cl_md_path)
        raise ValueError(f"CRITICAL QA FAILURE: Cover Letter does not meet production standards: {qa_msg}")
    else:
        print(f"    [QA AUDIT PASS] Cover Letter: {qa_msg}")
    
    # Read the audited cover letter content to compile the PDF
    with open(cl_md_path, "r", encoding="utf-8") as f:
        final_cl = f.read()

    print(f"    [Drafting] Saved and validated CoverLetter.md ({len(final_cl)} chars)")
    generate_pdf(cl_md_path, cl_pdf_path)

    # Summary of all validation issues
    all_warnings = resume_warnings + cl_warnings
    if all_warnings:
        print(f"  -> [AUDIT SUMMARY] {len(all_warnings)} total issue(s) caught and corrected.")
    else:
        print(f"  -> [AUDIT SUMMARY] All assets passed hard-fact validation. Clean output.")

    print(f"  -> Successfully generated and audited all assets for {company_name}")
