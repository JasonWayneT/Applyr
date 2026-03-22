# Skill: Scout (LinkedIn Sourcing)

## 0) Goal
Proactively source and extract job descriptions from LinkedIn that match Jason's specific transition profile and filter criteria using the browser subagent.

## 1) Execution Logic
When instructed to "scout", "run scout", or find jobs, execute the `browser_subagent` tool with the following comprehensive Task instructions:

### Search Criteria
- **Target URL:** `https://www.linkedin.com/jobs/`
- **Keywords:** `Product Manager NOT Senior`
- **Location:** `Remote, United States` OR `San Diego, CA`
- **Filters to Apply:**
  - Date Posted: **Past Week**
  - Experience Level: **Mid-Senior level** (Specifically exclude Entry level, Internship, Director, and Executive).

### Extraction Protocol
1. Command the browser subagent to execute the search combining the parameters above.
2. The subagent should scroll through the search results and click on individual job postings.
3. For each posting, check for immediate hard disqualifiers (e.g., hardware/firmware focus, 10+ years experience required, purely marketing/SEO).
4. If it appears to be a viable software/platform Product Manager role, check if the `[Company] - [Role]` is already listed in `C:\Users\Jason\Desktop\Jason\Projects\AntiGravity Projects\JobAgent\data\scouted_jobs_log.txt` (read the file if it exists). If it is in the log, SKIP IT and move to the next job.
5. If it is new, extract the entire text of the Job Description.
6. Create a new file in the `jobs/` directory using the naming convention: `[Company] - [Role].txt` (e.g., `jobs/Spotify - Product Manager.txt`).
7. Paste the full extracted text into the file.
8. Append the `[Company] - [Role]` string to `data/scouted_jobs_log.txt` so it is not processed again in future runs. Create the file if it doesn't exist.
9. Repeat this process until 3 to 5 high-quality, non-duplicate job descriptions have been successfully saved to the `jobs/` folder.

## 2) Output Rules
- After the browser subagent successfully saves the files, trigger a `notify_user` response summarizing the companies and roles found.
- Ask the user if they would like to proceed with running the batch evaluation pipeline (`scripts/batch_pipeline.py`) on the newly scouted roles.
