"""Tests for local_rewrite.py (CR-062, Deterministic-Minimal-LLM harness).

Covers the grounding gates in isolation (no network calls) plus the escalation-ladder
control flow with call_llm_stage monkeypatched, so these run fast and deterministically
in CI without needing Ollama running.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import local_rewrite
from local_rewrite import (
    is_local_rewrite_mode,
    local_rewrite_sentence,
    validate_bullet_rewrite,
    validate_prose_rewrite,
    _entity_subset_ok,
    _extract_rewrite_text,
    _numeric_tokens_equal,
)

SRC = "Resolved 90% of a ~300-item security vulnerability backlog without stalling core roadmap delivery."


class TestDraftModeFlag(unittest.TestCase):
    def test_default_mode_is_not_local_rewrite(self):
        os.environ.pop("DRAFT_MODE", None)
        self.assertFalse(is_local_rewrite_mode())

    def test_compose_mode_is_not_local_rewrite(self):
        os.environ["DRAFT_MODE"] = "compose"
        self.assertFalse(is_local_rewrite_mode())

    def test_local_rewrite_mode_detected(self):
        os.environ["DRAFT_MODE"] = "local_rewrite"
        self.assertTrue(is_local_rewrite_mode())
        os.environ.pop("DRAFT_MODE", None)


class TestNumericAndEntityChecks(unittest.TestCase):
    def test_numeric_equality_passes_on_identical_numbers(self):
        self.assertTrue(_numeric_tokens_equal(SRC, SRC))

    def test_numeric_equality_fails_on_dropped_number(self):
        dropped = "Resolved most of a large security vulnerability backlog without stalling core roadmap delivery."
        self.assertFalse(_numeric_tokens_equal(SRC, dropped))

    def test_numeric_equality_fails_on_changed_number(self):
        changed = SRC.replace("300", "500")
        self.assertFalse(_numeric_tokens_equal(SRC, changed))

    def test_entity_subset_allows_no_new_proper_nouns(self):
        rephrase = "Resolved 90% of a roughly 300-item security vulnerability backlog without stalling core roadmap delivery."
        self.assertTrue(_entity_subset_ok(SRC, rephrase))

    def test_entity_subset_rejects_invented_tool_name(self):
        invented = "Resolved 90% of a ~300-item security vulnerability backlog using Jira."
        self.assertFalse(_entity_subset_ok(SRC, invented))


class TestValidateBulletRewrite(unittest.TestCase):
    def test_accepts_safe_synonym_rewrite(self):
        good = "Resolved 90% of a roughly 300-item security vulnerability backlog without stalling core roadmap delivery."
        ok, err = validate_bullet_rewrite(SRC, good)
        self.assertTrue(ok, err)

    def test_rejects_dropped_number(self):
        bad = "Resolved most of a large security vulnerability backlog without stalling core roadmap delivery."
        ok, err = validate_bullet_rewrite(SRC, bad)
        self.assertFalse(ok)
        self.assertIn("Numeric token set changed", err)

    def test_rejects_fabricated_number(self):
        bad = SRC.replace("300", "999")
        ok, err = validate_bullet_rewrite(SRC, bad)
        self.assertFalse(ok)
        self.assertIn("Fabricated numeric claims", err)

    def test_rejects_invented_tool(self):
        bad = "Resolved 90% of a ~300-item security vulnerability backlog using Jira without stalling core roadmap delivery."
        ok, err = validate_bullet_rewrite(SRC, bad)
        self.assertFalse(ok)
        self.assertIn("proper noun/tool/team", err)

    def test_rejects_over_word_budget(self):
        # A source that is already verb-led and numeric-safe, but the "rewrite" pads it
        # past the word cap without changing any fact.
        source = "Resolved issues quickly."
        long_bad = "Resolved " + ("really " * 45) + "quickly."
        ok, err = validate_bullet_rewrite(source, long_bad, max_words=40)
        self.assertFalse(ok)


class TestValidateProseRewrite(unittest.TestCase):
    def test_does_not_require_leading_verb(self):
        # Cover-letter paragraphs are prose, not verb-first bullets -- this must not
        # reuse the bullet gate's leading-verb requirement.
        source = "The friction that builds up in a product's admin layer doesn't stay invisible for long."
        rephrase = "Friction in a product's admin layer never stays invisible for long."
        ok, err = validate_prose_rewrite(source, rephrase)
        self.assertTrue(ok, err)

    def test_rejects_dropped_number_in_prose(self):
        source = "We eliminated a 40% data drop-off within two quarters."
        bad = "We eliminated a significant data drop-off within two quarters."
        ok, err = validate_prose_rewrite(source, bad)
        self.assertFalse(ok)

    def test_rejects_empty_rewrite(self):
        ok, err = validate_prose_rewrite(SRC, "")
        self.assertFalse(ok)
        self.assertEqual(err, "Empty rewrite")


class TestExtractRewriteText(unittest.TestCase):
    def test_extracts_from_dict(self):
        self.assertEqual(_extract_rewrite_text({"rewritten": "hello"}), "hello")

    def test_extracts_from_json_string(self):
        self.assertEqual(_extract_rewrite_text('{"rewritten": "hello"}'), "hello")

    def test_extracts_from_fenced_json(self):
        self.assertEqual(_extract_rewrite_text('```json\n{"rewritten": "hello"}\n```'), "hello")

    def test_falls_back_to_raw_text_on_unparseable_input(self):
        self.assertEqual(_extract_rewrite_text("just plain text"), "just plain text")

    def test_handles_empty_input(self):
        self.assertEqual(_extract_rewrite_text(""), "")
        self.assertEqual(_extract_rewrite_text(None), "")


class TestEscalationLadder(unittest.TestCase):
    """Monkeypatch call_llm_stage so these run with zero network calls."""

    def setUp(self):
        self._orig_call = local_rewrite.call_llm_stage
        self._tmp_dir = tempfile.mkdtemp()
        os.environ["REWRITE_BATCH_ID"] = os.path.basename(self._tmp_dir)

    def tearDown(self):
        local_rewrite.call_llm_stage = self._orig_call
        os.environ.pop("REWRITE_BATCH_ID", None)

    def test_returns_verbatim_on_empty_source(self):
        self.assertEqual(local_rewrite_sentence(""), "")
        self.assertEqual(local_rewrite_sentence("   "), "   ")

    def test_accepts_first_attempt_when_valid(self):
        calls = []

        def fake(stage_id, system, user, **kwargs):
            calls.append(kwargs.get("model"))
            return {"rewritten": "Resolved 90% of a roughly 300-item security vulnerability backlog without stalling core roadmap delivery."}

        local_rewrite.call_llm_stage = fake
        out = local_rewrite_sentence(SRC)
        self.assertNotEqual(out, SRC)
        self.assertEqual(len(calls), 1)  # no escalation needed

    def test_falls_back_to_verbatim_after_exhausting_ladder(self):
        calls = []

        def fake(stage_id, system, user, **kwargs):
            calls.append(kwargs.get("model"))
            # Always fabricate a number so every attempt fails validation.
            return {"rewritten": SRC.replace("300", "777")}

        local_rewrite.call_llm_stage = fake
        out = local_rewrite_sentence(SRC)
        self.assertEqual(out, SRC)  # guaranteed-safe fallback
        self.assertEqual(len(calls), 3)  # primary + retry + escalation model
        self.assertEqual(calls[2], local_rewrite._ESCALATION_MODEL)

    def test_call_errors_do_not_raise_and_still_fall_back(self):
        def fake(stage_id, system, user, **kwargs):
            raise RuntimeError("Ollama not reachable")

        local_rewrite.call_llm_stage = fake
        out = local_rewrite_sentence(SRC)  # must not raise
        self.assertEqual(out, SRC)

    def test_fallback_is_logged(self):
        def fake(stage_id, system, user, **kwargs):
            return {"rewritten": SRC.replace("300", "777")}

        local_rewrite.call_llm_stage = fake
        local_rewrite_sentence(SRC)
        log_path = local_rewrite._audit_log_path()
        self.assertTrue(os.path.exists(log_path))
        with open(log_path, encoding="utf-8") as f:
            lines = f.readlines()
        self.assertTrue(any("fallback_to_verbatim" in ln for ln in lines))


if __name__ == "__main__":
    unittest.main()
