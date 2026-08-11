"""CR-076 workflow authority package.

Only ``receipts.py`` may write ``workflow_state.json`` / ``stage_receipts/*.json``.
Workers stay in ``scripts/*.py`` and are called by ``runner.py``.
"""
from __future__ import annotations

SCHEMA_VERSION = 1

WORKFLOW_STATE_NAME = "workflow_state.json"
RECEIPTS_DIR_NAME = "stage_receipts"

STAGES = ("stage0", "stage1", "stage2", "stage3")
