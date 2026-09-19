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

    def test_result_usage_sums_done_agent_steps(self):
        with tempfile.TemporaryDirectory() as directory:
            stream = Path(directory) / "stream.jsonl"
            lines = [
                json.dumps({"event": "step_update", "step_update": {
                    "step_index": 1, "state": "DONE", "step_type": "agent_response",
                    "usage": {"input_tokens": 38967, "output_tokens": 487,
                              "thinking_tokens": 416, "cache_read_tokens": 0},
                }}),
                json.dumps({"event": "step_update", "step_update": {
                    "step_index": 3, "state": "DONE", "step_type": "agent_response",
                    "usage": {"input_tokens": 2612, "output_tokens": 343,
                              "thinking_tokens": 169, "cache_read_tokens": 36949},
                }}),
                json.dumps({"event": "step_update", "step_update": {
                    "step_index": 2, "state": "ACTIVE", "step_type": "agent_response",
                    "text_delta": "ignored",
                }}),
                json.dumps({"event": "result", "result": {
                    "status": "SUCCESS",
                    "usage": {"input_tokens": 41579, "output_tokens": 830,
                              "thinking_tokens": 585, "cache_read_tokens": 36949},
                }}),
            ]
            stream.write_text("\n".join(lines) + "\n", encoding="utf-8")
            parsed = tracker.result_usage(stream)
            self.assertEqual(parsed["status"], "SUCCESS")
            self.assertEqual(parsed["usage"]["input_tokens"], 41579)
            self.assertEqual(parsed["agent_steps_with_usage"], 2)
            self.assertEqual(parsed["step_sum"]["input_tokens"], 41579)
            self.assertEqual(parsed["step_sum"]["cache_read_tokens"], 36949)

    def test_failed_quota_read_is_missing_not_zero(self) -> None:
        snap = tracker.snapshot_quota(reader=lambda: (_ for _ in ()).throw(RuntimeError("agy down")))
        self.assertTrue(snap["missing"])
        self.assertIsNone(snap["quota"])
        receipt = tracker.build_call_receipt(
            stage="stage0",
            slug="rentana",
            task="evidence",
            model="gemini-3.8-flash-medium",
            effort="medium",
            cache_status="fresh",
            prompt_estimate=None,
            reported_usage=None,
            before=snap,
            after=snap,
            wall_seconds=1.5,
        )
        self.assertIsNone(receipt["weekly_before"])
        self.assertIsNone(receipt["five_hour_before"])
        self.assertIsNone(receipt["weekly_after"])
        self.assertTrue(receipt["before_missing"])
        self.assertEqual(receipt["before_reason"], "agy down")

    def test_emit_call_receipt_writes_folder_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            before = tracker.snapshot_quota(reader=lambda: quota(70, 80))
            after = tracker.snapshot_quota(reader=lambda: quota(69, 79))
            receipt = tracker.build_call_receipt(
                stage="stage0",
                slug="rentana",
                task="extraction",
                model="gemini-3.8-flash-medium",
                effort="medium",
                cache_status="fresh",
                prompt_estimate=1200,
                reported_usage={"input_tokens": 10},
                before=before,
                after=after,
                wall_seconds=2,
            )
            tracker.emit_call_receipt(receipt, folder=folder)
            path = folder / "observability" / "agy_quota.jsonl"
            rows = tracker.events(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["weekly_before"], 70)
            self.assertEqual(rows[0]["five_hour_after"], 79)
            self.assertFalse(rows[0]["before_missing"])


if __name__ == "__main__":
    unittest.main()
