#!/usr/bin/env python3
"""CR-112 Stories 2.1 + 2.3 — lean default spawn (no WE reload, no per-JD swarm).

Story 2.2 (batch.js) is deferred: `.claude/` is gitignored so that file cannot
land in a normal commit without an ignore carve-out.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_SKILL = _REPO / ".codex" / "skills" / "generate-submission" / "SKILL.md"
_AGENTS = _REPO / "AGENTS.md"


def _stage0(skill: str) -> str:
    start = skill.index("## Stage 0")
    end = skill.index("## Stage 1")
    return skill[start:end]


def _stage1(skill: str) -> str:
    start = skill.index("## Stage 1")
    end = skill.index("## Stage 2")
    return skill[start:end]


def _stage2(skill: str) -> str:
    start = skill.index("## Stage 2")
    end = skill.index("## Stage 3")
    return skill[start:end]


class TestCr112LeanSpawn(unittest.TestCase):
    def setUp(self) -> None:
        self.skill = _SKILL.read_text(encoding="utf-8")
        self.agents = _AGENTS.read_text(encoding="utf-8")

    def test_stage0_runs_orchestrator_not_we_rescore(self) -> None:
        """Implements FR-299 / AC-396."""
        stage0 = _stage0(self.skill)
        self.assertIn("run_submission.py data/pending_review/{slug}", stage0)
        self.assertIn("Do **not** re-derive fit", stage0)
        self.assertNotRegex(
            stage0,
            r"Check every required item against four things",
        )
        self.assertNotRegex(
            stage0,
            r"(?m)^\s*[-*]\s*`workExperience\.md`",
        )

    def test_stage1_author_prompt_only_forbids_fat_loads(self) -> None:
        stage1 = _stage1(self.skill)
        self.assertIn("paste `authoring_prompt.md` only", stage1)
        for forbidden in (
            "agent_context_pack.md",
            "workExperience.md",
            "master_claims.json",
            "full `AGENTS.md`",
        ):
            self.assertIn(forbidden, stage1)
        self.assertIn("Author from the packet only", stage1)

    def test_stage2_mechanical_resume_is_not_hm_read(self) -> None:
        stage2 = _stage2(self.skill)
        self.assertIn("does **not** satisfy `hm.critical_read`", stage2)
        self.assertIn("qualitative read", stage2)
        self.assertIn("not a substitute for actually assessing truth", stage2)

    def test_agents_trigger_forbids_per_jd_spawn(self) -> None:
        """Implements FR-301 / AC-398."""
        m = re.search(
            r"\*\*Processing job descriptions today\?\*\*.*",
            self.agents,
        )
        self.assertIsNotNone(m)
        para = m.group(0)
        self.assertIn("Task/Agent-spawn", para)
        self.assertIn("authoring_prompt.md", para)
        self.assertIn("conversion-ready-pass", para)
        self.assertIn("run_submission.py data/pending_review/{slug}", para)


if __name__ == "__main__":
    unittest.main(verbosity=2)
