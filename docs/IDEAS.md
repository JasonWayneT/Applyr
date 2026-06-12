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

See [docs/spec/05-change-requests/README.md](docs/spec/05-change-requests/README.md) for formal feature work.
