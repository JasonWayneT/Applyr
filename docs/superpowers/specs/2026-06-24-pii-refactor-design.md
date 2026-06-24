# Design Spec: PII Refactor and Isolation

- **Date**: 2026-06-24
- **Objective**: Remove PII details from the tracked `CLAUDE.md` and relocate them to gitignored local files (`data/workExperience.md`) and the tracked template/mock example (`data/workExperience.example.md`).

## Architecture & Data Flow

1. **Active/Real PII**: Stored locally in the gitignored SQLite database (`jobagent.sqlite`) and under Section 1.0 of the gitignored [data/workExperience.md](file:///c:/Users/Jason/Desktop/Jason/Resource/CodeProjects/Applyr/data/workExperience.md).
2. **Mock/Template PII**: Stored in [data/workExperience.example.md](file:///c:/Users/Jason/Desktop/Jason/Resource/CodeProjects/Applyr/data/workExperience.example.md) for template reference.
3. **Agent Guidance**: [CLAUDE.md](file:///c:/Users/Jason/Desktop/Jason/Resource/CodeProjects/Applyr/CLAUDE.md) updated to point agents to load profile/positioning details from the gitignored local files instead of hardcoding any values.

## Proposed Changes

### 1. `CLAUDE.md`
- Remove real/placeholder email, phone, and linkedin references.
- Add guidance telling agents to look at `data/workExperience.md` or `jobagent.sqlite` for candidate contact info.

### 2. `data/workExperience.md`
- Add Section 1.0 containing:
  - Name: Jason Taylor
  - Email: [REDACTED_EMAIL]
  - Phone: [REDACTED_PHONE]
  - LinkedIn: https://www.linkedin.com/in/redacted-linkedin-slug/
  - Portfolio: Taylorbuilt.me

### 3. `data/workExperience.example.md`
- Add Section 1.0 containing mock values:
  - Name: John Doe
  - Email: john.doe@example.com
  - Phone: (555) 019-9238
  - LinkedIn: https://www.linkedin.com/in/johndoe/
  - Portfolio: johndoe.com
