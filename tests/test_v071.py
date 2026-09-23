"""0.7.1: warm-call caches and faster alias candidate scanning."""

from __future__ import annotations

from contextpress.models import Conversation, Turn
from contextpress.stats import ConversationTokenCounter, get_encoding
from contextpress.strategies.alias import (
    _candidate_ok,
    _candidate_window_ok,
    _looks_like_name,
)
from contextpress.strategies.lexical import load_rewrite_plan


def test_conversation_token_counter_reuses_unchanged_clones() -> None:
    counter = ConversationTokenCounter(get_encoding(None))
    original = Conversation(
        turns=[
            Turn(role="user", content="Keep this exact text."),
            Turn(role="assistant", content="And keep this response."),
        ]
    )
    cloned = Conversation(
        turns=[
            Turn(role="user", content="Keep this exact text."),
            Turn(role="assistant", content="And keep this response."),
        ]
    )

    first = counter.count_conversation(original)
    cache_size = len(counter._cache)
    second = counter.count_conversation(cloned)

    assert second == first
    assert len(counter._cache) == cache_size == 2


def test_bundled_rewrite_plan_is_cached() -> None:
    load_rewrite_plan.cache_clear()
    first = load_rewrite_plan("lexical", "cl100k_base")
    second = load_rewrite_plan("lexical", "cl100k_base")

    assert second is first
    assert load_rewrite_plan.cache_info().hits == 1


def test_fused_alias_candidate_check_matches_previous_checks() -> None:
    samples = [
        "International Business Machines",
        "pull request review",
        "in the middle",
        "word word word",
        "Context Press",
        "application programming interface",
        "to be or not",
        "a very Long Name",
    ]
    for sample in samples:
        words = sample.split()
        lowers = [word.lower() for word in words]
        expected = _candidate_ok(words) and _looks_like_name(words)
        assert _candidate_window_ok(words, lowers) is expected
