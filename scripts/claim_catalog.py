"""
Parse master_claims.json into structured claims.
Implements the hybrid vector-deterministic architecture (CR-017 updated).
"""
from __future__ import annotations

import os
import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from utils import DATA_DIR

MASTER_CLAIMS_FILE = os.path.join(DATA_DIR, "master_claims.json")


def _project_id_from_claim_id(claim_id: str) -> str:
    m = re.match(r"^(ACC-\d+)", claim_id or "")
    return m.group(1) if m else (claim_id or "")

@dataclass
class ClaimRecord:
    claim_id: str
    title: str
    body: str
    employer: str
    project_id: str = ""
    tags: List[str] = field(default_factory=list)
    metrics: List[str] = field(default_factory=list)

@dataclass
class ClaimCatalog:
    claims: Dict[str, ClaimRecord] = field(default_factory=dict)
    voc_map: Dict[str, str] = field(default_factory=dict)
    anti_claim_hints: List[str] = field(default_factory=list)
    raw_truth_lines: Dict[str, str] = field(default_factory=dict)
    claim_embeddings: Dict[str, list] = field(default_factory=dict)

    def truth_map(self) -> Dict[str, str]:
        return self.raw_truth_lines

def load_catalog(path: Optional[str] = None) -> ClaimCatalog:
    path = path or MASTER_CLAIMS_FILE
    catalog = ClaimCatalog()
    
    if not os.path.exists(path):
        import sys
        print(f"    [Warning] Claims DB not found at {path}", file=sys.stderr)
        return catalog

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        for cid, val in data.items():
            catalog.claims[cid] = ClaimRecord(
                claim_id=cid,
                title=val.get("lens", ""),
                body=val.get("text", ""),
                employer=val.get("employer", ""),
                project_id=val.get("project_id", "") or _project_id_from_claim_id(cid),
                tags=val.get("tags", []),
                metrics=val.get("metrics", []),
            )
            catalog.raw_truth_lines[cid] = val.get("text", "")
            
    except Exception as e:
        import sys
        print(f"    [Error] Failed to load {path}: {e}", file=sys.stderr)

    _sync_embeddings(catalog, path)
    return catalog

def _sync_embeddings(catalog: ClaimCatalog, source_path: str):
    """Load or generate cached embeddings for all claims in the catalog."""
    cache_path = os.path.join(DATA_DIR, "claim_embeddings.json")
    
    # Check if cache is fresh
    if os.path.exists(cache_path) and os.path.getmtime(cache_path) >= os.path.getmtime(source_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                catalog.claim_embeddings = json.load(f)
            # Verify we have embeddings for all claims
            if all(cid in catalog.claim_embeddings for cid in catalog.claims):
                return
        except Exception:
            pass

    # Need to generate or update embeddings
    import sys
    print("    [Info] Generating local embeddings for master_claims...", file=sys.stderr)
    try:
        from local_embeddings import get_embedding
        for cid, rec in catalog.claims.items():
            if cid not in catalog.claim_embeddings:
                # Embed the tags + body to maximize semantic matching capability
                embedding_payload = f"{' '.join(rec.tags)} {rec.body}"
                catalog.claim_embeddings[cid] = get_embedding(embedding_payload)
        
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(catalog.claim_embeddings, f)
    except Exception as e:
        print(f"    [Error] Failed to generate claim embeddings: {e}", file=sys.stderr)

def apply_voc_map(text: str, catalog: ClaimCatalog) -> str:
    # Deprecated: master_claims.json is already plain-language
    return text

def sanitize_claim_text(text: str, catalog: ClaimCatalog) -> str:
    # Deprecated: master_claims.json is already sanitized, just return it
    # We still ensure trailing period for styling safety.
    clean = text.strip()
    if clean and not clean.endswith("."):
        clean += "."
    return clean
