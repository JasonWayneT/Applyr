import os
import sys
from utils import load_file, call_llm, SUBMISSIONS_DIR, WORK_EXP_FILE


def generate_cheat_sheet(company_name):
    print(f"  -> Generating Interview Cheat Sheet for {company_name}...")

    company_folder = os.path.join(SUBMISSIONS_DIR, company_name.lower().replace(" ", "_"))
    research_packet_path = os.path.join(company_folder, "Research_Packet.json")

    if not os.path.exists(research_packet_path):
        # Try fall back to Research_Packet.md format
        packet_path_md = os.path.join(company_folder, "Research_Packet.md")
        if os.path.exists(packet_path_md):
            research_data = load_file(packet_path_md)
        else:
            print(f"    [Error] No research data found for {company_name}")
            return
    else:
        research_data = load_file(research_packet_path)

    work_exp = load_file(WORK_EXP_FILE)

    prompt = f"""
    You are an elite interview coach for a Product Manager. Your goal is to generate a 'Run of Show' / Interview Cheat Sheet 
    that maps the candidate's GROUND TRUTH experience to the COMPANY RESEARCH and ROLE.

    GROUND TRUTH (Jason Taylor):
    {work_exp}

    COMPANY & ROLE RESEARCH:
    {research_data}

    INSTRUCTIONS:
    Structure the cheat sheet with these specific sections:
    1. **"Tell me about yourself" (60-90 seconds)**: Tailor the pitch to the company's problem space. Focus on 'Platform PM' framing.
    2. **"Why this company/role?"**: Connect their recent news or transformation goals (from research) to Jason's experience.
    3. **Key Experience Bridge**: Map specific Cision stories (Bellwether, CPRE Infrastructure) to the company's technical challenges.
    4. **Handling Ambiguity & Stability**: How to talk about balancing legacy systems with innovation on small teams.
    5. **Custom Reverse-Interview Questions**: 3-4 high-level technical/strategic questions for the CTO and CEO.

    STYLE: Professional, direct, slightly cynical (no 'hallmark' words). Grade 10-12 reading level. No em-dashes.
    
    Output strictly Markdown.
    """

    result = call_llm(
        system_prompt="You are a professional interview coach. Output high-intent, tailored markdown.",
        user_prompt=prompt,
        temperature=0.3
    )

    if result:
        output_path = os.path.join(company_folder, "Interview_Cheat_Sheet.md")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"    [Success] Saved Cheat Sheet to {output_path}")
    else:
        print(f"    [Error] LLM call returned empty result")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_cheat_sheet.py 'Company Name'")
        sys.exit(1)

    generate_cheat_sheet(sys.argv[1])
