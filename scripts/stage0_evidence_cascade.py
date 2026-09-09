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
    """Classify all ambiguous items in one validated structured provider request.

    2026-09-01 Improvement #4: batches exceeding MAX_BATCH_ITEMS are now
    automatically split into chunks of <= MAX_BATCH_ITEMS, classified
    independently, and merged. This replaces the previous CascadeValidationError
    that discarded all results when a batch was too large.
    """
    if not items:
        return {}
    # Improvement #4: automatic chunking for batches > MAX_BATCH_ITEMS.
    if len(items) > MAX_BATCH_ITEMS:
        return _classify_in_chunks(
            items,
            settings=settings,
            raw_response_callback=raw_response_callback,
            provider_event_callback=provider_event_callback,
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


def _classify_in_chunks(
    items: list[BatchItem],
    *,
    settings: dict[str, Any] | None = None,
    raw_response_callback: Callable[[str], None] | None = None,
    provider_event_callback: Callable[[str, str], None] | None = None,
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
    return None


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
        raw_id = raw.get("item_id")
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
        raise CascadeValidationError(f"missing batch item_ids: {sorted(missing)!r}")
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
    """Build a redaction-safe batch prompt from requirement and retrieved evidence text.

    2026-09-01 Improvement #1: now includes k=2 few-shot examples retrieved from
    data/fit_rubric_golden_set.json (via fit_rubric_examples.retrieve_examples)
    before the items, aligning the batch path with the single-item path's
    few-shot support. Falls back to no examples if the golden set is missing
    (same skip-not-fail posture as the single-item path).
    """
    lines = ["Classify every item exactly once. Return JSON only.", ""]

    # Improvement #1: retrieve k=2 few-shot examples for the batch.
    few_shot_block = ""
    try:
        from fit_rubric_examples import retrieve_examples, format_evidence_examples_for_prompt
        # Use the first item's requirement as the query for retrieval ranking.
        query = items[0].requirement if items else ""
        examples = retrieve_examples(query, None, k=2)
        few_shot_block = format_evidence_examples_for_prompt(examples)
    except Exception:
        pass
    if few_shot_block:
        lines.append(few_shot_block)
        lines.append("")

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

EVIDENCE SCALE (0-4) -- rate how much of the requirement the candidate's documented \
experience actually satisfies:
0 = No documented evidence. Nothing in the candidate profile addresses this.
1 = Adjacent evidence. Candidate did work sharing the underlying capability, not the requested work itself.
2 = Partial direct evidence. Candidate did meaningful parts of it, but scope/tooling/context/ownership differs.
3 = Direct evidence. Candidate clearly did substantially equivalent work, comparable scope.
4 = Strong direct evidence. Substantially equivalent work with comparable-or-greater ownership, scope, or outcome.

OR-ALTERNATIVE LINES -- when a line offers multiple alternatives joined by "or", \
rate evidence_level against whichever single alternative the candidate matches BEST, \
not the worst. The line is satisfied if ANY listed alternative is well-documented.

FORBIDDEN AS EVIDENCE (score 0 if this is the only basis): a title alone, an employer \
name alone, company size, a merely-adjacent industry, an implied department interaction, \
a tool the candidate "probably" touched, seniority implying a capability, or trainability. \
Potential is not evidence of demonstrated experience.

HARD GATES -- gate="HARD" ends scoring for this line outright (disqualifying). \
A line from the PREFERRED bucket NEVER gates. Gating is possible ONLY for a REQUIRED-bucket \
line, and only in these four categories:
- degree: a required advanced degree (Master's/MBA/PhD/JD/MD) with NO Bachelor's alternative.
- domain: a required regulated/specialized domain paired with its OWN years-of-experience threshold.
- role_exclusion: a role category incompatible with the candidate's background (people management, \
AI/ML ownership, revenue/billing ownership, title above Senior IC, or building from nothing).
- certification: a required professional certification/license (PMP, CPA, PE, RN license, etc.).
Tools never gate. Bare years-of-experience never gates. If gate="HARD", gap_source MUST be \
exactly one of "degree", "domain", "role_exclusion", or "certification".

CONFIDENCE -- "high" when both line and evidence are unambiguous; "medium" when real \
interpretation was needed; "low" when the JD line is vague or evidence is thin.

Reasoning must cite the requirement's own vocabulary and the specific evidence that \
supports your rating. Do not invent facts or use evidence outside the supplied excerpts."""


def _tokens(value: str) -> set[str]:
    """Tokenize text for the conservative HARD grounding check."""
    return set(re.findall(r"[a-z0-9]+", value.lower()))
