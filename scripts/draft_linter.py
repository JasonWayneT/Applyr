"""
Optional phi3.5 JSON lint pass — reports issues only, never rewrites (CR-021 / FR-145).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from utils import get_verifier_model, call_llm


def lint_draft_text(text: str, label: str = "resume") -> Dict[str, Any]:
    """Returns {ok: bool, issues: list[str]}. Opt-in only (CR-070) — set
    LOCAL_LINT=1 to enable; skipped by default so this Ollama call doesn't
    fire on the default drafting path."""
    import os

    if os.environ.get("LOCAL_LINT", "0").strip() not in ("1", "true", "yes"):
        return {"ok": True, "issues": []}

    schema = {
        "type": "object",
        "properties": {
            "ok": {"type": "boolean"},
            "issues": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["ok", "issues"],
    }
    system = (
        "You are a resume fact linter. List ONLY stylistic or clarity issues. "
        "Do NOT suggest adding facts, metrics, tools, or employers. "
        "If text is acceptable, return ok:true and issues:[]. Output JSON only."
    )
    user = f"Document type: {label}\n\n{text[:3500]}"
    raw = call_llm(
        system,
        user,
        model=get_verifier_model(),
        temperature=0.0,
        response_mime_type="application/json",
        provider_override=["local"],
        response_schema=schema,
    )
    if not raw:
        return {"ok": True, "issues": []}
    try:
        data = json.loads(raw.strip().lstrip("```json").rstrip("```"))
        issues: List[str] = [str(i) for i in data.get("issues", [])]
        return {"ok": bool(data.get("ok", not issues)), "issues": issues}
    except json.JSONDecodeError:
        return {"ok": True, "issues": []}
