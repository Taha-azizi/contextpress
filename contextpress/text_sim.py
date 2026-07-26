"""Shared TF-IDF cosine helpers for Tier 1 strategies."""

from __future__ import annotations

from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def tfidf_cosine(a: str, b: str) -> float:
    """Cosine similarity of two texts; ``0.0`` if vectors cannot be built."""
    if not a.strip() or not b.strip():
        return 0.0
    try:
        vec = TfidfVectorizer(min_df=1, max_df=1.0)
        mat = vec.fit_transform([a, b])
        return float(cosine_similarity(mat[0:1], mat[1:2])[0, 0])
    except ValueError:
        return 0.0


def tfidf_similarity_matrix(texts: list[str]) -> Any | None:
    """Pairwise cosine matrix for ``texts``, or ``None`` if unfit."""
    if len(texts) < 2:
        return None
    try:
        vec = TfidfVectorizer(min_df=1, max_df=1.0)
        mat = vec.fit_transform(texts)
        return cosine_similarity(mat)
    except ValueError:
        return None
