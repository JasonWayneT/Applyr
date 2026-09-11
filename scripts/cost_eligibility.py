#!/usr/bin/env python3
"""CR-112 Epic 7 — model-cost eligibility and telemetry.

Runtime classes: offline | manual_paste | free_only | paid_with_budget.
Missing or unprovable class is unknown. Unknown is not callable.

free_only requires an adapter assertion that the configured call cannot
incur a charge. A provider name or advertised free tier is not enough.
Groq and Gemini stay unknown until that assertion exists.

This module does not call providers and does not write workflow receipts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

COST_CLASSES = ("offline", "manual_paste", "free_only", "paid_with_budget")
DEFAULT_COST_CLASS = {
    "local": "offline",
    "gemini": "unknown",
    "claude": "unknown",
    "perplexity": "unknown",
    "groq": "unknown",
}
_PAUSE_MESSAGE = (
    "No cost-eligible LLM provider. Do not call. Pause and use the existing "
    "authoring_prompt.md paste path."
)
LAST_RECEIPT: dict[str, Any] | None = None


def set_last_receipt(row: dict[str, Any]) -> dict[str, Any]:
    """Remember the most recent cost receipt for callers and tests."""
    global LAST_RECEIPT
    LAST_RECEIPT = dict(row)
    return LAST_RECEIPT


class CostPauseError(RuntimeError):
    """No eligible provider remains. Callers must not invoke a model."""

    def __init__(self, message: str = _PAUSE_MESSAGE, *, receipt: dict[str, Any] | None = None):
        super().__init__(message)
        self.receipt = receipt or unknown_refusal_receipt()


@dataclass
class BudgetLedger:
    """Remaining paid budget for one run and optional batch cap."""

    remaining_cents: int
    batch_remaining_cents: int | None = None

    def would_exceed(self, estimated_cents: int) -> bool:
        if estimated_cents > self.remaining_cents:
            return True
        if self.batch_remaining_cents is not None and estimated_cents > self.batch_remaining_cents:
            return True
        return False

    def debit(self, cents: int) -> None:
        self.remaining_cents -= cents
        if self.batch_remaining_cents is not None:
            self.batch_remaining_cents -= cents


@dataclass
class ProviderCost:
    """Resolved eligibility for one provider name."""

    provider: str
    cost_class: str
    eligible: bool
    reason: str
    cost_known: bool
    estimated_cents: int | None = None
    authorization_mode: str = "unknown"


@dataclass
class Authorization:
    """Filtered call chain plus refusals. Never includes unknown."""

    providers: list[str] = field(default_factory=list)
    decisions: list[ProviderCost] = field(default_factory=list)
    seen_free_only: bool = False

    @property
    def pause(self) -> bool:
        return not self.providers


def estimate_prompt_tokens(system_prompt: str, user_prompt: str) -> int:
    """Byte/4 estimate. Same method as the CR-112 eval harness."""
    raw = f"{system_prompt}\n{user_prompt}".encode("utf-8")
    return len(raw) // 4


def declared_cost_class(provider: str, settings: dict[str, Any] | None) -> str:
    """Return the declared class, or unknown. Provider name is not a class."""
    settings = settings or {}
    declared = (settings.get("costClasses") or {}).get(provider)
    if declared in COST_CLASSES:
        return str(declared)
    return DEFAULT_COST_CLASS.get(provider, "unknown")


_TEST_ZERO_CHARGE: set[str] = set()


def set_test_zero_charge_providers(providers: Iterable[str] | None) -> None:
    """Process-local test stub. Never read from llm_settings / SQLite."""
    global _TEST_ZERO_CHARGE
    _TEST_ZERO_CHARGE = {str(item) for item in (providers or [])}


def adapter_can_assert_zero_charge(provider: str, settings: dict[str, Any] | None) -> bool:
    """True only when the configured call cannot incur a charge.

    Cloud keys do not prove billing is disabled. Production groq/gemini/
    claude/perplexity return False. Tests may stub via
    set_test_zero_charge_providers, not a settings key.
    """
    del settings
    if provider == "local":
        return True
    return provider in _TEST_ZERO_CHARGE


def _allowlist(settings: dict[str, Any] | None) -> set[str]:
    settings = settings or {}
    raw = settings.get("paidProviderAllowlist") or []
    if not isinstance(raw, list):
        return set()
    return {str(item) for item in raw}


def _int_setting(settings: dict[str, Any] | None, key: str, default: int | None = None) -> int | None:
    settings = settings or {}
    raw = settings.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def budget_ledger_from_settings(settings: dict[str, Any] | None) -> BudgetLedger:
    """Paid budget. Unset or 0 means paid is ineligible."""
    remaining = _int_setting(settings, "paidBudgetCents", 0) or 0
    batch = _int_setting(settings, "paidBatchBudgetCents", None)
    return BudgetLedger(remaining_cents=max(0, remaining), batch_remaining_cents=batch)


def estimated_call_cents(
    provider: str,
    settings: dict[str, Any] | None,
    *,
    estimated_tokens: int,
) -> int | None:
    """Known paid estimate, or None when the call could exceed an unknown amount."""
    settings = settings or {}
    per_call = (settings.get("estimatedCentsPerCall") or {}).get(provider)
    if per_call is not None:
        try:
            return max(0, int(per_call))
        except (TypeError, ValueError):
            return None
    per_1k = (settings.get("centsPer1kTokens") or {}).get(provider)
    if per_1k is None:
        return None
    try:
        rate = int(per_1k)
    except (TypeError, ValueError):
        return None
    return max(0, int((estimated_tokens / 1000) * rate))


def classify_provider(
    provider: str,
    settings: dict[str, Any] | None,
    *,
    ledger: BudgetLedger | None = None,
    estimated_tokens: int = 0,
) -> ProviderCost:
    """Resolve one provider. unknown and manual_paste are never eligible to call."""
    settings = settings or {}
    ledger = ledger or budget_ledger_from_settings(settings)
    declared = declared_cost_class(provider, settings)
    if declared == "manual_paste":
        return ProviderCost(
            provider=provider,
            cost_class="manual_paste",
            eligible=False,
            reason="manual_paste",
            cost_known=True,
            authorization_mode="manual_paste",
        )
    if declared == "offline":
        if provider != "local":
            return ProviderCost(
                provider=provider,
                cost_class="unknown",
                eligible=False,
                reason="offline_not_local",
                cost_known=False,
                authorization_mode="unknown",
            )
        return ProviderCost(
            provider=provider,
            cost_class="offline",
            eligible=True,
            reason="offline",
            cost_known=True,
            estimated_cents=0,
            authorization_mode="offline",
        )
    if declared == "free_only":
        if not adapter_can_assert_zero_charge(provider, settings):
            return ProviderCost(
                provider=provider,
                cost_class="unknown",
                eligible=False,
                reason="free_only_unproven",
                cost_known=False,
                authorization_mode="unknown",
            )
        return ProviderCost(
            provider=provider,
            cost_class="free_only",
            eligible=True,
            reason="free_only_asserted",
            cost_known=True,
            estimated_cents=0,
            authorization_mode="free_only",
        )
    if declared == "paid_with_budget":
        if provider not in _allowlist(settings):
            return ProviderCost(
                provider=provider,
                cost_class="paid_with_budget",
                eligible=False,
                reason="paid_not_allowlisted",
                cost_known=True,
                authorization_mode="paid_with_budget",
            )
        if ledger.remaining_cents <= 0:
            return ProviderCost(
                provider=provider,
                cost_class="paid_with_budget",
                eligible=False,
                reason="paid_budget_empty",
                cost_known=True,
                authorization_mode="paid_with_budget",
            )
        estimate = estimated_call_cents(
            provider, settings, estimated_tokens=estimated_tokens
        )
        if estimate is None:
            return ProviderCost(
                provider=provider,
                cost_class="unknown",
                eligible=False,
                reason="paid_estimate_unknown",
                cost_known=False,
                authorization_mode="unknown",
            )
        if ledger.would_exceed(estimate):
            return ProviderCost(
                provider=provider,
                cost_class="paid_with_budget",
                eligible=False,
                reason="paid_would_exceed_budget",
                cost_known=True,
                estimated_cents=estimate,
                authorization_mode="paid_with_budget",
            )
        return ProviderCost(
            provider=provider,
            cost_class="paid_with_budget",
            eligible=True,
            reason="paid_with_budget",
            cost_known=True,
            estimated_cents=estimate,
            authorization_mode="paid_with_budget",
        )
    return ProviderCost(
        provider=provider,
        cost_class="unknown",
        eligible=False,
        reason="unknown_cost_class",
        cost_known=False,
        authorization_mode="unknown",
    )


def authorize_provider_chain(
    providers: Iterable[str],
    settings: dict[str, Any] | None,
    *,
    ledger: BudgetLedger | None = None,
    estimated_tokens: int = 0,
    seen_free_only: bool = False,
) -> Authorization:
    """Drop unknown and illegal free→paid fallbacks. Empty chain means pause."""
    settings = settings or {}
    ledger = ledger or budget_ledger_from_settings(settings)
    result = Authorization(seen_free_only=seen_free_only)
    for provider in providers:
        info = classify_provider(
            provider, settings, ledger=ledger, estimated_tokens=estimated_tokens
        )
        result.decisions.append(info)
        if not info.eligible:
            continue
        if info.cost_class == "paid_with_budget" and result.seen_free_only:
            info.eligible = False
            info.reason = "free_to_paid_forbidden"
            continue
        if info.cost_class == "free_only":
            result.seen_free_only = True
        result.providers.append(provider)
    return result


def unknown_refusal_receipt(
    *,
    provider: str | None = None,
    estimated_tokens: int | None = None,
    reason: str = "unknown_cost_class",
) -> dict[str, Any]:
    """Telemetry for a refused unknown call. api_cents is omitted, never 0."""
    row: dict[str, Any] = {
        "invocations": 0,
        "cost_class": "unknown",
        "cost_known": False,
        "cost_confidence": "unknown",
        "authorization_mode": "unknown",
        "reason": reason,
        "subscription_minutes": 0,
    }
    if provider is not None:
        row["provider"] = provider
    if estimated_tokens is not None:
        row["estimated_tokens"] = estimated_tokens
    return row


def known_call_receipt(
    *,
    provider: str,
    cost_class: str,
    estimated_tokens: int,
    actual_tokens: int | None = None,
    api_cents: int,
    invocations: int = 1,
) -> dict[str, Any]:
    """Telemetry for a call whose cost is known. Known free/offline may be 0."""
    row: dict[str, Any] = {
        "invocations": invocations,
        "provider": provider,
        "estimated_tokens": estimated_tokens,
        "cost_class": cost_class,
        "cost_known": True,
        "cost_confidence": "known",
        "authorization_mode": cost_class,
        "api_cents": api_cents,
        "subscription_minutes": 0,
    }
    if actual_tokens is not None:
        row["actual_tokens"] = actual_tokens
    return row


def offline_zero_call_metrics() -> dict[str, Any]:
    """Eval / deterministic path: no model call, cost known, api_cents may be 0."""
    return known_call_receipt(
        provider="none",
        cost_class="offline",
        estimated_tokens=0,
        api_cents=0,
        invocations=0,
    )


def exhausted_chain_receipt(
    info: ProviderCost,
    *,
    estimated_tokens: int | None = None,
) -> dict[str, Any]:
    """Keep the authorized class after adapters return empty. Do not relabel unknown."""
    row: dict[str, Any] = {
        "invocations": 0,
        "provider": info.provider,
        "cost_class": info.cost_class,
        "cost_known": info.cost_known,
        "cost_confidence": "known" if info.cost_known else "unknown",
        "authorization_mode": info.authorization_mode,
        "reason": "providers_exhausted",
        "subscription_minutes": 0,
    }
    if estimated_tokens is not None:
        row["estimated_tokens"] = estimated_tokens
    if info.cost_known and info.cost_class in {"offline", "free_only"}:
        row["api_cents"] = 0
    return row


def raise_if_pause(auth: Authorization, *, estimated_tokens: int | None = None) -> None:
    """Raise CostPauseError when the filtered chain is empty."""
    if not auth.pause:
        return
    first_unknown = next(
        (row for row in auth.decisions if row.cost_class == "unknown"),
        None,
    )
    provider = first_unknown.provider if first_unknown else None
    reason = first_unknown.reason if first_unknown else "no_eligible_provider"
    raise CostPauseError(
        receipt=unknown_refusal_receipt(
            provider=provider,
            estimated_tokens=estimated_tokens,
            reason=reason,
        )
    )


def debit_if_paid(ledger: BudgetLedger, info: ProviderCost) -> None:
    """Subtract a known paid estimate after a successful paid call."""
    if info.cost_class == "paid_with_budget" and info.estimated_cents is not None:
        ledger.debit(info.estimated_cents)
