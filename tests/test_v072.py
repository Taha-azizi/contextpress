"""0.7.2: recency sumy component caching, tokens_per_second throughput, and immutability tests."""

from __future__ import annotations

import copy

from contextpress import ContextManager
from contextpress.stats import CompressionStats
from contextpress.strategies.alias import _compile_alias_patterns, apply_aliases_to_text
from contextpress.strategies.filler import _cleanup_after_filler
from contextpress.strategies.recency import _get_sumy_components, _summarize_text


def test_recency_cached_sumy_components_match_fresh() -> None:
    from sumy.nlp.tokenizers import Tokenizer
    from sumy.parsers.plaintext import PlaintextParser
    from sumy.summarizers.lsa import LsaSummarizer

    text = (
        "The Apollo program was conceived during the presidency of Dwight D. Eisenhower. "
        "It was later dedicated to President John F. Kennedy's national goal of landing "
        "a man on the Moon. "
        "Project Apollo was the third United States human spaceflight program carried out by NASA. "
        "It succeeded in landing the first humans on the Moon in July 1969 with Apollo 11."
    )

    fresh_tok = Tokenizer("english")
    fresh_sumr = LsaSummarizer()
    expected_sents = fresh_sumr(PlaintextParser.from_string(text, fresh_tok).document, 2)
    expected = " ".join(str(s) for s in expected_sents)

    actual = _summarize_text(text, 2)
    assert actual == expected

    # Verify _get_sumy_components returns cached singletons
    tok1, sumr1 = _get_sumy_components()
    tok2, sumr2 = _get_sumy_components()
    assert tok1 is tok2
    assert sumr1 is sumr2


def test_alias_compiled_patterns_match_uncompiled() -> None:
    aliases = [("Context Press", "CP"), ("Large Language Model", "LLM")]
    text = (
        "Context Press is designed for Large Language Model pipelines. "
        "Context Press makes Large Language Model contexts smaller."
    )

    compiled = _compile_alias_patterns(aliases)
    seen_uncompiled: dict[str, bool] = {}
    seen_compiled: dict[str, bool] = {}

    res_uncompiled = apply_aliases_to_text(text, aliases, seen_uncompiled)
    res_compiled = apply_aliases_to_text(text, compiled, seen_compiled)

    assert res_compiled == res_uncompiled
    assert "Context Press (CP)" in res_compiled
    assert "Large Language Model (LLM)" in res_compiled
    assert seen_compiled == seen_uncompiled


def test_tokens_per_second_on_compression_stats() -> None:
    stats = CompressionStats(tokens_before=1000, elapsed_ms=50.0)
    # 1000 tokens in 0.05 seconds = 20,000 tokens/sec
    assert stats.tokens_per_second == 20000.0

    d = stats.to_dict()
    assert d["tokens_per_second"] == 20000.0

    # None or zero elapsed_ms produces None without error
    empty = CompressionStats()
    assert empty.tokens_per_second is None
    assert empty.to_dict()["tokens_per_second"] is None

    zero_ms = CompressionStats(tokens_before=500, elapsed_ms=0.0)
    assert zero_ms.tokens_per_second is None


def test_filler_cleanup_precompiled_regexes() -> None:
    dirty = "   ,  hello  world , ,  how are you ?   "
    clean = _cleanup_after_filler(dirty)
    assert clean == "Hello world, how are you?"


def test_input_messages_immutability_audit_t1() -> None:
    """Audit T1: ensure input messages structure and dicts are strictly untouched."""
    cm = ContextManager(type="chat", compression="medium")
    original_messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Please utilise the application programming interface."},
        {"role": "assistant", "content": "Got it, I will definitely help you with that!"},
        {"role": "user", "content": "What is the final decision?"},
    ]
    snapshot = copy.deepcopy(original_messages)

    result = cm.compress(original_messages, return_stats=True)
    assert original_messages == snapshot, "compress() mutated input messages!"
    assert result.messages is not original_messages
