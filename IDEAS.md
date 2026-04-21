# JobAgent Future Ideas & Roadmap

This file is to track ideas and enhancements that we want to implement in the future.

## Features to Implement
- [ ] **Geographic Filtering:** Implement proper location parsing from the OpenPostings database to support UI dropdowns for "Fully Remote", "Hybrid", and "On-site" filtering.
- [ ] **City-Level Filtering:** Expand the location filter from country-level (USA) down to specific city support.
- [ ] **Dynamic Search UI:** Build out the top-bar search experience in the "Find new jobs" view to allow runtime filtering of the firehose.
- [ ] **LLM Integration:** Connect the "Prepare" pipeline stages to OpenAI/Gemini to actually generate the Cover Letters and Resumes dynamically.
- [ ] **Automated Cron Scheduling:** Move the "Manual Sync" trigger to a true background Cron job that runs daily at 4:00 AM.
- [ ] **Smart Silent Period Tracking:** Re-implement logic tracking how many days a company has been "silent" after an application, hooking it to actual DB timestamps.
- [ ] **Last Mile Handheld Apply:** Add functionality to pre-fill application forms or copy specific role assets to the clipboard when the "Apply" link is clicked.
- [ ] **Granular Interview Tracking:** Expand the "In Conversation" status into sub-stages (Recruiter, Manager, Case Study, Panel) with tailored preparation guides for each.

