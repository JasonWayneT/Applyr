"""Tests for generate_context_pack.py and check_context_pack_freshness.py."""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import generate_context_pack as gcp
import check_context_pack_freshness as cpf


class TestSectionSplitting(unittest.TestCase):
    def test_split_preserves_preamble_and_sections(self):
        md = "preamble text\n\n## First\nbody1\n\n## Second\nbody2\n"
        sections = gcp.split_into_h2_sections(md)
        self.assertEqual([h for h, _ in sections], ["", "First", "Second"])
        self.assertIn("preamble text", sections[0][1])
        self.assertIn("body1", sections[1][1])
        self.assertIn("body2", sections[2][1])

    def test_filter_sections_drops_only_named_headings(self):
        md = "pre\n\n## Keep Me\nkeep body\n\n## Drop Me\ndrop body\n\n## Keep Too\nkeep2\n"
        out = gcp.filter_sections(md, frozenset({"Drop Me"}))
        self.assertIn("keep body", out)
        self.assertIn("keep2", out)
        self.assertNotIn("drop body", out)
        self.assertNotIn("Drop Me", out)


class TestWePiiStrip(unittest.TestCase):
    def test_strips_contact_and_references_keeps_accomplishments(self):
        we = (
            "# Work Experience\n\n"
            "## 1.0 Contact Information\n"
            "Name: Example Person\n"
            "email@example.com\n\n"
            "### 1.0a Professional References\n"
            "Ref One — 555-0100\n\n"
            "## 5 Accomplishments\n"
            "* [ACC-101] Platform stabilization\n"
        )
        out = gcp.strip_we_pii_sections(we)
        self.assertNotIn("email@example.com", out)
        self.assertNotIn("555-0100", out)
        self.assertNotIn("Contact Information", out)
        self.assertIn("ACC-101", out)
        self.assertIn("Platform stabilization", out)


class TestRealAgentsMdExtraction(unittest.TestCase):
    """Golden-content tests against the REAL current AGENTS.md (the canonical
    rules file -- CLAUDE.md is now a thin @AGENTS.md import stub for Claude
    Code, not a second copy) -- catches the real risk (silently dropping
    operative content), not just synthetic fixtures."""

    @classmethod
    def setUpClass(cls):
        with open(gcp.AGENTS_MD, encoding="utf-8") as f:
            cls.raw = f.read()
        cls.trimmed = gcp.filter_sections(cls.raw, gcp.AGENTS_MD_EXCLUDE_SECTIONS)

    def test_excludes_engineering_only_sections(self):
        self.assertNotIn("Active Engineering Work", self.trimmed)
        self.assertNotIn("Documentation Update Checklist", self.trimmed)
        # Sanity: these strings must actually exist in the raw file, or this
        # test would trivially pass by testing nothing.
        self.assertIn("Active Engineering Work", self.raw)
        self.assertIn("Documentation Update Checklist", self.raw)

    def test_keeps_operative_content(self):
        must_survive = [
            "revenue-bearing",  # Forbidden Language
            "0-to-1 greenfield PM",  # Exclusion Zones
            "## PROFESSIONAL SUMMARY",  # Required Document Structure
            "Dear Hiring Manager,",  # Required Cover Letter Structure
            "1-Page Resume Rule",
            "Cover Letter Proof-Point Selection",
            "Conversion thresholds",  # "a floor, not a stop signal" section
        ]
        for needle in must_survive:
            self.assertIn(needle, self.trimmed, f"Lost operative content: {needle!r}")

    def test_met_acc_relocated_not_lost(self):
        """MET/ACC quick-reference tables were cut from AGENTS.md (harness-bridge
        session-009, R25-R32, Phase 2) -- workExperience.md is the canonical
        source and was already the stated source of truth even when AGENTS.md
        carried a duplicate copy. This confirms the fact actually lives there,
        not just that AGENTS.md points at it.

        Golden-content check against the REAL (gitignored) workExperience.md --
        only meaningful when real candidate data is present. On a fresh clone
        or CI, bootstrap_local_data.py creates this file from
        workExperience.example.md instead, which has no MET section at all by
        design (2026-08-31: found failing every CI run for exactly this
        reason). Skip rather than fail when only the example is present.
        """
        with open(gcp.WORK_EXPERIENCE_MD, encoding="utf-8") as f:
            work_experience = f.read()
        example_path = os.path.join(
            os.path.dirname(gcp.WORK_EXPERIENCE_MD), "workExperience.example.md"
        )
        if os.path.exists(example_path):
            with open(example_path, encoding="utf-8") as f:
                if work_experience == f.read():
                    self.skipTest(
                        "data/workExperience.md is just the bootstrapped example "
                        "(no real candidate data present) -- this golden-content "
                        "check needs the real, gitignored file."
                    )
        self.assertIn("MET-01", work_experience)
        self.assertIn("40,000,000", work_experience)
        self.assertIn("ACC-101", work_experience)
        # AGENTS.md itself must still point to workExperience.md for these,
        # not silently drop the pointer along with the table.
        self.assertIn("workExperience.md", self.trimmed)
        self.assertIn("MET-01", self.trimmed)  # named in the pointer paragraph

    def test_meaningfully_smaller_than_raw(self):
        # No percentage floor here (dropped in harness-bridge session-009,
        # R25-R27, same reasoning as TestAgentsMdLineBudget above): once the
        # excluded sections' own bodies get trimmed toward pointers, the
        # *excluded* content shrinks too, so any ratio-based floor drifts
        # down from legitimate content changes, not a real regression. The
        # actually-precise check already lives in
        # test_excludes_engineering_only_sections (the two named sections'
        # content is gone, verbatim, from the trimmed output) -- this test
        # just confirms filter_sections did non-zero real work at all,
        # i.e. it isn't a silent no-op.
        self.assertLess(len(self.trimmed), len(self.raw))


class TestRealSkillMdExtraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(gcp.SKILL_MD, encoding="utf-8") as f:
            cls.raw = f.read()
        cls.trimmed = gcp.filter_sections(cls.raw, gcp.SKILL_MD_EXCLUDE_SECTIONS)

    def test_excludes_self_repair_protocol(self):
        # A bare substring check on the heading text is too strict -- other
        # sections legitimately cross-reference "Self-repair protocol" by
        # name even after the section itself is removed (e.g. Required
        # Verification says "the same way Section 'Self-repair protocol'
        # above already describes"). Check for content unique to the
        # section's own body instead of its title.
        body_only_text = "Do not add a new numbered item to a growing prose list"
        self.assertNotIn(body_only_text, self.trimmed)
        self.assertIn(body_only_text, self.raw)
        # The cross-reference mention elsewhere is expected to survive.
        self.assertIn("Self-repair protocol", self.trimmed)

    def test_keeps_operative_stage_content(self):
        must_survive = [
            "Stage 0",
            "Stage 1",
            "Stage 2",
            "stage0_fit_gate.json",
            "gap-confession",
            "verify_submission.py",
        ]
        for needle in must_survive:
            self.assertIn(needle, self.trimmed, f"Lost operative content: {needle!r}")


class TestClaimsTagsOnly(unittest.TestCase):
    def test_strips_text_and_cover_story_preserves_everything_else(self):
        with open(gcp.MASTER_CLAIMS_JSON, encoding="utf-8") as f:
            original = json.load(f)
        filtered = gcp.generate_claims_tags_only()

        def _flatten(obj):
            if isinstance(obj, list):
                return [c for c in obj if isinstance(c, dict)]
            if isinstance(obj, dict):
                if "claims" in obj and isinstance(obj["claims"], list):
                    return [c for c in obj["claims"] if isinstance(c, dict)]
                return [v for v in obj.values() if isinstance(v, dict)]
            return []

        orig_claims = _flatten(original)
        filtered_claims = _flatten(filtered)

        self.assertEqual(
            len(orig_claims), len(filtered_claims), "Claim count must be preserved exactly"
        )
        for claim in filtered_claims:
            self.assertNotIn("text", claim)
            self.assertNotIn("cover_story", claim)

        # At least one claim in the real catalog has tags -- confirm tags survive.
        claims_with_tags = [c for c in filtered_claims if c.get("tags")]
        self.assertGreater(len(claims_with_tags), 0, "Expected some claims to retain tags")

        # disabled flags must be preserved where present in the source.
        orig_disabled_ids = {
            c.get("id") for c in orig_claims if c.get("disabled") is True
        }
        filtered_disabled_ids = {
            c.get("id") for c in filtered_claims if c.get("disabled") is True
        }
        self.assertEqual(orig_disabled_ids, filtered_disabled_ids)

    def test_output_is_valid_json_serializable(self):
        filtered = gcp.generate_claims_tags_only()
        # Must not raise.
        json.dumps(filtered)


class TestManifestKeysResolveToRealFiles(unittest.TestCase):
    """Regression test for a real bug: build_manifest() first wrote bare
    filenames ('SKILL.md') instead of the true path relative to REPO_ROOT
    ('.claude/skills/generate-submission/SKILL.md'), so
    check_context_pack_freshness.py's `os.path.join(REPO_ROOT, rel_path)`
    resolved to a nonexistent file and reported every fresh pack as STALE.
    Caught by actually running the generator end to end, not by any unit
    test -- this test exists so the next regression is caught here instead."""

    def test_every_manifest_key_resolves_under_repo_root(self):
        manifest = gcp.build_manifest()
        for rel_path in manifest["sources"]:
            abs_path = os.path.join(gcp.REPO_ROOT, rel_path)
            self.assertTrue(
                os.path.isfile(abs_path),
                f"Manifest key {rel_path!r} does not resolve to a real file at {abs_path!r}",
            )

    def test_generated_pack_manifest_is_fresh_immediately(self):
        pack_text, _manifest = gcp.generate_pack()
        with tempfile.TemporaryDirectory() as tmp:
            pack_path = os.path.join(tmp, "pack.md")
            with open(pack_path, "w", encoding="utf-8") as f:
                f.write(pack_text)
            # check_freshness resolves manifest keys against the REAL repo
            # root (cpf.REPO_ROOT), which is correct here since this manifest
            # really was built from the real source files.
            is_fresh, problems = cpf.check_freshness(pack_path)
            self.assertTrue(is_fresh, problems)


class TestAgentsMdLineBudget(unittest.TestCase):
    """Replaces the old pack-size-reduction-ratio test (harness-bridge
    session-009, R25-R27). That test measured pack_chars vs. total source
    bulk -- a metric that gets WORSE when engineering-only sections already
    excluded from the pack are trimmed from AGENTS.md itself, since trimming
    them shrinks the denominator without changing what's actually in the
    pack. It also drifted from its original ~19.7%-at-writing baseline down
    to 14.9% purely from legitimate content growth (ACC-113..121, no-ai-slop
    integration, LR-031, etc.), with no real regression involved either time.

    What actually matters is the thing the whole rules/reference split is
    about: how much always-loaded content AGENTS.md itself carries, since
    every harness (Claude Code via the @AGENTS.md import, Cursor, Antigravity)
    pays that cost on every session regardless of whether the pack is ever
    generated. This is a direct budget on that, not a derived ratio.

    Interim ceiling, not the final target: the frozen design (session-009)
    targets AGENTS.md at <=200 lines, human-written cut. Phase 1 (Active
    Engineering Work / Documentation Update Checklist trim) landed first,
    390 -> 360 lines. Phase 2 (this pass, MET/ACC tables moved to a pointer
    at data/workExperience.md) landed next, 360 -> 309 lines. Still deferred:
    Required Document/Cover-Letter Structure, Proof-Point Selection, and
    Submission Folder Structure -- each needs rewriting several SKILL.md
    cross-references that name those sections by exact title in the same
    commit, more cross-reference risk than Phase 1/2 carried. This test's
    ceiling should keep ratcheting down as that work lands; it exists now to
    catch NEW bloat regressing past this pass's cut, not to assert the end
    state prematurely.
    """

    def test_agents_md_under_interim_line_budget(self):
        with open(gcp.AGENTS_MD, encoding="utf-8") as f:
            line_count = sum(1 for _ in f)
        self.assertLessEqual(
            line_count,
            330,
            f"AGENTS.md grew to {line_count} lines, past this pass's interim "
            "budget (309 measured after the Phase 2 MET/ACC cut) -- either "
            "this is new bloat that should be trimmed, or a deliberate "
            "addition that should also raise this ceiling explicitly, not "
            "silently.",
        )


class TestFreshnessChecker(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

        # Build a tiny isolated "repo" with one source file and a generated pack,
        # so this test doesn't depend on mutating the real repo's source docs.
        self.source_path = os.path.join(self.tmpdir, "source.md")
        with open(self.source_path, "w", encoding="utf-8") as f:
            f.write("original content\n")

        import hashlib

        digest = hashlib.sha256(open(self.source_path, "rb").read()).hexdigest()
        manifest = {"generated_at": "2026-01-01T00:00:00+00:00", "sources": {"source.md": digest}}
        self.pack_path = os.path.join(self.tmpdir, "pack.md")
        with open(self.pack_path, "w", encoding="utf-8") as f:
            f.write(f"<!-- CONTEXT_PACK_MANIFEST\n{json.dumps(manifest)}\n-->\n\nbody\n")

        # check_context_pack_freshness resolves source paths relative to REPO_ROOT;
        # patch it to this tmpdir for the duration of the test.
        self._orig_root = cpf.REPO_ROOT
        cpf.REPO_ROOT = self.tmpdir
        self.addCleanup(setattr, cpf, "REPO_ROOT", self._orig_root)

    def test_fresh_immediately_after_generation(self):
        is_fresh, problems = cpf.check_freshness(self.pack_path)
        self.assertTrue(is_fresh, problems)
        self.assertEqual(problems, [])

    def test_detects_source_change(self):
        with open(self.source_path, "w", encoding="utf-8") as f:
            f.write("MODIFIED content\n")
        is_fresh, problems = cpf.check_freshness(self.pack_path)
        self.assertFalse(is_fresh)
        self.assertTrue(any("source.md" in p for p in problems))

    def test_missing_pack_is_clear_failure_not_crash(self):
        missing_path = os.path.join(self.tmpdir, "does_not_exist.md")
        is_fresh, problems = cpf.check_freshness(missing_path)
        self.assertFalse(is_fresh)
        self.assertTrue(any("does not exist" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
