#!/usr/bin/env python3
"""Stage 0-only subscription harness adapter (CR-114 Story 2 / FR-328).

This module shells out to a pinned claudexor CLI. It is not wired into the
production Groq/Gemini path until Stories 3 and 5 enable it behind a switch.
Failed, invalid, timed-out, or exhausted calls return explicit review outcomes.
They never guess a bucket or a HARD/Skip judgment, and they never fall through
to a metered API.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

from pii_guard import redact_pii

# Implements FR-328 / AC-426: pin the tested claudexor that survived the
# readonly + schema smoke. Do not inherit Metis's older default pin.
CLAUDEXOR_PIN = "claudexor@3.12.1"
SCHEMA_VERSION = "stage0-subscription-v1"
TASKS = ("extraction", "evidence")
EXTRACTION_BUCKETS = ("required", "preferred", "responsibilities", "culture")
EVIDENCE_GATES = ("HARD", "NONE")
EVIDENCE_SOURCES = ("", "domain", "tool", "skill", "seniority", "people", "zero_to_one")
ENABLED_ENV = "APPLYR_STAGE0_SUBSCRIPTION_ADAPTER"
FORBIDDEN_TARGETS = {"groq", "gemini", "factory", "droid"}

RunTask = Literal["extraction", "evidence"]
RunOutcome = Literal["ok", "review", "cache_hit", "exhausted", "disabled"]

_EXTRACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["results"],
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["item_id", "bucket"],
                "properties": {
                    "item_id": {"type": "string", "minLength": 1},
                    "bucket": {"type": "string", "enum": list(EXTRACTION_BUCKETS)},
                },
            },
        }
    },
}

_EVIDENCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["results"],
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "item_id",
                    "gate",
                    "gap_source",
                    "evidence_level",
                    "confidence",
                    "reasoning",
                ],
                "properties": {
                    "item_id": {"type": "string", "minLength": 1},
                    "gate": {"type": "string", "enum": list(EVIDENCE_GATES)},
                    "gap_source": {"type": "string"},
                    "evidence_level": {"type": "integer", "minimum": 0, "maximum": 4},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "reasoning": {"type": "string", "minLength": 1},
                    "needs_user_confirmation": {"type": "boolean"},
                    "canonical_skill": {"type": "string"},
                    "skill_kind": {"type": "string"},
                },
            },
        }
    },
}


@dataclass(frozen=True)
class Stage0Item:
    item_id: str
    text: str


@dataclass
class AdapterConfig:
    enabled: bool = False
    profile: str = "cursor-default"
    harness: str = "cursor"
    timeout_seconds: int = 120
    max_calls: int = 8
    max_wall_seconds: int = 600
    cache_dir: Path = field(default_factory=lambda: Path("data") / "stage0_subscription_cache")
    workspace: Path | None = None


@dataclass
class AdapterResult:
    outcome: RunOutcome
    task: RunTask
    results: list[dict[str, Any]]
    missing_item_ids: list[str]
    reason: str | None
    calls: int
    elapsed_seconds: float
    subscription_minutes: float
    api_cents: int | None
    cache_key: str | None
    command: list[str]

    def to_telemetry(self) -> dict[str, Any]:
        """Return cost fields that must never be summed together."""
        return {
            "calls": self.calls,
            "elapsed_seconds": self.elapsed_seconds,
            "subscription_minutes": self.subscription_minutes,
            "api_cents": self.api_cents,
            "outcome": self.outcome,
            "reason": self.reason,
            "claudexor_pin": CLAUDEXOR_PIN,
            "schema_version": SCHEMA_VERSION,
        }


class AdapterBudget:
    """Per-batch call and wall-clock ceilings. Implements FR-328 / AC-426."""

    def __init__(self, config: AdapterConfig) -> None:
        self.max_calls = config.max_calls
        self.max_wall_seconds = config.max_wall_seconds
        self.calls = 0
        self.started = time.monotonic()

    def remaining(self) -> tuple[bool, str | None]:
        if self.calls >= self.max_calls:
            return False, "call ceiling exhausted"
        if time.monotonic() - self.started >= self.max_wall_seconds:
            return False, "wall-clock ceiling exhausted"
        return True, None


def adapter_enabled(config: AdapterConfig | None = None) -> bool:
    """Production switch. Off unless config or env explicitly enables it."""
    env = os.environ.get(ENABLED_ENV, "").strip().lower()
    if env in {"1", "true", "yes", "on"}:
        return True
    return bool(config and config.enabled)


def _forbidden_target(config: AdapterConfig) -> str | None:
    """Reject metered APIs and Factory. Implements FR-328 / AC-426."""
    for value in (config.harness, config.profile):
        lowered = (value or "").strip().lower()
        if lowered in FORBIDDEN_TARGETS or any(token in lowered for token in FORBIDDEN_TARGETS):
            return f"forbidden harness target: {value}"
    return None


def schema_for(task: RunTask) -> dict[str, Any]:
    if task not in TASKS:
        raise ValueError(f"unsupported Stage 0 adapter task: {task}")
    return json.loads(json.dumps(_EXTRACT_SCHEMA if task == "extraction" else _EVIDENCE_SCHEMA))


def cache_key(task: RunTask, items: list[Stage0Item], *, profile: str, extra: str = "") -> str:
    payload = {
        "task": task,
        "schema_version": SCHEMA_VERSION,
        "pin": CLAUDEXOR_PIN,
        "profile": profile,
        "extra": extra,
        "items": [{"item_id": item.item_id, "text": item.text} for item in items],
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return f"{task}-{digest}"


def _npx_cmd() -> str:
    found = shutil.which("npx.cmd" if os.name == "nt" else "npx") or shutil.which("npx")
    if not found:
        raise FileNotFoundError("npx is not available")
    return found


def build_command(
    prompt: str,
    schema_path: Path,
    config: AdapterConfig,
) -> list[str]:
    """Build the readonly schema-constrained claudexor argv. shell=False only."""
    return [
        _npx_cmd(),
        "-y",
        CLAUDEXOR_PIN,
        "agent",
        prompt,
        "--harness",
        config.harness,
        "--profile",
        config.profile,
        "--access",
        "readonly",
        "--workspace-kind",
        "directory",
        "--no-review",
        "--json",
        "--web",
        "off",
        "--output-schema",
        str(schema_path),
        "--max-seconds",
        str(config.timeout_seconds),
    ]


def _redact_items(items: list[Stage0Item]) -> list[Stage0Item]:
    return [Stage0Item(item.item_id, redact_pii(item.text)) for item in items]


def _prompt(task: RunTask, items: list[Stage0Item]) -> str:
    redacted = _redact_items(items)
    lines = [f"[{item.item_id}] {item.text}" for item in redacted]
    if task == "extraction":
        return (
            "Classify each Stage 0 job-description line into exactly one bucket. "
            "Return JSON {\"results\":[{\"item_id\":\"...\",\"bucket\":\"required|preferred|"
            "responsibilities|culture\"}]} with one result per listed item_id. "
            "Do not invent item_ids.\n\n" + "\n".join(lines)
        )
    return (
        "Judge each Stage 0 requirement against the supplied evidence excerpt. "
        "Return JSON {\"results\":[{\"item_id\":\"...\",\"gate\":\"HARD|NONE\","
        "\"gap_source\":\"\",\"evidence_level\":0,\"confidence\":\"high|medium|low\","
        "\"reasoning\":\"...\"}]} with one result per listed item_id. "
        "Do not invent item_ids. Do not skip an item.\n\n" + "\n".join(lines)
    )


def _load_json_object(text: str) -> dict[str, Any]:
    """Parse the first JSON object in possibly noisy harness stdout."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("empty harness stdout")
    decoder = json.JSONDecoder()
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            return payload
        raise ValueError("harness JSON must be an object")
    except json.JSONDecodeError:
        pass
    for index, char in enumerate(raw):
        if char != "{":
            continue
        try:
            payload, _end = decoder.raw_decode(raw[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError("harness JSON missing object")


def _results_payload(envelope: dict[str, Any]) -> dict[str, Any]:
    if "results" in envelope:
        return envelope
    primary = envelope.get("primaryOutput")
    if isinstance(primary, dict):
        text = primary.get("text")
        if isinstance(text, str) and text.strip():
            inner = json.loads(text)
            if isinstance(inner, dict):
                return inner
    answer = envelope.get("answer")
    if isinstance(answer, dict):
        return answer
    if isinstance(answer, str) and answer.strip():
        parsed = json.loads(answer)
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("harness JSON missing results")


def _route_violation(envelope: dict[str, Any], config: AdapterConfig) -> str | None:
    """Reject substituted harnesses or non-readonly access. Implements FR-328."""
    requested = (config.harness or "").strip().lower()
    telemetry = envelope.get("telemetry") if isinstance(envelope.get("telemetry"), dict) else {}
    attempts = telemetry.get("attempts") if isinstance(telemetry.get("attempts"), list) else []
    ran = [
        str(attempt.get("harness_id") or "").strip().lower()
        for attempt in attempts
        if isinstance(attempt, dict)
    ]
    ran = [name for name in ran if name]
    if requested and ran and any(name != requested for name in ran):
        return f"harness substituted: requested {requested}, ran {ran}"
    contract = envelope.get("contract") if isinstance(envelope.get("contract"), dict) else {}
    access = contract.get("access") if isinstance(contract.get("access"), dict) else {}
    effective = str(access.get("effective_profile") or "").strip().lower()
    if effective and effective != "readonly":
        return f"access was {effective}, expected readonly"
    return None


def _validate(task: RunTask, payload: dict[str, Any], items: list[Stage0Item]) -> tuple[list[dict[str, Any]], list[str]]:
    wanted = [item.item_id for item in items]
    wanted_set = set(wanted)
    rows = payload.get("results")
    if not isinstance(rows, list):
        raise ValueError("results must be an array")
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("result row must be an object")
        item_id = str(row.get("item_id") or "").strip()
        if item_id not in wanted_set:
            continue
        if task == "extraction":
            bucket = str(row.get("bucket") or "")
            if bucket not in EXTRACTION_BUCKETS:
                raise ValueError(f"invalid bucket for {item_id}")
            by_id[item_id] = {"item_id": item_id, "bucket": bucket}
            continue
        gate = str(row.get("gate") or "")
        if gate not in EVIDENCE_GATES:
            raise ValueError(f"invalid gate for {item_id}")
        source = str(row.get("gap_source") or "")
        if source not in EVIDENCE_SOURCES:
            raise ValueError(f"invalid gap_source for {item_id}")
        try:
            level = int(row.get("evidence_level"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid evidence_level for {item_id}") from exc
        if level not in range(5):
            raise ValueError(f"evidence_level out of range for {item_id}")
        confidence = str(row.get("confidence") or "").strip().lower()
        if confidence not in {"high", "medium", "low"}:
            raise ValueError(f"invalid confidence for {item_id}")
        reasoning = str(row.get("reasoning") or "").strip()
        if not reasoning:
            raise ValueError(f"missing reasoning for {item_id}")
        by_id[item_id] = {
            "item_id": item_id,
            "gate": gate,
            "gap_source": source,
            "evidence_level": level,
            "confidence": confidence,
            "reasoning": reasoning,
        }
    ordered = [by_id[item_id] for item_id in wanted if item_id in by_id]
    missing = [item_id for item_id in wanted if item_id not in by_id]
    return ordered, missing


def _load_cache(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_cache(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_stage0_subscription(
    task: RunTask,
    items: list[Stage0Item],
    *,
    config: AdapterConfig | None = None,
    budget: AdapterBudget | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> AdapterResult:
    """Run one bounded Stage 0 harness batch. Implements FR-328 / AC-426."""
    cfg = config or AdapterConfig()
    empty_command: list[str] = []
    if not items:
        return AdapterResult("review", task, [], [], "no items", 0, 0.0, 0.0, None, None, empty_command)
    if not adapter_enabled(cfg):
        return AdapterResult(
            "disabled", task, [], [item.item_id for item in items],
            "subscription adapter is off", 0, 0.0, 0.0, None, None, empty_command,
        )
    blocked = _forbidden_target(cfg)
    if blocked:
        return AdapterResult(
            "review", task, [], [item.item_id for item in items],
            blocked, 0, 0.0, 0.0, None, None, empty_command,
        )
    live_budget = budget or AdapterBudget(cfg)
    allowed, reason = live_budget.remaining()
    if not allowed:
        return AdapterResult(
            "exhausted", task, [], [item.item_id for item in items],
            reason, live_budget.calls, 0.0, 0.0, None, None, empty_command,
        )
    key = cache_key(task, items, profile=cfg.profile)
    cache_path = cfg.cache_dir / f"{key}.json"
    cached = _load_cache(cache_path)
    if cached and cached.get("results") and not cached.get("missing_item_ids"):
        return AdapterResult(
            "cache_hit", task, list(cached["results"]), list(cached.get("missing_item_ids") or []),
            None, 0, 0.0, 0.0, None, key, empty_command,
        )
    prompt = _prompt(task, items)
    execute = runner or subprocess.run
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="stage0-sub-") as tmp:
        schema_path = Path(tmp) / f"{task}.schema.json"
        schema_path.write_text(json.dumps(schema_for(task), indent=2) + "\n", encoding="utf-8")
        try:
            command = build_command(prompt, schema_path, cfg)
        except FileNotFoundError as exc:
            live_budget.calls += 1
            elapsed = time.monotonic() - started
            return AdapterResult(
                "review", task, [], [item.item_id for item in items],
                f"harness unavailable: {exc}", live_budget.calls, elapsed, elapsed / 60.0,
                None, key, empty_command,
            )
        if any(any(token in part.lower() for token in FORBIDDEN_TARGETS) for part in command):
            return AdapterResult(
                "review", task, [], [item.item_id for item in items],
                "forbidden harness target in command", live_budget.calls, 0.0, 0.0,
                None, key, command,
            )
        live_budget.calls += 1
        try:
            completed = execute(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=cfg.timeout_seconds,
                cwd=str(cfg.workspace or tmp),
                shell=False,
            )
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - started
            return AdapterResult(
                "review", task, [], [item.item_id for item in items],
                "harness timed out", live_budget.calls, elapsed, elapsed / 60.0, None, key, command,
            )
        except OSError as exc:
            elapsed = time.monotonic() - started
            return AdapterResult(
                "review", task, [], [item.item_id for item in items],
                f"harness unavailable: {exc}", live_budget.calls, elapsed, elapsed / 60.0, None, key, command,
            )
    elapsed = time.monotonic() - started
    minutes = elapsed / 60.0
    if completed.returncode != 0:
        return AdapterResult(
            "review", task, [], [item.item_id for item in items],
            f"harness exit {completed.returncode}", live_budget.calls, elapsed, minutes, None, key, command,
        )
    try:
        envelope = _load_json_object(completed.stdout)
        violation = _route_violation(envelope, cfg)
        if violation:
            return AdapterResult(
                "review", task, [], [item.item_id for item in items],
                violation, live_budget.calls, elapsed, minutes, None, key, command,
            )
        payload = _results_payload(envelope)
        results, missing = _validate(task, payload, items)
    except (ValueError, json.JSONDecodeError) as exc:
        return AdapterResult(
            "review", task, [], [item.item_id for item in items],
            f"invalid harness output: {exc}", live_budget.calls, elapsed, minutes, None, key, command,
        )
    if missing:
        return AdapterResult(
            "review", task, results, missing,
            "harness omitted item_ids", live_budget.calls, elapsed, minutes, None, key, command,
        )
    _write_cache(cache_path, {"results": results, "missing_item_ids": []})
    return AdapterResult(
        "ok", task, results, [], None, live_budget.calls, elapsed, minutes, None, key, command,
    )
