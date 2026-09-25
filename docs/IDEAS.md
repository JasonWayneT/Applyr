# JobAgent Future Ideas & Roadmap

> **Note (CR-032):** This file is a scratchpad, not the product backlog. Shipped items are struck through. Use GitHub issues for tracked work.

## Shipped (remove from active planning)

- ~~**LLM Integration:** Connect Prepare pipeline to generate cover letters and resumes~~ — implemented (`batch_pipeline`, compose mode).
- Core scout + evaluate + draft via WebApp sync.

## Still open

- [ ] **Geographic Filtering:** Location parsing from OpenPostings for UI dropdowns (Remote / Hybrid / On-site).
- [ ] **City-Level Filtering:** Beyond country-level USA.
- [ ] **Dynamic Search UI:** Runtime filtering in Find new jobs view.
- [ ] **Automated Cron Scheduling:** Daily background sync (e.g. 4:00 AM).
- [ ] **Smart Silent Period Tracking:** Days since application from DB timestamps.
- [ ] **Last Mile Handheld Apply:** Pre-fill or clipboard helpers on Apply click.
- [ ] **Granular Interview Tracking:** Sub-stages under In Conversation.
- [ ] **Cloud Migration:** Turso / Railway / auth — conflicts with constitution `NG-001` unless scope changes.
- [ ] **AI Copywriter rework (`DocumentEditor.tsx`):** currently a free-text rewrite box that sends the whole doc straight to a local Ollama model with no rubric/truth-grounding/claim-provenance checks — bypasses the governed authoring pipeline entirely. Also mislabels itself as gated on a "Gemini API key" when it's actually always-unlocked and always local. Needs a redesign that either routes through the real Stage 1/2 guardrails or is clearly scoped as an unguarded scratch tool.

See [docs/spec/05-change-requests/README.md](docs/spec/05-change-requests/README.md) for formal feature work.
