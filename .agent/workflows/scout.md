---
description: Scout for new PM roles on LinkedIn (Mid-level, Remote/SD)
---

# Scout Workflow

Whenever the user runs the `/scout` command (or when triggered automatically by the `/evaluate` loop), you will use the browser subagent to fetch new jobs from LinkedIn.

## Core Rules:
1. **Pipeline Quota:** The ultimate goal of calling `/scout` is to feed the `/evaluate` pipeline until there are exactly **5 completed application folders** sitting inside the `submissions/` directory.
2. **Duplicate Prevention:** Before passing jobs back, the subagent MUST check `data/scouted_jobs_log.txt` to ensure the company has not already been pulled.

## Execution Steps: to Execute:

1. Read the search terms, location, and target role from `data/candidate_preferences.json`.
2. Invoke the `browser_subagent` tool with the following task instructions:
   "Navigate to LinkedIn Jobs. Use the 'search_terms' and 'location_preference' found in `data/candidate_preferences.json`. Apply the 'Past week' filter for date posted. Browse the results. For each qualifying role, first check the file `data/scouted_jobs_log.txt` to see if the company/role was already processed. If it is in the log, skip it. If it is new, copy the full job description text. Save the text into a new file in the `jobs/` directory named `jobs/[Company Name] - [Role Title].txt`. IMPORTANT: Ensure the very first line of this file is 'URL: [The direct LinkedIn Job URL]'. Then, append the '[Company Name] - [Role Title]' string to the `data/scouted_jobs_log.txt` file. Do this until you have 3-4 NEW jobs."
2. Wait for the browser subagent to complete.
3. Notify the user of the jobs that were successfully downloaded and ask if they'd like to run the batch pipeline.
