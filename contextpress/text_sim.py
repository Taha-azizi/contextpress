"""Shared TF-IDF cosine helpers for Tier 1 strategies."""

from __future__ import annotations

from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel


def tfidf_query_scores(query: str, documents: list[str]) -> list[float]:
    """Cosine of ``query`` against each document. ``0.0`` when a vector cannot be built."""
    if not documents:
        return []
    if not query.strip() or not any(d.strip() for d in documents):
        return [0.0] * len(documents)
    try:
        vec = TfidfVectorizer(min_df=1, max_df=1.0)
        mat = vec.fit_transform([query, *documents])
        row = linear_kernel(mat[0:1], mat[1:])[0]
        return [float(x) for x in row]
    except ValueError:
        return [0.0] * len(documents)


def tfidf_cosine(a: str, b: str) -> float:
    """Cosine similarity of two texts; ``0.0`` if vectors cannot be built.

    ``TfidfVectorizer`` L2-normalizes rows, so cosine equals the sparse dot
    product (``linear_kernel``) — same numbers as ``cosine_similarity``.
    """
    if not a.strip() or not b.strip():
        return 0.0
    try:
        vec = TfidfVectorizer(min_df=1, max_df=1.0)
        mat = vec.fit_transform([a, b])
        return float(linear_kernel(mat[0:1], mat[1:2])[0, 0])
    except ValueError:
        return 0.0


def tfidf_similarity_matrix(texts: list[str]) -> Any | None:
    """Pairwise cosine matrix for ``texts``, or ``None`` if unfit."""
    if len(texts) < 2:
        return None
    try:
        vec = TfidfVectorizer(min_df=1, max_df=1.0)
        mat = vec.fit_transform(texts)
        return linear_kernel(mat)
    except ValueError:
        return None
