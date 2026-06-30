"""
Structured cover letter slot generation (Epics 2 & 7).

Epic 7 — Hook Isolation: generate_hook, validate_hook, generate_validated_hook
Epic 2 — Skeleton: CLSlot, CLSlotConstraints, generate_cl_slots, assemble_cl_from_slots
Epic 6 — Per-slot critic: critique_slot, retry_slot_until_passing
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Tuple

# ---------------------------------------------------------------------------
# Epic 2 — Data classes
# ---------------------------------------------------------------------------

@dataclass
class CLSlotConstraints:
    slot_type: str
    max_words: int
    min_words: int
    forbidden_openers: List[str]
    required_content_type: str
    no_i_statements: bool = False


@dataclass
class CLSlot:
    slot_type: Literal["HOOK", "PROOF_1", "PROOF_2", "CLOSING"]
    content: Optional[str] = None
    attempts: int = 0
    passed_lint: bool = False


# Slot constraints per type (module-level constants)
SLOT_CONSTRAINTS: Dict[str, CLSlotConstraints] = {
    "HOOK": CLSlotConstraints(
        slot_type="HOOK",
        max_words=35,
        min_words=8,
        forbidden_openers=["I ", "My ", "I've ", "I'd "],
        required_content_type="company observation or role problem",
        no_i_statements=True,
    ),
    "PROOF_1": CLSlotConstraints(
        slot_type="PROOF_1",
        max_words=100,
        min_words=60,
        forbidden_openers=["I am", "My background", "I have a proven"],
        required_content_type="proof with metric or specific outcome",
        no_i_statements=False,
    ),
    "PROOF_2": CLSlotConstraints(
        slot_type="PROOF_2",
        max_words=100,
        min_words=60,
        forbidden_openers=["I am", "My background", "I have a proven"],
        required_content_type="second claim or gap acknowledgment",
        no_i_statements=False,
    ),
    "CLOSING": CLSlotConstraints(
        slot_type="CLOSING",
        max_words=30,
        min_words=10,
        forbidden_openers=["I am excited", "I am confident", "I look forward to"],
        required_content_type="direct call to action",
        no_i_statements=False,
    ),
}


class HookGenerationError(Exception):
    """Raised when hook generation fails all retry attempts."""
    def __init__(self, message: str, best_attempt: str = ""):
        super().__init__(message)
        self.best_attempt = best_attempt


# ---------------------------------------------------------------------------
# Epic 7 — Hook Isolation
# ---------------------------------------------------------------------------

_HOOK_SYSTEM = """You write opening sentences for cover letters.
Rules:
- Exactly one sentence.
- Under 35 words.
- No "I" anywhere in the sentence.
- Must contain at least one specific detail from the company or role description.
- Do not express enthusiasm, desire, or excitement.
- Do not describe the applicant.
- Describe something true about the company's situation or the problem this role solves.

Output only the sentence. Nothing else."""

_FIRST_PERSON_RE = re.compile(r"\b(I|my|me|we|I've|I'd|I'm)\b", re.IGNORECASE)


def extract_hook_facts(jd_profile) -> Dict[str, str]:
    """Extract 5 concrete facts from a JdProfile for hook generation (Story 7.1).

    Returns a dict with at least 3 populated fields for any valid JdProfile.
    Falls back to raw JD text slice if a field is missing.
    """
    facts: Dict[str, str] = {}

    # company_name — from profile keywords or themes
    facts["company_name"] = ""

    # role_mission — first priority theme
    themes = getattr(jd_profile, "priority_themes", [])
    facts["role_mission"] = themes[0] if themes else ""

    # primary_challenge — second theme or first requirement
    reqs = getattr(jd_profile, "requirements", [])
    facts["primary_challenge"] = themes[1] if len(themes) > 1 else (reqs[0] if reqs else "")

    # product_surface — third theme or second requirement
    facts["product_surface"] = themes[2] if len(themes) > 2 else (reqs[1] if len(reqs) > 1 else "")

    # customer_type — infer from keywords
    keywords = getattr(jd_profile, "keywords", [])
    customer_signals = [k for k in keywords if k in (
        "enterprise", "saas", "b2b", "consumer", "users", "customers",
        "lenders", "borrowers", "students", "accounts", "clients"
    )]
    facts["customer_type"] = customer_signals[0] if customer_signals else ""

    # Ensure at least 3 are populated
    populated = sum(1 for v in facts.values() if v.strip())
    if populated < 3 and reqs:
        for req in reqs[:3]:
            if req.strip() and req not in facts.values():
                facts[f"req_{len(facts)}"] = req[:80]
                break

    return facts


def validate_hook(hook: str, hook_facts: Dict[str, str]) -> Tuple[bool, str]:
    """Validate hook against three hard checks (Story 7.3).

    Returns (passed, failure_reason). Empty failure_reason means passed.
    """
    # Check 1: no first-person pronouns
    if _FIRST_PERSON_RE.search(hook):
        m = _FIRST_PERSON_RE.search(hook)
        return False, f"Contains first-person pronoun '{m.group(0)}'."

    # Check 2: at least one word from JD facts appears in hook
    hook_l = hook.lower()
    all_fact_words = set()
    for v in hook_facts.values():
        for word in re.findall(r"[a-z]{4,}", v.lower()):
            all_fact_words.add(word)
    if not any(w in hook_l for w in all_fact_words):
        return False, "Hook contains no JD-specific detail (no word from JD facts found)."

    # Check 3: word count ≤ 35
    wc = len(hook.split())
    if wc > 35:
        return False, f"Hook is {wc} words; maximum is 35."

    return True, ""


def generate_hook(hook_facts: Dict[str, str], llm_client=None) -> str:
    """Generate a single hook sentence with constrained prompt (Story 7.2)."""
    from utils import call_llm

    facts_block = "\n".join(f"- {k}: {v}" for k, v in hook_facts.items() if v.strip())
    user_prompt = f"Company/role facts:\n{facts_block}\n\nWrite the opening sentence."

    raw = call_llm(
        system_prompt=_HOOK_SYSTEM,
        user_prompt=user_prompt,
        temperature=0.3,
    )
    if not raw:
        return ""
    # Strip any accidental fences or extra lines
    hook = raw.strip().split("\n")[0].strip()
    return hook


def generate_validated_hook(
    hook_facts: Dict[str, str],
    llm_client=None,
    max_attempts: int = 3,
) -> str:
    """Retry loop: generate + validate, up to max_attempts (Story 7.4).

    Raises HookGenerationError with best_attempt if all attempts fail.
    """
    best = ""
    last_reason = ""

    for attempt in range(1, max_attempts + 1):
        system = _HOOK_SYSTEM
        if attempt > 1 and last_reason:
            # Inject failure reason into the next attempt
            system = f"{_HOOK_SYSTEM}\n\nPrevious attempt failed: {last_reason} Try again."

        from utils import call_llm

        facts_block = "\n".join(f"- {k}: {v}" for k, v in hook_facts.items() if v.strip())
        user_prompt = f"Company/role facts:\n{facts_block}\n\nWrite the opening sentence."

        raw = call_llm(system_prompt=system, user_prompt=user_prompt, temperature=0.3)
        hook = (raw or "").strip().split("\n")[0].strip()

        if not best:
            best = hook

        passed, reason = validate_hook(hook, hook_facts)
        if passed:
            return hook

        last_reason = reason
        best = hook  # keep last attempt as best

    raise HookGenerationError(
        f"Hook generation failed after {max_attempts} attempts. Last reason: {last_reason}",
        best_attempt=best,
    )


# ---------------------------------------------------------------------------
# Epic 2 — Slot generation
# ---------------------------------------------------------------------------

_SLOT_SYSTEM_TEMPLATE = """You write a single paragraph for a structured cover letter.

SLOT: {slot_type}
CONSTRAINTS:
- {min_words}–{max_words} words.
- Do NOT use bullet points.
- Do NOT start with: {forbidden_openers}.
- Content type required: {required_content_type}.
{no_i_note}
Output ONLY the paragraph text. No labels, no headers, no extra lines."""

_PROOF_SLOT_PROMPT = """You are writing the {slot_type} paragraph for a cover letter.

JOB DESCRIPTION (excerpt):
{jd_excerpt}

PRE-SELECTED CLAIMS TO USE (use at least one):
{claims_block}

PREVIOUS CONTENT (for context and cohesion — do NOT repeat it):
{accumulated}

Write only the {slot_type} paragraph. Echo one word or theme from the opening if natural.
{slot_type} = {required_content_type}. {min_words}–{max_words} words. No bullet points."""

_CLOSING_PROMPT = """You are writing the CLOSING for a cover letter.

PREVIOUS CONTENT:
{accumulated}

Write one or two sentences that are a direct call to action. Under 30 words total.
Do not start with 'I am excited', 'I am confident', or 'I look forward to'.
Do not express enthusiasm. Just state what you want — a conversation, a call, an interview.
Output only the sentences."""


def _slot_passes_constraints(slot_content: str, slot_type: str) -> Tuple[bool, str]:
    """Check a generated slot against its hard constraints."""
    constraints = SLOT_CONSTRAINTS.get(slot_type)
    if not constraints:
        return True, ""

    wc = len(slot_content.split())

    if wc > constraints.max_words:
        return False, f"Word count {wc} exceeds max {constraints.max_words}."
    if wc < constraints.min_words:
        return False, f"Word count {wc} below min {constraints.min_words}."

    for opener in constraints.forbidden_openers:
        if slot_content.lstrip().startswith(opener):
            return False, f"Starts with forbidden opener '{opener}'."

    if constraints.no_i_statements and _FIRST_PERSON_RE.search(slot_content):
        m = _FIRST_PERSON_RE.search(slot_content)
        return False, f"Contains first-person pronoun '{m.group(0)}'."

    return True, ""


def _generate_one_slot(
    slot_type: str,
    jd_text: str,
    claims: List[str],
    accumulated_slots: List[CLSlot],
) -> str:
    """Generate a single slot with the LLM."""
    from utils import call_llm

    constraints = SLOT_CONSTRAINTS[slot_type]
    accumulated_text = "\n\n".join(
        s.content for s in accumulated_slots if s.content
    )

    if slot_type == "CLOSING":
        user_prompt = _CLOSING_PROMPT.format(accumulated=accumulated_text)
        system = (
            "You write cover letter closings. One or two sentences. Under 30 words. "
            "Direct call to action only. No enthusiasm words."
        )
    else:
        no_i_note = (
            "- Do NOT use 'I', 'my', 'me', or 'we'." if constraints.no_i_statements else ""
        )
        system = _SLOT_SYSTEM_TEMPLATE.format(
            slot_type=slot_type,
            min_words=constraints.min_words,
            max_words=constraints.max_words,
            forbidden_openers=", ".join(f"'{o}'" for o in constraints.forbidden_openers),
            required_content_type=constraints.required_content_type,
            no_i_note=no_i_note,
        )
        claims_block = "\n".join(f"- {c}" for c in claims) if claims else "Use your best judgment."
        user_prompt = _PROOF_SLOT_PROMPT.format(
            slot_type=slot_type,
            jd_excerpt=jd_text[:1500],
            claims_block=claims_block,
            accumulated=accumulated_text or "(none yet)",
            required_content_type=constraints.required_content_type,
            min_words=constraints.min_words,
            max_words=constraints.max_words,
        )

    raw = call_llm(system_prompt=system, user_prompt=user_prompt, temperature=0.4)
    return (raw or "").strip()


def generate_cl_slots(
    hook: str,
    pre_selected_claims: List[str],
    jd_text: str,
    plan=None,
    max_slot_attempts: int = 3,
) -> List[CLSlot]:
    """Generate PROOF_1, PROOF_2, CLOSING slots sequentially (Story 2.2 + 2.3).

    Hook is already provided and locked. Returns list of 4 CLSlot objects.
    """
    hook_slot = CLSlot(slot_type="HOOK", content=hook, attempts=1, passed_lint=True)
    slots: List[CLSlot] = [hook_slot]

    for slot_type in ("PROOF_1", "PROOF_2", "CLOSING"):
        slot = _generate_and_validate_slot(
            slot_type=slot_type,
            jd_text=jd_text,
            claims=pre_selected_claims,
            accumulated_slots=slots,
            max_attempts=max_slot_attempts,
        )
        slots.append(slot)

    return slots


def _generate_and_validate_slot(
    slot_type: str,
    jd_text: str,
    claims: List[str],
    accumulated_slots: List[CLSlot],
    max_attempts: int = 3,
) -> CLSlot:
    """Generate a slot with per-slot retry on constraint failure (Story 2.3)."""
    import sys

    best_content = ""
    for attempt in range(1, max_attempts + 1):
        content = _generate_one_slot(slot_type, jd_text, claims, accumulated_slots)
        if not best_content:
            best_content = content

        passed, reason = _slot_passes_constraints(content, slot_type)
        if passed:
            return CLSlot(
                slot_type=slot_type,
                content=content,
                attempts=attempt,
                passed_lint=True,
            )

        print(
            f"    [Slots] {slot_type} attempt {attempt} failed constraint: {reason}",
            file=sys.stderr,
        )
        best_content = content

    # All attempts failed — use best attempt with a warning
    print(
        f"    [Slots] WARNING: {slot_type} did not pass constraints after {max_attempts} attempts. Using best attempt.",
        file=sys.stderr,
    )
    return CLSlot(
        slot_type=slot_type,
        content=best_content,
        attempts=max_attempts,
        passed_lint=False,
    )


def assemble_cl_from_slots(
    slots: List[CLSlot],
    header: str,
    candidate_name: str = "",
) -> str:
    """Join slots into a complete cover letter markdown string (Story 2.4)."""
    salutation = "Dear Hiring Manager,"
    signoff = f"Best regards,\n\n{candidate_name or 'Jason Taylor'}"

    body_parts = []
    for slot in slots:
        if slot.content and slot.content.strip():
            body_parts.append(slot.content.strip())

    body = "\n\n".join(body_parts)
    letter = f"{header.strip()}\n\n{salutation}\n\n{body}\n\n{signoff}\n"
    return letter


# ---------------------------------------------------------------------------
# Epic 6 — Per-slot critic
# ---------------------------------------------------------------------------

_SLOT_RUBRIC_MAP = {
    "HOOK": ("C1", "C2"),       # C1=hook specificity, C2=opening energy
    "PROOF_1": ("C3",),         # C3=proof density
    "PROOF_2": ("C3", "C4"),    # C3=proof density, C4=role fit
    "CLOSING": ("C5",),         # C5=closing
}

_CRITIC_SYSTEM = """You are a cover letter quality evaluator.
Score the provided paragraph against the rubric dimensions specified.
Return JSON: {"score": <float 0.0-1.0>, "feedback": "<one sentence>"}
Be strict. A score of 1.0 means flawless. 0.65 is the minimum acceptable threshold."""


def critique_slot(
    slot: CLSlot,
    jd_profile,
    accumulated_context: str = "",
) -> Tuple[float, str]:
    """Score a single slot against its rubric dimensions (Story 6.1).

    Returns (score, feedback).
    """
    from utils import call_llm
    import json as _json

    if not slot.content:
        return 0.0, "Slot has no content."

    rubric_dims = _SLOT_RUBRIC_MAP.get(slot.slot_type, ())
    dim_descriptions = {
        "C1": "Opening hook specificity — references specific company detail or role problem.",
        "C2": "Opening energy and voice — not generic, not AI-sounding.",
        "C3": "Proof density — includes specific accomplishment with metric or clear outcome.",
        "C4": "Role fit logic — connects candidate background to this specific role.",
        "C5": "Closing — direct call to action, low-pressure, under 30 words.",
    }
    dims_block = "\n".join(
        f"- {d}: {dim_descriptions.get(d, d)}" for d in rubric_dims
    )

    themes = getattr(jd_profile, "priority_themes", [])
    jd_context = f"JD themes: {', '.join(themes[:3])}" if themes else ""

    user_prompt = (
        f"Slot type: {slot.slot_type}\n"
        f"Rubric dimensions to score against:\n{dims_block}\n"
        f"{jd_context}\n\n"
        f"Previous content (for context):\n{accumulated_context[:600] or '(none)'}\n\n"
        f"Paragraph to score:\n{slot.content}\n\n"
        "Return only JSON: {\"score\": <0.0-1.0>, \"feedback\": \"<one sentence>\"}"
    )

    raw = call_llm(
        system_prompt=_CRITIC_SYSTEM,
        user_prompt=user_prompt,
        temperature=0.1,
        response_mime_type="application/json",
    )
    if not raw:
        return 0.5, "LLM returned nothing — score unknown."

    try:
        cleaned = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        data = _json.loads(cleaned)
        score = float(data.get("score", 0.5))
        feedback = str(data.get("feedback", ""))
        return max(0.0, min(1.0, score)), feedback
    except Exception:
        return 0.5, "Could not parse score."


def retry_slot_until_passing(
    slot: CLSlot,
    jd_profile,
    accumulated_context: str,
    threshold: float = 0.65,
    max_attempts: int = 3,
    jd_text: str = "",
    claims: List[str] = None,
    accumulated_slots: List[CLSlot] = None,
) -> CLSlot:
    """Retry a slot until it passes rubric threshold or max_attempts reached (Story 6.2).

    Returns the best-scoring slot.
    """
    import sys

    if claims is None:
        claims = []
    if accumulated_slots is None:
        accumulated_slots = []

    best_slot = slot
    best_score = 0.0

    current_slot = slot
    for attempt in range(1, max_attempts + 1):
        score, feedback = critique_slot(current_slot, jd_profile, accumulated_context)

        if score > best_score:
            best_score = score
            best_slot = current_slot

        if score >= threshold:
            return current_slot

        print(
            f"    [Critic] {slot.slot_type} score {score:.2f} below threshold {threshold}; "
            f"retry {attempt}/{max_attempts}. Feedback: {feedback}",
            file=sys.stderr,
        )

        if attempt < max_attempts:
            # Regenerate with feedback injected
            from utils import call_llm

            constraints = SLOT_CONSTRAINTS.get(slot.slot_type)
            retry_system = (
                f"Previous attempt failed because: {feedback} Try again.\n\n"
                + (_SLOT_SYSTEM_TEMPLATE.format(
                    slot_type=slot.slot_type,
                    min_words=constraints.min_words if constraints else 60,
                    max_words=constraints.max_words if constraints else 100,
                    forbidden_openers=", ".join(
                        f"'{o}'" for o in (constraints.forbidden_openers if constraints else [])
                    ),
                    required_content_type=constraints.required_content_type if constraints else "",
                    no_i_note="",
                ) if constraints else "")
            )
            claims_block = "\n".join(f"- {c}" for c in claims) if claims else ""
            if slot.slot_type == "CLOSING":
                user_prompt = _CLOSING_PROMPT.format(
                    accumulated=accumulated_context[:600] or "(none)"
                )
            else:
                user_prompt = _PROOF_SLOT_PROMPT.format(
                    slot_type=slot.slot_type,
                    jd_excerpt=jd_text[:1500],
                    claims_block=claims_block or "Use your best judgment.",
                    accumulated=accumulated_context[:600] or "(none)",
                    required_content_type=constraints.required_content_type if constraints else "",
                    min_words=constraints.min_words if constraints else 60,
                    max_words=constraints.max_words if constraints else 100,
                )
            raw = call_llm(system_prompt=retry_system, user_prompt=user_prompt, temperature=0.5)
            new_content = (raw or "").strip()
            current_slot = CLSlot(
                slot_type=slot.slot_type,
                content=new_content,
                attempts=attempt + 1,
                passed_lint=False,
            )

    print(
        f"    [Critic] {slot.slot_type} max attempts reached; using best attempt (score {best_score:.2f}).",
        file=sys.stderr,
    )
    return best_slot
