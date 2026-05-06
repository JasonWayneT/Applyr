import sys
import os
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
            "You are an expert resume and cover letter editor. Your task is to edit the provided Markdown document "
            "according to the user's instructions. Keep all existing Markdown headings and formatting styles intact "
            "unless explicitly told to change them. Return ONLY the modified Markdown text. Do not wrap your response "
            "in ```markdown code blocks. Only return the edited content itself."
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
            # Strip any potential markdown wrapper if the model added it anyway
            if rewritten_text.startswith("```markdown"):
                rewritten_text = rewritten_text[11:]
            if rewritten_text.endswith("```"):
                rewritten_text = rewritten_text[:-3]
            
            print(rewritten_text.strip())
        else:
            print("Error: Empty response from LLM")
            sys.exit(1)
    except Exception as e:
        print(f"Error executing AI rewrite: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
