import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import agy_quota_tracker as tracker


def quota(weekly=72, five_hour=85, reset="2026-09-23T02:26:54Z"):
    return {"at": "2026-09-18T20:00:00+00:00", "windows": {
        tracker.WINDOWS[0]: {"remaining_percent": weekly, "reset_at": reset},
        tracker.WINDOWS[1]: {"remaining_percent": five_hour, "reset_at": reset},
    }}


class AgyQuotaTrackerTests(unittest.TestCase):
    def test_parses_live_usage_shape(self):
        output = ("Gemini Models\tWeekly Limit Remaining\t72%\t2026-09-23T02:26:54Z\n"
                  "Gemini Models\tFive Hour Limit Remaining\t85%\t2026-09-18T22:45:28Z\n"
                  "Claude and GPT models\tWeekly Limit Remaining\t96%\t2026-09-25T02:59:32Z\n")
        with patch.object(tracker.subprocess, "run", return_value=SimpleNamespace(stdout=output)):
            result = tracker.read_quota()
        self.assertEqual(result["windows"][tracker.WINDOWS[0]]["remaining_percent"], 72)
        self.assertEqual(result["windows"][tracker.WINDOWS[1]]["remaining_percent"], 85)

    def test_missing_window_fails_closed(self):
        output = "Gemini Models\tWeekly Limit Remaining\t72%\t2026-09-23T02:26:54Z\n"
        with patch.object(tracker.subprocess, "run", return_value=SimpleNamespace(stdout=output)):
            with self.assertRaises(ValueError):
                tracker.read_quota()

    def test_preflight_reserve_and_unfinished_call(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt = root / "prompt.md"
            prompt.write_text("test prompt", encoding="utf-8")
            (root / "authoring_prompt_meta.json").write_text(
                json.dumps({"total_estimated_tokens": 1234}), encoding="utf-8"
            )
            args = SimpleNamespace(ledger=root / "ledger.jsonl", run_id="one", case="case",
                                   model="gemini-3.8-flash-medium", prompt=prompt,
                                   prompt_estimated_tokens=10, reserve_percent=20)
            with patch.object(tracker, "read_quota", return_value=quota(25, 85)):
                self.assertEqual(tracker.preflight(args), 2)
            self.assertFalse(args.ledger.exists())
            with patch.object(tracker, "read_quota", return_value=quota()):
                self.assertEqual(tracker.preflight(args), 0)
                self.assertEqual(tracker.events(args.ledger)[0]["prompt_estimated_tokens"], 10)
                args.run_id = "two"
                with self.assertRaises(ValueError):
                    tracker.preflight(args)

    def test_preflight_uses_prompt_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt = root / "authoring_prompt.md"
            prompt.write_text("prompt", encoding="utf-8")
            (root / "authoring_prompt_meta.json").write_text(
                json.dumps({"total_estimated_tokens": 1234}), encoding="utf-8"
            )
            args = SimpleNamespace(ledger=root / "ledger.jsonl", run_id="one", case="case",
                                   model="gemini-3.8-flash-medium", prompt=prompt,
                                   prompt_estimated_tokens=None, reserve_percent=20)
            with patch.object(tracker, "read_quota", return_value=quota()):
                self.assertEqual(tracker.preflight(args), 0)
            self.assertEqual(tracker.events(args.ledger)[0]["prompt_estimated_tokens"], 1234)

    def test_after_reads_nested_result_and_reset_blocks_delta(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = root / "ledger.jsonl"
            tracker.append_event(ledger, {"type": "before", "run_id": "one", "quota": quota()})
            stream = root / "stream.jsonl"
            stream.write_text(json.dumps({"event": "result", "result": {
                "status": "SUCCESS", "usage": {"input_tokens": 123, "thinking_tokens": 45}
            }}) + "\n", encoding="utf-8")
            args = SimpleNamespace(ledger=ledger, run_id="one", stream=stream)
            with patch.object(tracker, "read_quota", return_value=quota(70, 84, "new-reset")):
                self.assertEqual(tracker.finish(args), 0)
            after = tracker.events(ledger)[1]
            self.assertEqual(after["agy_result"]["usage"]["input_tokens"], 123)
            self.assertIsNone(after["quota_drop_points"][tracker.WINDOWS[0]])


if __name__ == "__main__":
    unittest.main()
