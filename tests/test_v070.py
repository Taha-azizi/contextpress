"""0.7.0: lexical hash matcher, elapsed_ms, lazy NLTK."""

from __future__ import annotations

import tiktoken

from contextpress import ContextManager
from contextpress.stats import CompressionStats
from contextpress.strategies.lexical import (
    apply_lexical_text,
    compile_mapping_pattern,
    load_lexical_dict,
)
from contextpress.text_sim import tfidf_cosine, tfidf_similarity_matrix


def test_elapsed_ms_on_stats() -> None:
    cm = ContextManager(type="chat", compression="low")
    result = cm.compress(
        [{"role": "user", "content": "Please utilise the API due to the fact that we can."}],
        token_budget=None,
        return_stats=True,
    )
    assert result.stats.elapsed_ms is not None
    assert result.stats.elapsed_ms >= 0
    assert result.stats.elapsed_ms_by_stage
    assert set(result.stats.elapsed_ms_by_stage) == set(result.stats.stages_run)
    d = result.stats.to_dict()
    assert "elapsed_ms" in d
    assert "elapsed_ms_by_stage" in d
    assert "elapsed:" in result.summary()


def test_to_dict_includes_timing_defaults() -> None:
    d = CompressionStats().to_dict()
    assert d["elapsed_ms"] is None
    assert d["elapsed_ms_by_stage"] == {}


def test_unigram_plan_matches_giant_regex() -> None:
    mapping = load_lexical_dict("cl100k_base")
    sample = {k: mapping[k] for i, k in enumerate(mapping) if i % 400 == 0}
    text = "Please " + " ".join(sample) + " leftover words utilise the API."
    enc = tiktoken.get_encoding("cl100k_base")
    via_regex = apply_lexical_text(
        text, sample, encoding=enc, pattern=compile_mapping_pattern(sample)
    )
    via_plan = apply_lexical_text(text, sample, encoding=enc)
    assert via_plan == via_regex


def test_tfidf_linear_kernel_is_cosine() -> None:
    a = "elephants in africa eat leaves"
    b = "elephants and wildlife in africa"
    score = tfidf_cosine(a, b)
    assert 0.0 < score <= 1.0 + 1e-9
    mat = tfidf_similarity_matrix([a, b])
    assert mat is not None
    assert abs(float(mat[0, 1]) - score) < 1e-9
