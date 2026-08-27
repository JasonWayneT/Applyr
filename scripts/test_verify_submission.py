"""Regression tests for CR-103 ATS retrieval and PDF parser QA."""
from __future__ import annotations

import json
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))

from verify_submission import _check_packet_ats_contract, _check_pdf_parseability


RESUME = """# Alex Example
alex@example.com | San Diego, CA

## PROFESSIONAL SUMMARY
Product Manager with platform experience.

## PROFESSIONAL EXPERIENCE
### Product Manager | Acme Corp | January 2020 - January 2024
Remote
* Built product roadmaps.

## EDUCATION
Bachelor of Business Administration
"""

COVER = """# Alex Example
alex@example.com | San Diego, CA

Dear Hiring Manager,

I build useful products.

Best regards,

Alex Example
"""


def _pdf_result(text: str, returncode: int = 0):
    return mock.Mock(stdout=text, stderr="", returncode=returncode)


def test_pdf_parseability_reports_clean_resume_fields(tmp_path):
    pdf = tmp_path / "resume.pdf"
    pdf.touch()
    with mock.patch("verify_submission.subprocess.run", return_value=_pdf_result(RESUME)):
        result = _check_pdf_parseability(str(pdf), RESUME, "resume")
    assert result["checked"] is True
    assert result["ok"] is True
    assert result["missing"] == []


def test_pdf_parseability_reports_missing_fields_without_blocking(tmp_path):
    pdf = tmp_path / "resume.pdf"
    pdf.touch()
    with mock.patch(
        "verify_submission.subprocess.run",
        return_value=_pdf_result("# Alex Example\n## PROFESSIONAL SUMMARY\n"),
    ):
        result = _check_pdf_parseability(str(pdf), RESUME, "resume")
    assert result["checked"] is True
    assert "contact" in result["missing"]
    assert "experience[0].company" in result["missing"]


def test_pdf_parseability_checks_cover_letter_boundaries(tmp_path):
    pdf = tmp_path / "cover.pdf"
    pdf.touch()
    with mock.patch("verify_submission.subprocess.run", return_value=_pdf_result(COVER)):
        result = _check_pdf_parseability(str(pdf), COVER, "cover_letter")
    assert result["fields"]["greeting"] is True
    assert result["fields"]["signoff"] is True
    assert result["ok"] is True


def test_packet_ats_contract_reports_supported_missing_terms(tmp_path):
    packet = {
        "ats_term_contract": [
            {
                "term": "Product Analytics",
                "claim_ids": ["ACC-117"],
                "jd_items": ["Own product analytics"],
            }
        ]
    }
    (tmp_path / "authoring_packet.json").write_text(json.dumps(packet), encoding="utf-8")
    result = _check_packet_ats_contract(str(tmp_path), RESUME)
    assert result["checked"] is True
    assert result["missing_supported_terms"] == ["Product Analytics"]
    assert result["terms"][0]["claim_ids"] == ["ACC-117"]
