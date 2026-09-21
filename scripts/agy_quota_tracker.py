#!/usr/bin/env python3
"""Record Agy Gemini quota around supervised Stage 1 authoring calls.

``/usage`` in headless mode (``agy -p "/usage"``) is currently broken -- a
confirmed Google-side bug in the agy/Antigravity CLI (headless print mode
soft-denies the file-read the command needs to answer, so it never returns
real numbers; reproduced directly 2026-09-21, no client-side permissions.allow
fix found). read_quota() below still tries the real panel first (self-healing
the moment Google fixes it, no code change needed here), and falls back to a
SELF-TRACKED estimate computed purely from our own ledger's real per-call
token usage (every agy call already reports exact token counts via
``--output-format json``/stream usage, independent of ``/usage``) against a
locally configured safety budget in data/agy_quota_budget.json -- NOT
Google's real ceiling, which headless mode has no way to read. See that
file's _description for how the budget numbers were derived and how to
recalibrate them. Every quota dict below carries a "source" field
("usage_panel" or "self_tracked_estimate") so callers and printed output are
never silently vague about which one produced a number.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "data" / "eval" / "cr117" / "agy_quota_ledger.jsonl"
DEFAULT_BUDGET_CONFIG = ROOT / "data" / "agy_quota_budget.json"
FAMILY = "Gemini Models"
WINDOWS = ("Weekly Limit Remaining", "Five Hour Limit Remaining")
_WINDOW_HOURS = {WINDOWS[0]: 24 * 7, WINDOWS[1]: 5}
_WINDOW_BUDGET_KEY = {WINDOWS[0]: "weekly_token_budget", WINDOWS[1]: "five_hour_token_budget"}
_FALLBACK_TOKEN_BUDGET = {WINDOWS[0]: 50_000_000, WINDOWS[1]: 6_000_000}
RECEIPTS_ENV = "APPLYR_AGY_QUOTA_RECEIPTS"
ACTIVE_SLUG_ENV = "APPLYR_ACTIVE_SLUG"
ACTIVE_FOLDER_ENV = "APPLYR_ACTIVE_FOLDER"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_usage_panel() -> dict:
    """The real Google-reported quota, via agy's interactive /usage panel.

    Currently fails in headless mode (see module docstring) -- kept as the
    first attempt, not removed, so this self-heals the moment Google fixes
    the underlying bug."""
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
        windows[fields[1]] = {
            "remaining_percent": remaining,
            "reset_at": fields[3],
            "source": "usage_panel",
        }
    if set(windows) != set(WINDOWS):
        raise ValueError("Agy /usage did not return both Gemini quota windows")
    return {"at": now(), "windows": windows}


def load_budget_config(path: Path = DEFAULT_BUDGET_CONFIG) -> dict[str, int]:
    """Local safety-budget ceilings for the self-tracked fallback estimate.
    Falls back to conservative hardcoded defaults if the file is missing or
    a key is absent -- never crashes just because config wasn't written."""
    budget = dict(_FALLBACK_TOKEN_BUDGET)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return budget
        for window, key in _WINDOW_BUDGET_KEY.items():
            value = data.get(key)
            if isinstance(value, (int, float)) and value > 0:
                budget[window] = int(value)
    return budget


def _event_tokens(event: dict[str, Any]) -> int:
    """Best-effort real token total from an 'after' ledger event. Prefers
    agy's own result.usage.total_tokens; falls back to the step-sum for the
    rare SUCCESS-with-empty-result.usage case (FIXQUEUE item 9b)."""
    result = event.get("agy_result") or {}
    if not isinstance(result, dict):
        return 0
    usage = result.get("usage") or {}
    if isinstance(usage, dict):
        total = usage.get("total_tokens")
        if isinstance(total, (int, float)) and total > 0:
            return int(total)
    step_sum = result.get("step_sum") or {}
    if isinstance(step_sum, dict):
        return sum(
            int(step_sum.get(key) or 0)
            for key in ("input_tokens", "output_tokens", "thinking_tokens")
        )
    return 0


def _self_tracked_quota(
    *, ledger: Path, budget: dict[str, int], extra_tokens: dict[str, int] | None = None
) -> dict:
    """Estimate remaining quota purely from our own ledger's real per-call
    token usage within each rolling window -- no agy call at all, so this
    cannot hang or hit the headless-permission bug. See module docstring."""
    history = events(ledger) if ledger.exists() else []
    now_dt = datetime.now(timezone.utc)
    pending = extra_tokens or {}
    windows_out: dict[str, dict[str, Any]] = {}
    for window in WINDOWS:
        cutoff = now_dt - timedelta(hours=_WINDOW_HOURS[window])
        used = 0
        for item in history:
            if item.get("type") != "after":
                continue
            try:
                at = datetime.fromisoformat(str(item.get("at", "")).replace("Z", "+00:00"))
            except ValueError:
                continue
            if at < cutoff:
                continue
            used += _event_tokens(item)
        used += int(pending.get(window, 0))
        ceiling = max(1, int(budget[window]))
        remaining_percent = max(0, min(100, round(100 * (1 - used / ceiling))))
        windows_out[window] = {
            "remaining_percent": remaining_percent,
            "reset_at": (now_dt + timedelta(hours=_WINDOW_HOURS[window])).isoformat(),
            "source": "self_tracked_estimate",
            "tokens_used_in_window": used,
            "token_budget": ceiling,
        }
    return {"at": now(), "windows": windows_out}


def read_quota(
    *,
    ledger: Path = DEFAULT_LEDGER,
    budget: dict[str, int] | None = None,
    extra_tokens: dict[str, int] | None = None,
) -> dict:
    """The real /usage panel if it works, else our own self-tracked
    estimate. Never raises for the "headless /usage is broken" case --
    that's the expected, common path now, not an error."""
    try:
        return _read_usage_panel()
    except Exception:
        pass
    return _self_tracked_quota(
        ledger=ledger, budget=budget or load_budget_config(), extra_tokens=extra_tokens
    )


def receipts_enabled() -> bool:
    return os.environ.get(RECEIPTS_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def snapshot_quota(reader: Callable[[], dict] | None = None) -> dict[str, Any]:
    """Read Agy quota. A failed read is missing, never a silent zero."""
    try:
        quota = (reader or read_quota)()
    except Exception as exc:
        reason = " ".join(str(exc).split())[:240] or "quota read failed"
        return {"ok": False, "missing": True, "reason": reason, "quota": None}
    if not isinstance(quota, dict) or not isinstance(quota.get("windows"), dict):
        return {
            "ok": False,
            "missing": True,
            "reason": "quota snapshot missing windows",
            "quota": None,
        }
    return {"ok": True, "missing": False, "reason": None, "quota": quota}


def _window_remaining(snapshot: dict[str, Any] | None, window: str) -> int | None:
    if not isinstance(snapshot, dict) or snapshot.get("missing") or not snapshot.get("ok"):
        return None
    windows = (snapshot.get("quota") or {}).get("windows") or {}
    value = windows.get(window) if isinstance(windows, dict) else None
    if not isinstance(value, dict):
        return None
    remaining = value.get("remaining_percent")
    return remaining if isinstance(remaining, int) else None


def build_call_receipt(
    *,
    stage: str,
    slug: str,
    task: str,
    model: str,
    effort: str | None,
    cache_status: str,
    prompt_estimate: int | None,
    reported_usage: dict[str, Any] | None,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    wall_seconds: float,
) -> dict[str, Any]:
    return {
        "schema_version": "agy-quota-receipt-v1",
        "type": "call",
        "stage": stage,
        "slug": slug,
        "task": task,
        "model": model,
        "effort": effort,
        "cache_status": cache_status,
        "prompt_estimate": prompt_estimate,
        "reported_usage": reported_usage,
        "weekly_before": _window_remaining(before, WINDOWS[0]),
        "five_hour_before": _window_remaining(before, WINDOWS[1]),
        "weekly_after": _window_remaining(after, WINDOWS[0]),
        "five_hour_after": _window_remaining(after, WINDOWS[1]),
        "wall_seconds": round(float(wall_seconds), 3),
        "before_missing": bool(not before or before.get("missing")),
        "after_missing": bool(not after or after.get("missing")),
        "before_reason": None if not before else before.get("reason"),
        "after_reason": None if not after else after.get("reason"),
        "at": now(),
    }


def emit_call_receipt(
    receipt: dict[str, Any],
    *,
    folder: Path | str | None = None,
    ledger: Path | None = None,
) -> None:
    if folder:
        append_event(Path(folder) / "observability" / "agy_quota.jsonl", receipt)
    if ledger is not None:
        append_event(ledger, receipt)


def bind_active_job(folder: Path | str, slug: str | None = None) -> None:
    path = Path(folder)
    os.environ[ACTIVE_FOLDER_ENV] = str(path)
    os.environ[ACTIVE_SLUG_ENV] = slug or path.name


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
    """Return Agy's final result usage plus per-step sums from the stream.

    Agy's top-level result.usage is the sum of DONE agent_response steps in that
    process, not a single prompt-sized call. Cache-read tokens are reported
    separately and must not be treated as five-hour quota 1:1 with input.
    """
    if not path.exists():
        return None
    result = None
    step_sum = {
        "input_tokens": 0,
        "output_tokens": 0,
        "thinking_tokens": 0,
        "cache_read_tokens": 0,
    }
    agent_steps = 0
    with path.open(encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("event") == "result":
                result = item
            step = item.get("step_update") if item.get("event") == "step_update" else None
            usage = step.get("usage") if isinstance(step, dict) else None
            if (
                isinstance(step, dict)
                and step.get("state") == "DONE"
                and isinstance(usage, dict)
            ):
                agent_steps += 1
                for key in step_sum:
                    try:
                        step_sum[key] += int(usage.get(key) or 0)
                    except (TypeError, ValueError):
                        continue
    if result is None and agent_steps == 0:
        return None
    payload = result.get("result", {}) if isinstance(result, dict) else {}
    if not isinstance(payload, dict):
        payload = {}
    return {
        "status": payload.get("status"),
        "usage": payload.get("usage"),
        "agent_steps_with_usage": agent_steps,
        "step_sum": step_sum,
    }


def deltas(before: dict, after: dict) -> dict[str, int | None]:
    """Percentage-point drop per window. None when not comparable: a real
    /usage panel read and a self-tracked estimate are different measurement
    systems (see read_quota()'s docstring), so mixing them would be
    misleading rather than just imprecise -- both sides must share a
    "source". Self-tracked mode has no fixed reset_at to compare (it is
    always "now + window hours", recomputed fresh each read), so unlike the
    original panel-only version this no longer gates on reset_at equality."""
    changes = {}
    for window in WINDOWS:
        old = before["windows"][window]
        new = after["windows"][window]
        changes[window] = (
            old["remaining_percent"] - new["remaining_percent"]
            if old.get("source") == new.get("source")
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
    quota = read_quota(ledger=args.ledger)
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
    print(f"READY {args.run_id} [{quota['windows'][WINDOWS[1]].get('source', 'unknown')}]: "
          f"weekly {quota['windows'][WINDOWS[0]]['remaining_percent']}%, "
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
    this_call_tokens = _event_tokens({"agy_result": stream}) if stream else 0
    quota = read_quota(
        ledger=args.ledger,
        extra_tokens={WINDOWS[0]: this_call_tokens, WINDOWS[1]: this_call_tokens},
    )
    changes = deltas(matches[0]["quota"], quota)
    append_event(args.ledger, {
        "type": "after", "run_id": args.run_id, "quota": quota,
        "quota_drop_points": changes, "agy_result": stream,
    })
    usage = (stream or {}).get("usage") or {}
    steps = (stream or {}).get("agent_steps_with_usage")
    print(f"RECORDED {args.run_id}: weekly drop {changes[WINDOWS[0]]}, "
          f"five-hour drop {changes[WINDOWS[1]]} percentage points; "
          f"Agy result {stream['status'] if stream else 'missing'}; "
          f"input={usage.get('input_tokens', '?')} "
          f"cache_read={usage.get('cache_read_tokens', '?')} "
          f"agent_steps={steps if steps is not None else '?'}.")
    if isinstance(steps, int) and steps > 1:
        print(
            "NOTE: result.usage is the sum of internal agent steps in this "
            "process, not one prompt-sized call. Size batches from five-hour "
            "percentage-point drops. Cache-read tokens are not 1:1 with those drops."
        )
    return 0


def status(args: argparse.Namespace) -> int:
    history = events(args.ledger)
    quota = read_quota(ledger=args.ledger)
    print(f"Gemini now [{quota['windows'][WINDOWS[1]].get('source', 'unknown')}]: "
          f"weekly {quota['windows'][WINDOWS[0]]['remaining_percent']}%, "
          f"five-hour {quota['windows'][WINDOWS[1]]['remaining_percent']}%")
    if quota["windows"][WINDOWS[1]].get("source") == "self_tracked_estimate":
        print(
            "  (estimate from our own ledger, not Google's real number -- "
            "/usage is unreadable in headless mode, see data/agy_quota_budget.json)"
        )
    runs = {item["run_id"]: item for item in history if item["type"] == "before"}
    for item in history:
        if item["type"] != "after":
            continue
        before = runs[item["run_id"]]
        drops = item["quota_drop_points"]
        usage = (item["agy_result"] or {}).get("usage") or {}
        steps = (item["agy_result"] or {}).get("agent_steps_with_usage")
        print(f"{item['run_id']} [{before['model']}] prompt~{before['prompt_estimated_tokens']} tokens; "
              f"input={usage.get('input_tokens', '?')} output={usage.get('output_tokens', '?')} "
              f"thinking={usage.get('thinking_tokens', '?')} "
              f"cache_read={usage.get('cache_read_tokens', '?')} "
              f"agent_steps={steps if steps is not None else '?'}; "
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
          "resets make cross-window deltas unavailable. Size batches from five-hour "
          "percentage-point drops. Cache-read tokens occupy context but did not move "
          "the five-hour window 1:1 with input on the 2026-09-18 shakedown.")
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
