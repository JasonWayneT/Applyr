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
   Extract the `Source URL` from the first line of the original JD file.
   Save this URL and Score into `submissions/[company]/metadata.json`.
   Copy the original JD text into `submissions/[company]/Original_JD.txt`.
   Use your own generation capabilities to write a highly tailored `Resume.md` and `CoverLetter.md`.
   Save these drafted markdown files directly to the submission folder.

5. **Generate PDFs & Intel:**
   Once drafting is complete:
   - Run `python scripts/manual_pdf_gen.py`.
   - Run `python scripts/research-engine.py "[Company]" "Product Manager"` (if research not already present).
   - Run `python scripts/generate_cheat_sheet.py "[Company]"`.

6. **Database Persistence:**
   For every processed job, update `data/job_database.json`:
   - Set status to `Drafted` for YES decisions.
   - Set status to `Rejected` for NO decisions.
   - Update score and folder path fields.

7. **The Pipeline Loop (Target: 5 Applications):**
   After clearing the queue, check the total number of application folders in `submissions/`.
   - If < 5, run `/scout` and repeat.
   - If >= 5, stop and notify user.

8. **Cleanup & Dashboard:**
   - Delete processed `.txt` files from `jobs/`.
   - Run `python scripts/generate_navigator.py`.
