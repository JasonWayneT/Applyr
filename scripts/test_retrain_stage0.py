"""No provider calls or live model writes in Stage 0 retraining tests."""

import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import retrain_stage0
import build_stage0_fit_gate


def _write(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class RetrainStage0Tests(unittest.TestCase):
    def test_fallback_response_does_not_create_training_feedback(self):
        class AmbiguousPipeline:
            classes_ = ["required", "preferred"]

            def predict(self, lines):
                return ["required"]

            def predict_proba(self, lines):
                return [[0.55, 0.45]]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "data" / "stage0_classifier.pkl").touch()
            with patch.object(build_stage0_fit_gate, "_REPO_ROOT", root), patch(
                "joblib.load", return_value=AmbiguousPipeline()
            ), patch("utils.call_llm", return_value='{"0": "required"}'), patch(
                "pipeline_env.stage0_section_mode", return_value="nlp"
            ):
                result = build_stage0_fit_gate._extract_sections_nlp(
                    "Requirements\nExperience managing complex product requirements across teams"
                )
            self.assertIn("Experience managing complex product requirements across teams", result["required"])
            self.assertFalse((root / "data" / "training_data_feedback.csv").exists())

    def test_company_split_has_no_group_overlap(self):
        rows = [{"text": f"Line {i}", "label": "required", "company": f"Company {i // 4}", "source_file": f"jd{i // 4}"} for i in range(40)]
        train, holdout = retrain_stage0.split_by_company(rows)
        self.assertTrue(train)
        self.assertTrue(holdout)
        self.assertFalse({row["company"] for row in train} & {row["company"] for row in holdout})

    def test_unreviewed_legacy_feedback_is_not_read_or_promoted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base.csv"
            reviewed = root / "approved.csv"
            candidate = root / "candidate.pkl"
            report = root / "report.json"
            rows = []
            for company in range(20):
                for label, wording in (("required", "Must have"), ("preferred", "Nice to have"),
                                       ("responsibilities", "You will own"), ("culture", "We offer")):
                    rows.append({"text": f"{wording} task {company} for the team", "label": label,
                                 "company": f"Firm{company}", "source_file": f"jd{company}"})
            _write(base, rows)
            _write(root / "training_data_feedback.csv", [{"text": "POISON", "label": "required", "company": "FeedbackLoop", "source_file": "fallback_api"}])
            with patch.object(retrain_stage0.joblib, "dump") as dump:
                result = retrain_stage0.train_candidate(base, reviewed, candidate, report)
            dump.assert_called_once()
            self.assertEqual(result["reviewed_rows"], 0)
            self.assertEqual(result["holdout_companies"], 4)
            self.assertFalse((root / "stage0_classifier.pkl").exists())

    def test_reviewed_rows_require_human_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "approved.csv"
            _write(path, [{"text": "Must have SQL", "label": "required", "company": "Acme",
                           "source_file": "jd1", "reviewed_by": "fallback_api", "reviewed_at": "2026-09-17T12:00:00Z"}])
            with self.assertRaisesRegex(ValueError, "human reviewer"):
                retrain_stage0.load_rows(path, reviewed=True)

    def test_promotion_report_binds_candidate_and_replay_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "candidate.pkl"
            candidate.write_bytes(b"candidate")
            report_path = root / "replay.json"
            report = {
                "candidate_sha256": hashlib.sha256(b"candidate").hexdigest(),
                "jd_count": 30,
                "false_skips": 0,
                "silent_losses": 0,
                "reviewed_by": "human reviewer",
                "reviewed_at": "2026-09-17T12:00:00Z",
            }
            report_path.write_text(json.dumps(report), encoding="utf-8")
            retrain_stage0.validate_replay_report(report_path, candidate)
            report["false_skips"] = 1
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "zero false skips"):
                retrain_stage0.validate_replay_report(report_path, candidate)
            report["false_skips"] = 0
            candidate.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "does not match"):
                retrain_stage0.validate_replay_report(report_path, candidate)
            candidate.write_bytes(b"candidate")
            report["candidate_sha256"] = hashlib.sha256(b"candidate").hexdigest()
            report["reviewed_by"] = "llm"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "human reviewer"):
                retrain_stage0.validate_replay_report(report_path, candidate)


if __name__ == "__main__":
    unittest.main()
