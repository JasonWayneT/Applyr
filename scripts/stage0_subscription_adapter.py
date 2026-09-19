#!/usr/bin/env python3
"""Stage 0-only subscription transport (CR-114 Story 2 / FR-328).

Applyr classifier rules live in stage0_classifier_contract. The default tool
is native Agy print mode. Failed, invalid, timed-out, or exhausted calls
return explicit review. They never guess a bucket or a HARD/Skip judgment,
and they never fall through to a metered API.
"""

from __future__ import annotations

import hashlib
import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

from pii_guard import redact_pii
from stage0_classifier_contract import (
    EVIDENCE_GATES,
    EVIDENCE_SOURCES,
    EXTRACTION_BUCKETS,
    SCHEMA_VERSION,
    combined_classifier_prompt,
    evidence_user_prompt,
    extraction_user_prompt,
    schema_for as contract_schema_for,
)

# Default tool is native Agy. Claudexor remains available only when harness is
# not agy. Implements FR-328 / AC-426.
CLAUDEXOR_PIN = "claudexor@3.12.1"
AGY_TRANSPORT = "agy-print"
AGY_MODEL_DEFAULT = "gemini-3.8-flash-medium"
AGY_EFFORT_DEFAULT = "medium"
TASKS = ("extraction", "evidence")
ENABLED_ENV = "APPLYR_STAGE0_SUBSCRIPTION_ADAPTER"
FORBIDDEN_TARGETS = {"groq", "gemini", "factory", "droid"}

RunTask = Literal["extraction", "evidence"]
RunOutcome = Literal["ok", "review", "cache_hit", "exhausted", "disabled"]

@dataclass(frozen=True)
class Stage0Item:
    item_id: str
    text: str = ""
    bucket: str = ""
    requirement: str = ""
    evidence_excerpt: str = ""


@dataclass
class AdapterConfig:
    enabled: bool = False
    profile: str = "agy-default"
    harness: str = "agy"
    model: str = AGY_MODEL_DEFAULT
    effort: str = AGY_EFFORT_DEFAULT
    timeout_seconds: int = 120
    max_calls: int = 8
    max_wall_seconds: int = 600
    cache_dir: Path = field(default_factory=lambda: Path("data") / "stage0_subscription_cache")
    workspace: Path | None = None
    quota_reader: Callable[[], dict[str, Any]] | None = None


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
            "transport": AGY_TRANSPORT if (self.command and "agy" in " ".join(self.command).lower()) else CLAUDEXOR_PIN,
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
    """Return the Applyr classifier schema. Transport-agnostic."""
    if task not in TASKS:
        raise ValueError(f"unsupported Stage 0 adapter task: {task}")
    return contract_schema_for(task)


def cache_key(task: RunTask, items: list[Stage0Item], *, profile: str, extra: str = "") -> str:
    payload = {
        "task": task,
        "schema_version": SCHEMA_VERSION,
        "pin": AGY_TRANSPORT if profile.startswith("agy") else CLAUDEXOR_PIN,
        "profile": profile,
        "extra": extra,
        "items": [
            {
                "item_id": item.item_id,
                "text": item.text,
                "bucket": item.bucket,
                "requirement": item.requirement,
                "evidence_excerpt": item.evidence_excerpt,
            }
            for item in items
        ],
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return f"{task}-{digest}"


def _npx_cmd() -> str:
    found = shutil.which("npx.cmd" if os.name == "nt" else "npx") or shutil.which("npx")
    if not found:
        raise FileNotFoundError("npx is not available")
    return found


def _agy_cmd() -> str:
    """Resolve the native Agy CLI. Implements FR-328."""
    found = shutil.which("agy.exe" if os.name == "nt" else "agy") or shutil.which("agy")
    if not found:
        raise FileNotFoundError("agy is not available")
    return found


def _readline_timeout(pipe: Any, timeout_seconds: float) -> str:
    """Read one stdout line with a timeout. Windows pipes do not support select."""
    lines: queue.Queue[str] = queue.Queue()

    def _reader() -> None:
        lines.put(pipe.readline())

    worker = threading.Thread(target=_reader, daemon=True)
    worker.start()
    try:
        return lines.get(timeout=timeout_seconds)
    except queue.Empty as exc:
        raise subprocess.TimeoutExpired("agy", timeout_seconds) from exc


class AgySession:
    """One long-lived Agy stdin session for a single classifier schema. Implements FR-328."""

    def __init__(self, task: RunTask, config: AdapterConfig) -> None:
        self.task = task
        self.config = config
        self._tmp = tempfile.TemporaryDirectory(prefix=f"stage0-agy-{task}-")
        self.workspace = Path(self._tmp.name)
        schema_path = self.workspace / f"{task}.schema.json"
        schema_path.write_text(json.dumps(schema_for(task), indent=2) + "\n", encoding="utf-8")
        self.command = [
            _agy_cmd(),
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--json-schema",
            str(schema_path),
            "--sandbox",
            "--disable-slash-commands",
            "--new-project",
            "--model",
            config.model,
            "--effort",
            config.effort,
            "--print-timeout",
            f"{config.timeout_seconds}s",
        ]
        self.proc = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(self.workspace),
            shell=False,
            bufsize=1,
        )
        self._stderr: list[str] = []
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        self._wait_init()

    def _drain_stderr(self) -> None:
        """Keep stderr from filling the pipe and blocking the session."""
        if self.proc.stderr is None:
            return
        for line in self.proc.stderr:
            snippet = " ".join(line.split())[:240]
            if snippet:
                self._stderr.append(snippet)

    def _wait_init(self) -> None:
        """Block until Agy emits the stream-json init event."""
        if self.proc.stdout is None:
            raise FileNotFoundError("agy stdout is not available")
        raw = _readline_timeout(self.proc.stdout, float(self.config.timeout_seconds))
        if not raw:
            raise FileNotFoundError("agy session produced no init event")
        event = json.loads(raw)
        if event.get("event") != "init":
            raise ValueError("agy session missing init event")

    def classify(self, prompt: str) -> dict[str, Any]:
        """Send one leftover packet and return the result envelope."""
        if self.proc.stdin is None or self.proc.stdout is None:
            raise FileNotFoundError("agy session is closed")
        if self.proc.poll() is not None:
            raise FileNotFoundError("agy session exited")
        payload = {"event": "user", "message": {"content": prompt}}
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()
        deadline = time.monotonic() + self.config.timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(self.command, self.config.timeout_seconds)
            raw = _readline_timeout(self.proc.stdout, remaining)
            if not raw:
                raise ValueError("agy session closed stdout")
            event = json.loads(raw)
            if event.get("event") != "result":
                continue
            result = event.get("result")
            if not isinstance(result, dict):
                raise ValueError("agy session result missing object")
            return result

    def close(self) -> None:
        """End the stdin session and drop the temp workspace."""
        try:
            if self.proc.stdin is not None:
                self.proc.stdin.close()
            self.proc.wait(timeout=15)
        except Exception:
            self.proc.kill()
        self._tmp.cleanup()


def build_command(
    prompt_path: Path,
    schema_path: Path,
    config: AdapterConfig,
) -> list[str]:
    """Build a schema-constrained argv. shell=False only. Implements FR-328.

    One-shot Agy puts the Applyr packet on --print. Batches should reuse
    AgySession stdin so startup is paid once. Other harness ids still use
    pinned claudexor.
    """
    if (config.harness or "").strip().lower() == "agy":
        prompt = prompt_path.read_text(encoding="utf-8")
        return [
            _agy_cmd(),
            "--output-format",
            "json",
            "--json-schema",
            str(schema_path),
            "--sandbox",
            "--disable-slash-commands",
            "--new-project",
            "--model",
            config.model,
            "--effort",
            config.effort,
            "--print-timeout",
            f"{config.timeout_seconds}s",
            "--print",
            prompt,
        ]
    return [
        _npx_cmd(),
        "-y",
        CLAUDEXOR_PIN,
        "agent",
        "--prompt-file",
        str(prompt_path),
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
    """Redact PII in every Applyr-owned text field before a tool sees it."""
    return [
        Stage0Item(
            item.item_id,
            redact_pii(item.text),
            redact_pii(item.bucket),
            redact_pii(item.requirement),
            redact_pii(item.evidence_excerpt),
        )
        for item in items
    ]


def _prompt(task: RunTask, items: list[Stage0Item]) -> str:
    """Render the Applyr classifier packet for a single-prompt CLI transport."""
    redacted = _redact_items(items)
    if task == "extraction":
        user = extraction_user_prompt(
            [(item.item_id, item.text or item.requirement) for item in redacted]
        )
        return combined_classifier_prompt("extraction", user)
    user = evidence_user_prompt(
        [
            {
                "item_id": item.item_id,
                "bucket": item.bucket,
                "requirement": item.requirement or item.text,
                "evidence_excerpt": item.evidence_excerpt,
            }
            for item in redacted
        ]
    )
    return combined_classifier_prompt("evidence", user)


def _harness_exit_reason(completed: subprocess.CompletedProcess[str]) -> str:
    """Summarize a non-zero harness exit without keeping a raw log. Implements FR-328."""
    snippet = redact_pii((completed.stderr or completed.stdout or "").strip())
    snippet = " ".join(snippet.split())[:240]
    if snippet:
        return f"harness exit {completed.returncode}: {snippet}"
    return f"harness exit {completed.returncode}"


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


def _denied_actions(envelope: dict[str, Any]) -> list[str]:
    """Return tool names the harness tried and could not run."""
    raw = envelope.get("denied_actions")
    names: list[str] = []
    if not isinstance(raw, list):
        return names
    for item in raw:
        if isinstance(item, dict):
            name = str(item.get("action") or item.get("display_name") or "").strip()
        else:
            name = str(item).strip()
        if name:
            names.append(name)
    return names


def _results_payload(envelope: dict[str, Any]) -> dict[str, Any]:
    denied = _denied_actions(envelope)
    if denied:
        raise ValueError("harness used tools: " + ", ".join(denied[:8]))
    if "results" in envelope:
        return envelope
    for key in ("structured_output", "result", "response", "output", "data", "answer"):
        value = envelope.get(key)
        if isinstance(value, dict) and "results" in value:
            return value
        if isinstance(value, str) and value.strip():
            parsed = json.loads(value)
            if isinstance(parsed, dict) and "results" in parsed:
                return parsed
    primary = envelope.get("primaryOutput")
    if isinstance(primary, dict):
        text = primary.get("text")
        if isinstance(text, str) and text.strip():
            inner = json.loads(text)
            if isinstance(inner, dict):
                return inner
    raise ValueError("harness JSON missing results")


def _route_violation(envelope: dict[str, Any], config: AdapterConfig) -> str | None:
    """Reject substituted or writable claudexor runs. Agy print mode skips this."""
    if (config.harness or "").strip().lower() == "agy":
        return None
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


def _record_stage0_quota(
    cfg: AdapterConfig,
    *,
    task: RunTask,
    cache_status: str,
    wall_seconds: float,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    reported_usage: dict[str, Any] | None = None,
) -> None:
    if cfg.quota_reader is None:
        try:
            from agy_quota_tracker import receipts_enabled
        except ImportError:
            return
        if not receipts_enabled():
            return
    try:
        from agy_quota_tracker import (
            ACTIVE_FOLDER_ENV,
            ACTIVE_SLUG_ENV,
            DEFAULT_LEDGER,
            build_call_receipt,
            emit_call_receipt,
            receipts_enabled,
        )
    except ImportError:
        return
    folder = os.environ.get(ACTIVE_FOLDER_ENV) or None
    slug = os.environ.get(ACTIVE_SLUG_ENV) or (Path(folder).name if folder else "")
    receipt = build_call_receipt(
        stage="stage0",
        slug=slug,
        task=task,
        model=cfg.model,
        effort=cfg.effort,
        cache_status=cache_status,
        prompt_estimate=None,
        reported_usage=reported_usage,
        before=before,
        after=after,
        wall_seconds=wall_seconds,
    )
    write_ledger = receipts_enabled() and cfg.quota_reader is None
    emit_call_receipt(
        receipt,
        folder=folder,
        ledger=DEFAULT_LEDGER if write_ledger else None,
    )


def _quota_snapshot(cfg: AdapterConfig) -> dict[str, Any] | None:
    if cfg.quota_reader is None:
        try:
            from agy_quota_tracker import receipts_enabled, snapshot_quota
        except ImportError:
            return None
        if not receipts_enabled():
            return None
        return snapshot_quota()
    try:
        from agy_quota_tracker import snapshot_quota
    except ImportError:
        return None
    return snapshot_quota(cfg.quota_reader)


def _kept_from_cache(
    cached: dict[str, Any] | None,
    items: list[Stage0Item],
) -> list[dict[str, Any]]:
    wanted = {item.item_id for item in items}
    kept: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in (cached or {}).get("results") or []:
        if not isinstance(row, dict):
            continue
        item_id = str(row.get("item_id") or "")
        if item_id in wanted and item_id not in seen:
            kept.append(row)
            seen.add(item_id)
    return kept


def _pending_items(items: list[Stage0Item], kept: list[dict[str, Any]]) -> list[Stage0Item]:
    have = {str(row.get("item_id") or "") for row in kept}
    return [item for item in items if item.item_id not in have]


def _merge_item_results(
    items: list[Stage0Item],
    *batches: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    wanted = [item.item_id for item in items]
    wanted_set = set(wanted)
    by_id: dict[str, dict[str, Any]] = {}
    for batch in batches:
        for row in batch:
            item_id = str(row.get("item_id") or "")
            if item_id in wanted_set:
                by_id[item_id] = row
    ordered = [by_id[item_id] for item_id in wanted if item_id in by_id]
    missing = [item_id for item_id in wanted if item_id not in by_id]
    return ordered, missing


def _call_harness(
    task: RunTask,
    batch: list[Stage0Item],
    cfg: AdapterConfig,
    live_budget: AdapterBudget,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None,
    session: AgySession | None,
    key: str,
    empty_command: list[str],
) -> AdapterResult:
    """One harness attempt for `batch`. Does not read or write cache."""
    prompt = _prompt(task, batch)
    started = time.monotonic()
    if session is not None:
        live_budget.calls += 1
        try:
            envelope = session.classify(prompt)
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - started
            return AdapterResult(
                "review", task, [], [item.item_id for item in batch],
                "harness timed out", live_budget.calls, elapsed, elapsed / 60.0, None, key,
                session.command,
            )
        except (OSError, FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            elapsed = time.monotonic() - started
            return AdapterResult(
                "review", task, [], [item.item_id for item in batch],
                f"invalid harness output: {exc}", live_budget.calls, elapsed, elapsed / 60.0,
                None, key, session.command,
            )
        elapsed = time.monotonic() - started
        minutes = elapsed / 60.0
        try:
            payload = _results_payload(envelope)
            results, missing = _validate(task, payload, batch)
        except (ValueError, json.JSONDecodeError) as exc:
            return AdapterResult(
                "review", task, [], [item.item_id for item in batch],
                f"invalid harness output: {exc}", live_budget.calls, elapsed, minutes,
                None, key, session.command,
            )
        if missing:
            return AdapterResult(
                "review", task, results, missing,
                "harness omitted item_ids", live_budget.calls, elapsed, minutes,
                None, key, session.command,
            )
        return AdapterResult(
            "ok", task, results, [], None, live_budget.calls, elapsed, minutes, None, key,
            session.command,
        )
    execute = runner or subprocess.run
    with tempfile.TemporaryDirectory(prefix="stage0-sub-") as tmp:
        schema_path = Path(tmp) / f"{task}.schema.json"
        schema_path.write_text(json.dumps(schema_for(task), indent=2) + "\n", encoding="utf-8")
        prompt_path = Path(tmp) / "prompt.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        try:
            command = build_command(prompt_path, schema_path, cfg)
        except FileNotFoundError as exc:
            live_budget.calls += 1
            elapsed = time.monotonic() - started
            return AdapterResult(
                "review", task, [], [item.item_id for item in batch],
                f"harness unavailable: {exc}", live_budget.calls, elapsed, elapsed / 60.0,
                None, key, empty_command,
            )
        if (cfg.harness or "").strip().lower() != "agy" and any(
            any(token in part.lower() for token in FORBIDDEN_TARGETS) for part in command
        ):
            return AdapterResult(
                "review", task, [], [item.item_id for item in batch],
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
                "review", task, [], [item.item_id for item in batch],
                "harness timed out", live_budget.calls, elapsed, elapsed / 60.0, None, key, command,
            )
        except OSError as extra:
            elapsed = time.monotonic() - started
            return AdapterResult(
                "review", task, [], [item.item_id for item in batch],
                f"harness unavailable: {extra}", live_budget.calls, elapsed, elapsed / 60.0,
                None, key, command,
            )
    elapsed = time.monotonic() - started
    minutes = elapsed / 60.0
    if completed.returncode != 0:
        return AdapterResult(
            "review", task, [], [item.item_id for item in batch],
            _harness_exit_reason(completed), live_budget.calls, elapsed, minutes, None, key, command,
        )
    try:
        envelope = _load_json_object(completed.stdout)
        violation = _route_violation(envelope, cfg)
        if violation:
            return AdapterResult(
                "review", task, [], [item.item_id for item in batch],
                violation, live_budget.calls, elapsed, minutes, None, key, command,
            )
        payload = _results_payload(envelope)
        results, missing = _validate(task, payload, batch)
    except (ValueError, json.JSONDecodeError) as exc:
        return AdapterResult(
            "review", task, [], [item.item_id for item in batch],
            f"invalid harness output: {exc}", live_budget.calls, elapsed, minutes, None, key, command,
        )
    if missing:
        return AdapterResult(
            "review", task, results, missing,
            "harness omitted item_ids", live_budget.calls, elapsed, minutes, None, key, command,
        )
    return AdapterResult(
        "ok", task, results, [], None, live_budget.calls, elapsed, minutes, None, key, command,
    )


def run_stage0_subscription(
    task: RunTask,
    items: list[Stage0Item],
    *,
    config: AdapterConfig | None = None,
    budget: AdapterBudget | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    session: AgySession | None = None,
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
    key = cache_key(
        task,
        items,
        profile=cfg.profile,
        extra=f"{cfg.model}:{cfg.effort}",
    )
    cache_path = cfg.cache_dir / f"{key}.json"
    cached = _load_cache(cache_path)
    kept = _kept_from_cache(cached, items)
    pending = _pending_items(items, kept)
    if not pending:
        missing = {
            "ok": False,
            "missing": True,
            "reason": "cache_hit_no_agy_call",
            "quota": None,
        }
        _record_stage0_quota(
            cfg,
            task=task,
            cache_status="hit",
            wall_seconds=0.0,
            before=missing,
            after=missing,
        )
        return AdapterResult(
            "cache_hit", task, kept, [], None, 0, 0.0, 0.0, None, key, empty_command,
        )

    started = time.monotonic()
    before = _quota_snapshot(cfg)
    last = _call_harness(
        task, pending, cfg, live_budget, runner, session, key, empty_command,
    )
    after = _quota_snapshot(cfg)
    _record_stage0_quota(
        cfg,
        task=task,
        cache_status="fresh",
        wall_seconds=time.monotonic() - started,
        before=before,
        after=after,
    )
    parsed = last.reason in {None, 'harness omitted item_ids'}
    merged, still_missing = _merge_item_results(items, kept, last.results if parsed else [])
    _write_cache(cache_path, {'results': merged, 'missing_item_ids': still_missing})
    if parsed and still_missing and last.results:
        retry_allowed, _retry_reason = live_budget.remaining()
        if retry_allowed:
            retry_batch = [item for item in items if item.item_id in still_missing]
            retry_started = time.monotonic()
            retry_before = _quota_snapshot(cfg)
            last = _call_harness(
                task, retry_batch, cfg, live_budget, runner, session, key, empty_command,
            )
            _record_stage0_quota(
                cfg,
                task=task,
                cache_status="retry",
                wall_seconds=time.monotonic() - retry_started,
                before=retry_before,
                after=_quota_snapshot(cfg),
            )
            parsed = last.reason in {None, 'harness omitted item_ids'}
            merged, still_missing = _merge_item_results(
                items, merged, last.results if parsed else [],
            )
            _write_cache(cache_path, {'results': merged, 'missing_item_ids': still_missing})

    elapsed = time.monotonic() - started
    minutes = elapsed / 60.0
    if not parsed:
        return AdapterResult(
            last.outcome, task, merged, still_missing or [item.item_id for item in pending],
            last.reason, live_budget.calls, elapsed, minutes, None, key, last.command,
        )
    if still_missing:
        return AdapterResult(
            'review', task, merged, still_missing,
            last.reason or 'harness omitted item_ids',
            live_budget.calls, elapsed, minutes, None, key, last.command,
        )
    return AdapterResult(
        'ok', task, merged, [], None, live_budget.calls, elapsed, minutes, None, key, last.command,
    )
