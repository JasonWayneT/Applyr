#!/usr/bin/env python3
"""Exercise every Stage 0 checkpoint failure boundary (CR-108)."""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from stage0_checkpoint import (
    CHECKPOINT_BOUNDARIES,
    checkpoint_boundary,
    complete_judgment,
    make_item_key,
    make_run_key,
    mark_run_status,
    set_failure_injector,
    start_run,
    update_run_metadata,
    write_spool,
)
from stage0_confirmations import create_skill_confirmation


class InjectedCrash(RuntimeError):
    """Represent a process crash at one controlled checkpoint boundary."""


class TestStage0CheckpointFailures(unittest.TestCase):
    """Verify every injected checkpoint failure can be safely resumed."""

    def test_each_boundary_is_retryable_and_does_not_duplicate_judgments(self) -> None:
        """Inject one failure at each boundary, resume, and assert one judgment row."""
        for boundary in CHECKPOINT_BOUNDARIES:
            with self.subTest(boundary=boundary):
                self._exercise_boundary(boundary)

    def _exercise_boundary(self, failure_boundary: str) -> None:
        """Run a checkpoint fixture with one injected failure and then resume it."""
        fd, db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        try:
            run_key = make_run_key("acme", "jd", "v1", "policy", "index")
            item_key = make_item_key("required", "Experience with Trello", 0)
            request_hash = "request-hash"
            content_hash = "content-hash"
            evidence_index_hash = "evidence-index"

            def inject(name: str) -> None:
                """Raise only at the selected simulated process-crash boundary."""
                if name == failure_boundary:
                    raise InjectedCrash(name)

            set_failure_injector(inject)
            try:
                checkpoint_boundary("before_request_spool")
                with tempfile.TemporaryDirectory() as folder:
                    request_path, _ = write_spool(
                        Path(folder), "request", run_key, {"items": [item_key]}
                    )
                    checkpoint_boundary("after_request_spool")
                    start_run(
                        db_path,
                        run_key=run_key,
                        opportunity_key="acme",
                        jd_hash="jd",
                        prompt_version="v1",
                        provider_policy_hash="policy",
                        evidence_index_hash=evidence_index_hash,
                        request_hash=request_hash,
                        request_spool_path=request_path,
                    )
                    checkpoint_boundary("after_run_requested")
                    mark_run_status(db_path, run_key, "RUNNING")
                    checkpoint_boundary("before_provider_call")
                    response_path, response_digest = write_spool(
                        Path(folder), "response", run_key, {"results": [item_key]}
                    )
                    mark_run_status(
                        db_path,
                        run_key,
                        "RUNNING",
                        response_spool_path=response_path,
                        response_hash=response_digest,
                    )
                    checkpoint_boundary("after_response_spool")
                    complete_judgment(
                        db_path,
                        judgment_key=f"{run_key}:{item_key}",
                        run_key=run_key,
                        opportunity_key="acme",
                        item_key=item_key,
                        item_text="Experience with Trello",
                        bucket="required",
                        request_hash=request_hash,
                        content_hash=content_hash,
                        evidence_index_hash=evidence_index_hash,
                        judgment={"gate": "NONE", "evidence_level": 1},
                        provider="groq",
                        model="golden-test",
                    )
                    checkpoint_boundary("after_judgment_commit")
                    create_skill_confirmation(
                        db_path=db_path,
                        skill_key="trello",
                        display_name="Trello",
                        requirement="Experience with Trello",
                        opportunity_key="acme",
                        opportunity_company="Acme",
                        opportunity_title="Product Manager",
                    )
                    checkpoint_boundary("after_pending_confirmation_commit")
                    update_run_metadata(db_path, run_key, {"recovered_fixture": True})
                    mark_run_status(db_path, run_key, "COMPLETE")
                    checkpoint_boundary("after_run_complete")
            except InjectedCrash:
                pass
            finally:
                set_failure_injector(None)

            # Resume uses the same deterministic run key and idempotent writes.
            start_run(
                db_path,
                run_key=run_key,
                opportunity_key="acme",
                jd_hash="jd",
                prompt_version="v1",
                provider_policy_hash="policy",
                evidence_index_hash=evidence_index_hash,
                request_hash=request_hash,
            )
            complete_judgment(
                db_path,
                judgment_key=f"{run_key}:{item_key}",
                run_key=run_key,
                opportunity_key="acme",
                item_key=item_key,
                item_text="Experience with Trello",
                bucket="required",
                request_hash=request_hash,
                content_hash=content_hash,
                evidence_index_hash=evidence_index_hash,
                judgment={"gate": "NONE", "evidence_level": 1},
                provider="groq",
                model="golden-test",
            )
            connection = sqlite3.connect(db_path)
            try:
                judgment_count = connection.execute(
                    "SELECT COUNT(*) FROM stage0_judgments WHERE judgment_key = ?",
                    (f"{run_key}:{item_key}",),
                ).fetchone()[0]
                self.assertEqual(judgment_count, 1)
            finally:
                connection.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


if __name__ == "__main__":
    unittest.main()
