---
description: Evaluate all pending jobs in the jobs/ folder and draft materials for the winners
---

# Evaluate Jobs Workflow

When the user runs the `/evaluate` command, you should act as the Job-Fit Decision Engine and Drafting Engine, completely bypassing the need for external Python API scripts.

## Steps to Execute:

1. **Read Core Context:**
   Read `data/workExperience.md` (Ground Truth) and `.agent/rules/job_fit_engine.md` (Decision Matrix) if you do not already have them in your immediate memory.

2. **Load Pending Jobs:**
   List all `.txt` files in the `jobs/` directory. Read the contents of each job description.

3. **Evaluate:**
   For each job, apply the precise gating and scoring criteria from the `job_fit_engine.md`. 
   Determine the Score (0-100) and the Decision (YES/NO).
   Output a short summary report to the user detailing the scores, reasoning, and whether they passed the 72-point threshold.

4. **Draft Materials (For YES decisions only):**
   For every job that scores a YES (>= 72), create a new directory inside `submissions/` named after the company (e.g., `submissions/art_of_problem_solving/`).
   Copy the original JD text into `submissions/[company]/Original_JD.txt`.
   Use your own generation capabilities to write a highly tailored `Resume.md` and `CoverLetter.md` using the precise HTML styling formats found in `data/Resume_Style_Reference.md` and `data/Cover_Letter_Reference.md`.
   Save these drafted markdown files directly to the submission folder.

5. **Generate PDFs:**
   Once the markdown files are saved, run the terminal command `python scripts/manual_pdf_gen.py` to convert all new markdown drafts into clean PDFs.

6. **The Pipeline Loop (Target: 5 Applications):**
   After clearing the queue, check the total number of drafted application folders sitting inside the `submissions/` directory.
   - If the total number of folders is **less than 5**, you MUST automatically run the `/scout` workflow again to pull fresh jobs, and then repeat this `/evaluate` process.
   - Continue this loop continuously until there are exactly 5 ready-to-go application folders in the `submissions/` directory OR until you run out of qualifying LinkedIn opportunities posted in the last 7 days.
   - Once the count hits 5, stop the loop and notify the user that the pipeline is full.

7. **Cleanup:**
   Delete the processed `.txt` files from the `jobs/` directory to keep the queue clean for the next run.
