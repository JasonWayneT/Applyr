#!/usr/bin/env python3
"""CLI wrapper for catalog + metrics validation (CR-031). Uses example fixtures when data/ absent."""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catalog_validator import validate_catalog


def main() -> int:
    result = validate_catalog()
    if result.warnings:
        for w in result.warnings:
            print(f"WARN: {w}")
    if not result.ok:
        print("Validation Failed:")
        for err in result.errors:
            print(f" - {err}")
        return 1
    print("Validation Passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
