# FEAT-008-settings-modal: Premium Claude-Style Settings Overlay Modal

## 1. Context & Business Value
To align the Applyr platform design with premium AI products (such as Anthropic Claude), the settings configuration should transition from a static profile sub-tab to a high-fidelity, absolute-positioned modal overlay. This modal provides a single control room for theme styling, API keys, usage limits tracking, and privacy settings.

## 2. Requirement Mapping
- **Requirement ID:** `FR-041`
- **Acceptance Criterion:** `AC-042`

## 3. Visual & Functional Specifications

### A. Backdrop Blur & Layout
- Darkened `backdrop-blur-md` overlay container wrapping the settings modal.
- Dual-pane layout inside the modal:
  - **Left Pane (Navigation):** Vertically stacked, clean navigation items (General, Account, Privacy, Billing, Usage, Capabilities, Connectors, LLM Engine).
  - **Right Pane (Content Workspace):** Dynamic scrolling viewport rendering content for each selected tab.

### B. Usage Limits Tracker (Usage Tab)
Replicates the Claude usage panel with clean progress bars and dynamic usage indicators:
- **Plan usage limits**: Displays "Pro" status badge.
- **Current session**: Shows "Resets in 4 hr 30 min" progress indicator (e.g., 4% used).
- **Weekly limits**:
  - **All models**: Resets Wed 5:00 AM (25% used progress bar).
  - **Agent Writing & Auditing**: Tracks weekly edits/audits (e.g., 12 / 50 used).
- **Daily included routine runs**: Tracks background Selenium crawls (e.g., 0 / 5 run).
- **Extra usage**: An active interactive toggle to allow additional local compute runs.

### C. Unified LLM Engine Selector
Migrates the Multi-LLM provider selection directly into the modal for seamless, centralized setup.
