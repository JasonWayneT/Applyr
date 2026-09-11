#!/usr/bin/env python3
"""Advisory FR-306 / AC-403 trailing-mechanism resume reporter."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Sequence

BULLET_PATTERN = re.compile(r"^\s*[-*]\s+")
TRAILING_MECHANISM_PATTERN = re.compile(
    r"(?:,|\bby\b|\bwhile\b)\s+[A-Za-z]{3,}ing\b",
    re.IGNORECASE,
)
MAX_EXAMPLES = 8
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
DEFAULT_ROOT = _REPO_ROOT / "data" / "submissions"


@dataclass(slots=True)
class ScanResult:
    """Store advisory trailing-mechanism counts for one resume."""

    slug: str
    bullet_count: int
    trailing_mechanism_count: int
    rate: float
    examples: list[str]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe representation of the scan result."""
        return asdict(self)


def extract_bullets(resume_text: str) -> list[str]:
    """Return markdown bullet lines from a resume document."""
    return [line.rstrip() for line in resume_text.splitlines() if BULLET_PATTERN.match(line)]


def count_trailing_mechanisms(bullets: Sequence[str]) -> tuple[int, list[str]]:
    """Count F7 trailing-mechanism bullets and keep up to eight examples."""
    examples: list[str] = []
    count = 0
    for bullet in bullets:
        if TRAILING_MECHANISM_PATTERN.search(bullet):
            count += 1
            if len(examples) < MAX_EXAMPLES:
                examples.append(bullet)
    return count, examples


def scan_resume(slug: str, resume_path: Path) -> ScanResult:
    """Scan one Resume.md file and return advisory counts."""
    bullets = extract_bullets(resume_path.read_text(encoding="utf-8"))
    trailing_mechanism_count, examples = count_trailing_mechanisms(bullets)
    bullet_count = len(bullets)
    rate = round(trailing_mechanism_count / bullet_count, 4) if bullet_count else 0.0
    return ScanResult(
        slug=slug,
        bullet_count=bullet_count,
        trailing_mechanism_count=trailing_mechanism_count,
        rate=rate,
        examples=examples,
    )


def scan_root(root: Path) -> list[ScanResult]:
    """Scan every submission folder under the requested root."""
    if not root.exists():
        return []
    results: list[ScanResult] = []
    for folder in sorted((path for path in root.iterdir() if path.is_dir()), key=lambda path: path.name):
        resume_path = folder / "Resume.md"
        if not resume_path.exists():
            continue
        results.append(scan_resume(folder.name, resume_path))
    return results


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(description="Report advisory trailing-gerund rates for Resume.md files.")
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help="Submission root to scan. Defaults to data/submissions relative to the repo root.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser


def print_text_report(results: Sequence[ScanResult]) -> None:
    """Print the human-readable advisory report."""
    for result in results:
        print(
            f"{result.slug}: bullets={result.bullet_count} "
            f"trailing_mechanism={result.trailing_mechanism_count} rate={result.rate:.2f}"
        )
        for example in result.examples:
            print(f"  {example}")
    print("Advisory only. No linter rule. No rewrite.")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the advisory trailing-gerund reporter."""
    parser = build_parser()
    args = parser.parse_args(argv)
    results = scan_root(Path(args.root))
    if args.json:
        json.dump([result.to_dict() for result in results], sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print_text_report(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
