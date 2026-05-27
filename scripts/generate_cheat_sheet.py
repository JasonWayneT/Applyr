"""
Interview cheat sheet — template-first (CR-018 / FR-108).
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from claim_composer import strip_bridge_prefix
from llm_stages import call_llm_stage, local_only_mode
from utils import SUBMISSIONS_DIR, WORK_EXP_FILE, load_file

CHEAT_SHEET_MODES = ("template", "llm", "skip")
DEFAULT_REVERSE_QUESTIONS = [
    "How do you measure platform reliability and customer impact today?",
    "What is the biggest technical debt item on the roadmap this quarter?",
    "How does product partner with engineering on prioritization and tradeoffs?",
]


def _company_folder(company_name: str) -> str:
    return os.path.join(SUBMISSIONS_DIR, company_name.lower().replace(" ", "_"))


def _load_research(company_folder: str) -> tuple[Optional[str], str]:
    json_path = os.path.join(company_folder, "Research_Packet.json")
    md_path = os.path.join(company_folder, "Research_Packet.md")
    if os.path.exists(json_path):
        return load_file(json_path), "json"
    if os.path.exists(md_path):
        return load_file(md_path), "md"
    return None, ""


def _parse_research_blob(raw: str, fmt: str) -> Dict[str, Any]:
    if not raw:
        return {}
    if fmt == "json":
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return {"_raw_markdown": raw}


def _dig(data: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, list) and val:
            first = val[0]
            if isinstance(first, str):
                return first.strip()
            if isinstance(first, dict):
                return str(first.get("text") or first.get("title") or first)[:300]
    nested = data.get("module_a") or data.get("company_dna") or {}
    if isinstance(nested, dict):
        for key in keys:
            v = nested.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
    raw = data.get("_raw_markdown", "")
    if raw:
        for label, pattern in (
            ("mission", r"(?:mission|values?)[:\s]+(.{40,220})"),
            ("problem", r"(?:problem space|pain)[:\s]+(.{40,220})"),
        ):
            m = re.search(pattern, raw, re.I)
            if m:
                return m.group(1).strip()
    return ""


def _resume_bullets(company_folder: str, limit: int = 2) -> List[str]:
    resume_path = os.path.join(company_folder, "Resume.md")
    if not os.path.exists(resume_path):
        manifest_path = os.path.join(company_folder, "draft_manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)
            ids = manifest.get("bullet_claim_ids") or []
            return [f"[Claim {cid}]" for cid in ids[:limit]]
        return []
    with open(resume_path, encoding="utf-8") as f:
        text = f.read()
    bullets = []
    for line in text.splitlines():
        if line.strip().startswith("*"):
            bullets.append(strip_bridge_prefix(line.lstrip("* ").strip()))
        if len(bullets) >= limit:
            break
    return bullets


def _reverse_questions(data: Dict[str, Any]) -> List[str]:
    challenges = data.get("key_challenges") or data.get("challenges")
    if isinstance(challenges, list):
        qs = []
        for c in challenges[:3]:
            if isinstance(c, str):
                qs.append(f"How is the team addressing {c.rstrip('.')}?")
            elif isinstance(c, dict):
                title = c.get("title") or c.get("challenge") or ""
                if title:
                    qs.append(f"How is the team addressing {title}?")
        if len(qs) >= 2:
            return qs[:4]
    return list(DEFAULT_REVERSE_QUESTIONS)


def build_template_cheat_sheet(
    display_name: str,
    research: Dict[str, Any],
    bullets: List[str],
    jd_themes: Optional[List[str]] = None,
) -> str:
    mission = _dig(research, "mission", "core_mission", "company_mission", "values")
    problem = _dig(research, "problem_space", "pain", "problem")
    theme = (jd_themes or research.get("priority_themes") or [])[:1]
    theme_line = theme[0] if theme else "platform product delivery"

    pitch = (
        f"I am a platform-oriented Product Manager with experience stabilizing data-heavy B2B systems, "
        f"roadmap execution, and cross-functional delivery. This aligns with {display_name}'s focus on "
        f"{theme_line}."
    )
    if mission:
        pitch += f" Your stated mission around {mission[:120]} is a strong fit for how I prioritize outcomes."

    why = (
        f"{display_name} is operating in a space where {problem[:200] or 'reliable product execution matters'} "
        f"I have shipped comparable platform and data-integrity work and want to apply that pattern here."
    )

    proof_lines = bullets[:2] or [
        "Led platform stabilization and roadmap execution for enterprise SaaS workloads.",
        "Partnered with engineering on data integrity, migrations, and measurable customer outcomes.",
    ]

    questions = _reverse_questions(research)

    sections = [
        "# Interview Cheat Sheet",
        f"**Company:** {display_name}",
        "",
        "## Tell me about yourself (60–90 seconds)",
        pitch,
        "",
        "## Why this company / role?",
        why,
        "",
        "## Proof stories (resume-backed)",
    ]
    for i, b in enumerate(proof_lines, 1):
        sections.append(f"{i}. {b}")
    sections.extend([
        "",
        "## Handling ambiguity and stability",
        "Frame legacy constraints as prioritization problems: protect revenue paths, sequence migrations, "
        "and ship incremental reliability wins with clear metrics.",
        "",
        "## Reverse-interview questions",
    ])
    for q in questions:
        sections.append(f"- {q}")
    return "\n".join(sections) + "\n"


def _patch_manifest_source(company_folder: str, source: str) -> None:
    manifest_path = os.path.join(company_folder, "draft_manifest.json")
    if not os.path.exists(manifest_path):
        return
    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
        manifest["cheat_sheet_source"] = source
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
    except (json.JSONDecodeError, OSError):
        pass


def generate_cheat_sheet(company_name: str, display_name: Optional[str] = None) -> Optional[str]:
    """
    Generate Interview_Cheat_Sheet.md. Returns source: template | llm | skip | None.
    """
    mode = os.environ.get("CHEAT_SHEET_MODE", "template").lower()
    if mode not in CHEAT_SHEET_MODES:
        mode = "template"

    display = (display_name or company_name).strip()
    company_folder = _company_folder(company_name)
    raw, fmt = _load_research(company_folder)

    if mode == "skip" or not raw:
        if not raw:
            print(f"    [Cheat sheet] No research packet for {company_name} — skip")
        return "skip" if mode == "skip" else None

    research = _parse_research_blob(raw, fmt)
    jd_themes = []
    manifest_path = os.path.join(company_folder, "draft_manifest.json")
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, encoding="utf-8") as f:
                prof = json.load(f).get("jd_profile") or {}
            jd_themes = prof.get("priority_themes") or []
        except (json.JSONDecodeError, OSError):
            pass

    bullets = _resume_bullets(company_folder)
    output_path = os.path.join(company_folder, "Interview_Cheat_Sheet.md")

    if mode == "template":
        print(f"    [Cheat sheet] Building template cheat sheet for {display}...")
        body = build_template_cheat_sheet(display, research, bullets, jd_themes)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(body)
        print(f"    [Success] Saved template cheat sheet to {output_path}")
        _patch_manifest_source(company_folder, "template")
        return "template"

    work_exp = load_file(WORK_EXP_FILE)
    prompt = f"""
You are an elite interview coach for a Product Manager. Generate a Run of Show / Interview Cheat Sheet
mapping GROUND TRUTH experience to COMPANY RESEARCH.

GROUND TRUTH (Jason Taylor):
{work_exp}

COMPANY & ROLE RESEARCH:
{raw}

Structure: Tell me about yourself; Why this company; Key experience bridge; Ambiguity/stability; Reverse questions.
Professional, direct, grade 10-12 reading level. No em-dashes. Output strictly Markdown.
"""
    print(f"    [Cheat sheet] LLM mode for {display}...")
    result = call_llm_stage(
        "bullet",
        system_prompt="You are the Cheat Sheet Engine. Output Markdown strictly.",
        user_prompt=prompt,
        temperature=0.2,
    )
    if result:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"    [Success] Saved LLM cheat sheet to {output_path}")
        _patch_manifest_source(company_folder, "llm")
        return "llm"

    if local_only_mode():
        print("    [Cheat sheet] LLM empty — falling back to template")
        body = build_template_cheat_sheet(display, research, bullets, jd_themes)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(body)
        _patch_manifest_source(company_folder, "template")
        return "template"

    print("    [Error] LLM cheat sheet returned empty")
    return None


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python generate_cheat_sheet.py 'Company Name' [display name]")
        sys.exit(1)
    disp = sys.argv[2] if len(sys.argv) > 2 else None
    generate_cheat_sheet(sys.argv[1], display_name=disp)
