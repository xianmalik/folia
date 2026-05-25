#!/usr/bin/env python3
"""
Semantic embedding layer for ATS matching.

Uses sentence-transformers/all-MiniLM-L6-v2 (≈80MB, offline) to compute
cosine similarity between JD keywords and resume text.  Falls back to a
no-op (returns 0.0) if the model cannot be loaded.

The model is downloaded once to ~/.cache/folia/embeddings/ and reused.

Usage
-----
    from ats.embeddings import semantic_score, is_available

    if is_available():
        score = semantic_score("PostgreSQL connection pooling", resume_text)
        # score ∈ [0, 1]
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_CACHE_DIR = Path.home() / ".cache" / "folia" / "embeddings"

_model = None          # lazy-loaded SentenceTransformer
_HAS_ST = None         # True/False/None (not-yet-checked)

# Cosine similarity threshold below which we don't count as a match
SEMANTIC_MIN_SIM: float = 0.55

# Score assigned to a semantic match (between ontology=0.70 and direct=1.00)
SEMANTIC_SCORE: float = float(
    os.environ.get("FOLIA_SEMANTIC_SCORE", "0.55")
)


def is_available() -> bool:
    """Return True if sentence-transformers is installed and the model can load."""
    global _HAS_ST
    if _HAS_ST is not None:
        return _HAS_ST
    try:
        import importlib.util
        _HAS_ST = importlib.util.find_spec("sentence_transformers") is not None
    except Exception:
        _HAS_ST = False
    return _HAS_ST


def _get_model():
    global _model
    if _model is not None:
        return _model
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        _model = SentenceTransformer(_MODEL_NAME, cache_folder=str(_CACHE_DIR))
        return _model
    except Exception:
        return None


def _encode(texts: list[str]):
    """Return an ndarray of shape (n, dim) or None on failure."""
    model = _get_model()
    if model is None:
        return None
    try:
        return model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    except Exception:
        return None


def _cosine_sim(a, b) -> float:
    """Cosine similarity between two 1-D numpy arrays."""
    try:
        import numpy as np  # type: ignore
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
    except Exception:
        return 0.0


def semantic_score(keyword: str, resume_section_texts: dict[str, str]) -> tuple[float, list[str]]:
    """
    Compute the best cosine similarity between ``keyword`` and each resume section.

    Returns
    -------
    (score, found_in_sections)
        score : float in [0, 1] — 0.0 if model unavailable or below threshold.
        found_in_sections : list of section names where similarity exceeded threshold.
    """
    if not is_available():
        return 0.0, []

    model = _get_model()
    if model is None:
        return 0.0, []

    sections = list(resume_section_texts.keys())
    texts = [resume_section_texts[s] for s in sections]

    try:
        kw_emb = _encode([keyword])
        if kw_emb is None:
            return 0.0, []

        found_in: list[str] = []
        best_sim = 0.0

        # For each section: encode in chunks then take max similarity to keyword
        for i, (section, text) in enumerate(zip(sections, texts)):
            if not text.strip():
                continue
            # Split into sentences/phrases (≤512 chars each) for better granularity
            chunks = _split_chunks(text, max_len=200)
            if not chunks:
                continue
            chunk_embs = _encode(chunks)
            if chunk_embs is None:
                continue
            sims = [_cosine_sim(kw_emb[0], ce) for ce in chunk_embs]
            max_sim = max(sims) if sims else 0.0
            if max_sim >= SEMANTIC_MIN_SIM:
                found_in.append(section)
                if max_sim > best_sim:
                    best_sim = max_sim

        if not found_in:
            return 0.0, []

        # Scale: SEMANTIC_MIN_SIM → SEMANTIC_SCORE, 1.0 → 1.0
        scaled = SEMANTIC_SCORE + (best_sim - SEMANTIC_MIN_SIM) / (1.0 - SEMANTIC_MIN_SIM) * (1.0 - SEMANTIC_SCORE)
        return round(min(scaled, 1.0), 4), found_in

    except Exception:
        return 0.0, []


def _split_chunks(text: str, max_len: int = 200) -> list[str]:
    """
    Split text into chunks of at most ``max_len`` characters, splitting on
    sentence boundaries (periods, bullets) where possible.
    """
    import re
    # Split on common bullet / sentence boundaries
    parts = re.split(r"[\.\!\?\n•·]+", text)
    chunks: list[str] = []
    current = ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(current) + len(p) + 1 <= max_len:
            current = (current + " " + p).strip()
        else:
            if current:
                chunks.append(current)
            current = p[:max_len]
    if current:
        chunks.append(current)
    return chunks or [text[:max_len]]


def bulk_semantic_scores(
    keywords: list[str],
    resume_section_texts: dict[str, str],
    batch_size: int = 32,
) -> dict[str, tuple[float, list[str]]]:
    """
    Compute semantic scores for a list of keywords in one batched pass.

    Returns a dict: keyword → (score, found_in_sections).
    This is more efficient than calling semantic_score() in a loop.
    """
    if not is_available() or not keywords:
        return {kw: (0.0, []) for kw in keywords}

    try:
        import numpy as np  # type: ignore

        sections = list(resume_section_texts.keys())
        # Build per-section chunk lists and encode in one batch per section
        section_chunk_embs: dict[str, list] = {}
        for section, text in resume_section_texts.items():
            if not text.strip():
                section_chunk_embs[section] = []
                continue
            chunks = _split_chunks(text, max_len=200)
            embs = _encode(chunks)
            section_chunk_embs[section] = list(embs) if embs is not None else []

        # Encode all keywords in one pass
        kw_embs = _encode(keywords)
        if kw_embs is None:
            return {kw: (0.0, []) for kw in keywords}

        results: dict[str, tuple[float, list[str]]] = {}
        for i, kw in enumerate(keywords):
            kw_vec = kw_embs[i]
            found_in: list[str] = []
            best_sim = 0.0
            for section in sections:
                chunk_embs = section_chunk_embs.get(section, [])
                if not chunk_embs:
                    continue
                sims = [_cosine_sim(kw_vec, ce) for ce in chunk_embs]
                max_sim = max(sims) if sims else 0.0
                if max_sim >= SEMANTIC_MIN_SIM:
                    found_in.append(section)
                    if max_sim > best_sim:
                        best_sim = max_sim

            if not found_in:
                results[kw] = (0.0, [])
            else:
                scaled = SEMANTIC_SCORE + (best_sim - SEMANTIC_MIN_SIM) / (1.0 - SEMANTIC_MIN_SIM) * (1.0 - SEMANTIC_SCORE)
                results[kw] = (round(min(scaled, 1.0), 4), found_in)

        return results

    except Exception:
        return {kw: (0.0, []) for kw in keywords}
