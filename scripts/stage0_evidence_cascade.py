#!/usr/bin/env python3
"""Batched, provider-configured Stage 0 evidence classification (CR-108)."""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


from stage0_classifier_contract import (
    EVIDENCE_SYSTEM,
    evidence_user_prompt,
)

MAX_BATCH_ITEMS = 24
# Live Agy evidence omits item_ids on Groq-sized batches. Archive smoke that
# passed used chunks of 3 (`scripts/smoke_stage0_agy_archive.py`).
SUBSCRIPTION_EVIDENCE_CHUNK = 3

# CR-108 Epic 7.5 (2026-09-09): proactive batch sizing. When the estimated
# output tokens for a batch exceed _SAFE_OUTPUT_TOKENS, the batch is split in
# half before sending. This prevents truncation on providers (notably Groq)
# that have an output token limit. The estimate is based on the prompt size,
# which naturally accounts for evidence excerpt length, not just item count.
_SAFE_OUTPUT_TOKENS = 6000  # 25% margin under the 8192 Groq max_tokens
_OUTPUT_TOKEN_RATIO = 0.35  # conservative: output tokens per prompt char
_MIN_SPLIT_BATCH = 3  # don't split batches too small to benefit
_SUPPORTED_PROVIDERS = ("groq", "gemini", "local")
# CR-114 Story 5: do not load the Stage 0 subscription adapter module here.
# Uncertain evidence stays on the existing provider chain until matcher + replay pass.
_DEFAULT_MODELS = {
    "groq": "openai/gpt-oss-120b",
    "gemini": "gemini-3.5-flash-lite",
    "local": "qwen2.5:7b-instruct-q4_K_M",
}
_GATE_SOURCES = {"degree", "domain", "role_exclusion", "certification"}
CASCADE_IMPORT_NAME = "stage0_cascade_import.json"
CASCADE_IMPORT_TEMPLATE_NAME = "stage0_cascade_import.template.json"
CASCADE_IMPORT_CONSUMED_NAME = "stage0_cascade_import.consumed.json"
CASCADE_IMPORT_SCHEMA_VERSION = 1
_IMPORT_ALLOWED_KEYS = {
    "schema_version",
    "import_source",
    "submission_slug",
    "jd_sha256",
    "batch_sha256",
    "created_at",
    "expected_item_ids",
    "results",
}
_IMPORT_FORBIDDEN_KEYS = {
    "workflow_status",
    "status",
    "receipts",
    "receipt_id",
    "stages",
    "api_cents",
    "cost",
    "cost_class",
    "cost_known",
    "cost_confidence",
    "verification_passed",
    "rubric_score",
    "model_call_occurred",
    "active_stage",
    "issued_by",
    "pause_kind",
    "workflow_state",
    "mechanically_verified",
}
_FILLER_WORDS = {
    "work",
    "experience",
    "role",
    "candidate",
    "requirement",
    "requirements",
    "position",
    "job",
    "team",
    "years",
    "skills",
}


class CascadeValidationError(ValueError):
    """A provider response cannot be trusted as a complete batch."""


class CascadeReviewNeeded(CascadeValidationError):
    """Subscription adapter failed closed and the batch must pause for review."""


class CascadeUnavailable(RuntimeError):
    """No configured Stage 0 provider returned a usable response."""


@dataclass(frozen=True)
class BatchItem:
    """One stable requirement item in a provider batch."""

    item_id: str
    bucket: str
    requirement: str
    evidence_excerpt: str = ""


def _subscription_evidence_enabled() -> bool:
    """Return True only when the CR-114 adapter switch is on. Implements FR-328."""
    from stage0_subscription_adapter import AdapterConfig, adapter_enabled
    return adapter_enabled(AdapterConfig())


def _classify_requirements_subscription(
    items: list[BatchItem],
    *,
    raw_response_callback: Callable[[str], None] | None = None,
    provider_event_callback: Callable[[str, str], None] | None = None,
) -> dict[str, dict[str, Any]]:
    """Classify uncertain evidence through the bounded adapter. Implements FR-328.

    Never calls Groq or Gemini. Invalid, partial, exhausted, or substituted
    harness output raises CascadeReviewNeeded so Stage 0 can pause for review.
    Successful rows still pass through validate_batch_response, so unsafe HARD
    cannot skip. One omitted-ID retry on the missing items only, matching the
    Groq cascade's partial-acceptance behavior. Never pass an AgySession here:
    the worker is one-shot per chunk. Sessions must not be reused across jobs.
    """
    from stage0_subscription_adapter import (
        AdapterBudget,
        AdapterConfig,
        AdapterResult,
        Stage0Item,
        run_stage0_subscription,
    )

    config = AdapterConfig(enabled=True)
    budget = AdapterBudget(config)

    def _run(batch: list[BatchItem]) -> AdapterResult:
        payload = [
            Stage0Item(
                item.item_id,
                bucket=item.bucket,
                requirement=item.requirement,
                evidence_excerpt=item.evidence_excerpt,
            )
            for item in batch
        ]
        if provider_event_callback:
            provider_event_callback("subscription", "call")
        return run_stage0_subscription(
            "evidence", payload, config=config, budget=budget
        )

    def _emit(result: AdapterResult) -> None:
        if not raw_response_callback:
            return
        raw_response_callback(
            json.dumps(
                {
                    "outcome": result.outcome,
                    "results": result.results,
                    "missing_item_ids": result.missing_item_ids,
                    "reason": result.reason,
                    "subscription_minutes": result.subscription_minutes,
                    "api_cents": result.api_cents,
                }
            )
        )

    result = _run(items)
    _emit(result)
    kept: list[dict[str, Any]] = list(result.results)
    got = {str(row.get("item_id")) for row in kept if isinstance(row, dict)}
    missing_items = [item for item in items if item.item_id not in got]
    if missing_items and result.outcome in {"ok", "cache_hit", "review"}:
        retry = _run(missing_items)
        _emit(retry)
        kept.extend(retry.results)
        got = {str(row.get("item_id")) for row in kept if isinstance(row, dict)}
        missing_items = [item for item in items if item.item_id not in got]
        if not missing_items:
            return validate_batch_response({"results": kept}, items, exact_ids=True)
        raise CascadeReviewNeeded(
            retry.reason or result.reason or "harness omitted item_ids"
        )
    if result.outcome not in {"ok", "cache_hit"} or missing_items:
        raise CascadeReviewNeeded(
            result.reason or "subscription adapter required review"
        )
    return validate_batch_response({"results": kept}, items, exact_ids=True)


def configured_provider_order(settings: dict[str, Any]) -> list[str]:
    """Resolve explicit Stage 0 provider policy without implicit Local fallback."""
    config = settings.get("stage0_evidence_classification") or {}
    local_only = config.get("local_only") is True or os.environ.get(
        "LOCAL_ONLY_MODE", ""
    ).lower() in {"1", "true", "yes", "on"}
    if local_only:
        return ["local"]
    configured = config.get("provider_order")
    if not isinstance(configured, list) or not configured:
        configured = ["groq", "gemini"]
    return _clean_provider_order(configured)


def normalize_stage0_evidence_policy(settings: dict[str, Any]) -> dict[str, Any]:
    """Normalize Stage 0 provider order, models, and local-only behavior."""
    config = settings.get("stage0_evidence_classification") or {}
    providers = configured_provider_order(settings)
    configured_models = config.get("models") if isinstance(config.get("models"), dict) else {}
    models = {
        provider: str(configured_models.get(provider) or _DEFAULT_MODELS[provider]).strip()
        or _DEFAULT_MODELS[provider]
        for provider in providers
    }
    return {
        "provider_order": providers,
        "models": models,
        "local_only": providers == ["local"],
    }


def cascade_batch_sha256(items: list[BatchItem]) -> str:
    """Stable identity of the exact requirement batch Stage 0 is classifying."""
    payload = [
        {
            "item_id": item.item_id,
            "bucket": item.bucket,
            "requirement": item.requirement,
        }
        for item in items
    ]
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def render_cascade_import_template(
    *,
    submission_slug: str,
    jd_sha256: str,
    items: list[BatchItem],
) -> dict[str, Any]:
    """Bound import skeleton. No private biography. Results must be filled in."""
    item_ids = [item.item_id for item in items]
    return {
        "schema_version": CASCADE_IMPORT_SCHEMA_VERSION,
        "import_source": "manual",
        "submission_slug": submission_slug,
        "jd_sha256": jd_sha256,
        "batch_sha256": cascade_batch_sha256(items),
        "created_at": "audit-only-not-identity",
        "expected_item_ids": item_ids,
        "results": [
            {
                "item_id": item.item_id,
                # CR-112 (Defect B, exact-text binding): echoed back so
                # try_load_cascade_import can verify whoever answered this
                # import was looking at the real requirement text, not text
                # they rewrote or a different item entirely.
                "requirement": item.requirement,
                "bucket": item.bucket,
                "gate": "NONE",
                "evidence_level": 4,
                "confidence": "high",
                "reasoning": f"Replace this placeholder for {item.item_id}.",
            }
            for item in items
        ],
    }


def write_cascade_import_template(
    folder: str | Path,
    *,
    submission_slug: str,
    jd_sha256: str,
    items: list[BatchItem],
) -> Path:
    """Write a non-authoritative template next to the live import name."""
    path = Path(folder) / CASCADE_IMPORT_TEMPLATE_NAME
    payload = render_cascade_import_template(
        submission_slug=submission_slug,
        jd_sha256=jd_sha256,
        items=items,
    )
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def consume_cascade_import(folder: str | Path) -> str | None:
    """Rename a successfully used live import. Deterministic; no second live file."""
    live = Path(folder) / CASCADE_IMPORT_NAME
    if not live.is_file():
        return None
    consumed = Path(folder) / CASCADE_IMPORT_CONSUMED_NAME
    if consumed.exists():
        consumed.unlink()
    live.replace(consumed)
    return CASCADE_IMPORT_CONSUMED_NAME


def try_load_cascade_import(
    folder: str | Path,
    items: list[BatchItem],
    *,
    submission_slug: str,
    jd_sha256: str,
) -> dict[str, Any] | None:
    """Load a bound manual cascade import. None if the live file is absent.

    Present-but-invalid raises CascadeValidationError. Does not write state.
    """
    path = Path(folder) / CASCADE_IMPORT_NAME
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except UnicodeDecodeError as exc:
        raise CascadeValidationError(f"invalid cascade import encoding: {exc}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise CascadeValidationError(f"invalid cascade import: {exc}") from exc
    if not isinstance(payload, dict):
        raise CascadeValidationError("cascade import must be a JSON object")
    extra = set(payload) - _IMPORT_ALLOWED_KEYS
    forbidden = set(payload) & _IMPORT_FORBIDDEN_KEYS
    if forbidden:
        raise CascadeValidationError(
            f"cascade import cannot set workflow or cost fields: {sorted(forbidden)}"
        )
    if extra:
        raise CascadeValidationError(
            f"cascade import has unsupported keys: {sorted(extra)}"
        )
    if payload.get("schema_version") != CASCADE_IMPORT_SCHEMA_VERSION:
        raise CascadeValidationError(
            f"cascade import schema_version must be {CASCADE_IMPORT_SCHEMA_VERSION}"
        )
    if payload.get("import_source") != "manual":
        raise CascadeValidationError("cascade import_source must be manual")
    if str(payload.get("submission_slug") or "") != str(submission_slug):
        raise CascadeValidationError("cascade import submission_slug does not match this folder")
    if str(payload.get("jd_sha256") or "") != str(jd_sha256):
        raise CascadeValidationError("cascade import jd_sha256 does not match this JD")
    expected_batch = cascade_batch_sha256(items)
    if str(payload.get("batch_sha256") or "") != expected_batch:
        raise CascadeValidationError("cascade import batch_sha256 does not match this requirement set")
    if "created_at" not in payload:
        raise CascadeValidationError("cascade import created_at is required for audit")
    if not isinstance(payload.get("created_at"), str) or not payload["created_at"].strip():
        raise CascadeValidationError("cascade import created_at must be a non-empty string")
    declared_ids = payload.get("expected_item_ids")
    actual_ids = [item.item_id for item in items]
    if declared_ids is None:
        raise CascadeValidationError("cascade import expected_item_ids is required")
    if not isinstance(declared_ids, list) or list(declared_ids) != actual_ids:
        raise CascadeValidationError("cascade import expected_item_ids do not match this batch")
    # CR-112 (Defect B, exact-text binding): a submitted import's echoed
    # requirement/bucket must match the real item text/bucket exactly --
    # otherwise a classifier could answer about text it rewrote and nothing
    # would catch it. Checked before validate_batch_response(), which does
    # not look at these two fields at all.
    expected_by_id = {item.item_id: item for item in items}
    raw_results = payload.get("results")
    if isinstance(raw_results, list):
        for raw_result in raw_results:
            if not isinstance(raw_result, dict):
                continue
            raw_item_id = raw_result.get("item_id")
            expected_item = expected_by_id.get(raw_item_id) if isinstance(raw_item_id, str) else None
            if expected_item is None:
                continue
            if str(raw_result.get("requirement") or "") != expected_item.requirement:
                raise CascadeValidationError(
                    f"cascade import echoed requirement text for {raw_item_id!r} "
                    "does not match this batch's real item text"
                )
            if str(raw_result.get("bucket") or "") != expected_item.bucket:
                raise CascadeValidationError(
                    f"cascade import echoed bucket for {raw_item_id!r} does not "
                    "match this batch's real item bucket"
                )
    results = validate_batch_response(payload, items, exact_ids=True)
    assert isinstance(results, dict)
    import_sha256 = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return {
        "results": results,
        "import_source": "manual",
        "import_sha256": import_sha256,
        "schema_version": CASCADE_IMPORT_SCHEMA_VERSION,
        "model_call_occurred": False,
        "cost_applicable": False,
        "validation": "pass",
    }


def classify_requirements_batch(
    items: list[BatchItem],
    *,
    settings: dict[str, Any] | None = None,
    raw_response_callback: Callable[[str], None] | None = None,
    provider_event_callback: Callable[[str, str], None] | None = None,
    folder: str | Path | None = None,
    cost_ledger: Any | None = None,
    allow_import: bool = True,
) -> dict[str, dict[str, Any]]:
    """Classify all ambiguous items in one validated structured provider request.

    2026-09-01 Improvement #4: batches exceeding MAX_BATCH_ITEMS are now
    automatically split into chunks of <= MAX_BATCH_ITEMS, classified
    independently, and merged. This replaces the previous CascadeValidationError
    that discarded all results when a batch was too large.

    CR-108 Epic 7.5 (2026-09-09): two robustness improvements for provider
    truncation:
    - Proactive split: if estimated output tokens exceed _SAFE_OUTPUT_TOKENS,
      the batch is split in half and each half is classified recursively.
      This prevents truncation before it happens by accounting for evidence
      excerpt length, not just item count.
    - Partial-result acceptance: when a provider returns a truncated response
      that the JSON repair can only partially recover, the recovered items are
      accepted and only the missing items are retried (same provider first,
      then fallback). This avoids re-sending the full batch to the fallback
      provider and wasting the work the first provider already did.
    """
    if not items:
        return {}
    if _subscription_evidence_enabled():
        if len(items) > SUBSCRIPTION_EVIDENCE_CHUNK:
            merged: dict[str, dict[str, Any]] = {}
            for start in range(0, len(items), SUBSCRIPTION_EVIDENCE_CHUNK):
                chunk = items[start : start + SUBSCRIPTION_EVIDENCE_CHUNK]
                merged.update(
                    classify_requirements_batch(
                        chunk,
                        settings=settings,
                        raw_response_callback=raw_response_callback,
                        provider_event_callback=provider_event_callback,
                        folder=folder,
                        cost_ledger=cost_ledger,
                        allow_import=False,
                    )
                )
            return merged
        return _classify_requirements_subscription(
            items,
            raw_response_callback=raw_response_callback,
            provider_event_callback=provider_event_callback,
        )
    # Manual import is validated only by the Stage 0 builder, never here.
    # Improvement #4: automatic chunking for batches > MAX_BATCH_ITEMS.
    if len(items) > MAX_BATCH_ITEMS:
        return _classify_in_chunks(
            items,
            settings=settings,
            raw_response_callback=raw_response_callback,
            provider_event_callback=provider_event_callback,
            folder=folder,
            cost_ledger=cost_ledger,
        )
    # CR-108: proactive split based on estimated output size. Accounts for
    # long evidence excerpts that would exceed the output token budget even
    # when the item count is under MAX_BATCH_ITEMS. Recursive: halves that
    # are still too big split again. Don't split batches too small to benefit.
    if len(items) >= _MIN_SPLIT_BATCH and _estimate_output_tokens(items) > _SAFE_OUTPUT_TOKENS:
        mid = len(items) // 2
        left = classify_requirements_batch(
            items[:mid],
            settings=settings,
            raw_response_callback=raw_response_callback,
            provider_event_callback=provider_event_callback,
            folder=folder,
            cost_ledger=cost_ledger,
            allow_import=False,
        )
        right = classify_requirements_batch(
            items[mid:],
            settings=settings,
            raw_response_callback=raw_response_callback,
            provider_event_callback=provider_event_callback,
            folder=folder,
            cost_ledger=cost_ledger,
            allow_import=False,
        )
        return {**left, **right}
    from utils import call_llm, load_llm_settings
    from cost_eligibility import (
        CostPauseError,
        authorize_provider_chain,
        budget_ledger_from_settings,
        estimate_prompt_tokens,
        raise_if_pause,
    )

    active_settings = settings if settings is not None else load_llm_settings()
    policy = normalize_stage0_evidence_policy(active_settings)
    models = policy["models"]
    last_error: Exception | None = None
    ledger = cost_ledger if cost_ledger is not None else budget_ledger_from_settings(active_settings)
    prompt_for_auth = _build_batch_prompt(items)
    tokens_est = estimate_prompt_tokens(_SYSTEM_PROMPT, prompt_for_auth)
    auth = authorize_provider_chain(
        policy["provider_order"],
        active_settings,
        ledger=ledger,
        estimated_tokens=tokens_est,
    )
    raise_if_pause(auth, estimated_tokens=tokens_est)
    providers = auth.providers
    # CR-108: track accumulated results and remaining items across providers.
    # When a provider returns a partial response (truncation + JSON repair),
    # the recovered items are kept and only the missing items are retried.
    merged: dict[str, dict[str, Any]] = {}
    remaining = list(items)
    for provider_index, provider in enumerate(providers):
        if not remaining:
            break
        prompt = _build_batch_prompt(remaining)
        try:
            raw = call_llm(
                _SYSTEM_PROMPT,
                prompt,
                model=models.get(provider) or _DEFAULT_MODELS[provider],
                temperature=0.0,
                response_mime_type="application/json",
                response_schema={"type": "object"},
                provider_override=[provider],
                request_timeout=120,
                cost_settings=active_settings,
                cost_ledger=ledger,
            )
        except CostPauseError:
            raise
        except Exception as exc:
            last_error = exc
            if provider_event_callback and provider_index + 1 < len(providers):
                provider_event_callback(provider, "fallback")
            continue
        if provider_event_callback:
            provider_event_callback(provider, "call")
        if not raw:
            if provider_event_callback and provider_index + 1 < len(providers):
                provider_event_callback(provider, "fallback")
            continue
        if raw_response_callback:
            raw_response_callback(raw)
        try:
            parsed = _parse_json_object(raw)
            partial_results, missing_ids = validate_batch_response(
                parsed, remaining, partial=True
            )
            merged.update(partial_results)
            remaining = [item for item in remaining if item.item_id in missing_ids]
            if not remaining:
                return merged
            # Only retry with the same provider when we actually recovered
            # some items (a truncation with partial success). An empty or
            # wholly-invalid response is a complete failure — fall back to
            # the next provider rather than retrying the same one.
            if partial_results:
                if provider_event_callback:
                    provider_event_callback(provider, "call")
                retry_prompt = _build_batch_prompt(remaining)
                # CR-108 bug fix (2026-09-09): a transport error here (timeout,
                # connection reset, rate limit) must fall back to the next
                # provider like every other call_llm() invocation in this loop,
                # not crash out of classify_requirements_batch entirely.
                # Previously only CascadeValidationError from parsing/validating
                # the retry response was caught -- a raw call_llm() exception
                # propagated uncaught, skipping the configured fallback
                # provider (e.g. Gemini) even though it was available.
                try:
                    retry_raw = call_llm(
                        _SYSTEM_PROMPT,
                        retry_prompt,
                        model=models.get(provider) or _DEFAULT_MODELS[provider],
                        temperature=0.0,
                        response_mime_type="application/json",
                        response_schema={"type": "object"},
                        provider_override=[provider],
                        request_timeout=120,
                        cost_settings=active_settings,
                        cost_ledger=ledger,
                    )
                except CostPauseError:
                    raise
                except Exception as exc:
                    last_error = exc
                    retry_raw = None
                if retry_raw:
                    if raw_response_callback:
                        raw_response_callback(retry_raw)
                    retry_parsed = _parse_json_object(retry_raw)
                    retry_results, retry_missing = validate_batch_response(
                        retry_parsed, remaining, partial=True
                    )
                    merged.update(retry_results)
                    remaining = [item for item in remaining if item.item_id in retry_missing]
            if not remaining:
                return merged
            if provider_event_callback and provider_index + 1 < len(providers):
                provider_event_callback(provider, "fallback")
        except CascadeValidationError as exc:
            last_error = exc
            if provider_event_callback and provider_index + 1 < len(providers):
                provider_event_callback(provider, "fallback")
    if remaining:
        if last_error:
            raise last_error
        raise CascadeValidationError(
            f"missing batch item_ids after all providers: {sorted(i.item_id for i in remaining)!r}"
        )
    return merged


def _classify_in_chunks(
    items: list[BatchItem],
    *,
    settings: dict[str, Any] | None = None,
    raw_response_callback: Callable[[str], None] | None = None,
    provider_event_callback: Callable[[str, str], None] | None = None,
    folder: str | Path | None = None,
    cost_ledger: Any | None = None,
) -> dict[str, dict[str, Any]]:
    """Split a large batch into MAX_BATCH_ITEMS-sized chunks, classify each,
    and merge results. If a chunk fails, its items are re-attempted individually
    (partial acceptance) so one bad chunk doesn't discard valid results from
    other chunks."""
    merged: dict[str, dict[str, Any]] = {}
    for i in range(0, len(items), MAX_BATCH_ITEMS):
        chunk = items[i : i + MAX_BATCH_ITEMS]
        try:
            chunk_results = classify_requirements_batch(
                chunk,
                settings=settings,
                raw_response_callback=raw_response_callback,
                provider_event_callback=provider_event_callback,
                folder=folder,
                cost_ledger=cost_ledger,
                allow_import=False,
            )
            merged.update(chunk_results)
        except (CascadeValidationError, CascadeUnavailable):
            # Partial acceptance: try each item in the failed chunk individually
            # so valid items from other chunks are not discarded.
            for single in chunk:
                try:
                    single_results = classify_requirements_batch(
                        [single],
                        settings=settings,
                        raw_response_callback=raw_response_callback,
                        provider_event_callback=provider_event_callback,
                        folder=folder,
                        cost_ledger=cost_ledger,
                        allow_import=False,
                    )
                    merged.update(single_results)
                except (CascadeValidationError, CascadeUnavailable):
                    # This single item truly failed -- skip it rather than
                    # abort the whole batch. The caller's missing-item check
                    # will surface it.
                    continue
    return merged


def _resolve_item_id(raw_id: str, expected: dict[str, BatchItem]) -> str | None:
    """Resolve a provider-returned item_id against the expected id set.

    CR-108 cascade testing (2026-09-01): confirmed live on a real archived JD
    that Gemini can drop the "bucket:ordinal:" prefix from a compound
    make_item_key() id (e.g. "required:0:bf418179f1c24783") and return only
    the trailing hash ("bf418179f1c24783") -- plausibly because its own
    response already carries "bucket" as a separate field, so the model
    treats the prefix as redundant and normalizes it away. That's a display
    difference, not an ambiguity: the hash suffix alone is exactly as unique
    as the full id within one company's batch (same digest algorithm, same
    input), so accept it when -- and only when -- it identifies exactly one
    expected item. A suffix shared by two expected items is never silently
    guessed; the caller's "unknown batch item_id" error still fires for that.
    """
    if raw_id in expected:
        return raw_id
    # Try progressively shorter suffixes of the expected id against the raw_id.
    # Providers can drop the "bucket:" prefix (returning "ordinal:hash") or
    # even drop everything but the hash. Each shorter suffix is only accepted
    # when it identifies exactly one expected item.
    max_parts = max((full_id.count(":") for full_id in expected), default=0)
    for drop in range(1, max_parts + 1):
        suffix_matches = [
            full_id
            for full_id in expected
            if ":".join(full_id.split(":")[drop:]) == raw_id
        ]
        if len(suffix_matches) == 1:
            return suffix_matches[0]
    # CR-108 (2026-09-09): some providers return just the ordinal ("0", "1")
    # extracted from the "bucket:ordinal:hash" id. Match it against the
    # ordinal position (second segment) when exactly one expected id has
    # that ordinal.
    ordinal_matches = [
        full_id
        for full_id in expected
        if len(full_id.split(":")) >= 2 and full_id.split(":")[1] == raw_id
    ]
    if len(ordinal_matches) == 1:
        return ordinal_matches[0]
    # CR-108 (2026-09-09) / CR-112 Story 1.1: providers sometimes mangle the
    # id format (replace ":" with "-", abbreviate "required" to "req") while
    # still echoing the 16-char hash tail. Accept that hash tail when -- and
    # only when -- it identifies exactly one expected item.
    # Invented sequential ids such as "req-001" have a 3-character numeric
    # tail, not a hash. Mapping those onto list position (the 2026-09-09
    # dirty patch) attached HARD/NONE to the wrong requirement when the
    # model's numbering and content disagreed. CR-112 rejects them so the
    # batch retries or falls back instead of guessing.
    raw_segments = re.split(r"[:-]", raw_id)
    raw_tail = raw_segments[-1] if raw_segments else ""
    if raw_tail and len(raw_tail) >= 8:
        hash_matches = [
            full_id
            for full_id in expected
            if full_id.split(":")[-1] == raw_tail
        ]
        if len(hash_matches) == 1:
            return hash_matches[0]
    return None


def validate_batch_response(
    payload: dict[str, Any],
    items: list[BatchItem],
    *,
    partial: bool = False,
    exact_ids: bool = False,
) -> dict[str, dict[str, Any]] | tuple[dict[str, dict[str, Any]], set[str]]:
    """Validate and normalize exactly one safe result for every batch item.

    When partial=False (default), raises CascadeValidationError if any item is
    missing. When partial=True, returns (normalized_dict, missing_set) so the
    caller can accept recovered results and retry only the missing items.
    Other validation errors (invalid gate, unknown item_id, ungrounded HARD)
    always raise regardless of the partial flag.
    exact_ids=True rejects suffix/ordinal/hash-tail aliases (manual import).
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise CascadeValidationError("batch response must contain a results list")
    expected = {item.item_id: item for item in items}
    seen: set[str] = set()
    normalized: dict[str, dict[str, Any]] = {}
    for raw in payload["results"]:
        if not isinstance(raw, dict):
            raise CascadeValidationError("batch result must be an object")
        raw_id = raw.get("item_id")
        if exact_ids:
            item_id = raw_id if isinstance(raw_id, str) and raw_id in expected else None
        else:
            item_id = _resolve_item_id(raw_id, expected) if isinstance(raw_id, str) else None
        if item_id is None:
            raise CascadeValidationError(f"unknown batch item_id: {raw_id!r}")
        if item_id in seen:
            raise CascadeValidationError(f"duplicate batch item_id: {raw_id!r}")
        seen.add(item_id)
        item = expected[item_id]
        normalized[item_id] = _normalize_result(raw, item)
    missing = set(expected) - seen
    if missing:
        if partial:
            return normalized, missing
        raise CascadeValidationError(f"missing batch item_ids: {sorted(missing)!r}")
    if partial:
        return normalized, set()
    return normalized


def _normalize_result(raw: dict[str, Any], item: BatchItem) -> dict[str, Any]:
    """Normalize one provider result while holding unsafe HARD decisions."""
    gate = str(raw.get("gate") or "").strip().upper()
    # CR-108 cascade testing (2026-09-01): Gemini returned "SOFT" live on a
    # real archived JD instead of the prompted HARD/NONE binary -- plausibly
    # picked up from this codebase's own ambient gap_class vocabulary
    # (HARD/SOFT appears throughout build_stage0_fit_gate.py) rather than
    # this prompt's own instructions. "SOFT" only ever means "not a hard
    # gate" here, exactly like NONE -- the actual gap_class the caller sees
    # is still computed from evidence_level below, so normalizing the label
    # doesn't change what gets decided, only whether a harmless synonym
    # discards an otherwise well-reasoned, safe response.
    if gate == "SOFT":
        gate = "NONE"
    # CR-108 cascade testing (2026-09-01): Gemini can also omit the "gate"
    # field entirely, returning only evidence_level/level + reasoning. An
    # absent gate is "not a hard gate" -- the actual gap_class is computed
    # from evidence_level below, so defaulting to NONE is safe.
    if gate == "":
        gate = "NONE"
    source = str(raw.get("gap_source") or "").strip().lower()
    if source in {"none", "null"}:
        source = ""
    if gate not in {"HARD", "NONE"}:
        raise CascadeValidationError(f"invalid gate for {item.item_id}: {gate!r}")
    if source not in _GATE_SOURCES and source != "":
        raise CascadeValidationError(f"invalid gap_source for {item.item_id}: {source!r}")
    # CR-108 cascade testing (2026-09-01): same real response also used a
    # field named "level" instead of the prompted "evidence_level". Accept
    # either name -- this is a label difference, not a value one.
    level_value = raw.get("evidence_level")
    if level_value is None:
        level_value = raw.get("level")
    try:
        evidence_level = int(level_value)
    except (TypeError, ValueError) as exc:
        raise CascadeValidationError(f"invalid evidence_level for {item.item_id}") from exc
    if evidence_level not in range(5):
        raise CascadeValidationError(
            f"evidence_level out of range for {item.item_id}: {evidence_level}"
        )
    confidence = str(raw.get("confidence") or "").strip().lower()
    if confidence not in {"high", "medium", "low"}:
        raise CascadeValidationError(f"invalid confidence for {item.item_id}: {confidence!r}")
    reasoning = str(raw.get("reasoning") or "").strip()
    if not reasoning:
        raise CascadeValidationError(f"missing reasoning for {item.item_id}")

    # CR-108 Epic 7.2 (2026-09-08): honor the Layer C model-flagged
    # confirmation fields. A model that detects a named tool the conservative
    # extractor missed may set needs_user_confirmation=true with a
    # canonical_skill and skill_kind so the fit gate can create the same
    # durable pending item the deterministic path would have created. Fail
    # closed: a flag with no skill key must never silently finalize as a
    # permanent anonymous gap -- reject the batch so the provider chain
    # falls back and a later provider gets the chance to name the entity.
    flag_value = raw.get("needs_user_confirmation")
    needs_user_confirmation = (
        flag_value is True or str(flag_value).strip().lower() in {"true", "1", "yes"}
    )
    skill_kind = str(raw.get("skill_kind") or "").strip().lower()
    if skill_kind not in {"tool", "skill", "domain", "role", "none", ""}:
        raise CascadeValidationError(f"invalid skill_kind for {item.item_id}: {skill_kind!r}")
    if skill_kind == "none":
        skill_kind = ""
    canonical_skill = str(raw.get("canonical_skill") or "").strip().lower()
    if needs_user_confirmation and not canonical_skill:
        raise CascadeValidationError(
            f"needs_user_confirmation=true without canonical_skill for {item.item_id}"
        )

    unsafe_hard = (
        gate == "HARD"
        and (
            confidence != "high"
            or not _reasoning_grounded_in_item(item.requirement, reasoning)
        )
    )
    if item.bucket != "required":
        gate = "NONE"
        source = ""
    if unsafe_hard:
        gate = "NONE"
        source = ""
        confidence = "low"
        reasoning = f"Held for review: proposed HARD was not sufficiently grounded. {reasoning}"
    gap_class = "HARD" if gate == "HARD" else "SOFT" if evidence_level <= 2 else None
    return {
        "item": item.requirement,
        "anchor": reasoning,
        "gap": gap_class is not None,
        "gap_class": gap_class,
        "gap_source": source or None,
        "domain_soft": source == "domain" and gate == "NONE" and evidence_level <= 2,
        "evidence_level": evidence_level,
        "confidence": confidence,
        "gate": gate,
        "needs_user_confirmation": needs_user_confirmation,
        "canonical_skill": canonical_skill or None,
        "skill_kind": skill_kind or None,
    }


def _reasoning_grounded_in_item(item: str, reasoning: str) -> bool:
    """Require meaningful lexical overlap before accepting a HARD result."""
    item_tokens = _tokens(item) - _FILLER_WORDS
    reasoning_tokens = _tokens(reasoning) - _FILLER_WORDS
    return not item_tokens or not reasoning_tokens or bool(item_tokens & reasoning_tokens)


def _estimate_output_tokens(items: list[BatchItem]) -> int:
    """Estimate output tokens for a batch based on prompt size.

    Empirically derived from live CR-108 golden testing: a 5969-char prompt
    (21 items with evidence excerpts) produced ~1600 output tokens, a ratio
    of 0.27 tokens/char. The conservative 0.35 ratio accounts for verbose
    reasoning and longer evidence excerpts in production JDs.
    """
    prompt = _build_batch_prompt(items)
    return int(len(prompt) * _OUTPUT_TOKEN_RATIO)


def _build_batch_prompt(items: list[BatchItem]) -> str:
    """Build the Applyr evidence user packet, including retrieved few-shot examples."""
    few_shot_block = ""
    try:
        from fit_rubric_examples import retrieve_examples, format_evidence_examples_for_prompt
        query = items[0].requirement if items else ""
        examples = retrieve_examples(query, None, k=2)
        few_shot_block = format_evidence_examples_for_prompt(examples)
    except Exception:
        pass
    return evidence_user_prompt(
        [
            {
                "item_id": item.item_id,
                "bucket": item.bucket,
                "requirement": item.requirement,
                "evidence_excerpt": item.evidence_excerpt,
            }
            for item in items
        ],
        few_shot=few_shot_block,
    )


def _repair_truncated_json(raw: str) -> dict[str, Any] | None:
    """Attempt to recover a results dict from a truncated or malformed JSON response.

    LLM providers (notably Groq's gpt-oss-120b) sometimes produce valid JSON
    for the first N items but truncate or malform the tail of a large batch.
    This function extracts individual result objects via a balanced-brace scan
    and returns a synthetic {"results": [...]} dict if at least one valid object
    is found. Returns None if no objects can be recovered.
    """
    # Find the start of the "results" array, then scan for individual
    # result objects within it. This avoids the problem where the outer
    # JSON object is truncated and its closing brace is missing.
    results_idx = raw.find('"results"')
    if results_idx == -1:
        # No "results" key — try scanning the whole string for item_id objects
        scan_start = 0
    else:
        # Skip past "results": [
        bracket_idx = raw.find('[', results_idx)
        scan_start = bracket_idx + 1 if bracket_idx != -1 else results_idx

    objects: list[dict[str, Any]] = []
    i = scan_start
    while i < len(raw):
        brace = raw.find("{", i)
        if brace == -1:
            break
        depth = 0
        j = brace
        in_string = False
        escape = False
        while j < len(raw):
            ch = raw[j]
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = not in_string
            elif not in_string:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = raw[brace : j + 1]
                        try:
                            obj = json.loads(candidate)
                            if isinstance(obj, dict) and "item_id" in obj:
                                objects.append(obj)
                        except json.JSONDecodeError:
                            pass
                        break
            j += 1
        i = j + 1 if j < len(raw) else len(raw)
    if not objects:
        return None
    return {"results": objects}


def _parse_json_object(raw: str) -> dict[str, Any]:
    """Parse a JSON object from a provider response without accepting a JSON array.

    Includes a repair step for truncated/malformed responses: if the standard
    JSON parse fails, attempt to recover individual result objects via a
    balanced-brace scan. This handles the common failure mode where a provider
    (notably Groq) produces valid JSON for most items but truncates the tail.
    """
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    candidate = match.group(0) if match else raw
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        # CR-108: attempt repair before giving up
        repaired = _repair_truncated_json(raw)
        if repaired is not None:
            return repaired
        raise CascadeValidationError(f"invalid JSON batch response: {exc}") from exc
    if not isinstance(value, dict):
        raise CascadeValidationError("batch response must be a JSON object")
    return value


def _clean_provider_order(values: list[Any]) -> list[str]:
    """Filter and deduplicate provider names while preserving configured order."""
    result: list[str] = []
    for value in values:
        provider = str(value).strip().lower()
        if provider in _SUPPORTED_PROVIDERS and provider not in result:
            result.append(provider)
    if not result:
        raise ValueError("Stage 0 provider_order must contain groq, gemini, or local")
    return result


_SYSTEM_PROMPT = EVIDENCE_SYSTEM


def _tokens(value: str) -> set[str]:
    """Tokenize text for the conservative HARD grounding check."""
    return set(re.findall(r"[a-z0-9]+", value.lower()))
