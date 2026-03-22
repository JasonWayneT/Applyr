# Skill: Researcher (v2.1, API-Integrated)

## 0) Goal
Execute the `scripts/research_engine.py` to gather structured company intelligence while preventing redundant API calls.

## 1) Execution Logic
When a Job Description is provided:

### Phase 1: Local Cache Check
- Check the directory: `submissions/[company_name_slug]/`.
- If `Research_Packet.json` already exists AND is less than 7 days old, LOAD the file and skip to Phase 3.
- If the file does not exist or is stale, proceed to Phase 2.

### Phase 2: API Trigger
- **Command:** Generate and propose the following terminal execution:
  `python3 scripts/research_engine.py "[extracted_company_name]" "[extracted_role_title]"`
- **Constraint:** Do not proceed until the script confirms the creation of `Research_Packet.json`.

### Phase 3: Intelligence Mapping
- Parse the JSON data against `data/workExperience.md`.
- Identify the "Bridge Points" where Jason’s platform/data history solves the company's specific "Headaches" identified by the API.

## 2) Output Rules
- If Phase 2 is required: Output ONLY the terminal command in a code block.
- If Phase 3 is reached: Output a "Strategic Research Summary" and signal the Writer Agent to begin.