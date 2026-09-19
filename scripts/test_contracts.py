#!/usr/bin/env python3
"""
Tests for contracts.py (CR-075 Epic 2, Story 2.1).
# Implements FR-256

Baseline coverage for all five existing contract functions -- this file did not exist before
this story (verified: no other scripts/test_*.py imports contracts, per the CR-075 epics doc's
Story 2.1 note). It exists specifically to give the rest of CR-075's Epic 2 work (making
check_freshness hash-aware) a regression net before that function changes.

Run with:
    .venv\\Scripts\\python.exe -m unittest scripts.test_contracts -v
    (or) python scripts/test_contracts.py

No cloud LLM calls. All I/O uses temp directories.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contracts import (
    check_draft_manifest,
    check_finalize_ready,
    check_freshness,
    check_rubric_floors,
    check_rubric_score_provenance,
    check_stage0_fit_gate,
    check_stage1_ready,
    check_stage2_ready,
    check_verification_receipt,
    load_json,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_VALID_STAGE0: dict = {
    "company": "TestCo",
    "required": ["5+ years product management"],
    "preferred": ["Agile experience"],
    "responsibilities": ["Own the roadmap"],
    "flagged_gaps": [],
    "stage_signal": "unknown",
    "thin_jd": False,
}

_VALID_MANIFEST: dict = {
    "company": "TestCo",
    "title": "Product Manager",
    "verification_passed": True,
    "rubric_score": {
        "resume": {"total": 78},
        "cover_letter": {"total": 70},
    },
}

_VALID_RECEIPT: dict = {
    "submission": "TestCo",
    "mechanically_verified": True,
    "lint_all_clean": True,
    "unapproved_metrics_clean": True,
    "page_counts_ok": True,
    "check_resume": {"passed": True},
    "check_cover_letter": {"passed": True},
}

_VALID_PACKET: dict = {
    "company": "TestCo",
    "packet_status": "ready",
    "incomplete_reasons": [],
}

# -- CR-075 Epic 3 Story 3.3 fixtures: check_stage2_ready() ---------------------------------

_VALID_LINT_CLEAN: list = [
    {"document": "Resume.md", "doc_type": "resume", "status": "PASS", "blocks": [], "warns": [], "infos": []},
    {"document": "CoverLetter.md", "doc_type": "cover_letter", "status": "PASS", "blocks": [], "warns": [], "infos": []},
]

_VALID_RUBRIC_AUDIT_CLEAN: dict = {"ran": True, "clean": True, "findings": []}

_VALID_CLAIM_PROVENANCE_CLEAN: dict = {"ran": True, "ok": True, "findings": []}

_STAGE2_RESUME_CONTENT = "resume body"
_STAGE2_COVER_CONTENT = "cover letter body"


def _write_json(folder: Path, name: str, data: dict) -> Path:
    p = folder / name
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return p


def _write_text(folder: Path, name: str, content: str = "content") -> Path:
    p = folder / name
    p.write_text(content, encoding="utf-8")
    return p


def _hash(content: str) -> str:
    """sha256 hex digest of a string's utf-8 bytes -- matches how verify_submission.py's
    _sha256_hex (and contracts.py's own copy of it) hash file content, for building
    content_hashes fixtures."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _doc_hashes(resume_content: str = _STAGE2_RESUME_CONTENT, cover_content: str = _STAGE2_COVER_CONTENT) -> dict:
    return {
        "resume": _hash(resume_content),
        "cover_letter": _hash(cover_content),
    }


def _rubric_sha() -> str:
    rubric = Path(__file__).resolve().parents[1] / "data" / "conversion_rubric.md"
    return hashlib.sha256(rubric.read_bytes()).hexdigest()


def _criterion_breakdown(max_values: dict[str, int], total: float) -> dict:
    remaining = float(total)
    breakdown = {}
    for key, max_value in max_values.items():
        value = min(remaining, float(max_value))
        breakdown[key] = value
        remaining -= value
    return breakdown


def _resume_breakdown(total: float = 78) -> dict:
    return _criterion_breakdown(
        {"R1": 10, "R2": 15, "R3": 15, "R4": 20, "R5": 15, "R6": 10, "R7": 10, "R8": 5},
        total,
    )


def _cover_breakdown(total: float = 70) -> dict:
    return _criterion_breakdown({"C1": 25, "C2": 25, "C3": 20, "C4": 20, "C5": 10}, total)


def _score(
    resume_total: float = 78,
    cover_total: float = 70,
    *,
    hashes: dict | None = None,
) -> dict:
    return {
        "document_sha256": hashes or _doc_hashes(),
        "resume": {"total": resume_total},
        "cover_letter": {"total": cover_total},
    }


def _scorecard_row(
    resume_total: float = 78,
    cover_total: float = 70,
    *,
    role: str = "authoring_session",
    hashes: dict | None = None,
) -> dict:
    return {
        "schema_version": 1,
        "rubric_sha256": _rubric_sha(),
        "scored_at": "2026-09-15T00:00:00+00:00",
        "reviewer_run_id": "test-run-001",
        "reviewer_role": role,
        "document_sha256": hashes or _doc_hashes(),
        "resume": {"total": resume_total, "breakdown": _resume_breakdown(resume_total), "citations": {}},
        "cover_letter": {"total": cover_total, "breakdown": _cover_breakdown(cover_total), "citations": {}},
    }


def _needs_blind(side: str, total: float) -> bool:
    if side == "resume":
        return 67 <= total <= 73
    return 62 <= total <= 68


def _write_scorecards(
    folder: Path,
    *,
    resume_total: float = 78,
    cover_total: float = 70,
    hashes: dict | None = None,
    rows: list[dict] | None = None,
) -> None:
    if rows is None:
        rows = [_scorecard_row(resume_total, cover_total, hashes=hashes)]
        if _needs_blind("resume", resume_total) or _needs_blind("cover_letter", cover_total):
            rows.append(
                _scorecard_row(
                    resume_total,
                    cover_total,
                    role="independent_blind",
                    hashes=hashes,
                )
            )
    reviews = folder / "reviews"
    reviews.mkdir(exist_ok=True)
    _write_json(reviews, "rubric_scorecard.json", rows)


def _write_stage2_ready_fixture(
    folder: Path,
    receipt_overrides: dict | None = None,
    manifest_overrides: dict | None = None,
    receipt_omit_keys: list | None = None,
    manifest_omit_keys: list | None = None,
    write_resume: bool = True,
    write_cover: bool = True,
) -> None:
    """Writes a folder that satisfies check_stage2_ready() in full: matching-hash
    Resume.md/CoverLetter.md, a receipt newer than both with clean lint/rubric_audit/
    claim_provenance, and a draft_manifest.json with a populated rubric_score. Individual
    tests pass receipt_overrides/manifest_overrides (or the *_omit_keys lists, since dict.update
    can't delete a key) to break exactly one requirement at a time."""
    now = time.time()
    if write_resume:
        resume = _write_text(folder, "Resume.md", _STAGE2_RESUME_CONTENT)
        os.utime(resume, (now - 100, now - 100))
    if write_cover:
        cover = _write_text(folder, "CoverLetter.md", _STAGE2_COVER_CONTENT)
        os.utime(cover, (now - 100, now - 100))

    receipt_data = {
        **_VALID_RECEIPT,
        "lint": _VALID_LINT_CLEAN,
        "content_hashes": {
            "algorithm": "sha256",
            "Resume.md": _hash(_STAGE2_RESUME_CONTENT),
            "CoverLetter.md": _hash(_STAGE2_COVER_CONTENT),
        },
        "rubric_audit": _VALID_RUBRIC_AUDIT_CLEAN,
        "claim_provenance": _VALID_CLAIM_PROVENANCE_CLEAN,
    }
    if receipt_overrides:
        receipt_data.update(receipt_overrides)
    for key in receipt_omit_keys or []:
        receipt_data.pop(key, None)
    receipt = _write_json(folder, "verification_receipt.json", receipt_data)
    os.utime(receipt, (now, now))

    manifest_data = {**_VALID_MANIFEST}
    if manifest_overrides:
        manifest_data.update(manifest_overrides)
    score = manifest_data.get("rubric_score")
    if isinstance(score, dict) and isinstance(score.get("resume"), dict) and isinstance(score.get("cover_letter"), dict):
        resume_total = score["resume"].get("total", 78)
        cover_total = score["cover_letter"].get("total", 70)
        if isinstance(resume_total, (int, float)) and isinstance(cover_total, (int, float)):
            hashes = _doc_hashes(
                _STAGE2_RESUME_CONTENT if write_resume else "",
                _STAGE2_COVER_CONTENT if write_cover else "",
            )
            score = {**score, "document_sha256": hashes}
            manifest_data["rubric_score"] = score
            if resume_total >= 70 and cover_total >= 65 and write_resume and write_cover:
                _write_scorecards(
                    folder,
                    resume_total=resume_total,
                    cover_total=cover_total,
                    hashes=hashes,
                )
    for key in manifest_omit_keys or []:
        manifest_data.pop(key, None)
    _write_json(folder, "draft_manifest.json", manifest_data)


# ---------------------------------------------------------------------------
# load_json
# ---------------------------------------------------------------------------

class TestLoadJson(unittest.TestCase):

    def test_missing_file_returns_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data, err = load_json(os.path.join(tmpdir, "nope.json"))
            self.assertIsNone(data)
            self.assertIn("not found", err)

    def test_invalid_json_returns_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad.json"
            path.write_text("{not valid json", encoding="utf-8")
            data, err = load_json(str(path))
            self.assertIsNone(data)
            self.assertIn("could not be read/parsed", err)

    def test_non_dict_json_returns_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "list.json"
            path.write_text("[1, 2, 3]", encoding="utf-8")
            data, err = load_json(str(path))
            self.assertIsNone(data)
            self.assertIn("not a JSON object", err)

    def test_valid_dict_json_loads(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ok.json"
            path.write_text('{"a": 1}', encoding="utf-8")
            data, err = load_json(str(path))
            self.assertIsNone(err)
            self.assertEqual(data, {"a": 1})


# ---------------------------------------------------------------------------
# check_stage0_fit_gate
# ---------------------------------------------------------------------------

class TestCheckStage0FitGate(unittest.TestCase):

    def test_missing_file_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ok, errors = check_stage0_fit_gate(tmpdir)
            self.assertFalse(ok)
            self.assertIn("stage0_fit_gate.json not found", errors[0])

    def test_valid_fixture_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_json(Path(tmpdir), "stage0_fit_gate.json", _VALID_STAGE0)
            ok, errors = check_stage0_fit_gate(tmpdir)
            self.assertTrue(ok, errors)
            self.assertEqual(errors, [])

    def test_missing_company_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {**_VALID_STAGE0, "company": ""}
            _write_json(Path(tmpdir), "stage0_fit_gate.json", data)
            ok, errors = check_stage0_fit_gate(tmpdir)
            self.assertFalse(ok)
            self.assertTrue(any("company" in e for e in errors))

    def test_list_key_wrong_type_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {**_VALID_STAGE0, "required": "not a list"}
            _write_json(Path(tmpdir), "stage0_fit_gate.json", data)
            ok, errors = check_stage0_fit_gate(tmpdir)
            self.assertFalse(ok)
            self.assertTrue(any("'required' must be a list" in e for e in errors))

    def test_missing_stage_signal_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {**_VALID_STAGE0, "stage_signal": ""}
            _write_json(Path(tmpdir), "stage0_fit_gate.json", data)
            ok, errors = check_stage0_fit_gate(tmpdir)
            self.assertFalse(ok)
            self.assertTrue(any("stage_signal" in e for e in errors))

    def test_thin_jd_missing_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {k: v for k, v in _VALID_STAGE0.items() if k != "thin_jd"}
            _write_json(Path(tmpdir), "stage0_fit_gate.json", data)
            ok, errors = check_stage0_fit_gate(tmpdir)
            self.assertFalse(ok)
            self.assertTrue(any("thin_jd" in e for e in errors))

    def test_thin_jd_non_bool_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {**_VALID_STAGE0, "thin_jd": "false"}
            _write_json(Path(tmpdir), "stage0_fit_gate.json", data)
            ok, errors = check_stage0_fit_gate(tmpdir)
            self.assertFalse(ok)
            self.assertTrue(any("thin_jd" in e for e in errors))


# ---------------------------------------------------------------------------
# check_draft_manifest
# ---------------------------------------------------------------------------

class TestCheckDraftManifest(unittest.TestCase):

    def test_missing_file_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ok, errors = check_draft_manifest(tmpdir)
            self.assertFalse(ok)
            self.assertIn("draft_manifest.json not found", errors[0])

    def test_valid_fixture_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_json(Path(tmpdir), "draft_manifest.json", _VALID_MANIFEST)
            ok, errors = check_draft_manifest(tmpdir)
            self.assertTrue(ok, errors)
            self.assertEqual(errors, [])

    def test_missing_title_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {**_VALID_MANIFEST, "title": ""}
            _write_json(Path(tmpdir), "draft_manifest.json", data)
            ok, errors = check_draft_manifest(tmpdir)
            self.assertFalse(ok)
            self.assertTrue(any("title" in e for e in errors))

    def test_verification_passed_missing_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {k: v for k, v in _VALID_MANIFEST.items() if k != "verification_passed"}
            _write_json(Path(tmpdir), "draft_manifest.json", data)
            ok, errors = check_draft_manifest(tmpdir)
            self.assertFalse(ok)
            self.assertTrue(any("verification_passed" in e for e in errors))

    def test_verification_passed_non_bool_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {**_VALID_MANIFEST, "verification_passed": "yes"}
            _write_json(Path(tmpdir), "draft_manifest.json", data)
            ok, errors = check_draft_manifest(tmpdir)
            self.assertFalse(ok)
            self.assertTrue(any("verification_passed" in e for e in errors))

    def test_rubric_score_not_dict_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {**_VALID_MANIFEST, "rubric_score": "not scored yet"}
            _write_json(Path(tmpdir), "draft_manifest.json", data)
            ok, errors = check_draft_manifest(tmpdir)
            self.assertFalse(ok)
            self.assertTrue(any("rubric_score" in e for e in errors))

    def test_rubric_score_missing_side_total_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {**_VALID_MANIFEST, "rubric_score": {"resume": {"total": 78}}}
            _write_json(Path(tmpdir), "draft_manifest.json", data)
            ok, errors = check_draft_manifest(tmpdir)
            self.assertFalse(ok)
            self.assertTrue(any("cover_letter.total" in e for e in errors))

    def test_resume_below_floor_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {
                **_VALID_MANIFEST,
                "rubric_score": {"resume": {"total": 68}, "cover_letter": {"total": 69}},
            }
            _write_json(Path(tmpdir), "draft_manifest.json", data)
            ok, errors = check_draft_manifest(tmpdir)
            self.assertFalse(ok)
            self.assertTrue(any("resume" in e and "70" in e for e in errors))

    def test_cover_letter_below_floor_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {
                **_VALID_MANIFEST,
                "rubric_score": {"resume": {"total": 70}, "cover_letter": {"total": 64}},
            }
            _write_json(Path(tmpdir), "draft_manifest.json", data)
            ok, errors = check_draft_manifest(tmpdir)
            self.assertFalse(ok)
            self.assertTrue(any("cover_letter" in e and "65" in e for e in errors))

    def test_exact_floors_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {
                **_VALID_MANIFEST,
                "rubric_score": {"resume": {"total": 70}, "cover_letter": {"total": 65}},
            }
            _write_json(Path(tmpdir), "draft_manifest.json", data)
            ok, errors = check_draft_manifest(tmpdir)
            self.assertTrue(ok, errors)

    def test_resume_69_9_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {
                **_VALID_MANIFEST,
                "rubric_score": {"resume": {"total": 69.9}, "cover_letter": {"total": 65}},
            }
            _write_json(Path(tmpdir), "draft_manifest.json", data)
            ok, errors = check_draft_manifest(tmpdir)
            self.assertFalse(ok)
            self.assertTrue(any("resume" in e and "70" in e for e in errors))

    def test_nan_total_fails_shape(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {
                **_VALID_MANIFEST,
                "rubric_score": {"resume": {"total": float("nan")}, "cover_letter": {"total": 65}},
            }
            _write_json(Path(tmpdir), "draft_manifest.json", data)
            ok, errors = check_draft_manifest(tmpdir)
            self.assertFalse(ok)
            self.assertTrue(any("resume.total" in e for e in errors))
            self.assertFalse(any("CONVERT-READY floor" in e for e in errors))


# ---------------------------------------------------------------------------
# check_rubric_floors (CR-112 completion contract)
# ---------------------------------------------------------------------------

class TestCheckRubricFloors(unittest.TestCase):
    """Negative controls: floors are independent of shape errors."""

    def test_camunda_shaped_68_69_fails_resume(self):
        errors = check_rubric_floors({"resume": {"total": 68}, "cover_letter": {"total": 69}})
        self.assertTrue(any("resume" in e and "70" in e for e in errors))
        self.assertFalse(any("cover_letter" in e and "65" in e for e in errors))

    def test_resume_69_9_fails(self):
        errors = check_rubric_floors({"resume": {"total": 69.9}, "cover_letter": {"total": 65}})
        self.assertTrue(any("resume" in e and "70" in e for e in errors))

    def test_exact_floors_empty(self):
        self.assertEqual(
            check_rubric_floors({"resume": {"total": 70}, "cover_letter": {"total": 65}}),
            [],
        )

    def test_missing_score_is_shape_not_floor(self):
        self.assertEqual(check_rubric_floors("not scored yet"), [])
        self.assertEqual(check_rubric_floors({"resume": {"total": 78}}), [])

    def test_nan_is_shape_not_a_passing_floor(self):
        self.assertEqual(
            check_rubric_floors({"resume": {"total": float("nan")}, "cover_letter": {"total": 65}}),
            [],
        )


# ---------------------------------------------------------------------------
# check_rubric_score_provenance (CR-112 Story 8.6 / FR-322)
# ---------------------------------------------------------------------------

class TestCheckRubricScoreProvenance(unittest.TestCase):

    def _write_docs(self, folder: Path, resume: str = _STAGE2_RESUME_CONTENT, cover: str = _STAGE2_COVER_CONTENT) -> dict:
        _write_text(folder, "Resume.md", resume)
        _write_text(folder, "CoverLetter.md", cover)
        return _doc_hashes(resume, cover)

    def test_resume_78_needs_no_blind_row(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            hashes = self._write_docs(folder)
            score = _score(78, 70, hashes=hashes)
            _write_scorecards(folder, resume_total=78, cover_total=70, hashes=hashes)
            self.assertEqual(check_rubric_score_provenance(str(folder), score), [])

    def test_stale_document_hash_blocks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            old_hashes = self._write_docs(folder, resume="old resume", cover=_STAGE2_COVER_CONTENT)
            score = _score(78, 70, hashes=old_hashes)
            _write_scorecards(folder, resume_total=78, cover_total=70, hashes=old_hashes)
            (folder / "Resume.md").write_text("edited resume", encoding="utf-8")
            errors = check_rubric_score_provenance(str(folder), score)
            self.assertTrue(any("document_sha256" in e or "no scorecard row" in e for e in errors), errors)

    def test_current_hash_70_and_68_blocks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            hashes = self._write_docs(folder)
            score = _score(70, 70, hashes=hashes)
            _write_scorecards(
                folder,
                rows=[
                    _scorecard_row(70, 70, role="correcting_implementer", hashes=hashes),
                    _scorecard_row(68, 70, role="independent_blind", hashes=hashes),
                ],
            )
            errors = check_rubric_score_provenance(str(folder), score)
            self.assertTrue(any("below 70" in e and "disagreement" in e for e in errors), errors)

    def test_resume_70_plus_blind_71_completes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            hashes = self._write_docs(folder)
            score = _score(70, 70, hashes=hashes)
            _write_scorecards(
                folder,
                rows=[
                    _scorecard_row(70, 70, role="correcting_implementer", hashes=hashes),
                    _scorecard_row(71, 70, role="independent_blind", hashes=hashes),
                ],
            )
            self.assertEqual(check_rubric_score_provenance(str(folder), score), [])

    def test_boundary_score_without_blind_blocks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            hashes = self._write_docs(folder)
            score = _score(70, 70, hashes=hashes)
            _write_scorecards(
                folder,
                rows=[_scorecard_row(70, 70, role="correcting_implementer", hashes=hashes)],
            )
            errors = check_rubric_score_provenance(str(folder), score)
            self.assertTrue(any("independent_blind" in e for e in errors), errors)

    def test_scorecard_missing_schema_version_blocks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            hashes = self._write_docs(folder)
            score = _score(78, 70, hashes=hashes)
            row = _scorecard_row(78, 70, hashes=hashes)
            row.pop("schema_version")
            _write_scorecards(folder, rows=[row])
            errors = check_rubric_score_provenance(str(folder), score)
            self.assertTrue(any("schema_version" in e for e in errors), errors)

    def test_scorecard_stale_rubric_hash_blocks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            hashes = self._write_docs(folder)
            score = _score(78, 70, hashes=hashes)
            row = _scorecard_row(78, 70, hashes=hashes)
            row["rubric_sha256"] = "0" * 64
            _write_scorecards(folder, rows=[row])
            errors = check_rubric_score_provenance(str(folder), score)
            self.assertTrue(any("rubric_sha256" in e for e in errors), errors)

    def test_scorecard_bad_scored_at_blocks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            hashes = self._write_docs(folder)
            score = _score(78, 70, hashes=hashes)
            row = _scorecard_row(78, 70, hashes=hashes)
            row["scored_at"] = "2026-09-15 00:00:00"
            _write_scorecards(folder, rows=[row])
            errors = check_rubric_score_provenance(str(folder), score)
            self.assertTrue(any("scored_at" in e for e in errors), errors)

    def test_scorecard_missing_reviewer_run_metadata_blocks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            hashes = self._write_docs(folder)
            score = _score(78, 70, hashes=hashes)
            row = _scorecard_row(78, 70, hashes=hashes)
            row.pop("reviewer_run_id")
            _write_scorecards(folder, rows=[row])
            errors = check_rubric_score_provenance(str(folder), score)
            self.assertTrue(any("reviewer_run_id" in e or "spawned_by" in e for e in errors), errors)

    def test_scorecard_extra_breakdown_keys_block(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            hashes = self._write_docs(folder)
            score = _score(78, 70, hashes=hashes)
            row = _scorecard_row(78, 70, hashes=hashes)
            row["resume"]["breakdown"]["R9"] = 5
            _write_scorecards(folder, rows=[row])
            errors = check_rubric_score_provenance(str(folder), score)
            self.assertTrue(any("breakdown has unknown keys" in e and "R9" in e for e in errors), errors)

    def test_scorecard_incomplete_breakdown_blocks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            hashes = self._write_docs(folder)
            score = _score(78, 70, hashes=hashes)
            row = _scorecard_row(78, 70, hashes=hashes)
            row["resume"]["breakdown"].pop("R8")
            _write_scorecards(folder, rows=[row])
            errors = check_rubric_score_provenance(str(folder), score)
            self.assertTrue(any("breakdown missing keys" in e and "R8" in e for e in errors), errors)

    def test_scorecard_boolean_breakdown_blocks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            hashes = self._write_docs(folder)
            score = _score(78, 70, hashes=hashes)
            row = _scorecard_row(78, 70, hashes=hashes)
            row["resume"]["breakdown"]["R1"] = True
            _write_scorecards(folder, rows=[row])
            errors = check_rubric_score_provenance(str(folder), score)
            self.assertTrue(any("breakdown.R1 must be a finite number" in e for e in errors), errors)

    def test_scorecard_over_max_breakdown_blocks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            hashes = self._write_docs(folder)
            score = _score(78, 70, hashes=hashes)
            row = _scorecard_row(78, 70, hashes=hashes)
            row["resume"]["breakdown"]["R8"] = 6
            _write_scorecards(folder, rows=[row])
            errors = check_rubric_score_provenance(str(folder), score)
            self.assertTrue(any("breakdown.R8 must be between 0 and 5" in e for e in errors), errors)

    def test_scorecard_breakdown_sum_must_match_total(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            hashes = self._write_docs(folder)
            score = _score(78, 70, hashes=hashes)
            row = _scorecard_row(78, 70, hashes=hashes)
            row["cover_letter"]["breakdown"]["C5"] = 6
            _write_scorecards(folder, rows=[row])
            errors = check_rubric_score_provenance(str(folder), score)
            self.assertTrue(any("breakdown sum must equal cover_letter.total" in e for e in errors), errors)


# ---------------------------------------------------------------------------
# check_verification_receipt
# ---------------------------------------------------------------------------

class TestCheckVerificationReceipt(unittest.TestCase):

    def test_missing_file_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ok, errors = check_verification_receipt(tmpdir)
            self.assertFalse(ok)
            self.assertIn("verification_receipt.json not found", errors[0])

    def test_valid_fixture_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_json(Path(tmpdir), "verification_receipt.json", _VALID_RECEIPT)
            ok, errors = check_verification_receipt(tmpdir)
            self.assertTrue(ok, errors)
            self.assertEqual(errors, [])

    def test_missing_submission_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {**_VALID_RECEIPT, "submission": ""}
            _write_json(Path(tmpdir), "verification_receipt.json", data)
            ok, errors = check_verification_receipt(tmpdir)
            self.assertFalse(ok)
            self.assertTrue(any("submission" in e for e in errors))

    def test_missing_bool_key_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {k: v for k, v in _VALID_RECEIPT.items() if k != "lint_all_clean"}
            _write_json(Path(tmpdir), "verification_receipt.json", data)
            ok, errors = check_verification_receipt(tmpdir)
            self.assertFalse(ok)
            self.assertTrue(any("lint_all_clean" in e for e in errors))

    def test_check_resume_missing_passed_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {**_VALID_RECEIPT, "check_resume": {}}
            _write_json(Path(tmpdir), "verification_receipt.json", data)
            ok, errors = check_verification_receipt(tmpdir)
            self.assertFalse(ok)
            self.assertTrue(any("check_resume.passed" in e for e in errors))

    def test_mechanically_verified_false_fails_with_specific_message(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {**_VALID_RECEIPT, "mechanically_verified": False}
            _write_json(Path(tmpdir), "verification_receipt.json", data)
            ok, errors = check_verification_receipt(tmpdir)
            self.assertFalse(ok)
            self.assertTrue(any("mechanically_verified is False" in e for e in errors))


# ---------------------------------------------------------------------------
# check_freshness
# ---------------------------------------------------------------------------

class TestCheckFreshness(unittest.TestCase):

    def test_missing_receipt_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ok, errors = check_freshness(tmpdir)
            self.assertFalse(ok)
            self.assertIn("verification_receipt.json not found", errors[0])

    def test_receipt_newer_than_docs_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            now = time.time()
            resume = _write_text(folder, "Resume.md")
            cover = _write_text(folder, "CoverLetter.md")
            os.utime(resume, (now - 100, now - 100))
            os.utime(cover, (now - 100, now - 100))
            receipt = _write_json(folder, "verification_receipt.json", _VALID_RECEIPT)
            os.utime(receipt, (now, now))

            ok, errors = check_freshness(tmpdir)
            self.assertTrue(ok, errors)
            self.assertEqual(errors, [])

    def test_resume_edited_after_receipt_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            now = time.time()
            receipt = _write_json(folder, "verification_receipt.json", _VALID_RECEIPT)
            os.utime(receipt, (now - 100, now - 100))
            resume = _write_text(folder, "Resume.md")
            os.utime(resume, (now, now))
            cover = _write_text(folder, "CoverLetter.md")
            os.utime(cover, (now - 100, now - 100))

            ok, errors = check_freshness(tmpdir)
            self.assertFalse(ok)
            self.assertTrue(any("Resume.md was edited after" in e for e in errors))

    def test_cover_letter_edited_after_receipt_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            now = time.time()
            receipt = _write_json(folder, "verification_receipt.json", _VALID_RECEIPT)
            os.utime(receipt, (now - 100, now - 100))
            resume = _write_text(folder, "Resume.md")
            os.utime(resume, (now - 100, now - 100))
            cover = _write_text(folder, "CoverLetter.md")
            os.utime(cover, (now, now))

            ok, errors = check_freshness(tmpdir)
            self.assertFalse(ok)
            self.assertTrue(any("CoverLetter.md was edited after" in e for e in errors))

    def test_missing_docs_do_not_fail_freshness(self):
        """Freshness only compares docs that exist -- an absent Resume.md/CoverLetter.md is not
        itself a freshness failure (that's check_verification_receipt's / check_draft_manifest's
        job to catch a missing document some other way)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            receipt = _write_json(Path(tmpdir), "verification_receipt.json", _VALID_RECEIPT)
            ok, errors = check_freshness(tmpdir)
            self.assertTrue(ok, errors)

    # -- CR-075 Epic 2 Story 2.3: hash-aware freshness -------------------------------------

    def test_hash_match_with_newer_mtime_reads_fresh(self):
        """Simulates a `touch`: content is unchanged but mtime is bumped past the receipt's own
        mtime. Mtime alone would call this stale (as the pre-Story-2.3 behavior did) -- once the
        receipt carries content_hashes, the hash comparison must override that and read fresh."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            now = time.time()
            resume_content = "resume body"
            cover_content = "cover letter body"
            resume = _write_text(folder, "Resume.md", resume_content)
            cover = _write_text(folder, "CoverLetter.md", cover_content)
            os.utime(resume, (now - 100, now - 100))
            os.utime(cover, (now - 100, now - 100))

            receipt_data = {
                **_VALID_RECEIPT,
                "content_hashes": {
                    "algorithm": "sha256",
                    "Resume.md": _hash(resume_content),
                    "CoverLetter.md": _hash(cover_content),
                },
            }
            receipt = _write_json(folder, "verification_receipt.json", receipt_data)
            os.utime(receipt, (now - 50, now - 50))

            # Simulate a touch: bump mtime forward past the receipt's own mtime, content untouched.
            os.utime(resume, (now, now))
            os.utime(cover, (now, now))

            ok, errors = check_freshness(str(folder))
            self.assertTrue(ok, errors)
            self.assertEqual(errors, [])

    def test_hash_mismatch_with_unchanged_mtime_reads_stale(self):
        """Content changed but mtime never moved past the receipt's own mtime -- mtime alone
        would call this fresh. Once the receipt carries content_hashes, the hash comparison must
        override that and read stale."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            now = time.time()
            resume_content = "original resume body"
            cover_content = "original cover body"
            resume = _write_text(folder, "Resume.md", resume_content)
            cover = _write_text(folder, "CoverLetter.md", cover_content)
            os.utime(resume, (now - 100, now - 100))
            os.utime(cover, (now - 100, now - 100))

            receipt_data = {
                **_VALID_RECEIPT,
                "content_hashes": {
                    "algorithm": "sha256",
                    "Resume.md": _hash(resume_content),
                    "CoverLetter.md": _hash(cover_content),
                },
            }
            receipt = _write_json(folder, "verification_receipt.json", receipt_data)
            os.utime(receipt, (now, now))

            # Change content but leave mtime at the old (pre-receipt) timestamp -- no `touch`.
            resume.write_text("edited resume body", encoding="utf-8")
            os.utime(resume, (now - 100, now - 100))

            ok, errors = check_freshness(str(folder))
            self.assertFalse(ok)
            self.assertTrue(
                any("Resume.md content does not match the hash" in e for e in errors), errors
            )

    def test_legacy_receipt_without_content_hashes_uses_mtime_only(self):
        """A receipt with no content_hashes field at all (every receipt written before Story 2.2)
        must behave exactly as it did before this story -- mtime-only, no hash comparison
        attempted or required."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            now = time.time()
            self.assertNotIn("content_hashes", _VALID_RECEIPT)
            resume = _write_text(folder, "Resume.md")
            cover = _write_text(folder, "CoverLetter.md")
            os.utime(resume, (now - 100, now - 100))
            os.utime(cover, (now - 100, now - 100))
            receipt = _write_json(folder, "verification_receipt.json", _VALID_RECEIPT)
            os.utime(receipt, (now, now))

            ok, errors = check_freshness(str(folder))
            self.assertTrue(ok, errors)


# ---------------------------------------------------------------------------
# check_finalize_ready
# ---------------------------------------------------------------------------

class TestCheckFinalizeReady(unittest.TestCase):

    def _write_all_valid(self, folder: Path) -> None:
        now = time.time()
        resume = _write_text(folder, "Resume.md")
        cover = _write_text(folder, "CoverLetter.md")
        os.utime(resume, (now - 100, now - 100))
        os.utime(cover, (now - 100, now - 100))
        receipt = _write_json(folder, "verification_receipt.json", _VALID_RECEIPT)
        os.utime(receipt, (now, now))
        hashes = _doc_hashes("content", "content")
        _write_json(
            folder,
            "draft_manifest.json",
            {**_VALID_MANIFEST, "rubric_score": _score(hashes=hashes)},
        )
        _write_scorecards(folder, hashes=hashes)

    def test_all_valid_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            self._write_all_valid(folder)
            ok, errors = check_finalize_ready(str(folder))
            self.assertTrue(ok, errors)
            self.assertEqual(errors, [])

    def test_exact_floors_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            self._write_all_valid(folder)
            manifest = {
                **_VALID_MANIFEST,
                "rubric_score": _score(70, 65, hashes=_doc_hashes("content", "content")),
            }
            _write_json(folder, "draft_manifest.json", manifest)
            _write_scorecards(
                folder,
                resume_total=70,
                cover_total=65,
                hashes=_doc_hashes("content", "content"),
            )
            ok, errors = check_finalize_ready(str(folder))
            self.assertTrue(ok, errors)

    def test_resume_below_floor_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            self._write_all_valid(folder)
            manifest = {
                **_VALID_MANIFEST,
                "rubric_score": _score(68, 69, hashes=_doc_hashes("content", "content")),
            }
            _write_json(folder, "draft_manifest.json", manifest)
            ok, errors = check_finalize_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("resume" in e and "70" in e for e in errors))

    def test_missing_receipt_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _write_json(folder, "draft_manifest.json", _VALID_MANIFEST)
            ok, errors = check_finalize_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("verification_receipt.json not found" in e for e in errors))

    def test_missing_manifest_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            now = time.time()
            resume = _write_text(folder, "Resume.md")
            cover = _write_text(folder, "CoverLetter.md")
            os.utime(resume, (now - 100, now - 100))
            os.utime(cover, (now - 100, now - 100))
            receipt = _write_json(folder, "verification_receipt.json", _VALID_RECEIPT)
            os.utime(receipt, (now, now))
            ok, errors = check_finalize_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("draft_manifest.json not found" in e for e in errors))

    def test_manifest_verification_passed_false_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            self._write_all_valid(folder)
            manifest = {**_VALID_MANIFEST, "verification_passed": False}
            _write_json(folder, "draft_manifest.json", manifest)
            ok, errors = check_finalize_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("verification_passed is not True" in e for e in errors))

    def test_stale_receipt_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            now = time.time()
            receipt = _write_json(folder, "verification_receipt.json", _VALID_RECEIPT)
            os.utime(receipt, (now - 100, now - 100))
            resume = _write_text(folder, "Resume.md")
            os.utime(resume, (now, now))
            cover = _write_text(folder, "CoverLetter.md")
            os.utime(cover, (now - 100, now - 100))
            _write_json(folder, "draft_manifest.json", _VALID_MANIFEST)

            ok, errors = check_finalize_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("Resume.md was edited after" in e for e in errors))


# ---------------------------------------------------------------------------
# check_stage1_ready (CR-075 Epic 3, Story 3.1/3.3)
# ---------------------------------------------------------------------------

class TestCheckStage1Ready(unittest.TestCase):

    def _write_all_valid(self, folder: Path) -> None:
        _write_json(folder, "authoring_packet.json", _VALID_PACKET)
        _write_text(folder, "Resume.md")
        _write_text(folder, "CoverLetter.md")
        _write_json(folder, "claim_provenance.json", _VALID_CLAIM_PROVENANCE_CLEAN)

    def test_valid_fixture_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            self._write_all_valid(folder)
            ok, errors = check_stage1_ready(str(folder))
            self.assertTrue(ok, errors)
            self.assertEqual(errors, [])

    def test_missing_packet_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _write_text(folder, "Resume.md")
            _write_text(folder, "CoverLetter.md")
            ok, errors = check_stage1_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("authoring_packet.json not found" in e for e in errors))

    def test_packet_status_incomplete_echoes_incomplete_reasons(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            data = {
                "company": "TestCo",
                "packet_status": "incomplete",
                "incomplete_reasons": ["unmapped required item: SQL", "disabled claim referenced: ACC-114"],
            }
            _write_json(folder, "authoring_packet.json", data)
            _write_text(folder, "Resume.md")
            _write_text(folder, "CoverLetter.md")
            ok, errors = check_stage1_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("unmapped required item: SQL" in e for e in errors))
            self.assertTrue(any("disabled claim referenced: ACC-114" in e for e in errors))

    def test_packet_status_incomplete_with_no_reasons_still_fails_with_specific_message(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            data = {"company": "TestCo", "packet_status": "incomplete", "incomplete_reasons": []}
            _write_json(folder, "authoring_packet.json", data)
            _write_text(folder, "Resume.md")
            _write_text(folder, "CoverLetter.md")
            ok, errors = check_stage1_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("packet_status is 'incomplete'" in e for e in errors))

    def test_missing_resume_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _write_json(folder, "authoring_packet.json", _VALID_PACKET)
            _write_text(folder, "CoverLetter.md")
            ok, errors = check_stage1_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("Resume.md not found" in e for e in errors))

    def test_missing_cover_letter_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _write_json(folder, "authoring_packet.json", _VALID_PACKET)
            _write_text(folder, "Resume.md")
            ok, errors = check_stage1_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("CoverLetter.md not found" in e for e in errors))

    def test_missing_claim_provenance_fails(self):
        """CR-092 (2026-08-15): claim_provenance.json's existence used to have no gate at
        all -- confirmed real on 2 of 4 real submissions in one batch, both advanced past
        Stage 1 with the file silently absent. Resume.md/CoverLetter.md present, packet
        ready, but the third promised Stage 1 artifact missing must now fail closed the
        same way the other two already do."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _write_json(folder, "authoring_packet.json", _VALID_PACKET)
            _write_text(folder, "Resume.md")
            _write_text(folder, "CoverLetter.md")
            ok, errors = check_stage1_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("claim_provenance.json not found" in e for e in errors))

    def test_empty_resume_is_not_stage1_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            self._write_all_valid(folder)
            (folder / "Resume.md").write_text("  \n", encoding="utf-8")
            ok, errors = check_stage1_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("Resume.md is empty" in e for e in errors))

    def test_empty_provenance_is_not_stage1_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            self._write_all_valid(folder)
            (folder / "claim_provenance.json").write_text("{}\n", encoding="utf-8")
            ok, errors = check_stage1_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("claim_provenance.json is empty or invalid" in e for e in errors))


# ---------------------------------------------------------------------------
# check_stage2_ready (CR-075 Epic 3, Story 3.2/3.3)
# ---------------------------------------------------------------------------

class TestCheckStage2Ready(unittest.TestCase):

    def test_all_valid_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _write_stage2_ready_fixture(folder)
            ok, errors = check_stage2_ready(str(folder))
            self.assertTrue(ok, errors)
            self.assertEqual(errors, [])

    def test_resume_below_floor_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _write_stage2_ready_fixture(
                folder,
                manifest_overrides={
                    "rubric_score": {"resume": {"total": 68}, "cover_letter": {"total": 69}},
                },
            )
            ok, errors = check_stage2_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("resume" in e and "70" in e for e in errors))

    def test_cover_letter_below_floor_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _write_stage2_ready_fixture(
                folder,
                manifest_overrides={
                    "rubric_score": {"resume": {"total": 70}, "cover_letter": {"total": 64}},
                },
            )
            ok, errors = check_stage2_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("cover_letter" in e and "65" in e for e in errors))

    def test_exact_floors_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _write_stage2_ready_fixture(
                folder,
                manifest_overrides={
                    "rubric_score": {"resume": {"total": 70}, "cover_letter": {"total": 65}},
                },
            )
            ok, errors = check_stage2_ready(str(folder))
            self.assertTrue(ok, errors)

    def test_resume_69_9_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _write_stage2_ready_fixture(
                folder,
                manifest_overrides={
                    "rubric_score": {"resume": {"total": 69.9}, "cover_letter": {"total": 65}},
                },
            )
            ok, errors = check_stage2_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("resume" in e and "70" in e for e in errors))

    def test_missing_receipt_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _write_json(folder, "draft_manifest.json", _VALID_MANIFEST)
            ok, errors = check_stage2_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("verification_receipt.json not found" in e for e in errors))

    def test_mechanically_verified_false_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _write_stage2_ready_fixture(folder, receipt_overrides={"mechanically_verified": False})
            ok, errors = check_stage2_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("mechanically_verified is False" in e for e in errors))

    def test_stale_receipt_fails(self):
        """Resume.md edited (different content, same recorded hash) after the receipt --
        exercises check_freshness()'s hash path inside the combined gate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _write_stage2_ready_fixture(folder)
            resume_path = folder / "Resume.md"
            now = time.time()
            resume_path.write_text("edited resume body", encoding="utf-8")
            os.utime(resume_path, (now - 100, now - 100))  # no mtime bump -- must be caught by hash
            ok, errors = check_stage2_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("Resume.md content does not match the hash" in e for e in errors))

    def test_missing_manifest_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _write_stage2_ready_fixture(folder)
            os.remove(folder / "draft_manifest.json")
            ok, errors = check_stage2_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("draft_manifest.json not found" in e for e in errors))

    def test_rubric_score_not_populated_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _write_stage2_ready_fixture(folder, manifest_omit_keys=["rubric_score"])
            ok, errors = check_stage2_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("rubric_score" in e for e in errors))

    def test_lint_all_clean_false_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _write_stage2_ready_fixture(folder, receipt_overrides={"lint_all_clean": False})
            ok, errors = check_stage2_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("lint_all_clean is not True" in e for e in errors))

    def test_lint_blocks_present_fails_even_if_lint_all_clean_says_true(self):
        """Defensive per-document assertion: a receipt where 'lint' actually records a HARD_BLOCK
        must fail this gate even if lint_all_clean itself (an inconsistent/stale receipt) still
        says True -- the story asks for both checks, not just the derived boolean."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            bad_lint = [
                {"document": "Resume.md", "doc_type": "resume", "status": "FAIL",
                 "blocks": [{"rule_id": "LR-014", "message": "semicolon found"}], "warns": [], "infos": []},
                _VALID_LINT_CLEAN[1],
            ]
            _write_stage2_ready_fixture(
                folder, receipt_overrides={"lint_all_clean": True, "lint": bad_lint}
            )
            ok, errors = check_stage2_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("HARD_BLOCK" in e and "Resume.md" in e for e in errors))

    def test_lint_field_missing_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _write_stage2_ready_fixture(folder, receipt_omit_keys=["lint"])
            ok, errors = check_stage2_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("'lint' field missing or not a list" in e for e in errors))

    def test_rubric_audit_missing_fails_with_rerun_instruction_not_crash(self):
        """A receipt written before Epic 5 lands has no rubric_audit key -- must produce a
        specific 're-run scripts/verify_submission.py' error, not raise."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _write_stage2_ready_fixture(folder, receipt_omit_keys=["rubric_audit"])
            ok, errors = check_stage2_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(
                any("'rubric_audit' not found" in e and "re-run scripts/verify_submission.py" in e for e in errors)
            )

    def test_rubric_audit_not_yet_run_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _write_stage2_ready_fixture(
                folder,
                receipt_overrides={"rubric_audit": {"ran": False, "reason": "rubric_score not yet entered"}},
            )
            ok, errors = check_stage2_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("rubric_audit has not run yet" in e for e in errors))

    def test_rubric_audit_not_clean_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _write_stage2_ready_fixture(
                folder,
                receipt_overrides={
                    "rubric_audit": {"ran": True, "clean": False, "findings": ["byte-identical to acme"]}
                },
            )
            ok, errors = check_stage2_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("rubric_audit is not clean" in e for e in errors))

    def test_claim_provenance_missing_fails_with_rerun_instruction_not_crash(self):
        """Same defensive treatment as rubric_audit -- a pre-Epic-5 receipt has no
        claim_provenance key at all."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _write_stage2_ready_fixture(folder, receipt_omit_keys=["claim_provenance"])
            ok, errors = check_stage2_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(
                any("'claim_provenance' not found" in e and "re-run scripts/verify_submission.py" in e for e in errors)
            )

    def test_ac9_claim_provenance_findings_do_not_block_when_everything_else_clean(self):
        """AC9, explicitly required by Story 3.3: a fixture where claim_provenance reports real
        findings (ok: False) but every other Stage 2 requirement is clean must still return
        check_stage2_ready() == True. claim_provenance is WARN-tier -- presence is required,
        content is not gating."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _write_stage2_ready_fixture(
                folder,
                receipt_overrides={
                    "claim_provenance": {
                        "ran": True,
                        "ok": False,
                        "findings": ["Resume.md bullet 3 cites ACC-999 which does not exist in master_claims.json"],
                    }
                },
            )
            ok, errors = check_stage2_ready(str(folder))
            self.assertTrue(ok, errors)
            self.assertEqual(errors, [])

    def test_does_not_require_verification_passed(self):
        """Locked decision: check_stage2_ready() must NOT require draft_manifest.json's
        verification_passed (that stays check_finalize_ready's job). A manifest with
        verification_passed explicitly False must not block this gate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _write_stage2_ready_fixture(folder, manifest_overrides={"verification_passed": False})
            ok, errors = check_stage2_ready(str(folder))
            self.assertTrue(ok, errors)

    def test_does_not_chain_check_stage1_ready(self):
        """Locked decision: check_stage2_ready() must not require authoring_packet.json at all --
        chaining check_stage1_ready() would make packet-less legacy folders permanently
        un-verifiable. No authoring_packet.json exists in this folder at all."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _write_stage2_ready_fixture(folder)
            self.assertFalse((folder / "authoring_packet.json").exists())
            ok, errors = check_stage2_ready(str(folder))
            self.assertTrue(ok, errors)


if __name__ == "__main__":
    unittest.main()
