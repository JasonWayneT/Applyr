#!/usr/bin/env python3
"""
Dispatcher script for Subagent-Driven Development (SDD).
Invokes the local model or configured primary LLM with specialized templates for:
- Implementer Subagents
- Spec Compliance Reviewers
- Code Quality Reviewers
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

# Reconfigure stdout/stderr to utf-8 to prevent encoding crashes on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure scripts directory is in path for utils imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import call_llm


def load_template(filename: str) -> str:
    path = os.path.join("C:\\Users\\Jason\\.gemini\\config\\\\plugins\\\\superpowers\\\\skills\\\\subagent-driven-development", filename)
    if not os.path.exists(path):
        # Fallback to local skills search path if plugin path doesn't exist
        path = os.path.join(os.path.expanduser("~"), ".gemini", "config", "plugins", "superpowers", "skills", "subagent-driven-development", filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main() -> int:
    parser = argparse.ArgumentParser(description="SDD Subagent Dispatcher")
    parser.add_argument("--type", choices=["implementer", "spec-reviewer", "quality-reviewer"], required=True)
    parser.add_argument("--task-num", type=int, required=True)
    parser.add_argument("--task-desc", required=True, help="Full description of the task")
    parser.add_argument("--context", default="", help="Context/Scene-setting for the task")
    parser.add_argument("--report", default="", help="Implementer's report (for reviewers)")
    parser.add_argument("--diff", default="", help="Git diff content (for code quality review)")
    args = parser.parse_args()

    diff_content = args.diff
    if not diff_content:
        try:
            staged = subprocess.run(["git", "diff", "--cached"], capture_output=True, text=True, encoding="utf-8")
            unstaged = subprocess.run(["git", "diff"], capture_output=True, text=True, encoding="utf-8")
            diff_content = (staged.stdout or "") + "\n" + (unstaged.stdout or "")
            diff_content = diff_content.strip()
        except Exception as e:
            diff_content = f"Could not fetch git diff: {e}"

    print(f"--- Dispatching SDD Subagent: {args.type} for Task {args.task_num} ---")

    system_prompt = ""
    user_prompt = ""

    if args.type == "implementer":
        template = load_template("implementer-prompt.md")
        system_prompt = "You are an AI software developer implementing a specific task. Focus purely on implementation, code writing, and self-review."
        
        # Build prompt from template
        user_prompt = (
            f"You are implementing Task {args.task_num}.\n\n"
            f"## Task Description\n\n{args.task_desc}\n\n"
            f"## Context\n\n{args.context}\n\n"
            f"Please output a detailed report status (DONE | BLOCKED | NEEDS_CONTEXT), what you plan to change, and the exact code implementation for this task."
        )

    elif args.type == "spec-reviewer":
        template = load_template("spec-reviewer-prompt.md")
        system_prompt = "You are a Spec Compliance Reviewer verifying that the implemented code matches requirements exactly (nothing more, nothing less)."
        
        user_prompt = (
            f"You are reviewing Task {args.task_num} spec compliance.\n\n"
            f"## What Was Requested\n\n{args.task_desc}\n\n"
            f"## What Implementer Claims They Built\n\n{args.report}\n\n"
            f"## Git Diff / Actual Code Built\n\n{diff_content}\n\n"
            f"Please verify compliance and respond with:\n"
            f"- ✅ Spec compliant\n"
            f"- ❌ Issues found: [list specifically]"
        )

    elif args.type == "quality-reviewer":
        # Load the base reviewer template which points to code-reviewer.md
        reviewer_template = load_template("code-quality-reviewer-prompt.md")
        # Load the code-reviewer template
        base_template_path = os.path.join("C:\\Users\\Jason\\.gemini\\config\\plugins\\superpowers\\skills\\requesting-code-review\\code-reviewer.md")
        if not os.path.exists(base_template_path):
            base_template_path = os.path.join(os.path.expanduser("~"), ".gemini", "config", "plugins", "superpowers", "skills", "requesting-code-review", "code-reviewer.md")
        
        with open(base_template_path, "r", encoding="utf-8") as f:
            code_reviewer_template = f.read()

        system_prompt = "You are a Senior Code Reviewer evaluating implementation code quality, separation of concerns, scalability, and tests."
        
        user_prompt = code_reviewer_template.format(
            DESCRIPTION=args.report,
            PLAN_OR_REQUIREMENTS=f"Task {args.task_num}: {args.task_desc}",
            BASE_SHA="BASE",
            HEAD_SHA="HEAD",
        ) + f"\n\n## Actual Git Diff to Review:\n\n{diff_content}"

    # Call the local model
    print("Calling local LLM...")
    response = call_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )

    if not response:
        print("Error: Empty response or failure from LLM.")
        return 1

    # Save output to scratch directory
    scratch_dir = "scratch"
    os.makedirs(scratch_dir, exist_ok=True)
    out_file = os.path.join(scratch_dir, f"subagent_task_{args.task_num}_{args.type}.md")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(response)

    print(f"\nResponse saved to {out_file}\n")
    print("=" * 60)
    print(response)
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
