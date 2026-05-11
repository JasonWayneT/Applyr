"""
Implements FR-064: Auto-generates data/workExperience_summary.md from data/workExperience.md.
Spawned as a background process by the server after every experience save.
Uses the configured LLM provider (with fallback chain) — no manual maintenance required.
"""
import os
import sys
from utils import load_file, call_llm, WORK_EXP_FILE, WORK_EXP_SUMMARY_FILE

_SYSTEM_PROMPT = """You are generating a concise scoring brief from a candidate's full work experience document.
This brief is used by an automated job fit scoring engine to evaluate role matches efficiently.
It must be factual and grounded only in what is explicitly stated in the source document.

Output using exactly these headers and no others:

# [Candidate Name] — Scoring Context (Condensed)

## Identity
[1-2 sentences: role type, years of experience, domain, and explicit NOT statements about what they are not]

## Employers
[Bulleted timeline — one line each: Company (years): Title — one sentence of context]

## Core Strengths
[Bulleted list of concrete, demonstrated competencies. No filler words.]

## Key Wins (Grounded Metrics Only)
[Bulleted: **Bold title** — quantified result. Only include wins where a number or metric appears in the source. Skip unquantified wins.]

## Hard Constraints (DO NOT CLAIM)
[Bulleted: things explicitly stated as not true, not owned, or not completed. This section prevents AI hallucination in downstream document generation.]

## Tools & Technologies (Actual, No Inflation)
[Comma-separated. Only tools and systems explicitly named in the source. Do not infer or generalize.]

## Fit Profile
[Exactly 2 sentences: "Strong match for: X." and "Poor match for: Y."]

Strict rules:
- Do not invent, infer, or embellish anything. Every claim must be directly traceable to the source.
- Do not include ACC, VOC, or MET proof codes in the output — they are internal references only.
- Keep total output under 600 words. Brevity is a feature here."""


def generate_summary():
    full_experience = load_file(WORK_EXP_FILE)
    if not full_experience or len(full_experience.strip()) < 100:
        print("workExperience.md is empty or too short to summarize. Skipping.", file=sys.stderr)
        return

    print("[Summary] Generating workExperience_summary.md from workExperience.md...", file=sys.stderr)

    result = call_llm(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=f"Generate the scoring brief from this work experience document:\n\n{full_experience}",
        temperature=0.1,
        provider_override='gemini'
    )

    if not result:
        print("[Summary] LLM call failed. workExperience_summary.md not updated.", file=sys.stderr)
        return

    with open(WORK_EXP_SUMMARY_FILE, 'w', encoding='utf-8') as f:
        f.write(result)

    word_count = len(result.split())
    print(f"[Summary] workExperience_summary.md updated ({word_count} words).", file=sys.stderr)


if __name__ == '__main__':
    generate_summary()
