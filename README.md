# JobHuntAgent
Using the new JobAgent v2.5 is simple and fully automated. Here is your step-by-step guide to running the batch pipeline:

1. Drop Job Descriptions into the jobs/ Folder
Instead of pasting job descriptions into a chat interface one by one, you now process them in bulk.

Save any Job Description you want to apply for as a plain text file (

.txt
).
Name the file after the company (e.g., Stripe.txt, OpenAI.txt).
Place these 

.txt
 files directly into the jobs/ folder in your project directory.
Note: I have already created two test files in there (

Acme_Corp.txt
 and 

Globex_Corp.txt
) that you can use to see how the system handles a "Pass" versus a "Fail" before adding your own!

2. Run the Batch Pipeline
Open your terminal, ensure you are in the JobAgent project directory (c:\Users\Jason\Desktop\Jason\Projects\AntiGravity Projects\JobAgent), and run the following command:

bash
python scripts/batch_pipeline.py
3. What Happens Next (The Automation)
Once you hit enter, the agent takes over:

The Context Firewall: It loads your workExperience.md fresh for the first JD.
The Gatekeeper: It scores the JD. If it scores below 72 or hits a Hard Disqualifier (like requiring you to manage PMs), it will print a rejection reason to your terminal and immediately skip to the next file.
Research & Drafting: If it passes the gatekeeper, the system will automatically:
Call Perplexity to research the company.
Use the "Bridge Logic" to confidently translate your Platform wins into Growth outcomes.
Run the Hallucination Guard to ensure no fake metrics slipped in.
Render the final assets as ATS-Optimized PDFs.
4. Collect Your Ready-to-Send Applications
When the script finishes running through all the text files in the jobs/ folder, you will find your final, tailored applications organized automatically.

Navigate to the submissions/ folder. For every job that passed, there will be a new folder named after the company containing:

[Date]_Resume.pdf (Single-column, ATS-optimized)
[Date]_CoverLetter.pdf
The markdown versions and the raw Perplexity research packet, just in case you want to review them.
That's it! Let me know if you want to run a test batch together right now.