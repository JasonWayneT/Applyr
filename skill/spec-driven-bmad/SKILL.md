---
name: spec-driven-bmad
description: "Use when the user wants BMAD outputs, PRDs, epics, stories, architecture docs, UX notes, or change requests converted into Spec Driven Development artifacts before coding. Enforces requirement IDs, traceability, change-first documentation, and agent coding rules."
license: MIT
metadata:
  version: '1.0'
---

# Spec Driven BMAD

## When to use this skill

Use this skill when the user wants to:
- Scaffold a new project from BMAD documentation.
- Convert BMAD outputs into implementation-ready specs.
- Maintain requirement IDs and traceability across code, tests, and documentation.
- Add a repeatable workflow for feature changes, bug fixes, refactors, or design updates.

## Core principle

The documentation chain is the source of truth. Code is an implementation of accepted requirements, specs, decisions, and tests.

## Required workflow

1. Read or create the project constitution.
2. Import BMAD outputs into a BMAD intake file.
3. Normalize the BMAD outputs into a requirements registry.
4. Assign stable IDs to requirements, acceptance criteria, tasks, tests, bugs, and decisions.
5. Create or update feature specs and design specs.
6. Update the traceability matrix.
7. Create implementation tasks that cite requirement IDs.
8. Only then modify code.

## Change-first rule

When the user asks for a change:
1. Create or update a `CR-*`.
2. Link affected requirements.
3. Add or update acceptance criteria.
4. Update traceability.
5. Then implement.
