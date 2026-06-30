"""Tests for cover_letter_slots.py — Epic 2 skeleton, Epic 6 per-slot critic, Epic 7 hook."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _mock_llm(response: str):
    """Return a callable that always returns `response` when invoked as call_llm."""
    return MagicMock(return_value=response)


def _make_jd_profile(themes=None, keywords=None):
    profile = MagicMock()
    profile.priority_themes = themes or ["data platform", "reliability"]
    profile.keywords = keywords or ["saas", "enterprise"]
    profile.requirements = []
    return profile


# ---------------------------------------------------------------------------
# Hook validation
# ---------------------------------------------------------------------------

class TestHookValidation:
    def test_rejects_i_opener(self):
        from cover_letter_slots import validate_hook
        ok, reason = validate_hook("I have 6 years of experience.", {})
        assert not ok
        assert "I" in reason or "opener" in reason.lower()

    def test_rejects_over_35_words(self):
        from cover_letter_slots import validate_hook
        long_hook = " ".join(["word"] * 36)
        ok, reason = validate_hook(long_hook, {})
        assert not ok

    def test_rejects_enthusiasm_openers(self):
        from cover_letter_slots import validate_hook
        for phrase in ["Excited to", "Thrilled to", "Passionate about"]:
            ok, _ = validate_hook(f"{phrase} apply to HubSpot.", {})
            assert not ok, f"Expected failure for opener: {phrase}"

    def test_accepts_valid_hook(self):
        from cover_letter_slots import validate_hook
        hook = "HubSpot's bet on CRM data integrity is exactly where I've built product."
        ok, _ = validate_hook(hook, {})
        assert ok

    def test_under_8_words_rejected(self):
        from cover_letter_slots import validate_hook
        ok, reason = validate_hook("HubSpot is interesting.", {})
        assert not ok


# ---------------------------------------------------------------------------
# Hook generation
# ---------------------------------------------------------------------------

class TestHookGeneration:
    def test_generate_hook_returns_string(self):
        from cover_letter_slots import generate_hook
        mock_llm = _mock_llm("HubSpot's data quality investment is the problem I've spent six years solving.")
        with patch("cover_letter_slots.call_llm", mock_llm):
            result = generate_hook({"company_name": "HubSpot"})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_hook_strips_quotes(self):
        from cover_letter_slots import generate_hook
        mock_llm = _mock_llm('"HubSpot built the CRM that everyone integrates against."')
        with patch("cover_letter_slots.call_llm", mock_llm):
            result = generate_hook({"company_name": "HubSpot"})
        assert not result.startswith('"')

    def test_validated_hook_raises_on_persistent_bad(self):
        from cover_letter_slots import generate_validated_hook, HookGenerationError
        # Always returns an invalid hook (starts with "I")
        mock_llm = _mock_llm("I am excited to apply to HubSpot.")
        with patch("cover_letter_slots.call_llm", mock_llm):
            with pytest.raises(HookGenerationError):
                generate_validated_hook({"company_name": "HubSpot"}, max_attempts=2)

    def test_validated_hook_accepts_on_second_attempt(self):
        from cover_letter_slots import generate_validated_hook
        call_count = {"n": 0}

        def mock_llm(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return "I am excited about this role."  # bad
            return "HubSpot's reliability roadmap is where my work in platform stabilization applies directly."  # good

        with patch("cover_letter_slots.call_llm", mock_llm):
            result = generate_validated_hook({"company_name": "HubSpot"}, max_attempts=3)
        assert result.startswith("HubSpot")
        assert call_count["n"] == 2


# ---------------------------------------------------------------------------
# Slot generation — sequential context accumulation
# ---------------------------------------------------------------------------

class TestSlotGeneration:
    def _slot_llm(self):
        """Returns different content per call to test accumulation."""
        call_n = {"n": 0}
        responses = [
            "Asana's data reliability gap is a problem I've been solving for six years.",  # hook already set
            "At Cision I eliminated a 40% contact data drop-off across the platform pipeline.",  # PROOF_1
            "I also led 700 voluntary account migrations with zero forced migrations.",  # PROOF_2
            "I'd welcome the chance to bring this platform discipline to Asana.",  # CLOSING
        ]

        def _call(*args, **kwargs):
            i = call_n["n"] % len(responses)
            call_n["n"] += 1
            return responses[i]

        return _call

    def test_returns_four_slots(self):
        from cover_letter_slots import generate_cl_slots
        with patch("cover_letter_slots.call_llm", self._slot_llm()):
            slots = generate_cl_slots(
                hook="Asana's reliability gap is where I do my best work.",
                pre_selected_claims=["ACC-102: contact data remediation"],
                jd_text="PM role at Asana. Drive platform reliability.",
            )
        assert len(slots) == 4

    def test_slot_types_in_order(self):
        from cover_letter_slots import generate_cl_slots
        with patch("cover_letter_slots.call_llm", self._slot_llm()):
            slots = generate_cl_slots(
                hook="Asana's data quality problem is where I've built product.",
                pre_selected_claims=[],
                jd_text="Platform PM role.",
            )
        types = [s.slot_type for s in slots]
        assert types == ["HOOK", "PROOF_1", "PROOF_2", "CLOSING"]

    def test_hook_slot_uses_provided_hook(self):
        from cover_letter_slots import generate_cl_slots
        hook_text = "Asana's bet on workflow reliability is exactly where I've delivered."
        with patch("cover_letter_slots.call_llm", self._slot_llm()):
            slots = generate_cl_slots(
                hook=hook_text,
                pre_selected_claims=[],
                jd_text="PM role.",
            )
        assert slots[0].content == hook_text
        assert slots[0].slot_type == "HOOK"

    def test_later_slots_have_content(self):
        from cover_letter_slots import generate_cl_slots
        with patch("cover_letter_slots.call_llm", self._slot_llm()):
            slots = generate_cl_slots(
                hook="Asana's platform bet is exactly the problem space I know.",
                pre_selected_claims=[],
                jd_text="Platform PM.",
            )
        for s in slots:
            assert s.content is not None and len(s.content.strip()) > 0


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

class TestAssembly:
    def test_assembly_includes_header(self):
        from cover_letter_slots import CLSlot, assemble_cl_from_slots
        slots = [
            CLSlot("HOOK", "The hook sentence here.", 1, True),
            CLSlot("PROOF_1", "Proof one body.", 1, True),
            CLSlot("PROOF_2", "Proof two body.", 1, True),
            CLSlot("CLOSING", "Thank you for your time.", 1, True),
        ]
        result = assemble_cl_from_slots(slots, "HEADER", "Jason Taylor")
        assert "HEADER" in result
        assert "Jason Taylor" in result

    def test_assembly_no_em_dashes(self):
        from cover_letter_slots import CLSlot, assemble_cl_from_slots
        slots = [
            CLSlot("HOOK", "The hook — sentence.", 1, True),
            CLSlot("PROOF_1", "Proof — body.", 1, True),
            CLSlot("PROOF_2", "Second proof.", 1, True),
            CLSlot("CLOSING", "Closing line.", 1, True),
        ]
        result = assemble_cl_from_slots(slots, "HEADER", "Jason Taylor")
        assert "—" not in result

    def test_assembly_separates_paragraphs(self):
        from cover_letter_slots import CLSlot, assemble_cl_from_slots
        slots = [
            CLSlot("HOOK", "Hook.", 1, True),
            CLSlot("PROOF_1", "Proof one.", 1, True),
            CLSlot("PROOF_2", "Proof two.", 1, True),
            CLSlot("CLOSING", "Closing.", 1, True),
        ]
        result = assemble_cl_from_slots(slots, "HEADER", "Jason")
        assert "\n\n" in result


# ---------------------------------------------------------------------------
# Per-slot critic
# ---------------------------------------------------------------------------

class TestSlotCritic:
    def test_critique_returns_score_and_feedback(self):
        from cover_letter_slots import critique_slot, CLSlot
        slot = CLSlot("PROOF_1", "I led a cross-functional team to reduce data drop-off by 40%.", 1, True)
        mock_llm = _mock_llm('{"score": 0.8, "feedback": "Good proof density."}')
        jd = _make_jd_profile()
        with patch("cover_letter_slots.call_llm", mock_llm):
            score, feedback = critique_slot(slot, jd)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
        assert isinstance(feedback, str)

    def test_retry_slot_returns_passing_slot(self):
        from cover_letter_slots import retry_slot_until_passing, CLSlot
        slot = CLSlot("PROOF_1", "Some weak content.", 1, False)
        jd = _make_jd_profile()

        call_n = {"n": 0}

        def _llm(*args, **kwargs):
            call_n["n"] += 1
            if call_n["n"] < 3:
                return '{"score": 0.4, "feedback": "Too generic."}'
            if call_n["n"] == 3:
                return "Improved proof: eliminated 40% contact data drop-off across the pipeline."
            return '{"score": 0.75, "feedback": "Better."}'

        with patch("cover_letter_slots.call_llm", _llm):
            result = retry_slot_until_passing(slot, jd, "", threshold=0.65, max_attempts=3)
        assert isinstance(result, CLSlot)
