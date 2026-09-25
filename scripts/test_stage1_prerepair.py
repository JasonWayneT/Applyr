"""Tests for scripts/stage1_prerepair.py."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import stage1_prerepair as prerepair  # noqa: E402

_WE = "### 1.0 Contact\nA PM with **7 years** of experience in platforms.\n"


class TestStage1Prerepair(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.folder = Path(self._tmp.name)

    def test_six_years_fixed_without_agy(self) -> None:
        resume = "Product Manager with six years of experience in B2B platforms.\n"
        (self.folder / "Resume.md").write_text(resume, encoding="utf-8")
        (self.folder / "CoverLetter.md").write_text("Dear Hiring Manager,\n\nHello.\n", encoding="utf-8")
        result = prerepair.apply_mechanical_fixes(self.folder, we_text=_WE)
        self.assertTrue(result["changed"])
        self.assertTrue(any(row["rule_id"] == "LR-013" for row in result["applied"]))
        text = (self.folder / "Resume.md").read_text(encoding="utf-8")
        self.assertIn("seven years of experience", text)
        self.assertNotIn("six years", text)

    def test_uncited_sentence_is_removed_when_other_lines_are_cited(self) -> None:
        letter = (
            "Dear Hiring Manager,\n\n"
            "At Cision, enterprise users kept reporting that contact records were stale.\n\n"
            "I have seven years of platform work and I have grounded roadmap decisions in support tickets.\n\n"
            "Best regards,\n\nJason Taylor\n"
        )
        (self.folder / "Resume.md").write_text(
            "# Name\n\n## PROFESSIONAL EXPERIENCE\n* Kept the cited bullet.\n",
            encoding="utf-8",
        )
        (self.folder / "CoverLetter.md").write_text(letter, encoding="utf-8")
        (self.folder / "claim_provenance.json").write_text(
            json.dumps(
                {
                    "resume_claims": [
                        {"bullet": "Kept the cited bullet.", "claim_ids": ["ACC-102-LEAD"]}
                    ],
                    "cover_letter_claims": [
                        {
                            "sentence": "At Cision, enterprise users kept reporting that contact records were stale.",
                            "claim_ids": ["ACC-102-LEAD"],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        result = prerepair.apply_mechanical_fixes(self.folder, we_text=_WE)
        self.assertTrue(result["changed"])
        updated = (self.folder / "CoverLetter.md").read_text(encoding="utf-8")
        self.assertNotIn("grounded roadmap", updated)
        self.assertIn("contact records were stale", updated)

    def test_sole_employer_sentence_is_not_dropped_when_uncited(self) -> None:
        """Deleting the only past-employer sentence creates LR-045. Implements FR-386."""
        letter = (
            "Dear Hiring Manager,\n\n"
            "At Cision, enterprise users kept reporting that contact records were stale.\n\n"
            "Support tickets grounded the roadmap decisions for the platform.\n\n"
            "Best regards,\n\nJason Taylor\n"
        )
        (self.folder / "Resume.md").write_text(
            "# Name\n\n## PROFESSIONAL EXPERIENCE\n* Kept the cited bullet.\n",
            encoding="utf-8",
        )
        (self.folder / "CoverLetter.md").write_text(letter, encoding="utf-8")
        (self.folder / "claim_provenance.json").write_text(
            json.dumps(
                {
                    "resume_claims": [
                        {"bullet": "Kept the cited bullet.", "claim_ids": ["ACC-102-LEAD"]}
                    ],
                    "cover_letter_claims": [
                        {
                            "sentence": (
                                "Support tickets grounded the roadmap decisions for the platform."
                            ),
                            "claim_ids": ["ACC-102-LEAD"],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        prerepair.apply_mechanical_fixes(self.folder, we_text=_WE)
        updated = (self.folder / "CoverLetter.md").read_text(encoding="utf-8")
        self.assertIn("At Cision", updated)

    def test_missing_employer_name_is_filled_from_a_cited_bullet(self) -> None:
        """LR-045 is filled from a cited Cision bullet, not left for the model to delete. Implements FR-386."""
        resume = (
            "# Name\n\n## PROFESSIONAL EXPERIENCE\n"
            "### Product Manager | Cision | 2021 - 2026\n"
            "* Addressed renewal risk with a cited remediation plan.\n"
            "### Product Manager | Sterkly | 2019 - 2021\n"
            "* Kept the second role on a security product.\n"
            "### Account Manager | Zero To Sixty | 2017 - 2019\n"
            "* Kept the third role on onboarding.\n\n"
            "## EDUCATION\nBachelor of Business Administration\n"
        )
        letter = (
            "Dear Hiring Manager,\n\n"
            "The posting is about platform work.\n\n"
            "Best regards,\n\nName\n"
        )
        (self.folder / "Resume.md").write_text(resume, encoding="utf-8")
        (self.folder / "CoverLetter.md").write_text(letter, encoding="utf-8")
        (self.folder / "claim_provenance.json").write_text(
            json.dumps(
                {
                    "resume_claims": [
                        {
                            "bullet": "Addressed renewal risk with a cited remediation plan.",
                            "claim_ids": ["ACC-102-LEAD"],
                        }
                    ],
                    "cover_letter_claims": [],
                }
            ),
            encoding="utf-8",
        )
        prerepair.apply_mechanical_fixes(self.folder, we_text=_WE)
        updated = (self.folder / "CoverLetter.md").read_text(encoding="utf-8")
        self.assertIn("At Cision, I addressed renewal risk", updated)
        provenance = json.loads(
            (self.folder / "claim_provenance.json").read_text(encoding="utf-8")
        )
        cited = [
            row
            for row in provenance.get("cover_letter_claims") or []
            if "At Cision, I addressed renewal risk" in str(row.get("sentence") or "")
        ]
        self.assertEqual(len(cited), 1)
        self.assertEqual(cited[0]["claim_ids"], ["ACC-102-LEAD"])

    def test_clean_draft_stays_byte_identical(self) -> None:
        resume = "Product Manager with seven years of experience in B2B platforms.\n"
        letter = "Dear Hiring Manager,\n\nHello there.\n"
        (self.folder / "Resume.md").write_text(resume, encoding="utf-8")
        (self.folder / "CoverLetter.md").write_text(letter, encoding="utf-8")
        result = prerepair.apply_mechanical_fixes(self.folder, we_text=_WE)
        self.assertFalse(result["changed"])
        self.assertEqual((self.folder / "Resume.md").read_text(encoding="utf-8"), resume)
        self.assertEqual((self.folder / "CoverLetter.md").read_text(encoding="utf-8"), letter)

    def test_semicolon_splits_into_two_sentences(self) -> None:
        resume = "I aligned engineering and CX; we shipped the cutover.\n"
        (self.folder / "Resume.md").write_text(resume, encoding="utf-8")
        (self.folder / "CoverLetter.md").write_text("Dear Hiring Manager,\n\nHello.\n", encoding="utf-8")
        result = prerepair.apply_mechanical_fixes(self.folder, we_text=_WE)
        self.assertTrue(result["changed"])
        text = (self.folder / "Resume.md").read_text(encoding="utf-8")
        self.assertNotIn(";", text)
        self.assertIn("CX. We shipped", text)

    def test_colon_split_resyncs_claim_provenance(self) -> None:
        """Found live on obie, 2026-09-20: an LR-015 colon-split rewrote a
        resume bullet's text but left claim_provenance.json pointing at the
        old (pre-fix) wording, turning a fully-cited bullet into a false
        sentence_provenance FAIL on the very next verify pass."""
        bullet = (
            "Organized the platform roadmap under four strategic pillars: "
            "cost reduction, platform stabilization, churn stabilization."
        )
        resume = f"## PROFESSIONAL EXPERIENCE\n\n* {bullet}\n"
        (self.folder / "Resume.md").write_text(resume, encoding="utf-8")
        (self.folder / "CoverLetter.md").write_text("Dear Hiring Manager,\n\nHello.\n", encoding="utf-8")
        provenance = {
            "company": "Acme",
            "resume_claims": [{"bullet": bullet, "claim_ids": ["ACC-179-ROADMAP"]}],
            "cover_letter_claims": [],
        }
        (self.folder / "claim_provenance.json").write_text(
            json.dumps(provenance, indent=2), encoding="utf-8"
        )
        result = prerepair.apply_mechanical_fixes(self.folder, we_text=_WE)
        self.assertTrue(result["changed"])
        new_resume = (self.folder / "Resume.md").read_text(encoding="utf-8")
        self.assertNotIn(":", new_resume)
        updated = json.loads((self.folder / "claim_provenance.json").read_text(encoding="utf-8"))
        stored_bullet = updated["resume_claims"][0]["bullet"]
        # The provenance's stored bullet text must match the rewritten resume
        # bullet (stripped of its leading "* " marker), not the stale
        # pre-fix wording -- otherwise sentence_provenance's exact-string
        # comparison falsely reports the bullet as uncited.
        self.assertIn(stored_bullet.rstrip(".!? "), new_resume)
        self.assertNotEqual(stored_bullet, bullet)

    def test_missing_estimate_hedge_is_inserted_without_dropping_the_cite(self) -> None:
        """A cited drafting line keeps its cite when the hedge word is added. Implements FR-386."""
        bullet = "Used AI to accelerate epic drafting from two weeks to a few days."
        sentence = "I accelerated story drafting from two weeks to a few days."
        resume = f"## PROFESSIONAL EXPERIENCE\n\n* {bullet}\n"
        letter = f"Dear Hiring Manager,\n\n{sentence}\n\nBest regards,\n\nName\n"
        (self.folder / "Resume.md").write_text(resume, encoding="utf-8")
        (self.folder / "CoverLetter.md").write_text(letter, encoding="utf-8")
        (self.folder / "claim_provenance.json").write_text(
            json.dumps(
                {
                    "resume_claims": [{"bullet": bullet, "claim_ids": ["ACC-179"]}],
                    "cover_letter_claims": [{"sentence": sentence, "claim_ids": ["ACC-179"]}],
                }
            ),
            encoding="utf-8",
        )
        result = prerepair.apply_mechanical_fixes(self.folder, we_text=_WE)
        self.assertTrue(result["changed"])
        new_resume = (self.folder / "Resume.md").read_text(encoding="utf-8")
        new_letter = (self.folder / "CoverLetter.md").read_text(encoding="utf-8")
        self.assertIn("estimated", new_resume.lower())
        self.assertIn("weeks", new_resume.lower())
        self.assertIn("days", new_resume.lower())
        self.assertIn("estimated", new_letter.lower())
        self.assertIn("weeks", new_letter.lower())
        provenance = json.loads((self.folder / "claim_provenance.json").read_text(encoding="utf-8"))
        self.assertIn("estimated", provenance["resume_claims"][0]["bullet"].lower())
        self.assertEqual(provenance["resume_claims"][0]["claim_ids"], ["ACC-179"])
        self.assertIn("estimated", provenance["cover_letter_claims"][0]["sentence"].lower())
        self.assertEqual(provenance["cover_letter_claims"][0]["claim_ids"], ["ACC-179"])

    def test_cited_hard_block_sentence_is_removed(self) -> None:
        """A cited data-model bullet and a cited blocked tool are removed. Implements FR-402."""
        blocked = "I built a data model for the contact platform."
        kept = "I kept the cleanup bullet for stale records."
        tool = "I used Snowflake to query the warehouse."
        kept_letter = "At Cision, I kept the contact records current for enterprise users."
        resume = (
            "## PROFESSIONAL EXPERIENCE\n\n"
            "### Product Manager | Cision | September 2021 - January 2026\n"
            f"* {blocked}\n"
            f"* {kept}\n"
        )
        letter = (
            "Dear Hiring Manager,\n\n"
            f"{kept_letter}\n\n"
            f"{tool}\n\n"
            "Best regards,\n\nName\n"
        )
        (self.folder / "Resume.md").write_text(resume, encoding="utf-8")
        (self.folder / "CoverLetter.md").write_text(letter, encoding="utf-8")
        (self.folder / "claim_provenance.json").write_text(
            json.dumps(
                {
                    "resume_claims": [
                        {"bullet": blocked, "claim_ids": ["ACC-102"]},
                        {"bullet": kept, "claim_ids": ["ACC-102"]},
                    ],
                    "cover_letter_claims": [
                        {"sentence": kept_letter, "claim_ids": ["ACC-102"]},
                        {"sentence": tool, "claim_ids": ["ACC-121"]},
                    ],
                }
            ),
            encoding="utf-8",
        )
        result = prerepair.apply_mechanical_fixes(self.folder, we_text=_WE)
        self.assertTrue(any(row["rule_id"] == "LR-046" for row in result["applied"]))
        self.assertTrue(any(row["rule_id"] == "LR-026" for row in result["applied"]))
        new_resume = (self.folder / "Resume.md").read_text(encoding="utf-8")
        new_letter = (self.folder / "CoverLetter.md").read_text(encoding="utf-8")
        self.assertNotIn("data model", new_resume.lower())
        self.assertIn(kept, new_resume)
        self.assertNotIn("Snowflake", new_letter)
        self.assertIn("Cision", new_letter)

    def test_only_employer_hard_block_sentence_is_kept(self) -> None:
        """Removing the only past-employer sentence is refused. Implements FR-402."""
        sentence = "At Cision, I built a data model for the contact platform."
        letter = f"Dear Hiring Manager,\n\n{sentence}\n\nBest regards,\n\nName\n"
        (self.folder / "Resume.md").write_text(
            "## PROFESSIONAL EXPERIENCE\n* I kept the cleanup bullet for stale records.\n",
            encoding="utf-8",
        )
        (self.folder / "CoverLetter.md").write_text(letter, encoding="utf-8")
        (self.folder / "claim_provenance.json").write_text(
            json.dumps(
                {
                    "resume_claims": [
                        {
                            "bullet": "I kept the cleanup bullet for stale records.",
                            "claim_ids": ["ACC-102"],
                        }
                    ],
                    "cover_letter_claims": [{"sentence": sentence, "claim_ids": ["ACC-102"]}],
                }
            ),
            encoding="utf-8",
        )
        prerepair.apply_mechanical_fixes(self.folder, we_text=_WE)
        updated = (self.folder / "CoverLetter.md").read_text(encoding="utf-8")
        self.assertIn("Cision", updated)
        self.assertIn("data model", updated.lower())

    def test_nonfactual_buzzword_sentence_is_removed(self) -> None:
        """A cover sentence with no personal fact still drops when it is a hard block. Implements AC-513."""
        blocked = "The posting describes a robust platform for operators."
        kept = "At Cision, I kept the contact records current for enterprise users."
        letter = f"Dear Hiring Manager,\n\n{blocked}\n\n{kept}\n\nBest regards,\n\nName\n"
        (self.folder / "Resume.md").write_text(
            "## PROFESSIONAL EXPERIENCE\n* I kept the cleanup bullet for stale records.\n",
            encoding="utf-8",
        )
        (self.folder / "CoverLetter.md").write_text(letter, encoding="utf-8")
        (self.folder / "claim_provenance.json").write_text(
            json.dumps(
                {
                    "resume_claims": [
                        {
                            "bullet": "I kept the cleanup bullet for stale records.",
                            "claim_ids": ["ACC-102"],
                        }
                    ],
                    "cover_letter_claims": [{"sentence": kept, "claim_ids": ["ACC-102"]}],
                }
            ),
            encoding="utf-8",
        )
        result = prerepair.apply_mechanical_fixes(self.folder, we_text=_WE)
        self.assertTrue(any(row["rule_id"] == "LR-009" for row in result["applied"]))
        updated = (self.folder / "CoverLetter.md").read_text(encoding="utf-8")
        self.assertNotIn("robust", updated.lower())
        self.assertIn("Cision", updated)

    def test_hedged_precise_100k_becomes_100k(self) -> None:
        """A hedged $100,000 becomes $100K. An unhedged one stays. Implements FR-403."""
        resume = (
            "## PROFESSIONAL EXPERIENCE\n"
            "* Saved roughly $100,000 on the migration.\n"
            "* Booked $100,000 with no hedge in this bullet.\n"
        )
        (self.folder / "Resume.md").write_text(resume, encoding="utf-8")
        (self.folder / "CoverLetter.md").write_text(
            "Dear Hiring Manager,\n\nAbout $100,000 was the planning figure.\n\nBest regards,\n\nName\n",
            encoding="utf-8",
        )
        result = prerepair.apply_mechanical_fixes(self.folder, we_text=_WE)
        self.assertTrue(any(row["rule_id"] == "FR-403" for row in result["applied"]))
        updated = (self.folder / "Resume.md").read_text(encoding="utf-8")
        letter = (self.folder / "CoverLetter.md").read_text(encoding="utf-8")
        self.assertIn("roughly $100K", updated)
        self.assertIn("$100,000", updated)
        self.assertIn("About $100K", letter)
        self.assertNotIn("$100,000", letter)

    def test_uncited_only_employer_sentence_is_replaced(self) -> None:
        """An uncited sole employer sentence is replaced by a cited one. Implements FR-404."""
        resume = (
            "# Name\n\n## PROFESSIONAL EXPERIENCE\n"
            "### Product Manager | Cision | 2021 - 2026\n"
            "* Addressed renewal risk with a cited remediation plan.\n"
        )
        uncited = "At Cision, I kept an uncited account of the renewal work."
        letter = f"Dear Hiring Manager,\n\n{uncited}\n\nBest regards,\n\nName\n"
        (self.folder / "Resume.md").write_text(resume, encoding="utf-8")
        (self.folder / "CoverLetter.md").write_text(letter, encoding="utf-8")
        (self.folder / "claim_provenance.json").write_text(
            json.dumps(
                {
                    "resume_claims": [
                        {
                            "bullet": "Addressed renewal risk with a cited remediation plan.",
                            "claim_ids": ["ACC-102-LEAD"],
                        }
                    ],
                    "cover_letter_claims": [],
                }
            ),
            encoding="utf-8",
        )
        prerepair.apply_mechanical_fixes(self.folder, we_text=_WE)
        updated = (self.folder / "CoverLetter.md").read_text(encoding="utf-8")
        self.assertIn("At Cision, I addressed renewal risk", updated)
        self.assertNotIn("uncited account", updated)

    def test_unverified_partner_clause_is_removed(self) -> None:
        """A partner group that is not on the verified list is cut out. Implements FR-405."""
        kept = "Optimized customer data ingestion workflows into Salesforce."
        bullet = (
            "Optimized customer data ingestion workflows into Salesforce, "
            "partnering with operational stakeholders to standardize intake schemas."
        )
        engineering = "Partnered with engineering to ship the intake fix."
        resume = (
            "## PROFESSIONAL EXPERIENCE\n"
            "### Product Manager | Cision | 2021 - 2026\n"
            f"* {bullet}\n"
            f"* {engineering}\n"
        )
        (self.folder / "Resume.md").write_text(resume, encoding="utf-8")
        (self.folder / "CoverLetter.md").write_text(
            "Dear Hiring Manager,\n\nAt Cision, I kept the contact records current.\n\nBest regards,\n\nName\n",
            encoding="utf-8",
        )
        (self.folder / "claim_provenance.json").write_text(
            json.dumps(
                {
                    "resume_claims": [
                        {"bullet": bullet, "claim_ids": ["ACC-102"]},
                        {"bullet": engineering, "claim_ids": ["ACC-104"]},
                    ],
                    "cover_letter_claims": [],
                }
            ),
            encoding="utf-8",
        )
        result = prerepair.apply_mechanical_fixes(self.folder, we_text=_WE)
        self.assertTrue(any(row["rule_id"] == "LW-005" for row in result["applied"]))
        updated = (self.folder / "Resume.md").read_text(encoding="utf-8")
        self.assertIn(kept, updated)
        self.assertNotIn("operational stakeholders", updated)
        self.assertIn(engineering, updated)
        provenance = json.loads((self.folder / "claim_provenance.json").read_text(encoding="utf-8"))
        cited = [row["bullet"] for row in provenance["resume_claims"]]
        self.assertIn(kept, cited)

    def test_dropoff_ingestion_pipeline_is_renamed(self) -> None:
        """The 40% drop-off story is not an ingestion pipeline. Implements FR-406."""
        bad = "The stale contact drop-off fell 40% after the ingestion pipeline was retired."
        kept = "The migration used an ingestion pipeline for a different feed."
        letter = f"Dear Hiring Manager,\n\n{bad}\n\nBest regards,\n\nName\n"
        resume = f"## PROFESSIONAL EXPERIENCE\n* {kept}\n"
        (self.folder / "Resume.md").write_text(resume, encoding="utf-8")
        (self.folder / "CoverLetter.md").write_text(letter, encoding="utf-8")
        result = prerepair.apply_mechanical_fixes(self.folder, we_text=_WE)
        self.assertTrue(any(row["rule_id"] == "LR-038" for row in result["applied"]))
        updated = (self.folder / "CoverLetter.md").read_text(encoding="utf-8")
        resume_text = (self.folder / "Resume.md").read_text(encoding="utf-8")
        self.assertIn("ETL path", updated)
        self.assertNotIn("ingestion pipeline", updated)
        self.assertIn("ingestion pipeline", resume_text)
        from submission_linter import check_bypass_authorship

        self.assertEqual(check_bypass_authorship(resume_text, updated), [])

    def test_contributed_claim_does_not_say_designed_and_built(self) -> None:
        """A contributed claim loses designed and built. An owned built line stays. Implements FR-407."""
        owned = "Built the landing page that cut the drop-off."
        contributed = "I designed and built the prompt orchestration for content generation."
        letter = f"Dear Hiring Manager,\n\n{contributed}\n\nBest regards,\n\nName\n"
        resume = f"## PROFESSIONAL EXPERIENCE\n* {owned}\n"
        (self.folder / "Resume.md").write_text(resume, encoding="utf-8")
        (self.folder / "CoverLetter.md").write_text(letter, encoding="utf-8")
        result = prerepair.apply_mechanical_fixes(self.folder, we_text=_WE)
        self.assertTrue(any(row["rule_id"] == "LW-028" for row in result["applied"]))
        updated = (self.folder / "CoverLetter.md").read_text(encoding="utf-8")
        resume_text = (self.folder / "Resume.md").read_text(encoding="utf-8")
        self.assertIn("I contributed to the prompt orchestration", updated)
        self.assertNotIn("designed and built", updated)
        self.assertIn(owned, resume_text)

    def test_cited_backlog_claim_is_dropped(self) -> None:
        """A bullet that cites ACC-103 and says the backlog was resolved is removed. Implements FR-408."""
        blocked = "Resolved an inherited penetration-test security backlog by grouping the open items."
        kept = "Kept the weekly planning bullet that names no backlog."
        (self.folder / "Resume.md").write_text(
            "## PROFESSIONAL EXPERIENCE\n"
            "### Product Manager | Cision | 2018 - 2024\n"
            f"* {blocked}\n"
            f"* {kept}\n",
            encoding="utf-8",
        )
        (self.folder / "CoverLetter.md").write_text(
            "Dear Hiring Manager,\n\nAt Cision, the cited planning work stayed.\n\nBest regards,\n\nName\n",
            encoding="utf-8",
        )
        (self.folder / "claim_provenance.json").write_text(
            json.dumps(
                {
                    "resume_claims": [
                        {"bullet": blocked, "claim_ids": ["ACC-103"]},
                        {"bullet": kept, "claim_ids": ["ACC-102"]},
                    ],
                    "cover_letter_claims": [
                        {
                            "sentence": "At Cision, the cited planning work stayed.",
                            "claim_ids": ["ACC-102"],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        applied = prerepair.drop_blocked_units(self.folder)
        self.assertTrue(any(row["rule_id"] == "LR-049" for row in applied))
        resume = (self.folder / "Resume.md").read_text(encoding="utf-8")
        self.assertNotIn("security backlog", resume)
        self.assertIn(kept, resume)

    def test_overlong_letter_drops_an_uncited_sentence(self) -> None:
        """A letter over one page loses an uncited sentence. The employer sentence stays. Implements FR-410."""
        cited = "At Cision, I kept the planning cadence for the platform team."
        uncited = (
            "The extra context in this sentence is not a cited fact "
            + "and the weekly notes stayed in the folder " * 70
        ).strip()
        if not uncited.endswith("."):
            uncited += "."
        letter = (
            "# Name\nline\n\n"
            "Dear Hiring Manager,\n\n"
            f"{cited}\n\n{uncited}\n\n"
            "Best regards,\n\nName\n"
        )
        self.assertGreater(len(letter), 2800)
        (self.folder / "Resume.md").write_text(
            "## PROFESSIONAL EXPERIENCE\n* Kept a resume bullet.\n",
            encoding="utf-8",
        )
        (self.folder / "CoverLetter.md").write_text(letter, encoding="utf-8")
        (self.folder / "claim_provenance.json").write_text(
            json.dumps(
                {
                    "resume_claims": [
                        {"bullet": "Kept a resume bullet.", "claim_ids": ["ACC-102"]}
                    ],
                    "cover_letter_claims": [{"sentence": cited, "claim_ids": ["ACC-102"]}],
                }
            ),
            encoding="utf-8",
        )
        applied = prerepair.trim_cover_to_page(self.folder)
        self.assertTrue(any(row["rule_id"] == "CL-006" for row in applied))
        updated = (self.folder / "CoverLetter.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(updated), 2800)
        self.assertIn(cited, updated)
        self.assertNotIn("not a cited fact", updated)

    def test_thin_letter_gains_a_cited_sentence(self) -> None:
        """A letter under 220 words gains one cited resume sentence. Implements FR-411."""
        bullet = "Kept the planning cadence " + "for the platform team " * 55
        bullet = bullet.strip()
        if not bullet.endswith("."):
            bullet += "."
        cited = "At Cision, the short line stays."
        letter = (
            "Dear Hiring Manager,\n\n"
            f"{cited}\n\n"
            "Best regards,\n\nName\n"
        )
        resume = (
            "## PROFESSIONAL EXPERIENCE\n"
            "### Product Manager | Cision | 2018 - 2024\n"
            f"* {bullet}\n"
        )
        (self.folder / "Resume.md").write_text(resume, encoding="utf-8")
        (self.folder / "CoverLetter.md").write_text(letter, encoding="utf-8")
        (self.folder / "claim_provenance.json").write_text(
            json.dumps(
                {
                    "resume_claims": [{"bullet": bullet, "claim_ids": ["ACC-102"]}],
                    "cover_letter_claims": [{"sentence": cited, "claim_ids": ["ACC-101"]}],
                }
            ),
            encoding="utf-8",
        )
        applied = prerepair.extend_thin_cover(self.folder)
        self.assertTrue(any(row["rule_id"] == "LW-001" for row in applied))
        updated = (self.folder / "CoverLetter.md").read_text(encoding="utf-8")
        self.assertGreaterEqual(prerepair._cover_body_words(updated), 220)
        self.assertLessEqual(prerepair._cover_body_words(updated), 450)
        self.assertIn("planning cadence", updated)


if __name__ == "__main__":
    unittest.main()
