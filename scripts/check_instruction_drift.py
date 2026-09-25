"""Check Applyr instruction-file authority and pointer-stub invariants."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
POINTERS = {
    Path(".claude/skills/generate-submission/SKILL.md"): Path(
        ".codex/skills/generate-submission/SKILL.md"
    ),
    Path(".claude/skills/conversion-ready-pass/SKILL.md"): Path(
        ".codex/skills/conversion-ready-pass/SKILL.md"
    ),
    Path(".claude/skills/networking-outreach/SKILL.md"): Path(
        ".codex/skills/networking-outreach/SKILL.md"
    ),
    Path(".codex/skills/submission-no-ai-slop/SKILL.md"): Path(
        ".agents/skills/submission-no-ai-slop/SKILL.md"
    ),
}
CANONICALS = tuple(POINTERS.values())
POINTER_MAX_LINES = 20

BYTE_IDENTICAL_EDIT_RE = re.compile(
    r"(?i)(?:AGENTS\.md.*CLAUDE\.md|CLAUDE\.md.*AGENTS\.md)"
    r".{0,100}(?:must|should|keep|stay|remain|edit|edited|sync|synchroniz)"
    r".{0,100}byte[- ]identical"
)
WAITING_FOR_HUMAN_ASSIGNMENT_RE = re.compile(
    r"(?im)^\s*(?:status|state|verdict)\s*[:=].*WAITING_FOR_HUMAN\b"
)
ACTIVE_CR_ENUMERATION_RE = re.compile(r"(?i)\bcurrently\s+CR-\d+")


def _iter_instruction_files(root: Path) -> Iterable[Path]:
    """Yield tracked instruction surfaces that must remain mechanically clean."""
    fixed = (
        root / "AGENTS.md",
        root / "CLAUDE.md",
        root / "docs" / "AGENTS.md",
    )
    for path in fixed:
        if path.exists():
            yield path

    for directory in (
        root / ".claude" / "agents",
        root / ".claude" / "skills",
        root / ".codex" / "skills",
        root / ".agents" / "skills",
    ):
        if directory.exists():
            yield from sorted(directory.rglob("*.md"))


def _relative(path: Path, root: Path) -> str:
    """Return a repository-relative display path."""
    return path.relative_to(root).as_posix()


def check_drift(root: Path = REPO_ROOT) -> list[str]:
    """Return instruction-authority drift findings for a repository root."""
    problems: list[str] = []

    for pointer, canonical in POINTERS.items():
        pointer_path = root / pointer
        canonical_path = root / canonical

        if not pointer_path.exists():
            problems.append(f"Missing pointer stub: {pointer.as_posix()}")
        else:
            lines = pointer_path.read_text(encoding="utf-8").splitlines()
            if len(lines) > POINTER_MAX_LINES:
                problems.append(
                    f"Pointer stub exceeds {POINTER_MAX_LINES} lines: "
                    f"{pointer.as_posix()} ({len(lines)})"
                )
            target = canonical.as_posix()
            if target not in pointer_path.read_text(encoding="utf-8"):
                problems.append(
                    f"Pointer stub does not name canonical target: {pointer.as_posix()}"
                )

        if not canonical_path.exists():
            problems.append(f"Missing canonical skill: {canonical.as_posix()}")
        elif "Canonical copy" not in canonical_path.read_text(encoding="utf-8"):
            problems.append(
                f"Canonical skill lacks declaration: {canonical.as_posix()}"
            )

    for path in _iter_instruction_files(root):
        text = path.read_text(encoding="utf-8")
        display = _relative(path, root)

        if "file:///" in text:
            problems.append(f"Absolute file URL in instruction file: {display}")
        if BYTE_IDENTICAL_EDIT_RE.search(text):
            problems.append(
                f"Byte-identical AGENTS.md/CLAUDE.md edit instruction: {display}"
            )
        if WAITING_FOR_HUMAN_ASSIGNMENT_RE.search(text):
            problems.append(f"Legacy WAITING_FOR_HUMAN assignment: {display}")
        if ACTIVE_CR_ENUMERATION_RE.search(text) and display.startswith(
            ".claude/agents/"
        ):
            problems.append(f"Hardcoded active-CR enumeration: {display}")

    return problems


def main() -> None:
    """Print the drift result and exit nonzero when findings exist."""
    problems = check_drift()
    if not problems:
        print("CLEAN -- instruction authority and pointer stubs are consistent.")
        return

    print("DRIFT -- instruction authority checks failed:")
    for problem in problems:
        print(f"  - {problem}")
    sys.exit(1)


if __name__ == "__main__":
    main()
