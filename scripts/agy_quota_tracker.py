#!/usr/bin/env python3
"""Record Agy Gemini quota around supervised Stage 1 authoring calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "data" / "eval" / "cr117" / "agy_quota_ledger.jsonl"
FAMILY = "Gemini Models"
WINDOWS = ("Weekly Limit Remaining", "Five Hour Limit Remaining")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_quota() -> dict:
    result = subprocess.run(
        ["agy", "-p", "/usage"], capture_output=True, text=True, timeout=30, check=True
    )
    windows = {}
    for line in result.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) != 4 or fields[0] != FAMILY or fields[1] not in WINDOWS:
            continue
        percent = fields[2].strip()
        if not percent.endswith("%"):
            raise ValueError(f"Unexpected quota value: {percent}")
        remaining = int(percent[:-1])
        if not 0 <= remaining <= 100:
            raise ValueError(f"Quota outside 0-100: {percent}")
        datetime.fromisoformat(fields[3].replace("Z", "+00:00"))
        windows[fields[1]] = {"remaining_percent": remaining, "reset_at": fields[3]}
    if set(windows) != set(WINDOWS):
        raise ValueError("Agy /usage did not return both Gemini quota windows")
    return {"at": now(), "windows": windows}


def events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def append_event(path: Path, event: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as target:
        target.write(json.dumps(event, sort_keys=True) + "\n")


def result_usage(path: Path) -> dict | None:
    if not path.exists():
        return None
    result = None
    with path.open(encoding="utf-8") as source:
        for line in source:
            item = json.loads(line)
            if item.get("event") == "result":
                result = item
    if result is None:
        return None
    payload = result.get("result", {})
    return {"status": payload.get("status"), "usage": payload.get("usage")}


def deltas(before: dict, after: dict) -> dict[str, int | None]:
    changes = {}
    for window in WINDOWS:
        old = before["windows"][window]
        new = after["windows"][window]
        changes[window] = (
            old["remaining_percent"] - new["remaining_percent"]
            if old["reset_at"] == new["reset_at"]
            and old["remaining_percent"] >= new["remaining_percent"] else None
        )
    return changes


def observed_cushions(history: list[dict]) -> dict[str, int]:
    return {
        window: max([5] + [item["quota_drop_points"][window] or 0
                            for item in history if item["type"] == "after"])
        for window in WINDOWS
    }


def preflight(args: argparse.Namespace) -> int:
    history = events(args.ledger)
    if any(item["type"] == "before" and not any(
        later["type"] == "after" and later["run_id"] == item["run_id"] for later in history
    ) for item in history):
        raise ValueError("A prior run has no after-snapshot; finish it before starting another")
    if any(item["run_id"] == args.run_id for item in history):
        raise ValueError(f"Run ID already used: {args.run_id}")
    prompt_bytes = args.prompt.read_bytes()
    estimate = args.prompt_estimated_tokens
    metadata = args.prompt.parent / "authoring_prompt_meta.json"
    if estimate is None and metadata.exists():
        estimate = json.loads(metadata.read_text(encoding="utf-8")).get("total_estimated_tokens")
    quota = read_quota()
    cushions = observed_cushions(history)
    lows = [name for name, value in quota["windows"].items()
            if value["remaining_percent"] <= args.reserve_percent + cushions[name]]
    if lows:
        print(f"BLOCKED: Gemini quota too near {args.reserve_percent}% reserve "
              f"for another call: {', '.join(lows)}")
        return 2
    event = {
        "type": "before", "run_id": args.run_id, "case": args.case,
        "model": args.model, "prompt_bytes": len(prompt_bytes),
        "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
        "prompt_estimated_tokens": estimate,
        "reserve_percent": args.reserve_percent, "quota": quota,
    }
    append_event(args.ledger, event)
    print(f"READY {args.run_id}: weekly {quota['windows'][WINDOWS[0]]['remaining_percent']}%, "
          f"five-hour {quota['windows'][WINDOWS[1]]['remaining_percent']}% "
          f"(reserve {args.reserve_percent}%, minimum call cushion 5pp). "
          "Finish this run before the next preflight.")
    return 0


def finish(args: argparse.Namespace) -> int:
    history = events(args.ledger)
    matches = [item for item in history if item["run_id"] == args.run_id]
    if len(matches) != 1 or matches[0]["type"] != "before":
        raise ValueError("Run must have exactly one unfinished preflight")
    stream = result_usage(args.stream)
    quota = read_quota()
    changes = deltas(matches[0]["quota"], quota)
    append_event(args.ledger, {
        "type": "after", "run_id": args.run_id, "quota": quota,
        "quota_drop_points": changes, "agy_result": stream,
    })
    print(f"RECORDED {args.run_id}: weekly drop {changes[WINDOWS[0]]}, "
          f"five-hour drop {changes[WINDOWS[1]]} percentage points; "
          f"Agy result {stream['status'] if stream else 'missing'}.")
    return 0


def status(args: argparse.Namespace) -> int:
    history = events(args.ledger)
    quota = read_quota()
    print(f"Gemini now: weekly {quota['windows'][WINDOWS[0]]['remaining_percent']}%, "
          f"five-hour {quota['windows'][WINDOWS[1]]['remaining_percent']}%")
    runs = {item["run_id"]: item for item in history if item["type"] == "before"}
    for item in history:
        if item["type"] != "after":
            continue
        before = runs[item["run_id"]]
        drops = item["quota_drop_points"]
        usage = (item["agy_result"] or {}).get("usage") or {}
        print(f"{item['run_id']} [{before['model']}] prompt~{before['prompt_estimated_tokens']} tokens; "
              f"input={usage.get('input_tokens', '?')} output={usage.get('output_tokens', '?')} "
              f"thinking={usage.get('thinking_tokens', '?')}; "
              f"weekly={drops[WINDOWS[0]]}pp five-hour={drops[WINDOWS[1]]}pp")
    for run_id in runs:
        if not any(item["type"] == "after" and item["run_id"] == run_id for item in history):
            print(f"UNFINISHED {run_id}")
    comparable = [item for item in history if item["type"] == "after" and all(
        item["quota_drop_points"][window] is not None for window in WINDOWS
    )]
    if len(comparable) < 2:
        print("Batch-size estimate: waiting for two comparable before/after calls.")
    else:
        cushions = observed_cushions(history)
        capacity = min(max(0, (quota["windows"][window]["remaining_percent"] - 20)
                           // cushions[window]) for window in WINDOWS)
        print(f"Tentative capacity above 20% reserve: {capacity} calls "
              f"(planning cushions {cushions[WINDOWS[0]]}pp weekly and "
              f"{cushions[WINDOWS[1]]}pp five-hour per call; not a guarantee).")
    print("Quota is rounded and work-based. A 0pp change does not mean a free call; "
          "resets make cross-window deltas unavailable.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    sub = parser.add_subparsers(dest="command", required=True)
    before = sub.add_parser("before", help="Check reserve and record a planned call")
    before.add_argument("--run-id", required=True)
    before.add_argument("--case", required=True)
    before.add_argument("--model", default="gemini-3.8-flash-medium")
    before.add_argument("--prompt", type=Path, required=True)
    before.add_argument("--prompt-estimated-tokens", type=int)
    before.add_argument("--reserve-percent", type=int, default=20)
    after = sub.add_parser("after", help="Record quota and Agy stream after the call")
    after.add_argument("--run-id", required=True)
    after.add_argument("--stream", type=Path, required=True)
    sub.add_parser("status", help="Show current quota and completed run deltas")
    args = parser.parse_args()
    if getattr(args, "reserve_percent", 20) not in range(101):
        parser.error("reserve percent must be 0-100")
    try:
        return {"before": preflight, "after": finish, "status": status}[args.command](args)
    except (OSError, ValueError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(f"Quota tracker failed closed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
