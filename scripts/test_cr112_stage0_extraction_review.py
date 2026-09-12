#!/usr/bin/env python3
"""CR-112 Stage 0 extraction-fallback defect -- full test plan (design doc v3).

Covers, in order: the three-way qualification-risk gate (independence
properties + category coverage, tests 8/9), the _extract_sections_nlp
dump-site/partial-mapping-loss fixes (tests 1/3/4, direct), the new
requirement_extraction_review pause wiring in build_stage0_fit_gate and its
two message-copy sites (tests 1/2/5/6/7/10), the requirement-extraction-
review artifact (bucket-correction only, exact-text binding), the exact-text
binding added to the existing cascade import template (test 14), and the
manual judgment-correction mechanism (tests 11/11a/12/13/13a).

No real DB, no LLM, no network -- call_llm / classify_requirements_batch /
industry_semantic are always mocked. Every reason code and label enumerated
here is checked against the CR-112 design doc's own measurement table.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Must not depend on real provider config for section-mode routing (only
# STAGE0_SECTION_MODE=="llm" changes which extractor build_stage0_fit_gate
# calls; every test below either patches _extract_sections_nlp directly or
# relies on the default "nlp" mode still calling it).
os.environ.setdefault("STAGE0_SECTION_MODE", "nlp")

from build_stage0_fit_gate import (  # noqa: E402
    Stage0RequirementExtractionReviewNeeded,
    _extract_sections_nlp,
    build_stage0_fit_gate,
)
from stage0_qualification_risk_gate import (  # noqa: E402
    AMBIGUOUS,
    NON_QUALIFICATION,
    QUALIFICATION_LIKELY,
    classify_qualification_risk,
    is_bypass,
)
from stage0_requirement_extraction_review import (  # noqa: E402
    REVIEW_CONSUMED_NAME,
    REVIEW_IMPORT_NAME,
    REVIEW_TEMPLATE_NAME,
    RequirementExtractionReviewValidationError,
    consume_review_import,
    render_review_template,
    try_load_review_import,
    write_review_template,
)
from stage0_evidence_cascade import (  # noqa: E402
    BatchItem,
    CascadeValidationError,
    render_cascade_import_template,
    try_load_cascade_import,
    write_cascade_import_template,
)
import stage0_checkpoint  # noqa: E402
from workflow.runner import run_stage0  # noqa: E402
from workflow.state import init_state, load_state  # noqa: E402
from workflow.receipts import load_receipt, write_state  # noqa: E402
import contracts  # noqa: E402


# ---------------------------------------------------------------------------
# Offline scoring stand-in (module-local, deliberately minimal -- these tests
# are about the pause/gate/receipt contract, not evidence-classification
# nuance). Every item is "no gap, high confidence" unless a test needs the
# unresolved queue to reach a terminal decision at all, which none do (the
# gate pauses before Step 4 evidence scoring in every "needs review" case).
# ---------------------------------------------------------------------------
def _offline_classify_batch(items, *, settings=None, **_kwargs):
    return {
        item.item_id: {
            "item": item.requirement,
            "anchor": "documented evidence",
            "gap": False,
            "gap_class": None,
            "gap_source": None,
            "domain_soft": False,
            "evidence_level": 4,
            "confidence": "high",
            "gate": "NONE",
            "needs_user_confirmation": False,
            "canonical_skill": None,
            "skill_kind": None,
        }
        for item in items
    }


_PATCHERS: list = []


def setUpModule():
    patchers = [
        patch("stage0_evidence_cascade.classify_requirements_batch", side_effect=_offline_classify_batch),
        patch(
            "industry_semantic.classify_industry_safe",
            return_value={"blocked_industry": "", "confidence": "high", "reasoning": "mocked"},
        ),
        patch("build_stage0_fit_gate._prepare_skill_confirmations", return_value=([], [])),
    ]
    for p in patchers:
        p.start()
        _PATCHERS.append(p)


def tearDownModule():
    for p in _PATCHERS:
        p.stop()
    _PATCHERS.clear()


def _folder(jd_text: str = "Product Manager\n") -> Path:
    d = Path(tempfile.mkdtemp())
    (d / "Original_JD.txt").write_text(jd_text, encoding="utf-8")
    return d


def _db() -> str:
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    return path


def _build(folder: Path, sections: dict, db_path: str) -> dict:
    with patch("build_stage0_fit_gate._extract_sections_nlp", return_value=sections):
        return build_stage0_fit_gate(
            folder,
            db_gate_result={"action": "clear"},
            prefs={"blocked_companies": []},
            confirmation_db_path=db_path,
        )


# ===========================================================================
# Part A -- three-way qualification-risk gate: independence + categories
# (tests 8 and 9, plus the three testable independence properties)
# ===========================================================================
class TestQualificationRiskGateIndependence(unittest.TestCase):
    """The three concrete, checkable independence properties (v3 "made
    testable" section) -- not just prose claims."""

    def test_property_2_matches_evidence_anywhere_not_leading_phrase_only(self):
        """_QUAL_LEADIN_RE (.match(), leading-phrase only) returns False on
        both real jd_05 trap lines and a real Camunda requirement -- this
        gate must not repeat that mistake (re.search, not re.match)."""
        from build_stage0_fit_gate import _looks_like_qualification

        lines = [
            "Must pass a Level II fingerprint background check",
            "Nights and weekends availability required",
            "Technical knowledge of configuring, deploying, managing the "
            "life cycle of platform products.",
        ]
        for line in lines:
            with self.subTest(line=line):
                self.assertFalse(
                    _looks_like_qualification(line),
                    "sanity check: the old leading-phrase heuristic really "
                    "does miss this line (that is exactly the bug)",
                )
                label, _reason = classify_qualification_risk(
                    line, header="Requirements:", role_title="Product Manager"
                )
                self.assertFalse(
                    is_bypass(label),
                    f"gate must pause on {line!r}, matching evidence anywhere in the line",
                )

    def test_property_3_default_is_ambiguous_pause_not_bypass(self):
        label, reason = classify_qualification_risk(
            "Keep the self-managed team equipped to work on the appropriate epics.",
            header="What You'll Be Doing",
            role_title="Product Manager",
        )
        self.assertEqual(label, AMBIGUOUS)
        self.assertFalse(is_bypass(label))
        self.assertEqual(reason, "no_confident_match")

    def test_property_1_gate_module_never_imports_bucketing_helpers(self):
        """The detector must share no code path with _extract_sections /
        _extract_sections_nlp's own bucket assignment. The helper names may
        legitimately appear in this module's own prose (explaining what it
        does NOT do) -- check for real usage (a call or an import), not a
        bare substring match against the docstring."""
        import ast

        import stage0_qualification_risk_gate as gate_module

        source = Path(gate_module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)

        called_names: set[str] = set()
        imported_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
            if isinstance(node, ast.Attribute):
                called_names.add(node.attr)
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    imported_names.add(alias.name)

        self.assertNotIn("_looks_like_qualification", called_names)
        self.assertNotIn("_looks_like_duty", called_names)
        self.assertNotIn("predict", called_names)
        self.assertNotIn("build_stage0_fit_gate", imported_names)
        # No import at all beyond the standard library -- confirms this
        # module cannot even reach the LogReg pipeline or the bucketing
        # helpers, not just that it happens not to call them today.
        self.assertEqual(imported_names, {"re", "annotations"})


class TestQualificationRiskGateCategories(unittest.TestCase):
    """Test 8: each NON_QUALIFICATION category gets its own fixture/assertion."""

    def _bypass(self, text, header="", role="Product Manager"):
        label, reason = classify_qualification_risk(text, header=header, role_title=role)
        return is_bypass(label), label, reason

    def test_compensation_range(self):
        bypass, _label, reason = self._bypass(
            "The base salary range for this role is $120,000-$150,000 depending on experience.",
            header="Compensation",
        )
        self.assertTrue(bypass)
        self.assertEqual(reason, "compensation_range")

    def test_benefits_perks(self):
        bypass, _label, reason = self._bypass(
            "We invest in your wellbeing, growth, and financial security.",
            header="Benefits & Perks",
        )
        self.assertTrue(bypass)
        self.assertEqual(reason, "benefits_perks")

    def test_eeo_accommodation(self):
        bypass, _label, reason = self._bypass(
            "We are an equal opportunity employer. All qualified applicants will "
            "receive consideration for employment without regard to race, color, "
            "religion, sex, or national origin."
        )
        self.assertTrue(bypass)
        self.assertEqual(reason, "eeo_or_background_disclosure")

    def test_recruiting_process_instructions(self):
        bypass, _label, reason = self._bypass(
            "If you're based elsewhere, you'll be hired via Remote.com, our "
            "Employer of Record partner.",
            header="Compensation",
        )
        self.assertTrue(bypass)
        self.assertEqual(reason, "recruiting_or_hiring_logistics")

    def test_company_marketing_description(self):
        bypass, _label, reason = self._bypass(
            "Northwind Labs is a fictional B2B workflow company. We are hiring a "
            "Product Manager to own an existing customer-facing platform used by "
            "operations and account teams."
        )
        self.assertTrue(bypass)
        self.assertEqual(reason, "company_marketing_description")

    def test_location_travel_logistics_as_information(self):
        bypass, _label, reason = self._bypass(
            "This role is based in our Austin office, with occasional in-person "
            "team offsites."
        )
        self.assertTrue(bypass)
        self.assertEqual(reason, "location_logistics_information")

    def test_internal_posting_instructions(self):
        """Camunda #10, named exactly, per the test plan: 'What You Bring: "
        Talent Ops to delete as necessary...' -- affirmative category match,
        not header-protected."""
        bypass, _label, reason = self._bypass(
            "Talent Ops to delete as necessary -> remove this line before posting",
            header="What You Bring",
        )
        self.assertTrue(bypass)
        self.assertEqual(reason, "internal_posting_instruction")

    def test_posting_title_line(self):
        bypass, _label, reason = self._bypass(
            "Product Manager, Platform", header="", role="Product Manager, Platform"
        )
        self.assertTrue(bypass)
        self.assertEqual(reason, "posting_title_line")

    def test_explicit_requirements_headed_capability_line_pauses(self):
        bypass, _label, _reason = self._bypass(
            "Roadmap ownership with engineering, CX, and sales partners",
            header="Requirements:",
        )
        self.assertFalse(bypass)

    def test_responsibilities_headed_real_capability_line_pauses(self):
        """Responsibility-header text is NOT auto-exempted (v3, explicit
        Jason examples)."""
        for text in (
            "Communicate complex technical concepts",
            "Partner with engineering on distributed systems",
        ):
            with self.subTest(text=text):
                bypass, _label, _reason = self._bypass(text, header="Responsibilities:")
                self.assertFalse(bypass)

    def test_mixed_queue_pauses_all_non_qualification_queue_bypasses(self):
        """One non-qual + one anything-else pauses; an all-non-qual queue
        proceeds -- checked at the gate-classification level here; the
        integration-level version is TestRequirementExtractionReviewPause
        below."""
        queue = [
            ("We invest in your wellbeing, growth, and financial security.", "Benefits & Perks"),
            ("Strong understanding of distributed systems concepts.", "What You Bring"),
        ]
        labels = [classify_qualification_risk(t, header=h, role_title="Product Manager")[0] for t, h in queue]
        self.assertTrue(any(not is_bypass(lbl) for lbl in labels))

        all_non_qual_queue = [
            ("We invest in your wellbeing, growth, and financial security.", "Benefits & Perks"),
            ("Financial Security: Retirement and pension plans available in most countries.", "Benefits & Perks"),
        ]
        labels2 = [classify_qualification_risk(t, header=h, role_title="Product Manager")[0] for t, h in all_non_qual_queue]
        self.assertTrue(all(is_bypass(lbl) for lbl in labels2))


class TestJd05TrapRegression(unittest.TestCase):
    """Test 9: the two jd_05_wideworld trap lines must classify
    QUALIFICATION_LIKELY, never NON_QUALIFICATION, despite sitting near
    privacy/schedule vocabulary."""

    def test_background_check_eligibility_is_not_boilerplate(self):
        label, reason = classify_qualification_risk(
            "Must pass a Level II fingerprint background check",
            header="Requirements:",
            role_title="Product Manager",
        )
        self.assertEqual(label, QUALIFICATION_LIKELY)
        self.assertFalse(is_bypass(label))
        self.assertEqual(reason, "explicit_eligibility_demand")

    def test_schedule_eligibility_is_not_logistics_information(self):
        label, reason = classify_qualification_risk(
            "Nights and weekends availability required",
            header="Requirements:",
            role_title="Product Manager",
        )
        self.assertEqual(label, QUALIFICATION_LIKELY)
        self.assertFalse(is_bypass(label))
        self.assertEqual(reason, "explicit_eligibility_demand")


# ===========================================================================
# Part B -- _extract_sections_nlp's own three dump-site fixes (tests 1/3/4,
# direct, real trained classifier, mocked utils.call_llm)
# ===========================================================================
class TestExtractSectionsNlpDumpSites(unittest.TestCase):
    """Real data/stage0_classifier.pkl, mocked utils.call_llm -- no network."""

    _JD = textwrap.dedent(
        """
        Requirements
        Xk8j Qzpr Vwmn synergistic paradigm bullet with no clear signal
        Zrqm Ftlk Bxpo transformative disruption bullet with no clear signal
        """
    ).strip() + "\n"

    def setUp(self):
        os.environ["STAGE0_SECTION_MODE"] = "nlp"

    def test_no_provider_is_recorded_not_defaulted_to_responsibilities(self):
        with patch("utils.call_llm", return_value=None):
            result = _extract_sections_nlp(self._JD)
        self.assertIsNotNone(result)
        unresolved = result.get("unresolved_for_review") or []
        self.assertGreaterEqual(len(unresolved), 1)
        for entry in unresolved:
            self.assertEqual(entry["reason"], "no_provider")
            self.assertFalse(entry["model_call_occurred"])
            self.assertNotIn(entry["text"], result.get("responsibilities", []))

    def test_parse_failure_is_recorded_model_call_occurred_true(self):
        with patch("utils.call_llm", return_value="not json at all { garbage"):
            result = _extract_sections_nlp(self._JD)
        unresolved = result.get("unresolved_for_review") or []
        self.assertGreaterEqual(len(unresolved), 1)
        for entry in unresolved:
            self.assertEqual(entry["reason"], "parse_failure")
            self.assertTrue(entry["model_call_occurred"])
            self.assertNotIn(entry["text"], result.get("responsibilities", []))

    def test_partial_mapping_does_not_silently_drop_unmapped_items(self):
        """Two low-confidence items queued; the provider only answers index 0.
        Index 1 must not be silently dropped (old behavior: `continue`)."""
        with patch("utils.call_llm", return_value='{"0": "required"}'):
            result = _extract_sections_nlp(self._JD)
        unresolved = result.get("unresolved_for_review") or []
        partial_reasons = [e for e in unresolved if e["reason"] == "partial_mapping_unresolved"]
        self.assertEqual(len(partial_reasons), 1)
        self.assertTrue(partial_reasons[0]["model_call_occurred"])
        # And it never silently landed in any bucket either.
        all_bucketed_text = (
            result.get("required", []) + result.get("preferred", [])
            + result.get("responsibilities", []) + result.get("culture", [])
        )
        self.assertNotIn(partial_reasons[0]["text"], all_bucketed_text)

    def test_fully_confident_extraction_has_no_unresolved_key(self):
        """Test 6 at the extractor level: a JD with only high-confidence
        bullets produces the same plain-dict shape as before (no
        unresolved_for_review key at all)."""
        jd = "Requirements\n5+ years of product management experience in B2B SaaS\n"
        with patch("utils.call_llm") as mock_call:
            result = _extract_sections_nlp(jd)
        mock_call.assert_not_called()
        self.assertNotIn("unresolved_for_review", result)


# ===========================================================================
# Part C -- build_stage0_fit_gate wiring: the new pause, PIN 1/3/4
# (tests 1, 2, 3, 4, 6, 7, 10)
# ===========================================================================
class TestRequirementExtractionReviewPause(unittest.TestCase):
    def test_1_no_provider_pauses_not_skipped_no_run_row_no_mark_status(self):
        folder = _folder()
        db_path = _db()
        sections = {
            "required": [],
            "preferred": [],
            "responsibilities": [],
            "culture": [],
            "unresolved_for_review": [
                {
                    "text": "Strong understanding of distributed systems concepts.",
                    "header": "What You Bring",
                    "reason": "no_provider",
                    "model_call_occurred": False,
                }
            ],
        }
        with patch("build_stage0_fit_gate.start_run") as mock_start, patch(
            "build_stage0_fit_gate.mark_run_status"
        ) as mock_mark:
            with patch("build_stage0_fit_gate._extract_sections_nlp", return_value=sections):
                with self.assertRaises(Stage0RequirementExtractionReviewNeeded) as ctx:
                    build_stage0_fit_gate(
                        folder,
                        db_gate_result={"action": "clear"},
                        prefs={"blocked_companies": []},
                        confirmation_db_path=db_path,
                    )
            mock_start.assert_not_called()
            mock_mark.assert_not_called()
        self.assertEqual(ctx.exception.opportunity_key, folder.name)
        self.assertTrue(any(item["label"] != NON_QUALIFICATION for item in ctx.exception.queue))

    def test_2_confident_required_item_plus_risky_queue_still_pauses(self):
        """The false-PASS direction: a Skip-only fix would let this through."""
        folder = _folder()
        db_path = _db()
        sections = {
            "required": ["5+ years of experience with B2B SaaS platforms"],
            "preferred": [],
            "responsibilities": [],
            "culture": [],
            "unresolved_for_review": [
                {
                    "text": "Strong understanding of distributed systems concepts.",
                    "header": "What You Bring",
                    "reason": "no_provider",
                    "model_call_occurred": False,
                }
            ],
        }
        with patch("build_stage0_fit_gate._extract_sections_nlp", return_value=sections):
            with self.assertRaises(Stage0RequirementExtractionReviewNeeded):
                build_stage0_fit_gate(
                    folder,
                    db_gate_result={"action": "clear"},
                    prefs={"blocked_companies": []},
                    confirmation_db_path=db_path,
                )

    def test_3_parse_failure_pauses_same_way(self):
        folder = _folder()
        db_path = _db()
        sections = {
            "required": [],
            "preferred": [],
            "responsibilities": [],
            "culture": [],
            "unresolved_for_review": [
                {
                    "text": "Familiarity with technologies such as Kubernetes, Docker.",
                    "header": "What You Bring",
                    "reason": "parse_failure",
                    "model_call_occurred": True,
                }
            ],
        }
        with patch("build_stage0_fit_gate._extract_sections_nlp", return_value=sections):
            with self.assertRaises(Stage0RequirementExtractionReviewNeeded) as ctx:
                build_stage0_fit_gate(
                    folder,
                    db_gate_result={"action": "clear"},
                    prefs={"blocked_companies": []},
                    confirmation_db_path=db_path,
                )
        self.assertTrue(ctx.exception.queue[0]["model_call_occurred"])

    def test_4_partial_mapping_item_enters_gate_not_lost(self):
        folder = _folder()
        db_path = _db()
        sections = {
            "required": [],
            "preferred": [],
            "responsibilities": [],
            "culture": [],
            "unresolved_for_review": [
                {
                    "text": "Technical knowledge of configuring, deploying, managing the life cycle of platform products.",
                    "header": "What You Bring",
                    "reason": "partial_mapping_unresolved",
                    "model_call_occurred": True,
                }
            ],
        }
        with patch("build_stage0_fit_gate._extract_sections_nlp", return_value=sections):
            with self.assertRaises(Stage0RequirementExtractionReviewNeeded) as ctx:
                build_stage0_fit_gate(
                    folder,
                    db_gate_result={"action": "clear"},
                    prefs={"blocked_companies": []},
                    confirmation_db_path=db_path,
                )
        queue_texts = [item["text"] for item in ctx.exception.queue]
        self.assertIn(
            "Technical knowledge of configuring, deploying, managing the life "
            "cycle of platform products.",
            queue_texts,
        )

    def test_6_fully_confident_extraction_unchanged_no_new_pause(self):
        folder = _folder()
        db_path = _db()
        sections = {
            "required": ["5+ years of experience with B2B SaaS platforms"],
            "preferred": [],
            "responsibilities": [],
            "culture": [],
        }
        result = _build(folder, sections, db_path)
        self.assertIn(result["tier"], ("Tier 1", "Tier 2", "Skip"))
        self.assertEqual(result["requirement_extraction_review"], {"bypassed_non_qualification": []})

    def test_7_thin_jd_reaches_tier2_or_skip_normally(self):
        folder = _folder()
        db_path = _db()
        sections = {
            "required": ["Own the roadmap"],
            "preferred": [],
            "responsibilities": [],
            "culture": [],
        }
        result = _build(folder, sections, db_path)
        self.assertIn(result["tier"], ("Tier 2", "Skip"))

    def test_10_non_qualification_bypasses_visible_in_receipt_with_reason(self):
        folder = _folder()
        db_path = _db()
        sections = {
            "required": ["5+ years of experience with B2B SaaS platforms"],
            "preferred": [],
            "responsibilities": [],
            "culture": [],
            "unresolved_for_review": [
                {
                    "text": "We invest in your wellbeing, growth, and financial security.",
                    "header": "Benefits & Perks",
                    "reason": "no_provider",
                    "model_call_occurred": False,
                },
                {
                    "text": "Talent Ops to delete as necessary -> remove this line before posting",
                    "header": "What You Bring",
                    "reason": "no_provider",
                    "model_call_occurred": False,
                },
            ],
        }
        result = _build(folder, sections, db_path)
        bypassed = result["requirement_extraction_review"]["bypassed_non_qualification"]
        self.assertEqual(len(bypassed), 2)
        reason_codes = {item["reason_code"] for item in bypassed}
        self.assertEqual(reason_codes, {"benefits_perks", "internal_posting_instruction"})
        for item in bypassed:
            self.assertEqual(item["label"], NON_QUALIFICATION)


# ===========================================================================
# Part D -- PIN 2: both copy sites branch on pause_kind (test 5)
# ===========================================================================
class TestPauseMessageCopySites(unittest.TestCase):
    def _pause_receipt_folder(self) -> Path:
        """Real run_stage0() call, isolated the same way test_cr112_story71.py's
        own _pause_once/_stage0_ctx helpers isolate it: real DB gate/prefs/skip
        ledger swapped for safe stand-ins, APPLYR_STAGE0_REVIEW_DB pointed at a
        fresh temp sqlite file, only _extract_sections_nlp's return value
        controlled."""
        folder = _folder()
        state = init_state(str(folder))
        write_state(str(folder), state)
        db_path = _db()
        sections = {
            "required": [],
            "preferred": [],
            "responsibilities": [],
            "culture": [],
            "unresolved_for_review": [
                {
                    "text": "Strong understanding of distributed systems concepts.",
                    "header": "What You Bring",
                    "reason": "no_provider",
                    "model_call_occurred": False,
                }
            ],
        }
        with patch.dict(os.environ, {"APPLYR_STAGE0_REVIEW_DB": db_path}), patch(
            "build_stage0_fit_gate._extract_sections_nlp", return_value=sections
        ), patch("utils.load_candidate_preferences", return_value={"blocked_companies": []}), patch(
            "stage0_db_gate.evaluate_db_gate", return_value={"action": "clear"}
        ), patch("stage0_skip_ledger.lookup_skip", return_value=None):
            out = run_stage0(str(folder), state)
        self.assertEqual(out["status"], "WAITING_FOR_INPUT")
        return folder

    def test_receipt_has_requirement_extraction_review_pause_kind(self):
        folder = self._pause_receipt_folder()
        receipt = load_receipt(str(folder), "stage0")
        self.assertEqual(receipt["status"], "WAITING_FOR_INPUT")
        self.assertEqual(receipt["result"]["pause_kind"], "requirement_extraction_review")

    def test_contracts_message_branches_for_this_pause_kind(self):
        folder = self._pause_receipt_folder()
        msg = contracts.waiting_for_input_message(str(folder))
        self.assertIn("requirement extraction", msg.lower())
        self.assertIn("stage0_requirement_extraction_review.json", msg)
        self.assertNotIn("Review Center confirmation", msg)

    def test_run_submission_console_print_branches_for_this_pause_kind(self):
        import run_submission

        folder = self._pause_receipt_folder()
        fake_state = load_state(str(folder))
        with patch.object(run_submission, "run_until_truth_settled", return_value=fake_state):
            with patch("sys.argv", ["run_submission.py", str(folder)]):
                import io
                import contextlib

                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    with self.assertRaises(SystemExit) as ctx:
                        run_submission.main()
        self.assertEqual(ctx.exception.code, 0)
        output = buf.getvalue()
        self.assertIn("requirement extraction review", output.lower())
        self.assertNotIn("resolve the pending Review Center confirmation", output)


# ===========================================================================
# Part E -- requirement-extraction-review artifact (generation/validation)
# ===========================================================================
class TestRequirementExtractionReviewArtifact(unittest.TestCase):
    def _queue(self):
        return [
            {
                "text": "Strong understanding of distributed systems concepts.",
                "header": "What You Bring",
                "label": QUALIFICATION_LIKELY,
                "reason_code": "explicit_capability_vocabulary",
            }
        ]

    def test_template_has_no_default_bucket_no_accept_all(self):
        queue = self._queue()
        template = render_review_template(submission_slug="acme", jd_sha256="abc", queue=queue)
        self.assertEqual(template["items"][0]["bucket"], None)
        self.assertNotIn("accept_all", template)

    def test_valid_import_resolves_explicit_bucket_per_item(self):
        folder = Path(tempfile.mkdtemp())
        queue = self._queue()
        template = render_review_template(submission_slug=folder.name, jd_sha256="abc", queue=queue)
        live = dict(template)
        live["items"] = [dict(template["items"][0], bucket="required")]
        (folder / REVIEW_IMPORT_NAME).write_text(json.dumps(live), encoding="utf-8")
        resolved = try_load_review_import(folder, queue, submission_slug=folder.name, jd_sha256="abc")
        self.assertEqual(resolved, {0: "required"})

    def test_import_missing_bucket_answer_is_rejected(self):
        folder = Path(tempfile.mkdtemp())
        queue = self._queue()
        template = render_review_template(submission_slug=folder.name, jd_sha256="abc", queue=queue)
        (folder / REVIEW_IMPORT_NAME).write_text(json.dumps(template), encoding="utf-8")
        with self.assertRaises(RequirementExtractionReviewValidationError):
            try_load_review_import(folder, queue, submission_slug=folder.name, jd_sha256="abc")

    def test_import_with_rewritten_text_is_rejected(self):
        """Exact-text binding: an import answering about text that does not
        match the real queued item must be rejected, not silently accepted."""
        folder = Path(tempfile.mkdtemp())
        queue = self._queue()
        template = render_review_template(submission_slug=folder.name, jd_sha256="abc", queue=queue)
        live = dict(template)
        item = dict(template["items"][0], bucket="required")
        item["text"] = "A rewritten version of this requirement"
        live["items"] = [item]
        (folder / REVIEW_IMPORT_NAME).write_text(json.dumps(live), encoding="utf-8")
        with self.assertRaises(RequirementExtractionReviewValidationError):
            try_load_review_import(folder, queue, submission_slug=folder.name, jd_sha256="abc")

    def test_import_cannot_set_workflow_or_scoring_fields(self):
        folder = Path(tempfile.mkdtemp())
        queue = self._queue()
        template = render_review_template(submission_slug=folder.name, jd_sha256="abc", queue=queue)
        live = dict(template)
        live["items"] = [dict(template["items"][0], bucket="required")]
        live["fit_score"] = 100
        (folder / REVIEW_IMPORT_NAME).write_text(json.dumps(live), encoding="utf-8")
        with self.assertRaises(RequirementExtractionReviewValidationError):
            try_load_review_import(folder, queue, submission_slug=folder.name, jd_sha256="abc")

    def test_integration_manual_import_resolves_pause_without_repausing(self):
        """End to end: build_stage0_fit_gate writes the template on first
        pass, a human answers it, --resume (a second build_stage0_fit_gate
        call) applies the corrected bucket and does not re-pause."""
        folder = _folder()
        db_path = _db()
        sections = {
            "required": [],
            "preferred": [],
            "responsibilities": [],
            "culture": [],
            "unresolved_for_review": [
                {
                    "text": "Strong understanding of distributed systems concepts.",
                    "header": "What You Bring",
                    "reason": "no_provider",
                    "model_call_occurred": False,
                }
            ],
        }
        with patch("build_stage0_fit_gate._extract_sections_nlp", return_value=sections):
            with self.assertRaises(Stage0RequirementExtractionReviewNeeded):
                build_stage0_fit_gate(
                    folder,
                    db_gate_result={"action": "clear"},
                    prefs={"blocked_companies": []},
                    confirmation_db_path=db_path,
                )
        self.assertTrue((folder / REVIEW_TEMPLATE_NAME).is_file())
        template = json.loads((folder / REVIEW_TEMPLATE_NAME).read_text(encoding="utf-8"))
        live = dict(template)
        live["items"] = [dict(template["items"][0], bucket="required")]
        (folder / REVIEW_IMPORT_NAME).write_text(json.dumps(live), encoding="utf-8")

        with patch("build_stage0_fit_gate._extract_sections_nlp", return_value=sections):
            result = build_stage0_fit_gate(
                folder,
                db_gate_result={"action": "clear"},
                prefs={"blocked_companies": []},
                confirmation_db_path=db_path,
            )
        required_items = [row.get("item") for row in result.get("required", [])]
        self.assertIn(
            "Strong understanding of distributed systems concepts.",
            required_items,
        )
        self.assertTrue((folder / REVIEW_CONSUMED_NAME).is_file())
        self.assertFalse((folder / REVIEW_IMPORT_NAME).is_file())


# ===========================================================================
# Part F -- test 14: exact-text binding on the existing cascade import
# template
# ===========================================================================
class TestCascadeImportExactTextBinding(unittest.TestCase):
    def _item(self) -> BatchItem:
        return BatchItem(
            item_id="required:0:aaaaaaaaaaaaaaaa",
            bucket="required",
            requirement="Own the platform roadmap",
        )

    def test_template_carries_requirement_and_bucket(self):
        item = self._item()
        template = render_cascade_import_template(
            submission_slug="acme", jd_sha256="abc", items=[item]
        )
        row = template["results"][0]
        self.assertEqual(row["requirement"], item.requirement)
        self.assertEqual(row["bucket"], item.bucket)

    def test_echoed_requirement_mismatch_is_rejected(self):
        item = self._item()
        folder = Path(tempfile.mkdtemp())
        write_cascade_import_template(folder, submission_slug=folder.name, jd_sha256="abc", items=[item])
        template = json.loads((folder / "stage0_cascade_import.template.json").read_text(encoding="utf-8"))
        live = dict(template)
        live["created_at"] = "2026-09-12T00:00:00Z"
        row = dict(live["results"][0])
        row["requirement"] = "A different requirement entirely"
        row["reasoning"] = "answered"
        live["results"] = [row]
        (folder / "stage0_cascade_import.json").write_text(json.dumps(live), encoding="utf-8")
        with self.assertRaises(CascadeValidationError):
            try_load_cascade_import(folder, [item], submission_slug=folder.name, jd_sha256="abc")

    def test_echoed_bucket_mismatch_is_rejected(self):
        item = self._item()
        folder = Path(tempfile.mkdtemp())
        write_cascade_import_template(folder, submission_slug=folder.name, jd_sha256="abc", items=[item])
        template = json.loads((folder / "stage0_cascade_import.template.json").read_text(encoding="utf-8"))
        live = dict(template)
        live["created_at"] = "2026-09-12T00:00:00Z"
        row = dict(live["results"][0])
        row["bucket"] = "preferred"
        row["reasoning"] = "answered"
        live["results"] = [row]
        (folder / "stage0_cascade_import.json").write_text(json.dumps(live), encoding="utf-8")
        with self.assertRaises(CascadeValidationError):
            try_load_cascade_import(folder, [item], submission_slug=folder.name, jd_sha256="abc")

    def test_correctly_echoed_import_is_accepted(self):
        item = self._item()
        folder = Path(tempfile.mkdtemp())
        write_cascade_import_template(folder, submission_slug=folder.name, jd_sha256="abc", items=[item])
        template = json.loads((folder / "stage0_cascade_import.template.json").read_text(encoding="utf-8"))
        live = dict(template)
        live["created_at"] = "2026-09-12T00:00:00Z"
        row = dict(live["results"][0])
        row["reasoning"] = "Owned the roadmap in prior work."
        live["results"] = [row]
        (folder / "stage0_cascade_import.json").write_text(json.dumps(live), encoding="utf-8")
        loaded = try_load_cascade_import(folder, [item], submission_slug=folder.name, jd_sha256="abc")
        self.assertIsNotNone(loaded)
        self.assertIn(item.item_id, loaded["results"])


# ===========================================================================
# Part G -- manual judgment-correction mechanism (tests 11/11a/12/13/13a)
# ===========================================================================
class TestManualJudgmentCorrection(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.run_key = "run:testkey"
        self.opportunity_key = "acme"
        self.request_hash = "reqhash"
        self.evidence_index_hash = "evhash"

    def _seed_judgment(self, item_key: str, item_text: str, bucket: str, judgment: dict) -> None:
        stage0_checkpoint.complete_judgment(
            self.db_path,
            judgment_key=f"{self.run_key}:{item_key}",
            run_key=self.run_key,
            opportunity_key=self.opportunity_key,
            item_key=item_key,
            item_text=item_text,
            bucket=bucket,
            request_hash=self.request_hash,
            content_hash=f"content:{item_key}",
            evidence_index_hash=self.evidence_index_hash,
            judgment=judgment,
            provider="local",
            model="evidence_scale",
        )

    def test_11_replay_real_incident_no_sql_needed(self):
        """Replays the actual incident: a wrong manual classification for
        required:0:bjiplgnonojgoadn on an unchanged requirement set."""
        item_key = "required:0:bjiplgnonojgoadn"
        wrong = {"gate": "HARD", "evidence_level": 0, "gap_class": "HARD", "reasoning": "wrong"}
        self._seed_judgment(item_key, "Own the platform roadmap", "required", wrong)

        corrected = {"gate": "NONE", "evidence_level": 4, "gap_class": None, "reasoning": "corrected"}
        stage0_checkpoint.correct_judgment(
            self.db_path,
            run_key=self.run_key,
            item_key=item_key,
            request_hash=self.request_hash,
            content_hash=f"content:{item_key}",
            evidence_index_hash=self.evidence_index_hash,
            opportunity_key=self.opportunity_key,
            corrected_judgment=corrected,
            correction_source="human_review",
            reason="misclassified HARD; real evidence exists",
        )

        result = stage0_checkpoint.get_completed_judgment(
            self.db_path,
            run_key=self.run_key,
            item_key=item_key,
            request_hash=self.request_hash,
            content_hash=f"content:{item_key}",
            evidence_index_hash=self.evidence_index_hash,
        )
        self.assertEqual(result["judgment"], corrected)

        # The wrong judgment is preserved as append-only history.
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM stage0_judgment_corrections WHERE item_key = ?", (item_key,)
            ).fetchall()
        finally:
            conn.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(json.loads(rows[0]["previous_judgment_json"]), wrong)
        self.assertEqual(json.loads(rows[0]["corrected_judgment_json"]), corrected)

    def test_11a_other_cached_judgments_under_same_run_key_untouched(self):
        item_key_a = "required:0:bjiplgnonojgoadn"
        item_key_b = "required:1:otheritemkeyhash"
        judgment_a = {"gate": "HARD", "evidence_level": 0, "gap_class": "HARD"}
        judgment_b = {"gate": "NONE", "evidence_level": 4, "gap_class": None}
        self._seed_judgment(item_key_a, "Own the platform roadmap", "required", judgment_a)
        self._seed_judgment(item_key_b, "A second, unrelated requirement", "required", judgment_b)

        stage0_checkpoint.correct_judgment(
            self.db_path,
            run_key=self.run_key,
            item_key=item_key_a,
            request_hash=self.request_hash,
            content_hash=f"content:{item_key_a}",
            evidence_index_hash=self.evidence_index_hash,
            opportunity_key=self.opportunity_key,
            corrected_judgment={"gate": "NONE", "evidence_level": 4, "gap_class": None},
            correction_source="human_review",
        )

        untouched = stage0_checkpoint.get_completed_judgment(
            self.db_path,
            run_key=self.run_key,
            item_key=item_key_b,
            request_hash=self.request_hash,
            content_hash=f"content:{item_key_b}",
            evidence_index_hash=self.evidence_index_hash,
        )
        self.assertEqual(untouched["judgment"], judgment_b)

    def test_12_stale_request_hash_is_rejected(self):
        item_key = "required:0:bjiplgnonojgoadn"
        self._seed_judgment(item_key, "Own the platform roadmap", "required", {"gate": "HARD"})
        with self.assertRaises(ValueError):
            stage0_checkpoint.correct_judgment(
                self.db_path,
                run_key=self.run_key,
                item_key=item_key,
                request_hash="a-different-request-hash",
                content_hash=f"content:{item_key}",
                evidence_index_hash=self.evidence_index_hash,
                opportunity_key=self.opportunity_key,
                corrected_judgment={"gate": "NONE"},
                correction_source="human_review",
            )

    def test_12_stale_content_hash_is_rejected(self):
        item_key = "required:0:bjiplgnonojgoadn"
        self._seed_judgment(item_key, "Own the platform roadmap", "required", {"gate": "HARD"})
        with self.assertRaises(ValueError):
            stage0_checkpoint.correct_judgment(
                self.db_path,
                run_key=self.run_key,
                item_key=item_key,
                request_hash=self.request_hash,
                content_hash="a-different-content-hash",
                evidence_index_hash=self.evidence_index_hash,
                opportunity_key=self.opportunity_key,
                corrected_judgment={"gate": "NONE"},
                correction_source="human_review",
            )

    def test_12_stale_evidence_index_hash_is_rejected(self):
        item_key = "required:0:bjiplgnonojgoadn"
        self._seed_judgment(item_key, "Own the platform roadmap", "required", {"gate": "HARD"})
        with self.assertRaises(ValueError):
            stage0_checkpoint.correct_judgment(
                self.db_path,
                run_key=self.run_key,
                item_key=item_key,
                request_hash=self.request_hash,
                content_hash=f"content:{item_key}",
                evidence_index_hash="a-different-evidence-hash",
                opportunity_key=self.opportunity_key,
                corrected_judgment={"gate": "NONE"},
                correction_source="human_review",
            )

    def test_12_different_opportunity_key_is_rejected(self):
        item_key = "required:0:bjiplgnonojgoadn"
        self._seed_judgment(item_key, "Own the platform roadmap", "required", {"gate": "HARD"})
        with self.assertRaises(ValueError):
            stage0_checkpoint.correct_judgment(
                self.db_path,
                run_key=self.run_key,
                item_key=item_key,
                request_hash=self.request_hash,
                content_hash=f"content:{item_key}",
                evidence_index_hash=self.evidence_index_hash,
                opportunity_key="a-different-opportunity",
                corrected_judgment={"gate": "NONE"},
                correction_source="human_review",
            )

    def test_12_unknown_item_key_is_rejected(self):
        with self.assertRaises(KeyError):
            stage0_checkpoint.correct_judgment(
                self.db_path,
                run_key=self.run_key,
                item_key="required:99:unknown",
                request_hash=self.request_hash,
                content_hash="content:unknown",
                evidence_index_hash=self.evidence_index_hash,
                opportunity_key=self.opportunity_key,
                corrected_judgment={"gate": "NONE"},
                correction_source="human_review",
            )

    def test_13_correction_cannot_set_workflow_or_scoring_fields(self):
        item_key = "required:0:bjiplgnonojgoadn"
        self._seed_judgment(item_key, "Own the platform roadmap", "required", {"gate": "HARD"})
        with self.assertRaises(ValueError):
            stage0_checkpoint.correct_judgment(
                self.db_path,
                run_key=self.run_key,
                item_key=item_key,
                request_hash=self.request_hash,
                content_hash=f"content:{item_key}",
                evidence_index_hash=self.evidence_index_hash,
                opportunity_key=self.opportunity_key,
                corrected_judgment={"gate": "NONE", "fit_score": 100, "tier": "Tier 1"},
                correction_source="human_review",
            )

    def test_13a_correction_request_artifact_carries_binding_fields(self):
        item_key = "required:0:bjiplgnonojgoadn"
        wrong = {"gate": "HARD", "evidence_level": 0}
        self._seed_judgment(item_key, "Own the platform roadmap", "required", wrong)
        artifact = stage0_checkpoint.build_judgment_correction_request(
            self.db_path, run_key=self.run_key, item_key=item_key
        )
        self.assertEqual(artifact["item_key"], item_key)
        self.assertEqual(artifact["bucket"], "required")
        self.assertEqual(artifact["item_text"], "Own the platform roadmap")
        self.assertEqual(artifact["current_judgment"], wrong)
        # Also carries what correct_judgment() needs -- answerable without
        # inspecting stage0_judgments directly.
        self.assertEqual(artifact["request_hash"], self.request_hash)
        self.assertEqual(artifact["evidence_index_hash"], self.evidence_index_hash)


# ===========================================================================
# Part H -- test 15: repeated --resume before either pause is answered makes
# zero provider calls and does not fork receipts.
# ===========================================================================
class TestRepeatedResumeMakesNoProviderCalls(unittest.TestCase):
    def test_repeated_build_before_answer_makes_zero_llm_calls(self):
        folder = _folder()
        db_path = _db()
        sections = {
            "required": [],
            "preferred": [],
            "responsibilities": [],
            "culture": [],
            "unresolved_for_review": [
                {
                    "text": "Strong understanding of distributed systems concepts.",
                    "header": "What You Bring",
                    "reason": "no_provider",
                    "model_call_occurred": False,
                }
            ],
        }
        with patch("utils.call_llm") as mock_call:
            with patch("build_stage0_fit_gate._extract_sections_nlp", return_value=sections):
                for _ in range(3):
                    with self.assertRaises(Stage0RequirementExtractionReviewNeeded):
                        build_stage0_fit_gate(
                            folder,
                            db_gate_result={"action": "clear"},
                            prefs={"blocked_companies": []},
                            confirmation_db_path=db_path,
                        )
            mock_call.assert_not_called()
        # No live import, no consumed import -- the template stays, no fork.
        self.assertFalse((folder / REVIEW_IMPORT_NAME).is_file())
        self.assertFalse((folder / REVIEW_CONSUMED_NAME).is_file())
        self.assertTrue((folder / REVIEW_TEMPLATE_NAME).is_file())


if __name__ == "__main__":
    unittest.main()
