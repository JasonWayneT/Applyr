# Applyr Release Notes Template (Firefox Style)

Use this template when appending new entries to the Release Ledger inside `PRODUCT_CAPABILITIES_AND_RELEASE_NOTES.md`.

Copy and paste the markdown below, substituting the placeholders `[Your Version]`, `[Your Date]`, and relevant sections.

```markdown
### [Version Number]
Applyr Release
[Month DD, YYYY]

Version [Version Number], first offered to local users on [Month DD, YYYY]

Previous
Applyr [Previous Version]

Next
Applyr [Next Version or "Planned"]

New
[List any new user-facing features or major modules added. Include a descriptive sentence or paragraph.]

![[Image Caption]](file:///path/to/your/screenshot.png)

Fixed
[List any bugs, Windows parameter limits, CLI character escaping issues, or execution hangs that were resolved.]

Changed
[List any structural, styling, or interface adjustments made to existing components or pipelines.]

Developer
[List any background scripts, APIs, or developer-facing tool improvements (e.g., compile scripts, db tables).]
```

## Guidelines for Consistent Release Notes:
1. **User-Friendly Voice:** Write the notes in an active, direct, and slightly technical but highly readable voice (e.g., "We have integrated..." rather than "The system added...").
2. **Include Visual Evidence:** Whenever a release introduces visual interface elements, capture a screenshot and link it inline directly under the `New` section using absolute file URIs.
3. **Keep Sections Discrete:** Avoid mixing fixes under new features. If something was repaired, list it under `Fixed`. If a feature was updated or relocated, list it under `Changed`.
