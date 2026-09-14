"""Prefix-cache vs compression cost tradeoff."""

from __future__ import annotations

import pytest

from contextpress.costs import compare_cache_tradeoff


def test_low_savings_lose_to_anthropic_cache():
    # 6% token cut vs 50% of the prompt already cached at 0.1x.
    t = compare_cache_tradeoff(10_000, 9_400, cache_hit_rate=0.5, cache_read_multiplier=0.1)
    assert t.compress_is_cheaper is False
    assert t.break_even_cache_hit_rate is not None
    assert t.break_even_cache_hit_rate == pytest.approx(0.0667, abs=0.001)


def test_medium_savings_beat_low_cache_hit():
    t = compare_cache_tradeoff(10_000, 5_200, cache_hit_rate=0.2, cache_read_multiplier=0.1)
    assert t.compress_is_cheaper is True


def test_medium_loses_when_most_of_prompt_is_cached():
    t = compare_cache_tradeoff(10_000, 5_200, cache_hit_rate=0.8, cache_read_multiplier=0.1)
    assert t.compress_is_cheaper is False


def test_no_cache_compression_always_cheaper_if_smaller():
    t = compare_cache_tradeoff(10_000, 5_200, cache_hit_rate=0.0, cache_read_multiplier=0.1)
    assert t.compress_is_cheaper is True
