import json
import os
import tempfile

from fit_judgment_io import read_equivalence_judgment, write_equivalence_judgment

VALID_PAYLOAD = {
    "must_haves": [
        {"text": "5+ years PM experience", "judgment": "yes", "justification": "6 years at Cision"},
    ],
    "criteria": {
        "title_seniority_fit": {"judgment": "yes", "justification": "Senior PM title matches"},
        "pm_craft_overlap": {"judgment": "partial", "justification": "roadmap and cross-functional overlap"},
        "team_structure_fit": {"judgment": "yes", "justification": "structured team, not solo PM"},
        "execution_depth": {"judgment": "yes", "justification": "shipped ETL remediation end to end"},
        "transition_potential": {"judgment": "partial", "justification": "adjacent industry"},
    },
}


def test_write_then_read_round_trips_valid_payload():
    with tempfile.TemporaryDirectory() as folder:
        write_equivalence_judgment(folder, VALID_PAYLOAD)
        result = read_equivalence_judgment(folder)
        assert result == VALID_PAYLOAD


def test_read_returns_none_when_file_missing():
    with tempfile.TemporaryDirectory() as folder:
        assert read_equivalence_judgment(folder) is None


def test_read_returns_none_on_malformed_json():
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "fit_judgment.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{not valid json")
        assert read_equivalence_judgment(folder) is None


def test_read_returns_none_when_required_keys_missing():
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "fit_judgment.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"must_haves": []}, fh)  # missing "criteria"
        assert read_equivalence_judgment(folder) is None
