from contextpress import ContextManager
from contextpress.stats import CompressionStats


def test_token_savings_pct():
    stats = CompressionStats(tokens_before=100, tokens_after=60)
    assert stats.token_savings_pct == 40.0
    assert stats.to_dict()["token_savings_pct"] == 40.0


def test_token_savings_pct_zero_when_empty():
    stats = CompressionStats(tokens_before=0, tokens_after=0)
    assert stats.token_savings_pct == 0.0


def test_recommend_preset_picks_mildest_that_fits():
    cm = ContextManager(type="chat")
    messages = [
        {"role": "user", "content": "hello basically there " * 5},
        {"role": "assistant", "content": "sounds good " * 5},
    ]
    budget = 500
    rows = cm.compare_presets(messages, token_budget=budget)
    preset = cm.recommend_preset(messages, token_budget=budget)
    assert rows[preset].tokens_after <= budget
    fitting = [p for p in ("low", "medium", "high") if rows[p].tokens_after <= budget]
    assert preset == fitting[0]


def test_recommend_preset_falls_back_to_most_compression():
    cm = ContextManager(type="chat")
    messages = [{"role": "user", "content": "word " * 500}]
    preset = cm.recommend_preset(messages, token_budget=10)
    rows = cm.compare_presets(messages, token_budget=10)
    assert preset == min(("low", "medium", "high"), key=lambda p: rows[p].tokens_after)


def test_recommend_preset_requires_budget():
    cm = ContextManager(type="chat")
    try:
        cm.recommend_preset([{"role": "user", "content": "hi"}], token_budget=0)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
