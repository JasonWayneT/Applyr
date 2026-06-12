import unittest

from candidate_context import (
    build_contact_header,
    employer_for_claim_id,
    employer_slug,
    load_employer_headers,
    load_employers,
    parse_company_names,
    parse_experience_headers,
)


SAMPLE_EXP = """## **Acme Corp**
**Product Manager**
*2021 - 2026*

### Product Manager | Acme Corp | September 2021 - January 2026
* Did platform work.
"""


class TestCandidateContext(unittest.TestCase):
    def test_employer_slug(self):
        self.assertEqual(employer_slug("Acme Corp"), "acme_corp")

    def test_parse_company_names(self):
        self.assertEqual(parse_company_names(SAMPLE_EXP), ["Acme Corp"])

    def test_parse_experience_headers(self):
        headers = parse_experience_headers(SAMPLE_EXP)
        self.assertIn("acme_corp", headers)
        self.assertIn("Acme Corp", headers["acme_corp"])

    def test_load_employer_headers_has_defaults(self):
        headers = load_employer_headers()
        self.assertTrue(len(headers) > 0)
        from claim_catalog import load_catalog
        catalog_slugs = {rec.employer for rec in load_catalog().claims.values() if rec.employer}
        if catalog_slugs:
            for slug in catalog_slugs:
                self.assertIn(slug, headers)
        else:
            self.assertIn("acme_corp", headers)

    def test_load_employers_from_example_catalog(self):
        employers = load_employers()
        self.assertTrue(len(employers) >= 1)

    def test_employer_for_claim_from_catalog(self):
        slug = employer_for_claim_id("ACC-203-TECH")
        self.assertIn(slug, set(load_employers()) | {"example_inc"})

    def test_build_contact_header_generic(self):
        header = build_contact_header({
            "name": "John Doe",
            "location": "City, State",
            "phone": "555-019-9238",
            "email": "email@example.com",
            "linkedin": "linkedin.com/in/johndoe",
        })
        self.assertIn("# JOHN DOE", header)
        self.assertIn("email@example.com", header)
        self.assertNotIn("jason.wayne", header.lower())


if __name__ == "__main__":
    unittest.main()
