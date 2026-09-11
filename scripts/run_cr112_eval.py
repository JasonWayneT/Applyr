#!/usr/bin/env python3
"""CR-112 eval harness for FR-310 and FR-311 with AC-407 and AC-408."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "cr112_eval"
_DEFAULT_OUT = _REPO_ROOT / "data" / "eval" / "cr112"
_COST_RULE = "Never add subscription_minutes to api_cents."
_TOKEN_METHOD = "bytes_div_4_estimate"

sys.path.insert(0, str(_SCRIPT_DIR))

from workflow.observability import append_event, new_run_id, read_events  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description="Run the CR-112 sanitized offline eval harness.")
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT, help="Output directory.")
    parser.add_argument(
        "--paid-llm",
        action="store_true",
        help="Opt-in only. Requires APPLYR_CR112_PAID_BUDGET and still records zero paid calls.",
    )
    parser.add_argument(
        "--assemble-packets",
        action="store_true",
        default=False,
        help="Reserved flag for later CR-112 work. This story keeps default assembly off.",
    )
    parser.add_argument(
        "--sqlite",
        type=Path,
        default=None,
        help="Optional redirected SQLite path. Basename jobagent.sqlite is refused.",
    )
    return parser


def _estimate_tokens_from_bytes(raw: bytes) -> int:
    """Estimate token count as bytes divided by four."""
    return len(raw) // 4


def _read_text(path: Path) -> str:
    """Read UTF-8 text from disk."""
    return path.read_text(encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def materialize_eval_set(dest: Path, fixtures: Path = _FIXTURES) -> list[Path]:
    """Copy only sanitized fixture inputs into the destination."""
    dest.mkdir(parents=True, exist_ok=True)
    folders: list[Path] = []
    for src in sorted(path for path in fixtures.iterdir() if path.is_dir()):
        target = dest / src.name
        target.mkdir(parents=True, exist_ok=True)
        for name in ("Original_JD.txt", "stage0_fit_gate.json"):
            source_file = src / name
            if source_file.is_file():
                shutil.copy2(source_file, target / name)
        folders.append(target)
    return folders


def _sqlite_is_production(path: Path | None) -> bool:
    """Return True when the path targets the production SQLite basename."""
    if path is None:
        return False
    try:
        candidate = path.resolve()
    except OSError:
        candidate = path
    return candidate.name.lower() == "jobagent.sqlite"


def _record_eval_events(folder: Path, run_id: str, event: str, **fields: Any) -> None:
    """Append one eval-stage observability event."""
    append_event(str(folder), run_id, "eval", event, **fields)


def collect_folder_metrics(
    folder: Path,
    *,
    call_llm_invocations: int,
    harness_spawn_count: int,
    paid_llm: bool,
    assemble_packets: bool,
) -> dict[str, Any]:
    """Collect one folder's offline eval metrics."""
    jd_bytes = (folder / "Original_JD.txt").read_bytes()
    row = {
        "slug": folder.name,
        "assemble_packets_requested": assemble_packets,
        "paid_llm_requested": paid_llm,
        "prompt_meta_estimated_tokens": _estimate_tokens_from_bytes(jd_bytes),
        "call_llm_invocations": call_llm_invocations,
        "harness_spawn_count": harness_spawn_count,
        "api_cents": 0,
        "subscription_minutes": 0,
        "cost_rule": _COST_RULE,
        "token_method": _TOKEN_METHOD,
        "run_events_count": len(read_events(str(folder))),
    }
    return row


def run_eval(
    dest: Path,
    *,
    paid_llm: bool,
    assemble_packets: bool,
    sqlite_path: Path | None,
) -> dict[str, Any]:
    """Run the sanitized offline evaluation harness."""
    if _sqlite_is_production(sqlite_path):
        raise SystemExit("Refusing production jobagent.sqlite. Pass a redirected eval DB or omit.")

    folders = materialize_eval_set(dest)
    rows: list[dict[str, Any]] = []
    for folder in folders:
        run_id = new_run_id()
        started_at = time.time()
        _record_eval_events(
            folder,
            run_id,
            "start",
            paid_llm_requested=paid_llm,
            assemble_packets_requested=assemble_packets,
            call_llm_invocations=0,
            harness_spawn_count=0,
        )
        row = collect_folder_metrics(
            folder,
            call_llm_invocations=0,
            harness_spawn_count=0,
            paid_llm=paid_llm,
            assemble_packets=assemble_packets,
        )
        duration_seconds = round(time.time() - started_at, 3)
        _record_eval_events(
            folder,
            run_id,
            "complete",
            paid_llm_requested=paid_llm,
            assemble_packets_requested=assemble_packets,
            call_llm_invocations=0,
            harness_spawn_count=0,
            prompt_meta_estimated_tokens=row["prompt_meta_estimated_tokens"],
            duration_seconds=duration_seconds,
            token_method=_TOKEN_METHOD,
        )
        row["run_events_count"] = len(read_events(str(folder)))
        rows.append(row)

    summary = {
        "schema_version": "1.0",
        "fixtures_root": str(_FIXTURES),
        "output_root": str(dest),
        "paid_llm": paid_llm,
        "paid_budget_env_present": bool(os.environ.get("APPLYR_CR112_PAID_BUDGET")),
        "paid_calls": 0,
        "sqlite": None if sqlite_path is None else str(sqlite_path),
        "assemble_packets": assemble_packets,
        "token_method": _TOKEN_METHOD,
        "cost_rule": _COST_RULE,
        "folders": rows,
        "totals": {
            "prompt_meta_estimated_tokens": sum(int(row["prompt_meta_estimated_tokens"]) for row in rows),
            "call_llm_invocations": 0,
            "harness_spawn_count": 0,
            "api_cents": 0,
            "subscription_minutes": 0,
        },
    }
    _write_json(dest / "metrics.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    """Run the CLI entry point."""
    args = build_parser().parse_args(argv)
    if args.paid_llm and not os.environ.get("APPLYR_CR112_PAID_BUDGET"):
        print("Paid eval requires APPLYR_CR112_PAID_BUDGET.", file=sys.stderr)
        return 2
    summary = run_eval(
        args.out,
        paid_llm=bool(args.paid_llm),
        assemble_packets=bool(args.assemble_packets),
        sqlite_path=args.sqlite,
    )
    print(json.dumps(summary["totals"], indent=2))
    print(f"Wrote {args.out / 'metrics.json'}")
    print("Columns kept separate: prompt_meta_estimated_tokens, call_llm_invocations, harness_spawn_count.")
    print("Cost rule: api_cents and subscription_minutes are never summed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
