import unittest
from cover_letter_audit import audit_cover_letter
from cover_letter_plan import CoverLetterPlan

class TestPMReportAudit(unittest.TestCase):
    def test_new_forbidden_openers(self):
        plan = CoverLetterPlan(
            company_display="Acme",
            role_title="Product Manager",
            opening_variant="need_first"
        )
        # Forbidden opener in cover letter
        text = "Dear Hiring Manager,\n\nI am writing to express my interest in the Product Manager role at Acme."
        res = audit_cover_letter(text, plan, "Acme", "")
        self.assertFalse(res.passed)
        self.assertTrue(any("Forbidden opener pattern" in i for i in res.issues))

    def test_new_buzzwords(self):
        plan = CoverLetterPlan(
            company_display="Acme",
            role_title="Product Manager",
            opening_variant="need_first"
        )
        # Banned buzzwords
        text = (
            "Dear Hiring Manager,\n\n"
            "I am applying for the Product Manager role at Acme. "
            "I have a proven track record of delivering seamless integrations."
        )
        res = audit_cover_letter(text, plan, "Acme", "")
        self.assertTrue(any("Buzzword: proven track record" in i for i in res.issues))
        self.assertTrue(any("Buzzword: seamless" in i for i in res.issues))

if __name__ == "__main__":
    unittest.main()
