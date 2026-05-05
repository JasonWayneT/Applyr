# Project Constitution

Use this file to preserve project intent across agents, sessions, rebuilds, and refactors.

## Project identity

- Project name: JobAgent (Applyr)
- Product type: Local-first job application automation platform
- Target users: Jason Taylor (Product Manager)
- Primary problem: Manual job hunting is high-effort, low-reward, and prone to "application fatigue" and hallucinated resumes.
- Primary value proposition: Automated discovery and high-fidelity application generation with a "Zero-Hallucination" guarantee.
- Current stage: production

## Operating mode

- Spec mode: standard
- Required requirement categories:
  - Functional: yes
  - Non-functional: yes
  - UX/design: yes
  - Architecture: yes
  - Data: yes
  - Security/privacy: yes
  - Operations: yes
- Default priority scale: P0 | P1 | P2 | Won't have

## Technical defaults

- Frontend: React / Vite / Tailwind CSS
- Backend: Node.js / Express
- Database: SQLite (via better-sqlite3)
- Automation: Python (batch pipeline)
- LLM Providers: Gemini (Google), Perplexity (Search)
- Package manager: npm
- Style system: Applyr Design System (Nature-rooted, soft minimalism)

## Product boundaries

### Goals

- `GOAL-001`: Automate multi-source job scouting (LinkedIn, BuiltIn, OpenPostings).
- `GOAL-002`: Implement deterministic fit scoring to minimize LLM token waste.
- `GOAL-003`: Generate application materials (Resume, Cover Letter) grounded in verified `workExperience.md`.
- `GOAL-004`: Maintain absolute data privacy by running the core engine on `localhost`.
- `GOAL-005`: Provide a real-time dashboard for monitoring the automation pipeline.

### Non-goals

- `NG-001`: Cloud hosting or multi-user access (privacy violation).
- `NG-002`: Direct ATS submission (requires human-in-the-loop for safety).
- `NG-003`: "General purpose" career coaching (focused strictly on PM roles).

## Global quality bar

- Performance: Sub-second UI response; sub-15-minute end-to-end job evaluation.
- Accessibility: Standard WCAG compliance for internal use.
- Security: Zero-knowledge architecture; API keys restricted to local `.env`.
- Reliability: 100% "Context Firewall" success between job iterations.
- Maintainability: SDD-compliant code with full requirement traceability.
- Documentation: Spec-first workflow enforced for all changes.

## Agent constraints

- Agents must update specs before code.
- Agents must cite requirement IDs in tasks and implementation summaries.
- Agents must preserve existing accepted behavior unless a change request says otherwise.
- Agents must record open questions instead of guessing when the decision changes product behavior.
