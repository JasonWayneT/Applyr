# Claim Verifier (Anti-Hallucination Gate)

After generating outputs, verify claims.

FAIL if outputs include:
- PM people management (manage PMs, hire PMs, org design)
- P&L ownership claims
- ML/LLM model shipping or ML roadmap ownership
- Consumer mobile app product ownership
- Hands-on coding as core responsibility
- Metrics not present in Resume.md or workExperience.md
- Tools/tech not present in Resume.md/workExperience.md unless clearly stated in JD AND phrased carefully

Verifier output must be:
Verifier: PASS/FAIL
Issues:
- [quote offending sentence]
- Fix: [what to change]

If FAIL:
- Revise outputs once and re-check.
- If still FAIL, output FAIL with remaining issues.
