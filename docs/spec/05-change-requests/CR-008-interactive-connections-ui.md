# CR-008 — Interactive Connections UI Redesign

**Status:** Accepted
**Date:** 2026-05-14
**Author:** Antigravity

## Overview

Redesign the "API or Connections" tab inside `SettingsView` into a unified, interactive accordion-style layout that consolidates LLM Providers and Data Sources under a premium, responsive interface. Key improvements include integrated global searching/filtering, beautiful typography, dynamic collapse/expand interactions for credential management, and dedicated visual icons/badges mirroring the premium UI layout mockup.

## Motivation

- The current card-based layout for LLM settings is statically fully expanded, causing vertical density issues and excessive whitespace.
- Consolidating the credential entry fields beneath an interactive, collapsible list improves interface scan-ability and visual hierarchy.
- Integrated search provides efficient routing when multiple data aggregators or LLMs are available.
- Distinct visual indicators (e.g., CONNECTED vs PRIMARY) need better alignment with the application's soft aesthetic.

## Requirements

| ID | Title | Description |
|----|-------|-------------|
| FR-076 | Accordion-style Connections UI | Replace the current `API or Connections` panel with a unified search-and-accordion layout. One item can be expanded at a time to reveal input fields, while others remain condensed with status tags and quick-action buttons. |
| FR-077 | Integrated Connection Filtering | Add a top-mounted text input acting as a live filter to search across all LLM provider and Data Source names and descriptions in real-time. |

## Non-Functional Requirements

| ID | Description |
|----|-------------|
| DES-002 | Accordion UI elements must use custom micro-animations for fluid collapse/expand operations. |

## Security

| ID | Description |
|----|-------------|
| SEC-005 | All existing debounce and auto-save security isolation logic is preserved; credential data persists natively to the local SQLite DB via the `/api/profile` pipeline. |

## Impact Surface

| File | Change |
|------|--------|
| `src/components/SettingsView.tsx` | Rewrite the `activeTab === 'API or Connections'` render block with active search, state-driven accordion item components, responsive layouts, and updated styling. |
