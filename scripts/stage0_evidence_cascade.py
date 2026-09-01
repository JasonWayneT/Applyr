#!/usr/bin/env python3
"""Batched, provider-configured Stage 0 evidence classification (CR-108)."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable


MAX_BATCH_ITEMS = 24
_SUPPORTED_PROVIDERS = ("groq", "gemini", "local")
_DEFAULT_MODELS = {
    "groq": "openai/gpt-oss-120b",
    "gemini": "gemini-3.5-flash-lite",
    "local": "qwen2.5:7b-instruct-q4_K_M",
}
_GATE_SOURCES = {"degree", "domain", "role_exclusion", "certification"}
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


class CascadeUnavailable(RuntimeError):
    """No configured Stage 0 provider returned a usable response."""


@dataclass(frozen=True)
class BatchItem:
    """One stable requirement item in a provider batch."""

    item_id: str
    bucket: str
    requirement: str
    evidence_excerpt: str = ""


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


def classify_requirements_batch(
    items: list[BatchItem],
    *,
    settings: dict[str, Any] | None = None,
    raw_response_callback: Callable[[str], None] | None = None,
    provider_event_callback: Callable[[str, str], None] | None = None,
) -> dict[str, dict[str, Any]]:
    """Classify all ambiguous items in one validated structured provider request."""
    if not items:
        return {}
    if len(items) > MAX_BATCH_ITEMS:
        raise CascadeValidationError(
            f"Stage 0 batch has {len(items)} items; maximum is {MAX_BATCH_ITEMS}"
        )
    from utils import call_llm, load_llm_settings

    active_settings = settings if settings is not None else load_llm_settings()
    policy = normalize_stage0_evidence_policy(active_settings)
    providers = policy["provider_order"]
    models = policy["models"]
    prompt = _build_batch_prompt(items)
    last_error: Exception | None = None
    for provider_index, provider in enumerate(providers):
        if provider_event_callback:
            provider_event_callback(provider, "call")
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
            )
        except Exception as exc:
            # A provider timeout or transport error is recoverable when the
            # policy includes another provider. Keep the failure for an
            # accurate final error if every configured provider fails.
            last_error = exc
            if provider_event_callback and provider_index + 1 < len(providers):
                provider_event_callback(provider, "fallback")
            continue
        if not raw:
            if provider_event_callback and provider_index + 1 < len(providers):
                provider_event_callback(provider, "fallback")
            continue
        if raw_response_callback:
            raw_response_callback(raw)
        try:
            return validate_batch_response(_parse_json_object(raw), items)
        except CascadeValidationError as exc:
            last_error = exc
            if provider_event_callback and provider_index + 1 < len(providers):
                provider_event_callback(provider, "fallback")
    if last_error:
        raise last_error
    raise CascadeUnavailable("No configured Stage 0 evidence provider returned a response")


def validate_batch_response(
    payload: dict[str, Any],
    items: list[BatchItem],
) -> dict[str, dict[str, Any]]:
    """Validate and normalize exactly one safe result for every batch item."""
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise CascadeValidationError("batch response must contain a results list")
    expected = {item.item_id: item for item in items}
    seen: set[str] = set()
    normalized: dict[str, dict[str, Any]] = {}
    for raw in payload["results"]:
        if not isinstance(raw, dict):
            raise CascadeValidationError("batch result must be an object")
        item_id = raw.get("item_id")
        if not isinstance(item_id, str) or item_id not in expected:
            raise CascadeValidationError(f"unknown batch item_id: {item_id!r}")
        if item_id in seen:
            raise CascadeValidationError(f"duplicate batch item_id: {item_id!r}")
        seen.add(item_id)
        item = expected[item_id]
        normalized[item_id] = _normalize_result(raw, item)
    missing = set(expected) - seen
    if missing:
        raise CascadeValidationError(f"missing batch item_ids: {sorted(missing)!r}")
    return normalized


def _normalize_result(raw: dict[str, Any], item: BatchItem) -> dict[str, Any]:
    """Normalize one provider result while holding unsafe HARD decisions."""
    gate = str(raw.get("gate") or "").strip().upper()
    source = str(raw.get("gap_source") or "").strip().lower()
    if source in {"none", "null"}:
        source = ""
    if gate not in {"HARD", "NONE"}:
        raise CascadeValidationError(f"invalid gate for {item.item_id}: {gate!r}")
    if source not in _GATE_SOURCES and source != "":
        raise CascadeValidationError(f"invalid gap_source for {item.item_id}: {source!r}")
    try:
        evidence_level = int(raw.get("evidence_level"))
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
    }


def _reasoning_grounded_in_item(item: str, reasoning: str) -> bool:
    """Require meaningful lexical overlap before accepting a HARD result."""
    item_tokens = _tokens(item) - _FILLER_WORDS
    reasoning_tokens = _tokens(reasoning) - _FILLER_WORDS
    return not item_tokens or not reasoning_tokens or bool(item_tokens & reasoning_tokens)


def _build_batch_prompt(items: list[BatchItem]) -> str:
    """Build a redaction-safe batch prompt from requirement and retrieved evidence text."""
    lines = ["Classify every item exactly once. Return JSON only.", ""]
    for item in items:
        lines.append(f"[{item.item_id}] bucket={item.bucket}")
        lines.append(f"requirement={item.requirement}")
        if item.evidence_excerpt:
            lines.append(f"evidence={item.evidence_excerpt}")
        lines.append("")
    return "\n".join(lines)


def _parse_json_object(raw: str) -> dict[str, Any]:
    """Parse a JSON object from a provider response without accepting a JSON array."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    candidate = match.group(0) if match else raw
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
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


_SYSTEM_PROMPT = """You classify job requirements against supplied candidate evidence.
Return {"results":[...]} with one result per item_id.
Use gate=HARD only for an unambiguous required degree, domain, role-exclusion,
or certification requirement that is the only path. Tools never use HARD.
Preferred items never use HARD. Evidence level is 0 through 4. Confidence is
high, medium, or low. Reasoning must cite the requirement's own vocabulary.
Do not invent facts or use evidence outside the supplied excerpts."""


def _tokens(value: str) -> set[str]:
    """Tokenize text for the conservative HARD grounding check."""
    return set(re.findall(r"[a-z0-9]+", value.lower()))
