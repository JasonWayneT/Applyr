---
title: Applyr Product Brief
status: draft
created: 2026-06-08
updated: 2026-06-08
---

# Applyr

> A locally-hosted job search platform that generates tailored resumes and cover letters from a verified, complete work history — so every claim in every document you submit is true, and nothing relevant gets left on the table.

---

## Executive Summary

The project started from a real job search in early 2026. The builder identified a gap in existing AI resume tools: they treat a single resume as the source of truth, which leaves relevant experience buried and opens the door to AI hallucination. Applyr was built to close that gap — dogfooded daily through an active search and validated against real application outcomes.

The platform has three layers: a background scout that surfaces qualified jobs without wasting AI tokens on junk, a tailoring engine that generates targeted resumes and cover letters from the user's full work history, and a tracker for the entire application journey. It runs locally, privately, and — on the Ollama path — for free.

---

## The Problem

Job seekers applying to multiple roles face a compound problem:

**One resume is a lossy source.** A resume is an edited snapshot — written for the last job you applied for, not this one. Experiences that are directly relevant to *this* JD were never written down, or were cut for space. The applicant is working from a constrained starting point.

**AI tools make it worse, not better.** Every major AI resume tool fills gaps. If your resume doesn't mention a skill the JD asks for, the tool invents plausible-sounding experience. Job seekers who rely on these tools risk getting caught in interviews, or worse — landing roles they fabricated their way into.

**Volume without quality.** The instinct in a tough job market is to apply faster, to more jobs. The tools that enable speed sacrifice the integrity of the output.

The result: candidates apply with documents that are simultaneously under-representative of their real experience and over-representative of skills they don't have.

---

## The Solution

Applyr is a locally-hosted full-stack web application built around a single constraint: the AI only works with what you've verified as true.

**Scout.** A background engine scrapes job boards and applies pre-AI filtering — keyword rules, salary range, location — to surface qualified roles without burning tokens on garbage. The firehose gets filtered before AI ever sees it.

**Tailor.** The user inputs a job description. The system draws from their complete, structured work history (not their current resume) and generates a targeted resume and cover letter. Every bullet, every claim, every phrasing traces back to a real entry in the work history file. The AI writes prose; it cannot invent facts.

**Track.** Every application — role, company, status, response, follow-up — is logged in one place so nothing falls through the cracks.

The stack runs on the user's machine: React + Vite + TypeScript frontend, Node/Express backend, SQLite with FTS5 and vector embeddings for local semantic matching, and Ollama for local LLM inference. No data leaves the hard drive.

---

## What Makes This Different

Most AI resume tools treat the resume as the source of truth. Applyr treats the **complete work history** as the source of truth — a structured record of everything the user has done, from which each application draws the most relevant subset.

This design choice has two consequences:

- **Nothing gets fabricated.** The AI has a strict source. It elevates and organizes what's real; it cannot fill gaps with invented experience.
- **Nothing gets missed.** A project that was cut from the current resume might be exactly what this JD needs. The system finds it because the system has access to the full picture.

The prose goal matters here too: the constraint is on *what facts* the AI can use, not on *how* it writes. The output should be polished and targeted — a strong first draft the user reviews and refines before submitting. Human review before submission is expected and by design.

**On competition, honestly:** Teal, Rezi, Kickresume, and similar tools could build this architecture. They haven't — because the majority of users want AI to fill gaps, not constrain itself to what's true. Applyr bets on a different user: one who values integrity of output over inflated claims, and who has enough real experience to make that bet worthwhile.

---

## Who This Serves

**Primary user:** Anyone actively job searching who has real experience to draw from — whether that's 15 years in corporate roles, a mix of freelance and volunteer work, or early-career experience including extracurriculars, community organizing, and transferable skills.

The system doesn't discriminate by credential type. A structured work history that includes Girl Scouts project leadership, a college capstone, a part-time job, and a volunteer coordination role is a legitimate source of truth. The tailoring engine finds what's relevant to the JD — regardless of whether it would appear on a conventional resume.

This matters most for people with non-traditional backgrounds. A standard resume template buries transferable skills by design — the format wasn't built for them. The full work history approach surfaces exactly what those applicants need surfaced.

**What this user is NOT:** Someone looking for AI to exaggerate or fabricate credentials. That user is explicitly not the target, and the system is architected to prevent it.

---

## Success Criteria

| Criterion | Status |
|---|---|
| Achieved screener-stage interviews during Jason's own job search | Yes |
| Zero hallucination — every claim traces to verified work history | Architectural guarantee |
| All processing local — no data leaves the user's machine | Yes |
| Generated prose is polished enough to serve as a strong first draft for human review | Target; actively tuned |
| Job scout surfaces qualified roles without manual review overhead | Yes |
| Application pipeline tracked end-to-end | Yes |

---

## Scope

**In scope:**
- Job discovery and pre-AI filtering (scout engine)
- Resume and cover letter generation from full work history
- Application tracking (status, responses, follow-ups)
- Local LLM inference via Ollama; cloud LLM as fallback

**Out of scope (by design):**
- Interview preparation
- Salary negotiation tooling
- Reference management
- Multi-user or SaaS deployment

---

## Vision

The cost of tailoring a resume should be zero — in time and money. The roadmap points toward locally-run models (Ollama as default) so generation is free, private, and runs without an internet connection. Cloud LLM remains an option for users who want higher output quality and are willing to pay API costs.

The longer arc: every knowledge worker should maintain a complete, structured work history — not a resume, which is always a partial snapshot — and generate targeted applications on demand, for any role, in minutes, with no risk of misrepresentation.

The resume that gets you the interview should be the one that reflects who you actually are.
