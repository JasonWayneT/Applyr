"""
BM25 + embedding pre-score for batch queue ordering.

Implements FR-132 (CR-021). No LLM required.
Used to sort jobs before fit evaluation and optional FIT_EVAL_TOP_N cap.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

from local_embeddings import BM25, cosine_similarity, get_embedding


def _anchor_embedding(work_exp_summary: str) -> Optional[list]:
    anchor = (
        "B2B SaaS product manager platform stability data integrity "
        "customer migration roadmap cross-functional delivery"
    )
    try:
        return get_embedding(anchor)
    except Exception:
        return None


def pre_score_job(jd_text: str, work_exp_summary: str, anchor_vec: Optional[list] = None) -> int:
    """
    Returns 0–100 integer pre-score combining BM25 keyword overlap and optional cosine vs anchor.
    """
    if not jd_text or len(jd_text.strip()) < 50:
        return 0

    jd = jd_text[:4000]
    corpus = work_exp_summary or ""
    bm25_score = 0.0
    if corpus:
        paras = [p.strip() for p in re.split(r"\n\s*\n", corpus) if len(p.strip()) > 40]
        if not paras:
            paras = [line.strip() for line in corpus.splitlines() if line.strip().startswith("*")]
        if paras:
            bm25 = BM25(paras[:80])
            hits = bm25.get_top_n(jd, n=3)
            bm25_score = sum(s for _, s in hits) / max(len(hits), 1)

    embed_score = 0.0
    if anchor_vec is None:
        anchor_vec = _anchor_embedding(corpus)
    if anchor_vec:
        try:
            jd_vec = get_embedding(jd[:3000])
            if jd_vec:
                embed_score = max(0.0, cosine_similarity(jd_vec, anchor_vec))
        except Exception:
            pass

    combined = (bm25_score * 0.55) + (embed_score * 45.0)
    return int(min(100, max(0, round(combined))))


def score_staging_file(filepath: str, work_exp_summary: str, anchor_vec: Optional[list] = None) -> Tuple[str, int]:
    from utils import load_file

    text = load_file(filepath) or ""
    return filepath, pre_score_job(text, work_exp_summary, anchor_vec)
