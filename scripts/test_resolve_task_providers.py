#!/usr/bin/env python3
"""CR-106 tests for resolve_task_providers and resolve_default_task_providers.

Mirrors tests/unit/groqClient.test.ts's resolveTaskProviders block on the Python side.
Env API keys are cleared so _is_configured only sees the settings dict we pass in.

Run:
    .venv\\Scripts\\python.exe -m unittest scripts.test_resolve_task_providers -v
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import utils  # noqa: E402

_CLEAR_LLM_ENV = {
    "GEMINI_API_KEY": "",
    "ANTHROPIC_API_KEY": "",
    "OLLAMA_HOST": "",
    "PERPLEXITY_API_KEY": "",
    "GROQ_API_KEY": "",
}


def _patch_settings(settings: dict):
    """Load the given settings and ignore process-level API keys."""
    return mock.patch.multiple(
        utils,
        load_llm_settings=mock.Mock(return_value=settings),
    )


class TestResolveTaskProviders(unittest.TestCase):
    def test_no_override_returns_default_chain_unchanged(self):
        with _patch_settings({}):
            self.assertEqual(
                utils.resolve_task_providers("we_scoring_summary", ["gemini"]),
                ["gemini"],
            )

    def test_override_promotes_to_front_without_dropping_the_rest(self):
        with _patch_settings({"taskProviderOverrides": {"we_scoring_summary": "groq"}}):
            self.assertEqual(
                utils.resolve_task_providers("we_scoring_summary", ["gemini"]),
                ["groq", "gemini"],
            )

    def test_override_already_first_does_not_duplicate(self):
        with _patch_settings({"taskProviderOverrides": {"we_scoring_summary": "gemini"}}):
            self.assertEqual(
                utils.resolve_task_providers("we_scoring_summary", ["gemini"]),
                ["gemini"],
            )

    def test_override_for_a_different_task_is_ignored(self):
        with _patch_settings({"taskProviderOverrides": {"ai_rewrite": "claude"}}):
            self.assertEqual(
                utils.resolve_task_providers("we_scoring_summary", ["gemini"]),
                ["gemini"],
            )

    def test_empty_overrides_dict_is_treated_as_unset(self):
        with _patch_settings({"taskProviderOverrides": {}}):
            self.assertEqual(
                utils.resolve_task_providers("ai_rewrite", ["claude", "gemini"]),
                ["claude", "gemini"],
            )


class TestResolveDefaultTaskProviders(unittest.TestCase):
    def test_no_override_returns_configured_primary_rotation(self):
        settings = {
            "primaryProvider": "claude",
            "claudeApiKey": "sk-ant-x",
            "geminiApiKey": "gm-x",
        }
        with _patch_settings(settings), mock.patch.dict(os.environ, _CLEAR_LLM_ENV, clear=False):
            self.assertEqual(
                utils.resolve_default_task_providers("ai_rewrite"),
                ["claude", "gemini"],
            )

    def test_override_promotes_to_front_of_configured_chain(self):
        settings = {
            "primaryProvider": "gemini",
            "geminiApiKey": "gm-x",
            "claudeApiKey": "sk-ant-x",
            "taskProviderOverrides": {"ai_rewrite": "claude"},
        }
        with _patch_settings(settings), mock.patch.dict(os.environ, _CLEAR_LLM_ENV, clear=False):
            self.assertEqual(
                utils.resolve_default_task_providers("ai_rewrite"),
                ["claude", "gemini"],
            )

    def test_groq_override_is_prepended_even_though_groq_is_not_in_fixed_order(self):
        settings = {
            "primaryProvider": "gemini",
            "geminiApiKey": "gm-x",
            "groqApiKey": "gsk-x",
            "taskProviderOverrides": {"ai_rewrite": "groq"},
        }
        with _patch_settings(settings), mock.patch.dict(os.environ, _CLEAR_LLM_ENV, clear=False):
            self.assertEqual(
                utils.resolve_default_task_providers("ai_rewrite"),
                ["groq", "gemini"],
            )

    def test_unconfigured_providers_are_not_in_the_default_chain(self):
        settings = {
            "primaryProvider": "gemini",
            "geminiApiKey": "gm-x",
        }
        with _patch_settings(settings), mock.patch.dict(os.environ, _CLEAR_LLM_ENV, clear=False):
            self.assertEqual(utils.resolve_default_task_providers("ai_rewrite"), ["gemini"])

    def test_we_scoring_summary_does_not_use_this_helper_default_on_purpose(self):
        """Regression guard for the near-miss in CR-106: wrapping we_scoring_summary in
        resolve_default_task_providers would have silently switched its default from Gemini
        to whatever primaryProvider is. generate_experience_summary.py must keep calling
        resolve_task_providers(..., ['gemini']) instead."""
        settings = {
            "primaryProvider": "claude",
            "claudeApiKey": "sk-ant-x",
            "geminiApiKey": "gm-x",
        }
        with _patch_settings(settings), mock.patch.dict(os.environ, _CLEAR_LLM_ENV, clear=False):
            default_rotation = utils.resolve_default_task_providers("we_scoring_summary")
            preserved_gemini = utils.resolve_task_providers("we_scoring_summary", ["gemini"])
            self.assertEqual(default_rotation, ["claude", "gemini"])
            self.assertEqual(preserved_gemini, ["gemini"])


if __name__ == "__main__":
    unittest.main()
