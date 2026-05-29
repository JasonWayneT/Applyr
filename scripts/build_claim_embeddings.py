#!/usr/bin/env python3
"""Build or refresh data/claim_embeddings.json from workExperience.md (CR-021)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from claim_catalog import load_catalog


def main() -> int:
    cat = load_catalog()
    n = len(cat.claim_embeddings)
    print(f"Claim embeddings ready: {n} vectors for {len(cat.claims)} claims.")
    return 0 if n else 1


if __name__ == "__main__":
    raise SystemExit(main())
