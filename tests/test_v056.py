from unittest.mock import MagicMock

import pytest

from contextpress import ContextManager
from contextpress.text_sim import tfidf_cosine, tfidf_similarity_matrix


def test_tfidf_cosine_identical():
    assert tfidf_cosine("hello world", "hello world") == pytest.approx(1.0)


def test_tfidf_cosine_empty():
    assert tfidf_cosine("", "hello") == 0.0


def test_tfidf_similarity_matrix_shape():
    mat = tfidf_similarity_matrix(["alpha beta", "alpha gamma", "unrelated words here"])
    assert mat is not None
    assert mat.shape == (3, 3)


def test_llm_dedup_failure_emits_warning():
    backend = MagicMock()
    backend.deduplicate.side_effect = RuntimeError("boom")

    cm = ContextManager(
        type="chat",
        llm_backend=backend,
        llm_min_input_chars=1,
        llm_mode="dedupe_only",
    )
    messages = [
        {"role": "user", "content": "first turn about databases"},
        {"role": "assistant", "content": "second turn about databases"},
    ]
    result = cm.compress(messages, token_budget=None, return_stats=True)
    assert any("LLM deduplicate failed" in w for w in result.stats.warnings_emitted)
    assert len(result.messages) == 2
