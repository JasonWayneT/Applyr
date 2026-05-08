import sys
import os
import re
from utils import call_llm

def main():
    if len(sys.argv) < 3:
        print("Error: Missing file path arguments")
        sys.exit(1)

    instruction_path = sys.argv[1]
    text_path = sys.argv[2]

    if not os.path.exists(instruction_path) or not os.path.exists(text_path):
        print("Error: Temporary files do not exist")
        sys.exit(1)

    try:
        with open(instruction_path, "r", encoding="utf-8") as f:
            instruction = f.read().strip()
        with open(text_path, "r", encoding="utf-8") as f:
            markdown_content = f.read().strip()

        system_prompt = (
            "You are an expert resume and cover letter editor.\n"
            "Your task is to edit the provided HTML/Markdown document according to the user's instructions.\n"
            "CRITICAL FORMATTING RULES:\n"
            "1. You MUST keep all HTML tags, wrappers, divs (<div style=\"...\">), and inline-styled headers (<h1 style=\"...\">, <h2 style=\"...\">, <h3 style=\"...\">) exactly as they are. DO NOT strip them or convert them to standard Markdown headings (#).\n"
            "2. DO NOT backslash-escape any characters. Return plain commas, hyphens, and pipes without prefixing them with '\\'.\n"
            "3. Return ONLY the edited document content. Do not include markdown code block fences (```html or ```markdown)."
        )

        user_prompt = (
            f"INSTRUCTION: {instruction}\n\n"
            f"CURRENT MARKDOWN CONTENT:\n"
            f"```markdown\n"
            f"{markdown_content}\n"
            f"```"
        )

        rewritten_text = call_llm(system_prompt, user_prompt)
        if rewritten_text:
            rewritten_text = rewritten_text.strip()
            if rewritten_text.startswith("```"):
                rewritten_text = re.sub(r"^```(?:markdown|html)?\n|```$", "", rewritten_text, flags=re.MULTILINE).strip()
            
            # Save LLM output back to temporary text_path to run style_compliance_guard
            with open(text_path, "w", encoding="utf-8") as f:
                f.write(rewritten_text)
                
            # Execute the style compliance guard to guarantee conformity
            from style_compliance_guard import run_guard
            run_guard(text_path)
            
            # Read the verified, fully compliant text
            with open(text_path, "r", encoding="utf-8") as f:
                verified_text = f.read().strip()
                
            print(verified_text)
        else:
            print("Error: Empty response from LLM", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Error executing AI rewrite: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
