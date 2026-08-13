"""0.6.3 — LangChain compress round-trip and output_tokens on cost stats."""

from __future__ import annotations

from contextpress import ContextManager
from contextpress.stats import CompressionStats


class _FakeMsg:
    def __init__(self, typ: str, content: str):
        self.type = typ
        self.content = content


def test_langchain_compress_roundtrip_keeps_object_shape():
    msgs = [
        _FakeMsg("system", "You are a concise assistant."),
        _FakeMsg("human", "Summarize the deploy status for api-v2."),
        _FakeMsg("ai", "Checking logs now."),
    ]
    cm = ContextManager(type="chat", compression="low")
    out = cm.compress(msgs, token_budget=None)
    assert isinstance(out, list)
    assert len(out) >= 1
    assert all(hasattr(m, "content") for m in out)
    assert out[0].type == "system"
    assert out[0].content == "You are a concise assistant."


def test_langchain_dropped_turn_does_not_remap_roles():
    """Index-based denormalize would put later content onto the dropped object's type."""
    msgs = [
        _FakeMsg("system", "sys"),
        _FakeMsg("human", "We've decided on using Monday."),
        _FakeMsg("ai", "Sounds good"),
        _FakeMsg("human", "Please confirm the Monday plan in detail."),
        _FakeMsg("ai", "Confirmed. Monday it is, with the new pipeline."),
    ]
    original = [(m.type, m.content) for m in msgs]
    cm = ContextManager(type="chat", compression="high")
    out = cm.compress(msgs, token_budget=None)
    assert [(m.type, m.content) for m in msgs] == original
    types = [getattr(m, "type", None) for m in out]
    assert types[0] == "system"
    for m in out:
        if getattr(m, "type", None) == "human":
            assert "Sounds good" not in str(m.content)


def test_attach_cost_output_tokens():
    stats = CompressionStats(tokens_before=1_000_000, tokens_after=500_000)
    stats.attach_cost(provider="openai", model="gpt-4o-mini", output_tokens=100_000)
    assert stats.estimated_input_cost_before_usd == 0.15
    assert stats.estimated_input_cost_after_usd == 0.075
    assert stats.estimated_output_tokens == 100_000
    assert stats.estimated_output_cost_usd == 0.06
    assert stats.estimated_total_cost_before_usd == 0.21
    assert stats.estimated_total_cost_after_usd == 0.135
    text = stats.summary()
    assert "est. output cost:" in text
    assert "100000 tokens" in text
    assert "est. total:" in text
    d = stats.to_dict()
    assert d["estimated_output_cost_usd"] == 0.06


def test_attach_cost_zero_output_leaves_output_fields_none():
    stats = CompressionStats(tokens_before=1000, tokens_after=500)
    stats.attach_cost(provider="openai", model="gpt-4o-mini", output_tokens=0)
    assert stats.estimated_output_tokens is None
    assert stats.estimated_output_cost_usd is None
    assert "est. output cost" not in stats.summary()


def test_compress_output_tokens_kwarg():
    cm = ContextManager(type="chat", model="gpt-4o-mini", cost_provider="openai")
    result = cm.compress(
        [{"role": "user", "content": "hello " * 40}],
        token_budget=None,
        return_stats=True,
        output_tokens=200,
    )
    assert result.stats.estimated_output_tokens == 200
    assert result.stats.estimated_output_cost_usd is not None
    assert result.stats.estimated_total_cost_after_usd is not None
    assert "est. total:" in result.summary()


def test_cost_output_tokens_constructor_default():
    cm = ContextManager(
        type="chat",
        model="gpt-4o-mini",
        cost_provider="openai",
        cost_output_tokens=50,
    )
    result = cm.compress(
        [{"role": "user", "content": "hello " * 20}],
        token_budget=None,
        return_stats=True,
    )
    assert result.stats.estimated_output_tokens == 50
