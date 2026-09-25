#!/usr/bin/env python3
"""CR-114: Stage 0 evidence retrieval includes AI side corpus when relevant."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from evidence_scale import (
    build_evidence_context,
    retrieval_coverage,
    _should_include_ai_corpus,
)


_WE = """# Professional Experience
Built B2B SaaS roadmaps and SQL reporting for a media monitoring platform.
Owned sequencing with engineering on customer-facing data work.
"""

_AI = """# ACC-401 AI tooling
Hands-on agentic coding pipeline with LLM applications, MCP tools, and AI agents.
"""

_AI_LINE = (
    "Hands-on experience building or shipping with AI agents, "
    "LLM applications, or agentic coding tools."
)


class EvidenceContextTests(unittest.TestCase):
    def test_ai_query_pulls_side_corpus_instead_of_we_prefix(self) -> None:
        excerpt = build_evidence_context(
            _AI_LINE,
            _WE,
            k=4,
            max_chars=3000,
            extra_corpus=_AI,
        )
        self.assertIn("agentic", excerpt.lower())
        self.assertIn("MCP", excerpt)

    def test_empty_extra_corpus_keeps_we_only(self) -> None:
        excerpt = build_evidence_context(
            _AI_LINE,
            _WE,
            k=4,
            max_chars=3000,
            extra_corpus="",
        )
        self.assertNotIn("MCP", excerpt)
        self.assertNotIn("agentic coding", excerpt.lower())

    def test_non_ai_query_does_not_auto_load_side_corpus(self) -> None:
        self.assertFalse(_should_include_ai_corpus("Experience with Jira and SQL"))
        self.assertTrue(_should_include_ai_corpus(_AI_LINE))
        with patch("evidence_scale._load_ai_projects_corpus", return_value=_AI) as load:
            excerpt = build_evidence_context(
                "Experience with Jira and SQL",
                _WE,
                k=4,
                max_chars=3000,
            )
        load.assert_not_called()
        self.assertNotIn("MCP", excerpt)


# Reproduces sitting-1 Acquia false gaps: a huge inventory chunk holds the
# real evidence, a small generic chunk wins Jaccard, window_ok stays True.
_JIRA_LINE = (
    "Proficiency with product management tools such as Jira, Confluence, and Aha!."
)
_EXEC_LINE = (
    "Executive presence: Strong verbal communication and the ability to "
    "communicate upward. You can brief an executive, defend a decision with "
    "data, and move a room to a decision."
)
_STARVE_WE = """# Professional Experience

### Factual Anti-Claims
Do not claim product management tools generally. Never invent operational
delivery. Product management work is documented elsewhere.

### 2.2 Verified Cross-Functional Partners
| Executive / Presidential Leadership | Presented the quarterly roadmap to 200-300 people including CEOs |
Jira is used for intake with engineering.

### 5.1 Cision
Navigated three executive team transitions. Roadmap ownership continued
through executive turnover. Product management tools are mentioned generally.

#### Approved Accomplishments Inventory
""" + ("padding product management tools operational delivery " * 1800) + """
ACC-119 Tools Used: Confluence, Jira, SQL.
ACC-108 Built a weighted priority-score formula over inbound Jira issues.
ACC-109 Presenting the quarterly roadmap to approximately 200-300 stakeholders
including CEOs and executive leadership.
"""

_WE_PATH = Path(__file__).resolve().parents[1] / "data" / "workExperience.md"


class RetrievalCoverageTests(unittest.TestCase):
    def test_jira_excerpt_contains_confluence_and_jira(self) -> None:
        excerpt = build_evidence_context(
            _JIRA_LINE, _STARVE_WE, k=4, max_chars=3000, extra_corpus="",
        )
        low = excerpt.lower()
        self.assertIn("jira", low)
        self.assertIn("confluence", low)
        ok, missing = retrieval_coverage(_JIRA_LINE, excerpt, _STARVE_WE)
        self.assertTrue(ok, missing)

    def test_exec_excerpt_contains_briefing_evidence(self) -> None:
        excerpt = build_evidence_context(
            _EXEC_LINE, _STARVE_WE, k=4, max_chars=3000, extra_corpus="",
        )
        low = excerpt.lower()
        self.assertTrue(
            "200-300" in low or "200 to 300" in low,
            excerpt[:400],
        )
        self.assertTrue("presented" in low or "presenting" in low)
        ok, missing = retrieval_coverage(_EXEC_LINE, excerpt, _STARVE_WE)
        self.assertTrue(ok, missing)

    def test_coverage_ok_false_when_distinctive_tokens_starved(self) -> None:
        starved = (
            "### Factual Anti-Claims\n"
            "Do not claim product management tools generally.\n"
        )
        ok, missing = retrieval_coverage(_JIRA_LINE, starved, _STARVE_WE)
        self.assertFalse(ok)
        self.assertTrue({"jira", "confluence"} & set(missing))

    @unittest.skipUnless(_WE_PATH.exists(), "gitignored workExperience.md")
    def test_acquia_live_we_jira_and_exec(self) -> None:
        we = _WE_PATH.read_text(encoding="utf-8", errors="replace")
        jira_excerpt = build_evidence_context(
            _JIRA_LINE, we, k=4, max_chars=3000, extra_corpus="",
        )
        self.assertIn("jira", jira_excerpt.lower())
        self.assertIn("confluence", jira_excerpt.lower())
        jira_ok, jira_missing = retrieval_coverage(
            _JIRA_LINE, jira_excerpt, we, extra_corpus="",
        )
        self.assertTrue(jira_ok, jira_missing)

        exec_excerpt = build_evidence_context(
            _EXEC_LINE, we, k=4, max_chars=3000, extra_corpus="",
        )
        low = exec_excerpt.lower()
        self.assertTrue("200-300" in low or "200 to 300" in low, exec_excerpt[:500])
        self.assertTrue("presented" in low or "presenting" in low)
        exec_ok, exec_missing = retrieval_coverage(
            _EXEC_LINE, exec_excerpt, we, extra_corpus="",
        )
        self.assertTrue(exec_ok, exec_missing)


if __name__ == "__main__":
    unittest.main()
